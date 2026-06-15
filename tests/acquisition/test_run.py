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


def test_run_build_mask_invokes_pipeline(mocker, tmp_path):
    from acquisition.run import run_build_mask

    build = mocker.patch("acquisition.bofedal_mask.build_mask")

    primary = tmp_path / "mapbiomas" / "raw" / "bofedal_stable.tif"
    reference = tmp_path / "wetland2026" / "puna" / "wetland_puna.tif"
    primary.parent.mkdir(parents=True)
    reference.parent.mkdir(parents=True)
    primary.touch()
    reference.touch()

    run_build_mask(
        external_root=tmp_path,
        repo_root=tmp_path / "_repo",
    )

    build.assert_called_once()
    kw = build.call_args.kwargs or {}
    # Normalize args/kwargs into a single dict.
    args = build.call_args.args
    all_args = {"primary_raster": args[0] if args else kw.get("primary_raster"),
                "reference_raster": args[1] if len(args) > 1 else kw.get("reference_raster"),
                "accepted_out": args[2] if len(args) > 2 else kw.get("accepted_out"),
                "disputed_out": args[3] if len(args) > 3 else kw.get("disputed_out")}
    assert all_args["primary_raster"] == primary
    assert all_args["reference_raster"] == reference
    assert all_args["accepted_out"] == tmp_path / "_repo" / "Data" / "bofedales_v2.geojson"
    assert all_args["disputed_out"] == tmp_path / "_repo" / "Data" / "bofedales_v2_disputed.geojson"


def test_run_build_mask_requires_inputs(tmp_path):
    from acquisition.run import run_build_mask

    with pytest.raises(FileNotFoundError, match="MapBiomas raster"):
        run_build_mask(external_root=tmp_path, repo_root=tmp_path / "_repo")


def test_run_build_mask_auto_extracts_wetland_zip(mocker, tmp_path):
    """If the zenodo zip is present and the puna tif is missing, the driver
    invokes extract_puna_tif before bofedal_mask.build_mask."""
    from acquisition.run import run_build_mask

    # Pre-create the primary raster + the zenodo zip; do NOT create the puna tif.
    primary = tmp_path / "mapbiomas" / "raw" / "bofedal_stable.tif"
    primary.parent.mkdir(parents=True)
    primary.touch()

    zenodo_zip = tmp_path / "wetland2026" / "raw" / "wetland2026_high_probabilities.zip"
    zenodo_zip.parent.mkdir(parents=True)
    zenodo_zip.touch()

    extract = mocker.patch(
        "acquisition.datasets.wetland2026.Wetland2026Dataset.extract_puna_tif",
        side_effect=lambda raw, dest: (
            (dest / "puna").mkdir(parents=True, exist_ok=True) or
            (dest / "puna" / "wetland_puna.tif").touch() or
            (dest / "puna" / "wetland_puna.tif")
        ),
    )
    mocker.patch("acquisition.bofedal_mask.build_mask")

    run_build_mask(external_root=tmp_path, repo_root=tmp_path / "_repo")

    extract.assert_called_once()
