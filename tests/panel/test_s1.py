"""Tests for panel.s1 — Sentinel-1 GRD backscatter extraction."""
from __future__ import annotations

import pytest


def test_extract_year_skips_pre_2014():
    """Sentinel-1 GRD doesn't exist before 2014; raise loudly."""
    from panel.s1 import extract_year

    with pytest.raises(ValueError, match="2014"):
        extract_year(year=2013, bofedales=None, polarization="VV", local_dest=None)


def test_extract_year_skips_when_csv_exists(mocker, tmp_path):
    from panel.s1 import extract_year

    out_dir = tmp_path / "panel/s1_vv"
    out_dir.mkdir(parents=True)
    (out_dir / "2020.csv").write_text("bofedal_id,s1_vv_db_median\n")

    init = mocker.patch("panel.s1.initialize")
    export = mocker.patch("panel.s1.export_table_to_drive")

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(),
        polarization="VV",
        local_dest=out_dir,
    )
    init.assert_not_called()
    export.assert_not_called()


def test_extract_year_filters_to_descending_iw(mocker, tmp_path):
    """Verify the S1 collection is filtered to IW + descending + the right polarization."""
    from panel.s1 import extract_year

    out_dir = tmp_path / "panel/s1_vv"
    mocker.patch("panel.s1.initialize")
    mocker.patch("panel.s1._puna_region")
    coll_mock = mocker.MagicMock(name="S1Collection")
    coll_mock.filterBounds.return_value = coll_mock
    coll_mock.filterDate.return_value = coll_mock
    coll_mock.filter.return_value = coll_mock
    coll_mock.select.return_value = coll_mock
    mocker.patch("ee.ImageCollection", return_value=coll_mock)
    mocker.patch("panel.s1._bofedales_to_fc")
    mocker.patch("panel.s1._reduce_to_table")
    mocker.patch("panel.s1.export_table_to_drive", return_value=out_dir)

    filter_eq = mocker.patch("ee.Filter.eq", side_effect=lambda *args: ("eq", args))
    filter_list_contains = mocker.patch(
        "ee.Filter.listContains", side_effect=lambda *args: ("contains", args)
    )

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="gdf"),
        polarization="VV",
        local_dest=out_dir,
    )

    filter_args = [c.args for c in filter_eq.call_args_list]
    list_args = [c.args for c in filter_list_contains.call_args_list]
    assert ("instrumentMode", "IW") in filter_args
    assert ("orbitProperties_pass", "DESCENDING") in filter_args
    assert ("transmitterReceiverPolarisation", "VV") in list_args


def test_extract_year_export_description_includes_polarization(mocker, tmp_path):
    from panel.s1 import extract_year

    out_dir = tmp_path / "panel/s1_vh"
    mocker.patch("panel.s1.initialize")
    mocker.patch("panel.s1._puna_region")
    coll = mocker.MagicMock()
    coll.filterBounds.return_value = coll
    coll.filterDate.return_value = coll
    coll.filter.return_value = coll
    coll.select.return_value = coll
    mocker.patch("ee.ImageCollection", return_value=coll)
    mocker.patch("panel.s1._bofedales_to_fc")
    mocker.patch("panel.s1._reduce_to_table")
    mocker.patch("ee.Filter.eq")
    mocker.patch("ee.Filter.listContains")
    export = mocker.patch("panel.s1.export_table_to_drive", return_value=out_dir)

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="gdf"),
        polarization="VH",
        local_dest=out_dir,
    )

    kw = export.call_args.kwargs
    assert kw["description"] == "s1_vh_2020"
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_panel_s1_vh"
