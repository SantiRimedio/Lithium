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
import rasterio
from rasterio.features import shapes as rio_shapes, sieve
from shapely.geometry import shape


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
