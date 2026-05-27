"""USGS Argentine Lithium Geodatabase (DOI 10.5066/P9RLUH4F).

86 Argentine salars including 42 with known Li and 44 without — the no-Li
set is the candidate control group per Methodology v2 §3.4.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from acquisition.aoi import BBox
from acquisition.datasets._base import http_download


@dataclass
class UsgsDataset:
    url: str
    key: str = "usgs"

    def fetch(self, dest: Path) -> Path:
        raw_dir = dest / "raw"
        out = raw_dir / "usgs.gdb.zip"
        return http_download(self.url, out)

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        # Already regional. No clipping needed.
        return None
