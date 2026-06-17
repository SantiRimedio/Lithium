"""Tests for panel.static_attrs — elevation + USGS salar join."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest


def test_extract_elevation_submits_srtm_export(mocker, tmp_path):
    """Elevation pulls SRTM mean per bofedal via reduceRegions."""
    from panel.static_attrs import extract_elevation

    mocker.patch("panel.static_attrs.initialize")
    img_mock = mocker.MagicMock(name="SRTMImage")
    image_factory = mocker.patch("ee.Image", return_value=img_mock)
    mocker.patch("panel.static_attrs._bofedales_to_fc")
    mocker.patch("panel.static_attrs._reduce_to_table")
    export = mocker.patch(
        "panel.static_attrs.export_table_to_drive",
        return_value=tmp_path,
    )

    extract_elevation(bofedales=mocker.MagicMock(), local_dest=tmp_path)

    image_factory.assert_called_with("USGS/SRTMGL1_003")
    kw = export.call_args.kwargs
    assert kw["file_prefix"] == "elevation"
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_panel_elevation"


def test_extract_containing_salar_largest_overlap_wins(tiny_bofedales, tiny_salars, tmp_path):
    """Each bofedal is assigned the salar with the largest intersection area."""
    from panel.static_attrs import extract_containing_salar_from_layer

    salars_gdf = gpd.read_file(tiny_salars)

    df = extract_containing_salar_from_layer(
        bofedales=tiny_bofedales,
        salars=salars_gdf,
    )

    assert set(df.columns) == {"bofedal_id", "containing_salar"}
    assert len(df) == 3
    expected = {
        "11111111-1111-5111-8111-111111111111": "Salar A",
        "22222222-2222-5222-8222-222222222222": "Salar B",
        "33333333-3333-5333-8333-333333333333": None,
    }
    for bid, want in expected.items():
        got = df.loc[df["bofedal_id"] == bid, "containing_salar"].iloc[0]
        if want is None:
            assert got is None or (isinstance(got, float) and got != got)
        else:
            assert got == want


def test_unpack_usgs_archive_idempotent(mocker, tmp_path):
    """If the extracted directory already has content, do not re-unpack."""
    from panel.static_attrs import unpack_usgs_archive

    target = tmp_path / "extracted"
    target.mkdir()
    (target / "marker.txt").touch()

    unpack = mocker.patch("py7zr.unpack_7zarchive")

    unpack_usgs_archive(
        archive=tmp_path / "usgs.gdb.7z",
        target_dir=target,
    )

    unpack.assert_not_called()


def test_unpack_usgs_archive_calls_py7zr_on_missing(mocker, tmp_path):
    from panel.static_attrs import unpack_usgs_archive

    target = tmp_path / "extracted"
    archive = tmp_path / "usgs.gdb.7z"
    archive.touch()

    unpack = mocker.patch("py7zr.unpack_7zarchive")

    unpack_usgs_archive(archive=archive, target_dir=target)

    unpack.assert_called_once_with(str(archive), str(target))
