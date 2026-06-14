"""Bofedal-mask orchestrator: sieve → polygonize → aggregate-300m → reconcile → emit.

Inputs (binary rasters):
- MapBiomas-derived stable-bofedal raster (primary)
- Zenodo 2026 high-probability mask, Puna-extracted (reference)

Output:
- Data/bofedales_v2.geojson — accepted polygons (committed)
- Data/bofedales_v2_disputed.geojson — disputed companion (committed)
"""
from __future__ import annotations

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
