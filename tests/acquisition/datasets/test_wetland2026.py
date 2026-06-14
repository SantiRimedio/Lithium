from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.wetland2026 import Wetland2026Dataset


@pytest.fixture
def tiny_geotiff(tmp_path: Path) -> Path:
    """Fine-resolution raster over a Puna superset.

    Overrides the shared 20x20 global fixture (conftest) because its
    9-degree pixels are far coarser than the 0.01-degree bounds tolerance
    asserted below, so a window-based clip can't satisfy it.
    """
    path = tmp_path / "tiny.tif"
    west, south, east, north = -75.0, -30.0, -60.0, -20.0
    px = 0.005  # well within the 0.01-degree tolerance after pixel-snapping
    width = int(round((east - west) / px))
    height = int(round((north - south) / px))
    data = (np.arange(height * width, dtype=np.uint8) % 7).reshape(height, width)
    transform = from_bounds(west, south, east, north, width, height)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=height, width=width, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)
    return path


def test_wetland_clip_writes_subset_with_puna_bounds(tiny_geotiff, tmp_path):
    ds = Wetland2026Dataset(url="https://example.com/wetland.tif")
    out = ds.clip(tiny_geotiff, tmp_path, PUNA_BBOX)

    assert out == tmp_path / "puna" / "wetland_puna.tif"
    assert out.exists()
    with rasterio.open(out) as src:
        b = src.bounds
        # Clipped bounds must lie within the Puna bbox (rounded to pixel grid).
        assert b.left >= PUNA_BBOX.west - 0.01
        assert b.right <= PUNA_BBOX.east + 0.01
        assert b.bottom >= PUNA_BBOX.south - 0.01
        assert b.top <= PUNA_BBOX.north + 0.01
        assert src.width > 0 and src.height > 0


def test_wetland_clip_idempotent(tiny_geotiff, tmp_path):
    ds = Wetland2026Dataset(url="https://example.com/wetland.tif")
    out1 = ds.clip(tiny_geotiff, tmp_path, PUNA_BBOX)
    mtime1 = out1.stat().st_mtime_ns
    out2 = ds.clip(tiny_geotiff, tmp_path, PUNA_BBOX)
    assert out2 == out1
    assert out2.stat().st_mtime_ns == mtime1  # not rewritten


def test_extract_puna_tif_filters_outside_tifs(tiny_zip_with_tifs, tmp_path):
    """Only TIFs whose bbox intersects PUNA_BBOX are mosaicked into the output."""
    ds = Wetland2026Dataset(url="https://example.com/wetland.zip")
    out = ds.extract_puna_tif(tiny_zip_with_tifs, tmp_path)

    assert out == tmp_path / "puna" / "wetland_puna.tif"
    assert out.exists()
    with rasterio.open(out) as src:
        # Bounds should match the "inside.tif" (Puna-overlapping fixture).
        assert src.bounds.left >= -68.0 and src.bounds.right <= -66.0
        assert src.bounds.bottom >= -26.0 and src.bounds.top <= -24.0


def test_extract_puna_tif_idempotent(tiny_zip_with_tifs, tmp_path):
    ds = Wetland2026Dataset(url="https://example.com/wetland.zip")
    out1 = ds.extract_puna_tif(tiny_zip_with_tifs, tmp_path)
    mtime1 = out1.stat().st_mtime_ns
    out2 = ds.extract_puna_tif(tiny_zip_with_tifs, tmp_path)
    assert out2 == out1
    assert out2.stat().st_mtime_ns == mtime1
