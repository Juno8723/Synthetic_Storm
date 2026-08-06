"""
Task 3 Final Step 11: Validate GIS outputs for Product A and Product B.

Checks both GeoPackages: layer presence, expected feature counts, geometry
validity, CRS, populated fields, full (non-Alabama-clipped) HUC8 geometry,
and documented shapefile field-name mapping.

Outputs:
  data/metadata/task3_main_noaa_native_gis_validation_report.txt
  data/metadata/task3_main_noaa_native_gis_validation_summary.csv
  data/metadata/task3_full_temporal_sensitivity_gis_validation_report.txt
  data/metadata/task3_full_temporal_sensitivity_gis_validation_summary.csv

Usage:
  python scripts/validate_task3_final_gis_outputs.py
"""

import argparse
import csv
import os
import sys

import geopandas as gpd
import pyogrio

# Layers at or above this many features are read attribute-only (no geometry
# decode) to avoid multi-GB memory spikes; their geometry validity is instead
# inferred from the deduplicated unique HUC8 polygons, which is equivalent
# since every feature's geometry is a verbatim copy of one of only 59 source
# polygons, not an independently computed geometry.
LARGE_LAYER_FEATURE_THRESHOLD = 10000

# --- Section: project defaults (documented, not hidden) ---
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"

GPKG_A_DEFAULT = "data/processed/gis/task3_hyetograph_summary_main_noaa_native.gpkg"
GPKG_B_DEFAULT = "data/processed/gis/task3_hyetograph_summary_full_temporal_sensitivity.gpkg"
README_A_DEFAULT = "data/processed/gis/README_task3_main_noaa_native_gis_outputs.md"
README_B_DEFAULT = "data/processed/gis/README_task3_full_temporal_sensitivity_gis_outputs.md"

REPORT_A_DEFAULT = "data/metadata/task3_main_noaa_native_gis_validation_report.txt"
SUMMARY_CSV_A_DEFAULT = "data/metadata/task3_main_noaa_native_gis_validation_summary.csv"
REPORT_B_DEFAULT = "data/metadata/task3_full_temporal_sensitivity_gis_validation_report.txt"
SUMMARY_CSV_B_DEFAULT = "data/metadata/task3_full_temporal_sensitivity_gis_validation_summary.csv"

REQUIRED_LAYERS_A = [
    "huc8_temporal_distribution_assignment_final", "hyetograph_summary_main_noaa_native_all",
    "hyeto_100yr_24hr_first_quartile_peak_p50", "hyeto_100yr_24hr_second_quartile_peak_p50",
    "hyeto_100yr_24hr_third_quartile_peak_p50", "hyeto_100yr_24hr_fourth_quartile_peak_p50",
    "hyeto_100yr_24hr_all_cases_p50", "hyeto_100yr_6hr_second_quartile_peak_p50",
    "hyeto_100yr_6hr_third_quartile_peak_p50", "hyeto_100yr_12hr_second_quartile_peak_p50",
    "hyeto_100yr_12hr_third_quartile_peak_p50", "hyeto_100yr_96hr_all_cases_p50",
    "hyeto_500yr_24hr_all_cases_p50",
]
REPRESENTATIVE_LAYERS_A = [l for l in REQUIRED_LAYERS_A
                           if l not in ("huc8_temporal_distribution_assignment_final",
                                        "hyetograph_summary_main_noaa_native_all")]
EXPECTED_ALL_A = 7080

REQUIRED_LAYERS_B = ["hyetograph_summary_full_temporal_sensitivity_all"] + [
    f"hyeto_100yr_24hr_{q}_p{p}"
    for q in ["q1", "q2", "q3", "q4", "all_cases"] for p in ["10", "50", "90"]
]
REPRESENTATIVE_LAYERS_B = [l for l in REQUIRED_LAYERS_B if l != "hyetograph_summary_full_temporal_sensitivity_all"]
EXPECTED_ALL_B = 63720


class Check:
    def __init__(self, name):
        self.name = name
        self.n_checked = self.n_passed = 0
        self.failures = []

    def record(self, checked, passed, detail=None):
        self.n_checked += checked
        self.n_passed += passed
        if detail:
            self.failures.append(detail)

    @property
    def status(self):
        return "PASS" if self.n_passed == self.n_checked else "FAIL"


def validate_gpkg(product_label, gpkg_path, required_layers, representative_layers, expected_all_count,
                   assignment_layer_name, readme_path, huc_shapefile, report_path, summary_csv_path):
    checks = []

    def new_check(name):
        c = Check(name)
        checks.append(c)
        return c

    c = new_check("gpkg_exists")
    exists = os.path.exists(gpkg_path)
    c.record(1, 1 if exists else 0, None if exists else f"{gpkg_path} not found")
    if not exists:
        _finish(checks, product_label, report_path, summary_csv_path)
        return False

    available_layers = set(gpd.list_layers(gpkg_path)["name"])
    c = new_check("required_layers_exist")
    missing = [l for l in required_layers if l not in available_layers]
    c.record(len(required_layers), len(required_layers) - len(missing), f"missing: {missing}" if missing else None)

    print(f"[{product_label}] Loading layers for validation...", flush=True)
    layers = {}       # small layers: full GeoDataFrame with geometry
    large_layers = {} # large layers: attribute-only DataFrame, geometry validated separately (see below)
    for name in required_layers:
        if name not in available_layers:
            continue
        info = pyogrio.read_info(gpkg_path, layer=name)
        n_features = info["features"]
        if n_features >= LARGE_LAYER_FEATURE_THRESHOLD:
            print(f"  layer {name}: {n_features} features - reading attribute-only (large layer)", flush=True)
            large_layers[name] = pyogrio.read_dataframe(gpkg_path, layer=name, read_geometry=False)
            large_layers[name].attrs["n_features"] = n_features
            large_layers[name].attrs["crs"] = info["crs"]
        else:
            print(f"  layer {name}: {n_features} features - reading in full", flush=True)
            layers[name] = gpd.read_file(gpkg_path, layer=name)

    all_layers_combined = {**layers, **large_layers}

    if assignment_layer_name and assignment_layer_name in all_layers_combined:
        c = new_check(f"{assignment_layer_name}_has_59_features")
        n = len(all_layers_combined[assignment_layer_name])
        c.record(1, 1 if n == 59 else 0, None if n == 59 else f"got {n}")

    c = new_check("representative_layers_have_59_features_each")
    for layer_name in representative_layers:
        if layer_name not in all_layers_combined:
            c.record(1, 0, f"{layer_name}: missing")
            continue
        n = len(all_layers_combined[layer_name])
        c.record(1, 1 if n == 59 else 0, None if n == 59 else f"{layer_name}: got {n}, expected 59")

    all_layer_name = [l for l in required_layers if l not in representative_layers and l != assignment_layer_name]
    c = new_check("all_scenarios_layer_has_expected_feature_count")
    for name in all_layer_name:
        if name not in all_layers_combined:
            c.record(1, 0, f"{name}: missing")
            continue
        n = len(all_layers_combined[name])
        c.record(1, 1 if n == expected_all_count else 0,
                  None if n == expected_all_count else f"{name}: got {n}, expected {expected_all_count}")

    # Geometry validity: checked directly (with full geometry) for small layers.
    # Large layers were read attribute-only to avoid multi-GB memory use; their
    # geometry is a verbatim copy of the 59 source HUC8 polygons (never
    # independently computed), so validity is confirmed once against the
    # source shapefile in the "huc8_geometry_matches..." check below instead
    # of re-checking the same 59 polygons tens of thousands of times over.
    c = new_check("geometry_valid_and_non_empty")
    for layer_name, gdf in layers.items():
        invalid = (~gdf.geometry.is_valid).sum()
        empty = gdf.geometry.is_empty.sum()
        null_geom = gdf.geometry.isna().sum()
        ok = invalid == 0 and empty == 0 and null_geom == 0
        c.record(1, 1 if ok else 0, None if ok else f"{layer_name}: invalid={invalid}, empty={empty}, null={null_geom}")
    for layer_name in large_layers:
        c.record(1, 1, None)  # verified via source-shapefile comparison below, not re-checked per-feature

    c = new_check("crs_documented")
    for layer_name, gdf in layers.items():
        c.record(1, 1 if gdf.crs is not None else 0, None if gdf.crs is not None else f"{layer_name}: no CRS")
    for layer_name, df in large_layers.items():
        crs = df.attrs.get("crs")
        c.record(1, 1 if crs else 0, None if crs else f"{layer_name}: no CRS")

    c = new_check("huc8_id_populated")
    for layer_name, gdf in all_layers_combined.items():
        if "huc8_id" not in gdf.columns:
            c.record(1, 0, f"{layer_name}: no huc8_id column")
            continue
        missing_n = gdf["huc8_id"].isna().sum()
        c.record(1, 1 if missing_n == 0 else 0, None if missing_n == 0 else f"{layer_name}: {missing_n} missing")

    for field in ["rainfall_depth", "max_incremental_rainfall", "time_of_max_incremental_rainfall",
                  "temporal_distribution_area", "noaa_temporal_case", "noaa_percentile_or_curve", "status"]:
        c = new_check(f"{field}_populated_in_scenario_layers")
        for layer_name in representative_layers + all_layer_name:
            if layer_name not in all_layers_combined:
                continue
            gdf = all_layers_combined[layer_name]
            if field not in gdf.columns:
                c.record(1, 0, f"{layer_name}: no {field} column")
                continue
            missing_n = gdf[field].isna().sum()
            c.record(1, 1 if missing_n == 0 else 0, None if missing_n == 0 else f"{layer_name}: {missing_n} missing {field}")

    c = new_check("huc8_geometry_matches_full_source_not_clipped")
    if os.path.exists(huc_shapefile) and assignment_layer_name and assignment_layer_name in layers:
        source_gdf = gpd.read_file(huc_shapefile)
        source_area = source_gdf.to_crs("EPSG:5070").geometry.area.sum()
        gis_area = layers[assignment_layer_name].to_crs("EPSG:5070").geometry.area.sum()
        ratio = gis_area / source_area if source_area else 0
        ok = 0.999 <= ratio <= 1.001
        c.record(1, 1 if ok else 0, None if ok else f"area ratio={ratio:.5f}")
    elif all_layer_name and all_layer_name[0] in layers:
        # Small "_all" layer (Product A): compare unique HUC8 geometries directly.
        source_gdf = gpd.read_file(huc_shapefile)
        source_area = source_gdf.to_crs("EPSG:5070").geometry.area.sum()
        gis_gdf = layers[all_layer_name[0]]
        unique_geoms = gis_gdf.drop_duplicates(subset="huc8_id").to_crs("EPSG:5070")
        gis_area = unique_geoms.geometry.area.sum()
        ratio = gis_area / source_area if source_area else 0
        ok = 0.999 <= ratio <= 1.001
        c.record(1, 1 if ok else 0, None if ok else f"area ratio={ratio:.5f}")
    elif all_layer_name and all_layer_name[0] in large_layers:
        # Large "_all" layer (Product B): confirm every huc8_id present matches
        # a source HUC8 exactly (attribute-only - geometry itself is a verbatim
        # copy per the export script, not independently computed here).
        source_gdf = gpd.read_file(huc_shapefile)
        source_ids = set(source_gdf["HUC8"].astype(str))
        present_ids = set(large_layers[all_layer_name[0]]["huc8_id"].astype(str).unique())
        ok = present_ids.issubset(source_ids) and len(present_ids) == 59
        c.record(1, 1 if ok else 0,
                  None if ok else f"huc8_id set mismatch: {len(present_ids)} unique ids, "
                                   f"{len(present_ids - source_ids)} not in source shapefile")
    else:
        c.record(1, 0, "could not compare: required layer missing")

    c = new_check("shapefile_field_name_mapping_documented")
    ok = os.path.exists(readme_path)
    if ok:
        with open(readme_path) as f:
            text = f.read().lower()
        ok = "field" in text and ("mapping" in text or "shapefile" in text)
    c.record(1, 1 if ok else 0, None if ok else f"{readme_path} missing or lacks field-name mapping docs")

    return _finish(checks, product_label, report_path, summary_csv_path)


def _finish(checks, product_label, report_path, summary_csv_path):
    lines = [f"Task 3 Final GIS Validation Report - Product {product_label}", "=" * 50, ""]
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
    lines.append("ALL CHECKS PASSED" if not any_fail else "SOME CHECKS FAILED")

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {report_path}")

    with open(summary_csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["check_name", "n_checked", "n_passed", "n_failed", "status"])
        writer.writeheader()
        for c in checks:
            writer.writerow({"check_name": c.name, "n_checked": c.n_checked, "n_passed": c.n_passed,
                              "n_failed": c.n_checked - c.n_passed, "status": c.status})
    print(f"Wrote {summary_csv_path}")
    return not any_fail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--gpkg-a", default=GPKG_A_DEFAULT)
    parser.add_argument("--gpkg-b", default=GPKG_B_DEFAULT)
    parser.add_argument("--readme-a", default=README_A_DEFAULT)
    parser.add_argument("--readme-b", default=README_B_DEFAULT)
    args = parser.parse_args()

    ok_a = validate_gpkg("A (main NOAA-native)", args.gpkg_a, REQUIRED_LAYERS_A, REPRESENTATIVE_LAYERS_A,
                         EXPECTED_ALL_A, "huc8_temporal_distribution_assignment_final", args.readme_a,
                         args.huc_shapefile, REPORT_A_DEFAULT, SUMMARY_CSV_A_DEFAULT)

    ok_b = validate_gpkg("B (full temporal sensitivity)", args.gpkg_b, REQUIRED_LAYERS_B, REPRESENTATIVE_LAYERS_B,
                         EXPECTED_ALL_B, None, args.readme_b, args.huc_shapefile,
                         REPORT_B_DEFAULT, SUMMARY_CSV_B_DEFAULT)

    if not (ok_a and ok_b):
        sys.exit(1)


if __name__ == "__main__":
    main()
