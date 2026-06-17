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
