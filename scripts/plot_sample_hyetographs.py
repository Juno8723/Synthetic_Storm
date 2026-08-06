"""
Task 3G: Selected diagnostic plots for Task 3 hyetographs (matplotlib only).

This is NOT an exhaustive plotting script - it produces a small, curated
set of diagnostic figures, not one plot per scenario (5,664 scenarios would
be excessive). Representative HUC8s (one northern, one central, one
southern/coastal Alabama) were chosen from the HUC8 shapefile's centroid
latitude, restricted to HUC8s with a clean (non-low-confidence) temporal
region assignment (Task 3B):
  - Northern Alabama:  Guntersville Lake (06030001)
  - Central Alabama:   Cahaba (03150202)
  - Southern/coastal:  Mobile Bay (03160205)

IMPORTANT - middle_peak is unresolved (Task 3D): NOAA provides two
candidate "middle" cases (Second-Quartile, Third-Quartile) with no
documented tiebreaker, so no hyetograph time series exists for any
middle_peak scenario. Plots that were requested for middle_peak
combinations are NOT fabricated:
  - The three location plots (north/central/south) show only the three
    RESOLVED patterns (early_peak, late_peak, balanced) and are annotated
    to note that middle_peak is pending.
  - The duration-comparison plot shows only the one resolved combination
    (100yr-96hr-balanced) with an annotation listing the three pending
    (middle_peak) combinations that could not be plotted.
  - The return-period-comparison plot is ENTIRELY middle_peak (all six
    combinations), so no real curve can be drawn; a placeholder figure
    states this plainly rather than a blank or fabricated chart.

Output folder: figures/task3_hyetographs/
Plot inventory: figures/task3_hyetographs/task3_plot_inventory.csv

Usage:
  python scripts/plot_sample_hyetographs.py
"""

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
LONG_TABLE_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_long.csv"
OUTPUT_DIR_DEFAULT = "figures/task3_hyetographs"

NORTH_HUC8 = ("06030001", "Guntersville Lake")
CENTRAL_HUC8 = ("03150202", "Cahaba")
SOUTH_HUC8 = ("03160205", "Mobile Bay")

RESOLVED_PATTERNS = ["early_peak", "late_peak", "balanced"]
PATTERN_COLORS = {"early_peak": "#1b6ca8", "late_peak": "#c0392b", "balanced": "#7f7f7f"}
PATTERN_LABELS = {"early_peak": "Early peak", "late_peak": "Late peak", "balanced": "Balanced (all cases)"}


def load_curve(long_df, huc8_id, return_period, duration_hour, temporal_pattern):
    sub = long_df[
        (long_df["huc8_id"] == huc8_id)
        & (long_df["return_period_year"] == return_period)
        & (long_df["duration_hour"] == duration_hour)
        & (long_df["temporal_pattern"] == temporal_pattern)
        & (long_df["status"] == "atlas14_hyetograph_generated")
    ].sort_values("time_hour")
    return sub


def plot_location_figure(long_df, huc8_id, huc8_name, output_dir, inventory_rows):
    """One figure per location: incremental (top) + cumulative (bottom), 3 resolved patterns."""
    fig, (ax_incr, ax_cum) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)

    any_data = False
    for pattern in RESOLVED_PATTERNS:
        curve = load_curve(long_df, huc8_id, 100, 24, pattern)
        if curve.empty:
            continue
        any_data = True
        color = PATTERN_COLORS[pattern]
        ax_incr.plot(curve["time_hour"], curve["incremental_rainfall"], marker="o", markersize=3,
                     color=color, label=PATTERN_LABELS[pattern])
        ax_cum.plot(curve["time_hour"], curve["cumulative_rainfall"], color=color,
                    label=PATTERN_LABELS[pattern])

    ax_incr.set_title(f"{huc8_name} (HUC8 {huc8_id}) - 100-year, 24-hour design storm")
    ax_incr.set_ylabel("Incremental rainfall (in)")
    ax_incr.legend(loc="upper right", fontsize=8)
    ax_incr.grid(alpha=0.3)

    ax_cum.set_xlabel("Time (hours)")
    ax_cum.set_ylabel("Cumulative rainfall (in)")
    ax_cum.grid(alpha=0.3)
    ax_cum.text(
        0.02, 0.95,
        "Note: 'middle_peak' pattern omitted - NOAA temporal-case mapping\n"
        "for middle_peak is unresolved (ambiguous between Second- and\n"
        "Third-Quartile Case); see task3_temporal_pattern_mapping.csv.",
        transform=ax_cum.transAxes, fontsize=7, va="top",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
    )

    fig.tight_layout()
    filename = f"hyetograph_{huc8_id}_{huc8_name.replace(' ', '_')}_100yr_24hr.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath} (data plotted: {any_data})")

    inventory_rows.append({
        "figure_file": filename, "figure_type": "location_pattern_comparison",
        "huc8_id": huc8_id, "huc8_name": huc8_name, "return_period_year": 100, "duration_hour": 24,
        "temporal_pattern": "early_peak;late_peak;balanced (middle_peak pending)",
        "description": f"Incremental and cumulative rainfall vs time for {huc8_name}, "
                        "100-yr/24-hr storm, three resolved temporal patterns.",
        "status": "generated",
    })


def plot_duration_comparison(long_df, huc8_id, huc8_name, output_dir, inventory_rows):
    fig, ax = plt.subplots(figsize=(8, 5))
    curve = load_curve(long_df, huc8_id, 100, 96, "balanced")
    if not curve.empty:
        ax.plot(curve["time_hour"], curve["incremental_rainfall"], color="#7f7f7f",
                label="96-hour, balanced")
    ax.set_title(f"{huc8_name} (HUC8 {huc8_id}) - duration comparison, 100-year storm")
    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Incremental rainfall (in)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    ax.text(
        0.02, 0.95,
        "Pending (middle_peak mapping unresolved, not plotted):\n"
        "  100yr-6hr-middle_peak\n  100yr-12hr-middle_peak\n  100yr-24hr-middle_peak",
        transform=ax.transAxes, fontsize=8, va="top",
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
    )
    fig.tight_layout()
    filename = f"duration_comparison_{huc8_id}_{huc8_name.replace(' ', '_')}_100yr.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath} (1 of 4 requested combinations plotted; 3 pending)")

    inventory_rows.append({
        "figure_file": filename, "figure_type": "duration_comparison",
        "huc8_id": huc8_id, "huc8_name": huc8_name, "return_period_year": 100, "duration_hour": "6;12;24;96",
        "temporal_pattern": "middle_peak (pending) / balanced (plotted)",
        "description": "Duration comparison for 100-yr storm; only 96hr-balanced is plotted "
                        "because the other three requested combinations use the unresolved "
                        "middle_peak temporal pattern.",
        "status": "partially_generated_pending_mapping_review",
    })


def plot_return_period_placeholder(huc8_id, huc8_name, output_dir, inventory_rows):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.axis("off")
    ax.text(
        0.5, 0.5,
        "Return-period comparison BLOCKED\n\n"
        f"{huc8_name} (HUC8 {huc8_id}), 24-hour duration,\n"
        "return periods 5/10/50/100/200/500-year, middle_peak pattern\n\n"
        "All six requested combinations use the 'middle_peak' temporal pattern,\n"
        "whose NOAA temporal-case mapping is unresolved (ambiguous between\n"
        "Second-Quartile and Third-Quartile Case; no documented tiebreaker).\n"
        "No hyetograph time series exists for these scenarios, so no curves\n"
        "are plotted here. See task3_temporal_pattern_mapping.csv and\n"
        "scripts/README_task3_hyetograph_generation.md for details.",
        ha="center", va="center", fontsize=10, transform=ax.transAxes,
        bbox=dict(boxstyle="round", facecolor="mistyrose", alpha=0.9),
    )
    fig.tight_layout()
    filename = f"return_period_comparison_{huc8_id}_{huc8_name.replace(' ', '_')}_BLOCKED.png"
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"Wrote {filepath} (placeholder - fully blocked by middle_peak ambiguity)")

    inventory_rows.append({
        "figure_file": filename, "figure_type": "return_period_comparison_placeholder",
        "huc8_id": huc8_id, "huc8_name": huc8_name,
        "return_period_year": "5;10;50;100;200;500", "duration_hour": 24,
        "temporal_pattern": "middle_peak (unresolved)",
        "description": "Placeholder: all 6 requested return-period combinations use the "
                        "unresolved middle_peak temporal pattern; no data could be plotted.",
        "status": "blocked_pending_mapping_review",
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--long-table", default=LONG_TABLE_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    args = parser.parse_args()

    if not os.path.exists(args.long_table):
        raise FileNotFoundError(f"Long hyetograph table not found: {args.long_table}")

    os.makedirs(args.output_dir, exist_ok=True)
    long_df = pd.read_csv(args.long_table, dtype={"huc8_id": str, "temporal_distribution_area": str})

    inventory_rows = []

    for huc8_id, huc8_name in (NORTH_HUC8, CENTRAL_HUC8, SOUTH_HUC8):
        plot_location_figure(long_df, huc8_id, huc8_name, args.output_dir, inventory_rows)

    plot_duration_comparison(long_df, CENTRAL_HUC8[0], CENTRAL_HUC8[1], args.output_dir, inventory_rows)
    plot_return_period_placeholder(CENTRAL_HUC8[0], CENTRAL_HUC8[1], args.output_dir, inventory_rows)

    inventory_path = os.path.join(args.output_dir, "task3_plot_inventory.csv")
    fieldnames = [
        "figure_file", "figure_type", "huc8_id", "huc8_name", "return_period_year",
        "duration_hour", "temporal_pattern", "description", "status",
    ]
    with open(inventory_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(inventory_rows)
    print(f"Wrote {len(inventory_rows)} rows to {inventory_path}")


if __name__ == "__main__":
    main()
