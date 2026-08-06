"""
Task 1 - Step 4: Build the controlled synthetic storm scenario template.

This generates the full cross-product of HUC8 IDs x return periods x
durations x temporal patterns. It is a SCENARIO DESIGN table only -
rainfall depths are NOT invented here. They are left blank/TBD and must
be extracted from NOAA Atlas 14 PFDS in a later step.

Input:  data/processed/huc_summary/alabama_huc8_summary.csv
Output: data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_template.csv
"""

import itertools

import pandas as pd

HUC_SUMMARY_PATH = "data/processed/huc_summary/alabama_huc8_summary.csv"
OUTPUT_PATH = "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_template.csv"

RETURN_PERIODS_YEAR = [5, 10, 50, 100, 200, 500]
DURATIONS_HOUR = [6, 12, 24, 96]
TEMPORAL_PATTERNS = ["early_peak", "middle_peak", "late_peak", "balanced"]

RAINFALL_DEPTH_SOURCE = "NOAA Atlas 14 PFDS - to be extracted"
TEMPORAL_DISTRIBUTION_SOURCE = "NOAA Atlas 14 temporal distribution - to be assigned"
STATUS = "pending_atlas14_depth"


def main():
    huc_df = pd.read_csv(HUC_SUMMARY_PATH, dtype={"huc8_id": str})

    rows = []
    for _, huc in huc_df.iterrows():
        combos = itertools.product(RETURN_PERIODS_YEAR, DURATIONS_HOUR, TEMPORAL_PATTERNS)
        for return_period, duration, pattern in combos:
            scenario_id = (
                f"{huc['huc8_id']}_RP{return_period}_D{duration}h_{pattern}"
            )
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "huc8_id": huc["huc8_id"],
                    "huc8_name": huc["huc8_name"],
                    "return_period_year": return_period,
                    "duration_hour": duration,
                    "temporal_pattern": pattern,
                    "rainfall_depth": "TBD",
                    "rainfall_depth_unit": "in",
                    "rainfall_depth_source": RAINFALL_DEPTH_SOURCE,
                    "temporal_distribution_source": TEMPORAL_DISTRIBUTION_SOURCE,
                    "status": STATUS,
                    "notes": "",
                }
            )

    scenarios = pd.DataFrame(rows)
    scenarios.to_csv(OUTPUT_PATH, index=False)

    n_huc = huc_df["huc8_id"].nunique()
    n_expected = n_huc * len(RETURN_PERIODS_YEAR) * len(DURATIONS_HOUR) * len(TEMPORAL_PATTERNS)
    print(f"HUC8 count: {n_huc}")
    print(f"Expected rows: {n_expected}")
    print(f"Wrote {len(scenarios)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
