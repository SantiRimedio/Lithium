"""Global 30 m high-altitude wetland map, 2026 release
(Zenodo 10.5281/zenodo.18339573; *Sci Data* s41597-026-07020-w).

Used as the cross-validation mask vs Izquierdo per Methodology v2 §3.1.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

from acquisition.aoi import BBox
from acquisition.datasets._base import http_download


@dataclass
class Wetland2026Dataset:
    url: str
    key: str = "wetland2026"

    def fetch(self, dest: Path) -> Path:
        # Zenodo 18339573 distributes the mask as a ZIP archive
        # (2_Maps_high_probabilities.zip). Stage 0 stores the zip;
        # Stage 1 will extract the inner TIF(s) and reclip to the Puna
        # bbox. The clip() method below still operates on a TIF — kept
        # for forward compatibility once extraction lands.
        raw_dir = dest / "raw"
        out = raw_dir / "wetland2026_high_probabilities.zip"
        return http_download(self.url, out)

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        out_dir = dest / "puna"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "wetland_puna.tif"
        if out.exists():
            return out

        with rasterio.open(raw_path) as src:
            window = from_bounds(aoi.west, aoi.south, aoi.east, aoi.north, src.transform)
            window = window.round_offsets().round_lengths()
            data = src.read(window=window)
            transform = src.window_transform(window)
            profile = src.profile.copy()
            profile.update(
                height=data.shape[1],
                width=data.shape[2],
                transform=transform,
            )
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(data)
        return out
