"""Tests for panel.spei — local NetCDF -> per-bofedal-year extract."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr


@pytest.fixture
def synthetic_spei(tmp_path):
    """Build a tiny SPEI NetCDF with known per-cell values for testing.

    Grid: 0.5° from -180 to 180 lon, -90 to 90 lat. Monthly 2018-01..2024-12.
    The bofedales fixture sits around (-67, -24); we set those cells to known values
    so the extract math is verifiable.
    """
    path = tmp_path / "spei.nc"
    lons = np.arange(-179.75, 180.0, 0.5)
    lats = np.arange(-89.75, 90.0, 0.5)
    times = np.array(
        [np.datetime64(f"{y:04d}-{m:02d}-01") for y in range(2018, 2025) for m in range(1, 13)]
    )
    rng = np.random.default_rng(42)
    data = rng.standard_normal((len(times), len(lats), len(lons))).astype("float32")
    bof1_lon_idx = int(np.argmin(np.abs(lons - (-66.75))))
    bof1_lat_idx = int(np.argmin(np.abs(lats - (-23.75))))
    dec_2019 = (2019 - 2018) * 12 + 11
    jan_2020 = (2020 - 2018) * 12 + 0
    feb_2020 = (2020 - 2018) * 12 + 1
    data[dec_2019, bof1_lat_idx, bof1_lon_idx] = 0.5
    data[jan_2020, bof1_lat_idx, bof1_lon_idx] = 1.0
    data[feb_2020, bof1_lat_idx, bof1_lon_idx] = -0.2
    ds = xr.Dataset(
        {"spei": (("time", "lat", "lon"), data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds.to_netcdf(path)
    return path


def test_growing_season_window_returns_dec_to_feb():
    """Helper exposes (start, end) for the growing-season window of a given year."""
    from panel.spei import _growing_season_window

    start, end = _growing_season_window(year=2020)
    assert str(start) == "2019-12-01" or str(start.astype("datetime64[D]")) == "2019-12-01"
    assert str(end).startswith("2020-02")


def test_extract_returns_per_bofedal_per_year_rows(tiny_bofedales, synthetic_spei):
    """The first bofedal's gs 2020 mean should match the known synthetic values."""
    from panel.spei import extract

    df = extract(
        nc_path=synthetic_spei,
        bofedales=tiny_bofedales,
        years=range(2020, 2021),
        column="spei_12_gs_mean",
    )

    assert set(df.columns) == {"bofedal_id", "year", "spei_12_gs_mean"}
    assert len(df) == 3
    bofedal_1 = "11111111-1111-5111-8111-111111111111"
    val = df.loc[df["bofedal_id"] == bofedal_1, "spei_12_gs_mean"].iloc[0]
    # (0.5 + 1.0 + -0.2) / 3 = 0.43333...
    assert abs(val - 0.43333333) < 1e-5


def test_extract_handles_multiple_years(tiny_bofedales, synthetic_spei):
    from panel.spei import extract

    df = extract(
        nc_path=synthetic_spei,
        bofedales=tiny_bofedales,
        years=range(2020, 2023),
        column="spei_12_gs_mean",
    )
    assert len(df) == 3 * 3
    assert set(df["year"]) == {2020, 2021, 2022}
