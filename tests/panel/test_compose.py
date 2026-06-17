"""Tests for panel.compose — merge intermediates -> parquet."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_compose_panel_schema_and_row_count(tiny_bofedales, tmp_path):
    """Synthetic intermediates -> parquet has the expected schema and row count."""
    from panel.compose import compose_panel

    bof_path = tmp_path / "bofedales.geojson"
    tiny_bofedales.to_file(bof_path, driver="GeoJSON")

    intermediates = tmp_path / "panel"
    (intermediates / "ndvi_gs").mkdir(parents=True)
    (intermediates / "ndvi_annual").mkdir()
    (intermediates / "s1_vv").mkdir()
    (intermediates / "s1_vh").mkdir()

    ids = list(tiny_bofedales["bofedal_id"])
    for y in (2019, 2020):
        pd.DataFrame({
            "bofedal_id": ids,
            "median": [0.5, 0.6, 0.7],
            "count": [10, 12, 8],
        }).to_csv(intermediates / "ndvi_gs" / f"{y}.csv", index=False)
        pd.DataFrame({
            "bofedal_id": ids,
            "median": [0.4, 0.5, 0.6],
            "count": [20, 22, 18],
        }).to_csv(intermediates / "ndvi_annual" / f"{y}.csv", index=False)
    pd.DataFrame({
        "bofedal_id": ids, "median": [-12.0, -13.5, -14.0], "count": [50, 50, 50],
    }).to_csv(intermediates / "s1_vv" / "2020.csv", index=False)
    pd.DataFrame({
        "bofedal_id": ids, "median": [-18.0, -19.5, -20.0], "count": [50, 50, 50],
    }).to_csv(intermediates / "s1_vh" / "2020.csv", index=False)

    spei12 = pd.DataFrame({"bofedal_id": ids * 2, "year": [2019, 2019, 2019, 2020, 2020, 2020],
                            "spei_12_gs_mean": [0.1] * 6})
    spei24 = pd.DataFrame({"bofedal_id": ids * 2, "year": [2019, 2019, 2019, 2020, 2020, 2020],
                            "spei_24_gs_mean": [0.2] * 6})
    elevation = pd.DataFrame({"bofedal_id": ids, "mean": [3800.0, 3900.0, 4000.0]})
    salar = pd.DataFrame({"bofedal_id": ids,
                           "containing_salar": ["Salar A", "Salar B", None]})

    out = tmp_path / "bofedal_panel.parquet"
    compose_panel(
        bofedales_path=bof_path,
        years=range(2019, 2021),
        ndvi_gs_dir=intermediates / "ndvi_gs",
        ndvi_annual_dir=intermediates / "ndvi_annual",
        s1_vv_dir=intermediates / "s1_vv",
        s1_vh_dir=intermediates / "s1_vh",
        spei12_df=spei12,
        spei24_df=spei24,
        elevation_df=elevation,
        containing_salar_df=salar,
        out_path=out,
    )

    df = pd.read_parquet(out)
    assert set(df.columns) == {
        "bofedal_id", "year",
        "ndvi_gs_median", "ndvi_gs_n_obs",
        "ndvi_annual_median", "ndvi_annual_n_obs",
        "s1_vv_db_median", "s1_vh_db_median", "s1_n_obs",
        "spei_12_gs_mean", "spei_24_gs_mean",
        "elevation_m", "containing_salar",
        "mega_drought_dummy",
    }
    assert len(df) == 3 * 2  # 3 bofedales * 2 years
    row_2019 = df[df["year"] == 2019]
    assert row_2019["s1_vv_db_median"].isna().all()
    assert (row_2019["mega_drought_dummy"] == 0).all()


def test_compose_panel_mega_drought_dummy(tiny_bofedales, tmp_path):
    """Mega-drought dummy is 1 for 2010..2018 inclusive."""
    from panel.compose import compose_panel

    bof_path = tmp_path / "bofedales.geojson"
    tiny_bofedales.to_file(bof_path, driver="GeoJSON")

    intermediates = tmp_path / "panel"
    for sub in ("ndvi_gs", "ndvi_annual", "s1_vv", "s1_vh"):
        (intermediates / sub).mkdir(parents=True)

    ids = list(tiny_bofedales["bofedal_id"])
    years = [2009, 2010, 2018, 2019]
    for y in years:
        pd.DataFrame({"bofedal_id": ids, "median": [0.5] * 3, "count": [10] * 3}).to_csv(
            intermediates / "ndvi_gs" / f"{y}.csv", index=False)
        pd.DataFrame({"bofedal_id": ids, "median": [0.4] * 3, "count": [20] * 3}).to_csv(
            intermediates / "ndvi_annual" / f"{y}.csv", index=False)

    spei12 = pd.DataFrame({"bofedal_id": ids * 4,
                            "year": sum([[y] * 3 for y in years], []),
                            "spei_12_gs_mean": [0.0] * 12})
    spei24 = pd.DataFrame({"bofedal_id": ids * 4,
                            "year": sum([[y] * 3 for y in years], []),
                            "spei_24_gs_mean": [0.0] * 12})
    elevation = pd.DataFrame({"bofedal_id": ids, "mean": [3800.0] * 3})
    salar = pd.DataFrame({"bofedal_id": ids,
                           "containing_salar": [None] * 3})

    out = tmp_path / "bofedal_panel.parquet"
    compose_panel(
        bofedales_path=bof_path,
        years=years,
        ndvi_gs_dir=intermediates / "ndvi_gs",
        ndvi_annual_dir=intermediates / "ndvi_annual",
        s1_vv_dir=intermediates / "s1_vv",
        s1_vh_dir=intermediates / "s1_vh",
        spei12_df=spei12,
        spei24_df=spei24,
        elevation_df=elevation,
        containing_salar_df=salar,
        out_path=out,
    )
    df = pd.read_parquet(out).sort_values(["bofedal_id", "year"]).reset_index(drop=True)
    dummies = df.set_index(["bofedal_id", "year"])["mega_drought_dummy"]
    for bid in ids:
        assert dummies[(bid, 2009)] == 0
        assert dummies[(bid, 2010)] == 1
        assert dummies[(bid, 2018)] == 1
        assert dummies[(bid, 2019)] == 0
