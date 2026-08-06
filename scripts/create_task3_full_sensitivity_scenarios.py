"""
Task 3 Final Step 6: Build Product B - the full NOAA temporal sensitivity
archive scenario table.

Unlike Product A (50th-percentile only), Product B uses EVERY officially
available NOAA temporal percentile curve found in the parsed templates -
inventoried dynamically here, not assumed. This inventory step found 5 NOAA
cases (First/Second/Third/Fourth-Quartile, All Cases) x 9 percentile curves
(10% through 90%, in 10% steps) = 45 curves per (volume, area, duration)
combination - not merely 10/50/90 as a naive assumption might suggest.

This product is intended as a database/archive for future temporal-shape
sensitivity analysis - it is NOT necessarily the default input for Task 4.

Outputs:
  data/metadata/task3_full_sensitivity_temporal_curve_inventory.csv
  data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_full_temporal_sensitivity.csv
    (scenario count computed dynamically - see printed report)

Usage:
  python scripts/create_task3_full_sensitivity_scenarios.py
"""

import argparse
import os

import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
DEPTH_TABLE_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)
ASSIGNMENT_TABLE_DEFAULT = "data/metadata/huc8_temporal_distribution_assignment_final.csv"
TEMPLATES_TABLE_DEFAULT = (
    "data/processed/hyetograph_templates/atlas14_temporal_distribution_templates_final.csv"
)

INVENTORY_OUTPUT_DEFAULT = "data/metadata/task3_full_sensitivity_temporal_curve_inventory.csv"
SCENARIO_OUTPUT_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_full_temporal_sensitivity.csv"
)

TEMPORAL_DISTRIBUTION_SOURCE = "NOAA Atlas 14 temporal distribution (full percentile-curve archive)"
GEOMETRY_SCOPE = "full HUC8 polygon"
SELECTION_RULE = "intersects Alabama"
STATE_CLIPPED = False

RAINFALL_DEPTH_SOURCE_BY_VOLUME = {
    "9": "NOAA Atlas 14 GIS grid (Volume 9, Southeastern States)",
    "2": "NOAA Atlas 14 GIS grid (Volume 2, Ohio River Basin and Surrounding States)",
}


def temporal_case_final_label(noaa_case, noaa_percentile):
    """Build a filesystem/column-safe label, e.g. 'first_quartile_p10', 'all_cases_p50'."""
    case_map = {
        "First-Quartile Case": "first_quartile",
        "Second-Quartile Case": "second_quartile",
        "Third-Quartile Case": "third_quartile",
        "Fourth-Quartile Case": "fourth_quartile",
        "All Cases": "all_cases",
    }
    case_slug = case_map.get(noaa_case, noaa_case.lower().replace(" ", "_").replace("-", "_"))
    pct_slug = f"p{noaa_percentile.rstrip('%')}"
    return f"{case_slug}_{pct_slug}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth-table", default=DEPTH_TABLE_DEFAULT)
    parser.add_argument("--assignment-table", default=ASSIGNMENT_TABLE_DEFAULT)
    parser.add_argument("--templates-table", default=TEMPLATES_TABLE_DEFAULT)
    parser.add_argument("--inventory-output", default=INVENTORY_OUTPUT_DEFAULT)
    parser.add_argument("--scenario-output", default=SCENARIO_OUTPUT_DEFAULT)
    args = parser.parse_args()

    for path in (args.depth_table, args.assignment_table, args.templates_table):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    os.makedirs(os.path.dirname(args.inventory_output), exist_ok=True)
    os.makedirs(os.path.dirname(args.scenario_output), exist_ok=True)

    templates = pd.read_csv(args.templates_table, dtype={
        "atlas14_volume": str, "temporal_distribution_area": str,
    })

    # --- Section: inventory every unique official curve actually present ---
    group_cols = [
        "atlas14_volume", "temporal_distribution_area", "temporal_distribution_region_name",
        "duration_hour", "noaa_temporal_case", "noaa_percentile_or_curve",
    ]
    inventory_rows = []
    for keys, group in templates.groupby(group_cols):
        atlas14_volume, area, region_name, duration_hour, case, percentile = keys
        time_diffs = group.sort_values("time_hour")["time_hour"].diff().dropna()
        inventory_rows.append({
            "atlas14_volume": atlas14_volume,
            "temporal_distribution_area": area,
            "temporal_distribution_region_name": region_name,
            "duration_hour": duration_hour,
            "noaa_temporal_case": case,
            "noaa_percentile_or_curve": percentile,
            "number_of_time_steps": len(group),
            "time_step_hour": round(time_diffs.median(), 4) if len(time_diffs) else "",
            "source_file": group["source_file"].iloc[0],
            "source_url": group["source_url"].iloc[0],
            "status": "official_curve_confirmed",
            "notes": "",
        })
    inventory_df = pd.DataFrame(inventory_rows).sort_values(
        ["atlas14_volume", "temporal_distribution_area", "duration_hour", "noaa_temporal_case", "noaa_percentile_or_curve"]
    )
    inventory_df.to_csv(args.inventory_output, index=False)

    n_cases = inventory_df["noaa_temporal_case"].nunique()
    n_percentiles = inventory_df["noaa_percentile_or_curve"].nunique()
    print(f"Curve inventory: {len(inventory_df)} unique (volume, area, duration, case, percentile) rows")
    print(f"  Distinct NOAA cases found: {n_cases} -> {sorted(inventory_df['noaa_temporal_case'].unique())}")
    print(f"  Distinct percentile curves found: {n_percentiles} -> {sorted(inventory_df['noaa_percentile_or_curve'].unique(), key=lambda p: int(p.rstrip('%')))}")
    print(f"Wrote {len(inventory_df)} rows to {args.inventory_output}")

    # --- Section: build the scenario table - every HUC8 x RP x duration x available curve ---
    depth_df = pd.read_csv(args.depth_table, dtype={"huc8_id": str, "atlas14_volume": str})
    assignment_df = pd.read_csv(args.assignment_table, dtype={
        "huc8_id": str, "atlas14_volume_temporal_distribution": str, "temporal_distribution_area": str,
    })
    assign_cols = assignment_df[[
        "huc8_id", "atlas14_volume_temporal_distribution", "temporal_distribution_area",
        "temporal_distribution_region_name",
    ]]
    base = depth_df.merge(assign_cols, on="huc8_id", how="left")

    # Curves available per (volume, area, duration) - only the combos actually assigned to a HUC8.
    curves_by_key = inventory_df.rename(columns={"atlas14_volume": "atlas14_volume_temporal_distribution"})
    curves_by_key = curves_by_key[[
        "atlas14_volume_temporal_distribution", "temporal_distribution_area", "duration_hour",
        "noaa_temporal_case", "noaa_percentile_or_curve",
    ]]

    scenario_df = base.merge(
        curves_by_key,
        on=["atlas14_volume_temporal_distribution", "temporal_distribution_area", "duration_hour"],
        how="left",
    )

    scenario_df["temporal_case_final"] = scenario_df.apply(
        lambda r: temporal_case_final_label(r["noaa_temporal_case"], r["noaa_percentile_or_curve"]), axis=1
    )
    scenario_df["scenario_id"] = (
        scenario_df["huc8_id"] + "_RP" + scenario_df["return_period_year"].astype(str)
        + "_D" + scenario_df["duration_hour"].astype(str) + "h_" + scenario_df["temporal_case_final"]
    )
    scenario_df["rainfall_depth_source"] = scenario_df["atlas14_volume"].map(RAINFALL_DEPTH_SOURCE_BY_VOLUME)
    scenario_df["temporal_distribution_source"] = TEMPORAL_DISTRIBUTION_SOURCE
    scenario_df["geometry_scope"] = GEOMETRY_SCOPE
    scenario_df["selection_rule"] = SELECTION_RULE
    scenario_df["state_clipped"] = STATE_CLIPPED
    scenario_df["status"] = "rainfall_depth_extracted"
    scenario_df["notes"] = ""
    scenario_df = scenario_df.rename(columns={"atlas14_volume": "atlas14_volume_rainfall_depth"})

    output_cols = [
        "scenario_id", "huc8_id", "huc8_name", "return_period_year", "duration_hour",
        "temporal_case_final", "noaa_temporal_case", "noaa_percentile_or_curve", "rainfall_depth",
        "rainfall_depth_unit", "atlas14_volume_rainfall_depth", "atlas14_volume_temporal_distribution",
        "temporal_distribution_area", "temporal_distribution_region_name", "rainfall_depth_source",
        "temporal_distribution_source", "geometry_scope", "selection_rule", "state_clipped",
        "status", "notes",
    ]
    scenario_df = scenario_df[output_cols]
    scenario_df.to_csv(args.scenario_output, index=False)

    n_huc = depth_df["huc8_id"].nunique()
    n_curves_per_huc = len(inventory_df) // (inventory_df.groupby(["atlas14_volume", "temporal_distribution_area"]).ngroups) \
        if inventory_df.groupby(["atlas14_volume", "temporal_distribution_area"]).ngroups else 0
    print(f"\nHUC8 count: {n_huc}; return periods: 6; durations: 4")
    print(f"Total Product B scenarios generated: {len(scenario_df)}")
    dup = scenario_df["scenario_id"].duplicated().sum()
    print(f"Duplicate scenario_id count: {dup}")
    print(f"Wrote {len(scenario_df)} rows to {args.scenario_output}")


if __name__ == "__main__":
    main()
