"""
Task 3 Final Step 7: Generate Product B synthetic hyetographs (full NOAA
temporal sensitivity archive).

Same method as Product A (scripts/generate_atlas14_hyetographs_main_noaa_native.py):
  cumulative_rainfall = rainfall_depth * cumulative_fraction
  incremental_rainfall[t] = cumulative_rainfall[t] - cumulative_rainfall[t-1]

Product B covers all 45 officially available NOAA curves (5 cases x 9
percentiles) per HUC8/return-period/duration, so the long-format table is
large (~4-5 million rows). This script uses vectorized pandas groupby
aggregation throughout (not a per-scenario Python loop) to keep runtime
reasonable at this scale.

Outputs:
  data/processed/hyetographs/atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_long.csv
  data/processed/hyetographs/atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_summary.csv

Usage:
  python scripts/generate_atlas14_hyetographs_full_temporal_sensitivity.py
"""

import argparse
import os

import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
SCENARIO_TABLE_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_full_temporal_sensitivity.csv"
)
TEMPLATES_TABLE_DEFAULT = (
    "data/processed/hyetograph_templates/atlas14_temporal_distribution_templates_final.csv"
)
OUTPUT_DIR_DEFAULT = "data/processed/hyetographs"
LONG_OUTPUT_NAME = "atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_long.csv"
SUMMARY_OUTPUT_NAME = "atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_summary.csv"

STATUS_RESOLVED = "atlas14_hyetograph_generated"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-table", default=SCENARIO_TABLE_DEFAULT)
    parser.add_argument("--templates-table", default=TEMPLATES_TABLE_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    args = parser.parse_args()

    for path in (args.scenario_table, args.templates_table):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    os.makedirs(args.output_dir, exist_ok=True)

    scenarios = pd.read_csv(args.scenario_table, dtype={
        "huc8_id": str, "atlas14_volume_rainfall_depth": str,
        "atlas14_volume_temporal_distribution": str, "temporal_distribution_area": str,
    })
    templates = pd.read_csv(args.templates_table, dtype={
        "atlas14_volume": str, "temporal_distribution_area": str,
    })
    print(f"Loaded {len(scenarios)} Product B scenarios.")

    template_cols = templates.rename(columns={"atlas14_volume": "atlas14_volume_temporal_distribution"})[[
        "atlas14_volume_temporal_distribution", "temporal_distribution_area", "duration_hour",
        "noaa_temporal_case", "noaa_percentile_or_curve", "time_hour", "cumulative_percent",
        "cumulative_fraction",
    ]]

    long_df = scenarios.merge(
        template_cols,
        on=["atlas14_volume_temporal_distribution", "temporal_distribution_area",
            "duration_hour", "noaa_temporal_case", "noaa_percentile_or_curve"],
        how="left",
    )
    print(f"Expanded to {len(long_df)} long-format rows after joining NOAA curves.")

    missing_curve = long_df["time_hour"].isna()
    if missing_curve.any():
        missing_ids = long_df.loc[missing_curve, "scenario_id"].unique()
        print(f"WARNING: {missing_curve.sum()} rows found no matching curve "
              f"({len(missing_ids)} scenario_ids affected, e.g. {list(missing_ids[:5])})")
    long_df = long_df[~missing_curve].sort_values(["scenario_id", "time_hour"]).reset_index(drop=True)

    long_df["cumulative_rainfall"] = long_df["rainfall_depth"].astype(float) * long_df["cumulative_fraction"]
    grouped_cum = long_df.groupby("scenario_id")["cumulative_rainfall"]
    long_df["incremental_rainfall"] = grouped_cum.diff().fillna(long_df["cumulative_rainfall"])
    long_df["cumulative_rainfall_unit"] = "in"
    long_df["incremental_rainfall_unit"] = "in"
    long_df["status"] = STATUS_RESOLVED
    long_df["notes"] = ""

    long_output_cols = [
        "scenario_id", "huc8_id", "huc8_name", "return_period_year", "duration_hour",
        "temporal_case_final", "noaa_temporal_case", "noaa_percentile_or_curve", "time_hour",
        "cumulative_percent", "cumulative_fraction", "rainfall_depth", "rainfall_depth_unit",
        "cumulative_rainfall", "cumulative_rainfall_unit", "incremental_rainfall",
        "incremental_rainfall_unit", "atlas14_volume_rainfall_depth",
        "atlas14_volume_temporal_distribution", "temporal_distribution_area",
        "temporal_distribution_region_name", "rainfall_depth_source", "temporal_distribution_source",
        "geometry_scope", "selection_rule", "state_clipped", "status", "notes",
    ]
    long_df = long_df[long_output_cols]
    long_path = os.path.join(args.output_dir, LONG_OUTPUT_NAME)
    long_df.to_csv(long_path, index=False)
    print(f"Wrote {len(long_df)} rows to {long_path}")

    # --- Section: vectorized per-scenario summary aggregation (no per-group Python loop) ---
    grp = long_df.groupby("scenario_id", sort=False)
    total_incremental = grp["incremental_rainfall"].sum()
    max_incremental = grp["incremental_rainfall"].max()
    idx_of_max = grp["incremental_rainfall"].idxmax()
    time_of_max = long_df.loc[idx_of_max, "time_hour"].values
    cumulative_final = grp["cumulative_rainfall"].last()
    n_steps = grp.size()
    time_step_hour = grp["time_hour"].diff().groupby(long_df["scenario_id"]).median()
    first_rows = long_df.groupby("scenario_id", sort=False).first()

    summary_df = pd.DataFrame({
        "scenario_id": total_incremental.index,
        "huc8_id": first_rows["huc8_id"].values,
        "huc8_name": first_rows["huc8_name"].values,
        "return_period_year": first_rows["return_period_year"].values,
        "duration_hour": first_rows["duration_hour"].values,
        "temporal_case_final": first_rows["temporal_case_final"].values,
        "noaa_temporal_case": first_rows["noaa_temporal_case"].values,
        "noaa_percentile_or_curve": first_rows["noaa_percentile_or_curve"].values,
        "rainfall_depth": first_rows["rainfall_depth"].values,
        "rainfall_depth_unit": first_rows["rainfall_depth_unit"].values,
        "total_incremental_rainfall": total_incremental.round(4).values,
        "max_incremental_rainfall": max_incremental.round(4).values,
        "time_of_max_incremental_rainfall": time_of_max,
        "cumulative_rainfall_final": cumulative_final.round(4).values,
        "number_of_time_steps": n_steps.values,
        "time_step_hour": time_step_hour.reindex(total_incremental.index).round(4).values,
        "atlas14_volume_rainfall_depth": first_rows["atlas14_volume_rainfall_depth"].values,
        "atlas14_volume_temporal_distribution": first_rows["atlas14_volume_temporal_distribution"].values,
        "temporal_distribution_area": first_rows["temporal_distribution_area"].values,
        "temporal_distribution_region_name": first_rows["temporal_distribution_region_name"].values,
        "status": STATUS_RESOLVED,
        "notes": "",
    })

    summary_path = os.path.join(args.output_dir, SUMMARY_OUTPUT_NAME)
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote {len(summary_df)} rows to {summary_path}")


if __name__ == "__main__":
    main()
