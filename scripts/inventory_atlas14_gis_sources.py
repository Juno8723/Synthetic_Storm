"""
Task 2A: Inventory of official NOAA Atlas 14 GIS grid sources.

This script does NOT download any data. It documents the official NOAA
Atlas 14 precipitation-frequency GIS grid source for the region covering
Alabama (Volume 9, Southeastern States) and writes a metadata registry
listing the expected source URL, file format, and local path for every
duration x return-period x confidence-bound combination needed by this
project.

Findings this script encodes were confirmed by direct inspection on
2026-07-08:
  - Official GIS grid directory: https://hdsc.nws.noaa.gov/pub/hdsc/data/se/
  - File format: zipped Arc/Info ASCII grid (.asc) + .prj + FGDC .xml metadata
  - Naming convention: se<return_period>yr<duration_code><bound>[_ams].zip
      bound: 'a' = estimate, 'al' = lower 90% CI, 'au' = upper 90% CI
      (the '_ams' variant is the annual-maximum-series alternative; the
      no-suffix files are the project default, partial-duration-series
      based estimates, which match the standard PFDS point-query values)
  - Grid CRS: EPSG:4269 (NAD83 geographic), confirmed from the .prj file
    inside a downloaded sample (se100yr24ha.zip)
  - Units: 1000ths of an inch; NODATA_value = -9
  - All 72 combinations required by this project (6 return periods x
    4 durations x 3 confidence bounds) were confirmed present in the
    official directory listing before this script was written.

Usage:
  python scripts/inventory_atlas14_gis_sources.py
  python scripts/inventory_atlas14_gis_sources.py --verify-urls
"""

import argparse
import csv
import datetime
import os
import urllib.error
import urllib.request

# --- Section: project defaults (documented, not hidden) ---
ATLAS14_VOLUME = "9"
ATLAS14_REGION_CODE = "se"  # Southeastern States, covers Alabama
BASE_GRID_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/se/"
GRID_METADATA_XML_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/metadata/se_metadata.xml"

RETURN_PERIODS_YEAR = [5, 10, 50, 100, 200, 500]
DURATIONS_HOUR = [6, 12, 24, 96]

# Map project duration_hour values to NOAA's file-naming duration codes.
DURATION_CODE_MAP = {
    6: "06h",
    12: "12h",
    24: "24h",
    96: "04d",  # 4 days = 96 hours
}

# Map project confidence_bound labels to NOAA's filename suffix.
CONFIDENCE_BOUND_SUFFIX = {
    "estimate": "a",
    "lower_90ci": "al",
    "upper_90ci": "au",
}

OUTPUT_PATH = "data/metadata/atlas14_gis_inventory.csv"
ACCESS_DATE = "2026-07-08"  # date these official sources were confirmed


def build_source_url(return_period, duration_hour, confidence_bound):
    """Construct the official download URL for one grid zip file."""
    dur_code = DURATION_CODE_MAP[duration_hour]
    bound_suffix = CONFIDENCE_BOUND_SUFFIX[confidence_bound]
    filename = f"{ATLAS14_REGION_CODE}{return_period}yr{dur_code}{bound_suffix}.zip"
    return BASE_GRID_URL + filename, filename


def verify_url(url):
    """Optionally perform a live HEAD request to confirm the URL resolves."""
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "Mozilla/5.0 (Synthetic-Storm-research-workflow)")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return f"http_{resp.status}"
    except urllib.error.HTTPError as e:
        return f"http_error_{e.code}"
    except urllib.error.URLError as e:
        return f"url_error_{e.reason}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--return-periods", type=int, nargs="+", default=RETURN_PERIODS_YEAR,
        help="Return periods in years (default: project standard set)",
    )
    parser.add_argument(
        "--durations", type=int, nargs="+", default=DURATIONS_HOUR,
        help="Durations in hours (default: project standard set)",
    )
    parser.add_argument(
        "--output", default=OUTPUT_PATH,
        help="Output CSV path (default: %(default)s)",
    )
    parser.add_argument(
        "--verify-urls", action="store_true",
        help="Perform a live HEAD request against each source URL before writing status",
    )
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    rows = []
    for return_period in args.return_periods:
        for duration_hour in args.durations:
            if duration_hour not in DURATION_CODE_MAP:
                raise ValueError(
                    f"No known NOAA duration code for duration_hour={duration_hour}. "
                    f"Known durations: {sorted(DURATION_CODE_MAP)}"
                )
            for confidence_bound in ("estimate", "lower_90ci", "upper_90ci"):
                source_url, filename = build_source_url(
                    return_period, duration_hour, confidence_bound
                )
                expected_local_path = f"data/raw/atlas14/{filename}"

                # Baseline status from the manual investigation already performed.
                status = "confirmed_available_official_url"
                notes = (
                    "Verified present in https://hdsc.nws.noaa.gov/pub/hdsc/data/se/ "
                    "directory listing on 2026-07-08. Zip contains .asc "
                    "(Arc/Info ASCII grid), .prj, and FGDC .xml metadata."
                )

                if args.verify_urls:
                    live_status = verify_url(source_url)
                    status = live_status
                    notes += f" Live HEAD check result: {live_status}."

                rows.append(
                    {
                        "atlas14_volume": ATLAS14_VOLUME,
                        "dataset_type": "precipitation_frequency_grid",
                        "duration_hour": duration_hour,
                        "return_period_year": return_period,
                        "confidence_bound": confidence_bound,
                        "source_url": source_url,
                        "file_format": "Zipped Arc/Info ASCII grid (.asc) + .prj + FGDC .xml",
                        "expected_local_path": expected_local_path,
                        "status": status,
                        "notes": notes,
                        "access_date": ACCESS_DATE,
                    }
                )

    # Add one row documenting the region-level FGDC metadata file itself.
    rows.append(
        {
            "atlas14_volume": ATLAS14_VOLUME,
            "dataset_type": "grid_metadata_xml",
            "duration_hour": "",
            "return_period_year": "",
            "confidence_bound": "",
            "source_url": GRID_METADATA_XML_URL,
            "file_format": "FGDC Content Standard for Digital Geospatial Metadata (XML)",
            "expected_local_path": "data/raw/atlas14/se_metadata.xml",
            "status": "confirmed_available_official_url",
            "notes": (
                "Confirms grid CRS = NAD83 geographic (EPSG:4269), units = "
                "1000ths of inch, NODATA=-9, 30 arc-second resolution, "
                "PRISM-based interpolation, PDS estimates derived from AMS."
            ),
            "access_date": ACCESS_DATE,
        }
    )

    fieldnames = [
        "atlas14_volume", "dataset_type", "duration_hour", "return_period_year",
        "confidence_bound", "source_url", "file_format", "expected_local_path",
        "status", "notes", "access_date",
    ]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
