"""CLI driver for Stage 3 panel build."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd

from panel import compose as compose_module
from panel import ndvi as ndvi_module
from panel import s1 as s1_module
from panel import spei as spei_module
from panel import static_attrs as static_module


_S1_AVAILABLE_FROM = 2014


def _load_usgs_salars(*, external_root: Path) -> gpd.GeoDataFrame:
    """Unpack the USGS gdb if needed, then load the salars layer."""
    archive = external_root / "usgs" / "raw" / "usgs.gdb.7z"
    target = external_root / "usgs" / "extracted"
    static_module.unpack_usgs_archive(archive=archive, target_dir=target)
    gdb_candidates = list(target.rglob("*.gdb"))
    if not gdb_candidates:
        raise FileNotFoundError(
            f"No .gdb directory found under {target}. Check the archive structure."
        )
    gdb = gdb_candidates[0]
    import pyogrio
    layer_info = pyogrio.list_layers(str(gdb))
    layer_names = [name for name, _ in layer_info]
    salar_layer = next(
        (name for name in layer_names if "salar" in name.lower()),
        None,
    )
    if salar_layer is None:
        raise RuntimeError(
            f"No salar layer in {gdb}. Available: {layer_names}"
        )
    return gpd.read_file(str(gdb), layer=salar_layer)


def _load_elevation_csv(*, external_root: Path) -> pd.DataFrame:
    """Read the SRTM mean CSV produced by panel.static_attrs.extract_elevation."""
    csv = external_root / "panel" / "elevation" / "elevation.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"Elevation CSV not found at {csv}. Run `--extract elevation` first."
        )
    return pd.read_csv(csv)


def run_extract(
    *,
    bofedales_path: Path,
    outcomes: set[str],
    years: Iterable[int],
    external_root: Path,
) -> None:
    """Submit GEE exports for the listed outcomes across the year range."""
    bofedales = gpd.read_file(bofedales_path)
    panel_root = external_root / "panel"
    years_list = sorted({int(y) for y in years})

    if "ndvi" in outcomes:
        for y in years_list:
            for window, suffix in (("growing_season", "gs"), ("annual", "annual")):
                ndvi_module.extract_year(
                    year=y,
                    bofedales=bofedales,
                    window=window,
                    local_dest=panel_root / f"ndvi_{suffix}",
                )

    if "s1" in outcomes:
        for y in years_list:
            if y < _S1_AVAILABLE_FROM:
                continue
            for pol in ("VV", "VH"):
                s1_module.extract_year(
                    year=y,
                    bofedales=bofedales,
                    polarization=pol,
                    local_dest=panel_root / f"s1_{pol.lower()}",
                )

    if "elevation" in outcomes:
        static_module.extract_elevation(
            bofedales=bofedales,
            local_dest=panel_root / "elevation",
        )


def run_compose(
    *,
    bofedales_path: Path,
    years: Iterable[int],
    external_root: Path,
    repo_root: Path,
) -> None:
    """Run local extracts + merge intermediates into the parquet."""
    bofedales = gpd.read_file(bofedales_path)
    panel_root = external_root / "panel"
    years_list = sorted({int(y) for y in years})

    spei12_df = spei_module.extract(
        nc_path=external_root / "spei12" / "raw" / "spei12.nc",
        bofedales=bofedales,
        years=years_list,
        column="spei_12_gs_mean",
    )
    spei24_df = spei_module.extract(
        nc_path=external_root / "spei24" / "raw" / "spei24.nc",
        bofedales=bofedales,
        years=years_list,
        column="spei_24_gs_mean",
    )

    salars = _load_usgs_salars(external_root=external_root)
    salar_df = static_module.extract_containing_salar_from_layer(
        bofedales=bofedales, salars=salars,
    )

    elevation_df = _load_elevation_csv(external_root=external_root)

    out_path = repo_root / "Data" / "bofedal_panel.parquet"
    compose_module.compose_panel(
        bofedales_path=bofedales_path,
        years=years_list,
        ndvi_gs_dir=panel_root / "ndvi_gs",
        ndvi_annual_dir=panel_root / "ndvi_annual",
        s1_vv_dir=panel_root / "s1_vv",
        s1_vh_dir=panel_root / "s1_vh",
        spei12_df=spei12_df,
        spei24_df=spei24_df,
        elevation_df=elevation_df,
        containing_salar_df=salar_df,
        out_path=out_path,
    )
    print(f"wrote {out_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="panel.run")
    parser.add_argument(
        "--bofedales",
        type=Path,
        default=Path("Data/bofedales_v2.geojson"),
    )
    parser.add_argument(
        "--external-root",
        type=Path,
        default=Path("Data/external"),
    )
    parser.add_argument(
        "--extract",
        help="Comma-separated list of outcomes to extract (ndvi, s1, elevation). "
             "If omitted, runs ndvi,s1,elevation by default.",
    )
    parser.add_argument(
        "--compose",
        action="store_true",
        help="Merge intermediates into Data/bofedal_panel.parquet.",
    )
    parser.add_argument(
        "--years",
        default="1998:2024",
        help="Year range like 1998:2024 (end inclusive).",
    )
    args = parser.parse_args(argv)

    start_str, end_str = args.years.split(":")
    years = range(int(start_str), int(end_str) + 1)

    if args.extract is None and not args.compose:
        outcomes = {"ndvi", "s1", "elevation"}
        run_extract(
            bofedales_path=args.bofedales,
            outcomes=outcomes,
            years=years,
            external_root=args.external_root,
        )
        run_compose(
            bofedales_path=args.bofedales,
            years=years,
            external_root=args.external_root,
            repo_root=Path.cwd(),
        )
        return 0

    if args.extract:
        outcomes = {o.strip() for o in args.extract.split(",")}
        run_extract(
            bofedales_path=args.bofedales,
            outcomes=outcomes,
            years=years,
            external_root=args.external_root,
        )

    if args.compose:
        run_compose(
            bofedales_path=args.bofedales,
            years=years,
            external_root=args.external_root,
            repo_root=Path.cwd(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
