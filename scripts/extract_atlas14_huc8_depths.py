"""
Task 2C-3: Extract NOAA Atlas 14 rainfall depths per HUC8 via zonal statistics.

This script reads the local HUC8 watershed polygons and the official NOAA
Atlas 14 GIS grids (downloaded by scripts/download_or_register_atlas14_grids.py)
and computes a zonal statistic (mean, by default) of rainfall depth over each
FULL HUC8 polygon, for every return_period_year x duration_hour combination.

Important spatial definition (per project convention):
  - geometry_scope = full HUC8 polygon (NOT clipped to a state boundary)
  - selection_rule = intersects Alabama
  - state_clipped  = false
These are recorded verbatim in the output table so downstream users never
mistake this for Alabama-clipped statistics.

Method: GIS-grid-based full-HUC8 zonal statistics (project's preferred
method; see scripts/README_task2_atlas14_extraction.md for the comparison
against HUC8-centroid PFDS point estimates).

Usage:
  python scripts/extract_atlas14_huc8_depths.py
  python scripts/extract_atlas14_huc8_depths.py --statistic mean --include-ci
  python scripts/extract_atlas14_huc8_depths.py --huc-shapefile path/to/other.shp \\
      --atlas14-grid-dir data/raw/atlas14_other_state/extracted --output-dir data/processed/other_state
"""

import argparse
import glob
import os

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.mask

# --- Section: project defaults (documented, not hidden) ---
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
HUC_ID_FIELD = "HUC8"
HUC_NAME_FIELD = "NAME"

ATLAS14_GRID_DIR_DEFAULT = "data/raw/atlas14/extracted"
OUTPUT_DIR_DEFAULT = "data/processed/atlas14_depth_tables"
OUTPUT_FILENAME = "alabama_intersecting_full_huc8_atlas14_depths.csv"

RETURN_PERIODS_YEAR_DEFAULT = [5, 10, 50, 100, 200, 500]
DURATIONS_HOUR_DEFAULT = [6, 12, 24, 96]
DURATION_CODE_MAP = {6: "06h", 12: "12h", 24: "24h", 96: "04d"}
REGION_CODE_DEFAULT = "se"  # Southeastern States (Volume 9)
ATLAS14_VOLUME_DEFAULT = "9"

# NOAA Atlas 14 GIS grid values are stored as integers in 1000ths of an inch.
GRID_UNIT_SCALE = 1000.0
RAINFALL_DEPTH_UNIT = "in"

# Fixed spatial-scope labels for this project (see module docstring).
GEOMETRY_SCOPE_DEFAULT = "full HUC8 polygon"
SELECTION_RULE_DEFAULT = "intersects Alabama"
STATE_CLIPPED_DEFAULT = False

STATISTIC_FUNCS = {
    "mean": np.ma.mean,
    "median": np.ma.median,
    "min": np.ma.min,
    "max": np.ma.max,
}


def find_grid_file(grid_dir, region_code, return_period, duration_hour, bound_suffix):
    """Locate the extracted .asc grid file for one combination, or return None."""
    dur_code = DURATION_CODE_MAP[duration_hour]
    filename = f"{region_code}{return_period}yr{dur_code}{bound_suffix}.asc"
    path = os.path.join(grid_dir, filename)
    return path if os.path.exists(path) else None


def zonal_stat_for_polygon(dataset, geometry, stat_func):
    """Mask one raster to one polygon and compute the requested statistic."""
    out_image, _ = rasterio.mask.mask(dataset, [geometry], crop=True, all_touched=False)
    band = out_image[0]
    masked = np.ma.masked_equal(band, dataset.nodata)
    if masked.count() == 0:
        return None
    return float(stat_func(masked))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT,
                         help="Path to HUC polygon shapefile (default: %(default)s)")
    parser.add_argument("--huc-id-field", default=HUC_ID_FIELD)
    parser.add_argument("--huc-name-field", default=HUC_NAME_FIELD)
    parser.add_argument("--atlas14-grid-dir", default=ATLAS14_GRID_DIR_DEFAULT,
                         help="Directory of extracted .asc grids (default: %(default)s)")
    parser.add_argument("--region-code", default=REGION_CODE_DEFAULT)
    parser.add_argument("--atlas14-volume", default=ATLAS14_VOLUME_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--return-periods", type=int, nargs="+", default=RETURN_PERIODS_YEAR_DEFAULT)
    parser.add_argument("--durations", type=int, nargs="+", default=DURATIONS_HOUR_DEFAULT)
    parser.add_argument("--statistic", choices=list(STATISTIC_FUNCS), default="mean",
                         help="Zonal statistic to compute (default: %(default)s)")
    parser.add_argument("--geometry-scope", default=GEOMETRY_SCOPE_DEFAULT)
    parser.add_argument("--selection-rule", default=SELECTION_RULE_DEFAULT)
    parser.add_argument("--include-ci", action="store_true",
                         help="Also extract lower/upper 90%% CI grids if present (default: estimate only)")
    args = parser.parse_args()

    if not os.path.exists(args.huc_shapefile):
        raise FileNotFoundError(
            f"HUC shapefile not found: {args.huc_shapefile}. "
            "Check --huc-shapefile or confirm Task 1 boundary data is present."
        )
    if not os.path.isdir(args.atlas14_grid_dir):
        raise FileNotFoundError(
            f"Atlas 14 grid directory not found: {args.atlas14_grid_dir}. "
            "Run scripts/download_or_register_atlas14_grids.py first."
        )

    os.makedirs(args.output_dir, exist_ok=True)
    stat_func = STATISTIC_FUNCS[args.statistic]

    # --- Section: load HUC polygons (full polygons, not state-clipped) ---
    huc_gdf = gpd.read_file(args.huc_shapefile)
    grid_crs = "EPSG:4269"  # NAD83 geographic, confirmed from se_metadata.xml / .prj
    huc_gdf_grid_crs = huc_gdf.to_crs(grid_crs)

    bounds_to_extract = ["estimate"] + (["lower_90ci", "upper_90ci"] if args.include_ci else [])
    bound_suffix_map = {"estimate": "a", "lower_90ci": "al", "upper_90ci": "au"}

    rows = []
    missing_grids = []

    for duration_hour in args.durations:
        for return_period in args.return_periods:
            for bound in bounds_to_extract:
                suffix = bound_suffix_map[bound]
                grid_path = find_grid_file(
                    args.atlas14_grid_dir, args.region_code, return_period, duration_hour, suffix
                )
                atlas14_source_file = os.path.basename(grid_path) if grid_path else (
                    f"{args.region_code}{return_period}yr{DURATION_CODE_MAP[duration_hour]}{suffix}.asc"
                    " (not found)"
                )

                if grid_path is None:
                    missing_grids.append(atlas14_source_file)
                    # Record one pending row per HUC so downstream joins still work.
                    for _, huc in huc_gdf.iterrows():
                        rows.append(_pending_row(
                            huc, args, return_period, duration_hour, bound,
                            atlas14_source_file, grid_crs,
                            "pending: grid file not found locally",
                        ))
                    continue

                with rasterio.open(grid_path) as dataset:
                    for idx, huc in huc_gdf_grid_crs.iterrows():
                        huc_original = huc_gdf.loc[idx]
                        try:
                            value = zonal_stat_for_polygon(dataset, huc.geometry, stat_func)
                        except ValueError as e:
                            # Polygon does not overlap the raster extent at all.
                            rows.append(_pending_row(
                                huc_original, args, return_period, duration_hour, bound,
                                atlas14_source_file, grid_crs, f"pending: {e}",
                            ))
                            continue

                        if value is None:
                            rows.append(_pending_row(
                                huc_original, args, return_period, duration_hour, bound,
                                atlas14_source_file, grid_crs,
                                "pending: all pixels nodata in Volume 9 (se) grid - this HUC8 "
                                "likely falls outside the Volume 9 Southeastern States coverage "
                                "area (e.g. Tennessee River basin HUC8s may require Volume 2, "
                                "Ohio River Basin and Surrounding States, grids instead)",
                            ))
                            continue

                        rainfall_depth_in = value / GRID_UNIT_SCALE
                        rows.append({
                            "huc8_id": huc_original[args.huc_id_field],
                            "huc8_name": huc_original.get(args.huc_name_field, ""),
                            "geometry_scope": args.geometry_scope,
                            "selection_rule": args.selection_rule,
                            "state_clipped": STATE_CLIPPED_DEFAULT,
                            "return_period_year": return_period,
                            "duration_hour": duration_hour,
                            "rainfall_depth": round(rainfall_depth_in, 3),
                            "rainfall_depth_unit": RAINFALL_DEPTH_UNIT,
                            "rainfall_depth_statistic": args.statistic,
                            "confidence_bound": bound,
                            "atlas14_volume": args.atlas14_volume,
                            "atlas14_source_file": atlas14_source_file,
                            "extraction_method": "GIS grid zonal statistics (full HUC8 polygon)",
                            "crs_polygon": str(huc_gdf.crs),
                            "crs_grid": grid_crs,
                            "status": "extracted",
                            "notes": "",
                        })

    fieldnames = [
        "huc8_id", "huc8_name", "geometry_scope", "selection_rule", "state_clipped",
        "return_period_year", "duration_hour", "rainfall_depth", "rainfall_depth_unit",
        "rainfall_depth_statistic", "confidence_bound", "atlas14_volume",
        "atlas14_source_file", "extraction_method", "crs_polygon", "crs_grid",
        "status", "notes",
    ]

    import csv
    output_path = os.path.join(args.output_dir, OUTPUT_FILENAME)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")
    if missing_grids:
        print(f"WARNING: {len(missing_grids)} grid file(s) were missing and produced pending rows:")
        for g in sorted(set(missing_grids)):
            print(f"  - {g}")


def _pending_row(huc, args, return_period, duration_hour, bound, atlas14_source_file, grid_crs, note):
    """Build a row with rainfall_depth left unset when extraction could not be completed."""
    return {
        "huc8_id": huc[args.huc_id_field],
        "huc8_name": huc.get(args.huc_name_field, ""),
        "geometry_scope": args.geometry_scope,
        "selection_rule": args.selection_rule,
        "state_clipped": STATE_CLIPPED_DEFAULT,
        "return_period_year": return_period,
        "duration_hour": duration_hour,
        "rainfall_depth": "TBD",
        "rainfall_depth_unit": RAINFALL_DEPTH_UNIT,
        "rainfall_depth_statistic": args.statistic,
        "confidence_bound": bound,
        "atlas14_volume": args.atlas14_volume,
        "atlas14_source_file": atlas14_source_file,
        "extraction_method": "GIS grid zonal statistics (full HUC8 polygon)",
        "crs_polygon": "",
        "crs_grid": grid_crs,
        "status": "pending_atlas14_grid_download",
        "notes": note,
    }


if __name__ == "__main__":
    main()
