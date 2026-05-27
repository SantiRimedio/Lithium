"""Izquierdo, Foguet & Grau 2016 — Argentine Puna hydroecosystem polygons
(CONICET handle 11336/58267). Primary bofedal mask per Methodology v2 §3.1.

NOTE: the CONICET handle resolves to a landing page; the resolved direct-download
URL must be filled into the manifest at acquisition time. If CONICET delivers a
manual click-through only, place the downloaded file at
Data/external/izquierdo/raw/izquierdo_hydroecosystems.zip and re-run; the fetch
will detect the existing file and skip.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from acquisition.aoi import BBox
from acquisition.datasets._base import http_download


@dataclass
class IzquierdoDataset:
    url: str
    key: str = "izquierdo"

    def fetch(self, dest: Path) -> Path:
        raw_dir = dest / "raw"
        out = raw_dir / "izquierdo_hydroecosystems.zip"
        return http_download(self.url, out)

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        return None
