"""AOI definitions used by acquisition modules to clip global rasters."""
from __future__ import annotations

from dataclasses import dataclass


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
