"""
Task 2C-2: Download or register official NOAA Atlas 14 GIS grid files.

This script attempts to download the official NOAA Atlas 14 precipitation
frequency GIS grids for Volume 9 (Southeastern States, covers Alabama)
directly from the confirmed official source:

    https://hdsc.nws.noaa.gov/pub/hdsc/data/se/

Every URL is built from a naming convention that was verified against the
live NOAA directory listing on 2026-07-08 (see
scripts/inventory_atlas14_gis_sources.py for the full documented rationale).
No URLs are guessed and no unofficial mirrors are used.

Downloaded zip files are saved unmodified under data/raw/atlas14/ (raw data
is never edited). Each zip is also extracted (still unmodified content) into
data/raw/atlas14/extracted/ so the ASCII grids are directly readable by the
extraction script.

If a download fails for any reason (network unavailable, NOAA server
change, etc.), this script does NOT fabricate a substitute. It records the
failure in a manifest CSV and writes/updates a manual-download instructions
file so a human can complete the step later.

Usage:
  python scripts/download_or_register_atlas14_grids.py
  python scripts/download_or_register_atlas14_grids.py --include-ci
  python scripts/download_or_register_atlas14_grids.py --return-periods 100 500 --durations 24
"""

import argparse
import csv
import os
import urllib.error
import urllib.request
import zipfile

# --- Section: project defaults (documented, not hidden) ---
ATLAS14_REGION_CODE = "se"  # Southeastern States (Volume 9), covers Alabama
BASE_GRID_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/se/"
GRID_METADATA_XML_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/metadata/se_metadata.xml"

RETURN_PERIODS_YEAR = [5, 10, 50, 100, 200, 500]
DURATIONS_HOUR = [6, 12, 24, 96]

DURATION_CODE_MAP = {6: "06h", 12: "12h", 24: "24h", 96: "04d"}
CONFIDENCE_BOUND_SUFFIX = {"estimate": "a", "lower_90ci": "al", "upper_90ci": "au"}

RAW_DIR = "data/raw/atlas14"
EXTRACTED_DIR = "data/raw/atlas14/extracted"
MANIFEST_PATH = "data/metadata/atlas14_grid_download_manifest.csv"
MANUAL_INSTRUCTIONS_PATH = "data/metadata/atlas14_manual_download_instructions.md"

USER_AGENT = "Mozilla/5.0 (Synthetic-Storm-research-workflow; contact: project owner)"


def download_file(url, dest_path):
    """Download one file with a browser-like User-Agent. Returns (ok, message)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest_path, "wb") as out:
            out.write(resp.read())
        return True, f"downloaded ({os.path.getsize(dest_path)} bytes)"
    except urllib.error.HTTPError as e:
        return False, f"http_error_{e.code}"
    except urllib.error.URLError as e:
        return False, f"url_error_{e.reason}"


def extract_zip(zip_path, extract_dir):
    """Extract a downloaded zip in place. Returns (ok, message)."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        return True, "extracted"
    except zipfile.BadZipFile as e:
        return False, f"bad_zip: {e}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--return-periods", type=int, nargs="+", default=RETURN_PERIODS_YEAR)
    parser.add_argument("--durations", type=int, nargs="+", default=DURATIONS_HOUR)
    parser.add_argument(
        "--include-ci", action="store_true",
        help="Also download lower/upper 90%% confidence interval grids (default: estimate only)",
    )
    parser.add_argument("--raw-dir", default=RAW_DIR)
    parser.add_argument("--extracted-dir", default=EXTRACTED_DIR)
    parser.add_argument(
        "--skip-existing", action="store_true", default=True,
        help="Skip files already present in --raw-dir (default: True)",
    )
    args = parser.parse_args()

    os.makedirs(args.raw_dir, exist_ok=True)
    os.makedirs(args.extracted_dir, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)

    confidence_bounds = ["estimate"] + (["lower_90ci", "upper_90ci"] if args.include_ci else [])

    manifest_rows = []
    failures = []

    # --- Section: download the region-level grid metadata XML once ---
    meta_dest = os.path.join(args.raw_dir, "se_metadata.xml")
    if args.skip_existing and os.path.exists(meta_dest):
        manifest_rows.append({"file": "se_metadata.xml", "url": GRID_METADATA_XML_URL,
                               "status": "already_present", "detail": "skipped"})
    else:
        ok, msg = download_file(GRID_METADATA_XML_URL, meta_dest)
        manifest_rows.append({"file": "se_metadata.xml", "url": GRID_METADATA_XML_URL,
                               "status": "downloaded" if ok else "failed", "detail": msg})
        if not ok:
            failures.append((GRID_METADATA_XML_URL, meta_dest, msg))

    # --- Section: download + extract each required grid zip ---
    for return_period in args.return_periods:
        for duration_hour in args.durations:
            if duration_hour not in DURATION_CODE_MAP:
                raise ValueError(f"No known NOAA duration code for duration_hour={duration_hour}")
            dur_code = DURATION_CODE_MAP[duration_hour]
            for bound in confidence_bounds:
                suffix = CONFIDENCE_BOUND_SUFFIX[bound]
                filename = f"{ATLAS14_REGION_CODE}{return_period}yr{dur_code}{suffix}.zip"
                url = BASE_GRID_URL + filename
                dest_path = os.path.join(args.raw_dir, filename)

                if args.skip_existing and os.path.exists(dest_path):
                    status, detail = "already_present", "skipped download"
                else:
                    ok, msg = download_file(url, dest_path)
                    status, detail = ("downloaded" if ok else "failed"), msg
                    if not ok:
                        failures.append((url, dest_path, msg))

                # Extract only if the zip is present on disk (freshly downloaded or already there).
                if status in ("downloaded", "already_present") and os.path.exists(dest_path):
                    ok_x, msg_x = extract_zip(dest_path, args.extracted_dir)
                    if not ok_x:
                        failures.append((url, dest_path, msg_x))
                        detail += f"; extract_failed: {msg_x}"
                    else:
                        detail += "; extracted"

                manifest_rows.append(
                    {"file": filename, "url": url, "status": status, "detail": detail}
                )

    # --- Section: write manifest of what happened ---
    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "url", "status", "detail"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote download manifest ({len(manifest_rows)} rows) to {MANIFEST_PATH}")

    # --- Section: always (re)write manual download instructions as a reproducibility fallback ---
    write_manual_instructions(failures)

    n_ok = sum(1 for r in manifest_rows if r["status"] in ("downloaded", "already_present"))
    n_fail = sum(1 for r in manifest_rows if r["status"] == "failed")
    print(f"Grid files ready: {n_ok}. Failed downloads: {n_fail}.")
    if failures:
        print("See data/metadata/atlas14_manual_download_instructions.md for manual steps.")


def write_manual_instructions(failures):
    """Write (or refresh) the manual download fallback instructions file."""
    lines = []
    lines.append("# NOAA Atlas 14 GIS Grid - Manual Download Instructions\n")
    lines.append(
        "This file documents how to manually obtain the official NOAA Atlas 14 "
        "precipitation-frequency GIS grids for Volume 9 (Southeastern States, "
        "covers Alabama) in case the automated download in "
        "`scripts/download_or_register_atlas14_grids.py` cannot reach the network "
        "in a given environment.\n"
    )
    lines.append("## Official source\n")
    lines.append("- Directory: https://hdsc.nws.noaa.gov/pub/hdsc/data/se/\n")
    lines.append("- Landing page describing the dataset: https://hdsc.nws.noaa.gov/pfds/pfds_gis.html\n")
    lines.append(
        "- Region metadata (CRS, units, methodology): "
        "https://hdsc.nws.noaa.gov/pub/hdsc/data/metadata/se_metadata.xml\n"
    )
    lines.append("## Naming convention\n")
    lines.append(
        "`se<return_period>yr<duration_code><bound>.zip`, where `<duration_code>` is "
        "`06h`, `12h`, `24h`, or `04d` (4 days = 96 hours), and `<bound>` is `a` "
        "(estimate), `al` (lower 90% CI), or `au` (upper 90% CI). "
        "Example: `se100yr24ha.zip` = 100-year, 24-hour estimate.\n"
    )
    lines.append("## Manual steps\n")
    lines.append("1. Open the directory URL above in a browser.\n")
    lines.append("2. Locate the file matching the naming convention for the needed "
                  "return period / duration / confidence bound.\n")
    lines.append(f"3. Download it into `{RAW_DIR}/` in this project, unmodified.\n")
    lines.append(f"4. Unzip its contents into `{EXTRACTED_DIR}/` (contains .asc, .prj, .xml).\n")
    lines.append(
        "5. Re-run `scripts/extract_atlas14_huc8_depths.py` to (re)compute zonal statistics.\n"
    )

    if failures:
        lines.append("\n## Files that failed automated download on last run\n")
        for url, dest, msg in failures:
            lines.append(f"- `{url}` -> `{dest}` ({msg})\n")
    else:
        lines.append(
            "\n## Status of last automated run\n"
            "All required grid files were downloaded successfully by "
            "`scripts/download_or_register_atlas14_grids.py`. This instructions file "
            "is kept as a fallback reference only.\n"
        )

    with open(MANUAL_INSTRUCTIONS_PATH, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()
