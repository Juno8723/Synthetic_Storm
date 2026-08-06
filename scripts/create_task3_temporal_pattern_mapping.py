"""
Task 3D: Map project scenario temporal_pattern labels to official NOAA
Atlas 14 temporal distribution curves.

NOAA Atlas 14 (Volumes 2 and 9, and generally across the Atlas 14 series)
tabulates temporal distributions as five groups per duration:
  - First-Quartile Case  (greatest precipitation fraction in 1st quarter)
  - Second-Quartile Case (greatest precipitation fraction in 2nd quarter)
  - Third-Quartile Case  (greatest precipitation fraction in 3rd quarter)
  - Fourth-Quartile Case (greatest precipitation fraction in 4th quarter)
  - All Cases            (combined distribution, not conditioned on quartile)
and within each group, nine percentile curves (10% to 90%) describing the
spread of realizations; the 50th-percentile curve is the median/typical
curve for that group.

This project's four temporal_pattern labels map as follows:

  early_peak   -> First-Quartile Case, 50th-percentile curve
                  RESOLVED: "early_peak" unambiguously means the greatest
                  precipitation fraction occurs early in the storm, which is
                  exactly NOAA's definition of the First-Quartile Case.

  late_peak    -> Fourth-Quartile Case, 50th-percentile curve
                  RESOLVED: same logic, mirrored to the last quarter.

  balanced     -> All Cases, 50th-percentile curve
                  RESOLVED: "balanced" (not conditioned on a specific peak
                  timing) corresponds to NOAA's combined, case-independent
                  distribution - the most defensible standard/typical curve
                  when no specific quartile-case timing is assumed.

  middle_peak  -> AMBIGUOUS, NOT RESOLVED.
                  NOAA provides TWO distinct "middle-timing" cases (Second-
                  Quartile Case and Third-Quartile Case), but this project
                  defines only ONE "middle_peak" label. Nothing in the
                  official NOAA data files or their embedded documentation
                  (inspected in Task 3A/3C) designates one of these two
                  cases as "the" middle case, and no combination/averaging
                  rule is documented. An attempt was made to consult the
                  NOAA Atlas 14 Volume 9 PDF
                  (https://www.weather.gov/media/owp/hdsc_documents/Atlas14_Volume9.pdf)
                  for additional guidance, but no PDF text-extraction tool
                  (pdftotext / pypdf / pdfplumber) is installed in this
                  environment, and installing one requires approval that was
                  not sought for this specific, narrow purpose. Per project
                  instructions, this ambiguity is NOT silently resolved by
                  picking Second-Quartile or Third-Quartile arbitrarily.
                  status = mapping_review_required for every middle_peak row.
                  Hyetograph generation (Task 3E) does not produce final
                  hyetographs for middle_peak scenarios as a result.

Output:
  data/metadata/task3_temporal_pattern_mapping.csv

Usage:
  python scripts/create_task3_temporal_pattern_mapping.py
"""

import argparse
import csv
import os

# --- Section: project defaults (documented, not hidden) ---
DURATIONS_HOUR = [6, 12, 24, 96]
REGION_COMBOS = [
    ("9", "1", "Mississippi Valley region"),
    ("9", "2", "Southeast region"),
    ("2", "general", "Ohio River Basin and Surrounding States (single area)"),
]
MEDIAN_CURVE = "50%"
OUTPUT_PATH_DEFAULT = "data/metadata/task3_temporal_pattern_mapping.csv"

RESOLVED_MAPPING_RULES = {
    "early_peak": {
        "noaa_temporal_case": "First-Quartile Case",
        "noaa_quartile_or_group": "1",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": (
            "NOAA First-Quartile Case: greatest precipitation fraction occurs in the "
            "first quarter of the storm duration - matches 'early_peak' by definition. "
            "50th-percentile (median) curve used as the representative curve within the case."
        ),
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    "late_peak": {
        "noaa_temporal_case": "Fourth-Quartile Case",
        "noaa_quartile_or_group": "4",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": (
            "NOAA Fourth-Quartile Case: greatest precipitation fraction occurs in the "
            "last quarter of the storm duration - matches 'late_peak' by definition. "
            "50th-percentile (median) curve used as the representative curve within the case."
        ),
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    "balanced": {
        "noaa_temporal_case": "All Cases",
        "noaa_quartile_or_group": "combined",
        "noaa_percentile_or_curve": MEDIAN_CURVE,
        "mapping_rule": (
            "NOAA All Cases: the combined distribution not conditioned on any specific "
            "quartile-case timing - the most defensible standard/typical curve for a "
            "'balanced' (non-peaked) scenario label. 50th-percentile (median) curve used."
        ),
        "mapping_confidence": "high",
        "status": "resolved",
        "notes": "",
    },
    "middle_peak": {
        "noaa_temporal_case": "AMBIGUOUS: Second-Quartile Case OR Third-Quartile Case",
        "noaa_quartile_or_group": "2_or_3",
        "noaa_percentile_or_curve": "",
        "mapping_rule": (
            "NOAA provides two distinct middle-timing cases (Second-Quartile: peak in "
            "2nd quarter; Third-Quartile: peak in 3rd quarter) but this project defines "
            "only one 'middle_peak' label. No official NOAA documentation found "
            "designating one as standard, or specifying a combination rule; PDF "
            "documentation could not be text-extracted in this environment (no "
            "pdftotext/pypdf/pdfplumber installed, and install was not requested for "
            "this narrow purpose). Not resolved - do not guess."
        ),
        "mapping_confidence": "unresolved_ambiguous",
        "status": "mapping_review_required",
        "notes": (
            "Hyetograph generation (Task 3E) does not produce final hyetographs for "
            "middle_peak scenarios until a human reviewer selects Second-Quartile, "
            "Third-Quartile, or an explicitly documented combination rule."
        ),
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=OUTPUT_PATH_DEFAULT)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    rows = []
    for temporal_pattern, rule in RESOLVED_MAPPING_RULES.items():
        for atlas14_volume, temporal_distribution_area, region_name in REGION_COMBOS:
            for duration_hour in DURATIONS_HOUR:
                rows.append({
                    "temporal_pattern": temporal_pattern,
                    "atlas14_volume": atlas14_volume,
                    "temporal_distribution_area": temporal_distribution_area,
                    "temporal_distribution_region_name": region_name,
                    "duration_hour": duration_hour,
                    "noaa_temporal_case": rule["noaa_temporal_case"],
                    "noaa_quartile_or_group": rule["noaa_quartile_or_group"],
                    "noaa_percentile_or_curve": rule["noaa_percentile_or_curve"],
                    "mapping_rule": rule["mapping_rule"],
                    "mapping_confidence": rule["mapping_confidence"],
                    "status": rule["status"],
                    "notes": rule["notes"],
                })

    fieldnames = [
        "temporal_pattern", "atlas14_volume", "temporal_distribution_area",
        "temporal_distribution_region_name", "duration_hour", "noaa_temporal_case",
        "noaa_quartile_or_group", "noaa_percentile_or_curve", "mapping_rule",
        "mapping_confidence", "status", "notes",
    ]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    n_resolved = sum(1 for r in rows if r["status"] == "resolved")
    n_review = sum(1 for r in rows if r["status"] == "mapping_review_required")
    print(f"Wrote {len(rows)} rows to {args.output}")
    print(f"  resolved: {n_resolved}")
    print(f"  mapping_review_required: {n_review}")


if __name__ == "__main__":
    main()
