"""SPEIbase v2.11 — global monthly SPEI (Beguería & Vicente-Serrano).

SPEI-12 and SPEI-24 drive conditional parallel trends in the CS-DiD design
per Methodology v2 §3.5. SPEIbase distributes one NetCDF per timescale
(spei01.nc, spei12.nc, …), so the manifest has one entry per timescale we
need and the dataset module is parameterized by `filename`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import xarray as xr

from acquisition.aoi import BBox
from acquisition.datasets._base import http_download


@dataclass
class SpeiDataset:
    url: str
    key: str = "spei"
    filename: str = "spei.nc"
    clipped_filename: str = "spei_puna.nc"

    def fetch(self, dest: Path) -> Path:
        raw_dir = dest / "raw"
        out = raw_dir / self.filename
        return http_download(self.url, out)

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        out_dir = dest / "puna"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / self.clipped_filename
        if out.exists():
            return out

        with xr.open_dataset(raw_path) as src:
            subset = src.sel(
                lon=slice(aoi.west, aoi.east),
                lat=slice(aoi.south, aoi.north),
            )
            # Some products store lat in descending order; handle both.
            if subset.sizes.get("lat", 0) == 0:
                subset = src.sel(
                    lon=slice(aoi.west, aoi.east),
                    lat=slice(aoi.north, aoi.south),
                )
            subset.to_netcdf(out)
        return out
