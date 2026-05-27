from pathlib import Path
from unittest.mock import MagicMock

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.izquierdo import IzquierdoDataset


def _stub_get(content: bytes):
    resp = MagicMock()
    resp.iter_content = MagicMock(return_value=[content])
    resp.headers = {"content-length": str(len(content))}
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.raise_for_status = MagicMock()
    return resp


def test_izquierdo_fetch_writes_to_raw(mocker, tmp_path):
    mocker.patch("requests.get", return_value=_stub_get(b"<shp-zip>"))

    ds = IzquierdoDataset(url="https://example.com/izq.zip")
    raw = ds.fetch(tmp_path)

    assert raw == tmp_path / "raw" / "izquierdo_hydroecosystems.zip"
    assert raw.read_bytes() == b"<shp-zip>"


def test_izquierdo_fetch_idempotent_when_present(mocker, tmp_path):
    get = mocker.patch("requests.get")
    (tmp_path / "raw").mkdir()
    existing = tmp_path / "raw" / "izquierdo_hydroecosystems.zip"
    existing.write_bytes(b"already")

    ds = IzquierdoDataset(url="https://example.com/izq.zip")
    raw = ds.fetch(tmp_path)

    assert raw == existing
    assert existing.read_bytes() == b"already"
    get.assert_not_called()


def test_izquierdo_clip_returns_none(tmp_path):
    ds = IzquierdoDataset(url="https://example.com/izq.zip")
    fake_raw = tmp_path / "raw" / "izquierdo_hydroecosystems.zip"
    fake_raw.parent.mkdir(parents=True)
    fake_raw.write_bytes(b"x")
    assert ds.clip(fake_raw, tmp_path, PUNA_BBOX) is None
