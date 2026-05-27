"""Shared protocol and HTTP helper for dataset modules."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from acquisition.aoi import BBox


class Dataset(Protocol):
    """Contract every dataset module implements."""

    key: str

    def fetch(self, dest: Path) -> Path:
        """Download raw artifact under `dest/raw/`. Return the primary file path.

        Must be idempotent: skip if the file already exists.
        """
        ...

    def clip(self, raw_path: Path, dest: Path, aoi: BBox) -> Path | None:
        """Clip raw to AOI, write under `dest/puna/`. Return None if N/A."""
        ...


def http_download(url: str, dest: Path, *, max_attempts: int = 3, chunk_size: int = 1 << 20) -> Path:
    """Stream a URL to dest with retries; idempotent on the final filename.

    Writes to `dest.tmp` first and renames on success so a partial download
    can never be mistaken for a complete one.
    """
    dest = Path(dest)
    if dest.exists():
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    @retry(
        retry=retry_if_exception_type((ConnectionError, requests.RequestException)),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    def _attempt() -> None:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)

    _attempt()
    tmp.rename(dest)
    return dest
