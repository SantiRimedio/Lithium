"""MapBiomas Argentina Collection 1 — bofedal-class GEE-mediated acquisition.

Builds a server-side image of "stable wetland" pixels (wetland class in
≥ n_years_required of the analysis window) and exports the Puna subset to
Drive via `acquisition.gee.export_to_drive`.

The asset is a single ee.Image with one band per year
(classification_1998 … classification_2022). The `asset_id` is the image
asset path; `wetland_classes` tuple lists the class codes to treat as
bofedal (class 11 = vegetación de humedal / vega per the Coll. 1 legend).
Both are resolved at acquisition time and pinned in the manifest's
`mapbiomas` entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import ee

from acquisition.aoi import PUNA_BBOX, BBox
from acquisition.gee import export_to_drive, initialize


def _build_stable_bofedal_image(
    asset_id: str,
    wetland_classes: tuple[int, ...],
    start_year: int,
    end_year: int,
    n_years_required: int,
) -> "ee.Image":
    """Server-side: sum wetland-class years per pixel, threshold at n_required.

    The asset is a single Image with one band per year
    (classification_<YYYY>). Loops over years client-side to build a sum
    of binary year masks; payload stays small (~25 band ops).
    """
    img = ee.Image(asset_id)
    n_years = ee.Image(0)
    for year in range(start_year, end_year + 1):
        band = img.select(f"classification_{year}")
        is_wetland = band.eq(wetland_classes[0])
        for cls in wetland_classes[1:]:
            is_wetland = is_wetland.Or(band.eq(cls))
        n_years = n_years.add(is_wetland)
    return n_years.gte(n_years_required).rename("stable_bofedal")


def _puna_region() -> "ee.Geometry":
    return ee.Geometry.Rectangle(
        [PUNA_BBOX.west, PUNA_BBOX.south, PUNA_BBOX.east, PUNA_BBOX.north]
    )


@dataclass
class MapbiomasDataset:
    asset_id: str
    key: str = "mapbiomas"
    wetland_classes: tuple[int, ...] = (11,)
    # MapBiomas Argentina Coll. 1 covers 1998–2022 (25 years). Methodology v2
    # §3.1 stability rule: wetland class in ≥ 50% of analytical years.
    analysis_window: tuple[int, int] = (1998, 2022)
    n_years_required: int = 13  # >= 50% of 25 years
    gee_project: str = "ee-nunezrimedio-tesina"

    def fetch(self, dest: Path) -> Path:
        raw_dir = dest / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        # Idempotent: skip the GEE round-trip if the export already mirrored.
        existing = sorted(raw_dir.glob("*.tif"))
        if existing:
            return existing[0]
        start_year, end_year = self.analysis_window
        initialize(project=self.gee_project)
        image = _build_stable_bofedal_image(
            asset_id=self.asset_id,
            wetland_classes=self.wetland_classes,
            start_year=start_year,
            end_year=end_year,
            n_years_required=self.n_years_required,
        )
        region = _puna_region()
        export_to_drive(
            image=image,
            description=f"mapbiomas_stable_bofedal_{start_year}_{end_year}",
            drive_folder="Lithium_v2_gee_exports_mapbiomas",
            file_prefix=f"bofedal_stable_{start_year}_{end_year}",
            region=region,
            local_dest=raw_dir,
            scale=30,
        )
        tifs = sorted(raw_dir.glob("*.tif"))
        if not tifs:
            raise RuntimeError(
                f"MapBiomas GEE export produced no .tif in {raw_dir}. "
                "Check the GEE Tasks panel for task "
                f"mapbiomas_stable_bofedal_{start_year}_{end_year}."
            )
        return tifs[0]

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        return None
