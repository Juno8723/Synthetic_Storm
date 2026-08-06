"""
Task 3 Final Step 1: Download and inspect official NOAA Atlas 14 temporal
distribution files (supersedes the original Task 3A file inventory with a
per-case/per-percentile-curve inventory needed for the Product A / Product B
final build).

Correction to the Task 2D conclusion: Task 2D reported that the per-area,
per-duration comma-delimited temporal distribution tables required manual
interactive download because no static URL pattern could be found. Direct
inspection of the page source of
https://hdsc.nws.noaa.gov/pfds/pfds_temporal.html on 2026-07-09 found the
client-side JavaScript function `tempDistDL()` that builds the download URL:

    tdURL = ftpBaseURL + selReg + '/' + fileReg + '_' + tdType + '_' + selDur + '_temporal.csv'
    ftpBaseURL = 'https://hdsc.nws.noaa.gov/pub/hdsc/data/'

For most regions `fileReg == selReg` and `tdType` comes from a region-specific
sub-selector (used for regions with multiple temporal "types", e.g. general
vs. convective for the Southwest). For Volume 9 (region code "se"), tdType is
the temporal distribution AREA number (1 or 2). For Volume 2 (region code
"orb"), the region is not one of the JS's explicitly handled cases, so it
falls through to the `else` branch, which hardcodes tdType = "general".
This was verified by testing both URL forms directly:
  - https://hdsc.nws.noaa.gov/pub/hdsc/data/se/se_1_24h_temporal.csv  (200 OK)
  - https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/orb_general_24h_temporal.csv (200 OK)
  - https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/orb_1_24h_temporal.csv (404)

So static, official, directly downloadable URLs DO exist for these files;
Task 2D's "manual download required" conclusion for this specific dataset is
superseded by this finding. (The Task 2D conclusion about GIS grids and
temporal-area shapefiles was already correct and downloaded successfully in
Task 2; only the per-area/per-duration curve CSVs were affected by this
correction.)

This script:
  1. Downloads the 8 Volume 9 files (2 areas x 4 durations) and 4 Volume 2
     files (1 general area x 4 durations) needed by this project, if not
     already present, into data/raw/atlas14_temporal_distributions/.
  2. Inspects every file under data/raw/atlas14_temporal_distributions/
     (CSV, TXT, shapefile components, metadata) and records file type,
     volume, area, duration, available NOAA case/curve identifiers, time
     step, and whether values are cumulative percentages.
  3. Writes data/metadata/task3_temporal_file_inventory.csv.

This script does NOT parse the curve values into a usable table - that is
Task 3C (scripts/build_atlas14_temporal_templates.py).

Usage:
  python scripts/inspect_atlas14_temporal_distribution_files.py
"""

import argparse
import csv
import os
import re
import urllib.error
import urllib.request

# --- Section: project defaults (documented, not hidden) ---
RAW_DIR_DEFAULT = "data/raw/atlas14_temporal_distributions"
OUTPUT_PATH_DEFAULT = "data/metadata/task3_final_temporal_file_inventory.csv"

BASE_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/"
DURATIONS_HOUR = [6, 12, 24, 96]

# (region_code, atlas14_volume, area_token, temporal_distribution_area, region_name)
# area_token is the literal token used in the URL/filename.
VOLUME9_AREAS = [
    ("se", "9", "1", "1", "Mississippi Valley region"),
    ("se", "9", "2", "2", "Southeast region"),
]
VOLUME2_AREAS = [
    ("orb", "2", "general", "general", "Ohio River Basin and Surrounding States (single area)"),
]
ALL_REGION_AREAS = VOLUME9_AREAS + VOLUME2_AREAS

ACCESS_DATE = "2026-07-09"
USER_AGENT = "Mozilla/5.0 (Synthetic-Storm-research-workflow; contact: project owner)"


def download_file(url, dest_path):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
            out.write(resp.read())
        return True, f"downloaded ({os.path.getsize(dest_path)} bytes)"
    except urllib.error.HTTPError as e:
        return False, f"http_error_{e.code}"
    except urllib.error.URLError as e:
        return False, f"url_error_{e.reason}"


def ensure_temporal_csvs(raw_dir):
    """Download the 12 required temporal distribution CSVs if not already present."""
    manifest = []
    for region_code, volume, area_token, _, _ in ALL_REGION_AREAS:
        for duration_hour in DURATIONS_HOUR:
            filename = f"{region_code}_{area_token}_{duration_hour}h_temporal.csv"
            url = f"{BASE_URL}{region_code}/{filename}"
            dest_path = os.path.join(raw_dir, filename)
            if os.path.exists(dest_path):
                manifest.append((filename, url, "already_present"))
                continue
            ok, msg = download_file(url, dest_path)
            manifest.append((filename, url, "downloaded" if ok else f"failed: {msg}"))
    return manifest


def detect_file_type(file_name):
    ext = os.path.splitext(file_name)[1].lower()
    return {
        ".csv": "comma_delimited_temporal_distribution",
        ".txt": "text",
        ".shp": "shapefile_geometry",
        ".shx": "shapefile_index",
        ".dbf": "shapefile_attributes",
        ".prj": "shapefile_projection",
        ".cpg": "shapefile_codepage",
        ".sbn": "shapefile_spatial_index",
        ".sbx": "shapefile_spatial_index",
        ".xml": "metadata_xml",
        ".zip": "zip_archive",
    }.get(ext, "other")


CASE_LABELS = {
    "first": "First-Quartile Case", "second": "Second-Quartile Case",
    "third": "Third-Quartile Case", "fourth": "Fourth-Quartile Case", "all": "All Cases",
}


def inspect_temporal_csv(file_path):
    """Inspect one temporal distribution CSV; return every (case, percentile) pair found."""
    with open(file_path, "r", errors="replace") as f:
        lines = f.readlines()

    text = "".join(lines)
    is_cumulative = "cumulative" in text.lower() or "percent of total precipitation" in text.lower()

    # NOAA "case" sections appear as short standalone header lines (not the
    # longer descriptive prose sentences that also mention "quartile").
    case_pattern = re.compile(
        r"^CUMULATIVE PERCENTAGES OF TOTAL PRECIPITATION FOR (FIRST|SECOND|THIRD|FOURTH)-QUARTILE CASES"
        r"|^CUMULATIVE PERCENTAGES OF TOTAL PRECIPITATION FOR ALL CASES"
        r"|^(First|Second|Third|Fourth) Quartile$"
        r"|^All Cases$",
        re.IGNORECASE,
    )

    # Time step: Volume 9 format has "hours,90%,80%,..." header with 0.5-hr rows;
    # Volume 2 format has "percent of duration,0.0,8.3,16.7,..." header.
    if "percent of duration" in text.lower():
        time_step_hour = "variable (13 steps at 1/12 of duration, i.e. ~8.33% increments)"
        x_axis = "percent_of_duration"
    elif re.search(r"^hours,", text, re.MULTILINE):
        time_step_hour = "0.5"
        x_axis = "absolute_hours"
    else:
        time_step_hour = "unknown"
        x_axis = "unknown"

    # Walk the file identifying which case each subsequent percentile-labeled
    # row/column-header belongs to, so we can report exact (case, percentile) pairs.
    case_percentile_pairs = set()
    current_case = None
    for line in lines:
        stripped = line.strip().rstrip(",").strip()
        m = case_pattern.match(stripped)
        if m:
            if "ALL CASES" in stripped.upper():
                current_case = CASE_LABELS["all"]
            else:
                word = re.search(r"(first|second|third|fourth)", stripped, re.IGNORECASE).group(1).lower()
                current_case = CASE_LABELS[word]
            continue
        if current_case is None:
            continue
        # Volume 9 long format: header row "hours,90%,80%,...,10%" lists all percentiles at once.
        if stripped.lower().startswith("hours,"):
            for pct in re.findall(r"([1-9]0)%", stripped):
                case_percentile_pairs.add((current_case, f"{pct}%"))
        # Volume 2 wide format: each data row starts with its own percentile label.
        m2 = re.match(r"^([1-9]0)%,", stripped)
        if m2:
            case_percentile_pairs.add((current_case, f"{m2.group(1)}%"))

    return {
        "case_percentile_pairs": sorted(case_percentile_pairs),
        "time_step_hour": time_step_hour,
        "x_axis_type": x_axis,
        "is_cumulative_percent": is_cumulative,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=RAW_DIR_DEFAULT)
    parser.add_argument("--output", default=OUTPUT_PATH_DEFAULT)
    args = parser.parse_args()

    os.makedirs(args.raw_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    download_manifest = ensure_temporal_csvs(args.raw_dir)
    n_ok = sum(1 for _, _, s in download_manifest if s in ("downloaded", "already_present"))
    n_fail = sum(1 for _, _, s in download_manifest if s.startswith("failed"))
    print(f"Temporal distribution CSVs ready: {n_ok}/{len(download_manifest)}. Failed: {n_fail}.")
    for filename, url, status in download_manifest:
        if status.startswith("failed"):
            print(f"  FAILED: {filename} <- {url} ({status})")

    # --- Section: build a lookup so we know the volume/area/duration for each expected file ---
    expected_lookup = {}
    for region_code, volume, area_token, area_id, region_name in ALL_REGION_AREAS:
        for duration_hour in DURATIONS_HOUR:
            filename = f"{region_code}_{area_token}_{duration_hour}h_temporal.csv"
            expected_lookup[filename] = (volume, area_id, region_name, duration_hour,
                                          f"{BASE_URL}{region_code}/{filename}")

    # --- Section: inspect every file actually present under the raw dir ---
    rows = []
    for root, _, files in os.walk(args.raw_dir):
        for file_name in sorted(files):
            file_path = os.path.join(root, file_name)
            file_type = detect_file_type(file_name)

            volume = area = region_name = duration_hour = source_url = ""
            status = "present"
            notes = ""

            if file_name in expected_lookup:
                volume, area, region_name, duration_hour, source_url = expected_lookup[file_name]

            if file_type == "comma_delimited_temporal_distribution":
                try:
                    info = inspect_temporal_csv(file_path)
                    notes = (
                        f"x_axis={info['x_axis_type']}; "
                        f"cumulative_percent_confirmed={info['is_cumulative_percent']}"
                    )
                    if not info["case_percentile_pairs"]:
                        rows.append({
                            "file_path": file_path, "file_name": file_name, "file_type": file_type,
                            "atlas14_volume": volume, "temporal_distribution_area": area,
                            "temporal_distribution_region_name": region_name, "duration_hour": duration_hour,
                            "noaa_temporal_case": "", "noaa_percentile_or_curve": "",
                            "time_step_hour": info["time_step_hour"], "source_url": source_url,
                            "status": "no_case_percentile_pairs_found", "notes": notes,
                        })
                    else:
                        for case, percentile in info["case_percentile_pairs"]:
                            rows.append({
                                "file_path": file_path, "file_name": file_name, "file_type": file_type,
                                "atlas14_volume": volume, "temporal_distribution_area": area,
                                "temporal_distribution_region_name": region_name, "duration_hour": duration_hour,
                                "noaa_temporal_case": case, "noaa_percentile_or_curve": percentile,
                                "time_step_hour": info["time_step_hour"], "source_url": source_url,
                                "status": status, "notes": notes,
                            })
                    continue
                except (OSError, UnicodeDecodeError) as e:
                    status = "inspection_failed"
                    notes = str(e)
            elif file_type == "zip_archive":
                notes = "Zipped shapefile of temporal distribution area boundaries (Task 2D)."
                source_url = "https://hdsc.nws.noaa.gov/pfds/shapefiles/Vol9_Temporals_Shapefiles.zip"
                volume = "9"
            elif "shapefile" in file_type or file_type == "metadata_xml":
                notes = "Component of the Volume 9 temporal distribution area boundary shapefile."
                volume = "9"

            rows.append({
                "file_path": file_path,
                "file_name": file_name,
                "file_type": file_type,
                "atlas14_volume": volume,
                "temporal_distribution_area": area,
                "temporal_distribution_region_name": region_name,
                "duration_hour": duration_hour,
                "noaa_temporal_case": "",
                "noaa_percentile_or_curve": "",
                "time_step_hour": "",
                "source_url": source_url,
                "status": status,
                "notes": notes,
            })

    fieldnames = [
        "file_path", "file_name", "file_type", "atlas14_volume", "temporal_distribution_area",
        "temporal_distribution_region_name", "duration_hour", "noaa_temporal_case",
        "noaa_percentile_or_curve", "time_step_hour", "source_url", "status", "notes",
    ]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
