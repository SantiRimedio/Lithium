"""SPEI per-bofedal growing-season mean extraction from local NetCDFs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import xarray as xr


def _growing_season_window(*, year: int):
    """Return numpy datetime64 (start, end) for austral summer Dec(y-1) - Feb(y)."""
    start = np.datetime64(f"{year - 1:04d}-12-01")
    feb_last = "29" if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else "28"
    end = np.datetime64(f"{year:04d}-02-{feb_last}")
    return start, end


def extract(
    *,
    nc_path: Path,
    bofedales,  # GeoDataFrame with bofedal_id + geometry
    years: Iterable[int],
    column: str,
    var_name: str = "spei",
) -> pd.DataFrame:
    """Open SPEI NetCDF; for each (bofedal, year) take the growing-season mean.

    Many bofedales will share a 0.5° SPEI cell — that's intentional, SPEI is
    a basin-scale climate signal.
    """
    centroids = bofedales.set_geometry("geometry").geometry.centroid
    rows = []
    with xr.open_dataset(nc_path) as ds:
        var = ds[var_name]
        for year in years:
            start, end = _growing_season_window(year=year)
            window = var.sel(time=slice(start, end))
            window_mean = window.mean("time")
            for bid, centroid in zip(bofedales["bofedal_id"], centroids):
                value = window_mean.sel(
                    lon=centroid.x, lat=centroid.y, method="nearest"
                ).item()
                rows.append({"bofedal_id": str(bid), "year": int(year), column: value})
    return pd.DataFrame(rows)
