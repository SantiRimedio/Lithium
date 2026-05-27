from pathlib import Path
from unittest.mock import MagicMock

import pytest

from acquisition.drive import DriveError, DriveRemote


def test_push_calls_rclone_copy(mocker, tmp_path):
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr=""))
    remote = DriveRemote(remote_name="gdrive", root="Lithium_v2/external")

    local = tmp_path / "spei.nc"
    local.write_text("x")
    remote.push(local, "spei/raw/spei.nc")

    run.assert_called_once()
    args = run.call_args[0][0]
    assert args[0] == "rclone"
    assert args[1] == "copyto"
    assert str(local) in args
    assert "gdrive:Lithium_v2/external/spei/raw/spei.nc" in args


def test_pull_calls_rclone_copyto(mocker, tmp_path):
    run = mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr=""))
    remote = DriveRemote(remote_name="gdrive", root="Lithium_v2/external")

    dst = tmp_path / "spei.nc"
    remote.pull("spei/raw/spei.nc", dst)

    args = run.call_args[0][0]
    assert args[0:2] == ["rclone", "copyto"]
    assert "gdrive:Lithium_v2/external/spei/raw/spei.nc" in args
    assert str(dst) in args


def test_exists_returns_true_when_lsf_finds_file(mocker):
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="spei.nc\n", stderr=""))
    remote = DriveRemote(remote_name="gdrive", root="Lithium_v2/external")
    assert remote.exists("spei/raw/spei.nc") is True


def test_exists_returns_false_when_lsf_empty(mocker):
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr=""))
    remote = DriveRemote(remote_name="gdrive", root="Lithium_v2/external")
    assert remote.exists("spei/raw/missing.nc") is False


def test_nonzero_exit_raises_drive_error(mocker, tmp_path):
    mocker.patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="auth failed"))
    remote = DriveRemote(remote_name="gdrive", root="Lithium_v2/external")
    f = tmp_path / "x"
    f.write_text("x")
    with pytest.raises(DriveError, match="auth failed"):
        remote.push(f, "x")
