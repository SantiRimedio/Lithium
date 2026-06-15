# `Data/external/` — Stage 0 acquired datasets

This directory is the local cache for raw and Puna-clipped artifacts of the
four tier-1 datasets specified by Methodology v2 §7.

## What's tracked vs. ignored

- **`manifest.yaml`** — committed. The authoritative catalog. Lists each
  dataset's DOI/URL, license, version, expected SHA256, and clip behavior.
- **`README.md`** — this file; committed.
- **`<key>/raw/`** and **`<key>/puna/`** — gitignored. Rebuild on demand
  from the manifest, or pull from the shared Google Drive folder.

## First-time setup

1. Install [`rclone`](https://rclone.org/install/) (e.g. `brew install rclone`).
2. Configure a Google Drive remote named `gdrive`:

   ```bash
   rclone config
   # n) new remote, name: gdrive, type: drive, follow OAuth in browser
   ```

3. Confirm access to the shared folder `Lithium_v2/external/` (ask Santi for
   sharing permission if it's not visible).
4. Resolve the `url` (and `license` where missing) for each entry in
   `manifest.yaml`. Commit the manifest after filling these in.

## Running the acquisition

Pull everyone else's existing downloads from Drive (cheap, recommended first
run — equivalent to `rclone copy gdrive:Lithium_v2/external Data/external --exclude manifest.yaml --exclude README.md`):

```bash
uv run python -m acquisition.run --pull-only
```

Run the full pipeline (fetch missing artifacts from source, clip, push to Drive):

```bash
uv run python -m acquisition.run
```

Run a single dataset:

```bash
uv run python -m acquisition.run --only usgs
```

After a first successful fetch for any entry, the driver writes the computed
SHA256 and `size_bytes` back to `manifest.yaml`. **Commit that diff** to pin
the data version.

## What each dataset is for

| Key | Used in | Notes |
|---|---|---|
| `usgs` | Methodology v2 §3.4 control set | 86 Argentine salars; 44 no-Li = candidate controls. |
| `izquierdo` | Methodology v2 §3.1 primary mask | Bofedal polygons with floristic class. |
| `wetland2026` | Methodology v2 §3.1 cross-validation mask | Global 30 m, clipped to Puna bbox. |
| `spei` | Methodology v2 §3.5 climate covariate | SPEI-12 and SPEI-24 drive parallel-trends conditioning. |

## Tier-2 datasets (not handled by this pipeline)

LiCSAR, SAOCOM, HLS, MapBiomas, CHIRPS, ERA5-Land, MSWEP, Paz et al. 2025,
and FARN reports are deferred to a separate spec (credential and storage
decisions pending). See
[docs/superpowers/specs/2026-05-26-stage-0-tier1-acquisition-design.md](../../docs/superpowers/specs/2026-05-26-stage-0-tier1-acquisition-design.md)
§13.

## Troubleshooting

- **`SHA256 mismatch`** — the upstream artifact changed. Confirm by inspecting
  the source page; if the change is legitimate (new version), clear `sha256`
  and `size_bytes` for that entry and re-run to repopulate.
- **`rclone failed`** — re-run `rclone config reconnect gdrive:` to refresh
  the OAuth token.
- **CONICET click-through download for `izquierdo`** — download manually,
  place at `Data/external/izquierdo/raw/izquierdo_hydroecosystems.zip`, and
  re-run the driver; it will detect the existing file and skip the fetch.

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
