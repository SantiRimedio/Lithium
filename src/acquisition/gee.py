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


def _poll_status(task, description: str):
    """task.status() with retries on transient network errors."""
    for attempt in range(5):
        try:
            return task.status()
        except Exception as e:
            if attempt == 4:
                raise
            wait = 30 * (2 ** attempt)
            print(
                f"[gee] transient error polling {description!r} (attempt {attempt + 1}/5): "
                f"{type(e).__name__}: {e}; retrying in {wait}s",
                flush=True,
            )
            time.sleep(wait)


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
        status = _poll_status(task, description)
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
    _rclone_copy_with_retry(drive_folder, local_dest)
    return local_dest


def export_table_to_drive(
    *,
    table: "ee.FeatureCollection",
    description: str,
    drive_folder: str,
    file_prefix: str,
    local_dest: Path,
    timeout_min: int = 15,
) -> Path:
    """Submit a FeatureCollection -> CSV export, poll until done, mirror locally.

    Parallels `export_to_drive` for images. Uses `Export.table.toDrive` with
    CSV format. Returns `local_dest` after the rclone mirror.
    """
    task = ee.batch.Export.table.toDrive(
        collection=table,
        description=description,
        folder=drive_folder,
        fileNamePrefix=file_prefix,
        fileFormat="CSV",
    )
    task.start()

    deadline = time.monotonic() + (timeout_min * 60)
    while True:
        status = _poll_status(task, description)
        state = status.get("state")
        if state == "COMPLETED":
            break
        if state == "FAILED":
            raise RuntimeError(
                f"GEE table export {description!r} failed: "
                f"{status.get('error_message', 'unknown error')}"
            )
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"GEE table export {description!r} did not finish within {timeout_min} min"
            )
        time.sleep(_POLL_INTERVAL_S)

    local_dest.mkdir(parents=True, exist_ok=True)
    _rclone_copy_with_retry(drive_folder, local_dest)
    return local_dest


def _rclone_copy_with_retry(drive_folder: str, local_dest: Path) -> None:
    """rclone copy with retries on transient failures (network/OAuth blips)."""
    for attempt in range(5):
        try:
            subprocess.run(
                ["rclone", "copy", f"gdrive:{drive_folder}", str(local_dest)],
                check=True,
            )
            return
        except subprocess.CalledProcessError as e:
            if attempt == 4:
                raise
            wait = 30 * (2 ** attempt)
            print(
                f"[gee] rclone copy {drive_folder!r} failed (attempt {attempt + 1}/5); "
                f"retrying in {wait}s",
                flush=True,
            )
            time.sleep(wait)
