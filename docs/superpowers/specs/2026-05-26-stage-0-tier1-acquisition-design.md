# Stage 0 Tier-1 Data Acquisition — Design

*Date: 2026-05-26 · Status: approved, ready for implementation plan*
*Implements: Methodology v2 §7 (partial — tier-1 only)*
*Reference: [text/Methodology_v2.md](../../../text/Methodology_v2.md)*

## 1. Context

Methodology v2 (May 2026) supersedes the v1 MODIS-on-H3 design. v2 moves the unit of analysis to bofedal polygons and adds a manifest of 11 datasets in §7 ("Stage 0 checklist"). This spec covers **tier-1 only**: the four datasets that require no special credentials and can be made fully reproducible immediately. Tier-2 (LiCSAR, SAOCOM, HLS, MapBiomas, CHIRPS/ERA5-Land/MSWEP, Paz et al. 2025 reverse-engineered data, FARN reports) is deferred to a separate spec once credential and storage assumptions for those sources are settled.

The repo currently follows a notebook-first convention from v1 ([notebooks/Data-Acquisition.ipynb](../../../notebooks/Data-Acquisition.ipynb)). v2 introduces a Python package (`src/acquisition/`) for reusable, testable acquisition logic, with a thin notebook as the interactive entry point. v1 notebooks are not deleted or moved.

## 2. Goals & non-goals

**Goals**

- Anyone with the repo + Drive access can rebuild `Data/external/` for the four tier-1 datasets by running one command.
- Every downloaded artifact has a recorded SHA256, version, license, and provenance note.
- Global rasters (Zenodo wetland, SPEI) are clipped to a generous Argentine Puna bounding box at acquisition time to keep local storage manageable.
- The module/manifest pattern scales to tier-2 by adding one entry + one module per new dataset.

**Non-goals**

- No bofedal mask construction (Stage 1).
- No mining footprint digitization (Stage 2).
- No GEE-mediated acquisition (HLS, MapBiomas, CHIRPS, ERA5-Land — all tier-2).
- No InSAR processing (Stage 4b).
- No CI / cloud automation beyond local test runs.
- No analytical processing of any kind.

## 3. Tier-1 datasets

| Key | Source | Format | Approx. size | Clip to Puna? |
|---|---|---|---|---|
| `usgs` | USGS Lithium Triangle geodatabase — DOI 10.5066/P9RLUH4F | File geodatabase (vector) | ~MBs | No (already regional) |
| `izquierdo` | Izquierdo, Foguet & Grau 2016 — CONICET handle 11336/58267 | Vector | ~tens of MB | No (already regional) |
| `wetland2026` | 2026 global 30 m high-altitude wetland map — Zenodo record 18339573 (*Sci Data* s41597-026-07020-w) | GeoTIFF, 30 m global | ~GBs | Yes |
| `spei` | Global SPEI 1982–2021 (*Sci Data* s41597-024-03047-z) | NetCDF, 0.5° monthly | ~GB | Yes |

Justification per dataset traces to Methodology v2 §7 and §1.

## 4. Architecture

```
src/acquisition/
├── __init__.py
├── aoi.py                  # PUNA_BBOX + helper to load endorheic basins
├── manifest.py             # YAML loader, dataclass schema, SHA verification
├── drive.py                # rclone wrapper (push, pull, list — idempotent)
├── run.py                  # CLI: `python -m acquisition.run [--only k1,k2]`
└── datasets/
    ├── __init__.py
    ├── _base.py            # Dataset protocol
    ├── usgs.py
    ├── izquierdo.py
    ├── wetland2026.py
    └── spei.py

Data/external/              # gitignored except manifest.yaml + README.md
├── manifest.yaml           # COMMITTED — declarative catalog
├── README.md               # COMMITTED — how to run, where Drive lives
└── <dataset_key>/
    ├── raw/                # original artifact, full resolution
    └── puna/               # bbox-clipped (only where clip_to_puna: true)

notebooks/v2_acquisition.ipynb   # thin: imports + per-dataset cells
tests/acquisition/                # unit + mocked-network integration tests
pyproject.toml                    # uv-managed deps, locked
```

Three layers, top-down:

- **`run.py`** is the only entry point. Reads the manifest, dispatches per dataset, handles Drive sync.
- **`datasets/<key>.py`** modules each own one dataset, implementing the protocol from `_base.py`.
- **`manifest.py`, `aoi.py`, `drive.py`** are shared utilities — pure functions, no per-dataset knowledge.

## 5. Dataset module contract

`datasets/_base.py`:

```python
from pathlib import Path
from typing import Protocol
from acquisition.aoi import BBox

class Dataset(Protocol):
    key: str

    def fetch(self, dest: Path) -> Path:
        """Download raw artifact to `dest/raw/`. Returns path to primary file.
        Must be idempotent: skip if file exists and SHA matches manifest."""
        ...

    def validate(self, raw_path: Path, expected_sha256: str) -> None:
        """Raise IntegrityError if SHA256 of raw_path != expected_sha256.
        Called by the driver, not by `fetch`."""
        ...

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        """Clip to AOI bbox, write to `dest/puna/`. Return None if not applicable
        (e.g. usgs, izquierdo) so the driver can skip the Drive push for the
        clipped variant."""
        ...
```

The driver loops per manifest entry:

```
fetch(local raw/)
  → validate against manifest SHA
  → clip(local puna/) if clip_to_puna
  → drive.push(raw)
  → drive.push(puna) if clipped
```

Every step is idempotent: re-running the driver with all data present should be a no-op (verified by tests).

## 6. Manifest schema

`Data/external/manifest.yaml`:

```yaml
- key: usgs
  title: "USGS Argentine Lithium Geodatabase"
  doi: "10.5066/P9RLUH4F"
  url: "https://www.sciencebase.gov/catalog/file/get/<id>"
  version: "1.0"
  license: "Public domain (USGS)"
  sha256: ""           # filled on first successful fetch
  size_bytes: 0        # filled on first successful fetch
  clip_to_puna: false
  notes: |
    86 Argentine salars; 44 no-Li are the candidate control set
    in Methodology v2 §3.4 (CS-DiD identification).

- key: izquierdo
  title: "Izquierdo, Foguet & Grau 2016 — Puna hydroecosystem polygons"
  doi: ""              # CONICET handle, not a DOI
  handle: "11336/58267"
  url: "<resolved URL filled at implementation time>"
  version: "2016"
  license: "<filled at implementation time from source page>"
  sha256: ""
  size_bytes: 0
  clip_to_puna: false
  notes: |
    Primary bofedal mask per Methodology v2 §3.1.
    Floristic class metadata required for stratification (v2 §1).

- key: wetland2026
  title: "Global 30 m high-altitude wetland map (2026)"
  doi: "10.5281/zenodo.18339573"
  url: "https://zenodo.org/records/18339573/files/<filename>"
  version: "v1.1"
  license: "<as stated on Zenodo record>"
  sha256: ""
  size_bytes: 0
  clip_to_puna: true
  notes: |
    Cross-validation mask vs Izquierdo per Methodology v2 §3.1.
    Mountain-wetland layer only; subset to Argentine Puna at clip step.

- key: spei
  title: "Global SPEI 1982–2021"
  doi: "10.1038/s41597-024-03047-z"
  url: "<SPEIbase download URL>"
  version: "2024 release"
  license: "<as stated by SPEIbase>"
  sha256: ""
  size_bytes: 0
  clip_to_puna: true
  notes: |
    SPEI-12 and SPEI-24 are the climate covariates in Methodology v2 §3.5.
    Driver of conditional parallel trends in CS-DiD.
```

`manifest.py` parses this into dataclasses, validates that required fields are present, and (on first successful run per entry) writes back the computed SHA + size. The resulting diff is committed by the user — pinning the data version.

## 7. AOI

`src/acquisition/aoi.py`:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

PUNA_BBOX = BBox(west=-69.0, south=-27.0, east=-65.0, north=-22.0)
```

Plus a `puna_basins() -> GeoDataFrame` helper that loads the existing [Data/Endorheic_basins_Puna.geojson](../../../Data/Endorheic_basins_Puna.geojson).

The bbox is deliberately generous — it is a storage optimization for global rasters, not the analytical AOI. Stage 1 will define the precise bofedal-selection geometry.

## 8. Storage strategy

**Local (developer machine):**

- `Data/external/<key>/raw/` — full downloads. Gitignored.
- `Data/external/<key>/puna/` — clipped subsets. Gitignored.
- `Data/external/manifest.yaml` — committed.
- `Data/external/README.md` — committed; explains the layout and the Drive path.

**Shared (Google Drive):**

- Folder `Lithium_v2/external/<key>/raw/` and `Lithium_v2/external/<key>/puna/`.
- Mirrors the local layout exactly.
- Access via `rclone` (token stored locally via `rclone config`). The acquisition driver shells out to `rclone copy` for idempotent push/pull.
- A second collaborator (Jakob) can bootstrap by running `python -m acquisition.run --pull-only`, which pulls from Drive without re-downloading from upstream.

**`.gitignore` addition:**

```
# Stage 0 external data (raw + clipped)
Data/external/*/
!Data/external/README.md
!Data/external/manifest.yaml
```

## 9. Error handling & idempotency

- **Network failures:** 3 retries with exponential backoff (`tenacity`). Failure after retries: raise, log dataset key.
- **Partial writes:** download to `<file>.tmp`, rename to final name only after byte-count and (where known) Content-Length match.
- **SHA mismatch on validate:** raise `IntegrityError`, leave the offending file in place (renamed to `<file>.SHA_MISMATCH`) so the developer can inspect rather than silently re-download.
- **First-run SHA capture:** if manifest entry's `sha256` is empty, compute it after fetch, write it back to the manifest. Subsequent runs require it to match.
- **Drive push failure:** local fetch already succeeded, so next driver invocation will retry the push from local cache.
- **Driver re-runs:** the no-op case (all manifest items present locally with matching SHA, all mirrored to Drive) completes in seconds and makes no network requests beyond an `rclone lsf` listing.

## 10. Dependency management

- Add `pyproject.toml` at repo root with `uv` as the package manager.
- Pinned deps: `requests`, `tenacity`, `pyyaml`, `geopandas`, `rasterio`, `xarray`, `netcdf4`, `pytest`, `pytest-mock`.
- Lockfile (`uv.lock`) committed.
- Notebooks pick up the same env via the project's kernel; no separate notebook deps.
- The existing v1 notebook has no env story; this is the entry point for fixing that, but we do not retroactively port v1 notebooks.

## 11. Testing

- **Unit:** `manifest.py` (schema validation, SHA fill-and-verify), `aoi.py` (bbox math, basin file load).
- **Integration (mocked network):** one per dataset module. Mock the HTTP fetch with a small fixture artifact, exercise validate + clip end-to-end. Assert the local layout and that `clip_to_puna: false` modules return `None` from `clip()`.
- **No live-network tests.** Live runs are manual.
- Run via `uv run pytest tests/acquisition/`.

## 12. Documentation deliverables

- `Data/external/README.md` (new, committed) — how to run, how to set up `rclone`, where the shared Drive folder is, the meaning of each dataset, the supersedes-v1 note.
- One-line note prepended to [notebooks/overview.md](../../../notebooks/overview.md) flagging the v1 notebooks as superseded by Methodology v2 and pointing to this spec.
- The manifest itself is the authoritative data catalog — no separate catalog doc.

## 13. Out of scope (tier-2 — separate spec)

Datasets listed in Methodology v2 §7 but not handled here, with the reason each is deferred:

- **MapBiomas Argentina Collection 2 (Puna y Altos Andes)** — GEE-mediated; requires GEE auth design + export-to-Drive orchestration.
- **HLS Landsat/Sentinel-2** — GEE-mediated; large; needs scene-selection logic per bofedal.
- **CHIRPS, ERA5-Land, MSWEP** — GEE-mediated for two of three; bias-correction strategy not yet specified.
- **Sentinel-1 LiCSAR frames** — needs COMET portal credentials + LiCSBAS pipeline decision.
- **SAOCOM L-band** — needs CONAE credentials; access timeline uncertain.
- **Paz et al. 2025 Heliyon water-footprint data** — manual extraction from supplementary materials.
- **FARN reports (Marchegiani 2019, Sal de Vida 2023)** — PDF testimony geocoding; qualitative pipeline.

A tier-2 spec will be brainstormed separately when credentials and storage volumes for those sources are known.

## 14. Risks (this spec only)

- **CONICET handle resolves to a webpage, not a direct download.** Izquierdo's data may require a manual click-through. Mitigation: if no programmatic URL exists, document the manual step in `README.md` and have the module verify a developer-placed file rather than fetch.
- **Zenodo file size.** The global 30 m wetland raster could be very large. Mitigation: stream the download; if a smaller tiled distribution exists on the Zenodo record, prefer those tiles overlapping the Puna bbox.
- **SPEI distribution channel.** SPEIbase has changed delivery mechanisms over time. Mitigation: confirm the active URL at implementation time and pin it in the manifest; if delivery is by GHCN-style chunked NetCDF, document the chunk pattern.
- **`rclone` setup friction.** First-time setup requires browser OAuth. Mitigation: `README.md` walks through it once; the token then persists.
