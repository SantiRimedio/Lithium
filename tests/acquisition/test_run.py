from pathlib import Path
from unittest.mock import MagicMock

import pytest

from acquisition.manifest import ManifestEntry, dump_manifest
from acquisition.run import DATASET_REGISTRY, run


@pytest.fixture
def manifest_path(tmp_path):
    entries = [
        ManifestEntry(
            key="usgs", title="t", url="https://example.com/u.zip",
            version="1", license="x", clip_to_puna=False,
        ),
    ]
    path = tmp_path / "manifest.yaml"
    dump_manifest(entries, path)
    return path


def test_run_invokes_fetch_then_drive_push(mocker, tmp_path, manifest_path):
    # Fake dataset module that succeeds.
    fake_ds = MagicMock()
    fake_ds.fetch.return_value = tmp_path / "external" / "usgs" / "raw" / "u.zip"
    (tmp_path / "external" / "usgs" / "raw").mkdir(parents=True)
    (tmp_path / "external" / "usgs" / "raw" / "u.zip").write_bytes(b"hello world")
    fake_ds.clip.return_value = None

    mocker.patch.dict(DATASET_REGISTRY, {"usgs": lambda url: fake_ds}, clear=True)

    drive = MagicMock()

    run(manifest_path=manifest_path, external_root=tmp_path / "external", drive=drive)

    fake_ds.fetch.assert_called_once_with(tmp_path / "external" / "usgs")
    drive.push.assert_called_once()
    # The pushed local file is the raw artifact.
    assert drive.push.call_args[0][0] == tmp_path / "external" / "usgs" / "raw" / "u.zip"


def test_run_fills_sha_and_size_on_first_success(mocker, tmp_path, manifest_path):
    fake_ds = MagicMock()
    raw = tmp_path / "external" / "usgs" / "raw" / "u.zip"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"hello world")
    fake_ds.fetch.return_value = raw
    fake_ds.clip.return_value = None

    mocker.patch.dict(DATASET_REGISTRY, {"usgs": lambda url: fake_ds}, clear=True)
    drive = MagicMock()

    run(manifest_path=manifest_path, external_root=tmp_path / "external", drive=drive)

    from acquisition.manifest import load_manifest
    entries = load_manifest(manifest_path)
    # SHA256 of "hello world".
    assert entries[0].sha256 == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert entries[0].size_bytes == 11


def test_run_only_filter_skips_other_keys(mocker, tmp_path, manifest_path):
    fake_ds = MagicMock()
    mocker.patch.dict(DATASET_REGISTRY, {"usgs": lambda url: fake_ds}, clear=True)
    drive = MagicMock()

    run(manifest_path=manifest_path, external_root=tmp_path / "external",
        drive=drive, only={"spei"})

    fake_ds.fetch.assert_not_called()
    drive.push.assert_not_called()


def test_run_pull_only_mirrors_drive_and_skips_fetch(mocker, tmp_path, manifest_path):
    fake_ds = MagicMock()
    mocker.patch.dict(DATASET_REGISTRY, {"usgs": lambda url: fake_ds}, clear=True)
    drive = MagicMock()

    external = tmp_path / "external"
    run(manifest_path=manifest_path, external_root=external,
        drive=drive, pull_only=True)

    drive.pull_root.assert_called_once_with(external)
    fake_ds.fetch.assert_not_called()
    drive.push.assert_not_called()
