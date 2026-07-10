"""Shared fixtures: tiny GeoTIFF, NetCDF, and GeoJSON used by dataset tests."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
import xarray as xr
from rasterio.transform import from_bounds


@pytest.fixture
def tiny_geotiff(tmp_path: Path) -> Path:
    """A 20x20 EPSG:4326 raster covering -90..90, -90..90."""
    path = tmp_path / "tiny.tif"
    height, width = 20, 20
    data = (np.arange(height * width, dtype=np.uint8) % 7).reshape(height, width)
    transform = from_bounds(-90, -90, 90, 90, width, height)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=height, width=width, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)
    return path


@pytest.fixture
def tiny_netcdf(tmp_path: Path) -> Path:
    """A 0.5-degree SPEI-like NetCDF covering the globe, 12 months."""
    path = tmp_path / "tiny.nc"
    lons = np.arange(-179.75, 180.0, 0.5)
    lats = np.arange(-89.75, 90.0, 0.5)
    times = np.array([np.datetime64(f"2020-{m:02d}-01") for m in range(1, 13)])
    data = np.random.default_rng(0).standard_normal((len(times), len(lats), len(lons))).astype("float32")
    ds = xr.Dataset(
        {"spei": (("time", "lat", "lon"), data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds.to_netcdf(path)
    return path


@pytest.fixture
def tiny_geojson(tmp_path: Path) -> Path:
    """A 2-polygon GeoJSON inside the Puna bbox."""
    path = tmp_path / "tiny.geojson"
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": 1, "name": "vega-a"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-67.0, -24.0], [-66.9, -24.0],
                        [-66.9, -23.9], [-67.0, -23.9], [-67.0, -24.0],
                    ]],
                },
            },
            {
                "type": "Feature",
                "properties": {"id": 2, "name": "vega-b"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-66.5, -25.0], [-66.4, -25.0],
                        [-66.4, -24.9], [-66.5, -24.9], [-66.5, -25.0],
                    ]],
                },
            },
        ],
    }
    path.write_text(json.dumps(fc))
    return path


@pytest.fixture
def tiny_zip_with_tifs(tmp_path: Path) -> Path:
    """A zip containing two tiny GeoTIFFs: one overlapping PUNA_BBOX, one outside."""
    path = tmp_path / "wetland_maps.zip"

    def make_tif_bytes(west, south, east, north) -> bytes:
        buf = io.BytesIO()
        height, width = 10, 10
        data = np.ones((height, width), dtype=np.uint8)
        transform = from_bounds(west, south, east, north, width, height)
        with rasterio.open(
            buf, "w", driver="GTiff",
            height=height, width=width, count=1,
            dtype="uint8", crs="EPSG:4326", transform=transform,
        ) as dst:
            dst.write(data, 1)
        return buf.getvalue()

    with zipfile.ZipFile(path, "w") as zf:
        # Puna-overlapping (-67, -25 area)
        zf.writestr("inside.tif", make_tif_bytes(-67.5, -25.5, -66.5, -24.5))
        # Far outside Puna (Brazil-ish)
        zf.writestr("outside.tif", make_tif_bytes(-50.0, -10.0, -49.0, -9.0))
    return path


@pytest.fixture
def tiny_binary_raster(tmp_path: Path) -> Path:
    """A small EPSG:4326 binary raster with a 3x3 wetland blob in the Puna bbox.

    Bounds: west=-67.5, south=-25.5, east=-66.5, north=-24.5 (well inside PUNA_BBOX).
    """
    path = tmp_path / "binary.tif"
    height, width = 20, 20
    data = np.zeros((height, width), dtype=np.uint8)
    # Single 3x3 blob centered at (10, 10).
    data[9:12, 9:12] = 1
    transform = from_bounds(-67.5, -25.5, -66.5, -24.5, width, height)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=height, width=width, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)
    return path
