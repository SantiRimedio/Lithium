"""Shared fixtures: tiny GeoTIFF, NetCDF, and GeoJSON used by dataset tests."""
from __future__ import annotations

import json
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
