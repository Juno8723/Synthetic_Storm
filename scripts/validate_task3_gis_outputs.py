"""
Task 3I: Validate Task 3 GIS outputs.

Checks the GeoPackage produced by scripts/assign_huc8_temporal_regions.py
(Task 3B) and scripts/export_task3_gis_layers.py (Task 3F): layer presence,
expected feature counts, geometry validity, CRS, populated fields, and that
HUC8 geometry is still the full (not Alabama-clipped) polygon set. Also
confirms the shapefile field-name mapping used for the shapefile exports is
documented.

Outputs:
  data/metadata/task3_gis_validation_report.txt
  data/metadata/task3_gis_validation_summary.csv

Usage:
  python scripts/validate_task3_gis_outputs.py
"""

import argparse
import csv
import os
import sys

import geopandas as gpd

# --- Section: project defaults (documented, not hidden) ---
GPKG_PATH_DEFAULT = "data/processed/gis/task3_hyetograph_summary.gpkg"
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
README_GIS_DEFAULT = "data/processed/gis/README_task3_gis_outputs.md"

REPORT_PATH_DEFAULT = "data/metadata/task3_gis_validation_report.txt"
SUMMARY_CSV_PATH_DEFAULT = "data/metadata/task3_gis_validation_summary.csv"

REQUIRED_LAYERS = [
    "huc8_temporal_distribution_assignment",
    "hyetograph_summary_all",
    "hyeto_100yr_24hr_early_peak",
    "hyeto_100yr_24hr_middle_peak",
    "hyeto_100yr_24hr_late_peak",
    "hyeto_100yr_24hr_balanced",
    "hyeto_100yr_6hr_middle_peak",
    "hyeto_100yr_12hr_middle_peak",
    "hyeto_100yr_96hr_balanced",
    "hyeto_500yr_24hr_middle_peak",
]
REPRESENTATIVE_LAYERS = [l for l in REQUIRED_LAYERS if l not in ("huc8_temporal_distribution_assignment", "hyetograph_summary_all")]
EXPECTED_TOTAL_SCENARIO_FEATURES = 5664


class Check:
    def __init__(self, name):
        self.name = name
        self.n_checked = 0
        self.n_passed = 0
        self.failures = []

    def record(self, checked, passed, detail=None):
        self.n_checked += checked
        self.n_passed += passed
        if detail:
            self.failures.append(detail)

    @property
    def status(self):
        return "PASS" if self.n_passed == self.n_checked else "FAIL"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpkg", default=GPKG_PATH_DEFAULT)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--gis-readme", default=README_GIS_DEFAULT)
    parser.add_argument("--report", default=REPORT_PATH_DEFAULT)
    parser.add_argument("--summary-csv", default=SUMMARY_CSV_PATH_DEFAULT)
    args = parser.parse_args()

    checks = []

    def new_check(name):
        c = Check(name)
        checks.append(c)
        return c

    c = new_check("gpkg_exists")
    gpkg_exists = os.path.exists(args.gpkg)
    c.record(1, 1 if gpkg_exists else 0, None if gpkg_exists else f"{args.gpkg} not found")
    if not gpkg_exists:
        _finish(checks, args)
        sys.exit(2)

    available_layers = set(gpd.list_layers(args.gpkg)["name"])
    c = new_check("required_layers_exist")
    missing_layers = [l for l in REQUIRED_LAYERS if l not in available_layers]
    c.record(len(REQUIRED_LAYERS), len(REQUIRED_LAYERS) - len(missing_layers),
              f"missing layers: {missing_layers}" if missing_layers else None)

    layers = {name: gpd.read_file(args.gpkg, layer=name) for name in REQUIRED_LAYERS if name in available_layers}

    c = new_check("huc8_temporal_distribution_assignment_has_59_features")
    if "huc8_temporal_distribution_assignment" in layers:
        n = len(layers["huc8_temporal_distribution_assignment"])
        c.record(1, 1 if n == 59 else 0, None if n == 59 else f"got {n}")
    else:
        c.record(1, 0, "layer missing")

    c = new_check("representative_layers_have_59_features_each")
    for layer_name in REPRESENTATIVE_LAYERS:
        if layer_name not in layers:
            c.record(1, 0, f"{layer_name}: layer missing")
            continue
        n = len(layers[layer_name])
        c.record(1, 1 if n == 59 else 0, None if n == 59 else f"{layer_name}: got {n}, expected 59")

    c = new_check("hyetograph_summary_all_has_expected_feature_count")
    if "hyetograph_summary_all" in layers:
        n = len(layers["hyetograph_summary_all"])
        c.record(1, 1 if n == EXPECTED_TOTAL_SCENARIO_FEATURES else 0,
                  None if n == EXPECTED_TOTAL_SCENARIO_FEATURES else f"got {n}, expected {EXPECTED_TOTAL_SCENARIO_FEATURES}")
    else:
        c.record(1, 0, "layer missing")

    c = new_check("geometry_valid_and_non_empty")
    for layer_name, gdf in layers.items():
        invalid = (~gdf.geometry.is_valid).sum()
        empty = gdf.geometry.is_empty.sum()
        null_geom = gdf.geometry.isna().sum()
        ok = invalid == 0 and empty == 0 and null_geom == 0
        c.record(1, 1 if ok else 0, None if ok else f"{layer_name}: invalid={invalid}, empty={empty}, null={null_geom}")

    c = new_check("crs_documented")
    for layer_name, gdf in layers.items():
        ok = gdf.crs is not None
        c.record(1, 1 if ok else 0, None if ok else f"{layer_name}: no CRS set")

    c = new_check("huc8_id_populated")
    for layer_name, gdf in layers.items():
        if "huc8_id" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: no huc8_id column")
            continue
        missing = gdf["huc8_id"].isna().sum()
        c.record(1, 1 if missing == 0 else 0, None if missing == 0 else f"{layer_name}: {missing} missing huc8_id")

    c = new_check("rainfall_depth_populated_in_scenario_layers")
    for layer_name in REPRESENTATIVE_LAYERS + ["hyetograph_summary_all"]:
        if layer_name not in layers:
            continue
        gdf = layers[layer_name]
        if "rainfall_depth" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: no rainfall_depth column")
            continue
        missing = gdf["rainfall_depth"].isna().sum()
        c.record(1, 1 if missing == 0 else 0, None if missing == 0 else f"{layer_name}: {missing} missing rainfall_depth")

    c = new_check("max_incremental_rainfall_populated_where_resolved")
    for layer_name in REPRESENTATIVE_LAYERS + ["hyetograph_summary_all"]:
        if layer_name not in layers:
            continue
        gdf = layers[layer_name]
        if "max_incremental_rainfall" not in gdf.columns or "status" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: missing required columns")
            continue
        resolved = gdf[gdf["status"] == "atlas14_hyetograph_generated"]
        missing = resolved["max_incremental_rainfall"].isna().sum()
        c.record(1, 1 if missing == 0 else 0,
                  None if missing == 0 else f"{layer_name}: {missing} resolved features missing max_incremental_rainfall")

    c = new_check("time_of_max_incremental_rainfall_populated_where_resolved")
    for layer_name in REPRESENTATIVE_LAYERS + ["hyetograph_summary_all"]:
        if layer_name not in layers:
            continue
        gdf = layers[layer_name]
        if "time_of_max_incremental_rainfall" not in gdf.columns or "status" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: missing required columns")
            continue
        resolved = gdf[gdf["status"] == "atlas14_hyetograph_generated"]
        missing = resolved["time_of_max_incremental_rainfall"].isna().sum()
        c.record(1, 1 if missing == 0 else 0,
                  None if missing == 0 else f"{layer_name}: {missing} resolved features missing time_of_max_incremental_rainfall")

    c = new_check("temporal_distribution_area_populated")
    for layer_name, gdf in layers.items():
        if "temporal_distribution_area" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: no temporal_distribution_area column")
            continue
        missing = gdf["temporal_distribution_area"].isna().sum()
        c.record(1, 1 if missing == 0 else 0, None if missing == 0 else f"{layer_name}: {missing} missing")

    c = new_check("status_populated")
    for layer_name, gdf in layers.items():
        if "status" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: no status column")
            continue
        missing = gdf["status"].isna().sum()
        c.record(1, 1 if missing == 0 else 0, None if missing == 0 else f"{layer_name}: {missing} missing status")

    # --- HUC8 geometries remain full polygons, not Alabama-clipped: compare total area to source shapefile ---
    c = new_check("huc8_geometry_matches_full_source_shapefile_not_clipped")
    if os.path.exists(args.huc_shapefile) and "huc8_temporal_distribution_assignment" in layers:
        source_gdf = gpd.read_file(args.huc_shapefile)
        source_area_total = source_gdf.to_crs("EPSG:5070").geometry.area.sum()
        gis_gdf = layers["huc8_temporal_distribution_assignment"].to_crs("EPSG:5070")
        gis_area_total = gis_gdf.geometry.area.sum()
        ratio = gis_area_total / source_area_total if source_area_total else 0
        ok = 0.999 <= ratio <= 1.001
        c.record(1, 1 if ok else 0, None if ok else f"area ratio={ratio:.5f} (expected ~1.0, i.e. full polygons, not clipped)")
    else:
        c.record(1, 0, "could not compare: source shapefile or layer missing")

    c = new_check("shapefile_field_name_mapping_documented")
    ok = os.path.exists(args.gis_readme)
    if ok:
        with open(args.gis_readme) as f:
            text = f.read()
        ok = "field" in text.lower() and ("mapping" in text.lower() or "shapefile" in text.lower())
    c.record(1, 1 if ok else 0, None if ok else f"{args.gis_readme} missing or lacks field-name mapping documentation")

    _finish(checks, args)


def _finish(checks, args):
    lines = ["Task 3 GIS Validation Report", "=" * 40, ""]
    any_fail = False
    for c in checks:
        line = f"[{c.status}] {c.name}: {c.n_passed}/{c.n_checked}"
        lines.append(line)
        print(line)
        if c.status == "FAIL":
            any_fail = True
            for f in c.failures[:20]:
                lines.append(f"    - {f}")
                print(f"    - {f}")

    lines.append("")
    lines.append(
        "Known, expected condition: hyeto_100yr_24hr_middle_peak, hyeto_100yr_6hr_middle_peak, "
        "hyeto_100yr_12hr_middle_peak, and hyeto_500yr_24hr_middle_peak have all 59 features at "
        "status=pending_temporal_mapping_review (max_incremental_rainfall / "
        "time_of_max_incremental_rainfall are null there by design, not a validation failure "
        "for those specific fields on those layers)."
    )
    lines.append("ALL CHECKS PASSED" if not any_fail else "SOME CHECKS FAILED - see details above")

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nWrote report to {args.report}")

    with open(args.summary_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["check_name", "n_checked", "n_passed", "n_failed", "status"])
        writer.writeheader()
        for c in checks:
            writer.writerow({
                "check_name": c.name, "n_checked": c.n_checked, "n_passed": c.n_passed,
                "n_failed": c.n_checked - c.n_passed, "status": c.status,
            })
    print(f"Wrote {len(checks)} rows to {args.summary_csv}")


if __name__ == "__main__":
    main()
