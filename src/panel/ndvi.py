"""Landsat C2 SR NDVI extraction per (bofedal, year).

For each year + window (growing-season or annual), build a server-side
image collection of Landsat 5/7/8/9 Collection 2 Surface Reflectance
scenes, cloud-mask via QA_PIXEL, compute per-pixel NDVI, take the
median across scenes, and reduceRegions over the bofedal polygons.
Exports one CSV per (window, year) to Drive and mirrors locally.
"""
from __future__ import annotations

import calendar
from pathlib import Path

import ee

from acquisition.aoi import PUNA_BBOX
from acquisition.gee import export_table_to_drive, initialize


# Sensor coverage windows (start_year, end_year inclusive).
_LANDSAT_ERAS: tuple[tuple[str, int, int], ...] = (
    ("LANDSAT/LT05/C02/T1_L2", 1984, 2012),
    ("LANDSAT/LE07/C02/T1_L2", 1999, 2024),  # SLC-off after 2003 but still useful
    ("LANDSAT/LC08/C02/T1_L2", 2013, 2024),
    ("LANDSAT/LC09/C02/T1_L2", 2021, 2024),
)


def _puna_region() -> "ee.Geometry":
    return ee.Geometry.Rectangle(
        [PUNA_BBOX.west, PUNA_BBOX.south, PUNA_BBOX.east, PUNA_BBOX.north]
    )


def _window_dates(*, year: int, window: str) -> tuple[str, str]:
    """Return (start, end) ISO dates for the named window in the given year."""
    if window == "growing_season":
        last_day_feb = calendar.monthrange(year, 2)[1]
        return f"{year - 1}-12-01", f"{year:04d}-02-{last_day_feb:02d}"
    if window == "annual":
        return f"{year:04d}-01-01", f"{year:04d}-12-31"
    raise ValueError(f"unknown window {window!r}; expected growing_season|annual")


def _landsat_collection_for_window(
    *, start: str, end: str, region: "ee.Geometry"
) -> "ee.ImageCollection":
    """Combine Landsat 5/7/8/9 scenes active during the window."""
    start_year = int(start[:4])
    end_year = int(end[:4])
    combined: ee.ImageCollection | None = None
    for asset_id, sensor_start, sensor_end in _LANDSAT_ERAS:
        if end_year < sensor_start or start_year > sensor_end:
            continue
        coll = (
            ee.ImageCollection(asset_id)
            .filterBounds(region)
            .filterDate(start, end)
        )
        combined = coll if combined is None else combined.merge(coll)
    if combined is None:
        raise RuntimeError(
            f"No Landsat sensors active for {start}..{end}"
        )
    return combined


def _ndvi_band_pair(asset_id: str) -> tuple[str, str]:
    """Return (NIR, Red) Collection 2 SR band names for a given Landsat sensor."""
    if asset_id.endswith("LT05/C02/T1_L2") or asset_id.endswith("LE07/C02/T1_L2"):
        return "SR_B4", "SR_B3"
    return "SR_B5", "SR_B4"  # L8 + L9


def _compute_ndvi_image(coll: "ee.ImageCollection") -> "ee.Image":
    """Apply Collection 2 scaling, QA-mask, compute NDVI, take per-pixel median."""

    def per_scene(img: ee.Image) -> ee.Image:
        asset_id = ee.String(img.get("system:id"))
        scaled = img.multiply(0.0000275).add(-0.2)
        qa = img.select("QA_PIXEL")
        clear = (
            qa.bitwiseAnd(1 << 3).eq(0)
            .And(qa.bitwiseAnd(1 << 4).eq(0))
            .And(qa.bitwiseAnd(1 << 2).eq(0))
        )
        nir = ee.Algorithms.If(
            asset_id.match("LC08|LC09"),
            scaled.select("SR_B5"),
            scaled.select("SR_B4"),
        )
        red = ee.Algorithms.If(
            asset_id.match("LC08|LC09"),
            scaled.select("SR_B4"),
            scaled.select("SR_B3"),
        )
        nir_img = ee.Image(nir).updateMask(clear)
        red_img = ee.Image(red).updateMask(clear)
        ndvi = nir_img.subtract(red_img).divide(nir_img.add(red_img))
        return ndvi.rename("NDVI").copyProperties(img, ["system:time_start"])

    return coll.map(per_scene).median()


def _bofedales_to_fc(bofedales_gdf) -> "ee.FeatureCollection":
    """Convert a GeoDataFrame to ee.FeatureCollection, carrying bofedal_id."""
    features = []
    for _, row in bofedales_gdf.iterrows():
        geom_geojson = row.geometry.__geo_interface__
        features.append(
            ee.Feature(
                ee.Geometry(geom_geojson),
                {"bofedal_id": str(row["bofedal_id"])},
            )
        )
    return ee.FeatureCollection(features)


def _reduce_to_table(
    image: "ee.Image", fc: "ee.FeatureCollection"
) -> "ee.FeatureCollection":
    """polygon-wise median + count of contributing pixels."""
    reducer = ee.Reducer.median().combine(ee.Reducer.count(), "", True)
    return image.reduceRegions(collection=fc, reducer=reducer, scale=30)


# Chunk size for export submission. GEE's API has a 10 MB payload limit;
# inlining all 3,821 polygons in a single FC blows that ceiling (the
# expression-tree serialization is ~6-10x the raw geometry size). Splitting
# into 8 chunks keeps each per-chunk payload comfortably under the limit.
_N_CHUNKS = 8


def _chunks(gdf, n: int = _N_CHUNKS):
    """Yield up to n approximately-equal slices of gdf."""
    if len(gdf) == 0:
        return
    chunk_size = (len(gdf) + n - 1) // n
    for i in range(n):
        slice_ = gdf.iloc[i * chunk_size:(i + 1) * chunk_size]
        if len(slice_) == 0:
            return
        yield i, slice_


def _concat_chunk_csvs(local_dest: Path, year: int, out_csv: Path) -> None:
    import pandas as pd
    chunk_csvs = sorted(local_dest.glob(f"{year}_chunk_*.csv"))
    if not chunk_csvs:
        raise RuntimeError(f"No chunk CSVs landed for year {year} in {local_dest}")
    pd.concat([pd.read_csv(c) for c in chunk_csvs], ignore_index=True).to_csv(
        out_csv, index=False
    )
    for c in chunk_csvs:
        c.unlink()


def extract_year(
    *,
    year: int,
    bofedales,
    window: str,
    local_dest: Path,
) -> Path:
    """Submit a GEE export for one (year, window). Idempotent.

    `bofedales` is a GeoDataFrame with columns `bofedal_id` and `geometry`.
    `window` is `growing_season` or `annual`. Bofedales are chunked into
    ~500-polygon batches to stay under GEE's 10 MB request payload limit;
    chunk CSVs are concatenated locally into a single `<year>.csv`.
    """
    out_csv = local_dest / f"{year}.csv"
    if out_csv.exists():
        return out_csv

    initialize()
    start, end = _window_dates(year=year, window=window)
    region = _puna_region()
    coll = _landsat_collection_for_window(start=start, end=end, region=region)
    ndvi_img = _compute_ndvi_image(coll)

    suffix = "gs" if window == "growing_season" else "annual"
    drive_folder = f"Lithium_v2_gee_exports_panel_ndvi_{suffix}"

    for i, chunk in _chunks(bofedales):
        fc = _bofedales_to_fc(chunk)
        table = _reduce_to_table(ndvi_img, fc)
        export_table_to_drive(
            table=table,
            description=f"ndvi_{suffix}_{year}_chunk_{i}",
            drive_folder=drive_folder,
            file_prefix=f"{year}_chunk_{i}",
            local_dest=local_dest,
            timeout_min=30,
        )

    _concat_chunk_csvs(local_dest, year, out_csv)
    return out_csv
