"""MapBiomas Argentina Collection 2 — bofedal-class GEE-mediated acquisition.

Builds a server-side image of "stable wetland" pixels (wetland class in
≥ n_years_required of the analysis window) and exports the Puna subset to
Drive via `acquisition.gee.export_to_drive`.

The `asset_id` is the MapBiomas Coll. 2 image collection ID; the
`wetland_classes` tuple lists the class codes to treat as bofedal.
Both are resolved at acquisition time from MapBiomas's catalog and pinned
in the manifest's `mapbiomas` entry.
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
    """Server-side: sum wetland-class years per pixel, threshold at n_required."""
    coll = ee.ImageCollection(asset_id).filter(
        ee.Filter.calendarRange(start_year, end_year, "year")
    )

    def to_binary(img):
        # Pixel == 1 if classification is in wetland_classes; else 0.
        wetland_list = ee.List(list(wetland_classes))
        return img.remap(wetland_list, ee.List.repeat(1, wetland_list.size()), 0)

    binary = coll.map(to_binary)
    n_years = binary.sum()
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
    analysis_window: tuple[int, int] = (1998, 2024)
    n_years_required: int = 14  # >= 50% of 27 years
    gee_project: str = "ee-nunezrimedio-tesina"

    def fetch(self, dest: Path) -> Path:
        raw_dir = dest / "raw"
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
