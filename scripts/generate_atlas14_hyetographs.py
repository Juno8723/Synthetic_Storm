"""
Task 3E: Generate synthetic hyetographs from Task 2 rainfall depths and
official NOAA Atlas 14 temporal distribution curves.

Reads:
  - Task 2 scenario table with rainfall depths (5,664 rows)
  - HUC8 -> temporal distribution area assignment (Task 3B)
  - Parsed NOAA temporal distribution curve templates (Task 3C)
  - Scenario-label -> NOAA curve mapping (Task 3D)

Joins on (huc8_id -> assigned atlas14_volume/temporal_distribution_area,
duration_hour, temporal_pattern -> noaa_temporal_case/noaa_percentile_or_curve),
then:
  cumulative_rainfall = rainfall_depth * cumulative_fraction
  incremental_rainfall[t] = cumulative_rainfall[t] - cumulative_rainfall[t-1]
  (with cumulative_rainfall at the point before the first NOAA time step
  treated as 0, which is always exactly true here because the NOAA curves
  themselves start at cumulative_percent = 0 at time_hour = 0 - verified in
  Task 3C's validation).

IMPORTANT - unresolved temporal_pattern mapping (middle_peak):
Task 3D left `middle_peak` unresolved (status = mapping_review_required)
because NOAA provides two candidate "middle" cases (Second-Quartile,
Third-Quartile) with no documented tiebreaker. Per project instructions,
this script does NOT invent a choice. For every middle_peak scenario, this
script writes exactly one placeholder row (no time series) with
status = pending_temporal_mapping_review and leaves cumulative/incremental
rainfall fields blank. No rainfall value is fabricated.

Units are inches throughout - rainfall_depth is never converted to volume.
NOAA-provided time steps are used as-is; no interpolation to another time
step is performed.

Outputs:
  data/processed/hyetographs/atlas14_controlled_storm_hyetographs_long.csv
  data/processed/hyetographs/atlas14_controlled_storm_hyetographs_summary.csv

Usage:
  python scripts/generate_atlas14_hyetographs.py
"""

import argparse
import os

import numpy as np
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
SCENARIO_TABLE_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv"
)
ASSIGNMENT_TABLE_DEFAULT = "data/metadata/huc8_temporal_distribution_assignment.csv"
TEMPLATES_TABLE_DEFAULT = "data/processed/hyetograph_templates/atlas14_temporal_distribution_templates.csv"
MAPPING_TABLE_DEFAULT = "data/metadata/task3_temporal_pattern_mapping.csv"

OUTPUT_DIR_DEFAULT = "data/processed/hyetographs"
LONG_OUTPUT_NAME = "atlas14_controlled_storm_hyetographs_long.csv"
SUMMARY_OUTPUT_NAME = "atlas14_controlled_storm_hyetographs_summary.csv"

TEMPORAL_DISTRIBUTION_SOURCE = "NOAA Atlas 14 temporal distribution (quartile-case curves)"
GEOMETRY_SCOPE = "full HUC8 polygon"
SELECTION_RULE = "intersects Alabama"
STATE_CLIPPED = False

STATUS_RESOLVED = "atlas14_hyetograph_generated"
STATUS_PENDING = "pending_temporal_mapping_review"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-table", default=SCENARIO_TABLE_DEFAULT)
    parser.add_argument("--assignment-table", default=ASSIGNMENT_TABLE_DEFAULT)
    parser.add_argument("--templates-table", default=TEMPLATES_TABLE_DEFAULT)
    parser.add_argument("--mapping-table", default=MAPPING_TABLE_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    args = parser.parse_args()

    for path in (args.scenario_table, args.assignment_table, args.templates_table, args.mapping_table):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    os.makedirs(args.output_dir, exist_ok=True)

    scenarios = pd.read_csv(args.scenario_table, dtype={"huc8_id": str})
    assignment = pd.read_csv(args.assignment_table, dtype={
        "huc8_id": str, "atlas14_volume_temporal_distribution": str, "temporal_distribution_area": str,
    })
    templates = pd.read_csv(args.templates_table, dtype={
        "atlas14_volume": str, "temporal_distribution_area": str,
    })
    mapping = pd.read_csv(args.mapping_table, dtype={
        "atlas14_volume": str, "temporal_distribution_area": str,
    })

    # --- Section: attach each scenario's HUC8 temporal-region assignment ---
    assign_cols = assignment[[
        "huc8_id", "atlas14_volume_rainfall_depth", "atlas14_volume_temporal_distribution",
        "temporal_distribution_area", "temporal_distribution_region_name", "status",
    ]].rename(columns={"status": "assignment_status"})
    merged = scenarios.merge(assign_cols, on="huc8_id", how="left")

    # --- Section: attach the temporal-pattern -> NOAA curve mapping rule ---
    # Select only the join keys plus the columns this script actually needs from the
    # mapping table - both the scenario table and the assignment table already carry
    # their own "notes" / "temporal_distribution_region_name" columns, and letting
    # pandas auto-suffix those collisions (_x/_y) would silently break every
    # downstream column reference.
    mapping_cols = mapping.rename(columns={
        "atlas14_volume": "atlas14_volume_temporal_distribution",
        "status": "mapping_status",
    })[[
        "temporal_pattern", "atlas14_volume_temporal_distribution", "temporal_distribution_area",
        "duration_hour", "noaa_temporal_case", "noaa_quartile_or_group", "noaa_percentile_or_curve",
        "mapping_rule", "mapping_confidence", "mapping_status",
    ]]
    merged = merged.merge(
        mapping_cols,
        on=["temporal_pattern", "atlas14_volume_temporal_distribution",
            "temporal_distribution_area", "duration_hour"],
        how="left",
    )

    resolved_mask = merged["mapping_status"] == "resolved"
    resolved = merged[resolved_mask].copy()
    pending = merged[~resolved_mask].copy()
    print(f"Scenarios with resolved temporal mapping: {len(resolved)}")
    print(f"Scenarios pending temporal mapping review (middle_peak): {len(pending)}")

    # --- Section: join resolved scenarios to their NOAA curve time series ---
    template_cols = templates.rename(columns={
        "atlas14_volume": "atlas14_volume_temporal_distribution",
    })[[
        "atlas14_volume_temporal_distribution", "temporal_distribution_area", "duration_hour",
        "noaa_temporal_case", "noaa_percentile_or_curve", "time_hour", "cumulative_percent",
        "cumulative_fraction",
    ]]
    long_resolved = resolved.merge(
        template_cols,
        on=["atlas14_volume_temporal_distribution", "temporal_distribution_area",
            "duration_hour", "noaa_temporal_case", "noaa_percentile_or_curve"],
        how="left",
    )

    missing_curve = long_resolved["time_hour"].isna()
    if missing_curve.any():
        print(f"WARNING: {missing_curve.sum()} resolved-mapping rows found no matching curve "
              f"in the templates table (scenario_ids: "
              f"{long_resolved.loc[missing_curve, 'scenario_id'].unique()[:5]}...)")

    long_resolved = long_resolved[~missing_curve].sort_values(["scenario_id", "time_hour"])
    long_resolved["cumulative_rainfall"] = (
        long_resolved["rainfall_depth"].astype(float) * long_resolved["cumulative_fraction"]
    )
    long_resolved["incremental_rainfall"] = (
        long_resolved.groupby("scenario_id")["cumulative_rainfall"].diff().fillna(
            long_resolved["cumulative_rainfall"]
        )
    )
    # First time step's diff() is NaN; since every NOAA curve starts at
    # cumulative_percent=0 at time_hour=0 (validated in Task 3C), the
    # correct incremental value there equals the cumulative value itself
    # (previous cumulative rainfall was 0 before the storm began).
    long_resolved["status"] = STATUS_RESOLVED
    long_resolved["notes"] = ""

    # --- Section: one placeholder row per pending (middle_peak) scenario - no invented series ---
    pending_out = pending.copy()
    for col in ["time_hour", "cumulative_percent", "cumulative_fraction",
                "cumulative_rainfall", "incremental_rainfall"]:
        pending_out[col] = np.nan
    pending_out["status"] = STATUS_PENDING
    pending_out["notes"] = (
        "Temporal pattern 'middle_peak' mapping is unresolved (ambiguous between NOAA "
        "Second-Quartile and Third-Quartile cases; see task3_temporal_pattern_mapping.csv). "
        "No hyetograph time series generated. rainfall_depth is preserved from Task 2 and is "
        "not invented; only the temporal distribution shape is missing."
    )

    long_all = pd.concat([long_resolved, pending_out], ignore_index=True, sort=False)

    long_output_cols = [
        "scenario_id", "huc8_id", "huc8_name", "return_period_year", "duration_hour",
        "temporal_pattern", "atlas14_volume_rainfall_depth", "atlas14_volume_temporal_distribution",
        "temporal_distribution_area", "temporal_distribution_region_name", "noaa_temporal_case",
        "noaa_quartile_or_group", "noaa_percentile_or_curve", "time_hour", "cumulative_percent",
        "cumulative_fraction", "rainfall_depth", "rainfall_depth_unit", "cumulative_rainfall",
        "cumulative_rainfall_unit", "incremental_rainfall", "incremental_rainfall_unit",
        "rainfall_depth_source", "temporal_distribution_source", "geometry_scope",
        "selection_rule", "state_clipped", "status", "notes",
    ]
    long_all["cumulative_rainfall_unit"] = "in"
    long_all["incremental_rainfall_unit"] = "in"
    long_all["temporal_distribution_source"] = TEMPORAL_DISTRIBUTION_SOURCE
    long_all["geometry_scope"] = GEOMETRY_SCOPE
    long_all["selection_rule"] = SELECTION_RULE
    long_all["state_clipped"] = STATE_CLIPPED

    long_all = long_all[long_output_cols]
    long_path = os.path.join(args.output_dir, LONG_OUTPUT_NAME)
    long_all.to_csv(long_path, index=False)
    print(f"Wrote {len(long_all)} rows to {long_path}")

    # --- Section: build the per-scenario summary table ---
    summary_rows = []
    for scenario_id, group in long_resolved.groupby("scenario_id"):
        group = group.sort_values("time_hour")
        max_row = group.loc[group["incremental_rainfall"].idxmax()]
        first = group.iloc[0]
        summary_rows.append({
            "scenario_id": scenario_id,
            "huc8_id": first["huc8_id"],
            "huc8_name": first["huc8_name"],
            "return_period_year": first["return_period_year"],
            "duration_hour": first["duration_hour"],
            "temporal_pattern": first["temporal_pattern"],
            "rainfall_depth": first["rainfall_depth"],
            "rainfall_depth_unit": first["rainfall_depth_unit"],
            "total_incremental_rainfall": round(group["incremental_rainfall"].sum(), 4),
            "max_incremental_rainfall": round(max_row["incremental_rainfall"], 4),
            "time_of_max_incremental_rainfall": max_row["time_hour"],
            "cumulative_rainfall_final": round(group["cumulative_rainfall"].iloc[-1], 4),
            "number_of_time_steps": len(group),
            "time_step_hour": (
                round(group["time_hour"].diff().dropna().median(), 4) if len(group) > 1 else np.nan
            ),
            "temporal_distribution_area": first["temporal_distribution_area"],
            "temporal_distribution_region_name": first["temporal_distribution_region_name"],
            "noaa_temporal_case": first["noaa_temporal_case"],
            "noaa_quartile_or_group": first["noaa_quartile_or_group"],
            "noaa_percentile_or_curve": first["noaa_percentile_or_curve"],
            "atlas14_volume_rainfall_depth": first["atlas14_volume_rainfall_depth"],
            "atlas14_volume_temporal_distribution": first["atlas14_volume_temporal_distribution"],
            "status": STATUS_RESOLVED,
            "notes": "",
        })

    for _, row in pending_out.iterrows():
        summary_rows.append({
            "scenario_id": row["scenario_id"],
            "huc8_id": row["huc8_id"],
            "huc8_name": row["huc8_name"],
            "return_period_year": row["return_period_year"],
            "duration_hour": row["duration_hour"],
            "temporal_pattern": row["temporal_pattern"],
            "rainfall_depth": row["rainfall_depth"],
            "rainfall_depth_unit": row["rainfall_depth_unit"],
            "total_incremental_rainfall": np.nan,
            "max_incremental_rainfall": np.nan,
            "time_of_max_incremental_rainfall": np.nan,
            "cumulative_rainfall_final": np.nan,
            "number_of_time_steps": 0,
            "time_step_hour": np.nan,
            "temporal_distribution_area": row.get("temporal_distribution_area", ""),
            "temporal_distribution_region_name": row.get("temporal_distribution_region_name", ""),
            "noaa_temporal_case": row.get("noaa_temporal_case", ""),
            "noaa_quartile_or_group": row.get("noaa_quartile_or_group", ""),
            "noaa_percentile_or_curve": row.get("noaa_percentile_or_curve", ""),
            "atlas14_volume_rainfall_depth": row.get("atlas14_volume_rainfall_depth", ""),
            "atlas14_volume_temporal_distribution": row.get("atlas14_volume_temporal_distribution", ""),
            "status": STATUS_PENDING,
            "notes": row["notes"],
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(args.output_dir, SUMMARY_OUTPUT_NAME)
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote {len(summary_df)} rows to {summary_path}")
    print(f"  {STATUS_RESOLVED}: {(summary_df['status'] == STATUS_RESOLVED).sum()}")
    print(f"  {STATUS_PENDING}: {(summary_df['status'] == STATUS_PENDING).sum()}")


if __name__ == "__main__":
    main()
