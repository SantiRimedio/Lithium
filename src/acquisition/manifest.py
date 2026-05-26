"""Manifest schema and YAML loader for Stage 0 datasets."""
from __future__ import annotations

from dataclasses import dataclass, fields
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
