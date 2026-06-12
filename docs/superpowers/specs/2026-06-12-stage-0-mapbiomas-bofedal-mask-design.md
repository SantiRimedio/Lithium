# Stage 0.5 — MapBiomas + Zenodo Bofedal Mask — Design

*Date: 2026-06-12 · Status: approved, ready for implementation plan*
*Implements: Methodology v2 §3.1 (bofedal-mask construction)*
*Reference specs: [Methodology v2](../../../text/Methodology_v2.md), [Stage 0 tier-1 design](2026-05-26-stage-0-tier1-acquisition-design.md)*

## 1. Context

Methodology v2 §3.1 specifies the bofedal-polygon panel as the unit of analysis. The original design assigned that role to the Izquierdo, Foguet & Grau (2015) polygon set, cross-validated against the 2026 global wetland map (Zenodo 18339573). Stage 0 tier-1 acquired the Zenodo zip but the Izquierdo polygons turned out to be unobtainable — the corresponding author did not respond to a data request, and no public download exists. See `Data/external/manifest.yaml`'s deprecated `izquierdo` entry.

This spec replaces the Izquierdo role with a **hybrid mask**: MapBiomas Argentina Collection 2 "Puna y Altos Andes" wetland class as primary, polygonized via the Izquierdo-style sieve + clump + aggregate-polygons-300m recipe, cross-validated against the Zenodo 18339573 high-probability mask. Methodology v2 §3.1 needs a corresponding text rewrite (tracked separately on the spec PR).

The MapBiomas + Zenodo combination is actually methodologically stronger than the original design: MapBiomas gives a 27-year Argentine-tuned annual classification (vs the single static Izquierdo map), and the cross-validation step is preserved by using Zenodo as the independent reference.

## 2. Goals & non-goals

**Goals**

- A committed `Data/bofedales_v2.geojson` ready for Stage 1 — one polygon per stable bofedal in the Argentine Puna ("stable" = MapBiomas wetland class in ≥ 14 of the 27 years 1998–2024; see §6).
- A companion `Data/bofedales_v2_disputed.geojson` listing polygons whose MapBiomas/Zenodo overlap is between 10% and 50%, for human review.
- Fully reproducible from `Data/external/manifest.yaml` + the new acquisition module: anyone with GEE auth and the existing `rclone` setup can rebuild both files from one command.
- All polygonization parameters (stability threshold, sieve area, aggregate distance, reconciliation thresholds) live in one config object, not scattered.

**Non-goals**

- Hand-validation of disputed polygons against Planet/Worldview imagery — that's the Stage 3 validation gate from Methodology v2 §3.1. We emit the disputed list; humans review.
- Floristic stratification — the 5-class IMBIV scheme requires a separate CONICET dataset we don't have. Stratification stays a Stage 1 robustness item.
- Other tier-2 GEE datasets (HLS, CHIRPS, ERA5-Land, MapBiomas other regions). The `gee.py` module is built generically enough to host them later, but no other Dataset module is delivered here.
- Cleanup of the deprecated `IzquierdoDataset` module + tests. Deferred to a separate cosmetic pass.
- Updating Methodology v2 §3.1 text. Tracked on the spec PR.

## 3. Inputs

| Source | State | What we use |
|---|---|---|
| MapBiomas Argentina Coll. 2 "Puna y Altos Andes" | New (this spec) | GEE asset, annual wetland classification 1998–2024 |
| Zenodo 2026 high-probability wetland map | Already acquired (Stage 0 tier-1) | Extract `2_Maps_high_probabilities.zip`, find the Puna-overlapping TIFs, polygonize |
| Existing Endorheic basins layer | Already in repo | `Data/Endorheic_basins_Puna.geojson` — masking convenience for the GEE clip |
| `PUNA_BBOX` from `src/acquisition/aoi.py` | Already in repo | GEE region of interest |

The MapBiomas Coll. 2 GEE asset path is not yet pinned. It's resolved from MapBiomas's ATBD / GitHub during implementation and stored in the manifest's `mapbiomas` entry (likely under `projects/mapbiomas-public/assets/argentina/collection2/...` or similar — confirmed before first export run).

## 4. Architecture

```
src/acquisition/
├── gee.py                          # NEW — auth + Drive-export helper
├── bofedal_mask.py                 # NEW — orchestrator: polygonize → reconcile → write
└── datasets/
    ├── mapbiomas.py                # NEW — GEE-mediated Dataset (Coll. 2 wetland prep)
    └── wetland2026.py              # EXTENDED — zip-extraction path

Data/
├── external/
│   ├── manifest.yaml               # MODIFIED — add mapbiomas entry
│   └── mapbiomas/raw/              # gitignored — pulled from Drive after GEE export
├── bofedales_v2.geojson            # NEW — primary deliverable, committed
└── bofedales_v2_disputed.geojson   # NEW — disputed companion, committed

tests/acquisition/
├── test_gee.py                     # NEW — mocked ee + drive export
├── test_bofedal_mask.py            # NEW — sieve/clump/polygonize/reconcile w/ fixtures
└── datasets/
    └── test_mapbiomas.py           # NEW — mocked GEE pipeline
```

Three new modules + extensions. Reuses every existing pattern: Dataset protocol, manifest, Drive, AOI, tests with `tmp_path` fixtures.

## 5. GEE strategy

- **Auth:** reuse the v1 pattern — `ee.Authenticate()` + `ee.Initialize(project='ee-nunezrimedio-tesina', opt_url='https://earthengine-highvolume.googleapis.com')` from [notebooks/Data-Acquisition.ipynb](../../../notebooks/Data-Acquisition.ipynb). No service account. Auth tokens persist in the user's `~/.config/earthengine/`. First-time setup mirrored from the v1 README is added to `Data/external/README.md`.
- **Export destination:** GEE exports go to a separate Drive folder `Lithium_v2/gee_exports/<dataset_key>/` (not under `external/`), to visually distinguish GEE-produced rasters from human/script-uploaded artifacts. Local `rclone copy` mirrors them into `Data/external/<dataset_key>/raw/` so the downstream code uses the existing `external/` layout uniformly.
- **Export idempotency:** `gee.py` polls for task completion, and after success calls `rclone copy gdrive:Lithium_v2/gee_exports/<key>/ Data/external/<key>/raw/`. Re-running with the export already present skips the GEE submission and just re-mirrors from Drive.
- **Region of interest:** server-side clipped to `PUNA_BBOX` (already defined in `aoi.py`) before any reduction — keeps tile count small.

`src/acquisition/gee.py` API:

```python
def initialize(project: str = "ee-nunezrimedio-tesina") -> None: ...

def export_to_drive(
    image: "ee.Image",
    description: str,
    drive_folder: str,        # e.g. "Lithium_v2/gee_exports/mapbiomas"
    file_prefix: str,
    region: "ee.Geometry",
    scale: int = 30,
    timeout_min: int = 30,
) -> Path:
    """Submit export, poll until done, return local path after rclone mirror."""
    ...
```

## 6. MapBiomas dataset module

`src/acquisition/datasets/mapbiomas.py` implements the Dataset protocol with GEE-specific `fetch` semantics:

- `fetch(dest)`: build a server-side image (Coll. 2 image collection → select years 1998–2024 → remap to binary wetland-or-not → sum across years → threshold at `n_years_required` = 14) → call `gee.export_to_drive(...)` → return the local path to the mirrored binary raster.
- `clip(raw_path, dest, aoi)` is a no-op (`return None`) — the GEE step already produces the Puna-clipped raster.

`MapbiomasDataset` exposes a small config block:

```python
@dataclass
class MapbiomasDataset:
    asset_id: str                     # MapBiomas Coll. 2 image collection ID
    key: str = "mapbiomas"
    wetland_classes: tuple[int, ...] = (11,)   # MapBiomas wetland code(s); confirmed at impl
    analysis_window: tuple[int, int] = (1998, 2024)
    n_years_required: int = 14        # ≥50% of 27 years
```

The `asset_id` is the only field driven by the manifest URL (we'll repurpose the manifest's `url` field for the asset ID, with a note explaining the convention).

## 7. Polygonization pipeline

`src/acquisition/bofedal_mask.py` is the orchestrator. Takes the binary raster from the MapBiomas export and emits polygons:

1. **Sieve.** Remove connected components smaller than `min_pixels` (default 10 → ~0.9 ha at 30 m; matches Izquierdo's small-bofedal class cutoff). `rasterio.features.sieve`.
2. **Clump.** Label connected components for downstream polygon ID assignment. `scipy.ndimage.label` on the sieved boolean mask.
3. **Polygonize.** Vectorize via `rasterio.features.shapes`. Project to EPSG:4326.
4. **Aggregate-polygons-300m.** Merge polygons whose nearest-point distance is ≤ 300 m. Algorithm: buffer each polygon by 150 m, compute connected components via `shapely.ops.unary_union` + `shapely.geometry.MultiPolygon.geoms`, then dissolve the ORIGINAL (not buffered) polygons within each component. Matches Izquierdo's "aggregate polygons 300 m" post-processing.
5. **Filter.** Drop polygons with area < `min_area_m2` (default 5,000 m² ≈ 0.5 ha) after aggregation.

All five parameters live in one `@dataclass BofedalMaskConfig` so tuning is one place to look. The same module also runs reconciliation (next section).

## 8. Zenodo wetland2026 extraction + polygonization

`src/acquisition/datasets/wetland2026.py` gains a method `extract_puna_tif(raw_zip_path: Path, dest: Path) -> Path` that:

- Opens the zip (`zipfile.ZipFile`), finds entries matching `*.tif`.
- For each TIF, peeks the bounding box via `rasterio.open`. Keeps only TIFs whose bbox intersects `PUNA_BBOX`.
- Mosaics the matching TIFs (`rasterio.merge.merge`) into a single Puna-clipped raster.
- Writes to `Data/external/wetland2026/puna/wetland_puna.tif`.

The polygonization step in `bofedal_mask.py` then runs the same sieve/clump/polygonize/aggregate pipeline on the Zenodo Puna TIF to get the reference polygon set. (Same parameters as MapBiomas — they need to be comparable.)

## 9. Reconciliation

`bofedal_mask.py` reconciles the two polygon sets:

```python
def reconcile(
    primary: GeoDataFrame,        # MapBiomas-derived polygons
    reference: GeoDataFrame,      # Zenodo-derived polygons
    *,
    accept_threshold: float = 0.50,
    dispute_threshold: float = 0.10,
) -> tuple[GeoDataFrame, GeoDataFrame]:
    """Return (accepted, disputed).

    For each primary polygon, compute area-weighted overlap with all
    intersecting reference polygons. Sum overlaps; if ≥ accept_threshold,
    the polygon enters `accepted`. If between dispute_threshold and
    accept_threshold, it enters `disputed`. If < dispute_threshold,
    it is dropped entirely (treated as MapBiomas false positive).
    """
```

The accepted set is written to `Data/bofedales_v2.geojson`. The disputed set to `Data/bofedales_v2_disputed.geojson`. Both committed to git as data deliverables (they're small — likely <10 MB).

Each polygon gets a stable `bofedal_id` (UUID computed from the polygon's WKT geometry + a fixed namespace so the IDs are deterministic across reruns).

## 10. Driver integration

The existing `run.py` driver gains MapBiomas in its registry. A new `--build-mask` flag triggers the polygonization+reconciliation step after acquisition:

```bash
uv run python -m acquisition.run --only mapbiomas              # GEE export + mirror
uv run python -m acquisition.run --build-mask                   # run polygonize + reconcile
uv run python -m acquisition.run --only mapbiomas --build-mask  # both, end-to-end
```

`--build-mask` is idempotent: if `Data/bofedales_v2.geojson` exists and the input rasters' SHAs match the manifest, it's a no-op.

## 11. Storage

- **Local:**
  - `Data/external/mapbiomas/raw/bofedal_stable_1998_2024.tif` — gitignored
  - `Data/external/wetland2026/puna/wetland_puna.tif` — gitignored (added by Zenodo extraction)
  - `Data/bofedales_v2.geojson` — committed
  - `Data/bofedales_v2_disputed.geojson` — committed
- **Drive:**
  - `Lithium_v2/gee_exports/mapbiomas/` — GEE export destination
  - `Lithium_v2/external/mapbiomas/raw/` — mirrored from gee_exports
  - `Lithium_v2/external/wetland2026/puna/` — mirrored after local extraction
- **Manifest:** `mapbiomas` entry follows the existing schema. `url` field repurposed for the GEE asset ID (with a clear notes explanation). SHA pinned post-first-run as usual.

## 12. Error handling & idempotency

- **GEE export failure:** `gee.py` polls task status; on failure, logs the GEE error and raises. Retries are NOT automatic — GEE failures often need human investigation (quota, asset path, etc.).
- **Mirror failure:** existing `DriveError` handling from `drive.py`.
- **Polygonization failure:** raise with the bad raster path; no partial output written.
- **Reconciliation needs both inputs:** `bofedal_mask.py` checks both input polygon sets exist before running; on missing input, fails loud.
- **Re-runs:** every step is content-addressed by SHA where possible. The driver short-circuits when inputs and outputs are both present + matching.

## 13. Testing

- `test_gee.py`: mock `ee` module + `subprocess.run` for `rclone`. Verify `initialize()` calls `ee.Authenticate` + `ee.Initialize` with the right project; verify `export_to_drive` polls until done, then calls rclone mirror.
- `test_mapbiomas.py`: mock the GEE pipeline; verify `MapbiomasDataset.fetch` constructs the right server-side image (year range, remap, threshold) and passes the right region/scale to export.
- `test_bofedal_mask.py`: with the existing `tiny_geotiff` conftest fixture (and a new `tiny_binary_raster` if needed), exercise sieve, clump, polygonize, aggregate-300m, and reconcile. Specifically test:
  - Sieve removes small components below `min_pixels`
  - Aggregate-300m merges close polygons
  - Reconcile classifies polygons into accepted/disputed/dropped by the configured thresholds
- `test_wetland2026.py`: extend with a fixture `tiny_zip_with_tifs` (zipfile.ZipFile in `tmp_path`) and verify `extract_puna_tif` correctly filters and mosaics the Puna-overlapping TIFs.
- No live GEE calls in pytest. A separate manual smoke notebook (added to `notebooks/v2_acquisition.ipynb` as new cells) drives the real end-to-end run.

## 14. Documentation deliverables

- Update `Data/external/README.md` with: GEE auth setup, the `--build-mask` flag, where the GEE exports go on Drive, and how the mask was built (one paragraph pointing back to this spec).
- The two output GeoJSONs are self-describing (properties: `bofedal_id`, `area_m2`, `overlap_with_reference`, `mapbiomas_n_years`).

## 15. Out of scope

- Hand-validation of disputed polygons against high-res imagery (Stage 3 gate).
- Floristic class stratification (separate CONICET dataset).
- Other tier-2 GEE datasets (HLS, CHIRPS, ERA5-Land).
- Methodology v2 §3.1 text rewrite (spec PR).
- IzquierdoDataset module cleanup.

## 16. Risks

- **MapBiomas Coll. 2 asset path mis-resolved.** Mitigation: implementation begins with a quick GEE Code Editor probe to confirm the asset exists and the wetland class code; manifest notes pin the exact ID.
- **GEE export quota / timeout.** Coll. 2 server-side prep is light (image arithmetic over 27 years for a 4°×5° bbox), but quota can still bite. Mitigation: `timeout_min` parameter; clear logging of GEE task IDs so failed runs can be diagnosed via the GEE Tasks panel.
- **Wetland-class semantics differ.** MapBiomas's "wetland" includes coastal mangroves, riparian wetlands, etc. Mitigation: we restrict to the Puna y Altos Andes regional product (which is region-tuned), AND clip server-side to `PUNA_BBOX`. If commission errors remain noticeable, we add a class-specific filter in a follow-up.
- **Aggregate-300m artifacts.** Buffering by 150 m then back-deriving polygons can produce strange shapes near edges. Mitigation: test with realistic-shaped fixtures; emit polygon convex-hull ratio as a property so anomalies surface.
- **Drive quota.** GEE exports + mirrored copies double the storage. Mitigation: the `gee_exports/` folder can be periodically pruned once the mirror is verified.
- **Reconciliation drops too many polygons.** If MapBiomas and Zenodo disagree sharply (e.g. different wetland-class definitions), `disputed` could be larger than `accepted`. Mitigation: spec sets thresholds at 50%/10%; first run lets us see the distribution and tune if needed before the spec text gets re-locked.
