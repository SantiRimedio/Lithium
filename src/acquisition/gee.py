"""Google Earth Engine wrapper: auth + Drive-export with polling + rclone mirror.

The export pipeline mirrors the v1 Data-Acquisition pattern: submit a task,
poll until done, then `rclone copy` the GEE-export Drive folder into the
local Data/external/<key>/raw/ layout the rest of the pipeline expects.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import ee

_HIGHVOL_URL = "https://earthengine-highvolume.googleapis.com"
_POLL_INTERVAL_S = 30.0


def initialize(project: str = "ee-nunezrimedio-tesina") -> None:
    """Authenticate (browser flow first time, cached after) and initialize EE."""
    ee.Authenticate()
    ee.Initialize(project=project, opt_url=_HIGHVOL_URL)


def export_to_drive(
    *,
    image: "ee.Image",
    description: str,
    drive_folder: str,
    file_prefix: str,
    region: "ee.Geometry",
    local_dest: Path,
    scale: int = 30,
    timeout_min: int = 30,
) -> Path:
    """Submit a Drive export, poll until done, then mirror to `local_dest`.

    Returns `local_dest` (after the rclone mirror) so callers can chain on it.
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=drive_folder,
        fileNamePrefix=file_prefix,
        region=region,
        scale=scale,
        maxPixels=int(1e13),
        fileFormat="GeoTIFF",
    )
    task.start()

    deadline = time.monotonic() + (timeout_min * 60)
    while True:
        status = task.status()
        state = status.get("state")
        if state == "COMPLETED":
            break
        if state == "FAILED":
            raise RuntimeError(
                f"GEE export {description!r} failed: "
                f"{status.get('error_message', 'unknown error')}"
            )
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"GEE export {description!r} did not finish within {timeout_min} min"
            )
        time.sleep(_POLL_INTERVAL_S)

    local_dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rclone", "copy", f"gdrive:{drive_folder}", str(local_dest)],
        check=True,
    )
    return local_dest
