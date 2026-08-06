"""
Task 3H: Validate the Task 3 tabular hyetograph outputs.

Checks mass-balance consistency of every resolved hyetograph (sum of
incremental rainfall equals the Task 2 rainfall_depth, cumulative rainfall
is non-decreasing and ends at rainfall_depth, final cumulative_percent is
100, duration matches the final time step), confirms every Task 2
scenario_id is accounted for (either generated or explicitly marked
pending_temporal_mapping_review - never silently missing), confirms no
rainfall values were invented for pending scenarios, and confirms HUC8
06020004 (Sequatchie) is handled via NOAA Atlas 14 Volume 2 as documented.

Writes a human-readable report and a machine-readable per-check summary.

Outputs:
  data/metadata/task3_hyetograph_validation_report.txt
  data/metadata/task3_hyetograph_validation_summary.csv

Usage:
  python scripts/validate_task3_hyetographs.py
"""

import argparse
import csv
import os
import sys

import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
SCENARIO_TABLE_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv"
)
LONG_TABLE_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_long.csv"
SUMMARY_TABLE_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_summary.csv"

REPORT_PATH_DEFAULT = "data/metadata/task3_hyetograph_validation_report.txt"
SUMMARY_CSV_PATH_DEFAULT = "data/metadata/task3_hyetograph_validation_summary.csv"

EXPECTED_SCENARIO_COUNT = 5664
TOLERANCE = 0.02  # inches, mass-balance tolerance (NOAA tables are rounded to 2 decimals)
SEQUATCHIE_HUC8_ID = "06020004"

RESOLVED_STATUS = "atlas14_hyetograph_generated"
PENDING_STATUS = "pending_temporal_mapping_review"


class Check:
    def __init__(self, name, category):
        self.name = name
        self.category = category
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
    parser.add_argument("--scenario-table", default=SCENARIO_TABLE_DEFAULT)
    parser.add_argument("--long-table", default=LONG_TABLE_DEFAULT)
    parser.add_argument("--summary-table", default=SUMMARY_TABLE_DEFAULT)
    parser.add_argument("--report", default=REPORT_PATH_DEFAULT)
    parser.add_argument("--summary-csv", default=SUMMARY_CSV_PATH_DEFAULT)
    args = parser.parse_args()

    for path in (args.scenario_table, args.long_table, args.summary_table):
        if not os.path.exists(path):
            print(f"ERROR: required input not found: {path}")
            sys.exit(2)

    scenarios = pd.read_csv(args.scenario_table, dtype={"huc8_id": str})
    long_df = pd.read_csv(args.long_table, dtype={"huc8_id": str, "temporal_distribution_area": str})
    summary_df = pd.read_csv(args.summary_table, dtype={"huc8_id": str, "temporal_distribution_area": str})

    checks = []

    def new_check(name, category):
        c = Check(name, category)
        checks.append(c)
        return c

    # --- Check 1: every Task 2 scenario_id is accounted for ---
    c = new_check("every_task2_scenario_id_accounted_for", "coverage")
    task2_ids = set(scenarios["scenario_id"])
    task3_ids = set(summary_df["scenario_id"])
    missing = task2_ids - task3_ids
    c.record(len(task2_ids), len(task2_ids) - len(missing),
             f"{len(missing)} scenario_ids missing entirely from Task 3 summary" if missing else None)

    # --- Check 2: expected scenario count ---
    c = new_check("scenario_count_matches_expected_5664", "coverage")
    c.record(1, 1 if len(summary_df) == EXPECTED_SCENARIO_COUNT else 0,
              f"got {len(summary_df)}, expected {EXPECTED_SCENARIO_COUNT}"
              if len(summary_df) != EXPECTED_SCENARIO_COUNT else None)

    resolved_summary = summary_df[summary_df["status"] == RESOLVED_STATUS]
    pending_summary = summary_df[summary_df["status"] == PENDING_STATUS]
    print(f"Resolved scenarios: {len(resolved_summary)}; pending: {len(pending_summary)}")

    # --- Check 3: per-scenario mass balance (resolved scenarios only) ---
    mass_balance = new_check("sum_incremental_equals_rainfall_depth", "mass_balance")
    final_cumulative = new_check("final_cumulative_rainfall_equals_rainfall_depth", "mass_balance")
    final_percent = new_check("final_cumulative_percent_equals_100", "mass_balance")
    non_decreasing = new_check("cumulative_rainfall_non_decreasing", "mass_balance")
    non_negative_incr = new_check("incremental_rainfall_non_negative", "mass_balance")
    duration_match = new_check("duration_hour_matches_final_time_hour", "mass_balance")
    no_dup_time = new_check("no_duplicate_time_steps_per_scenario", "mass_balance")

    resolved_long = long_df[long_df["status"] == RESOLVED_STATUS]
    grouped = resolved_long.groupby("scenario_id")
    n_scenarios = len(grouped)
    mass_balance.n_checked = final_cumulative.n_checked = final_percent.n_checked = n_scenarios
    non_decreasing.n_checked = non_negative_incr.n_checked = duration_match.n_checked = n_scenarios
    no_dup_time.n_checked = n_scenarios

    for scenario_id, group in grouped:
        group = group.sort_values("time_hour")
        rainfall_depth = group["rainfall_depth"].iloc[0]
        duration_hour = group["duration_hour"].iloc[0]

        total_incr = group["incremental_rainfall"].sum()
        if abs(total_incr - rainfall_depth) <= TOLERANCE:
            mass_balance.n_passed += 1
        else:
            mass_balance.failures.append(f"{scenario_id}: sum(incremental)={total_incr:.4f} vs depth={rainfall_depth:.4f}")

        final_cum = group["cumulative_rainfall"].iloc[-1]
        if abs(final_cum - rainfall_depth) <= TOLERANCE:
            final_cumulative.n_passed += 1
        else:
            final_cumulative.failures.append(f"{scenario_id}: final_cumulative={final_cum:.4f} vs depth={rainfall_depth:.4f}")

        final_pct = group["cumulative_percent"].iloc[-1]
        if abs(final_pct - 100.0) <= 0.5:
            final_percent.n_passed += 1
        else:
            final_percent.failures.append(f"{scenario_id}: final_cumulative_percent={final_pct}")

        cum_vals = group["cumulative_rainfall"].values
        if all(b >= a - 1e-6 for a, b in zip(cum_vals, cum_vals[1:])):
            non_decreasing.n_passed += 1
        else:
            non_decreasing.failures.append(f"{scenario_id}: cumulative_rainfall decreases somewhere")

        if (group["incremental_rainfall"] >= -1e-6).all():
            non_negative_incr.n_passed += 1
        else:
            non_negative_incr.failures.append(f"{scenario_id}: negative incremental_rainfall found")

        if abs(group["time_hour"].iloc[-1] - duration_hour) <= 0.51:
            duration_match.n_passed += 1
        else:
            duration_match.failures.append(
                f"{scenario_id}: final time_hour={group['time_hour'].iloc[-1]} vs duration_hour={duration_hour}"
            )

        if group["time_hour"].duplicated().sum() == 0:
            no_dup_time.n_passed += 1
        else:
            no_dup_time.failures.append(f"{scenario_id}: duplicate time_hour values found")

    # --- Check 4: rainfall_depth identical to Task 2 scenario table ---
    c = new_check("rainfall_depth_matches_task2_scenario_table", "consistency")
    task2_lookup = scenarios.set_index("scenario_id")["rainfall_depth"]
    mismatches = 0
    checked = 0
    for scenario_id, group in summary_df.groupby("scenario_id"):
        if scenario_id not in task2_lookup.index:
            continue
        checked += 1
        task2_val = task2_lookup.loc[scenario_id]
        task3_val = group["rainfall_depth"].iloc[0]
        try:
            if abs(float(task2_val) - float(task3_val)) > 1e-6:
                mismatches += 1
        except (ValueError, TypeError):
            if str(task2_val) != str(task3_val):
                mismatches += 1
    c.record(checked, checked - mismatches, f"{mismatches} scenario_ids have mismatched rainfall_depth" if mismatches else None)

    # --- Check 5/6: temporal_distribution_source / temporal_distribution_area populated ---
    c = new_check("temporal_distribution_source_populated", "field_completeness")
    n = len(long_df)
    n_ok = long_df["temporal_distribution_source"].notna().sum()
    c.record(n, n_ok, f"{n - n_ok} rows missing temporal_distribution_source" if n_ok < n else None)

    c = new_check("temporal_distribution_area_populated", "field_completeness")
    n_ok = long_df["temporal_distribution_area"].notna().sum()
    c.record(n, n_ok, f"{n - n_ok} rows missing temporal_distribution_area" if n_ok < n else None)

    # --- Check 7: Sequatchie handled correctly ---
    c = new_check("sequatchie_uses_volume2", "special_case")
    seq_rows = summary_df[summary_df["huc8_id"] == SEQUATCHIE_HUC8_ID]
    seq_ok = (
        len(seq_rows) > 0
        and (seq_rows["atlas14_volume_temporal_distribution"].astype(str) == "2").all()
        and (seq_rows["temporal_distribution_area"].astype(str) == "general").all()
    )
    c.record(1, 1 if seq_ok else 0, "" if seq_ok else f"{len(seq_rows)} Sequatchie rows, volume/area attribution incorrect")

    # --- Check 8: no invented rainfall values for pending scenarios ---
    c = new_check("no_invented_values_for_pending_scenarios", "integrity")
    pending_long = long_df[long_df["status"] == PENDING_STATUS]
    invented = pending_long[pending_long["cumulative_rainfall"].notna() | pending_long["incremental_rainfall"].notna()]
    c.record(len(pending_long), len(pending_long) - len(invented),
              f"{len(invented)} pending rows have non-null cumulative/incremental values" if len(invented) else None)

    # --- Print + write report ---
    lines = []
    lines.append("Task 3 Hyetograph Validation Report")
    lines.append("=" * 40)
    lines.append(f"Total Task 2 scenarios: {len(task2_ids)}")
    lines.append(f"Total Task 3 summary rows: {len(summary_df)}")
    lines.append(f"Resolved (hyetograph generated): {len(resolved_summary)}")
    lines.append(f"Pending (middle_peak, mapping_review_required): {len(pending_summary)}")
    lines.append("")

    any_fail = False
    for c in checks:
        line = f"[{c.status}] {c.name} ({c.category}): {c.n_passed}/{c.n_checked}"
        lines.append(line)
        print(line)
        if c.status == "FAIL":
            any_fail = True
            for f in c.failures[:20]:
                lines.append(f"    - {f}")
                print(f"    - {f}")
            if len(c.failures) > 20:
                lines.append(f"    ... and {len(c.failures) - 20} more")

    lines.append("")
    lines.append("Known, expected non-failure: 1,416 scenarios (middle_peak) are intentionally "
                  "pending_temporal_mapping_review, not failures - see task3_temporal_pattern_mapping.csv.")
    lines.append("")
    lines.append("ALL CHECKS PASSED" if not any_fail else "SOME CHECKS FAILED - see details above")

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nWrote report to {args.report}")

    with open(args.summary_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["check_name", "category", "n_checked", "n_passed", "n_failed", "status"])
        writer.writeheader()
        for c in checks:
            writer.writerow({
                "check_name": c.name, "category": c.category, "n_checked": c.n_checked,
                "n_passed": c.n_passed, "n_failed": c.n_checked - c.n_passed, "status": c.status,
            })
    print(f"Wrote {len(checks)} rows to {args.summary_csv}")

    if any_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
