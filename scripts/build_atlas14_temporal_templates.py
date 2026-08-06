"""
Task 3C: Parse official NOAA Atlas 14 temporal distribution curve files into
a single unified long-format table.

Two different NOAA file layouts must be handled (confirmed by direct
inspection on 2026-07-09):

Volume 9 (Southeastern States, files se_<area>_<dur>h_temporal.csv):
  - "Long" layout: one row per absolute time step (0 to duration_hour, in
    0.5-hour increments).
  - Columns are the percentile/curve labels, in DESCENDING order as written
    in the file's own header line (e.g. "hours,90%,80%,70%,...,10%") - the
    header line is parsed directly rather than assuming an order.
  - Five stacked tables per file, each preceded by a header line: "...FOR
    FIRST-QUARTILE CASES", "...SECOND-QUARTILE CASES", "...THIRD-QUARTILE
    CASES", "...FOURTH-QUARTILE CASES", "...FOR ALL CASES".

Volume 2 (Ohio River Basin, files orb_general_<dur>h_temporal.csv):
  - "Wide"/transposed layout: one row per percentile/curve label (10% to
    90%, ascending), columns are 13 fixed steps of PERCENT OF DURATION
    (0.0, 8.3, 16.7, ..., 100.0), not absolute hours.
  - Five stacked tables per file, each preceded by a bare header line:
    "First Quartile", "Second Quartile", "Third Quartile", "Fourth
    Quartile", "All Cases".

To produce one common `time_hour` axis, the Volume 2 percent-of-duration
column values are converted to absolute hours via
`time_hour = (percent_of_duration / 100) * duration_hour`. This is an exact
algebraic rescaling of the file's own stated axis (the 13 original points
are preserved exactly - none are added, removed, smoothed, or
interpolated); it is documented here and in each output row's `notes`
field, not silently applied.

No curve is smoothed. No missing value is interpolated or invented - if a
value is missing from the source file, this script does not fill it in.

This is the Task 3 Final version of this script (Step 3). It writes to a
new "_final" output path (the original
atlas14_temporal_distribution_templates.csv from the initial Task 3 run is
preserved untouched) and drops the redundant `noaa_quartile_or_group`
column (kept in the original run, not part of the final required schema)
since `noaa_temporal_case` already fully identifies the case.

Output:
  data/processed/hyetograph_templates/atlas14_temporal_distribution_templates_final.csv

Usage:
  python scripts/build_atlas14_temporal_templates.py
"""

import argparse
import csv
import os
import re

# --- Section: project defaults (documented, not hidden) ---
RAW_DIR_DEFAULT = "data/raw/atlas14_temporal_distributions"
OUTPUT_PATH_DEFAULT = "data/processed/hyetograph_templates/atlas14_temporal_distribution_templates_final.csv"

DURATIONS_HOUR = [6, 12, 24, 96]
VOLUME9_AREAS = [("1", "Mississippi Valley region"), ("2", "Southeast region")]
VOLUME2_AREA = ("general", "Ohio River Basin and Surrounding States (single area)")

BASE_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/"

# Normalize NOAA's section header text to a compact case label + quartile group.
CASE_NORMALIZATION = {
    "first": ("First-Quartile Case", "1"),
    "second": ("Second-Quartile Case", "2"),
    "third": ("Third-Quartile Case", "3"),
    "fourth": ("Fourth-Quartile Case", "4"),
    "all": ("All Cases", "combined"),
}

TOLERANCE = 0.5  # percent-of-total tolerance for validation checks (NOAA tables are rounded)


def classify_section_header(line, is_volume9_long_format):
    """Return (noaa_temporal_case, noaa_quartile_or_group) if line is a section header, else None."""
    stripped = line.strip().rstrip(",").strip()
    if is_volume9_long_format:
        m = re.match(
            r"CUMULATIVE PERCENTAGES OF TOTAL PRECIPITATION FOR (FIRST|SECOND|THIRD|FOURTH)-QUARTILE CASES"
            r"|CUMULATIVE PERCENTAGES OF TOTAL PRECIPITATION FOR ALL CASES",
            stripped, re.IGNORECASE,
        )
        if not m:
            return None
        if "ALL CASES" in stripped.upper():
            return CASE_NORMALIZATION["all"]
        quartile_word = m.group(1).lower()
        return CASE_NORMALIZATION[quartile_word]
    else:
        m = re.match(r"(First|Second|Third|Fourth) Quartile$|All Cases$", stripped, re.IGNORECASE)
        if not m:
            return None
        if stripped.lower().startswith("all"):
            return CASE_NORMALIZATION["all"]
        quartile_word = stripped.split()[0].lower()
        return CASE_NORMALIZATION[quartile_word]


def parse_volume9_file(file_path, duration_hour, area_id, region_name, source_url):
    """Parse a Volume 9 'long format' temporal distribution CSV."""
    with open(file_path, "r", errors="replace") as f:
        lines = [line.rstrip("\n") for line in f]

    rows = []
    i = 0
    while i < len(lines):
        case_info = classify_section_header(lines[i], is_volume9_long_format=True)
        if case_info is None:
            i += 1
            continue
        noaa_temporal_case, noaa_quartile_or_group = case_info

        # Expect: "Time,Percent of occurrence" then "hours,90%,80%,...,10%"
        i += 1
        while i < len(lines) and not lines[i].strip().lower().startswith("hours"):
            i += 1
        if i >= len(lines):
            break
        header_cols = [c.strip() for c in lines[i].split(",")]
        percentile_labels = header_cols[1:]  # order exactly as written in the file
        i += 1

        while i < len(lines) and lines[i].strip() != "" and not classify_section_header(lines[i], True):
            data_cols = [c.strip() for c in lines[i].split(",")]
            if len(data_cols) < 2 or not re.match(r"^-?\d", data_cols[0]):
                i += 1
                continue
            time_hour = float(data_cols[0])
            for col_idx, percentile_label in enumerate(percentile_labels, start=1):
                if col_idx >= len(data_cols) or data_cols[col_idx] == "":
                    continue  # missing value in source file - not filled in
                cumulative_percent = float(data_cols[col_idx])
                rows.append({
                    "atlas14_volume": "9",
                    "temporal_distribution_area": area_id,
                    "temporal_distribution_region_name": region_name,
                    "duration_hour": duration_hour,
                    "noaa_temporal_case": noaa_temporal_case,
                    "noaa_percentile_or_curve": percentile_label,
                    "time_hour": time_hour,
                    "cumulative_percent": cumulative_percent,
                    "cumulative_fraction": round(cumulative_percent / 100.0, 6),
                    "source_file": os.path.basename(file_path),
                    "source_url": source_url,
                    "status": "parsed",
                    "notes": "",
                })
            i += 1
    return rows


def parse_volume2_file(file_path, duration_hour, source_url):
    """Parse a Volume 2 'wide/transposed, percent-of-duration' temporal distribution CSV."""
    with open(file_path, "r", errors="replace") as f:
        lines = [line.rstrip("\n") for line in f]

    rows = []
    i = 0
    while i < len(lines):
        case_info = classify_section_header(lines[i], is_volume9_long_format=False)
        if case_info is None:
            i += 1
            continue
        noaa_temporal_case, noaa_quartile_or_group = case_info

        i += 1
        while i < len(lines) and "percent of duration" not in lines[i].strip().lower():
            i += 1
        if i >= len(lines):
            break
        header_cols = [c.strip() for c in lines[i].split(",")]
        percent_of_duration_values = [float(c) for c in header_cols[1:] if c != ""]
        i += 1

        while i < len(lines) and lines[i].strip() != "" and not classify_section_header(lines[i], False):
            data_cols = [c.strip() for c in lines[i].split(",")]
            if len(data_cols) < 2 or "%" not in data_cols[0]:
                i += 1
                continue
            percentile_label = data_cols[0]
            for col_idx, pct_of_duration in enumerate(percent_of_duration_values, start=1):
                if col_idx >= len(data_cols) or data_cols[col_idx] == "":
                    continue
                cumulative_percent = float(data_cols[col_idx])
                # Documented exact rescaling: percent-of-duration -> absolute hours.
                time_hour = round((pct_of_duration / 100.0) * duration_hour, 4)
                rows.append({
                    "atlas14_volume": "2",
                    "temporal_distribution_area": VOLUME2_AREA[0],
                    "temporal_distribution_region_name": VOLUME2_AREA[1],
                    "duration_hour": duration_hour,
                    "noaa_temporal_case": noaa_temporal_case,
                    "noaa_percentile_or_curve": percentile_label,
                    "time_hour": time_hour,
                    "cumulative_percent": cumulative_percent,
                    "cumulative_fraction": round(cumulative_percent / 100.0, 6),
                    "source_file": os.path.basename(file_path),
                    "source_url": source_url,
                    "status": "parsed",
                    "notes": "time_hour derived by exact rescaling of the file's own "
                             "percent-of-duration axis (percent_of_duration/100 * duration_hour); "
                             "no interpolation or smoothing applied.",
                })
            i += 1
    return rows


def validate_curves(rows):
    """Run the Task 3C validation checks; return list of problem descriptions."""
    problems = []
    curve_groups = {}
    for r in rows:
        key = (r["atlas14_volume"], r["temporal_distribution_area"], r["duration_hour"],
               r["noaa_temporal_case"], r["noaa_percentile_or_curve"])
        curve_groups.setdefault(key, []).append(r)

    for key, curve_rows in curve_groups.items():
        curve_rows = sorted(curve_rows, key=lambda r: r["time_hour"])
        times = [r["time_hour"] for r in curve_rows]
        percents = [r["cumulative_percent"] for r in curve_rows]
        duration_hour = key[2]

        if len(set(times)) != len(times):
            problems.append(f"{key}: duplicate time steps found")
        if times and times[0] > TOLERANCE:
            problems.append(f"{key}: does not start near 0 (first time_hour={times[0]})")
        if percents and percents[0] > TOLERANCE:
            problems.append(f"{key}: cumulative_percent does not start near 0 (got {percents[0]})")
        if percents and abs(percents[-1] - 100.0) > TOLERANCE:
            problems.append(f"{key}: final cumulative_percent != 100 (got {percents[-1]})")
        if any(p < -TOLERANCE for p in percents):
            problems.append(f"{key}: negative cumulative_percent value found")
        if any(p > 100 + TOLERANCE for p in percents):
            problems.append(f"{key}: cumulative_percent exceeds 100 beyond tolerance")
        if any(b < a - TOLERANCE for a, b in zip(percents, percents[1:])):
            problems.append(f"{key}: cumulative_percent is not non-decreasing")
        if times and abs(times[-1] - duration_hour) > TOLERANCE:
            problems.append(f"{key}: final time_hour ({times[-1]}) does not match duration_hour ({duration_hour})")

    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=RAW_DIR_DEFAULT)
    parser.add_argument("--output", default=OUTPUT_PATH_DEFAULT)
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    all_rows = []
    for area_id, region_name in VOLUME9_AREAS:
        for duration_hour in DURATIONS_HOUR:
            filename = f"se_{area_id}_{duration_hour}h_temporal.csv"
            file_path = os.path.join(args.raw_dir, filename)
            if not os.path.exists(file_path):
                print(f"WARNING: missing expected file {file_path}, skipping.")
                continue
            source_url = f"{BASE_URL}se/{filename}"
            all_rows.extend(parse_volume9_file(file_path, duration_hour, area_id, region_name, source_url))

    for duration_hour in DURATIONS_HOUR:
        filename = f"orb_general_{duration_hour}h_temporal.csv"
        file_path = os.path.join(args.raw_dir, filename)
        if not os.path.exists(file_path):
            print(f"WARNING: missing expected file {file_path}, skipping.")
            continue
        source_url = f"{BASE_URL}orb/{filename}"
        all_rows.extend(parse_volume2_file(file_path, duration_hour, source_url))

    print(f"Parsed {len(all_rows)} curve-value rows from "
          f"{len(VOLUME9_AREAS) * len(DURATIONS_HOUR) + len(DURATIONS_HOUR)} source files.")

    problems = validate_curves(all_rows)
    if problems:
        print(f"VALIDATION: {len(problems)} issue(s) found:")
        for p in problems[:50]:
            print(f"  - {p}")
        if len(problems) > 50:
            print(f"  ... and {len(problems) - 50} more")
    else:
        print("VALIDATION: all curve checks passed (non-decreasing, 0->100, no duplicates, "
              "duration match, no negative/over-100 values).")

    fieldnames = [
        "atlas14_volume", "temporal_distribution_area", "temporal_distribution_region_name",
        "duration_hour", "noaa_temporal_case", "noaa_percentile_or_curve",
        "time_hour", "cumulative_percent", "cumulative_fraction", "source_file", "source_url",
        "status", "notes",
    ]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
