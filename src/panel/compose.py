"""Merge per-outcome CSVs + SPEI + static attrs into the final parquet."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd

MEGA_DROUGHT_YEARS = range(2010, 2019)  # inclusive 2010..2018


def _read_year_csvs(
    directory: Path, value_col_name: str, count_col_name: str
) -> pd.DataFrame:
    """Read every <year>.csv in directory into long form with (bofedal_id, year, ...).

    GEE table exports use 'median' for the reducer column and 'count' for the count;
    we rename to the panel's column names.
    """
    if not directory.exists():
        return pd.DataFrame(columns=["bofedal_id", "year", value_col_name, count_col_name])
    parts = []
    for csv in sorted(directory.glob("*.csv")):
        year = int(csv.stem)
        df = pd.read_csv(csv)
        df = df.rename(columns={"median": value_col_name, "count": count_col_name})
        df["year"] = year
        parts.append(df[["bofedal_id", "year", value_col_name, count_col_name]])
    if not parts:
        return pd.DataFrame(columns=["bofedal_id", "year", value_col_name, count_col_name])
    return pd.concat(parts, ignore_index=True)


def compose_panel(
    *,
    bofedales_path: Path,
    years: Iterable[int],
    ndvi_gs_dir: Path,
    ndvi_annual_dir: Path,
    s1_vv_dir: Path,
    s1_vh_dir: Path,
    spei12_df: pd.DataFrame,
    spei24_df: pd.DataFrame,
    elevation_df: pd.DataFrame,
    containing_salar_df: pd.DataFrame,
    out_path: Path,
) -> Path:
    """Merge intermediate dataframes into the final parquet."""
    bofedales = gpd.read_file(bofedales_path)
    years_list = sorted({int(y) for y in years})

    # Cartesian product bofedal x year as the skeleton.
    skeleton = pd.MultiIndex.from_product(
        [bofedales["bofedal_id"].astype(str).tolist(), years_list],
        names=["bofedal_id", "year"],
    ).to_frame(index=False)

    ndvi_gs = _read_year_csvs(ndvi_gs_dir, "ndvi_gs_median", "ndvi_gs_n_obs")
    ndvi_annual = _read_year_csvs(
        ndvi_annual_dir, "ndvi_annual_median", "ndvi_annual_n_obs"
    )
    s1_vv = _read_year_csvs(s1_vv_dir, "s1_vv_db_median", "s1_n_obs")
    s1_vh = _read_year_csvs(s1_vh_dir, "s1_vh_db_median", "s1_n_obs_vh")

    df = (
        skeleton
        .merge(ndvi_gs, on=["bofedal_id", "year"], how="left")
        .merge(ndvi_annual, on=["bofedal_id", "year"], how="left")
        .merge(s1_vv, on=["bofedal_id", "year"], how="left")
        .merge(s1_vh.drop(columns=["s1_n_obs_vh"]), on=["bofedal_id", "year"], how="left")
        .merge(spei12_df, on=["bofedal_id", "year"], how="left")
        .merge(spei24_df, on=["bofedal_id", "year"], how="left")
        .merge(
            elevation_df.rename(columns={"mean": "elevation_m"}),
            on=["bofedal_id"], how="left",
        )
        .merge(containing_salar_df, on=["bofedal_id"], how="left")
    )

    df["mega_drought_dummy"] = df["year"].isin(MEGA_DROUGHT_YEARS).astype("int8")

    # Cast to compact dtypes per spec §8.
    schema = {
        "bofedal_id": "string",
        "year": "int16",
        "ndvi_gs_median": "float32",
        "ndvi_gs_n_obs": "Int16",
        "ndvi_annual_median": "float32",
        "ndvi_annual_n_obs": "Int16",
        "s1_vv_db_median": "float32",
        "s1_vh_db_median": "float32",
        "s1_n_obs": "Int16",
        "spei_12_gs_mean": "float32",
        "spei_24_gs_mean": "float32",
        "elevation_m": "float32",
        "containing_salar": "string",
        "mega_drought_dummy": "int8",
    }
    df = df.astype({k: v for k, v in schema.items() if k in df.columns})

    # Project to schema columns only — strips any extra columns leaking from
    # GEE table exports (`.geo`, `system:index`) or wide intermediate CSVs.
    df = df[[c for c in schema if c in df.columns]]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, engine="pyarrow", compression="snappy", index=False)
    return out_path
