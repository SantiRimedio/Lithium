"""Tests for panel.ndvi — Landsat C2 SR NDVI extraction."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_landsat_collection_for_year_picks_right_sensors(mocker):
    """Landsat 5 covers 1998-2012; L7 covers 1999-2013; L8 covers 2013+; L9 covers 2021+."""
    from panel.ndvi import _landsat_collection_for_window

    coll_mock = mocker.MagicMock(name="CombinedCollection")
    ic_mock = mocker.patch("ee.ImageCollection", return_value=coll_mock)
    coll_mock.merge.return_value = coll_mock
    coll_mock.filterBounds.return_value = coll_mock
    coll_mock.filterDate.return_value = coll_mock

    region = mocker.MagicMock(name="Region")
    _landsat_collection_for_window(
        start="2010-12-01", end="2011-02-28", region=region,
    )

    asset_calls = [c.args[0] for c in ic_mock.call_args_list]
    assert "LANDSAT/LT05/C02/T1_L2" in asset_calls
    assert "LANDSAT/LE07/C02/T1_L2" in asset_calls
    assert "LANDSAT/LC08/C02/T1_L2" not in asset_calls


def test_landsat_collection_for_year_post_2013_uses_l8(mocker):
    from panel.ndvi import _landsat_collection_for_window

    coll_mock = mocker.MagicMock(name="CombinedCollection")
    ic_mock = mocker.patch("ee.ImageCollection", return_value=coll_mock)
    coll_mock.merge.return_value = coll_mock
    coll_mock.filterBounds.return_value = coll_mock
    coll_mock.filterDate.return_value = coll_mock

    region = mocker.MagicMock(name="Region")
    _landsat_collection_for_window(
        start="2020-12-01", end="2021-02-28", region=region,
    )

    asset_calls = [c.args[0] for c in ic_mock.call_args_list]
    assert "LANDSAT/LC08/C02/T1_L2" in asset_calls
    assert "LANDSAT/LT05/C02/T1_L2" not in asset_calls


def test_extract_year_skips_when_csv_exists(mocker, tmp_path):
    """Idempotency: if the local CSV already exists, do nothing."""
    from panel.ndvi import extract_year

    out_dir = tmp_path / "panel/ndvi_gs"
    out_dir.mkdir(parents=True)
    (out_dir / "2020.csv").write_text("bofedal_id,ndvi_gs_median\n")

    init = mocker.patch("panel.ndvi.initialize")
    export = mocker.patch("panel.ndvi.export_table_to_drive")

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="bofedales_gdf"),
        window="growing_season",
        local_dest=out_dir,
    )

    init.assert_not_called()
    export.assert_not_called()


def test_extract_year_submits_export_with_right_metadata(mocker, tmp_path, tiny_bofedales):
    """When the CSV is missing, submit GEE exports (one per chunk) with the right metadata."""
    from panel.ndvi import extract_year

    out_dir = tmp_path / "panel/ndvi_gs"
    out_dir.mkdir(parents=True)
    mocker.patch("panel.ndvi.initialize")
    mocker.patch("panel.ndvi._puna_region")
    mocker.patch("panel.ndvi._landsat_collection_for_window")
    mocker.patch("panel.ndvi._compute_ndvi_image")
    mocker.patch("panel.ndvi._bofedales_to_fc")
    mocker.patch("panel.ndvi._reduce_to_table")
    # Skip the concat step (no real CSVs land in this unit test).
    mocker.patch("panel.ndvi._concat_chunk_csvs")
    export = mocker.patch(
        "panel.ndvi.export_table_to_drive",
        return_value=out_dir,
    )

    extract_year(
        year=2020,
        bofedales=tiny_bofedales,
        window="growing_season",
        local_dest=out_dir,
    )

    # Chunked: one export per chunk. tiny_bofedales has 3 polys; with _N_CHUNKS=8
    # the helper yields 3 single-polygon chunks.
    assert export.call_count >= 1
    kw = export.call_args_list[0].kwargs
    assert kw["description"].startswith("ndvi_gs_2020_chunk_")
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_panel_ndvi_gs"
    assert kw["file_prefix"].startswith("2020_chunk_")
    assert kw["local_dest"] == out_dir


def test_window_for_growing_season_uses_austral_summer():
    """Dec y-1 -> Feb y."""
    from panel.ndvi import _window_dates

    start, end = _window_dates(year=2020, window="growing_season")
    assert start == "2019-12-01"
    assert end == "2020-02-29"  # 2020 is a leap year


def test_window_for_annual_uses_calendar_year():
    from panel.ndvi import _window_dates

    start, end = _window_dates(year=2020, window="annual")
    assert start == "2020-01-01"
    assert end == "2020-12-31"
