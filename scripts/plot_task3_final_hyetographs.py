"""
Task 3 Final Step 9: Diagnostic plots for Product A and Product B
(matplotlib only, curated selection - not one plot per scenario).

Representative HUC8s (same as the original Task 3 run, chosen from HUC8
centroid latitude, restricted to clean/non-low-confidence temporal
assignments):
  - Northern Alabama:  Guntersville Lake (06030001)
  - Central Alabama:   Cahaba (03150202)
  - Southern/coastal:  Mobile Bay (03160205)

Product A plots (figures/task3_main_noaa_native/):
  1-3. One figure per location: all 5 NOAA-native P50 cases, 100yr/24hr.
  4. Duration comparison (Cahaba, all_cases_p50): 6/12/24/96-hr.
  5. Return-period comparison (Cahaba, all_cases_p50): 5/10/50/100/200/500-yr.

Product B plots (figures/task3_full_temporal_sensitivity/):
  6-10. One figure per NOAA case (First/Second/Third/Fourth-Quartile, All
        Cases), Cahaba, 100yr/24hr, comparing all 9 available percentile
        curves (10%-90%) for that case.

Product B's long-format table is ~1.1 GB, so it is read in filtered chunks
(only rows matching the plotted HUC8/return-period/duration are kept) to
avoid loading the whole file into memory.

Usage:
  python scripts/plot_task3_final_hyetographs.py
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
LONG_A_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_main_noaa_native_long.csv"
LONG_B_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_long.csv"
OUTPUT_DIR_A_DEFAULT = "figures/task3_main_noaa_native"
OUTPUT_DIR_B_DEFAULT = "figures/task3_full_temporal_sensitivity"

NORTH_HUC8 = ("06030001", "Guntersville Lake")
CENTRAL_HUC8 = ("03150202", "Cahaba")
SOUTH_HUC8 = ("03160205", "Mobile Bay")

CASES_A = ["first_quartile_peak_p50", "second_quartile_peak_p50", "third_quartile_peak_p50",
           "fourth_quartile_peak_p50", "all_cases_p50"]
CASE_COLORS_A = {
    "first_quartile_peak_p50": "#1b6ca8", "second_quartile_peak_p50": "#2e9e5b",
    "third_quartile_peak_p50": "#d4a017", "fourth_quartile_peak_p50": "#c0392b",
    "all_cases_p50": "#7f7f7f",
}
CASE_LABELS_A = {
    "first_quartile_peak_p50": "First-Quartile (P50)", "second_quartile_peak_p50": "Second-Quartile (P50)",
    "third_quartile_peak_p50": "Third-Quartile (P50)", "fourth_quartile_peak_p50": "Fourth-Quartile (P50)",
    "all_cases_p50": "All Cases (P50)",
}

PRODUCT_B_CASES = [
    ("first_quartile", "First-Quartile Case"), ("second_quartile", "Second-Quartile Case"),
    ("third_quartile", "Third-Quartile Case"), ("fourth_quartile", "Fourth-Quartile Case"),
    ("all_cases", "All Cases"),
]
PERCENTILES_B = [f"{p}0" for p in range(1, 10)]  # 10..90


def load_curve_a(long_df, huc8_id, rp, dur, case):
    return long_df[
        (long_df["huc8_id"] == huc8_id) & (long_df["return_period_year"] == rp)
        & (long_df["duration_hour"] == dur) & (long_df["temporal_case_final"] == case)
    ].sort_values("time_hour")


def plot_location_figure_a(long_df, huc8_id, huc8_name, output_dir, inventory_rows):
    fig, (ax_incr, ax_cum) = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    for case in CASES_A:
        curve = load_curve_a(long_df, huc8_id, 100, 24, case)
        if curve.empty:
            continue
        color = CASE_COLORS_A[case]
        ax_incr.plot(curve["time_hour"], curve["incremental_rainfall"], marker="o", markersize=3,
                     color=color, label=CASE_LABELS_A[case])
        ax_cum.plot(curve["time_hour"], curve["cumulative_rainfall"], color=color, label=CASE_LABELS_A[case])

    ax_incr.set_title(f"{huc8_name} (HUC8 {huc8_id}) - 100-year, 24-hour design storm - NOAA-native cases (P50)")
    ax_incr.set_ylabel("Incremental rainfall (in)")
    ax_incr.legend(loc="upper right", fontsize=8)
    ax_incr.grid(alpha=0.3)
    ax_cum.set_xlabel("Time (hours)")
    ax_cum.set_ylabel("Cumulative rainfall (in)")
    ax_cum.grid(alpha=0.3)
    fig.tight_layout()

    filename = f"hyetograph_A_{huc8_id}_{huc8_name.replace(' ', '_')}_100yr_24hr.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath}")
    inventory_rows.append({
        "figure_file": filename, "product": "A", "figure_type": "location_case_comparison",
        "huc8_id": huc8_id, "huc8_name": huc8_name, "return_period_year": 100, "duration_hour": 24,
        "temporal_case_final": ";".join(CASES_A), "noaa_temporal_case": "all 5 NOAA cases",
        "noaa_percentile_or_curve": "50%",
        "description": f"Incremental and cumulative rainfall vs time for {huc8_name}, 100-yr/24-hr, "
                        "all 5 NOAA-native cases at P50.",
        "status": "generated",
    })


def plot_duration_comparison_a(long_df, huc8_id, huc8_name, output_dir, inventory_rows):
    fig, ax = plt.subplots(figsize=(9, 5))
    durations = [6, 12, 24, 96]
    colors = cm.viridis([i / (len(durations) - 1) for i in range(len(durations))])
    for dur, color in zip(durations, colors):
        curve = load_curve_a(long_df, huc8_id, 100, dur, "all_cases_p50")
        if curve.empty:
            continue
        ax.plot(curve["time_hour"], curve["incremental_rainfall"], color=color, label=f"{dur}-hour")
    ax.set_title(f"{huc8_name} (HUC8 {huc8_id}) - duration comparison, 100-year storm, All Cases (P50)")
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Incremental rainfall (in)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    filename = f"duration_comparison_A_{huc8_id}_{huc8_name.replace(' ', '_')}_100yr.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath}")
    inventory_rows.append({
        "figure_file": filename, "product": "A", "figure_type": "duration_comparison",
        "huc8_id": huc8_id, "huc8_name": huc8_name, "return_period_year": 100, "duration_hour": "6;12;24;96",
        "temporal_case_final": "all_cases_p50", "noaa_temporal_case": "All Cases",
        "noaa_percentile_or_curve": "50%",
        "description": f"Duration comparison for {huc8_name}, 100-yr storm, All-Cases P50 curve.",
        "status": "generated",
    })


def plot_return_period_comparison_a(long_df, huc8_id, huc8_name, output_dir, inventory_rows):
    fig, ax = plt.subplots(figsize=(9, 5))
    return_periods = [5, 10, 50, 100, 200, 500]
    colors = cm.plasma([i / (len(return_periods) - 1) for i in range(len(return_periods))])
    for rp, color in zip(return_periods, colors):
        curve = load_curve_a(long_df, huc8_id, rp, 24, "all_cases_p50")
        if curve.empty:
            continue
        ax.plot(curve["time_hour"], curve["incremental_rainfall"], color=color, label=f"{rp}-year")
    ax.set_title(f"{huc8_name} (HUC8 {huc8_id}) - return period comparison, 24-hour storm, All Cases (P50)")
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Incremental rainfall (in)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    filename = f"return_period_comparison_A_{huc8_id}_{huc8_name.replace(' ', '_')}_24hr.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath}")
    inventory_rows.append({
        "figure_file": filename, "product": "A", "figure_type": "return_period_comparison",
        "huc8_id": huc8_id, "huc8_name": huc8_name,
        "return_period_year": "5;10;50;100;200;500", "duration_hour": 24,
        "temporal_case_final": "all_cases_p50", "noaa_temporal_case": "All Cases",
        "noaa_percentile_or_curve": "50%",
        "description": f"Return-period comparison for {huc8_name}, 24-hr storm, All-Cases P50 curve.",
        "status": "generated",
    })


def load_product_b_subset(long_b_path, huc8_id, rp, dur, chunksize=300000):
    """Read only the rows matching huc8_id/rp/dur from the large Product B long file."""
    chunks = []
    for chunk in pd.read_csv(long_b_path, chunksize=chunksize, dtype={
        "huc8_id": str, "temporal_distribution_area": str,
    }):
        match = chunk[
            (chunk["huc8_id"] == huc8_id) & (chunk["return_period_year"] == rp)
            & (chunk["duration_hour"] == dur)
        ]
        if not match.empty:
            chunks.append(match)
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def plot_product_b_case(subset_df, case_slug, case_label, huc8_id, huc8_name, output_dir, inventory_rows):
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = cm.coolwarm([i / (len(PERCENTILES_B) - 1) for i in range(len(PERCENTILES_B))])
    any_plotted = False
    for pct, color in zip(PERCENTILES_B, colors):
        curve = subset_df[
            (subset_df["noaa_temporal_case"] == case_label) & (subset_df["noaa_percentile_or_curve"] == f"{pct}%")
        ].sort_values("time_hour")
        if curve.empty:
            continue
        any_plotted = True
        ax.plot(curve["time_hour"], curve["incremental_rainfall"], color=color, label=f"{pct}%")

    ax.set_title(f"{huc8_name} (HUC8 {huc8_id}) - 100-yr/24-hr - NOAA {case_label} - all available percentiles")
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Incremental rainfall (in)")
    ax.legend(loc="upper right", fontsize=7, ncol=2, title="Percentile")
    ax.grid(alpha=0.3)
    fig.tight_layout()

    filename = f"percentile_comparison_B_{huc8_id}_{case_slug}_100yr_24hr.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath} (data plotted: {any_plotted})")
    inventory_rows.append({
        "figure_file": filename, "product": "B", "figure_type": "percentile_sensitivity_comparison",
        "huc8_id": huc8_id, "huc8_name": huc8_name, "return_period_year": 100, "duration_hour": 24,
        "temporal_case_final": f"{case_slug}_p10..p90", "noaa_temporal_case": case_label,
        "noaa_percentile_or_curve": "10%-90% (all 9)",
        "description": f"Incremental rainfall vs time for {huc8_name}, 100-yr/24-hr, NOAA {case_label}, "
                        "comparing all 9 available official percentile curves.",
        "status": "generated" if any_plotted else "no_data_found",
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--long-a", default=LONG_A_DEFAULT)
    parser.add_argument("--long-b", default=LONG_B_DEFAULT)
    parser.add_argument("--output-dir-a", default=OUTPUT_DIR_A_DEFAULT)
    parser.add_argument("--output-dir-b", default=OUTPUT_DIR_B_DEFAULT)
    args = parser.parse_args()

    if not os.path.exists(args.long_a):
        raise FileNotFoundError(f"Product A long table not found: {args.long_a}")
    if not os.path.exists(args.long_b):
        raise FileNotFoundError(f"Product B long table not found: {args.long_b}")

    os.makedirs(args.output_dir_a, exist_ok=True)
    os.makedirs(args.output_dir_b, exist_ok=True)

    # === Product A ===
    long_a = pd.read_csv(args.long_a, dtype={"huc8_id": str, "temporal_distribution_area": str})
    inventory_a = []
    for huc8_id, huc8_name in (NORTH_HUC8, CENTRAL_HUC8, SOUTH_HUC8):
        plot_location_figure_a(long_a, huc8_id, huc8_name, args.output_dir_a, inventory_a)
    plot_duration_comparison_a(long_a, CENTRAL_HUC8[0], CENTRAL_HUC8[1], args.output_dir_a, inventory_a)
    plot_return_period_comparison_a(long_a, CENTRAL_HUC8[0], CENTRAL_HUC8[1], args.output_dir_a, inventory_a)

    inv_a_path = os.path.join(args.output_dir_a, "task3_main_plot_inventory.csv")
    fieldnames = [
        "figure_file", "product", "figure_type", "huc8_id", "huc8_name", "return_period_year",
        "duration_hour", "temporal_case_final", "noaa_temporal_case", "noaa_percentile_or_curve",
        "description", "status",
    ]
    with open(inv_a_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inventory_a)
    print(f"Wrote {len(inventory_a)} rows to {inv_a_path}")

    # === Product B ===
    print("Reading Product B long table in filtered chunks (this file is ~1.1 GB)...")
    subset_b = load_product_b_subset(args.long_b, CENTRAL_HUC8[0], 100, 24)
    print(f"Loaded {len(subset_b)} matching rows for {CENTRAL_HUC8[1]}, 100yr/24hr.")

    inventory_b = []
    for case_slug, case_label in PRODUCT_B_CASES:
        plot_product_b_case(subset_b, case_slug, case_label, CENTRAL_HUC8[0], CENTRAL_HUC8[1],
                             args.output_dir_b, inventory_b)

    inv_b_path = os.path.join(args.output_dir_b, "task3_full_sensitivity_plot_inventory.csv")
    with open(inv_b_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inventory_b)
    print(f"Wrote {len(inventory_b)} rows to {inv_b_path}")


if __name__ == "__main__":
    main()
