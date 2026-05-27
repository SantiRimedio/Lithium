"""Manifest schema and YAML loader for Stage 0 datasets."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ManifestEntry:
    key: str
    title: str
    url: str
    version: str
    license: str
    clip_to_puna: bool
    sha256: str = ""
    size_bytes: int = 0
    doi: str = ""
    handle: str = ""
    notes: str = ""


_REQUIRED_FIELDS = {"key", "title", "url", "version", "license", "clip_to_puna"}
_ALL_FIELDS = {f.name for f in fields(ManifestEntry)}


def _validate_entry(raw: dict[str, Any]) -> ManifestEntry:
    keys = set(raw.keys())
    missing = _REQUIRED_FIELDS - keys
    if missing:
        raise ValueError(f"manifest entry missing required field(s): {sorted(missing)}")
    unknown = keys - _ALL_FIELDS
    if unknown:
        raise ValueError(f"manifest entry has unknown field(s): {sorted(unknown)}")
    return ManifestEntry(**raw)


def load_manifest(path: Path) -> list[ManifestEntry]:
    """Load and validate a manifest.yaml file."""
    raw = yaml.safe_load(path.read_text()) or []
    if not isinstance(raw, list):
        raise ValueError(f"manifest at {path} must be a YAML list, got {type(raw).__name__}")
    return [_validate_entry(item) for item in raw]


class IntegrityError(Exception):
    """Raised when a file's SHA256 does not match the manifest."""


def compute_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Compute SHA256 of a file, streaming in 1 MiB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    actual = compute_sha256(path)
    if actual != expected:
        # Move the bad file aside so the next run's existence check on the
        # original path misses and triggers a fresh download. Spec §9.
        bad = path.with_suffix(path.suffix + ".SHA_MISMATCH")
        path.rename(bad)
        raise IntegrityError(
            f"SHA256 mismatch for {path}: expected {expected}, got {actual}; "
            f"moved to {bad} so the next run will re-download"
        )


def dump_manifest(entries: list[ManifestEntry], path: Path) -> None:
    """Write entries back to a manifest.yaml, preserving field order."""
    payload = [asdict(e) for e in entries]
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
