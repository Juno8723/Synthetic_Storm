"""
Task 3 Final Step 4: Build Product A - the main NOAA-native 50th-percentile
scenario table.

This supersedes the original Task 3 early_peak/middle_peak/late_peak/balanced
scheme, which could not resolve "middle_peak" because NOAA Atlas 14 uses
quartile-based temporal cases, not early/middle/late/balanced terminology.
Product A instead uses NOAA's own five case labels directly, at the
50th-percentile (median) curve for each - eliminating the ambiguity
entirely, since every one of NOAA's five native cases maps to exactly one
final label with no leftover "which case is the middle one" question.

Final NOAA-native temporal case labels (all using the 50th-percentile curve):
  first_quartile_peak_p50   -> NOAA First-Quartile Case,  50th percentile
  second_quartile_peak_p50  -> NOAA Second-Quartile Case, 50th percentile
  third_quartile_peak_p50   -> NOAA Third-Quartile Case,  50th percentile
  fourth_quartile_peak_p50  -> NOAA Fourth-Quartile Case, 50th percentile
  all_cases_p50             -> NOAA All Cases,             50th percentile

Outputs:
  data/metadata/task3_main_noaa_native_temporal_curve_mapping.csv
  data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_main_noaa_native.csv
    (expected 7,080 rows = 59 HUC8 x 6 return periods x 4 durations x 5 cases)

Usage:
  python scripts/create_task3_main_noaa_native_scenarios.py
"""

import argparse
import csv
import os

import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
DEPTH_TABLE_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)
ASSIGNMENT_TABLE_DEFAULT = "data/metadata/huc8_temporal_distribution_assignment_final.csv"

MAPPING_OUTPUT_DEFAULT = "data/metadata/task3_main_noaa_native_temporal_curve_mapping.csv"
SCENARIO_OUTPUT_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_main_noaa_native.csv"
)

MEDIAN_CURVE = "50%"
TEMPORAL_DISTRIBUTION_SOURCE = "NOAA Atlas 14 temporal distribution (quartile-case curves, 50th-percentile)"
GEOMETRY_SCOPE = "full HUC8 polygon"
SELECTION_RULE = "intersects Alabama"
STATE_CLIPPED = False

RAINFALL_DEPTH_SOURCE_BY_VOLUME = {
    "9": "NOAA Atlas 14 GIS grid (Volume 9, Southeastern States)",
    "2": "NOAA Atlas 14 GIS grid (Volume 2, Ohio River Basin and Surrounding States)",
}

MAPPING_ROWS = [
    {
        "temporal_case_final": "first_quartile_peak_p50",
        "noaa_temporal_case": "First-Quartile Case",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": "Direct 1:1 mapping to NOAA's First-Quartile Case, 50th-percentile (median) curve.",
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    {
        "temporal_case_final": "second_quartile_peak_p50",
        "noaa_temporal_case": "Second-Quartile Case",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": "Direct 1:1 mapping to NOAA's Second-Quartile Case, 50th-percentile (median) curve.",
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    {
        "temporal_case_final": "third_quartile_peak_p50",
        "noaa_temporal_case": "Third-Quartile Case",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": "Direct 1:1 mapping to NOAA's Third-Quartile Case, 50th-percentile (median) curve.",
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    {
        "temporal_case_final": "fourth_quartile_peak_p50",
        "noaa_temporal_case": "Fourth-Quartile Case",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": "Direct 1:1 mapping to NOAA's Fourth-Quartile Case, 50th-percentile (median) curve.",
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    {
        "temporal_case_final": "all_cases_p50",
        "noaa_temporal_case": "All Cases",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": "Direct 1:1 mapping to NOAA's combined All Cases curve, 50th-percentile (median).",
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth-table", default=DEPTH_TABLE_DEFAULT)
    parser.add_argument("--assignment-table", default=ASSIGNMENT_TABLE_DEFAULT)
    parser.add_argument("--mapping-output", default=MAPPING_OUTPUT_DEFAULT)
    parser.add_argument("--scenario-output", default=SCENARIO_OUTPUT_DEFAULT)
    args = parser.parse_args()

    for path in (args.depth_table, args.assignment_table):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    os.makedirs(os.path.dirname(args.mapping_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.scenario_output), exist_ok=True)

    # --- Section: write the mapping table ---
    mapping_fieldnames = [
        "temporal_case_final", "noaa_temporal_case", "noaa_percentile_or_curve",
        "mapping_rule", "mapping_confidence", "status", "notes",
    ]
    with open(args.mapping_output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=mapping_fieldnames)
        writer.writeheader()
        writer.writerows(MAPPING_ROWS)
    print(f"Wrote {len(MAPPING_ROWS)} rows to {args.mapping_output}")

    # --- Section: build the scenario table (depth x assignment x 5 NOAA-native cases) ---
    depth_df = pd.read_csv(args.depth_table, dtype={"huc8_id": str, "atlas14_volume": str})
    assignment_df = pd.read_csv(args.assignment_table, dtype={
        "huc8_id": str, "atlas14_volume_temporal_distribution": str, "temporal_distribution_area": str,
    })

    assign_cols = assignment_df[[
        "huc8_id", "atlas14_volume_temporal_distribution", "temporal_distribution_area",
        "temporal_distribution_region_name",
    ]]
    base = depth_df.merge(assign_cols, on="huc8_id", how="left")

    rows = []
    for _, base_row in base.iterrows():
        rainfall_depth_source = RAINFALL_DEPTH_SOURCE_BY_VOLUME.get(
            str(base_row["atlas14_volume"]), "NOAA Atlas 14 GIS grid"
        )
        for mapping in MAPPING_ROWS:
            scenario_id = (
                f"{base_row['huc8_id']}_RP{base_row['return_period_year']}_"
                f"D{base_row['duration_hour']}h_{mapping['temporal_case_final']}"
            )
            rows.append({
                "scenario_id": scenario_id,
                "huc8_id": base_row["huc8_id"],
                "huc8_name": base_row["huc8_name"],
                "return_period_year": base_row["return_period_year"],
                "duration_hour": base_row["duration_hour"],
                "temporal_case_final": mapping["temporal_case_final"],
                "noaa_temporal_case": mapping["noaa_temporal_case"],
                "noaa_percentile_or_curve": mapping["noaa_percentile_or_curve"],
                "rainfall_depth": base_row["rainfall_depth"],
                "rainfall_depth_unit": base_row["rainfall_depth_unit"],
                "atlas14_volume_rainfall_depth": base_row["atlas14_volume"],
                "atlas14_volume_temporal_distribution": base_row["atlas14_volume_temporal_distribution"],
                "temporal_distribution_area": base_row["temporal_distribution_area"],
                "temporal_distribution_region_name": base_row["temporal_distribution_region_name"],
                "rainfall_depth_source": rainfall_depth_source,
                "temporal_distribution_source": TEMPORAL_DISTRIBUTION_SOURCE,
                "geometry_scope": GEOMETRY_SCOPE,
                "selection_rule": SELECTION_RULE,
                "state_clipped": STATE_CLIPPED,
                "status": "rainfall_depth_extracted",
                "notes": "",
            })

    scenario_df = pd.DataFrame(rows)
    scenario_df.to_csv(args.scenario_output, index=False)
    print(f"Wrote {len(scenario_df)} rows to {args.scenario_output}")

    expected = depth_df["huc8_id"].nunique() * 6 * 4 * len(MAPPING_ROWS)
    if len(scenario_df) != 7080:
        print(f"WARNING: expected 7,080 rows, got {len(scenario_df)} (computed expectation: {expected})")
    dup = scenario_df["scenario_id"].duplicated().sum()
    if dup:
        print(f"WARNING: {dup} duplicate scenario_id values found")


if __name__ == "__main__":
    main()
