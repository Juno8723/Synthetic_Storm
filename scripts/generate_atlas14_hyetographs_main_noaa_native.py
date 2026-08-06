"""
Task 3 Final Step 5: Generate Product A synthetic hyetographs (main
NOAA-native 50th-percentile ensemble).

Every scenario in the Product A table has a fully resolved NOAA temporal
case and percentile curve (no ambiguity, unlike the original Task 3 run's
middle_peak), so every one of the 7,080 scenarios gets a full hyetograph
time series here - there are no pending/placeholder rows in this product.

  cumulative_rainfall = rainfall_depth * cumulative_fraction
  incremental_rainfall[t] = cumulative_rainfall[t] - cumulative_rainfall[t-1]
  (cumulative_rainfall before the first NOAA time step is 0, which is
  always exactly true here since every NOAA curve starts at
  cumulative_percent = 0 at time_hour = 0 - verified by
  build_atlas14_temporal_templates.py's validation checks.)

Units are inches throughout. NOAA-provided time steps are used as-is; no
interpolation to another time step is performed.

Outputs:
  data/processed/hyetographs/atlas14_controlled_storm_hyetographs_main_noaa_native_long.csv
  data/processed/hyetographs/atlas14_controlled_storm_hyetographs_main_noaa_native_summary.csv

Usage:
  python scripts/generate_atlas14_hyetographs_main_noaa_native.py
"""

import argparse
import os

import numpy as np
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
SCENARIO_TABLE_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_main_noaa_native.csv"
)
TEMPLATES_TABLE_DEFAULT = (
    "data/processed/hyetograph_templates/atlas14_temporal_distribution_templates_final.csv"
)
OUTPUT_DIR_DEFAULT = "data/processed/hyetographs"
LONG_OUTPUT_NAME = "atlas14_controlled_storm_hyetographs_main_noaa_native_long.csv"
SUMMARY_OUTPUT_NAME = "atlas14_controlled_storm_hyetographs_main_noaa_native_summary.csv"

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

    missing_curve = long_df["time_hour"].isna()
    if missing_curve.any():
        missing_ids = long_df.loc[missing_curve, "scenario_id"].unique()
        print(f"WARNING: {missing_curve.sum()} rows found no matching curve "
              f"({len(missing_ids)} scenario_ids affected, e.g. {list(missing_ids[:5])})")

    long_df = long_df[~missing_curve].sort_values(["scenario_id", "time_hour"])
    long_df["cumulative_rainfall"] = long_df["rainfall_depth"].astype(float) * long_df["cumulative_fraction"]
    long_df["incremental_rainfall"] = (
        long_df.groupby("scenario_id")["cumulative_rainfall"].diff().fillna(long_df["cumulative_rainfall"])
    )
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

    # --- Section: build the per-scenario summary table ---
    summary_rows = []
    for scenario_id, group in long_df.groupby("scenario_id"):
        group = group.sort_values("time_hour")
        max_row = group.loc[group["incremental_rainfall"].idxmax()]
        first = group.iloc[0]
        summary_rows.append({
            "scenario_id": scenario_id,
            "huc8_id": first["huc8_id"],
            "huc8_name": first["huc8_name"],
            "return_period_year": first["return_period_year"],
            "duration_hour": first["duration_hour"],
            "temporal_case_final": first["temporal_case_final"],
            "noaa_temporal_case": first["noaa_temporal_case"],
            "noaa_percentile_or_curve": first["noaa_percentile_or_curve"],
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
            "atlas14_volume_rainfall_depth": first["atlas14_volume_rainfall_depth"],
            "atlas14_volume_temporal_distribution": first["atlas14_volume_temporal_distribution"],
            "temporal_distribution_area": first["temporal_distribution_area"],
            "temporal_distribution_region_name": first["temporal_distribution_region_name"],
            "status": STATUS_RESOLVED,
            "notes": "",
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(args.output_dir, SUMMARY_OUTPUT_NAME)
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote {len(summary_df)} rows to {summary_path}")


if __name__ == "__main__":
    main()
