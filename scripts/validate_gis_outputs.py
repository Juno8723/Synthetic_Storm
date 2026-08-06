"""
Validate the GIS-ready Task 2 outputs (scripts/export_task2_gis_layers.py).

Checks the GeoPackage produced from the Atlas 14 rainfall-depth table:
layer presence, expected row counts, geometry validity, populated fields,
and correct Atlas 14 volume attribution (Sequatchie = Volume 2, all other
HUC8s = Volume 9). Exits non-zero if any check fails.

Usage:
  python scripts/validate_gis_outputs.py
"""

import argparse
import os
import sys

import geopandas as gpd

# --- Section: project defaults (documented, not hidden) ---
GPKG_PATH_DEFAULT = "data/processed/gis/atlas14_huc8_rainfall_depths.gpkg"

EXPECTED_LAYERS = [
    "atlas14_depths_all",
    "atlas14_depths_100yr_24hr",
    "atlas14_depths_500yr_24hr",
    "atlas14_depths_100yr_6hr",
    "atlas14_depths_100yr_96hr",
    "atlas14_depths_50yr_24hr",
]
SINGLE_SCENARIO_LAYERS = [
    "atlas14_depths_100yr_24hr",
    "atlas14_depths_500yr_24hr",
    "atlas14_depths_100yr_6hr",
    "atlas14_depths_100yr_96hr",
    "atlas14_depths_50yr_24hr",
]

SEQUATCHIE_HUC8_ID = "06020004"
EXTRACTED_STATUSES = {"extracted"}


class CheckResults:
    def __init__(self):
        self.failures = []

    def check(self, description, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {description}" + (f" - {detail}" if detail else ""))
        if not passed:
            self.failures.append(description)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpkg", default=GPKG_PATH_DEFAULT)
    args = parser.parse_args()

    results = CheckResults()

    # --- Check: GeoPackage file exists ---
    gpkg_exists = os.path.exists(args.gpkg)
    results.check(f"GeoPackage exists at {args.gpkg}", gpkg_exists)
    if not gpkg_exists:
        print("Cannot continue without the GeoPackage.")
        sys.exit(2)

    # --- Check: expected layers exist ---
    available_layers = set(gpd.list_layers(args.gpkg)["name"])
    for layer in EXPECTED_LAYERS:
        results.check(f"Layer '{layer}' exists", layer in available_layers)

    if not set(EXPECTED_LAYERS).issubset(available_layers):
        print("Missing layer(s); skipping per-layer content checks that depend on them.")
        _finish(results)
        return

    layers = {name: gpd.read_file(args.gpkg, layer=name) for name in EXPECTED_LAYERS}

    # --- Check: atlas14_depths_all row count ---
    all_layer = layers["atlas14_depths_all"]
    results.check(
        "atlas14_depths_all has 1,416 rows",
        len(all_layer) == 1416,
        f"got {len(all_layer)}",
    )

    # --- Check: single-scenario layers each have 59 rows ---
    for layer_name in SINGLE_SCENARIO_LAYERS:
        gdf = layers[layer_name]
        results.check(
            f"{layer_name} has 59 rows",
            len(gdf) == 59,
            f"got {len(gdf)}",
        )

    # --- Check: valid, non-empty geometry in every layer ---
    for layer_name, gdf in layers.items():
        invalid = (~gdf.geometry.is_valid).sum()
        empty = gdf.geometry.is_empty.sum()
        null_geom = gdf.geometry.isna().sum()
        results.check(
            f"{layer_name} geometry valid/non-empty/non-null",
            invalid == 0 and empty == 0 and null_geom == 0,
            f"invalid={invalid}, empty={empty}, null={null_geom}",
        )

    # --- Check: rainfall_depth populated (no nulls, all numeric) ---
    for layer_name, gdf in layers.items():
        null_depth = gdf["rainfall_depth"].isna().sum()
        try:
            gdf["rainfall_depth"].astype(float)
            numeric_ok = True
        except (ValueError, TypeError):
            numeric_ok = False
        results.check(
            f"{layer_name} rainfall_depth populated and numeric",
            null_depth == 0 and numeric_ok,
            f"nulls={null_depth}, all_numeric={numeric_ok}",
        )

    # --- Check: no missing huc8_id ---
    for layer_name, gdf in layers.items():
        missing_id = gdf["huc8_id"].isna().sum() + (gdf["huc8_id"].astype(str).str.strip() == "").sum()
        results.check(f"{layer_name} has no missing huc8_id", missing_id == 0, f"missing={missing_id}")

    # --- Check: status indicates extracted values ---
    for layer_name, gdf in layers.items():
        non_extracted = (~gdf["status"].isin(EXTRACTED_STATUSES)).sum()
        results.check(
            f"{layer_name} status indicates extracted values",
            non_extracted == 0,
            f"{non_extracted} rows not status=extracted" if non_extracted else "",
        )

    # --- Check: Sequatchie retains Volume 2 attribution ---
    seq_rows = all_layer[all_layer["huc8_id"] == SEQUATCHIE_HUC8_ID]
    seq_vol_ok = (
        len(seq_rows) > 0
        and (seq_rows["atlas14_volume"].astype(str) == "2").all()
    )
    results.check(
        f"HUC8 {SEQUATCHIE_HUC8_ID} (Sequatchie) retains Atlas 14 Volume 2 attribution",
        seq_vol_ok,
        f"{len(seq_rows)} rows, volumes={sorted(seq_rows['atlas14_volume'].astype(str).unique())}"
        if len(seq_rows) else "no rows found",
    )

    # --- Check: all other HUC8s retain Volume 9 attribution ---
    other_rows = all_layer[all_layer["huc8_id"] != SEQUATCHIE_HUC8_ID]
    other_vol_ok = (other_rows["atlas14_volume"].astype(str) == "9").all()
    non_vol9 = other_rows[other_rows["atlas14_volume"].astype(str) != "9"]
    results.check(
        "All other HUC8s retain Atlas 14 Volume 9 attribution",
        other_vol_ok,
        f"{len(non_vol9)} non-Volume-9 rows found among other HUC8s" if not other_vol_ok else "",
    )

    _finish(results)


def _finish(results):
    print()
    if results.failures:
        print(f"{len(results.failures)} check(s) FAILED:")
        for f in results.failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks PASSED.")


if __name__ == "__main__":
    main()
