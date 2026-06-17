from pathlib import Path
from unittest.mock import MagicMock

import pytest

from acquisition.gee import export_to_drive, initialize


def test_initialize_calls_authenticate_and_initialize(mocker):
    auth = mocker.patch("ee.Authenticate")
    init = mocker.patch("ee.Initialize")

    initialize(project="my-project")

    auth.assert_called_once()
    init.assert_called_once()
    kwargs = init.call_args.kwargs
    assert kwargs["project"] == "my-project"
    assert "earthengine-highvolume.googleapis.com" in kwargs["opt_url"]


def test_export_to_drive_polls_until_done_then_mirrors(mocker, tmp_path):
    task = MagicMock()
    # Two polls: RUNNING, then COMPLETED.
    task.status.side_effect = [
        {"state": "RUNNING"},
        {"state": "COMPLETED"},
    ]
    export_factory = mocker.patch(
        "ee.batch.Export.image.toDrive",
        return_value=task,
    )
    sleep = mocker.patch("time.sleep")
    run = mocker.patch(
        "subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    image = MagicMock()
    region = MagicMock()

    out = export_to_drive(
        image=image,
        description="test_export",
        drive_folder="Lithium_v2/gee_exports/mapbiomas",
        file_prefix="bofedal_stable",
        region=region,
        local_dest=tmp_path / "Data/external/mapbiomas/raw",
        scale=30,
        timeout_min=30,
    )

    # Export was submitted with our params.
    export_factory.assert_called_once()
    kwargs = export_factory.call_args.kwargs
    assert kwargs["image"] is image
    assert kwargs["description"] == "test_export"
    assert kwargs["folder"] == "Lithium_v2/gee_exports/mapbiomas"
    assert kwargs["fileNamePrefix"] == "bofedal_stable"
    assert kwargs["region"] is region
    assert kwargs["scale"] == 30
    task.start.assert_called_once()
    # Polled twice.
    assert task.status.call_count == 2
    # rclone copy was called.
    rclone_args = run.call_args[0][0]
    assert rclone_args[0] == "rclone"
    assert rclone_args[1] == "copy"
    assert "gdrive:Lithium_v2/gee_exports/mapbiomas" in rclone_args
    assert out == tmp_path / "Data/external/mapbiomas/raw"


def test_export_to_drive_raises_on_gee_failure(mocker, tmp_path):
    task = MagicMock()
    task.status.return_value = {"state": "FAILED", "error_message": "asset not found"}
    mocker.patch("ee.batch.Export.image.toDrive", return_value=task)
    mocker.patch("time.sleep")

    with pytest.raises(RuntimeError, match="asset not found"):
        export_to_drive(
            image=MagicMock(),
            description="test_export",
            drive_folder="Lithium_v2/gee_exports/test",
            file_prefix="bofedal_stable",
            region=MagicMock(),
            local_dest=tmp_path / "out",
        )


def test_export_to_drive_times_out(mocker, tmp_path):
    task = MagicMock()
    task.status.return_value = {"state": "RUNNING"}
    mocker.patch("ee.batch.Export.image.toDrive", return_value=task)
    mocker.patch("time.sleep")

    with pytest.raises(TimeoutError):
        export_to_drive(
            image=MagicMock(),
            description="test_export",
            drive_folder="Lithium_v2/gee_exports/test",
            file_prefix="bofedal_stable",
            region=MagicMock(),
            local_dest=tmp_path / "out",
            timeout_min=0,  # immediately past deadline
        )


def test_export_table_to_drive_submits_polls_mirrors(mocker, tmp_path):
    """Same lifecycle as export_to_drive but for ee.FeatureCollection -> CSV."""
    task = mocker.MagicMock()
    task.status.side_effect = [
        {"state": "RUNNING"},
        {"state": "COMPLETED"},
    ]
    export_factory = mocker.patch(
        "ee.batch.Export.table.toDrive",
        return_value=task,
    )
    mocker.patch("time.sleep")
    run = mocker.patch(
        "subprocess.run",
        return_value=mocker.MagicMock(returncode=0, stdout="", stderr=""),
    )

    from acquisition.gee import export_table_to_drive

    fake_table = mocker.MagicMock(name="ReducedTable")

    out = export_table_to_drive(
        table=fake_table,
        description="ndvi_gs_2020",
        drive_folder="Lithium_v2_gee_exports_panel_ndvi_gs",
        file_prefix="2020",
        local_dest=tmp_path / "panel/ndvi_gs",
        timeout_min=15,
    )

    export_factory.assert_called_once()
    kwargs = export_factory.call_args.kwargs
    assert kwargs["collection"] is fake_table
    assert kwargs["description"] == "ndvi_gs_2020"
    assert kwargs["folder"] == "Lithium_v2_gee_exports_panel_ndvi_gs"
    assert kwargs["fileNamePrefix"] == "2020"
    assert kwargs["fileFormat"] == "CSV"
    task.start.assert_called_once()
    assert task.status.call_count == 2
    rclone_args = run.call_args[0][0]
    assert rclone_args[0:2] == ["rclone", "copy"]
    assert "gdrive:Lithium_v2_gee_exports_panel_ndvi_gs" in rclone_args
    assert out == tmp_path / "panel/ndvi_gs"


def test_export_table_to_drive_raises_on_gee_failure(mocker, tmp_path):
    task = mocker.MagicMock()
    task.status.return_value = {"state": "FAILED", "error_message": "quota exceeded"}
    mocker.patch("ee.batch.Export.table.toDrive", return_value=task)
    mocker.patch("time.sleep")

    from acquisition.gee import export_table_to_drive

    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="quota exceeded"):
        export_table_to_drive(
            table=mocker.MagicMock(),
            description="ndvi_gs_2020",
            drive_folder="x",
            file_prefix="2020",
            local_dest=tmp_path / "out",
        )
