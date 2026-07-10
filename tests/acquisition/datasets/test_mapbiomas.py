from pathlib import Path
from unittest.mock import MagicMock

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.mapbiomas import MapbiomasDataset


def test_mapbiomas_fetch_initializes_and_exports(mocker, tmp_path):
    init = mocker.patch("acquisition.datasets.mapbiomas.initialize")

    # Simulate export_to_drive landing a .tif in the raw dir, as the real
    # rclone copy would.
    raw_dir = tmp_path / "raw"
    expected_tif = raw_dir / "bofedal_stable_1998_2024-0000.tif"

    def fake_export(**kwargs):
        local_dest = kwargs["local_dest"]
        local_dest.mkdir(parents=True, exist_ok=True)
        expected_tif.touch()
        return local_dest

    export = mocker.patch(
        "acquisition.datasets.mapbiomas.export_to_drive",
        side_effect=fake_export,
    )
    # Stub the image-construction helper so we don't have to mock ee.* chains.
    image_stub = MagicMock(name="StableBofedalImage")
    mocker.patch(
        "acquisition.datasets.mapbiomas._build_stable_bofedal_image",
        return_value=image_stub,
    )
    # The region helper builds an ee.Geometry — stub it too.
    region_stub = MagicMock(name="PunaRegion")
    mocker.patch(
        "acquisition.datasets.mapbiomas._puna_region",
        return_value=region_stub,
    )

    ds = MapbiomasDataset(asset_id="projects/test/mapbiomas_coll2")
    out = ds.fetch(tmp_path)

    init.assert_called_once()
    export.assert_called_once()
    kw = export.call_args.kwargs
    assert kw["image"] is image_stub
    assert kw["region"] is region_stub
    assert kw["drive_folder"] == "Lithium_v2_gee_exports_mapbiomas"
    assert kw["file_prefix"].startswith("bofedal_stable_")
    assert kw["scale"] == 30
    assert out == expected_tif


def test_mapbiomas_clip_returns_none(tmp_path):
    """Server-side already produced the Puna subset; local clip is a no-op."""
    ds = MapbiomasDataset(asset_id="projects/test/mapbiomas_coll2")
    assert ds.clip(tmp_path / "raw" / "x.tif", tmp_path, PUNA_BBOX) is None
