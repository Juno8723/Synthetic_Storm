"""
Task 2C-5: Validate Task 2 outputs.

Runs a series of quality checks against the Task 2 rainfall-depth table and
updated scenario table, and against the metadata registries. Prints a PASS
or FAIL line for each check and exits with a non-zero status if any
required check fails. Row-count checks account for the one documented
HUC8 (Sequatchie, 06020004) that falls outside Volume 9 grid coverage and
is intentionally left pending rather than invented.

Usage:
  python scripts/validate_task2_outputs.py
"""

import argparse
import os
import sys

import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
HUC_SUMMARY_PATH_DEFAULT = "data/processed/huc_summary/alabama_huc8_summary.csv"
DEPTH_TABLE_PATH_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)
SCENARIO_WITH_DEPTHS_PATH_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv"
)
GIS_INVENTORY_PATH_DEFAULT = "data/metadata/atlas14_gis_inventory.csv"

RETURN_PERIODS_YEAR_DEFAULT = [5, 10, 50, 100, 200, 500]
DURATIONS_HOUR_DEFAULT = [6, 12, 24, 96]
TEMPORAL_PATTERNS_DEFAULT = ["early_peak", "middle_peak", "late_peak", "balanced"]

OFFICIAL_URL_PREFIXES = ("https://hdsc.nws.noaa.gov/", "https://www.weather.gov/")


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
    parser.add_argument("--huc-summary", default=HUC_SUMMARY_PATH_DEFAULT)
    parser.add_argument("--depth-table", default=DEPTH_TABLE_PATH_DEFAULT)
    parser.add_argument("--scenario-with-depths", default=SCENARIO_WITH_DEPTHS_PATH_DEFAULT)
    parser.add_argument("--gis-inventory", default=GIS_INVENTORY_PATH_DEFAULT)
    parser.add_argument("--return-periods", type=int, nargs="+", default=RETURN_PERIODS_YEAR_DEFAULT)
    parser.add_argument("--durations", type=int, nargs="+", default=DURATIONS_HOUR_DEFAULT)
    parser.add_argument("--temporal-patterns", nargs="+", default=TEMPORAL_PATTERNS_DEFAULT)
    args = parser.parse_args()

    for path in (args.huc_summary, args.depth_table, args.scenario_with_depths, args.gis_inventory):
        if not os.path.exists(path):
            print(f"ERROR: required input file not found: {path}")
            sys.exit(2)

    huc_summary = pd.read_csv(args.huc_summary, dtype={"huc8_id": str})
    depths = pd.read_csv(args.depth_table, dtype={"huc8_id": str})
    scenarios = pd.read_csv(args.scenario_with_depths, dtype={"huc8_id": str})
    gis_inventory = pd.read_csv(args.gis_inventory)

    n_huc = huc_summary["huc8_id"].nunique()
    n_rp = len(args.return_periods)
    n_dur = len(args.durations)
    n_pat = len(args.temporal_patterns)

    results = CheckResults()

    # --- Check: depth table row count (one estimate row per huc8-duration-return period) ---
    depths_estimate = depths[depths["confidence_bound"] == "estimate"]
    expected_depth_rows = n_huc * n_rp * n_dur
    results.check(
        "Depth table row count == huc8 x return_period x duration",
        len(depths_estimate) == expected_depth_rows,
        f"expected {expected_depth_rows}, got {len(depths_estimate)}",
    )

    # --- Check: scenario table row count ---
    expected_scenario_rows = n_huc * n_rp * n_dur * n_pat
    results.check(
        "Scenario table row count == huc8 x return_period x duration x temporal_pattern",
        len(scenarios) == expected_scenario_rows,
        f"expected {expected_scenario_rows}, got {len(scenarios)}",
    )

    # --- Check: no duplicate scenario_id ---
    dup_count = scenarios["scenario_id"].duplicated().sum()
    results.check("No duplicate scenario_id values", dup_count == 0, f"{dup_count} duplicates found")

    # --- Check: rainfall_depth identical across temporal patterns for same huc8+RP+duration ---
    group_nunique = scenarios.groupby(
        ["huc8_id", "return_period_year", "duration_hour"]
    )["rainfall_depth"].nunique()
    inconsistent = group_nunique[group_nunique > 1]
    results.check(
        "rainfall_depth identical across all temporal_pattern rows for same huc8+RP+duration",
        len(inconsistent) == 0,
        f"{len(inconsistent)} huc8/RP/duration groups have inconsistent depths"
        if len(inconsistent) else "",
    )

    # --- Check: units documented ---
    units_ok = scenarios["rainfall_depth_unit"].notna().all() and (scenarios["rainfall_depth_unit"] == "in").all()
    results.check("rainfall_depth_unit populated and consistent ('in')", units_ok)

    # --- Check: extraction_method documented for extracted rows ---
    extracted_rows = scenarios[scenarios["status"] == "atlas14_depth_extracted"]
    method_ok = (
        extracted_rows["rainfall_depth_extraction_method"].notna().all()
        and (extracted_rows["rainfall_depth_extraction_method"] != "").all()
    )
    results.check(
        "rainfall_depth_extraction_method populated for all extracted rows",
        method_ok if len(extracted_rows) else False,
        f"{len(extracted_rows)} extracted rows checked",
    )

    # --- Check: geometry_scope / selection_rule / state_clipped populated ---
    geom_ok = (
        (scenarios["geometry_scope"] == "full HUC8 polygon").all()
        and (scenarios["selection_rule"] == "intersects Alabama").all()
        and (scenarios["state_clipped"].astype(str).isin(["False", "false", "0"])).all()
    )
    results.check(
        "geometry_scope / selection_rule / state_clipped populated with fixed project values",
        geom_ok,
    )

    # --- Check: no invented rainfall values (pending rows must be exactly 'TBD') ---
    pending_rows = scenarios[scenarios["status"] == "pending_atlas14_depth"]
    invented = pending_rows[pending_rows["rainfall_depth"] != "TBD"]
    results.check(
        "No invented rainfall values (all pending rows use 'TBD')",
        len(invented) == 0,
        f"{len(invented)} pending rows have a non-TBD rainfall_depth value" if len(invented) else "",
    )

    # --- Check: source URLs in GIS inventory are official NOAA domains ---
    non_official = gis_inventory[
        ~gis_inventory["source_url"].astype(str).str.startswith(OFFICIAL_URL_PREFIXES)
    ]
    results.check(
        "All source_url entries in GIS inventory point to official NOAA domains",
        len(non_official) == 0,
        f"{len(non_official)} non-official URLs found" if len(non_official) else "",
    )

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
