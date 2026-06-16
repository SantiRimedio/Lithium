"""Bofedal-mask orchestrator: sieve → polygonize → aggregate-300m → reconcile → emit.

Inputs (binary rasters):
- MapBiomas-derived stable-bofedal raster (primary)
- Zenodo 2026 high-probability mask, Puna-extracted (reference)

Output:
- Data/bofedales_v2.geojson — accepted polygons (committed)
- Data/bofedales_v2_disputed.geojson — disputed companion (committed)
"""
from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes as rio_shapes, sieve
from scipy.sparse import lil_matrix
from scipy.sparse.csgraph import connected_components
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.strtree import STRtree


_METRIC_CRS = "EPSG:32719"  # UTM Zone 19S, covers Argentine Puna
_BOFEDAL_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class BofedalMaskConfig:
    min_pixels: int = 10                    # sieve cutoff (≈ 0.9 ha at 30 m)
    aggregate_distance_m: float = 300.0     # Izquierdo aggregate-polygons-300m
    min_area_m2: float = 5_000.0            # post-aggregate filter (~0.5 ha)
    accept_threshold: float = 0.50          # >= → accepted
    dispute_threshold: float = 0.10         # [dispute, accept) → disputed; below → dropped


def sieve_raster(src_path: Path, dst_path: Path, *, min_pixels: int) -> None:
    """rasterio.features.sieve wrapper: remove components below min_pixels."""
    with rasterio.open(src_path) as src:
        data = src.read(1)
        sieved = sieve(data, size=min_pixels)
        profile = src.profile.copy()
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(sieved, 1)


def polygonize(raster_path: Path) -> gpd.GeoDataFrame:
    """Vectorize a binary raster. Returns polygons for value==1 only."""
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        transform = src.transform
        crs = src.crs

    geoms = []
    values = []
    for geom_dict, value in rio_shapes(data, mask=(data == 1), transform=transform):
        geoms.append(shape(geom_dict))
        values.append(int(value))

    return gpd.GeoDataFrame(
        {"raster_value": values, "geometry": geoms},
        crs=crs,
    )


def aggregate_300m(gdf: gpd.GeoDataFrame, *, distance_m: float = 300.0) -> gpd.GeoDataFrame:
    """Merge polygons whose nearest-point distance is < distance_m.

    Algorithm: buffer each polygon by distance/2 in a metric CRS, build a
    spatial graph of pairwise intersections of the buffers, find connected
    components, and dissolve the ORIGINAL (un-buffered) polygons in each
    component. Returns a GeoDataFrame in the input CRS.
    """
    if len(gdf) == 0:
        return gdf.copy()

    input_crs = gdf.crs
    metric = gdf.to_crs(_METRIC_CRS)
    buffered = metric.geometry.buffer(distance_m / 2.0)

    tree = STRtree(list(buffered))
    n = len(buffered)
    adj = lil_matrix((n, n), dtype=bool)
    for i, geom in enumerate(buffered):
        for j in tree.query(geom):
            if i == j:
                continue
            if buffered.iloc[i].intersects(buffered.iloc[j]):
                adj[i, j] = True
                adj[j, i] = True

    n_components, labels = connected_components(adj.tocsr(), directed=False)

    dissolved_geoms = []
    for comp_id in range(n_components):
        idxs = np.where(labels == comp_id)[0]
        comp_geoms = [metric.geometry.iloc[i] for i in idxs]
        dissolved_geoms.append(unary_union(comp_geoms))

    out = gpd.GeoDataFrame(
        {"raster_value": [1] * len(dissolved_geoms), "geometry": dissolved_geoms},
        crs=_METRIC_CRS,
    )
    return out.to_crs(input_crs)


def reconcile(
    primary: gpd.GeoDataFrame,
    reference: gpd.GeoDataFrame,
    *,
    accept_threshold: float = 0.50,
    dispute_threshold: float = 0.10,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Classify primary polygons by their area-weighted overlap with reference.

    Returns (accepted, disputed). Polygons with overlap < dispute_threshold are
    dropped (not returned).
    """
    if primary.crs != reference.crs:
        reference = reference.to_crs(primary.crs)

    ref_tree = STRtree(list(reference.geometry))
    overlaps = []
    for prim in primary.geometry:
        total_overlap_area = 0.0
        for j in ref_tree.query(prim):
            ref_geom = reference.geometry.iloc[j]
            if prim.intersects(ref_geom):
                total_overlap_area += prim.intersection(ref_geom).area
        ratio = total_overlap_area / prim.area if prim.area > 0 else 0.0
        overlaps.append(ratio)

    out = primary.copy()
    out["overlap_with_reference"] = overlaps

    accepted = out[out["overlap_with_reference"] >= accept_threshold].copy()
    disputed = out[
        (out["overlap_with_reference"] >= dispute_threshold)
        & (out["overlap_with_reference"] < accept_threshold)
    ].copy()
    return accepted, disputed


def _assign_bofedal_ids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out["bofedal_id"] = [
        str(uuid.uuid5(_BOFEDAL_NAMESPACE, geom.wkt))
        for geom in out.geometry
    ]
    return out


def _filter_min_area(gdf: gpd.GeoDataFrame, min_area_m2: float) -> gpd.GeoDataFrame:
    if min_area_m2 <= 0 or len(gdf) == 0:
        return gdf
    metric = gdf.to_crs(_METRIC_CRS)
    keep = metric.geometry.area >= min_area_m2
    return gdf[keep].copy()


def _prepare_polygons(
    raster: Path, cfg: BofedalMaskConfig
) -> gpd.GeoDataFrame:
    """Run sieve → polygonize → aggregate_300m → min-area filter on one raster."""
    with tempfile.TemporaryDirectory() as tmp:
        sieved = Path(tmp) / "sieved.tif"
        sieve_raster(raster, sieved, min_pixels=cfg.min_pixels)
        gdf = polygonize(sieved)
    if len(gdf) == 0:
        return gdf
    gdf = aggregate_300m(gdf, distance_m=cfg.aggregate_distance_m)
    gdf = _filter_min_area(gdf, cfg.min_area_m2)
    return gdf


def build_mask(
    primary_raster: Path,
    reference_raster: Path | None,
    accepted_out: Path,
    disputed_out: Path | None = None,
    config: BofedalMaskConfig | None = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Run the bofedal-mask pipeline and write the GeoJSON(s).

    If ``reference_raster`` is None, skip the two-mask reconciliation step
    and treat the primary mask as authoritative (every primary polygon goes
    to ``accepted_out``; an empty disputed frame is returned but not
    written unless ``disputed_out`` is provided).

    Returns the (accepted, disputed) GeoDataFrames for convenience.
    """
    cfg = config or BofedalMaskConfig()

    primary = _prepare_polygons(primary_raster, cfg)

    if reference_raster is None:
        accepted = primary.copy()
        accepted["overlap_with_reference"] = float("nan")
        disputed = primary.iloc[0:0].copy()
        disputed["overlap_with_reference"] = float("nan")
    else:
        reference = _prepare_polygons(reference_raster, cfg)
        accepted, disputed = reconcile(
            primary, reference,
            accept_threshold=cfg.accept_threshold,
            dispute_threshold=cfg.dispute_threshold,
        )

    accepted = _assign_bofedal_ids(accepted)
    disputed = _assign_bofedal_ids(disputed)

    accepted_out.parent.mkdir(parents=True, exist_ok=True)
    accepted.to_file(accepted_out, driver="GeoJSON")
    if disputed_out is not None:
        disputed_out.parent.mkdir(parents=True, exist_ok=True)
        disputed.to_file(disputed_out, driver="GeoJSON")
    return accepted, disputed
