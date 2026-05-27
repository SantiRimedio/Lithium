from pathlib import Path
from unittest.mock import MagicMock

import pytest

from acquisition.datasets._base import http_download


def test_http_download_streams_to_tmp_and_renames(mocker, tmp_path):
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.iter_content = MagicMock(return_value=[b"chunk1", b"chunk2"])
    fake_resp.headers = {"content-length": "12"}
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    fake_resp.raise_for_status = MagicMock()
    mocker.patch("requests.get", return_value=fake_resp)

    dest = tmp_path / "out.bin"
    result = http_download("https://example.com/x", dest)

    assert result == dest
    assert dest.read_bytes() == b"chunk1chunk2"
    # The .tmp sidecar must be gone after success.
    assert not (tmp_path / "out.bin.tmp").exists()


def test_http_download_keeps_existing_file_when_present(mocker, tmp_path):
    """Idempotency: if the destination exists, do nothing."""
    dest = tmp_path / "out.bin"
    dest.write_bytes(b"already here")
    get = mocker.patch("requests.get")

    result = http_download("https://example.com/x", dest)

    assert result == dest
    assert dest.read_bytes() == b"already here"
    get.assert_not_called()


def test_http_download_retries_on_transient_error(mocker, tmp_path):
    failing = MagicMock(side_effect=ConnectionError("boom"))
    ok_resp = MagicMock()
    ok_resp.iter_content = MagicMock(return_value=[b"ok"])
    ok_resp.headers = {}
    ok_resp.__enter__ = MagicMock(return_value=ok_resp)
    ok_resp.__exit__ = MagicMock(return_value=False)
    ok_resp.raise_for_status = MagicMock()
    # First call raises, second returns ok.
    mocker.patch("requests.get", side_effect=[ConnectionError("boom"), ok_resp])

    dest = tmp_path / "out.bin"
    http_download("https://example.com/x", dest, max_attempts=3)

    assert dest.read_bytes() == b"ok"
