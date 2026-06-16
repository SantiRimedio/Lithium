# Stage 3 — Per-Bofedal Annual Panel (outcomes + climate + static attrs) — Design

*Date: 2026-06-16 · Status: approved, ready for implementation plan*
*Implements: Methodology v2 §§3.1, 3.2, 3.5 (outcome + climate + static-attr portion of the panel)*
*References: [Methodology v2](../../../text/Methodology_v2.md), [Stage 0 tier-1 design](2026-05-26-stage-0-tier1-acquisition-design.md), [Stage 0.5 bofedal mask design](2026-06-12-stage-0-mapbiomas-bofedal-mask-design.md)*

## 1. Context

The bofedal-polygon panel is the unit of analysis for Methodology v2 §3 (CS-DiD and spatial RDD on bofedal × year). Stage 0.5 produced the spatial unit (`Data/bofedales_v2.geojson`, 3,821 polygons from MapBiomas Argentina Coll. 1). This spec builds the **outcomes + climate + static-attr** columns of the panel and emits `Data/bofedal_panel.parquet`. Treatment columns (`brine_dist_m`, `fresh_dist_m`, `pond_area_m2`, `years_since_mine`) are Stage 2 work; this panel ships without them and can be joined later.

The methodology spec at §3.2 specifies HLS-harmonized Landsat+Sentinel-2 as the optical sensor. This spec departs from that and uses **Landsat 5/7/8/9 Collection 2 Surface Reflectance end-to-end** for 1998–2024 (rationale in §6). Sentinel-1 GRD VV/VH backscatter is the SAR robustness signal per spec §3.2; it covers 2014–present (the sensor doesn't exist before).

## 2. Goals & non-goals

**Goals**

- A committed `Data/bofedal_panel.parquet` with one row per (bofedal_id, year) for the 3,821 bofedales × 27 years (1998–2024) = ~103k rows.
- Reproducible from one command: `uv run python -m panel.run`. Idempotent on re-run.
- Per-outcome modules (NDVI, S1) testable independently with mocked GEE.
- Documented column schema committed alongside the parquet.

**Non-goals**

- Treatment columns (distances, pond area, years-since-mine). Stage 2.
- HLS + Sentinel-2 NDVI. Deferred — Landsat-only is the scope (§6).
- HydroBASINS micro-watershed. Deferred per scoping decision.
- Floristic class + hydroecosystem complex. Lost when Izquierdo's data didn't arrive.
- Hand-validation of bofedal polygons. Stage 3 human gate, separate from this code.
- The Stage 4 causal estimation itself.

## 3. Inputs

| Source | State | Used for |
|---|---|---|
| `Data/bofedales_v2.geojson` | committed (3,821 polys, Stage 0.5) | unit of analysis (rows = bofedal × year) |
| Landsat 5/7/8/9 C2 SR (`LANDSAT/L{T05,E07,C08,C09}/C02/T1_L2`) via GEE | live | NDVI growing-season + annual medians |
| Sentinel-1 GRD (`COPERNICUS/S1_GRD`, IW mode, descending) via GEE | live | VV/VH backscatter median (dB) |
| SRTM 30 m (`USGS/SRTMGL1_003`) via GEE | live | per-bofedal elevation |
| `Data/external/spei12/raw/spei12.nc`, `spei24.nc` | committed (Stage 0 tier-1) | climate covariates |
| `Data/external/usgs/raw/usgs.gdb.7z` | committed (Stage 0 tier-1, not yet extracted) | containing-salar spatial join |

## 4. Architecture

```
src/panel/
├── __init__.py
├── ndvi.py             # Landsat C2 SR NDVI extraction via GEE
├── s1.py               # Sentinel-1 GRD backscatter via GEE
├── spei.py             # local NetCDF → per-bofedal-year extract
├── static_attrs.py     # SRTM (GEE) + USGS salar join + mega-drought dummy
├── compose.py          # merge all pieces into the parquet
└── run.py              # CLI driver

src/acquisition/gee.py  # EXTEND: add export_table_to_drive helper
                        # (parallels existing export_to_drive for images)

Data/
├── bofedal_panel.parquet            # NEW: primary deliverable
├── bofedal_panel_schema.md          # NEW: column glossary
└── external/
    ├── panel/                        # gitignored — GEE intermediate CSVs
    │   ├── ndvi_gs/<year>.csv
    │   ├── ndvi_annual/<year>.csv
    │   ├── s1_vv/<year>.csv
    │   └── s1_vh/<year>.csv
    └── usgs/
        └── extracted/                # gitignored — py7zr unpack target
            └── Li_Triangle_ARG_MRP_NMIC.gdb/

tests/panel/
├── conftest.py                       # fixtures: tiny bofedales gdf, tiny SPEI nc, tiny salar layer
├── test_ndvi.py
├── test_s1.py
├── test_spei.py
├── test_static_attrs.py
├── test_compose.py
└── test_run.py
```

Five new modules in a fresh `src/panel/` subpackage. `src/acquisition/gee.py` is extended with one new helper (table-export). No existing modules' behavior changes.

## 5. Outcome pipelines (GEE)

For each calendar year `y` in `1998..2024`:

### 5.1 NDVI growing-season median (Dec `y-1` → Feb `y`, austral summer)

Server-side:
1. Collect Landsat C2 SR scenes intersecting the Puna bbox (reuses `PUNA_BBOX` from `acquisition.aoi`) in the date window.
2. For each scene: select the appropriate sensor's NIR + Red bands (L5/L7 use SR_B4/SR_B3; L8/L9 use SR_B5/SR_B4), apply Collection 2 scaling factors (`scale=0.0000275, offset=-0.2`), compute NDVI = (NIR-Red)/(NIR+Red).
3. Cloud mask via `QA_PIXEL` bit-decoded (clear-confidence bit 6 or absence of cloud bit 3 + cirrus bit 2).
4. Per-pixel median across all valid scene-pixels in the window.
5. `image.reduceRegions(collection=bofedales, reducer=ee.Reducer.median().combine(ee.Reducer.count(), '', true), scale=30)` → table with columns `bofedal_id, ndvi_gs_median, ndvi_gs_n_obs`.
6. `Export.table.toDrive(...)` → CSV at `gdrive:Lithium_v2_gee_exports_panel/ndvi_gs/<year>.csv`.

### 5.2 NDVI annual median (Jan `y` → Dec `y`)

Identical recipe with the full-year date window. Output column `ndvi_annual_median, ndvi_annual_n_obs` at `panel/ndvi_annual/<year>.csv`.

### 5.3 Sentinel-1 VV + VH (years 2014–2024 only)

Server-side per year:
1. Collect `COPERNICUS/S1_GRD` scenes in IW mode, descending orbit, polarizations VV + VH, intersecting Puna bbox in Jan `y` → Dec `y`.
2. Convert backscatter to dB: `10 * log10(scene)`.
3. Per-pixel median across scenes for VV (one image) and VH (separate image).
4. Two reduceRegions calls; two CSV exports per year (`panel/s1_vv/<year>.csv`, `panel/s1_vh/<year>.csv`).

### 5.4 Driver flow per outcome

Each module's `extract_year(year, bofedales, dest_drive_folder)` function:
- Idempotency guard: if the local CSV at `Data/external/panel/<outcome>/<year>.csv` exists, return immediately.
- Else build the server-side image, submit the export, return the task object.

A driver-level batch step polls all submitted tasks (parallel) and then runs `rclone copy gdrive:<folder> Data/external/panel/<outcome>/`.

## 6. Sensor strategy and the HLS deviation

Spec §3.2 listed HLS (NASA/HLS L30 + S30) as the optical product. HLS only starts in 2013, so it doesn't cover the 1998 baseline Fénix opened on. The alternatives are:

| Choice | Pros | Cons |
|---|---|---|
| **Landsat C2 SR end-to-end (chosen)** | One sensor family, no cross-sensor harmonization needed; matches the standard practice in published causal-DiD NDVI analyses; reliable QA bitmask | Misses Sentinel-2's 10 m resolution; SLC-off gaps in L7 2003–2013 |
| HLS post-2013 + Landsat C2 SR pre-2013 | Recent years at 30 m harmonized with S2 | Mixing two product families requires explicit harmonization handling; introduces a 2013 discontinuity exactly where our staggered cohorts open |
| Compute our own L5/L7/L8/L9 + S2 harmonization | Fully spec-compliant | Months of work |

The bofedal-polygon median at 30 m is robust to the Landsat-vs-HLS choice — the spectral indices are equivalent within ~0.01 NDVI units at this aggregation level. Document the deviation; the methodology paper text should be updated to reflect this when §3.2 is rewritten alongside §3.1.

## 7. Local extracts

### 7.1 SPEI per bofedal-year

`src/panel/spei.py`:
1. Load `Data/external/spei12/raw/spei12.nc` via `xarray.open_dataset(...)`.
2. Compute each bofedal's centroid in EPSG:4326.
3. Use `xarray.Dataset.sel(lon=centroid_lon, lat=centroid_lat, method='nearest')` to get the bofedal's grid-cell time series.
4. For each year `y`, slice the months Dec `y-1` → Feb `y`, compute the mean → `spei_12_gs_mean`.
5. Same with `spei24.nc` → `spei_24_gs_mean`.
6. Return long DataFrame indexed on (bofedal_id, year).

SPEI's 0.5°≈55 km cell size means many bofedales share the same grid cell. That's correct behavior — SPEI is a basin-scale climate signal, not a per-polygon detail.

### 7.2 Elevation per bofedal

`src/panel/static_attrs.py::extract_elevation()`:
- GEE `USGS/SRTMGL1_003`, `reduceRegions(reducer=ee.Reducer.mean(), scale=30)`.
- Single CSV export → `Data/external/panel/elevation.csv`. One row per bofedal, no year axis.

### 7.3 Containing salar (USGS gdb)

`src/panel/static_attrs.py::extract_containing_salar()`:
1. If `Data/external/usgs/extracted/` is empty, `py7zr.unpack_7zarchive(Data/external/usgs/raw/usgs.gdb.7z, Data/external/usgs/extracted/)`.
2. Identify the gdb directory inside.
3. List layers via `fiona.listlayers(gdb_path)` — locate the salars vector layer (likely named `salars`, `Salars`, or similar; the exact name is resolved at first run and pinned in code).
4. `gpd.read_file(gdb_path, layer=<name>)` to load the layer.
5. Spatial join: for each bofedal, find the salar whose intersection area with the bofedal is largest (NaN if no overlap).
6. Output one CSV: `Data/external/panel/containing_salar.csv` with columns `bofedal_id, containing_salar` (the salar's `NAME` attribute).

Fallback if `OpenFileGDB` driver isn't available: `ogr2ogr -f GeoJSON salars.geojson <gdb_path> <layer_name>` shell-out.

### 7.4 Mega-drought dummy

Trivial: `1 if 2010 <= year <= 2018 else 0`. Computed in `compose.py`, no CSV.

## 8. Compose → parquet

`src/panel/compose.py`:
1. Load `bofedales_v2.geojson` for the bofedal_id list.
2. Build the (bofedal_id, year) Cartesian product for years 1998–2024.
3. Left-join NDVI growing-season + NDVI annual + S1 VV + S1 VH (S1 only for 2014+) + SPEI extracts on (bofedal_id, year).
4. Left-join elevation + containing_salar on bofedal_id only (broadcast).
5. Compute mega-drought dummy.
6. Cast columns to compact dtypes (per schema below).
7. Write to `Data/bofedal_panel.parquet` via pyarrow.
8. Write `Data/bofedal_panel_schema.md` (column glossary).

Final schema:

| Column | Dtype | Notes |
|---|---|---|
| `bofedal_id` | string (UUID5) | join key from `bofedales_v2.geojson` |
| `year` | int16 | 1998..2024 |
| `ndvi_gs_median` | float32 | growing-season (Dec `y-1` – Feb `y`) per-pixel median, polygon-mean |
| `ndvi_gs_n_obs` | int16 | growing-season Landsat scene count |
| `ndvi_annual_median` | float32 | calendar-year per-pixel median, polygon-mean |
| `ndvi_annual_n_obs` | int16 | calendar-year Landsat scene count |
| `s1_vv_db_median` | float32 | NaN for years <2014 |
| `s1_vh_db_median` | float32 | NaN for years <2014 |
| `s1_n_obs` | int16 | 0 for years <2014 |
| `spei_12_gs_mean` | float32 | growing-season mean of SPEI-12 |
| `spei_24_gs_mean` | float32 | growing-season mean of SPEI-24 |
| `elevation_m` | float32 | constant per bofedal, broadcast across years |
| `containing_salar` | string | USGS salar `NAME`, NaN if outside any |
| `mega_drought_dummy` | int8 | 1 for 2010..2018 |

Approximate row count: 3,821 × 27 = 103,167. Expected size < 5 MB compressed.

## 9. Driver CLI

`src/panel/run.py`:

```bash
uv run python -m panel.run --extract ndvi,s1     # submit GEE tasks for the listed outcomes
uv run python -m panel.run --compose             # assemble parquet from local CSVs + SPEI + static
uv run python -m panel.run                       # both, end-to-end, idempotent
uv run python -m panel.run --years 2014:2024     # restrict to a year range
```

The `--extract` step submits ALL year×outcome combinations as parallel GEE tasks (NDVI gs + annual + S1 VV + S1 VH × years), polls until done with a single rclone-mirror step at the end. The `--compose` step is local-only and fast (seconds).

## 10. Testing

- `tests/panel/conftest.py`:
  - `tiny_bofedales` — a 3-polygon GeoDataFrame inside PUNA_BBOX
  - Reuse `tiny_netcdf` from `tests/acquisition/conftest.py` for SPEI tests
  - `tiny_salars` — a synthetic geojson with 2 salar polygons covering known territory
- `test_ndvi.py`: mock `ee.batch.Export.table.toDrive`, verify the right date range and reducer are passed; verify per-sensor band selection (L5/L7 use SR_B4/SR_B3 NIR/Red; L8/L9 use SR_B5/SR_B4).
- `test_s1.py`: mock GEE, verify dB conversion is applied and only descending IW scenes are used.
- `test_spei.py`: against the tiny NetCDF, verify the growing-season window math and nearest-neighbor cell selection.
- `test_static_attrs.py`: mocked GEE for SRTM; tiny synthetic salar layer for the spatial join (largest-overlap winner).
- `test_compose.py`: build synthetic CSVs + extracts → parquet → assert column dtypes, row count, and that mega_drought_dummy is correct.
- `test_run.py`: end-to-end with mocked GEE + already-prepared CSV inputs verifies the dispatch logic and the `--compose` short-circuit.

No live-network tests in CI. Live smoke test in §13.

## 11. Storage

- **Local** (gitignored): `Data/external/panel/<outcome>/<year>.csv` + `elevation.csv` + `containing_salar.csv` + `Data/external/usgs/extracted/`.
- **Drive**: `gdrive:Lithium_v2_gee_exports_panel/<outcome>/<year>.csv`. Single flat namespace (per the lesson from Stage 0.5 — GEE's `folder=` doesn't accept slashes).
- **Committed**: `Data/bofedal_panel.parquet` + `Data/bofedal_panel_schema.md`. Both small.

`.gitignore` additions:
```
Data/external/panel/
Data/external/usgs/extracted/
```

## 12. Error handling & idempotency

- **GEE export failure**: surface the task's `error_message`, log task ID for inspection in the Tasks panel, raise. No automatic retries (matches `acquisition.gee` pattern).
- **rclone OAuth expiry**: same as Stage 0.5 — the user runs `rclone config reconnect gdrive:` and re-invokes the driver; idempotency kicks in.
- **Missing intermediate CSV**: `compose.py` raises with a clear "run `--extract` first" message; doesn't fabricate NaN rows.
- **Year-without-observations**: row is kept with NDVI columns NaN and `ndvi_n_obs = 0`. Stage 4 estimation handles NaN.
- **Re-running with everything present**: `--extract` is a no-op (CSV exists); `--compose` rewrites parquet from existing inputs; deterministic outputs given identical inputs.

## 13. Live smoke test (manual, post-implementation)

1. Authenticate GEE if needed (one-time, already set up from Stage 0.5).
2. `uv run python -m panel.run --extract ndvi --years 2020:2020` — single year, single outcome. Watch GEE Tasks panel; expect 2 tasks (gs + annual), ~5 min.
3. Inspect the CSV: `head Data/external/panel/ndvi_gs/2020.csv`; spot-check a few bofedales have plausible NDVI (~0.4–0.8 for active bofedales in growing season).
4. `uv run python -m panel.run --extract s1 --years 2020:2020`. Same drill.
5. `uv run python -m panel.run --extract ndvi,s1` (full sweep). ~100 GEE tasks, ~30–60 min.
6. `uv run python -m panel.run --compose`. Local, seconds.
7. `uv run python -c "import pandas as pd; df = pd.read_parquet('Data/bofedal_panel.parquet'); print(df.head()); print(df.shape); print(df.dtypes)"`.
8. Commit `Data/bofedal_panel.parquet` + `Data/bofedal_panel_schema.md`. PR.

## 14. Documentation deliverables

- `Data/bofedal_panel_schema.md` — column glossary (committed).
- Extend `Data/external/README.md` with a "Stage 3 panel build" section (run instructions, what each `Data/external/panel/<outcome>/` directory holds, troubleshooting).
- Brief note on the Landsat-not-HLS choice (cross-reference this spec §6 from the spec PR's methodology rewrite when that happens).

## 15. Out of scope (explicit)

- All Stage 2 (mining footprint) work.
- HLS or Sentinel-2 NDVI.
- HydroBASINS micro-watershed.
- Floristic class / hydroecosystem complex.
- Hand-validation of bofedales (Stage 3 human gate).
- The Stage 4 causal estimation itself.
- Any updates to Methodology v2 §3.2 prose (that's a spec-PR follow-up).

## 16. Risks

1. **L7 SLC-off gaps (2003–2013)**: ~22% scan-line data loss. Mitigation: growing-season median pulls from L5 (still operating until 2013) and increasingly L8 (from 2013) in addition to L7; `ndvi_n_obs` column surfaces years with sparse coverage.
2. **GEE quota at ~100 export tasks**: GEE allows up to 3,000 concurrent active tasks but throttles submission. Mitigation: serialize submission with a small `time.sleep` between tasks; add `--batch-size` if needed.
3. **USGS FileGDB driver compatibility**: Esri's FileGDB driver isn't always present in `fiona`. Mitigation: try `OpenFileGDB` first, fall back to `ogr2ogr` shell-out, fall back to manual conversion documented in README.
4. **Bofedal-polygon edge effects on NDVI**: polygons whose perimeter exceeds their area (long thin riparian shapes) have edge pixels that may include non-bofedal vegetation. The Stage 0.5 `aggregate_300m` step mitigates by merging fragmented polygons, but residual effects exist. The `ndvi_n_obs` column flags polygons too small to have meaningful pixel counts.
5. **GEE export schema drift**: `Export.table.toDrive` writes CSV with a `.geo` column for geometry that we don't need but bloats files. Mitigation: strip the `.geo` column before reduce, or drop in pandas during compose.
6. **SPEI temporal coverage**: SPEIbase v2.11 runs 1901–2024; we're well within the window. No risk.
7. **2013 sensor transition**: L5 ended May 2013; L8 launched April 2013. A 1–2 month gap if cloud cover is bad. Mitigation: the growing-season window for 2013 specifically spans late 2012 → early 2013 — entirely L5+L7 territory — so the transition lands cleanly in the annual median for 2014+ where L8 is fully operational.
