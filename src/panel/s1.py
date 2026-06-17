"""Sentinel-1 GRD VV/VH backscatter median per (bofedal, year), in dB.

Filters to IW mode + descending orbit + the requested polarization, takes
the per-pixel median across the year, and reduces over the bofedal polygons.
The COPERNICUS/S1_GRD asset bands `VV` and `VH` are already in dB scale
after GEE's standard preprocessing (thermal noise removal + radiometric
calibration + terrain correction), so no explicit log10 step is needed.
"""
from __future__ import annotations

from pathlib import Path

import ee

from acquisition.aoi import PUNA_BBOX
from acquisition.gee import export_table_to_drive, initialize


_S1_ASSET = "COPERNICUS/S1_GRD"
_S1_AVAILABLE_FROM = 2014


def _puna_region() -> "ee.Geometry":
    return ee.Geometry.Rectangle(
        [PUNA_BBOX.west, PUNA_BBOX.south, PUNA_BBOX.east, PUNA_BBOX.north]
    )


def _bofedales_to_fc(bofedales_gdf) -> "ee.FeatureCollection":
    features = []
    for _, row in bofedales_gdf.iterrows():
        features.append(
            ee.Feature(
                ee.Geometry(row.geometry.__geo_interface__),
                {"bofedal_id": str(row["bofedal_id"])},
            )
        )
    return ee.FeatureCollection(features)


def _reduce_to_table(
    image: "ee.Image", fc: "ee.FeatureCollection"
) -> "ee.FeatureCollection":
    reducer = ee.Reducer.median().combine(ee.Reducer.count(), "", True)
    return image.reduceRegions(collection=fc, reducer=reducer, scale=30)


def extract_year(
    *,
    year: int,
    bofedales,
    polarization: str,
    local_dest: Path,
) -> Path:
    """Submit a GEE export for one (year, polarization). Idempotent."""
    if year < _S1_AVAILABLE_FROM:
        raise ValueError(
            f"Sentinel-1 GRD is not available before {_S1_AVAILABLE_FROM}; got {year}"
        )

    out_csv = local_dest / f"{year}.csv"
    if out_csv.exists():
        return out_csv

    initialize()
    region = _puna_region()
    coll = (
        ee.ImageCollection(_S1_ASSET)
        .filterBounds(region)
        .filterDate(f"{year:04d}-01-01", f"{year:04d}-12-31")
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", polarization))
    )
    band = coll.select(polarization).median()
    fc = _bofedales_to_fc(bofedales)
    table = _reduce_to_table(band, fc)

    pol_lower = polarization.lower()
    export_table_to_drive(
        table=table,
        description=f"s1_{pol_lower}_{year}",
        drive_folder=f"Lithium_v2_gee_exports_panel_s1_{pol_lower}",
        file_prefix=str(year),
        local_dest=local_dest,
    )
    return out_csv
