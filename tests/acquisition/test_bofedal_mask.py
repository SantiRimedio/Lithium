import numpy as np
import rasterio

from acquisition.bofedal_mask import BofedalMaskConfig, sieve_raster


def test_bofedal_mask_config_defaults():
    cfg = BofedalMaskConfig()
    assert cfg.min_pixels == 10
    assert cfg.aggregate_distance_m == 300.0
    assert cfg.min_area_m2 == 5_000.0
    assert cfg.accept_threshold == 0.50
    assert cfg.dispute_threshold == 0.10


def test_sieve_raster_removes_small_components(tmp_path):
    """Components smaller than min_pixels are zeroed."""
    src_path = tmp_path / "src.tif"
    out_path = tmp_path / "out.tif"
    data = np.zeros((20, 20), dtype=np.uint8)
    # 3x3 blob (9 pixels) — should be removed at min_pixels=10
    data[2:5, 2:5] = 1
    # 5x5 blob (25 pixels) — should be kept
    data[10:15, 10:15] = 1
    transform = rasterio.transform.from_bounds(-67.5, -25.5, -66.5, -24.5, 20, 20)
    with rasterio.open(
        src_path, "w", driver="GTiff", height=20, width=20, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)

    sieve_raster(src_path, out_path, min_pixels=10)

    with rasterio.open(out_path) as src:
        out_data = src.read(1)
    # Small blob is gone; big blob remains.
    assert out_data[2:5, 2:5].sum() == 0
    assert out_data[10:15, 10:15].sum() == 25


def test_polygonize_returns_geodataframe_in_4326(tiny_binary_raster):
    from acquisition.bofedal_mask import polygonize

    gdf = polygonize(tiny_binary_raster)
    assert len(gdf) == 1
    assert gdf.crs.to_epsg() == 4326
    # The polygon should be inside the raster bounds.
    minx, miny, maxx, maxy = gdf.total_bounds
    assert minx >= -67.5 and maxx <= -66.5
    assert miny >= -25.5 and maxy <= -24.5


def test_polygonize_skips_zero_class(tiny_binary_raster):
    """Only value==1 pixels become polygons (zero is background)."""
    from acquisition.bofedal_mask import polygonize

    gdf = polygonize(tiny_binary_raster)
    # All polygons should have raster_value == 1.
    assert (gdf["raster_value"] == 1).all()
