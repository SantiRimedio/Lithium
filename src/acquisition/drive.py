"""Thin rclone wrapper for the shared Google Drive folder."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class DriveError(Exception):
    """rclone returned a non-zero exit."""


@dataclass(frozen=True)
class DriveRemote:
    """A configured rclone remote + a root path under it.

    `remote_name` matches an entry in `rclone config` (e.g. "gdrive").
    `root` is the path under the remote where this project lives.
    """

    remote_name: str
    root: str

    def _remote_path(self, relpath: str) -> str:
        return f"{self.remote_name}:{self.root.rstrip('/')}/{relpath.lstrip('/')}"

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise DriveError(
                f"rclone failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    def push(self, local: Path, relpath: str) -> None:
        """Upload a single local file to relpath under the remote root."""
        self._run(["rclone", "copyto", str(local), self._remote_path(relpath)])

    def pull(self, relpath: str, local: Path) -> None:
        """Download a single remote file to a local path."""
        local.parent.mkdir(parents=True, exist_ok=True)
        self._run(["rclone", "copyto", self._remote_path(relpath), str(local)])

    def exists(self, relpath: str) -> bool:
        """Return True if the remote object exists. Uses `rclone lsf`."""
        result = self._run(["rclone", "lsf", self._remote_path(relpath)])
        return bool(result.stdout.strip())

    def pull_root(self, local_root: Path) -> None:
        """Mirror the remote root into local_root.

        Excludes manifest.yaml and README.md (those are committed locally
        and the remote copy is not authoritative). Used by the
        ``run --pull-only`` bootstrap path per spec §8.
        """
        local_root.mkdir(parents=True, exist_ok=True)
        self._run([
            "rclone", "copy",
            f"{self.remote_name}:{self.root}",
            str(local_root),
            "--exclude", "manifest.yaml",
            "--exclude", "README.md",
        ])
