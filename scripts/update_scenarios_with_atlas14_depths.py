"""
Task 2C-4: Join extracted Atlas 14 rainfall depths into the storm scenario table.

Reads the Task 1 scenario template (one row per huc8_id x return_period_year x
duration_hour x temporal_pattern, with rainfall_depth = "TBD") and the Task 2
extracted depth table (one estimate row per huc8_id x return_period_year x
duration_hour), joins them on (huc8_id, return_period_year, duration_hour),
and repeats the same rainfall_depth value across all four temporal_pattern
rows for that combination.

Hydrologic rule enforced here: rainfall depth depends only on
huc8_id + return_period_year + duration_hour. It does NOT vary by
temporal_pattern, so the join is a many-to-one broadcast, never a per-pattern
lookup.

This does NOT overwrite the Task 1 template. It writes a new file:
  data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv

Usage:
  python scripts/update_scenarios_with_atlas14_depths.py
"""

import argparse
import os

import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
SCENARIO_TEMPLATE_PATH_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_template.csv"
)
DEPTH_TABLE_PATH_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)
OUTPUT_PATH_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv"
)

RAINFALL_DEPTH_SOURCE_EXTRACTED = "NOAA Atlas 14 GIS grid (Volume 9, Southeastern States)"
EXTRACTION_METHOD = "GIS grid zonal statistics (full HUC8 polygon)"
STATUS_EXTRACTED = "atlas14_depth_extracted"
STATUS_PENDING = "pending_atlas14_depth"

GEOMETRY_SCOPE_DEFAULT = "full HUC8 polygon"
SELECTION_RULE_DEFAULT = "intersects Alabama"
STATE_CLIPPED_DEFAULT = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-template", default=SCENARIO_TEMPLATE_PATH_DEFAULT,
                         help="Task 1 scenario template CSV (default: %(default)s)")
    parser.add_argument("--depth-table", default=DEPTH_TABLE_PATH_DEFAULT,
                         help="Task 2 extracted depth table CSV (default: %(default)s)")
    parser.add_argument("--output", default=OUTPUT_PATH_DEFAULT,
                         help="Output path for the updated scenario table (default: %(default)s)")
    args = parser.parse_args()

    if not os.path.exists(args.scenario_template):
        raise FileNotFoundError(
            f"Scenario template not found: {args.scenario_template}. "
            "Run Task 1's scripts/build_storm_scenario_template.py first."
        )
    if not os.path.exists(args.depth_table):
        raise FileNotFoundError(
            f"Depth table not found: {args.depth_table}. "
            "Run scripts/extract_atlas14_huc8_depths.py first."
        )
    if os.path.abspath(args.output) == os.path.abspath(args.scenario_template):
        raise ValueError("Refusing to overwrite the Task 1 scenario template. Choose a different --output.")

    scenarios = pd.read_csv(args.scenario_template, dtype={"huc8_id": str})

    # Keep only the main "estimate" rows for the join - the scenario table
    # carries a single rainfall_depth per combination, matching PFDS point-
    # estimate convention. CI bounds (if extracted) remain in the depth table.
    depths = pd.read_csv(args.depth_table, dtype={"huc8_id": str})
    depths = depths[depths["confidence_bound"] == "estimate"].copy()

    depths_lookup = depths.set_index(["huc8_id", "return_period_year", "duration_hour"])

    # --- Section: drop the placeholder columns we are about to replace ---
    scenarios = scenarios.drop(
        columns=["rainfall_depth", "rainfall_depth_unit", "rainfall_depth_source", "status", "notes"]
    )

    join_keys = depths_lookup[["rainfall_depth", "rainfall_depth_unit", "rainfall_depth_statistic",
                                "status", "notes", "atlas14_source_file"]]
    merged = scenarios.merge(
        join_keys,
        left_on=["huc8_id", "return_period_year", "duration_hour"],
        right_index=True,
        how="left",
    )

    # --- Section: fill values for combinations that failed extraction (e.g. missing grid coverage) ---
    extracted_mask = merged["status"] == "extracted"
    merged.loc[~extracted_mask, "rainfall_depth"] = "TBD"
    merged["rainfall_depth"] = merged["rainfall_depth"].fillna("TBD")
    merged["rainfall_depth_unit"] = merged["rainfall_depth_unit"].fillna("in")
    merged["rainfall_depth_statistic"] = merged["rainfall_depth_statistic"].fillna("mean")
    merged["notes"] = merged["notes"].fillna("")

    merged["rainfall_depth_source"] = RAINFALL_DEPTH_SOURCE_EXTRACTED
    merged.loc[~extracted_mask, "rainfall_depth_source"] = (
        "NOAA Atlas 14 PFDS - to be extracted"
    )
    merged["rainfall_depth_extraction_method"] = EXTRACTION_METHOD
    merged.loc[~extracted_mask, "rainfall_depth_extraction_method"] = ""

    merged["status"] = extracted_mask.map({True: STATUS_EXTRACTED, False: STATUS_PENDING})

    merged["geometry_scope"] = GEOMETRY_SCOPE_DEFAULT
    merged["selection_rule"] = SELECTION_RULE_DEFAULT
    merged["state_clipped"] = STATE_CLIPPED_DEFAULT

    # temporal_distribution_source is unchanged from Task 1 - temporal patterns
    # are still only inventoried (Task 2D), not assigned (Task 3 item).
    merged = merged.drop(columns=["atlas14_source_file"])

    ordered_cols = [
        "scenario_id", "huc8_id", "huc8_name", "return_period_year", "duration_hour",
        "temporal_pattern", "rainfall_depth", "rainfall_depth_unit", "rainfall_depth_source",
        "rainfall_depth_extraction_method", "rainfall_depth_statistic",
        "geometry_scope", "selection_rule", "state_clipped",
        "temporal_distribution_source", "status", "notes",
    ]
    merged = merged[ordered_cols]

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    merged.to_csv(args.output, index=False)

    n_extracted = int((merged["status"] == STATUS_EXTRACTED).sum())
    n_pending = int((merged["status"] == STATUS_PENDING).sum())
    print(f"Wrote {len(merged)} rows to {args.output}")
    print(f"  status=atlas14_depth_extracted: {n_extracted}")
    print(f"  status=pending_atlas14_depth:   {n_pending}")


if __name__ == "__main__":
    main()
