"""CLI driver: read manifest, fetch+validate+clip each dataset, push to Drive."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Iterable

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets._base import Dataset
from acquisition.datasets.izquierdo import IzquierdoDataset
from acquisition.datasets.spei import SpeiDataset
from acquisition.datasets.usgs import UsgsDataset
from acquisition.datasets.wetland2026 import Wetland2026Dataset
from acquisition.drive import DriveRemote
from acquisition.manifest import (
    ManifestEntry,
    compute_sha256,
    dump_manifest,
    load_manifest,
    verify_sha256,
)


DATASET_REGISTRY: dict[str, Callable[[str], Dataset]] = {
    "usgs": lambda url: UsgsDataset(url=url),
    "izquierdo": lambda url: IzquierdoDataset(url=url),
    "wetland2026": lambda url: Wetland2026Dataset(url=url),
    "spei": lambda url: SpeiDataset(url=url),
}


def _process_entry(
    entry: ManifestEntry,
    external_root: Path,
    drive: DriveRemote,
) -> bool:
    """Process one manifest entry. Returns True if the entry mutated (new SHA)."""
    factory = DATASET_REGISTRY.get(entry.key)
    if factory is None:
        print(f"[{entry.key}] no registered module — skipping", file=sys.stderr)
        return False

    ds = factory(entry.url)
    dataset_root = external_root / entry.key
    raw = ds.fetch(dataset_root)

    mutated = False
    if entry.sha256:
        verify_sha256(raw, entry.sha256)
    else:
        entry.sha256 = compute_sha256(raw)
        entry.size_bytes = raw.stat().st_size
        mutated = True

    drive.push(raw, f"{entry.key}/raw/{raw.name}")

    if entry.clip_to_puna:
        clipped = ds.clip(raw, dataset_root, PUNA_BBOX)
        if clipped is not None:
            drive.push(clipped, f"{entry.key}/puna/{clipped.name}")

    return mutated


def run(
    *,
    manifest_path: Path,
    external_root: Path,
    drive: DriveRemote,
    only: Iterable[str] | None = None,
) -> None:
    """Process all (or a subset of) manifest entries end-to-end."""
    entries = load_manifest(manifest_path)
    only_set = set(only) if only else None

    any_mutated = False
    for entry in entries:
        if only_set is not None and entry.key not in only_set:
            continue
        print(f"[{entry.key}] fetching…", file=sys.stderr)
        mutated = _process_entry(entry, external_root, drive)
        any_mutated = any_mutated or mutated

    if any_mutated:
        dump_manifest(entries, manifest_path)
        print("manifest updated with new SHA/size — commit it", file=sys.stderr)


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
    args = parser.parse_args(argv)

    only = set(args.only.split(",")) if args.only else None
    drive = DriveRemote(remote_name=args.remote_name, root=args.remote_root)

    run(
        manifest_path=args.manifest,
        external_root=args.external_root,
        drive=drive,
        only=only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
