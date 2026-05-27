import xarray as xr

from acquisition.aoi import PUNA_BBOX
from acquisition.datasets.spei import SpeiDataset


def test_spei_clip_writes_puna_subset_netcdf(tiny_netcdf, tmp_path):
    ds = SpeiDataset(url="https://example.com/spei.nc")
    out = ds.clip(tiny_netcdf, tmp_path, PUNA_BBOX)

    assert out == tmp_path / "puna" / "spei_puna.nc"
    assert out.exists()

    clipped = xr.open_dataset(out)
    try:
        assert clipped["lon"].min() >= PUNA_BBOX.west
        assert clipped["lon"].max() <= PUNA_BBOX.east
        assert clipped["lat"].min() >= PUNA_BBOX.south
        assert clipped["lat"].max() <= PUNA_BBOX.north
        assert "spei" in clipped.data_vars
        assert clipped["spei"].sizes["time"] == 12
    finally:
        clipped.close()


def test_spei_clip_idempotent(tiny_netcdf, tmp_path):
    ds = SpeiDataset(url="https://example.com/spei.nc")
    out1 = ds.clip(tiny_netcdf, tmp_path, PUNA_BBOX)
    mtime1 = out1.stat().st_mtime_ns
    out2 = ds.clip(tiny_netcdf, tmp_path, PUNA_BBOX)
    assert out2 == out1
    assert out2.stat().st_mtime_ns == mtime1
