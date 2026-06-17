"""Static per-bofedal attributes: SRTM elevation + USGS salar spatial join."""
from __future__ import annotations

from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd
import py7zr

from acquisition.aoi import PUNA_BBOX
from acquisition.gee import export_table_to_drive, initialize


_SRTM_ASSET = "USGS/SRTMGL1_003"


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
    return image.reduceRegions(
        collection=fc, reducer=ee.Reducer.mean(), scale=30
    )


def extract_elevation(*, bofedales, local_dest: Path) -> Path:
    """Submit a GEE export of mean SRTM elevation per bofedal."""
    out_csv = local_dest / "elevation.csv"
    if out_csv.exists():
        return out_csv

    initialize()
    image = ee.Image(_SRTM_ASSET)
    drive_folder = "Lithium_v2_gee_exports_panel_elevation"

    from panel.ndvi import _chunks

    for i, chunk in _chunks(bofedales):
        fc = _bofedales_to_fc(chunk)
        table = _reduce_to_table(image, fc)
        export_table_to_drive(
            table=table,
            description=f"elevation_chunk_{i}",
            drive_folder=drive_folder,
            file_prefix=f"elevation_chunk_{i}",
            local_dest=local_dest,
            timeout_min=30,
        )

    import pandas as pd
    chunk_csvs = sorted(local_dest.glob("elevation_chunk_*.csv"))
    if not chunk_csvs:
        raise RuntimeError(f"No elevation chunk CSVs landed in {local_dest}")
    pd.concat([pd.read_csv(c) for c in chunk_csvs], ignore_index=True).to_csv(
        out_csv, index=False
    )
    for c in chunk_csvs:
        c.unlink()
    return out_csv


def unpack_usgs_archive(*, archive: Path, target_dir: Path) -> None:
    """Unpack the USGS gdb 7z to `target_dir`. Idempotent."""
    if target_dir.exists() and any(target_dir.iterdir()):
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    py7zr.unpack_7zarchive(str(archive), str(target_dir))


def extract_containing_salar_from_layer(
    *, bofedales: gpd.GeoDataFrame, salars: gpd.GeoDataFrame
) -> pd.DataFrame:
    """For each bofedal, return the NAME of the salar with the largest
    intersection area, or None if outside any salar."""
    if salars.crs != bofedales.crs:
        salars = salars.to_crs(bofedales.crs)

    rows = []
    for _, bof in bofedales.iterrows():
        bid = str(bof["bofedal_id"])
        best_name = None
        best_area = 0.0
        for _, sal in salars.iterrows():
            if not bof.geometry.intersects(sal.geometry):
                continue
            inter_area = bof.geometry.intersection(sal.geometry).area
            if inter_area > best_area:
                best_area = inter_area
                best_name = sal["NAME"]
        rows.append({"bofedal_id": bid, "containing_salar": best_name})
    return pd.DataFrame(rows)
