"""Shared fixtures for the panel test suite.

`tiny_bofedales` provides 3 polygons in the Puna bbox with stable
bofedal_id values. Reused across module tests so each module's
expectations stay consistent.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon


_BOFEDAL_IDS = (
    "11111111-1111-5111-8111-111111111111",
    "22222222-2222-5222-8222-222222222222",
    "33333333-3333-5333-8333-333333333333",
)


@pytest.fixture
def tiny_bofedales() -> gpd.GeoDataFrame:
    """Three small square polygons inside PUNA_BBOX with stable UUIDs."""
    polys = [
        Polygon([(-67.0, -24.0), (-66.99, -24.0),
                 (-66.99, -23.99), (-67.0, -23.99)]),
        Polygon([(-66.5, -25.0), (-66.49, -25.0),
                 (-66.49, -24.99), (-66.5, -24.99)]),
        Polygon([(-67.5, -24.5), (-67.49, -24.5),
                 (-67.49, -24.49), (-67.5, -24.49)]),
    ]
    return gpd.GeoDataFrame(
        {"bofedal_id": list(_BOFEDAL_IDS), "geometry": polys},
        crs="EPSG:4326",
    )


@pytest.fixture
def tiny_bofedales_path(tiny_bofedales, tmp_path: Path) -> Path:
    """The same fixture written to disk as GeoJSON."""
    path = tmp_path / "tiny_bofedales.geojson"
    tiny_bofedales.to_file(path, driver="GeoJSON")
    return path


@pytest.fixture
def tiny_salars(tmp_path: Path) -> Path:
    """Two synthetic salar polygons covering known territory.

    Salar A covers bofedales[0]; Salar B covers bofedales[1].
    Bofedal[2] is intentionally outside any salar.
    """
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"Name": "Salar A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-67.1, -24.1], [-66.9, -24.1],
                        [-66.9, -23.9], [-67.1, -23.9], [-67.1, -24.1],
                    ]],
                },
            },
            {
                "type": "Feature",
                "properties": {"Name": "Salar B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-66.6, -25.1], [-66.4, -25.1],
                        [-66.4, -24.9], [-66.6, -24.9], [-66.6, -25.1],
                    ]],
                },
            },
        ],
    }
    path = tmp_path / "tiny_salars.geojson"
    path.write_text(json.dumps(fc))
    return path
