# Stage 3 — Per-Bofedal Annual Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `Data/bofedal_panel.parquet` — per-bofedal annual rows with NDVI (Landsat C2 SR 1998–2024), Sentinel-1 VV/VH (2014–2024), SPEI-12/24 growing-season means, elevation, containing salar, and mega-drought dummy — ready to join with Stage 2 treatments and feed Stage 4 estimation.

**Architecture:** New `src/panel/` subpackage with five focused modules (`ndvi.py`, `s1.py`, `spei.py`, `static_attrs.py`, `compose.py`) and a CLI driver (`run.py`). NDVI + S1 + SRTM run server-side in GEE via `reduceRegions`, exported as CSVs to Drive and `rclone`-mirrored locally; SPEI + salar join happen in pure Python against already-acquired NetCDFs and the USGS gdb. `compose.py` merges everything into the parquet.

**Tech Stack:** Python 3.11+, `earthengine-api`, `geopandas`, `xarray`, `rasterio`, `pyarrow`, `pandas`, `py7zr` (new), `pytest`, `pytest-mock`.

**Spec:** [docs/superpowers/specs/2026-06-16-stage-3-bofedal-panel-design.md](../specs/2026-06-16-stage-3-bofedal-panel-design.md)

---

## File Structure

**Created by this plan:**

```
src/panel/
├── __init__.py
├── ndvi.py
├── s1.py
├── spei.py
├── static_attrs.py
├── compose.py
└── run.py

tests/panel/
├── __init__.py
├── conftest.py
├── test_ndvi.py
├── test_s1.py
├── test_spei.py
├── test_static_attrs.py
├── test_compose.py
└── test_run.py

Data/
├── bofedal_panel.parquet            # COMMITTED (after smoke test)
└── bofedal_panel_schema.md          # COMMITTED

docs/superpowers/plans/
└── 2026-06-16-stage-3-bofedal-panel.md   # this file
```

**Modified by this plan:**

- `pyproject.toml` — add `py7zr>=0.20`, `pyarrow>=15.0`, `pandas>=2.0` to runtime deps
- `src/acquisition/gee.py` — add `export_table_to_drive` helper
- `tests/acquisition/test_gee.py` — add tests for the new helper
- `.gitignore` — exclude `Data/external/panel/*/` and `Data/external/usgs/extracted/`
- `Data/external/README.md` — append "Stage 3 panel build" section

---

## Notes for the engineer

- **Commit style:** match `git log` — imperative verbs, no `feat:`/`fix:` prefix. Examples: "Add Stage 3 bofedal-panel design spec", "Pin MapBiomas asset_id and ship bofedales_v2 + disputed".
- **Branch:** work on `claude/stage-0-mapbiomas-bofedal` (the current branch — Stage 3 work continues from here; we'll rebase / re-PR at the end).
- **Test command:** `uv run pytest tests/ -q`. Baseline before this plan: 55 passing.
- **GEE mocking:** never call live GEE in pytest. Patch `ee.Authenticate`, `ee.Initialize`, `ee.batch.Export.*`, `ee.Image`, `ee.ImageCollection` etc. with `pytest-mock`. The existing `tests/acquisition/test_gee.py` is the reference pattern.
- **GeoDataFrame fixtures:** `tests/panel/conftest.py::tiny_bofedales` provides 3 polygons in the Puna bbox; reuse it across module tests.
- **Bofedal IDs:** the `bofedales_v2.geojson` already has `bofedal_id` column (UUID5 strings from Stage 0.5). All panel modules join on this column.
- **GEE asset paths used in this plan:**
  - Landsat C2 SR: `LANDSAT/LT05/C02/T1_L2`, `LANDSAT/LE07/C02/T1_L2`, `LANDSAT/LC08/C02/T1_L2`, `LANDSAT/LC09/C02/T1_L2`
  - Sentinel-1 GRD: `COPERNICUS/S1_GRD`
  - SRTM: `USGS/SRTMGL1_003`

---

## Task 1: Add new runtime dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `py7zr`, `pyarrow`, `pandas` to runtime deps**

Edit `pyproject.toml` — change the `dependencies` list to include the three new entries (preserve existing alphabetical order):

```toml
dependencies = [
    "earthengine-api>=1.0",
    "geopandas>=0.14",
    "netcdf4>=1.6",
    "pandas>=2.0",
    "py7zr>=0.20",
    "pyarrow>=15.0",
    "pyyaml>=6.0",
    "rasterio>=1.3",
    "requests>=2.31",
    "scipy>=1.11",
    "tenacity>=8.2",
    "xarray>=2024.1",
]
```

- [ ] **Step 2: Lock and install**

Run:

```bash
uv sync --extra dev
```

Expected: resolves and installs the three new packages, no errors.

- [ ] **Step 3: Verify imports**

Run:

```bash
uv run python -c "import py7zr, pyarrow, pandas; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Confirm baseline tests still pass**

Run:

```bash
uv run pytest tests/ -q
```

Expected: `55 passed`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add py7zr + pyarrow + pandas for Stage 3 panel build"
```

---

## Task 2: Update `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append Stage 3 ignore rules**

Append to `.gitignore`:

```

# Stage 3 panel — GEE intermediate CSVs (regenerable, committed via SHA in manifest)
Data/external/panel/*/

# Stage 3 panel — USGS gdb extraction (regenerable from the .7z)
Data/external/usgs/extracted/
```

- [ ] **Step 2: Verify the ignore works**

Run from the repo root:

```bash
mkdir -p Data/external/panel/ndvi_gs Data/external/usgs/extracted
touch Data/external/panel/ndvi_gs/2020.csv Data/external/usgs/extracted/probe.txt
git status --short Data/external/panel Data/external/usgs/extracted
```

Expected: empty output (both directories ignored). If anything appears, the rules are wrong.

- [ ] **Step 3: Clean up the dry-run files**

Run:

```bash
rm -rf Data/external/panel Data/external/usgs/extracted
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "Ignore Stage 3 panel intermediates and USGS gdb unpack"
```

---

## Task 3: Bootstrap `src/panel/` package skeleton

**Files:**
- Create: `src/panel/__init__.py`
- Create: `tests/panel/__init__.py`
- Create: `tests/panel/conftest.py`
- Modify: `pyproject.toml` (add `src/panel` to hatch packages)

- [ ] **Step 1: Create empty package directories**

Run:

```bash
mkdir -p src/panel tests/panel
touch src/panel/__init__.py tests/panel/__init__.py
```

- [ ] **Step 2: Update hatch packages in `pyproject.toml`**

Edit the `[tool.hatch.build.targets.wheel]` block:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/acquisition", "src/panel"]
```

- [ ] **Step 3: Re-sync so the editable install picks up the new package**

Run:

```bash
uv sync --extra dev
```

Expected: clean re-resolution; no version changes.

- [ ] **Step 4: Verify the package imports**

Run:

```bash
uv run python -c "import panel; print(panel.__file__)"
```

Expected: prints the path ending in `src/panel/__init__.py`.

- [ ] **Step 5: Create `tests/panel/conftest.py` with shared fixtures**

Create `tests/panel/conftest.py`:

```python
"""Shared fixtures for the panel test suite.

`tiny_bofedales` provides 3 polygons in the Puna bbox with stable
bofedal_id values. Reused across module tests so each module's
expectations stay consistent.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon


_BOFEDAL_IDS = (
    "11111111-1111-5111-8111-111111111111",
    "22222222-2222-5222-8222-222222222222",
    "33333333-3333-5333-8333-333333333333",
)


@pytest.fixture
def tiny_bofedales() -> gpd.GeoDataFrame:
    """Three small square polygons inside PUNA_BBOX with stable UUIDs."""
    polys = [
        Polygon([(-67.0, -24.0), (-66.99, -24.0),
                 (-66.99, -23.99), (-67.0, -23.99)]),
        Polygon([(-66.5, -25.0), (-66.49, -25.0),
                 (-66.49, -24.99), (-66.5, -24.99)]),
        Polygon([(-67.5, -24.5), (-67.49, -24.5),
                 (-67.49, -24.49), (-67.5, -24.49)]),
    ]
    return gpd.GeoDataFrame(
        {"bofedal_id": list(_BOFEDAL_IDS), "geometry": polys},
        crs="EPSG:4326",
    )


@pytest.fixture
def tiny_bofedales_path(tiny_bofedales, tmp_path: Path) -> Path:
    """The same fixture written to disk as GeoJSON."""
    path = tmp_path / "tiny_bofedales.geojson"
    tiny_bofedales.to_file(path, driver="GeoJSON")
    return path


@pytest.fixture
def tiny_salars(tmp_path: Path) -> Path:
    """Two synthetic salar polygons covering known territory.

    Salar A covers bofedales[0]; Salar B covers bofedales[1].
    Bofedal[2] is intentionally outside any salar.
    """
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME": "Salar A"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-67.1, -24.1], [-66.9, -24.1],
                        [-66.9, -23.9], [-67.1, -23.9], [-67.1, -24.1],
                    ]],
                },
            },
            {
                "type": "Feature",
                "properties": {"NAME": "Salar B"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-66.6, -25.1], [-66.4, -25.1],
                        [-66.4, -24.9], [-66.6, -24.9], [-66.6, -25.1],
                    ]],
                },
            },
        ],
    }
    path = tmp_path / "tiny_salars.geojson"
    path.write_text(json.dumps(fc))
    return path
```

- [ ] **Step 6: Verify the fixtures collect**

Run:

```bash
uv run pytest tests/panel/ --collect-only -q
```

Expected: `no tests collected` (0 tests), no import errors.

- [ ] **Step 7: Commit**

```bash
git add src/panel tests/panel pyproject.toml uv.lock
git commit -m "Bootstrap src/panel package and shared test fixtures"
```

---

## Task 4: `acquisition/gee.py` — add `export_table_to_drive`

**Files:**
- Modify: `src/acquisition/gee.py`
- Modify: `tests/acquisition/test_gee.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/acquisition/test_gee.py`:

```python
def test_export_table_to_drive_submits_polls_mirrors(mocker, tmp_path):
    """Same lifecycle as export_to_drive but for ee.FeatureCollection -> CSV."""
    task = mocker.MagicMock()
    task.status.side_effect = [
        {"state": "RUNNING"},
        {"state": "COMPLETED"},
    ]
    export_factory = mocker.patch(
        "ee.batch.Export.table.toDrive",
        return_value=task,
    )
    mocker.patch("time.sleep")
    run = mocker.patch(
        "subprocess.run",
        return_value=mocker.MagicMock(returncode=0, stdout="", stderr=""),
    )

    from acquisition.gee import export_table_to_drive

    fake_table = mocker.MagicMock(name="ReducedTable")

    out = export_table_to_drive(
        table=fake_table,
        description="ndvi_gs_2020",
        drive_folder="Lithium_v2_gee_exports_panel_ndvi_gs",
        file_prefix="2020",
        local_dest=tmp_path / "panel/ndvi_gs",
        timeout_min=15,
    )

    export_factory.assert_called_once()
    kwargs = export_factory.call_args.kwargs
    assert kwargs["collection"] is fake_table
    assert kwargs["description"] == "ndvi_gs_2020"
    assert kwargs["folder"] == "Lithium_v2_gee_exports_panel_ndvi_gs"
    assert kwargs["fileNamePrefix"] == "2020"
    assert kwargs["fileFormat"] == "CSV"
    task.start.assert_called_once()
    assert task.status.call_count == 2
    rclone_args = run.call_args[0][0]
    assert rclone_args[0:2] == ["rclone", "copy"]
    assert "gdrive:Lithium_v2_gee_exports_panel_ndvi_gs" in rclone_args
    assert out == tmp_path / "panel/ndvi_gs"


def test_export_table_to_drive_raises_on_gee_failure(mocker, tmp_path):
    task = mocker.MagicMock()
    task.status.return_value = {"state": "FAILED", "error_message": "quota exceeded"}
    mocker.patch("ee.batch.Export.table.toDrive", return_value=task)
    mocker.patch("time.sleep")

    from acquisition.gee import export_table_to_drive

    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="quota exceeded"):
        export_table_to_drive(
            table=mocker.MagicMock(),
            description="ndvi_gs_2020",
            drive_folder="x",
            file_prefix="2020",
            local_dest=tmp_path / "out",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/acquisition/test_gee.py -v -k export_table_to_drive
```

Expected: ImportError — `cannot import name 'export_table_to_drive'`.

- [ ] **Step 3: Implement `export_table_to_drive`**

Append to `src/acquisition/gee.py`:

```python
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
        status = task.status()
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

Expected: 6 passed (4 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/acquisition/gee.py tests/acquisition/test_gee.py
git commit -m "Add export_table_to_drive for GEE FeatureCollection -> CSV"
```

---

## Task 5: `src/panel/ndvi.py` — Landsat C2 SR NDVI extraction

**Files:**
- Create: `src/panel/ndvi.py`
- Create: `tests/panel/test_ndvi.py`

- [ ] **Step 1: Write the failing test**

Create `tests/panel/test_ndvi.py`:

```python
"""Tests for panel.ndvi — Landsat C2 SR NDVI extraction."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_landsat_collection_for_year_picks_right_sensors(mocker):
    """Landsat 5 covers 1998-2012; L7 covers 1999-2013; L8 covers 2013+; L9 covers 2021+."""
    from panel.ndvi import _landsat_collection_for_window

    coll_mock = mocker.MagicMock(name="CombinedCollection")
    ic_mock = mocker.patch("ee.ImageCollection", return_value=coll_mock)
    coll_mock.merge.return_value = coll_mock
    coll_mock.filterBounds.return_value = coll_mock
    coll_mock.filterDate.return_value = coll_mock

    region = mocker.MagicMock(name="Region")
    _landsat_collection_for_window(
        start="2010-12-01", end="2011-02-28", region=region,
    )

    # Should have built collections for L5 (still active 2010) + L7.
    asset_calls = [c.args[0] for c in ic_mock.call_args_list]
    assert "LANDSAT/LT05/C02/T1_L2" in asset_calls
    assert "LANDSAT/LE07/C02/T1_L2" in asset_calls
    # L8 launched 2013 -- not active in the 2010-2011 window.
    assert "LANDSAT/LC08/C02/T1_L2" not in asset_calls


def test_landsat_collection_for_year_post_2013_uses_l8(mocker):
    from panel.ndvi import _landsat_collection_for_window

    coll_mock = mocker.MagicMock(name="CombinedCollection")
    ic_mock = mocker.patch("ee.ImageCollection", return_value=coll_mock)
    coll_mock.merge.return_value = coll_mock
    coll_mock.filterBounds.return_value = coll_mock
    coll_mock.filterDate.return_value = coll_mock

    region = mocker.MagicMock(name="Region")
    _landsat_collection_for_window(
        start="2020-12-01", end="2021-02-28", region=region,
    )

    asset_calls = [c.args[0] for c in ic_mock.call_args_list]
    assert "LANDSAT/LC08/C02/T1_L2" in asset_calls
    # L5 ended 2013, not in the 2020-2021 window.
    assert "LANDSAT/LT05/C02/T1_L2" not in asset_calls


def test_extract_year_skips_when_csv_exists(mocker, tmp_path):
    """Idempotency: if the local CSV already exists, do nothing."""
    from panel.ndvi import extract_year

    out_dir = tmp_path / "panel/ndvi_gs"
    out_dir.mkdir(parents=True)
    (out_dir / "2020.csv").write_text("bofedal_id,ndvi_gs_median\n")

    init = mocker.patch("panel.ndvi.initialize")
    export = mocker.patch("panel.ndvi.export_table_to_drive")

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="bofedales_gdf"),
        window="growing_season",
        local_dest=out_dir,
    )

    init.assert_not_called()
    export.assert_not_called()


def test_extract_year_submits_export_with_right_metadata(mocker, tmp_path):
    """When the CSV is missing, submit a GEE export with the right metadata."""
    from panel.ndvi import extract_year

    out_dir = tmp_path / "panel/ndvi_gs"
    # Stub the heavy GEE machinery; we only care about the metadata flowing through.
    mocker.patch("panel.ndvi.initialize")
    mocker.patch("panel.ndvi._landsat_collection_for_window")
    mocker.patch("panel.ndvi._compute_ndvi_image")
    mocker.patch("panel.ndvi._bofedales_to_fc")
    mocker.patch("panel.ndvi._reduce_to_table")
    export = mocker.patch(
        "panel.ndvi.export_table_to_drive",
        return_value=out_dir,
    )

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="bofedales_gdf"),
        window="growing_season",
        local_dest=out_dir,
    )

    export.assert_called_once()
    kw = export.call_args.kwargs
    assert kw["description"] == "ndvi_gs_2020"
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_panel_ndvi_gs"
    assert kw["file_prefix"] == "2020"
    assert kw["local_dest"] == out_dir


def test_window_for_growing_season_uses_austral_summer():
    """Dec y-1 -> Feb y."""
    from panel.ndvi import _window_dates

    start, end = _window_dates(year=2020, window="growing_season")
    assert start == "2019-12-01"
    assert end == "2020-02-29"  # 2020 is a leap year


def test_window_for_annual_uses_calendar_year():
    from panel.ndvi import _window_dates

    start, end = _window_dates(year=2020, window="annual")
    assert start == "2020-01-01"
    assert end == "2020-12-31"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/panel/test_ndvi.py -v
```

Expected: ImportError on `panel.ndvi`.

- [ ] **Step 3: Implement `src/panel/ndvi.py`**

Create `src/panel/ndvi.py`:

```python
"""Landsat C2 SR NDVI extraction per (bofedal, year).

For each year + window (growing-season or annual), build a server-side
image collection of Landsat 5/7/8/9 Collection 2 Surface Reflectance
scenes, cloud-mask via QA_PIXEL, compute per-pixel NDVI, take the
median across scenes, and reduceRegions over the bofedal polygons.
Exports one CSV per (window, year) to Drive and mirrors locally.
"""
from __future__ import annotations

import calendar
from pathlib import Path

import ee

from acquisition.aoi import PUNA_BBOX
from acquisition.gee import export_table_to_drive, initialize


# Sensor coverage windows (start_year, end_year inclusive).
_LANDSAT_ERAS: tuple[tuple[str, int, int], ...] = (
    ("LANDSAT/LT05/C02/T1_L2", 1984, 2012),
    ("LANDSAT/LE07/C02/T1_L2", 1999, 2024),  # SLC-off after 2003 but still useful
    ("LANDSAT/LC08/C02/T1_L2", 2013, 2024),
    ("LANDSAT/LC09/C02/T1_L2", 2021, 2024),
)


def _puna_region() -> "ee.Geometry":
    return ee.Geometry.Rectangle(
        [PUNA_BBOX.west, PUNA_BBOX.south, PUNA_BBOX.east, PUNA_BBOX.north]
    )


def _window_dates(*, year: int, window: str) -> tuple[str, str]:
    """Return (start, end) ISO dates for the named window in the given year."""
    if window == "growing_season":
        # Austral summer: Dec (year-1) -> Feb (year), inclusive of Feb's last day.
        last_day_feb = calendar.monthrange(year, 2)[1]
        return f"{year - 1}-12-01", f"{year:04d}-02-{last_day_feb:02d}"
    if window == "annual":
        return f"{year:04d}-01-01", f"{year:04d}-12-31"
    raise ValueError(f"unknown window {window!r}; expected growing_season|annual")


def _landsat_collection_for_window(
    *, start: str, end: str, region: "ee.Geometry"
) -> "ee.ImageCollection":
    """Combine Landsat 5/7/8/9 scenes active during the window."""
    start_year = int(start[:4])
    end_year = int(end[:4])
    combined: ee.ImageCollection | None = None
    for asset_id, sensor_start, sensor_end in _LANDSAT_ERAS:
        if end_year < sensor_start or start_year > sensor_end:
            continue
        coll = (
            ee.ImageCollection(asset_id)
            .filterBounds(region)
            .filterDate(start, end)
        )
        combined = coll if combined is None else combined.merge(coll)
    if combined is None:
        raise RuntimeError(
            f"No Landsat sensors active for {start}..{end}"
        )
    return combined


def _ndvi_band_pair(asset_id: str) -> tuple[str, str]:
    """Return (NIR, Red) Collection 2 SR band names for a given Landsat sensor."""
    if asset_id.endswith("LT05/C02/T1_L2") or asset_id.endswith("LE07/C02/T1_L2"):
        return "SR_B4", "SR_B3"
    return "SR_B5", "SR_B4"  # L8 + L9


def _compute_ndvi_image(coll: "ee.ImageCollection") -> "ee.Image":
    """Apply Collection 2 scaling, QA-mask, compute NDVI, take per-pixel median."""

    def per_scene(img: ee.Image) -> ee.Image:
        asset_id = ee.String(img.get("system:id"))
        # Apply scaling factors: surface reflectance = DN * 0.0000275 - 0.2.
        scaled = img.multiply(0.0000275).add(-0.2)
        qa = img.select("QA_PIXEL")
        # Bit 3 = cloud, bit 4 = cloud shadow, bit 2 = cirrus, bit 1 = dilated cloud.
        clear = (
            qa.bitwiseAnd(1 << 3).eq(0)
            .And(qa.bitwiseAnd(1 << 4).eq(0))
            .And(qa.bitwiseAnd(1 << 2).eq(0))
        )
        # Pick NIR + Red dynamically (L5/L7 vs L8/L9).
        nir = ee.Algorithms.If(
            asset_id.match("LC08|LC09"),
            scaled.select("SR_B5"),
            scaled.select("SR_B4"),
        )
        red = ee.Algorithms.If(
            asset_id.match("LC08|LC09"),
            scaled.select("SR_B4"),
            scaled.select("SR_B3"),
        )
        nir_img = ee.Image(nir).updateMask(clear)
        red_img = ee.Image(red).updateMask(clear)
        ndvi = nir_img.subtract(red_img).divide(nir_img.add(red_img))
        return ndvi.rename("NDVI").copyProperties(img, ["system:time_start"])

    return coll.map(per_scene).median()


def _bofedales_to_fc(bofedales_gdf) -> "ee.FeatureCollection":
    """Convert a GeoDataFrame to ee.FeatureCollection, carrying bofedal_id."""
    features = []
    for _, row in bofedales_gdf.iterrows():
        geom_geojson = row.geometry.__geo_interface__
        features.append(
            ee.Feature(
                ee.Geometry(geom_geojson),
                {"bofedal_id": str(row["bofedal_id"])},
            )
        )
    return ee.FeatureCollection(features)


def _reduce_to_table(
    image: "ee.Image", fc: "ee.FeatureCollection"
) -> "ee.FeatureCollection":
    """polygon-wise median + count of contributing pixels."""
    reducer = ee.Reducer.median().combine(ee.Reducer.count(), "", True)
    return image.reduceRegions(collection=fc, reducer=reducer, scale=30)


def extract_year(
    *,
    year: int,
    bofedales,
    window: str,
    local_dest: Path,
) -> Path:
    """Submit a GEE export for one (year, window). Idempotent.

    `bofedales` is a GeoDataFrame with columns `bofedal_id` and `geometry`.
    `window` is `growing_season` or `annual`.
    """
    out_csv = local_dest / f"{year}.csv"
    if out_csv.exists():
        return out_csv

    initialize()
    start, end = _window_dates(year=year, window=window)
    region = _puna_region()
    coll = _landsat_collection_for_window(start=start, end=end, region=region)
    ndvi_img = _compute_ndvi_image(coll)
    fc = _bofedales_to_fc(bofedales)
    table = _reduce_to_table(ndvi_img, fc)

    suffix = "gs" if window == "growing_season" else "annual"
    export_table_to_drive(
        table=table,
        description=f"ndvi_{suffix}_{year}",
        drive_folder=f"Lithium_v2_gee_exports_panel_ndvi_{suffix}",
        file_prefix=str(year),
        local_dest=local_dest,
    )
    return out_csv
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/panel/test_ndvi.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/panel/ndvi.py tests/panel/test_ndvi.py
git commit -m "Add panel.ndvi for Landsat C2 SR NDVI extraction"
```

---

## Task 6: `src/panel/s1.py` — Sentinel-1 VV/VH backscatter

**Files:**
- Create: `src/panel/s1.py`
- Create: `tests/panel/test_s1.py`

- [ ] **Step 1: Write the failing test**

Create `tests/panel/test_s1.py`:

```python
"""Tests for panel.s1 — Sentinel-1 GRD backscatter extraction."""
from __future__ import annotations

import pytest


def test_extract_year_skips_pre_2014():
    """Sentinel-1 GRD doesn't exist before 2014; raise loudly."""
    from panel.s1 import extract_year

    with pytest.raises(ValueError, match="2014"):
        extract_year(year=2013, bofedales=None, polarization="VV", local_dest=None)


def test_extract_year_skips_when_csv_exists(mocker, tmp_path):
    from panel.s1 import extract_year

    out_dir = tmp_path / "panel/s1_vv"
    out_dir.mkdir(parents=True)
    (out_dir / "2020.csv").write_text("bofedal_id,s1_vv_db_median\n")

    init = mocker.patch("panel.s1.initialize")
    export = mocker.patch("panel.s1.export_table_to_drive")

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(),
        polarization="VV",
        local_dest=out_dir,
    )
    init.assert_not_called()
    export.assert_not_called()


def test_extract_year_filters_to_descending_iw(mocker, tmp_path):
    """Verify the S1 collection is filtered to IW + descending + the right polarization."""
    from panel.s1 import extract_year

    out_dir = tmp_path / "panel/s1_vv"
    mocker.patch("panel.s1.initialize")
    coll_mock = mocker.MagicMock(name="S1Collection")
    coll_mock.filterBounds.return_value = coll_mock
    coll_mock.filterDate.return_value = coll_mock
    coll_mock.filter.return_value = coll_mock
    mocker.patch("ee.ImageCollection", return_value=coll_mock)
    mocker.patch("panel.s1._bofedales_to_fc")
    mocker.patch("panel.s1._reduce_to_table")
    mocker.patch("panel.s1.export_table_to_drive", return_value=out_dir)

    # Capture the ee.Filter constructions so we can assert what was filtered on.
    filter_eq = mocker.patch("ee.Filter.eq", side_effect=lambda *args: ("eq", args))
    filter_list_contains = mocker.patch(
        "ee.Filter.listContains", side_effect=lambda *args: ("contains", args)
    )

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="gdf"),
        polarization="VV",
        local_dest=out_dir,
    )

    # We expect filters on instrumentMode=IW, orbitProperties_pass=DESCENDING,
    # and that the polarization VV is in transmitterReceiverPolarisation list.
    filter_args = [c.args for c in filter_eq.call_args_list]
    list_args = [c.args for c in filter_list_contains.call_args_list]
    assert ("instrumentMode", "IW") in filter_args
    assert ("orbitProperties_pass", "DESCENDING") in filter_args
    assert ("transmitterReceiverPolarisation", "VV") in list_args


def test_extract_year_export_description_includes_polarization(mocker, tmp_path):
    from panel.s1 import extract_year

    out_dir = tmp_path / "panel/s1_vh"
    mocker.patch("panel.s1.initialize")
    coll = mocker.MagicMock()
    coll.filterBounds.return_value = coll
    coll.filterDate.return_value = coll
    coll.filter.return_value = coll
    mocker.patch("ee.ImageCollection", return_value=coll)
    mocker.patch("panel.s1._bofedales_to_fc")
    mocker.patch("panel.s1._reduce_to_table")
    mocker.patch("ee.Filter.eq")
    mocker.patch("ee.Filter.listContains")
    export = mocker.patch("panel.s1.export_table_to_drive", return_value=out_dir)

    extract_year(
        year=2020,
        bofedales=mocker.MagicMock(name="gdf"),
        polarization="VH",
        local_dest=out_dir,
    )

    kw = export.call_args.kwargs
    assert kw["description"] == "s1_vh_2020"
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_panel_s1_vh"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/panel/test_s1.py -v
```

Expected: ImportError on `panel.s1`.

- [ ] **Step 3: Implement `src/panel/s1.py`**

Create `src/panel/s1.py`:

```python
"""Sentinel-1 GRD VV/VH backscatter median per (bofedal, year), in dB.

Filters to IW mode + descending orbit + the requested polarization, converts
amplitude to dB (10 * log10), takes the per-pixel median across the year,
and reduces over the bofedal polygons.
"""
from __future__ import annotations

from pathlib import Path

import ee

from acquisition.aoi import PUNA_BBOX
from acquisition.gee import export_table_to_drive, initialize


_S1_ASSET = "COPERNICUS/S1_GRD"
_S1_AVAILABLE_FROM = 2014


def _puna_region() -> "ee.Geometry":
    return ee.Geometry.Rectangle(
        [PUNA_BBOX.west, PUNA_BBOX.south, PUNA_BBOX.east, PUNA_BBOX.north]
    )


def _bofedales_to_fc(bofedales_gdf) -> "ee.FeatureCollection":
    features = []
    for _, row in bofedales_gdf.iterrows():
        features.append(
            ee.Feature(
                ee.Geometry(row.geometry.__geo_interface__),
                {"bofedal_id": str(row["bofedal_id"])},
            )
        )
    return ee.FeatureCollection(features)


def _reduce_to_table(
    image: "ee.Image", fc: "ee.FeatureCollection"
) -> "ee.FeatureCollection":
    reducer = ee.Reducer.median().combine(ee.Reducer.count(), "", True)
    return image.reduceRegions(collection=fc, reducer=reducer, scale=30)


def extract_year(
    *,
    year: int,
    bofedales,
    polarization: str,
    local_dest: Path,
) -> Path:
    """Submit a GEE export for one (year, polarization). Idempotent."""
    if year < _S1_AVAILABLE_FROM:
        raise ValueError(
            f"Sentinel-1 GRD is not available before {_S1_AVAILABLE_FROM}; got {year}"
        )

    out_csv = local_dest / f"{year}.csv"
    if out_csv.exists():
        return out_csv

    initialize()
    region = _puna_region()
    coll = (
        ee.ImageCollection(_S1_ASSET)
        .filterBounds(region)
        .filterDate(f"{year:04d}-01-01", f"{year:04d}-12-31")
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", polarization))
    )
    # COPERNICUS/S1_GRD is already in dB after the standard preprocessing chain;
    # the raw band values are amplitude in dB scale. Take the per-pixel median.
    band = coll.select(polarization).median()
    fc = _bofedales_to_fc(bofedales)
    table = _reduce_to_table(band, fc)

    pol_lower = polarization.lower()
    export_table_to_drive(
        table=table,
        description=f"s1_{pol_lower}_{year}",
        drive_folder=f"Lithium_v2_gee_exports_panel_s1_{pol_lower}",
        file_prefix=str(year),
        local_dest=local_dest,
    )
    return out_csv
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/panel/test_s1.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/panel/s1.py tests/panel/test_s1.py
git commit -m "Add panel.s1 for Sentinel-1 GRD VV/VH backscatter extraction"
```

---

## Task 7: `src/panel/spei.py` — local NetCDF extract

**Files:**
- Create: `src/panel/spei.py`
- Create: `tests/panel/test_spei.py`

- [ ] **Step 1: Write the failing test**

Create `tests/panel/test_spei.py`:

```python
"""Tests for panel.spei — local NetCDF -> per-bofedal-year extract."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr


@pytest.fixture
def synthetic_spei(tmp_path):
    """Build a tiny SPEI NetCDF with known per-cell values for testing.

    Grid: 0.5° from -180 to 180 lon, -90 to 90 lat. Monthly 2018-01..2024-12.
    The bofedales fixture sits around (-67, -24); we set those cells to known values
    so the extract math is verifiable.
    """
    path = tmp_path / "spei.nc"
    lons = np.arange(-179.75, 180.0, 0.5)
    lats = np.arange(-89.75, 90.0, 0.5)
    times = np.array(
        [np.datetime64(f"{y:04d}-{m:02d}-01") for y in range(2018, 2025) for m in range(1, 13)]
    )
    rng = np.random.default_rng(42)
    data = rng.standard_normal((len(times), len(lats), len(lons))).astype("float32")
    # Fix known values at the bofedal-1 cell: lon -67, lat -24 ->
    # cell-center lon -66.75, lat -23.75 (nearest 0.5° centers).
    bof1_lon_idx = int(np.argmin(np.abs(lons - (-66.75))))
    bof1_lat_idx = int(np.argmin(np.abs(lats - (-23.75))))
    # Set Dec 2019 = 0.5, Jan 2020 = 1.0, Feb 2020 = -0.2 -> mean for gs 2020 = 0.4333...
    dec_2019 = (2019 - 2018) * 12 + 11
    jan_2020 = (2020 - 2018) * 12 + 0
    feb_2020 = (2020 - 2018) * 12 + 1
    data[dec_2019, bof1_lat_idx, bof1_lon_idx] = 0.5
    data[jan_2020, bof1_lat_idx, bof1_lon_idx] = 1.0
    data[feb_2020, bof1_lat_idx, bof1_lon_idx] = -0.2
    ds = xr.Dataset(
        {"spei": (("time", "lat", "lon"), data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds.to_netcdf(path)
    return path


def test_growing_season_window_returns_dec_to_feb():
    """Helper exposes (start, end) for the growing-season window of a given year."""
    from panel.spei import _growing_season_window

    start, end = _growing_season_window(year=2020)
    assert str(start) == "2019-12-01" or str(start.astype("datetime64[D]")) == "2019-12-01"
    # Window ends inclusive on Feb 28 or 29.
    assert str(end).startswith("2020-02")


def test_extract_returns_per_bofedal_per_year_rows(tiny_bofedales, synthetic_spei):
    """The first bofedal's gs 2020 mean should match the known synthetic values."""
    from panel.spei import extract

    df = extract(
        nc_path=synthetic_spei,
        bofedales=tiny_bofedales,
        years=range(2020, 2021),
        column="spei_12_gs_mean",
    )

    # One row per (bofedal_id, year).
    assert set(df.columns) == {"bofedal_id", "year", "spei_12_gs_mean"}
    assert len(df) == 3
    bofedal_1 = "11111111-1111-5111-8111-111111111111"
    val = df.loc[df["bofedal_id"] == bofedal_1, "spei_12_gs_mean"].iloc[0]
    # (0.5 + 1.0 + -0.2) / 3 = 0.43333...
    assert abs(val - 0.43333333) < 1e-5


def test_extract_handles_multiple_years(tiny_bofedales, synthetic_spei):
    from panel.spei import extract

    df = extract(
        nc_path=synthetic_spei,
        bofedales=tiny_bofedales,
        years=range(2020, 2023),
        column="spei_12_gs_mean",
    )
    assert len(df) == 3 * 3  # 3 bofedales * 3 years
    assert set(df["year"]) == {2020, 2021, 2022}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/panel/test_spei.py -v
```

Expected: ImportError on `panel.spei`.

- [ ] **Step 3: Implement `src/panel/spei.py`**

Create `src/panel/spei.py`:

```python
"""SPEI per-bofedal growing-season mean extraction from local NetCDFs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import xarray as xr


def _growing_season_window(*, year: int):
    """Return numpy datetime64 (start, end) for austral summer Dec(y-1) - Feb(y)."""
    start = np.datetime64(f"{year - 1:04d}-12-01")
    # Feb end is 28 in non-leap, 29 in leap; xarray .sel slice end is inclusive on dates.
    feb_last = "29" if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else "28"
    end = np.datetime64(f"{year:04d}-02-{feb_last}")
    return start, end


def extract(
    *,
    nc_path: Path,
    bofedales,  # GeoDataFrame with bofedal_id + geometry
    years: Iterable[int],
    column: str,
    var_name: str = "spei",
) -> pd.DataFrame:
    """Open SPEI NetCDF; for each (bofedal, year) take the growing-season mean.

    Many bofedales will share a 0.5° SPEI cell — that's intentional, SPEI is
    a basin-scale climate signal.
    """
    centroids = bofedales.set_geometry("geometry").geometry.centroid
    rows = []
    with xr.open_dataset(nc_path) as ds:
        var = ds[var_name]
        for year in years:
            start, end = _growing_season_window(year=year)
            window = var.sel(time=slice(start, end))
            window_mean = window.mean("time")
            for bid, centroid in zip(bofedales["bofedal_id"], centroids):
                value = window_mean.sel(
                    lon=centroid.x, lat=centroid.y, method="nearest"
                ).item()
                rows.append({"bofedal_id": str(bid), "year": int(year), column: value})
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/panel/test_spei.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/panel/spei.py tests/panel/test_spei.py
git commit -m "Add panel.spei for SPEI per-bofedal-year growing-season extract"
```

---

## Task 8: `src/panel/static_attrs.py` — SRTM elevation + USGS salar join

**Files:**
- Create: `src/panel/static_attrs.py`
- Create: `tests/panel/test_static_attrs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/panel/test_static_attrs.py`:

```python
"""Tests for panel.static_attrs — elevation + USGS salar join."""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pytest


def test_extract_elevation_submits_srtm_export(mocker, tmp_path):
    """Elevation pulls SRTM mean per bofedal via reduceRegions."""
    from panel.static_attrs import extract_elevation

    mocker.patch("panel.static_attrs.initialize")
    img_mock = mocker.MagicMock(name="SRTMImage")
    image_factory = mocker.patch("ee.Image", return_value=img_mock)
    mocker.patch("panel.static_attrs._bofedales_to_fc")
    mocker.patch("panel.static_attrs._reduce_to_table")
    export = mocker.patch(
        "panel.static_attrs.export_table_to_drive",
        return_value=tmp_path,
    )

    extract_elevation(bofedales=mocker.MagicMock(), local_dest=tmp_path)

    image_factory.assert_called_with("USGS/SRTMGL1_003")
    kw = export.call_args.kwargs
    assert kw["file_prefix"] == "elevation"
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_panel_elevation"


def test_extract_containing_salar_largest_overlap_wins(tiny_bofedales, tiny_salars, tmp_path):
    """Each bofedal is assigned the salar with the largest intersection area."""
    from panel.static_attrs import extract_containing_salar_from_layer

    salars_gdf = gpd.read_file(tiny_salars)

    df = extract_containing_salar_from_layer(
        bofedales=tiny_bofedales,
        salars=salars_gdf,
    )

    assert set(df.columns) == {"bofedal_id", "containing_salar"}
    assert len(df) == 3
    # Bofedal 0 -> Salar A, bofedal 1 -> Salar B, bofedal 2 -> NaN (outside).
    expected = {
        "11111111-1111-5111-8111-111111111111": "Salar A",
        "22222222-2222-5222-8222-222222222222": "Salar B",
        "33333333-3333-5333-8333-333333333333": None,
    }
    for bid, want in expected.items():
        got = df.loc[df["bofedal_id"] == bid, "containing_salar"].iloc[0]
        if want is None:
            assert got is None or (isinstance(got, float) and got != got)  # NaN check
        else:
            assert got == want


def test_unpack_usgs_archive_idempotent(mocker, tmp_path):
    """If the extracted directory already has content, do not re-unpack."""
    from panel.static_attrs import unpack_usgs_archive

    target = tmp_path / "extracted"
    target.mkdir()
    (target / "marker.txt").touch()

    unpack = mocker.patch("py7zr.unpack_7zarchive")

    unpack_usgs_archive(
        archive=tmp_path / "usgs.gdb.7z",
        target_dir=target,
    )

    unpack.assert_not_called()


def test_unpack_usgs_archive_calls_py7zr_on_missing(mocker, tmp_path):
    from panel.static_attrs import unpack_usgs_archive

    target = tmp_path / "extracted"
    archive = tmp_path / "usgs.gdb.7z"
    archive.touch()

    unpack = mocker.patch("py7zr.unpack_7zarchive")

    unpack_usgs_archive(archive=archive, target_dir=target)

    unpack.assert_called_once_with(str(archive), str(target))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/panel/test_static_attrs.py -v
```

Expected: ImportError on `panel.static_attrs`.

- [ ] **Step 3: Implement `src/panel/static_attrs.py`**

Create `src/panel/static_attrs.py`:

```python
"""Static per-bofedal attributes: SRTM elevation + USGS salar spatial join."""
from __future__ import annotations

from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd
import py7zr

from acquisition.aoi import PUNA_BBOX
from acquisition.gee import export_table_to_drive, initialize


_SRTM_ASSET = "USGS/SRTMGL1_003"


def _puna_region() -> "ee.Geometry":
    return ee.Geometry.Rectangle(
        [PUNA_BBOX.west, PUNA_BBOX.south, PUNA_BBOX.east, PUNA_BBOX.north]
    )


def _bofedales_to_fc(bofedales_gdf) -> "ee.FeatureCollection":
    features = []
    for _, row in bofedales_gdf.iterrows():
        features.append(
            ee.Feature(
                ee.Geometry(row.geometry.__geo_interface__),
                {"bofedal_id": str(row["bofedal_id"])},
            )
        )
    return ee.FeatureCollection(features)


def _reduce_to_table(
    image: "ee.Image", fc: "ee.FeatureCollection"
) -> "ee.FeatureCollection":
    return image.reduceRegions(
        collection=fc, reducer=ee.Reducer.mean(), scale=30
    )


def extract_elevation(*, bofedales, local_dest: Path) -> Path:
    """Submit a GEE export of mean SRTM elevation per bofedal."""
    out_csv = local_dest / "elevation.csv"
    if out_csv.exists():
        return out_csv

    initialize()
    image = ee.Image(_SRTM_ASSET)
    fc = _bofedales_to_fc(bofedales)
    table = _reduce_to_table(image, fc)
    export_table_to_drive(
        table=table,
        description="elevation",
        drive_folder="Lithium_v2_gee_exports_panel_elevation",
        file_prefix="elevation",
        local_dest=local_dest,
    )
    return out_csv


def unpack_usgs_archive(*, archive: Path, target_dir: Path) -> None:
    """Unpack the USGS gdb 7z to `target_dir`. Idempotent."""
    if target_dir.exists() and any(target_dir.iterdir()):
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    py7zr.unpack_7zarchive(str(archive), str(target_dir))


def extract_containing_salar_from_layer(
    *, bofedales: gpd.GeoDataFrame, salars: gpd.GeoDataFrame
) -> pd.DataFrame:
    """For each bofedal, return the NAME of the salar with the largest
    intersection area, or None if outside any salar."""
    if salars.crs != bofedales.crs:
        salars = salars.to_crs(bofedales.crs)

    rows = []
    for _, bof in bofedales.iterrows():
        bid = str(bof["bofedal_id"])
        best_name = None
        best_area = 0.0
        for _, sal in salars.iterrows():
            if not bof.geometry.intersects(sal.geometry):
                continue
            inter_area = bof.geometry.intersection(sal.geometry).area
            if inter_area > best_area:
                best_area = inter_area
                best_name = sal["NAME"]
        rows.append({"bofedal_id": bid, "containing_salar": best_name})
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/panel/test_static_attrs.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/panel/static_attrs.py tests/panel/test_static_attrs.py
git commit -m "Add panel.static_attrs for SRTM elevation and USGS salar join"
```

---

## Task 9: `src/panel/compose.py` — merge to parquet

**Files:**
- Create: `src/panel/compose.py`
- Create: `tests/panel/test_compose.py`

- [ ] **Step 1: Write the failing test**

Create `tests/panel/test_compose.py`:

```python
"""Tests for panel.compose — merge intermediates -> parquet."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_compose_panel_schema_and_row_count(tiny_bofedales, tmp_path):
    """Synthetic intermediates -> parquet has the expected schema and row count."""
    from panel.compose import compose_panel

    bof_path = tmp_path / "bofedales.geojson"
    tiny_bofedales.to_file(bof_path, driver="GeoJSON")

    intermediates = tmp_path / "panel"
    (intermediates / "ndvi_gs").mkdir(parents=True)
    (intermediates / "ndvi_annual").mkdir()
    (intermediates / "s1_vv").mkdir()
    (intermediates / "s1_vh").mkdir()

    ids = list(tiny_bofedales["bofedal_id"])
    for y in (2019, 2020):
        pd.DataFrame({
            "bofedal_id": ids,
            "median": [0.5, 0.6, 0.7],
            "count": [10, 12, 8],
        }).to_csv(intermediates / "ndvi_gs" / f"{y}.csv", index=False)
        pd.DataFrame({
            "bofedal_id": ids,
            "median": [0.4, 0.5, 0.6],
            "count": [20, 22, 18],
        }).to_csv(intermediates / "ndvi_annual" / f"{y}.csv", index=False)
    pd.DataFrame({
        "bofedal_id": ids, "median": [-12.0, -13.5, -14.0], "count": [50, 50, 50],
    }).to_csv(intermediates / "s1_vv" / "2020.csv", index=False)
    pd.DataFrame({
        "bofedal_id": ids, "median": [-18.0, -19.5, -20.0], "count": [50, 50, 50],
    }).to_csv(intermediates / "s1_vh" / "2020.csv", index=False)

    spei12 = pd.DataFrame({"bofedal_id": ids * 2, "year": [2019, 2019, 2019, 2020, 2020, 2020],
                            "spei_12_gs_mean": [0.1] * 6})
    spei24 = pd.DataFrame({"bofedal_id": ids * 2, "year": [2019, 2019, 2019, 2020, 2020, 2020],
                            "spei_24_gs_mean": [0.2] * 6})
    elevation = pd.DataFrame({"bofedal_id": ids, "mean": [3800.0, 3900.0, 4000.0]})
    salar = pd.DataFrame({"bofedal_id": ids,
                           "containing_salar": ["Salar A", "Salar B", None]})

    out = tmp_path / "bofedal_panel.parquet"
    compose_panel(
        bofedales_path=bof_path,
        years=range(2019, 2021),
        ndvi_gs_dir=intermediates / "ndvi_gs",
        ndvi_annual_dir=intermediates / "ndvi_annual",
        s1_vv_dir=intermediates / "s1_vv",
        s1_vh_dir=intermediates / "s1_vh",
        spei12_df=spei12,
        spei24_df=spei24,
        elevation_df=elevation,
        containing_salar_df=salar,
        out_path=out,
    )

    df = pd.read_parquet(out)
    assert set(df.columns) == {
        "bofedal_id", "year",
        "ndvi_gs_median", "ndvi_gs_n_obs",
        "ndvi_annual_median", "ndvi_annual_n_obs",
        "s1_vv_db_median", "s1_vh_db_median", "s1_n_obs",
        "spei_12_gs_mean", "spei_24_gs_mean",
        "elevation_m", "containing_salar",
        "mega_drought_dummy",
    }
    assert len(df) == 3 * 2  # 3 bofedales * 2 years
    # S1 NaN in 2019 (pre-2014 logic doesn't apply here; we just have no CSV).
    row_2019 = df[df["year"] == 2019]
    assert row_2019["s1_vv_db_median"].isna().all()
    # mega-drought dummy: 2019 is post-mega-drought.
    assert (row_2019["mega_drought_dummy"] == 0).all()


def test_compose_panel_mega_drought_dummy(tiny_bofedales, tmp_path):
    """Mega-drought dummy is 1 for 2010..2018 inclusive."""
    from panel.compose import compose_panel

    bof_path = tmp_path / "bofedales.geojson"
    tiny_bofedales.to_file(bof_path, driver="GeoJSON")

    intermediates = tmp_path / "panel"
    for sub in ("ndvi_gs", "ndvi_annual", "s1_vv", "s1_vh"):
        (intermediates / sub).mkdir(parents=True)

    ids = list(tiny_bofedales["bofedal_id"])
    years = [2009, 2010, 2018, 2019]
    for y in years:
        pd.DataFrame({"bofedal_id": ids, "median": [0.5] * 3, "count": [10] * 3}).to_csv(
            intermediates / "ndvi_gs" / f"{y}.csv", index=False)
        pd.DataFrame({"bofedal_id": ids, "median": [0.4] * 3, "count": [20] * 3}).to_csv(
            intermediates / "ndvi_annual" / f"{y}.csv", index=False)

    spei12 = pd.DataFrame({"bofedal_id": ids * 4,
                            "year": sum([[y] * 3 for y in years], []),
                            "spei_12_gs_mean": [0.0] * 12})
    spei24 = pd.DataFrame({"bofedal_id": ids * 4,
                            "year": sum([[y] * 3 for y in years], []),
                            "spei_24_gs_mean": [0.0] * 12})
    elevation = pd.DataFrame({"bofedal_id": ids, "mean": [3800.0] * 3})
    salar = pd.DataFrame({"bofedal_id": ids,
                           "containing_salar": [None] * 3})

    out = tmp_path / "bofedal_panel.parquet"
    compose_panel(
        bofedales_path=bof_path,
        years=years,
        ndvi_gs_dir=intermediates / "ndvi_gs",
        ndvi_annual_dir=intermediates / "ndvi_annual",
        s1_vv_dir=intermediates / "s1_vv",
        s1_vh_dir=intermediates / "s1_vh",
        spei12_df=spei12,
        spei24_df=spei24,
        elevation_df=elevation,
        containing_salar_df=salar,
        out_path=out,
    )
    df = pd.read_parquet(out).sort_values(["bofedal_id", "year"]).reset_index(drop=True)
    dummies = df.set_index(["bofedal_id", "year"])["mega_drought_dummy"]
    for bid in ids:
        assert dummies[(bid, 2009)] == 0
        assert dummies[(bid, 2010)] == 1
        assert dummies[(bid, 2018)] == 1
        assert dummies[(bid, 2019)] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/panel/test_compose.py -v
```

Expected: ImportError on `panel.compose`.

- [ ] **Step 3: Implement `src/panel/compose.py`**

Create `src/panel/compose.py`:

```python
"""Merge per-outcome CSVs + SPEI + static attrs into the final parquet."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd

MEGA_DROUGHT_YEARS = range(2010, 2019)  # inclusive 2010..2018


def _read_year_csvs(
    directory: Path, value_col_name: str, count_col_name: str
) -> pd.DataFrame:
    """Read every <year>.csv in directory into long form with (bofedal_id, year, ...).

    GEE table exports use 'median' for the reducer column and 'count' for the count;
    we rename to the panel's column names.
    """
    if not directory.exists():
        return pd.DataFrame(columns=["bofedal_id", "year", value_col_name, count_col_name])
    parts = []
    for csv in sorted(directory.glob("*.csv")):
        year = int(csv.stem)
        df = pd.read_csv(csv)
        df = df.rename(columns={"median": value_col_name, "count": count_col_name})
        df["year"] = year
        parts.append(df[["bofedal_id", "year", value_col_name, count_col_name]])
    if not parts:
        return pd.DataFrame(columns=["bofedal_id", "year", value_col_name, count_col_name])
    return pd.concat(parts, ignore_index=True)


def compose_panel(
    *,
    bofedales_path: Path,
    years: Iterable[int],
    ndvi_gs_dir: Path,
    ndvi_annual_dir: Path,
    s1_vv_dir: Path,
    s1_vh_dir: Path,
    spei12_df: pd.DataFrame,
    spei24_df: pd.DataFrame,
    elevation_df: pd.DataFrame,
    containing_salar_df: pd.DataFrame,
    out_path: Path,
) -> Path:
    """Merge intermediate dataframes into the final parquet."""
    bofedales = gpd.read_file(bofedales_path)
    years_list = sorted({int(y) for y in years})

    # Cartesian product bofedal x year as the skeleton.
    skeleton = pd.MultiIndex.from_product(
        [bofedales["bofedal_id"].astype(str).tolist(), years_list],
        names=["bofedal_id", "year"],
    ).to_frame(index=False)

    ndvi_gs = _read_year_csvs(ndvi_gs_dir, "ndvi_gs_median", "ndvi_gs_n_obs")
    ndvi_annual = _read_year_csvs(
        ndvi_annual_dir, "ndvi_annual_median", "ndvi_annual_n_obs"
    )
    s1_vv = _read_year_csvs(s1_vv_dir, "s1_vv_db_median", "s1_n_obs")
    s1_vh = _read_year_csvs(s1_vh_dir, "s1_vh_db_median", "s1_n_obs_vh")

    df = (
        skeleton
        .merge(ndvi_gs, on=["bofedal_id", "year"], how="left")
        .merge(ndvi_annual, on=["bofedal_id", "year"], how="left")
        .merge(s1_vv, on=["bofedal_id", "year"], how="left")
        .merge(s1_vh.drop(columns=["s1_n_obs_vh"]), on=["bofedal_id", "year"], how="left")
        .merge(spei12_df, on=["bofedal_id", "year"], how="left")
        .merge(spei24_df, on=["bofedal_id", "year"], how="left")
        .merge(
            elevation_df.rename(columns={"mean": "elevation_m"}),
            on=["bofedal_id"], how="left",
        )
        .merge(containing_salar_df, on=["bofedal_id"], how="left")
    )

    df["mega_drought_dummy"] = df["year"].isin(MEGA_DROUGHT_YEARS).astype("int8")

    # Cast to compact dtypes per spec §8.
    schema = {
        "bofedal_id": "string",
        "year": "int16",
        "ndvi_gs_median": "float32",
        "ndvi_gs_n_obs": "Int16",
        "ndvi_annual_median": "float32",
        "ndvi_annual_n_obs": "Int16",
        "s1_vv_db_median": "float32",
        "s1_vh_db_median": "float32",
        "s1_n_obs": "Int16",
        "spei_12_gs_mean": "float32",
        "spei_24_gs_mean": "float32",
        "elevation_m": "float32",
        "containing_salar": "string",
        "mega_drought_dummy": "int8",
    }
    df = df.astype({k: v for k, v in schema.items() if k in df.columns})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, engine="pyarrow", compression="snappy", index=False)
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/panel/test_compose.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/panel/compose.py tests/panel/test_compose.py
git commit -m "Add panel.compose for merging intermediates into the parquet"
```

---

## Task 10: `src/panel/run.py` — CLI driver

**Files:**
- Create: `src/panel/run.py`
- Create: `tests/panel/test_run.py`

- [ ] **Step 1: Write the failing test**

Create `tests/panel/test_run.py`:

```python
"""Tests for panel.run — CLI driver."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_extract_calls_ndvi_and_s1_per_year(mocker, tmp_path, tiny_bofedales_path):
    from panel.run import run_extract

    ndvi = mocker.patch("panel.ndvi.extract_year")
    s1 = mocker.patch("panel.s1.extract_year")

    run_extract(
        bofedales_path=tiny_bofedales_path,
        outcomes={"ndvi", "s1"},
        years=range(2014, 2017),
        external_root=tmp_path,
    )

    # NDVI gets called for both windows for all 3 years -> 6 calls.
    assert ndvi.call_count == 6
    # S1 gets called for both polarizations for all 3 years -> 6 calls.
    assert s1.call_count == 6


def test_extract_skips_pre_2014_for_s1(mocker, tmp_path, tiny_bofedales_path):
    from panel.run import run_extract

    ndvi = mocker.patch("panel.ndvi.extract_year")
    s1 = mocker.patch("panel.s1.extract_year")

    run_extract(
        bofedales_path=tiny_bofedales_path,
        outcomes={"ndvi", "s1"},
        years=range(2012, 2015),
        external_root=tmp_path,
    )

    # NDVI: 2 windows * 3 years = 6
    assert ndvi.call_count == 6
    # S1: only 2014 -> 2 calls (VV, VH)
    assert s1.call_count == 2


def test_compose_calls_static_extracts_and_writes_parquet(mocker, tmp_path, tiny_bofedales_path):
    from panel.run import run_compose

    spei_df_12 = pd.DataFrame(columns=["bofedal_id", "year", "spei_12_gs_mean"])
    spei_df_24 = pd.DataFrame(columns=["bofedal_id", "year", "spei_24_gs_mean"])
    elevation_df = pd.DataFrame(columns=["bofedal_id", "mean"])
    salar_df = pd.DataFrame(columns=["bofedal_id", "containing_salar"])

    spei_extract = mocker.patch(
        "panel.spei.extract",
        side_effect=[spei_df_12, spei_df_24],
    )
    mocker.patch("panel.static_attrs.extract_elevation")
    mocker.patch("panel.static_attrs.unpack_usgs_archive")
    mocker.patch(
        "panel.static_attrs.extract_containing_salar_from_layer",
        return_value=salar_df,
    )
    # Stub the salar layer read so we don't need a real gdb.
    mocker.patch(
        "panel.run._load_usgs_salars",
        return_value=mocker.MagicMock(),
    )
    # Stub the elevation CSV read.
    mocker.patch(
        "panel.run._load_elevation_csv",
        return_value=elevation_df,
    )

    compose = mocker.patch(
        "panel.compose.compose_panel",
        return_value=tmp_path / "bofedal_panel.parquet",
    )

    run_compose(
        bofedales_path=tiny_bofedales_path,
        years=range(2014, 2016),
        external_root=tmp_path,
        repo_root=tmp_path / "_repo",
    )

    assert spei_extract.call_count == 2
    compose.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/panel/test_run.py -v
```

Expected: ImportError on `panel.run`.

- [ ] **Step 3: Implement `src/panel/run.py`**

Create `src/panel/run.py`:

```python
"""CLI driver for Stage 3 panel build."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd

from panel import compose as compose_module
from panel import ndvi as ndvi_module
from panel import s1 as s1_module
from panel import spei as spei_module
from panel import static_attrs as static_module


_S1_AVAILABLE_FROM = 2014


def _load_usgs_salars(*, external_root: Path) -> gpd.GeoDataFrame:
    """Unpack the USGS gdb if needed, then load the salars layer."""
    archive = external_root / "usgs" / "raw" / "usgs.gdb.7z"
    target = external_root / "usgs" / "extracted"
    static_module.unpack_usgs_archive(archive=archive, target_dir=target)
    # Find the .gdb directory and the salars layer inside.
    gdb_candidates = list(target.rglob("*.gdb"))
    if not gdb_candidates:
        raise FileNotFoundError(
            f"No .gdb directory found under {target}. Check the archive structure."
        )
    gdb = gdb_candidates[0]
    import fiona
    layers = fiona.listlayers(str(gdb))
    salar_layer = next(
        (l for l in layers if "salar" in l.lower()),
        None,
    )
    if salar_layer is None:
        raise RuntimeError(
            f"No salar layer in {gdb}. Available: {layers}"
        )
    return gpd.read_file(str(gdb), layer=salar_layer)


def _load_elevation_csv(*, external_root: Path) -> pd.DataFrame:
    """Read the SRTM mean CSV produced by panel.static_attrs.extract_elevation."""
    csv = external_root / "panel" / "elevation" / "elevation.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"Elevation CSV not found at {csv}. Run `--extract elevation` first."
        )
    return pd.read_csv(csv)


def run_extract(
    *,
    bofedales_path: Path,
    outcomes: set[str],
    years: Iterable[int],
    external_root: Path,
) -> None:
    """Submit GEE exports for the listed outcomes across the year range."""
    bofedales = gpd.read_file(bofedales_path)
    panel_root = external_root / "panel"
    years_list = sorted({int(y) for y in years})

    if "ndvi" in outcomes:
        for y in years_list:
            for window, suffix in (("growing_season", "gs"), ("annual", "annual")):
                ndvi_module.extract_year(
                    year=y,
                    bofedales=bofedales,
                    window=window,
                    local_dest=panel_root / f"ndvi_{suffix}",
                )

    if "s1" in outcomes:
        for y in years_list:
            if y < _S1_AVAILABLE_FROM:
                continue
            for pol in ("VV", "VH"):
                s1_module.extract_year(
                    year=y,
                    bofedales=bofedales,
                    polarization=pol,
                    local_dest=panel_root / f"s1_{pol.lower()}",
                )

    if "elevation" in outcomes:
        static_module.extract_elevation(
            bofedales=bofedales,
            local_dest=panel_root / "elevation",
        )


def run_compose(
    *,
    bofedales_path: Path,
    years: Iterable[int],
    external_root: Path,
    repo_root: Path,
) -> None:
    """Run local extracts + merge intermediates into the parquet."""
    bofedales = gpd.read_file(bofedales_path)
    panel_root = external_root / "panel"
    years_list = sorted({int(y) for y in years})

    spei12_df = spei_module.extract(
        nc_path=external_root / "spei12" / "raw" / "spei12.nc",
        bofedales=bofedales,
        years=years_list,
        column="spei_12_gs_mean",
    )
    spei24_df = spei_module.extract(
        nc_path=external_root / "spei24" / "raw" / "spei24.nc",
        bofedales=bofedales,
        years=years_list,
        column="spei_24_gs_mean",
    )

    salars = _load_usgs_salars(external_root=external_root)
    salar_df = static_module.extract_containing_salar_from_layer(
        bofedales=bofedales, salars=salars,
    )

    elevation_df = _load_elevation_csv(external_root=external_root)

    out_path = repo_root / "Data" / "bofedal_panel.parquet"
    compose_module.compose_panel(
        bofedales_path=bofedales_path,
        years=years_list,
        ndvi_gs_dir=panel_root / "ndvi_gs",
        ndvi_annual_dir=panel_root / "ndvi_annual",
        s1_vv_dir=panel_root / "s1_vv",
        s1_vh_dir=panel_root / "s1_vh",
        spei12_df=spei12_df,
        spei24_df=spei24_df,
        elevation_df=elevation_df,
        containing_salar_df=salar_df,
        out_path=out_path,
    )
    print(f"wrote {out_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="panel.run")
    parser.add_argument(
        "--bofedales",
        type=Path,
        default=Path("Data/bofedales_v2.geojson"),
    )
    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("Data/external"),
    )
    parser.add_argument(
        "--extract",
        help="Comma-separated list of outcomes to extract (ndvi, s1, elevation). "
             "If omitted, runs ndvi,s1,elevation by default.",
    )
    parser.add_argument(
        "--compose",
        action="store_true",
        help="Merge intermediates into Data/bofedal_panel.parquet.",
    )
    parser.add_argument(
        "--years",
        default="1998:2024",
        help="Year range like 1998:2024 (end inclusive).",
    )
    args = parser.parse_args(argv)

    start_str, end_str = args.years.split(":")
    years = range(int(start_str), int(end_str) + 1)

    if args.extract is None and not args.compose:
        outcomes = {"ndvi", "s1", "elevation"}
        run_extract(
            bofedales_path=args.bofedales,
            outcomes=outcomes,
            years=years,
            external_root=args.external_root,
        )
        run_compose(
            bofedales_path=args.bofedales,
            years=years,
            external_root=args.external_root,
            repo_root=Path.cwd(),
        )
        return 0

    if args.extract:
        outcomes = {o.strip() for o in args.extract.split(",")}
        run_extract(
            bofedales_path=args.bofedales,
            outcomes=outcomes,
            years=years,
            external_root=args.external_root,
        )

    if args.compose:
        run_compose(
            bofedales_path=args.bofedales,
            years=years,
            external_root=args.external_root,
            repo_root=Path.cwd(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/panel/test_run.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run:

```bash
uv run pytest tests/ -q
```

Expected: 79 passed (55 baseline + 2 GEE + 6 NDVI + 4 S1 + 3 SPEI + 4 static_attrs + 2 compose + 3 run = 79).

- [ ] **Step 6: Commit**

```bash
git add src/panel/run.py tests/panel/test_run.py
git commit -m "Add panel.run CLI driver for Stage 3 panel build"
```

---

## Task 11: Schema doc + README update

**Files:**
- Create: `Data/bofedal_panel_schema.md`
- Modify: `Data/external/README.md`

- [ ] **Step 1: Write the schema doc**

Create `Data/bofedal_panel_schema.md`:

```markdown
# `bofedal_panel.parquet` schema

One row per `(bofedal_id, year)`. Years 1998–2024 inclusive; 3,821 bofedales × 27 years ≈ 103,167 rows.

| Column | Dtype | Description |
|---|---|---|
| `bofedal_id` | string (UUID5) | Stable identifier from `Data/bofedales_v2.geojson` (Stage 0.5). |
| `year` | int16 | Calendar year 1998–2024. |
| `ndvi_gs_median` | float32 | Growing-season (Dec `y-1` – Feb `y`) per-pixel NDVI median, then polygon-mean. Landsat C2 SR. |
| `ndvi_gs_n_obs` | Int16 | Count of Landsat scenes contributing to the growing-season composite. |
| `ndvi_annual_median` | float32 | Calendar-year per-pixel NDVI median, then polygon-mean. Landsat C2 SR. |
| `ndvi_annual_n_obs` | Int16 | Count of Landsat scenes contributing to the calendar-year composite. |
| `s1_vv_db_median` | float32 | Sentinel-1 IW descending VV backscatter median (dB). NaN for years <2014. |
| `s1_vh_db_median` | float32 | Sentinel-1 IW descending VH backscatter median (dB). NaN for years <2014. |
| `s1_n_obs` | Int16 | Count of Sentinel-1 scenes contributing. 0 for years <2014. |
| `spei_12_gs_mean` | float32 | SPEI-12 growing-season mean from SPEIbase v2.11. |
| `spei_24_gs_mean` | float32 | SPEI-24 growing-season mean from SPEIbase v2.11. |
| `elevation_m` | float32 | SRTM 30 m mean elevation per bofedal. Constant across years. |
| `containing_salar` | string | USGS salar `NAME` attribute by largest-overlap rule. NaN if outside any salar. |
| `mega_drought_dummy` | int8 | 1 for 2010 ≤ `year` ≤ 2018 (Garreaud et al. 2020 mega-drought), else 0. |

## Provenance

- **Bofedal polygons:** `Data/bofedales_v2.geojson` (Stage 0.5; MapBiomas Argentina Coll. 1 class 11 stable ≥13 of 25 years).
- **NDVI:** Landsat 5/7/8/9 Collection 2 Surface Reflectance via GEE (`reduceRegions`, scale 30 m).
- **Sentinel-1:** `COPERNICUS/S1_GRD`, IW descending, polarizations VV+VH, median composite per year.
- **SPEI:** `Data/external/spei{12,24}/raw/*.nc` (SPEIbase v2.11 monthly, 0.5°). Nearest-cell sampling at bofedal centroid.
- **Elevation:** `USGS/SRTMGL1_003` via GEE.
- **Containing salar:** USGS Lithium Triangle geodatabase (`Data/external/usgs/raw/usgs.gdb.7z`), unpacked and spatial-joined.

## Methodology deviations

- **Landsat C2 SR end-to-end** instead of the spec §3.2 HLS choice. Rationale in [Stage 3 design spec §6](../docs/superpowers/specs/2026-06-16-stage-3-bofedal-panel-design.md).
- **No floristic class / hydroecosystem complex** — those required Izquierdo's data that didn't arrive (see deprecated `izquierdo` manifest entry).

## Not in this panel

- Treatment columns (`brine_dist_m`, `fresh_dist_m`, `pond_area_m2`, `years_since_mine`) — Stage 2 deliverable; join later on `bofedal_id`.
- HydroBASINS L10 micro-watershed — explicitly deferred.

## Rebuilding

```bash
uv run python -m panel.run                # full sweep + compose
uv run python -m panel.run --compose      # only re-merge from existing CSVs
uv run python -m panel.run --extract ndvi --years 2020:2020  # single dataset slice
```
```

- [ ] **Step 2: Update `Data/external/README.md`**

Append to `Data/external/README.md`:

```markdown

## Stage 3 panel build (`uv run python -m panel.run`)

Builds `Data/bofedal_panel.parquet` (~5 MB, committed) — one row per (bofedal_id, year) with NDVI + Sentinel-1 + SPEI + static attrs. Schema documented at [`Data/bofedal_panel_schema.md`](../bofedal_panel_schema.md).

### Setup

GEE auth must be configured (same as Stage 0.5):

```bash
uv run python -c "import ee; ee.Authenticate()"
```

`rclone` must be configured with the `gdrive` remote.

### Running

End-to-end (~30–60 min for the full 1998–2024 sweep, dominated by GEE export wait times):

```bash
uv run python -m panel.run
```

Outcome-by-outcome (useful for incremental work):

```bash
uv run python -m panel.run --extract ndvi              # both windows, all years
uv run python -m panel.run --extract s1                # VV + VH, 2014+
uv run python -m panel.run --extract elevation         # SRTM mean per bofedal
uv run python -m panel.run --compose                   # merge to parquet (local, seconds)
```

Restrict year range:

```bash
uv run python -m panel.run --extract ndvi --years 2020:2020
```

### Outputs

- `Data/external/panel/<outcome>/<year>.csv` — gitignored GEE intermediates
- `Data/external/usgs/extracted/` — gitignored USGS gdb unpack
- `Data/bofedal_panel.parquet` — committed deliverable

### Troubleshooting

- **GEE export FAILED**: open https://code.earthengine.google.com/ → Tasks panel; inspect the task by description (`ndvi_gs_2020`, `s1_vv_2018`, etc.). Re-run the same `--extract` after fixing.
- **`rclone failed: invalid_grant`**: `rclone config reconnect gdrive:` then re-run.
- **Missing USGS extracted directory**: `python -c "from panel.static_attrs import unpack_usgs_archive; from pathlib import Path; unpack_usgs_archive(archive=Path('Data/external/usgs/raw/usgs.gdb.7z'), target_dir=Path('Data/external/usgs/extracted'))"`.
```

- [ ] **Step 3: Commit**

```bash
git add Data/bofedal_panel_schema.md Data/external/README.md
git commit -m "Document bofedal_panel schema and Stage 3 build"
```

---

## Task 12: Live smoke test — single year (manual)

This is the first hands-on validation against real GEE. Single year, single outcome — fast feedback loop before committing to the full sweep.

**Files:**
- None (verification only).

- [ ] **Step 1: Confirm GEE auth**

Run:

```bash
uv run python -c "import ee; ee.Initialize(project='ee-nunezrimedio-tesina', opt_url='https://earthengine-highvolume.googleapis.com'); print('ok')"
```

Expected: `ok`. If you see an auth error, run `ee.Authenticate()` first.

- [ ] **Step 2: Run NDVI for a single year**

Run:

```bash
uv run python -m panel.run --extract ndvi --years 2020:2020
```

Expected:
- Two GEE tasks submitted (`ndvi_gs_2020`, `ndvi_annual_2020`).
- Polling output as they finish.
- Local CSVs at `Data/external/panel/ndvi_gs/2020.csv` and `Data/external/panel/ndvi_annual/2020.csv`.

If the export takes longer than 15 minutes, the timeout will fire. In that case, re-submit with `--years 2020:2020` — the existing CSVs (if any partial got mirrored) will short-circuit, otherwise it submits a fresh task.

- [ ] **Step 3: Spot-check the NDVI values**

Run:

```bash
uv run python -c "
import pandas as pd
gs = pd.read_csv('Data/external/panel/ndvi_gs/2020.csv')
annual = pd.read_csv('Data/external/panel/ndvi_annual/2020.csv')
print('gs:', gs.shape, 'cols:', list(gs.columns))
print('  median ndvi (gs):', gs['median'].median())
print('  fraction obs > 0 :', (gs['count'] > 0).mean())
print('annual:', annual.shape, 'cols:', list(annual.columns))
print('  median ndvi (annual):', annual['median'].median())
"
```

Expected: 3,821 rows in each CSV. Median NDVI in the growing season should be in roughly 0.3–0.7 (real bofedales are vegetated but at high elevation). Annual median typically lower. The `count` column should be >0 for nearly all bofedales.

If the median NDVI looks wrong (negative, > 1, or systematically NaN), stop and diagnose before moving on.

- [ ] **Step 4: Run Sentinel-1 for the same year**

Run:

```bash
uv run python -m panel.run --extract s1 --years 2020:2020
```

Expected: two more GEE tasks (`s1_vv_2020`, `s1_vh_2020`); two more CSVs.

- [ ] **Step 5: Spot-check S1 values**

Run:

```bash
uv run python -c "
import pandas as pd
for pol in ('vv', 'vh'):
    df = pd.read_csv(f'Data/external/panel/s1_{pol}/2020.csv')
    print(f'{pol}: median dB =', df['median'].median(), '  n_bofedales =', len(df))
"
```

Expected: VV around -10 to -15 dB for typical wetlands; VH around -15 to -22 dB. Anything wildly outside (e.g., positive dB) is suspicious.

- [ ] **Step 6: Run elevation extraction**

Run:

```bash
uv run python -m panel.run --extract elevation
```

Expected: one quick GEE task; CSV at `Data/external/panel/elevation/elevation.csv` with `mean` values around 3,500–4,500 m (Puna altitude band).

- [ ] **Step 7: Verify the CSVs locally before moving on to the full sweep**

Run:

```bash
ls -la Data/external/panel/
```

Expected: `ndvi_gs/`, `ndvi_annual/`, `s1_vv/`, `s1_vh/`, `elevation/` directories each with the 2020 CSV.

If everything checks out, proceed to Task 13.

---

## Task 13: Full sweep + commit parquet (manual)

**Files:**
- Create: `Data/bofedal_panel.parquet` (committed)

- [ ] **Step 1: Run the full extract sweep**

Run:

```bash
uv run python -m panel.run --extract ndvi,s1,elevation --years 1998:2024
```

Expected: ~108 GEE tasks submitted in parallel; the driver polls them all to completion. Wall-clock time: 30–60 minutes depending on GEE load. Each successful task lands a CSV under `Data/external/panel/<outcome>/<year>.csv`.

If any year's task FAILS, the driver raises and stops. Diagnose via the GEE Tasks panel, fix (often a region/quota issue), and re-run the same command — already-completed years are skipped via the local-CSV idempotency check.

- [ ] **Step 2: Run the compose step**

Run:

```bash
uv run python -m panel.run --compose
```

Expected: completes in seconds. Output `wrote .../Data/bofedal_panel.parquet`.

- [ ] **Step 3: Verify the parquet**

Run:

```bash
uv run python -c "
import pandas as pd
df = pd.read_parquet('Data/bofedal_panel.parquet')
print('shape:', df.shape)
print('cols:', list(df.columns))
print('years:', df['year'].min(), '..', df['year'].max())
print('bofedales:', df['bofedal_id'].nunique())
print('rows w/ ndvi_gs:', df['ndvi_gs_median'].notna().sum())
print('rows w/ s1_vv:', df['s1_vv_db_median'].notna().sum())
print('mega-drought rows:', (df['mega_drought_dummy'] == 1).sum())
print('containing_salar value counts:')
print(df['containing_salar'].value_counts().head(10))
"
```

Expected:
- Shape: roughly `(103167, 14)`
- 3,821 unique bofedales
- Years 1998..2024
- NDVI populated for nearly all rows
- S1 populated only for 2014+ (≈ 11 × 3,821 = 42,031 rows)
- Mega-drought rows: 9 × 3,821 = 34,389
- `containing_salar` has counts for the known operating salars (Olaroz, Cauchari, Hombre Muerto, etc.)

- [ ] **Step 4: Commit the parquet + the schema doc**

Run:

```bash
git add Data/bofedal_panel.parquet
git commit -m "Ship bofedal_panel.parquet from live Stage 3 build"
git push
```

- [ ] **Step 5: Open / update the PR**

If working from the `claude/stage-0-mapbiomas-bofedal` branch (Stage 3 was layered on top), check PR #4. If a separate branch was used, open a new PR with `gh pr create --base main`.

The PR description should note:
- Stage 3 deliverable shipped: `Data/bofedal_panel.parquet`
- The NDVI sensor deviation from spec §3.2 (Landsat C2 SR, not HLS) — rationale in the Stage 3 design §6
- Outstanding follow-ups: treatment columns (Stage 2), HLS migration if rebuilding becomes feasible, methodology spec §3.2 prose rewrite

---

## Self-review checklist

After completing all tasks, verify against the spec:

- [ ] **§2 deliverable:** `Data/bofedal_panel.parquet` exists and is committed.
- [ ] **§3 inputs:** all six input sources used (bofedales_v2, Landsat C2 SR, S1 GRD, SRTM, SPEI nc, USGS gdb).
- [ ] **§4 architecture:** five `src/panel/` modules + `run.py` exist; `gee.py` has `export_table_to_drive`.
- [ ] **§5 outcome pipelines:** NDVI growing-season + annual; S1 VV + VH 2014+; idempotency via local-CSV check.
- [ ] **§6 sensor strategy:** Landsat C2 SR end-to-end; documented in schema doc and PR.
- [ ] **§7 local extracts:** SPEI uses centroid + nearest-cell; SRTM via reduceRegions; USGS gdb extracted via py7zr + salar largest-overlap join.
- [ ] **§8 compose:** parquet schema matches column dtypes from spec; `~103k rows` order of magnitude.
- [ ] **§9 driver:** `--extract` / `--compose` / no-args / `--years` all work.
- [ ] **§10 testing:** all per-module tests + driver test pass; no live GEE in pytest.
- [ ] **§11 storage:** `.gitignore` excludes the panel intermediates and USGS extracted directories.
- [ ] **§12 error handling:** GEE failure raises loudly; rclone failure inherited; missing-input messages are clear.
- [ ] **§13 smoke test:** completed (Tasks 12–13).
- [ ] **§14 docs:** `Data/bofedal_panel_schema.md` + `Data/external/README.md` updated.
