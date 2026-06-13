# Stage 0.5 — MapBiomas + Zenodo Bofedal Mask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v2 bofedal polygon mask end-to-end — acquire MapBiomas Argentina Collection 2 wetland classification via GEE, extract the Puna subset of the Zenodo 2026 wetland map, polygonize both via the Izquierdo-style sieve+clump+aggregate-300m recipe, reconcile, and emit `Data/bofedales_v2.geojson` + a disputed companion.

**Architecture:** Extends the existing `src/acquisition/` package. Three new modules — `gee.py` (auth + Drive-export wrapper), `datasets/mapbiomas.py` (Dataset protocol implementation, GEE-mediated), `bofedal_mask.py` (polygonization + reconciliation orchestrator). Reuses `manifest`, `drive`, `aoi`, and the `Dataset` protocol patterns from the Stage 0 tier-1 work that just merged.

**Tech Stack:** Python 3.11+, `uv`, `earthengine-api` (new), `rasterio`, `geopandas`, `shapely`, `scipy` (new — `ndimage.label` + `sparse.csgraph.connected_components`), `pyyaml`, `pytest`, `pytest-mock`.

**Spec:** [docs/superpowers/specs/2026-06-12-stage-0-mapbiomas-bofedal-mask-design.md](../specs/2026-06-12-stage-0-mapbiomas-bofedal-mask-design.md)

---

## File Structure

**Created by this plan:**

```
src/acquisition/
├── gee.py                                  # NEW: ee.Authenticate + export_to_drive
├── bofedal_mask.py                         # NEW: sieve, polygonize, aggregate_300m, reconcile, build_mask
└── datasets/
    └── mapbiomas.py                        # NEW: MapbiomasDataset, GEE-mediated

tests/acquisition/
├── test_gee.py                             # NEW
├── test_bofedal_mask.py                    # NEW
└── datasets/
    └── test_mapbiomas.py                   # NEW

docs/superpowers/plans/
└── 2026-06-12-stage-0-mapbiomas-bofedal-mask.md   # this file
```

**Modified by this plan:**

- `pyproject.toml` — add `earthengine-api>=1.0`, `scipy>=1.11`
- `src/acquisition/datasets/wetland2026.py` — add `extract_puna_tif()`
- `src/acquisition/run.py` — register `mapbiomas` + `--build-mask` flag
- `tests/acquisition/conftest.py` — add `tiny_zip_with_tifs` + `tiny_binary_raster` fixtures
- `tests/acquisition/datasets/test_wetland2026.py` — extend with extraction test
- `tests/acquisition/test_run.py` — add `--build-mask` test
- `Data/external/manifest.yaml` — add `mapbiomas` entry
- `Data/external/README.md` — append GEE setup + `--build-mask` docs

**Output deliverables (committed to git after first successful run):**

- `Data/bofedales_v2.geojson` — primary deliverable, ~MB
- `Data/bofedales_v2_disputed.geojson` — companion for hand-review

---

## Notes for the engineer

- **Commit style:** imperative verbs, no `feat:`/`fix:` prefix. Match the existing `git log`.
- **Branch:** work on the current branch `claude/stage-0-mapbiomas-bofedal`.
- **Test command:** `uv run pytest tests/acquisition/ -v`. Cumulative baseline before this plan: 35 passing.
- **Mocking GEE:** never call live GEE in pytest. Mock `ee.Authenticate`, `ee.Initialize`, `ee.ImageCollection`, `ee.batch.Export.image.toDrive`, etc. via `pytest-mock`'s `mocker.patch`.
- **Buffer projection:** the aggregate-300m step needs metric distances. The Argentine Puna sits in UTM Zone 19S (EPSG:32719). Always reproject to 32719 before buffering, then back to EPSG:4326 for output.
- **Stable IDs:** `bofedal_id` is `uuid.uuid5(uuid.UUID('00000000-0000-0000-0000-000000000001'), wkt)` — deterministic across reruns provided the polygon geometries don't drift.

---

## Task 1: Bootstrap new dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add earthengine-api + scipy to runtime deps**

Edit `pyproject.toml` — change the `dependencies` list to:

```toml
dependencies = [
    "earthengine-api>=1.0",
    "geopandas>=0.14",
    "netcdf4>=1.6",
    "pyyaml>=6.0",
    "rasterio>=1.3",
    "requests>=2.31",
    "scipy>=1.11",
    "tenacity>=8.2",
    "xarray>=2024.1",
]
```

- [ ] **Step 2: Sync deps**

Run:

```bash
uv sync --extra dev
```

Expected: new packages resolved + installed; no errors.

- [ ] **Step 3: Verify imports**

Run:

```bash
uv run python -c "import ee, scipy.ndimage, scipy.sparse.csgraph; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 4: Verify baseline tests still pass**

Run:

```bash
uv run pytest tests/acquisition/ -q
```

Expected: `35 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add earthengine-api + scipy for MapBiomas + polygonization"
```

---

## Task 2: Add conftest fixtures

**Files:**
- Modify: `tests/acquisition/conftest.py`

- [ ] **Step 1: Add `tiny_zip_with_tifs` and `tiny_binary_raster` fixtures**

Append to `tests/acquisition/conftest.py`:

```python
import io
import zipfile


@pytest.fixture
def tiny_zip_with_tifs(tmp_path: Path) -> Path:
    """A zip containing two tiny GeoTIFFs: one overlapping PUNA_BBOX, one outside."""
    path = tmp_path / "wetland_maps.zip"

    def make_tif_bytes(west, south, east, north) -> bytes:
        buf = io.BytesIO()
        height, width = 10, 10
        data = np.ones((height, width), dtype=np.uint8)
        transform = from_bounds(west, south, east, north, width, height)
        with rasterio.open(
            buf, "w", driver="GTiff",
            height=height, width=width, count=1,
            dtype="uint8", crs="EPSG:4326", transform=transform,
        ) as dst:
            dst.write(data, 1)
        return buf.getvalue()

    with zipfile.ZipFile(path, "w") as zf:
        # Puna-overlapping (-67, -25 area)
        zf.writestr("inside.tif", make_tif_bytes(-67.5, -25.5, -66.5, -24.5))
        # Far outside Puna (Brazil-ish)
        zf.writestr("outside.tif", make_tif_bytes(-50.0, -10.0, -49.0, -9.0))
    return path


@pytest.fixture
def tiny_binary_raster(tmp_path: Path) -> Path:
    """A small EPSG:4326 binary raster with a 3x3 wetland blob in the Puna bbox.

    Bounds: west=-67.5, south=-25.5, east=-66.5, north=-24.5 (well inside PUNA_BBOX).
    """
    path = tmp_path / "binary.tif"
    height, width = 20, 20
    data = np.zeros((height, width), dtype=np.uint8)
    # Single 3x3 blob centered at (10, 10).
    data[9:12, 9:12] = 1
    transform = from_bounds(-67.5, -25.5, -66.5, -24.5, width, height)
    with rasterio.open(
        path, "w", driver="GTiff",
        height=height, width=width, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)
    return path
```

The `io`, `zipfile`, `np`, `rasterio`, `from_bounds` imports must be available at the top of the file (`np`, `rasterio`, `from_bounds` already are from earlier tasks; `io` and `zipfile` are stdlib).

- [ ] **Step 2: Add `io` and `zipfile` imports at the top of conftest**

Verify the conftest's import block contains:

```python
import io
import json
import zipfile
from pathlib import Path
```

If `io` / `zipfile` are missing, add them.

- [ ] **Step 3: Verify fixtures import cleanly**

Run:

```bash
uv run pytest tests/acquisition/ --collect-only -q
```

Expected: 35 tests collected, no import errors.

- [ ] **Step 4: Commit**

```bash
git add tests/acquisition/conftest.py
git commit -m "Add tiny_zip_with_tifs and tiny_binary_raster fixtures"
```

---

## Task 3: wetland2026 — `extract_puna_tif()`

**Files:**
- Modify: `src/acquisition/datasets/wetland2026.py`
- Modify: `tests/acquisition/datasets/test_wetland2026.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/datasets/test_wetland2026.py`:

```python
import rasterio

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.wetland2026 import Wetland2026Dataset


def test_extract_puna_tif_filters_outside_tifs(tiny_zip_with_tifs, tmp_path):
    """Only TIFs whose bbox intersects PUNA_BBOX are mosaicked into the output."""
    ds = Wetland2026Dataset(url="https://example.com/wetland.zip")
    out = ds.extract_puna_tif(tiny_zip_with_tifs, tmp_path)

    assert out == tmp_path / "puna" / "wetland_puna.tif"
    assert out.exists()
    with rasterio.open(out) as src:
        # Bounds should match the "inside.tif" (Puna-overlapping fixture).
        assert src.bounds.left >= -68.0 and src.bounds.right <= -66.0
        assert src.bounds.bottom >= -26.0 and src.bounds.top <= -24.0


def test_extract_puna_tif_idempotent(tiny_zip_with_tifs, tmp_path):
    ds = Wetland2026Dataset(url="https://example.com/wetland.zip")
    out1 = ds.extract_puna_tif(tiny_zip_with_tifs, tmp_path)
    mtime1 = out1.stat().st_mtime_ns
    out2 = ds.extract_puna_tif(tiny_zip_with_tifs, tmp_path)
    assert out2 == out1
    assert out2.stat().st_mtime_ns == mtime1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/datasets/test_wetland2026.py::test_extract_puna_tif_filters_outside_tifs -v
```

Expected: `AttributeError: 'Wetland2026Dataset' object has no attribute 'extract_puna_tif'`.

- [ ] **Step 3: Implement `extract_puna_tif`**

In `src/acquisition/datasets/wetland2026.py`, add new imports at the top:

```python
import zipfile
import tempfile

from rasterio.merge import merge as rio_merge

from acquisition.aoi import PUNA_BBOX
```

Then append this method to the `Wetland2026Dataset` class:

```python
    def extract_puna_tif(self, raw_zip_path: Path, dest: Path) -> Path:
        """Extract Puna-overlapping TIFs from the wetland zip and mosaic them.

        Idempotent: returns the existing output if already present.
        """
        out_dir = dest / "puna"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / "wetland_puna.tif"
        if out.exists():
            return out

        kept_paths = []
        with tempfile.TemporaryDirectory() as tmp_dir, zipfile.ZipFile(raw_zip_path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".tif"):
                    continue
                extracted = Path(tmp_dir) / Path(name).name
                with zf.open(name) as src_zip, extracted.open("wb") as dst_file:
                    dst_file.write(src_zip.read())
                with rasterio.open(extracted) as src:
                    b = src.bounds
                    if (b.right < PUNA_BBOX.west or b.left > PUNA_BBOX.east
                            or b.top < PUNA_BBOX.south or b.bottom > PUNA_BBOX.north):
                        continue
                    kept_paths.append(extracted)

            if not kept_paths:
                raise RuntimeError(f"No Puna-overlapping TIFs found in {raw_zip_path}")

            srcs = [rasterio.open(p) for p in kept_paths]
            try:
                mosaic, transform = rio_merge(srcs)
                profile = srcs[0].profile.copy()
                profile.update(
                    height=mosaic.shape[1],
                    width=mosaic.shape[2],
                    transform=transform,
                )
                with rasterio.open(out, "w", **profile) as dst:
                    dst.write(mosaic)
            finally:
                for s in srcs:
                    s.close()
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/datasets/test_wetland2026.py -v
```

Expected: 4 passed (2 existing clip tests + 2 new extract tests).

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/datasets/wetland2026.py tests/acquisition/datasets/test_wetland2026.py
git commit -m "Add wetland2026 extract_puna_tif for zip-to-mosaic"
```

---

## Task 4: `gee.py` — auth + export_to_drive

**Files:**
- Create: `src/acquisition/gee.py`
- Create: `tests/acquisition/test_gee.py`

- [ ] **Step 1: Write the failing test**

Create `tests/acquisition/test_gee.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from acquisition.gee import export_to_drive, initialize


def test_initialize_calls_authenticate_and_initialize(mocker):
    auth = mocker.patch("ee.Authenticate")
    init = mocker.patch("ee.Initialize")

    initialize(project="my-project")

    auth.assert_called_once()
    init.assert_called_once()
    kwargs = init.call_args.kwargs
    assert kwargs["project"] == "my-project"
    assert "earthengine-highvolume.googleapis.com" in kwargs["opt_url"]


def test_export_to_drive_polls_until_done_then_mirrors(mocker, tmp_path):
    task = MagicMock()
    # Two polls: RUNNING, then COMPLETED.
    task.status.side_effect = [
        {"state": "RUNNING"},
        {"state": "COMPLETED"},
    ]
    export_factory = mocker.patch(
        "ee.batch.Export.image.toDrive",
        return_value=task,
    )
    sleep = mocker.patch("time.sleep")
    run = mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    image = MagicMock()
    region = MagicMock()

    out = export_to_drive(
        image=image,
        description="test_export",
        drive_folder="Lithium_v2/gee_exports/mapbiomas",
        file_prefix="bofedal_stable",
        region=region,
        local_dest=tmp_path / "Data/external/mapbiomas/raw",
        scale=30,
        timeout_min=30,
    )

    # Export was submitted with our params.
    export_factory.assert_called_once()
    kwargs = export_factory.call_args.kwargs
    assert kwargs["image"] is image
    assert kwargs["description"] == "test_export"
    assert kwargs["folder"] == "Lithium_v2/gee_exports/mapbiomas"
    assert kwargs["fileNamePrefix"] == "bofedal_stable"
    assert kwargs["region"] is region
    assert kwargs["scale"] == 30
    task.start.assert_called_once()
    # Polled twice.
    assert task.status.call_count == 2
    # rclone copy was called.
    rclone_args = run.call_args[0][0]
    assert rclone_args[0] == "rclone"
    assert rclone_args[1] == "copy"
    assert "gdrive:Lithium_v2/gee_exports/mapbiomas" in rclone_args
    assert out == tmp_path / "Data/external/mapbiomas/raw"


def test_export_to_drive_raises_on_gee_failure(mocker, tmp_path):
    task = MagicMock()
    task.status.return_value = {"state": "FAILED", "error_message": "asset not found"}
    mocker.patch("ee.batch.Export.image.toDrive", return_value=task)
    mocker.patch("time.sleep")

    with pytest.raises(RuntimeError, match="asset not found"):
        export_to_drive(
            image=MagicMock(),
            description="test_export",
            drive_folder="Lithium_v2/gee_exports/test",
            file_prefix="bofedal_stable",
            region=MagicMock(),
            local_dest=tmp_path / "out",
        )


def test_export_to_drive_times_out(mocker, tmp_path):
    task = MagicMock()
    task.status.return_value = {"state": "RUNNING"}
    mocker.patch("ee.batch.Export.image.toDrive", return_value=task)
    mocker.patch("time.sleep")

    with pytest.raises(TimeoutError):
        export_to_drive(
            image=MagicMock(),
            description="test_export",
            drive_folder="Lithium_v2/gee_exports/test",
            file_prefix="bofedal_stable",
            region=MagicMock(),
            local_dest=tmp_path / "out",
            timeout_min=0,  # immediately past deadline
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_gee.py -v
```

Expected: ImportError on `acquisition.gee`.

- [ ] **Step 3: Implement gee.py**

Create `src/acquisition/gee.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_gee.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/gee.py tests/acquisition/test_gee.py
git commit -m "Add gee.py wrapper for auth and Drive export"
```

---

## Task 5: `datasets/mapbiomas.py`

**Files:**
- Create: `src/acquisition/datasets/mapbiomas.py`
- Create: `tests/acquisition/datasets/test_mapbiomas.py`

- [ ] **Step 1: Write the failing test**

Create `tests/acquisition/datasets/test_mapbiomas.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.mapbiomas import MapbiomasDataset


def test_mapbiomas_fetch_initializes_and_exports(mocker, tmp_path):
    init = mocker.patch("acquisition.datasets.mapbiomas.initialize")
    export = mocker.patch(
        "acquisition.datasets.mapbiomas.export_to_drive",
        return_value=tmp_path / "raw",
    )
    # Stub the image-construction helper so we don't have to mock ee.* chains.
    image_stub = MagicMock(name="StableBofedalImage")
    mocker.patch(
        "acquisition.datasets.mapbiomas._build_stable_bofedal_image",
        return_value=image_stub,
    )
    # The region helper builds an ee.Geometry — stub it too.
    region_stub = MagicMock(name="PunaRegion")
    mocker.patch(
        "acquisition.datasets.mapbiomas._puna_region",
        return_value=region_stub,
    )

    ds = MapbiomasDataset(asset_id="projects/test/mapbiomas_coll2")
    out = ds.fetch(tmp_path)

    init.assert_called_once()
    export.assert_called_once()
    kw = export.call_args.kwargs
    assert kw["image"] is image_stub
    assert kw["region"] is region_stub
    assert kw["drive_folder"] == "Lithium_v2/gee_exports/mapbiomas"
    assert kw["file_prefix"].startswith("bofedal_stable_")
    assert kw["scale"] == 30
    assert out == tmp_path / "raw"


def test_mapbiomas_clip_returns_none(tmp_path):
    """Server-side already produced the Puna subset; local clip is a no-op."""
    ds = MapbiomasDataset(asset_id="projects/test/mapbiomas_coll2")
    assert ds.clip(tmp_path / "raw" / "x.tif", tmp_path, PUNA_BBOX) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/datasets/test_mapbiomas.py -v
```

Expected: ImportError on `acquisition.datasets.mapbiomas`.

- [ ] **Step 3: Implement `datasets/mapbiomas.py`**

Create `src/acquisition/datasets/mapbiomas.py`:

```python
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
        return export_to_drive(
            image=image,
            description=f"mapbiomas_stable_bofedal_{start_year}_{end_year}",
            drive_folder="Lithium_v2/gee_exports/mapbiomas",
            file_prefix=f"bofedal_stable_{start_year}_{end_year}",
            region=region,
            local_dest=raw_dir,
        )

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/datasets/test_mapbiomas.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/datasets/mapbiomas.py tests/acquisition/datasets/test_mapbiomas.py
git commit -m "Add MapbiomasDataset for stable-bofedal GEE export"
```

---

## Task 6: `bofedal_mask.py` — config + sieve

**Files:**
- Create: `src/acquisition/bofedal_mask.py`
- Create: `tests/acquisition/test_bofedal_mask.py`

- [ ] **Step 1: Write the failing test**

Create `tests/acquisition/test_bofedal_mask.py`:

```python
import numpy as np
import rasterio

from acquisition.bofedal_mask import BofedalMaskConfig, sieve_raster


def test_bofedal_mask_config_defaults():
    cfg = BofedalMaskConfig()
    assert cfg.min_pixels == 10
    assert cfg.aggregate_distance_m == 300.0
    assert cfg.min_area_m2 == 5_000.0
    assert cfg.accept_threshold == 0.50
    assert cfg.dispute_threshold == 0.10


def test_sieve_raster_removes_small_components(tmp_path):
    """Components smaller than min_pixels are zeroed."""
    src_path = tmp_path / "src.tif"
    out_path = tmp_path / "out.tif"
    data = np.zeros((20, 20), dtype=np.uint8)
    # 3x3 blob (9 pixels) — should be removed at min_pixels=10
    data[2:5, 2:5] = 1
    # 5x5 blob (25 pixels) — should be kept
    data[10:15, 10:15] = 1
    transform = rasterio.transform.from_bounds(-67.5, -25.5, -66.5, -24.5, 20, 20)
    with rasterio.open(
        src_path, "w", driver="GTiff", height=20, width=20, count=1,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(data, 1)

    sieve_raster(src_path, out_path, min_pixels=10)

    with rasterio.open(out_path) as src:
        out_data = src.read(1)
    # Small blob is gone; big blob remains.
    assert out_data[2:5, 2:5].sum() == 0
    assert out_data[10:15, 10:15].sum() == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v
```

Expected: ImportError on `acquisition.bofedal_mask`.

- [ ] **Step 3: Implement config + sieve**

Create `src/acquisition/bofedal_mask.py`:

```python
"""Bofedal-mask orchestrator: sieve → polygonize → aggregate-300m → reconcile → emit.

Inputs (binary rasters):
- MapBiomas-derived stable-bofedal raster (primary)
- Zenodo 2026 high-probability mask, Puna-extracted (reference)

Output:
- Data/bofedales_v2.geojson — accepted polygons (committed)
- Data/bofedales_v2_disputed.geojson — disputed companion (committed)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import rasterio
from rasterio.features import sieve


@dataclass(frozen=True)
class BofedalMaskConfig:
    min_pixels: int = 10                    # sieve cutoff (≈ 0.9 ha at 30 m)
    aggregate_distance_m: float = 300.0     # Izquierdo aggregate-polygons-300m
    min_area_m2: float = 5_000.0            # post-aggregate filter (~0.5 ha)
    accept_threshold: float = 0.50          # >= → accepted
    dispute_threshold: float = 0.10         # [dispute, accept) → disputed; below → dropped


def sieve_raster(src_path: Path, dst_path: Path, *, min_pixels: int) -> None:
    """rasterio.features.sieve wrapper: remove components below min_pixels."""
    with rasterio.open(src_path) as src:
        data = src.read(1)
        sieved = sieve(data, size=min_pixels)
        profile = src.profile.copy()
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(sieved, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/bofedal_mask.py tests/acquisition/test_bofedal_mask.py
git commit -m "Add BofedalMaskConfig and sieve helper"
```

---

## Task 7: `bofedal_mask.py` — polygonize

**Files:**
- Modify: `src/acquisition/bofedal_mask.py`
- Modify: `tests/acquisition/test_bofedal_mask.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/test_bofedal_mask.py`:

```python
def test_polygonize_returns_geodataframe_in_4326(tiny_binary_raster):
    from acquisition.bofedal_mask import polygonize

    gdf = polygonize(tiny_binary_raster)
    assert len(gdf) == 1
    assert gdf.crs.to_epsg() == 4326
    # The polygon should be inside the raster bounds.
    minx, miny, maxx, maxy = gdf.total_bounds
    assert minx >= -67.5 and maxx <= -66.5
    assert miny >= -25.5 and maxy <= -24.5


def test_polygonize_skips_zero_class(tiny_binary_raster):
    """Only value==1 pixels become polygons (zero is background)."""
    from acquisition.bofedal_mask import polygonize

    gdf = polygonize(tiny_binary_raster)
    # All polygons should have raster_value == 1.
    assert (gdf["raster_value"] == 1).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v -k polygonize
```

Expected: ImportError on `polygonize`.

- [ ] **Step 3: Implement `polygonize`**

Append to `src/acquisition/bofedal_mask.py`:

```python
import geopandas as gpd
from rasterio.features import shapes as rio_shapes
from shapely.geometry import shape


def polygonize(raster_path: Path) -> gpd.GeoDataFrame:
    """Vectorize a binary raster. Returns polygons for value==1 only."""
    with rasterio.open(raster_path) as src:
        data = src.read(1)
        transform = src.transform
        crs = src.crs

    geoms = []
    values = []
    for geom_dict, value in rio_shapes(data, mask=(data == 1), transform=transform):
        geoms.append(shape(geom_dict))
        values.append(int(value))

    return gpd.GeoDataFrame(
        {"raster_value": values, "geometry": geoms},
        crs=crs,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/bofedal_mask.py tests/acquisition/test_bofedal_mask.py
git commit -m "Add polygonize helper for bofedal_mask"
```

---

## Task 8: `bofedal_mask.py` — aggregate_300m

**Files:**
- Modify: `src/acquisition/bofedal_mask.py`
- Modify: `tests/acquisition/test_bofedal_mask.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/test_bofedal_mask.py`:

```python
def test_aggregate_300m_merges_close_polygons():
    """Two polygons whose nearest points are < 300 m apart get merged."""
    import geopandas as gpd
    from shapely.geometry import Polygon
    from acquisition.bofedal_mask import aggregate_300m

    # Two squares in degree-space, ~100 m apart (well within 300 m).
    # ~0.001 deg ≈ 111 m at this latitude.
    a = Polygon([(-67.000, -24.000), (-66.999, -24.000),
                 (-66.999, -23.999), (-67.000, -23.999)])
    b = Polygon([(-66.998, -24.000), (-66.997, -24.000),
                 (-66.997, -23.999), (-66.998, -23.999)])
    far = Polygon([(-66.500, -24.000), (-66.499, -24.000),
                   (-66.499, -23.999), (-66.500, -23.999)])
    gdf = gpd.GeoDataFrame({"raster_value": [1, 1, 1], "geometry": [a, b, far]},
                           crs="EPSG:4326")

    merged = aggregate_300m(gdf, distance_m=300.0)

    # a + b merged into one feature; far stays separate.
    assert len(merged) == 2


def test_aggregate_300m_keeps_far_polygons_separate():
    import geopandas as gpd
    from shapely.geometry import Polygon
    from acquisition.bofedal_mask import aggregate_300m

    # Two squares ~5 km apart.
    a = Polygon([(-67.05, -24.0), (-67.04, -24.0),
                 (-67.04, -23.99), (-67.05, -23.99)])
    b = Polygon([(-67.00, -24.0), (-66.99, -24.0),
                 (-66.99, -23.99), (-67.00, -23.99)])
    gdf = gpd.GeoDataFrame({"raster_value": [1, 1], "geometry": [a, b]},
                           crs="EPSG:4326")

    merged = aggregate_300m(gdf, distance_m=300.0)
    assert len(merged) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v -k aggregate_300m
```

Expected: ImportError on `aggregate_300m`.

- [ ] **Step 3: Implement `aggregate_300m`**

Append to `src/acquisition/bofedal_mask.py`:

```python
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.csgraph import connected_components
from shapely.ops import unary_union
from shapely.strtree import STRtree


_METRIC_CRS = "EPSG:32719"  # UTM Zone 19S, covers Argentine Puna


def aggregate_300m(gdf: gpd.GeoDataFrame, *, distance_m: float = 300.0) -> gpd.GeoDataFrame:
    """Merge polygons whose nearest-point distance is < distance_m.

    Algorithm: buffer each polygon by distance/2 in a metric CRS, build a
    spatial graph of pairwise intersections of the buffers, find connected
    components, and dissolve the ORIGINAL (un-buffered) polygons in each
    component. Returns a GeoDataFrame in the input CRS.
    """
    if len(gdf) == 0:
        return gdf.copy()

    input_crs = gdf.crs
    metric = gdf.to_crs(_METRIC_CRS)
    buffered = metric.geometry.buffer(distance_m / 2.0)

    tree = STRtree(list(buffered))
    n = len(buffered)
    adj = lil_matrix((n, n), dtype=bool)
    for i, geom in enumerate(buffered):
        for j in tree.query(geom):
            if i == j:
                continue
            if buffered.iloc[i].intersects(buffered.iloc[j]):
                adj[i, j] = True
                adj[j, i] = True

    n_components, labels = connected_components(adj.tocsr(), directed=False)

    dissolved_geoms = []
    for comp_id in range(n_components):
        idxs = np.where(labels == comp_id)[0]
        comp_geoms = [metric.geometry.iloc[i] for i in idxs]
        dissolved_geoms.append(unary_union(comp_geoms))

    out = gpd.GeoDataFrame(
        {"raster_value": [1] * len(dissolved_geoms), "geometry": dissolved_geoms},
        crs=_METRIC_CRS,
    )
    return out.to_crs(input_crs)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/bofedal_mask.py tests/acquisition/test_bofedal_mask.py
git commit -m "Add aggregate_300m for Izquierdo-style polygon merging"
```

---

## Task 9: `bofedal_mask.py` — reconcile

**Files:**
- Modify: `src/acquisition/bofedal_mask.py`
- Modify: `tests/acquisition/test_bofedal_mask.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/test_bofedal_mask.py`:

```python
def test_reconcile_classifies_overlap_buckets():
    import geopandas as gpd
    from shapely.geometry import Polygon
    from acquisition.bofedal_mask import reconcile

    # Primary polygons, each 1 unit x 1 unit (in degrees, conceptually).
    p_accept = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    p_disputed = Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])
    p_dropped = Polygon([(4, 0), (5, 0), (5, 1), (4, 1)])

    # Reference polygons:
    # - 80% overlap with p_accept
    # - 25% overlap with p_disputed
    # - 5% overlap with p_dropped
    r_for_accept = Polygon([(0, 0), (0.8, 0), (0.8, 1), (0, 1)])
    r_for_disputed = Polygon([(2, 0), (2.25, 0), (2.25, 1), (2, 1)])
    r_for_dropped = Polygon([(4, 0), (4.05, 0), (4.05, 1), (4, 1)])

    primary = gpd.GeoDataFrame(
        {"raster_value": [1, 1, 1], "geometry": [p_accept, p_disputed, p_dropped]},
        crs="EPSG:32719",
    )
    reference = gpd.GeoDataFrame(
        {"raster_value": [1, 1, 1],
         "geometry": [r_for_accept, r_for_disputed, r_for_dropped]},
        crs="EPSG:32719",
    )

    accepted, disputed = reconcile(
        primary, reference, accept_threshold=0.50, dispute_threshold=0.10,
    )

    # accepted: only p_accept (0.8 >= 0.5)
    assert len(accepted) == 1
    assert "overlap_with_reference" in accepted.columns
    assert abs(accepted["overlap_with_reference"].iloc[0] - 0.80) < 1e-6

    # disputed: only p_disputed (0.10 <= 0.25 < 0.50)
    assert len(disputed) == 1
    assert abs(disputed["overlap_with_reference"].iloc[0] - 0.25) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v -k reconcile
```

Expected: ImportError on `reconcile`.

- [ ] **Step 3: Implement `reconcile`**

Append to `src/acquisition/bofedal_mask.py`:

```python
def reconcile(
    primary: gpd.GeoDataFrame,
    reference: gpd.GeoDataFrame,
    *,
    accept_threshold: float = 0.50,
    dispute_threshold: float = 0.10,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Classify primary polygons by their area-weighted overlap with reference.

    Returns (accepted, disputed). Polygons with overlap < dispute_threshold are
    dropped (not returned).
    """
    if primary.crs != reference.crs:
        reference = reference.to_crs(primary.crs)

    ref_tree = STRtree(list(reference.geometry))
    overlaps = []
    for prim in primary.geometry:
        total_overlap_area = 0.0
        for j in ref_tree.query(prim):
            ref_geom = reference.geometry.iloc[j]
            if prim.intersects(ref_geom):
                total_overlap_area += prim.intersection(ref_geom).area
        ratio = total_overlap_area / prim.area if prim.area > 0 else 0.0
        overlaps.append(ratio)

    out = primary.copy()
    out["overlap_with_reference"] = overlaps

    accepted = out[out["overlap_with_reference"] >= accept_threshold].copy()
    disputed = out[
        (out["overlap_with_reference"] >= dispute_threshold)
        & (out["overlap_with_reference"] < accept_threshold)
    ].copy()
    return accepted, disputed
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/bofedal_mask.py tests/acquisition/test_bofedal_mask.py
git commit -m "Add reconcile for two-mask overlap classification"
```

---

## Task 10: `bofedal_mask.py` — `build_mask` orchestrator + emit

**Files:**
- Modify: `src/acquisition/bofedal_mask.py`
- Modify: `tests/acquisition/test_bofedal_mask.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/test_bofedal_mask.py`:

```python
def test_build_mask_end_to_end_writes_two_geojsons(tiny_binary_raster, tmp_path):
    """Same raster as primary and reference → all polygons accepted, no disputed."""
    from acquisition.bofedal_mask import BofedalMaskConfig, build_mask

    accepted_path = tmp_path / "bofedales_v2.geojson"
    disputed_path = tmp_path / "bofedales_v2_disputed.geojson"

    build_mask(
        primary_raster=tiny_binary_raster,
        reference_raster=tiny_binary_raster,
        accepted_out=accepted_path,
        disputed_out=disputed_path,
        config=BofedalMaskConfig(min_pixels=1, min_area_m2=0.0),  # don't filter the tiny test blob
    )

    assert accepted_path.exists()
    assert disputed_path.exists()

    import geopandas as gpd
    accepted = gpd.read_file(accepted_path)
    disputed = gpd.read_file(disputed_path)
    assert len(accepted) == 1
    assert len(disputed) == 0

    # Stable bofedal_id present and looks like a UUID5 string.
    bid = accepted["bofedal_id"].iloc[0]
    assert len(bid) == 36 and bid.count("-") == 4


def test_build_mask_bofedal_id_deterministic(tiny_binary_raster, tmp_path):
    from acquisition.bofedal_mask import BofedalMaskConfig, build_mask
    import geopandas as gpd

    accepted1 = tmp_path / "a1.geojson"
    disputed1 = tmp_path / "d1.geojson"
    accepted2 = tmp_path / "a2.geojson"
    disputed2 = tmp_path / "d2.geojson"

    cfg = BofedalMaskConfig(min_pixels=1, min_area_m2=0.0)
    build_mask(tiny_binary_raster, tiny_binary_raster, accepted1, disputed1, cfg)
    build_mask(tiny_binary_raster, tiny_binary_raster, accepted2, disputed2, cfg)

    a1 = gpd.read_file(accepted1)
    a2 = gpd.read_file(accepted2)
    assert a1["bofedal_id"].iloc[0] == a2["bofedal_id"].iloc[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v -k build_mask
```

Expected: ImportError on `build_mask`.

- [ ] **Step 3: Implement `build_mask`**

Append to `src/acquisition/bofedal_mask.py`:

```python
import tempfile
import uuid


_BOFEDAL_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _assign_bofedal_ids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out["bofedal_id"] = [
        str(uuid.uuid5(_BOFEDAL_NAMESPACE, geom.wkt))
        for geom in out.geometry
    ]
    return out


def _filter_min_area(gdf: gpd.GeoDataFrame, min_area_m2: float) -> gpd.GeoDataFrame:
    if min_area_m2 <= 0 or len(gdf) == 0:
        return gdf
    metric = gdf.to_crs(_METRIC_CRS)
    keep = metric.geometry.area >= min_area_m2
    return gdf[keep].copy()


def _prepare_polygons(
    raster: Path, cfg: BofedalMaskConfig
) -> gpd.GeoDataFrame:
    """Run sieve → polygonize → aggregate_300m → min-area filter on one raster."""
    with tempfile.TemporaryDirectory() as tmp:
        sieved = Path(tmp) / "sieved.tif"
        sieve_raster(raster, sieved, min_pixels=cfg.min_pixels)
        gdf = polygonize(sieved)
    if len(gdf) == 0:
        return gdf
    gdf = aggregate_300m(gdf, distance_m=cfg.aggregate_distance_m)
    gdf = _filter_min_area(gdf, cfg.min_area_m2)
    return gdf


def build_mask(
    primary_raster: Path,
    reference_raster: Path,
    accepted_out: Path,
    disputed_out: Path,
    config: BofedalMaskConfig | None = None,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Run the full bofedal-mask pipeline and write both GeoJSONs.

    Returns the (accepted, disputed) GeoDataFrames for convenience.
    """
    cfg = config or BofedalMaskConfig()

    primary = _prepare_polygons(primary_raster, cfg)
    reference = _prepare_polygons(reference_raster, cfg)

    accepted, disputed = reconcile(
        primary, reference,
        accept_threshold=cfg.accept_threshold,
        dispute_threshold=cfg.dispute_threshold,
    )
    accepted = _assign_bofedal_ids(accepted)
    disputed = _assign_bofedal_ids(disputed)

    accepted_out.parent.mkdir(parents=True, exist_ok=True)
    disputed_out.parent.mkdir(parents=True, exist_ok=True)
    accepted.to_file(accepted_out, driver="GeoJSON")
    disputed.to_file(disputed_out, driver="GeoJSON")
    return accepted, disputed
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_bofedal_mask.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/bofedal_mask.py tests/acquisition/test_bofedal_mask.py
git commit -m "Add build_mask orchestrator with deterministic bofedal_id"
```

---

## Task 11: `run.py` — register mapbiomas + `--build-mask` flag

**Files:**
- Modify: `src/acquisition/run.py`
- Modify: `tests/acquisition/test_run.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/test_run.py`:

```python
def test_run_build_mask_invokes_pipeline(mocker, tmp_path):
    from acquisition.run import run_build_mask

    build = mocker.patch("acquisition.bofedal_mask.build_mask")

    primary = tmp_path / "mapbiomas" / "raw" / "bofedal_stable.tif"
    reference = tmp_path / "wetland2026" / "puna" / "wetland_puna.tif"
    primary.parent.mkdir(parents=True)
    reference.parent.mkdir(parents=True)
    primary.touch()
    reference.touch()

    run_build_mask(
        external_root=tmp_path,
        repo_root=tmp_path / "_repo",
    )

    build.assert_called_once()
    kw = build.call_args.kwargs or {}
    # Normalize args/kwargs into a single dict.
    args = build.call_args.args
    all_args = {"primary_raster": args[0] if args else kw.get("primary_raster"),
                "reference_raster": args[1] if len(args) > 1 else kw.get("reference_raster"),
                "accepted_out": args[2] if len(args) > 2 else kw.get("accepted_out"),
                "disputed_out": args[3] if len(args) > 3 else kw.get("disputed_out")}
    assert all_args["primary_raster"] == primary
    assert all_args["reference_raster"] == reference
    assert all_args["accepted_out"] == tmp_path / "_repo" / "Data" / "bofedales_v2.geojson"
    assert all_args["disputed_out"] == tmp_path / "_repo" / "Data" / "bofedales_v2_disputed.geojson"


def test_run_build_mask_requires_inputs(tmp_path):
    from acquisition.run import run_build_mask

    with pytest.raises(FileNotFoundError, match="MapBiomas raster"):
        run_build_mask(external_root=tmp_path, repo_root=tmp_path / "_repo")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_run.py -v -k build_mask
```

Expected: ImportError on `run_build_mask`.

- [ ] **Step 3: Implement registry update + `run_build_mask`**

In `src/acquisition/run.py`, find the DATASET_REGISTRY dict and add `mapbiomas` to it. The block becomes:

```python
DATASET_REGISTRY: dict[str, Callable[[str], Dataset]] = {
    "usgs": lambda url: UsgsDataset(url=url),
    "izquierdo": lambda url: IzquierdoDataset(url=url),
    "wetland2026": lambda url: Wetland2026Dataset(url=url),
    "spei12": lambda url: SpeiDataset(
        url=url, key="spei12",
        filename="spei12.nc", clipped_filename="spei12_puna.nc",
    ),
    "spei24": lambda url: SpeiDataset(
        url=url, key="spei24",
        filename="spei24.nc", clipped_filename="spei24_puna.nc",
    ),
    # MapBiomas's "url" field is repurposed as the GEE asset ID.
    "mapbiomas": lambda url: MapbiomasDataset(asset_id=url),
}
```

Add the import near the existing dataset imports:

```python
from acquisition.datasets.mapbiomas import MapbiomasDataset
```

Then add the `run_build_mask` function before `main`:

```python
def run_build_mask(*, external_root: Path, repo_root: Path) -> None:
    """Run the polygonization + reconciliation step.

    Inputs: the latest MapBiomas raster (under external/mapbiomas/raw/) and
    the Puna-extracted Zenodo TIF (under external/wetland2026/puna/).
    Outputs: Data/bofedales_v2.geojson + Data/bofedales_v2_disputed.geojson.
    """
    from acquisition import bofedal_mask

    primary_dir = external_root / "mapbiomas" / "raw"
    primary_candidates = sorted(primary_dir.glob("*.tif"))
    if not primary_candidates:
        raise FileNotFoundError(
            f"MapBiomas raster not found in {primary_dir}. Run "
            "`python -m acquisition.run --only mapbiomas` first."
        )
    primary = primary_candidates[0]

    reference = external_root / "wetland2026" / "puna" / "wetland_puna.tif"
    if not reference.exists():
        raise FileNotFoundError(
            f"Zenodo Puna TIF not found at {reference}. Call "
            "Wetland2026Dataset.extract_puna_tif first."
        )

    accepted_out = repo_root / "Data" / "bofedales_v2.geojson"
    disputed_out = repo_root / "Data" / "bofedales_v2_disputed.geojson"

    bofedal_mask.build_mask(
        primary_raster=primary,
        reference_raster=reference,
        accepted_out=accepted_out,
        disputed_out=disputed_out,
    )
    print(f"wrote {accepted_out} and {disputed_out}", file=sys.stderr)
```

Then extend `main` to handle a `--build-mask` flag. Replace the argparse + dispatch block:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="acquisition.run")
    parser.add_argument("--manifest", type=Path, default=Path("Data/external/manifest.yaml"))
    parser.add_argument("--external-root", type=Path, default=Path("Data/external"))
    parser.add_argument("--remote-name", default="gdrive")
    parser.add_argument("--remote-root", default="Lithium_v2/external")
    parser.add_argument(
        "--only",
        help="Comma-separated list of dataset keys to process; default = all",
    )
    parser.add_argument(
        "--pull-only",
        action="store_true",
        help="Skip upstream fetches; mirror the shared Drive folder into "
             "external-root (team-bootstrap path, spec §8).",
    )
    parser.add_argument(
        "--build-mask",
        action="store_true",
        help="After (or instead of) acquisition, run the bofedal_mask pipeline "
             "and emit Data/bofedales_v2.geojson + disputed companion.",
    )
    args = parser.parse_args(argv)

    only = set(args.only.split(",")) if args.only else None
    drive = DriveRemote(remote_name=args.remote_name, root=args.remote_root)
    repo_root = Path.cwd()

    # If --only or --pull-only is set (or neither --only nor --build-mask), run acquisition.
    if args.pull_only or args.only or not args.build_mask:
        run(
            manifest_path=args.manifest,
            external_root=args.external_root,
            drive=drive,
            only=only,
            pull_only=args.pull_only,
        )

    if args.build_mask:
        run_build_mask(external_root=args.external_root, repo_root=repo_root)

    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/acquisition/test_run.py -v
```

Expected: 5 passed (3 existing + 2 new).

- [ ] **Step 5: Run the full suite**

Run:

```bash
uv run pytest tests/acquisition/ -q
```

Expected: all 46 tests pass (35 baseline + 11 new from this plan).

- [ ] **Step 6: Commit**

```bash
git add src/acquisition/run.py tests/acquisition/test_run.py
git commit -m "Register mapbiomas and add --build-mask driver flag"
```

---

## Task 12: Update `Data/external/manifest.yaml`

**Files:**
- Modify: `Data/external/manifest.yaml`

- [ ] **Step 1: Append the mapbiomas entry**

Add as a NEW entry at the end of `Data/external/manifest.yaml`:

```yaml
- key: mapbiomas
  title: "MapBiomas Argentina Coll. 2 — Puna y Altos Andes stable-bofedal raster"
  url: ""
  version: "Collection 2"
  license: "CC-BY-SA 4.0 (per MapBiomas terms)"
  clip_to_puna: false
  sha256: ""
  size_bytes: 0
  doi: ""
  handle: ""
  notes: |
    The `url` field is repurposed for the MapBiomas Coll. 2 image-collection
    asset ID — find it on https://argentina.mapbiomas.org/ ATBD or the
    MapBiomas-Argentina GitHub catalog and fill before first GEE run.
    The acquisition runs server-side in GEE (project ee-nunezrimedio-tesina):
    sums wetland-class years across 1998–2024, thresholds at 14 (≥50%),
    clips to PUNA_BBOX, exports to gdrive:Lithium_v2/gee_exports/mapbiomas/.
    Local mirror lands in Data/external/mapbiomas/raw/. Primary mask for
    Methodology v2 §3.1 (replaces deprecated Izquierdo entry); polygonized
    + reconciled against Zenodo 18339573 via `--build-mask`.
```

- [ ] **Step 2: Verify the manifest still loads**

Run:

```bash
uv run python -c "from pathlib import Path; from acquisition.manifest import load_manifest; e = load_manifest(Path('Data/external/manifest.yaml')); print(len(e), [x.key for x in e])"
```

Expected:

```
6 ['usgs', 'izquierdo', 'wetland2026', 'spei12', 'spei24', 'mapbiomas']
```

- [ ] **Step 3: Commit**

```bash
git add Data/external/manifest.yaml
git commit -m "Add mapbiomas manifest entry for GEE-mediated acquisition"
```

---

## Task 13: Document GEE setup + `--build-mask` in README

**Files:**
- Modify: `Data/external/README.md`

- [ ] **Step 1: Append the new section**

Append to `Data/external/README.md`:

```markdown

## GEE-mediated acquisition (Stage 0.5)

The `mapbiomas` dataset is GEE-mediated and needs Earth Engine auth.

### First-time GEE setup

```bash
uv run python -c "import ee; ee.Authenticate()"
```

This opens a browser window for OAuth. The token is cached at
`~/.config/earthengine/credentials` and shared with subsequent runs.
Earth Engine project: `ee-nunezrimedio-tesina` (configured in
`src/acquisition/datasets/mapbiomas.py`).

### Running the MapBiomas acquisition

```bash
uv run python -m acquisition.run --only mapbiomas
```

This submits a GEE export job (server-side bofedal stability raster) to
`gdrive:Lithium_v2/gee_exports/mapbiomas/`, polls until done, then
`rclone copy`s the result into `Data/external/mapbiomas/raw/`. Expect
~5 minutes for the GEE step on a typical bofedal raster (~tens of MB).

### Building the bofedal mask

After both MapBiomas and Zenodo wetland2026 have been acquired, build
the final v2 bofedal polygon mask:

```bash
uv run python -m acquisition.run --build-mask
```

This runs the sieve → polygonize → aggregate-300m → reconcile pipeline
and writes:

- `Data/bofedales_v2.geojson` — accepted bofedal polygons (committed)
- `Data/bofedales_v2_disputed.geojson` — polygons 10–50% reference
  overlap, for hand-review (committed)

Re-running with all inputs unchanged is idempotent.

You can combine acquisition and mask-build in one invocation:

```bash
uv run python -m acquisition.run --only mapbiomas --build-mask
```
```

- [ ] **Step 2: Commit**

```bash
git add Data/external/README.md
git commit -m "Document GEE setup and --build-mask flow"
```

---

## Task 14: Live smoke test (manual)

This is the one task that hits real GEE + Drive. It validates the full pipeline and produces the committed `bofedales_v2.geojson`.

**Files:**
- Modify: `Data/external/manifest.yaml` (asset_id + SHA pinning)
- Create: `Data/bofedales_v2.geojson` (committed)
- Create: `Data/bofedales_v2_disputed.geojson` (committed)

- [ ] **Step 1: Authenticate GEE**

If you haven't authenticated in this venv before:

```bash
uv run python -c "import ee; ee.Authenticate(); ee.Initialize(project='ee-nunezrimedio-tesina')"
```

Expected: browser OAuth flow completes, no error on `Initialize`.

- [ ] **Step 2: Resolve the MapBiomas Coll. 2 asset ID**

Visit https://argentina.mapbiomas.org/ and navigate to the Coll. 2
documentation / ATBD. Find the GEE image-collection asset ID for the
Puna y Altos Andes wetland classification (likely under
`projects/mapbiomas-argentina/...` or `projects/mapbiomas-public/...`).
A useful fallback: the MapBiomas GitHub `mapbiomas-argentina/integration`
repo lists asset paths in its README.

Edit `Data/external/manifest.yaml` and fill the `mapbiomas` entry's
`url:` field with the resolved asset ID.

- [ ] **Step 3: Verify the wetland2026 Zenodo TIF is already extracted**

Run:

```bash
ls Data/external/wetland2026/puna/wetland_puna.tif 2>&1
```

If missing, extract it first:

```bash
uv run python -c "
from pathlib import Path
from acquisition.datasets.wetland2026 import Wetland2026Dataset
ds = Wetland2026Dataset(url='')
ds.extract_puna_tif(
    Path('Data/external/wetland2026/raw/wetland2026_high_probabilities.zip'),
    Path('Data/external/wetland2026'),
)
"
```

- [ ] **Step 4: Run MapBiomas acquisition end-to-end**

Run:

```bash
uv run python -m acquisition.run --only mapbiomas
```

Expected: prints `[mapbiomas] fetching…`, takes a few minutes (GEE
server-side prep + export), then prints the manifest-update message.
A `.tif` lands at `Data/external/mapbiomas/raw/`.

- [ ] **Step 5: Run the mask-build step**

Run:

```bash
uv run python -m acquisition.run --build-mask
```

Expected: prints `wrote Data/bofedales_v2.geojson and
Data/bofedales_v2_disputed.geojson`.

- [ ] **Step 6: Inspect the outputs**

Run:

```bash
uv run python -c "
import geopandas as gpd
a = gpd.read_file('Data/bofedales_v2.geojson')
d = gpd.read_file('Data/bofedales_v2_disputed.geojson')
print(f'accepted: {len(a)} polygons, total area ~{a.to_crs(32719).geometry.area.sum()/1e6:.1f} km²')
print(f'disputed: {len(d)} polygons')
print('sample bofedal_id:', a['bofedal_id'].iloc[0] if len(a) else 'none')
"
```

Expected: meaningful polygon counts (thousands of accepted; some hundreds
disputed is plausible).

- [ ] **Step 7: Commit the manifest update + the two output GeoJSONs**

```bash
git add Data/external/manifest.yaml Data/bofedales_v2.geojson Data/bofedales_v2_disputed.geojson
git commit -m "Pin MapBiomas asset_id and ship bofedales_v2 + disputed"
```

- [ ] **Step 8: Verify idempotent re-run**

Run:

```bash
uv run python -m acquisition.run --only mapbiomas --build-mask
```

Expected: skips GEE (raster already local), re-runs mask build (overwrites
the two GeoJSONs with identical content because `bofedal_id` is deterministic).
`git status` should be clean afterwards.

---

## Self-review checklist

After completing all tasks, verify against the spec:

- [ ] **§3 inputs:** MapBiomas + Zenodo extraction wired correctly via Tasks 3 + 5 + 12.
- [ ] **§4 architecture:** new modules `gee.py`, `bofedal_mask.py`, `datasets/mapbiomas.py` exist; `wetland2026.py` extended; `run.py` registers mapbiomas + `--build-mask`.
- [ ] **§5 GEE strategy:** `initialize()` uses project `ee-nunezrimedio-tesina` and high-volume URL; `export_to_drive` polls, fails loud, mirrors via rclone.
- [ ] **§6 MapBiomas module:** `MapbiomasDataset` exposes `asset_id`, `wetland_classes`, `analysis_window`, `n_years_required`. Defaults match spec.
- [ ] **§7 polygonization:** sieve (Task 6), polygonize (Task 7), aggregate-300m via metric reprojection (Task 8).
- [ ] **§8 Zenodo extraction:** `extract_puna_tif` filters by bbox intersect + mosaics (Task 3).
- [ ] **§9 reconciliation:** thresholds 0.50/0.10; accepted ≥ 0.50, disputed in [0.10, 0.50) (Task 9).
- [ ] **§10 driver:** `--build-mask` flag works alone and in combination with `--only` (Task 11).
- [ ] **§11 storage:** Drive folder split between `gee_exports/` and `external/`; local follows `Data/external/<key>/raw/` convention.
- [ ] **§12 errors:** GEE failure raises; timeout raises; mask build requires both inputs present.
- [ ] **§13 testing:** unit + mocked-network coverage in `test_gee.py`, `test_mapbiomas.py`, `test_bofedal_mask.py`, extended `test_wetland2026.py`.
- [ ] **§14 docs:** README appendix + manifest notes both done.
