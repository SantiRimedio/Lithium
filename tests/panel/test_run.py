"""Tests for panel.run — CLI driver."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_extract_calls_ndvi_and_s1_per_year(mocker, tmp_path, tiny_bofedales_path):
    from panel.run import run_extract

    ndvi = mocker.patch("panel.ndvi.extract_year")
    s1 = mocker.patch("panel.s1.extract_year")

    run_extract(
        bofedales_path=tiny_bofedales_path,
        outcomes={"ndvi", "s1"},
        years=range(2014, 2017),
        external_root=tmp_path,
    )

    assert ndvi.call_count == 6
    assert s1.call_count == 6


def test_extract_skips_pre_2014_for_s1(mocker, tmp_path, tiny_bofedales_path):
    from panel.run import run_extract

    ndvi = mocker.patch("panel.ndvi.extract_year")
    s1 = mocker.patch("panel.s1.extract_year")

    run_extract(
        bofedales_path=tiny_bofedales_path,
        outcomes={"ndvi", "s1"},
        years=range(2012, 2015),
        external_root=tmp_path,
    )

    assert ndvi.call_count == 6
    assert s1.call_count == 2


def test_compose_calls_static_extracts_and_writes_parquet(mocker, tmp_path, tiny_bofedales_path):
    from panel.run import run_compose

    spei_df_12 = pd.DataFrame(columns=["bofedal_id", "year", "spei_12_gs_mean"])
    spei_df_24 = pd.DataFrame(columns=["bofedal_id", "year", "spei_24_gs_mean"])
    elevation_df = pd.DataFrame(columns=["bofedal_id", "mean"])
    salar_df = pd.DataFrame(columns=["bofedal_id", "containing_salar"])

    spei_extract = mocker.patch(
        "panel.spei.extract",
        side_effect=[spei_df_12, spei_df_24],
    )
    mocker.patch("panel.static_attrs.extract_elevation")
    mocker.patch("panel.static_attrs.unpack_usgs_archive")
    mocker.patch(
        "panel.static_attrs.extract_containing_salar_from_layer",
        return_value=salar_df,
    )
    mocker.patch(
        "panel.run._load_usgs_salars",
        return_value=mocker.MagicMock(),
    )
    mocker.patch(
        "panel.run._load_elevation_csv",
        return_value=elevation_df,
    )

    compose = mocker.patch(
        "panel.compose.compose_panel",
        return_value=tmp_path / "bofedal_panel.parquet",
    )

    run_compose(
        bofedales_path=tiny_bofedales_path,
        years=range(2014, 2016),
        external_root=tmp_path,
        repo_root=tmp_path / "_repo",
    )

    assert spei_extract.call_count == 2
    compose.assert_called_once()
