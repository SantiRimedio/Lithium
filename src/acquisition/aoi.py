"""AOI definitions used by acquisition modules to clip global rasters."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BBox:
    """Geographic bounding box in EPSG:4326 (lon/lat, degrees)."""

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        if self.west >= self.east:
            raise ValueError(f"west ({self.west}) must be < east ({self.east})")
        if self.south >= self.north:
            raise ValueError(f"south ({self.south}) must be < north ({self.north})")


# Generous bounding box around the Argentine Puna. Used as a storage
# optimization for global rasters in Stage 0 — NOT the analytical AOI.
# Stage 1 will define the precise bofedal-selection geometry.
PUNA_BBOX = BBox(west=-69.0, south=-27.0, east=-65.0, north=-22.0)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PUNA_BASINS_PATH = _REPO_ROOT / "Data" / "Endorheic_basins_Puna.geojson"


def puna_basins():
    """Load the existing Puna endorheic basins layer as a GeoDataFrame.

    Returns the geopandas.GeoDataFrame; deferred import keeps test collection
    cheap when geopandas is slow to import.
    """
    import geopandas as gpd

    if not _PUNA_BASINS_PATH.exists():
        raise FileNotFoundError(f"Expected basin layer at {_PUNA_BASINS_PATH}")
    return gpd.read_file(_PUNA_BASINS_PATH)
