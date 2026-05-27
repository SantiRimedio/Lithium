from pathlib import Path
from unittest.mock import MagicMock

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.usgs import UsgsDataset


def _stub_get(content: bytes):
    resp = MagicMock()
    resp.iter_content = MagicMock(return_value=[content])
    resp.headers = {"content-length": str(len(content))}
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.raise_for_status = MagicMock()
    return resp


def test_usgs_fetch_downloads_zip_to_raw(mocker, tmp_path):
    mocker.patch("requests.get", return_value=_stub_get(b"PK\x03\x04fake-zip"))

    ds = UsgsDataset(url="https://example.com/usgs.gdb.zip")
    raw = ds.fetch(tmp_path)

    assert raw == tmp_path / "raw" / "usgs.gdb.zip"
    assert raw.read_bytes() == b"PK\x03\x04fake-zip"


def test_usgs_clip_returns_none(tmp_path):
    """USGS gdb is already regional; clip is a no-op."""
    ds = UsgsDataset(url="https://example.com/usgs.gdb.zip")
    fake_raw = tmp_path / "raw" / "usgs.gdb.zip"
    fake_raw.parent.mkdir(parents=True)
    fake_raw.write_bytes(b"x")

    assert ds.clip(fake_raw, tmp_path, PUNA_BBOX) is None
