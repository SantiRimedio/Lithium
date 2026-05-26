from acquisition.aoi import BBox, PUNA_BBOX


def test_bbox_is_frozen_dataclass():
    bb = BBox(west=-10, south=-5, east=10, north=5)
    assert (bb.west, bb.south, bb.east, bb.north) == (-10, -5, 10, 5)
    import dataclasses
    assert dataclasses.is_dataclass(bb)


def test_bbox_rejects_inverted_bounds():
    import pytest
    with pytest.raises(ValueError, match="west .* east"):
        BBox(west=10, south=-5, east=-10, north=5)
    with pytest.raises(ValueError, match="south .* north"):
        BBox(west=-10, south=5, east=10, north=-5)


def test_puna_bbox_covers_argentine_puna():
    # The Argentine Puna spans roughly 22S-27S latitude, 65W-69W longitude.
    assert PUNA_BBOX.west <= -68.0
    assert PUNA_BBOX.east >= -66.0
    assert PUNA_BBOX.south <= -26.0
    assert PUNA_BBOX.north >= -23.0


def test_puna_basins_loads_endorheic_geojson():
    from acquisition.aoi import puna_basins

    gdf = puna_basins()
    assert len(gdf) > 0
    assert gdf.crs is not None
    # Basins must intersect the Puna bbox.
    from acquisition.aoi import PUNA_BBOX
    minx, miny, maxx, maxy = gdf.total_bounds
    assert maxx >= PUNA_BBOX.west and minx <= PUNA_BBOX.east
    assert maxy >= PUNA_BBOX.south and miny <= PUNA_BBOX.north
