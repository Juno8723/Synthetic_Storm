"""
Task 2 supplement: fill HUC8 06020004 (Sequatchie) using NOAA Atlas 14 Volume 2.

HUC8 06020004 (Sequatchie) intersects Alabama but falls primarily in the
Tennessee River / Ohio River Basin, which is covered by NOAA Atlas 14
Volume 2 (Ohio River Basin and Surrounding States), not Volume 9
(Southeastern States) used for the other 58 HUC8s in Task 2. This script:

  1. Downloads the official NOAA Atlas 14 Volume 2 GIS grids needed for
     this HUC8 (6 return periods x 4 durations, estimate grids only).
  2. Computes zonal-mean rainfall depth for HUC8 06020004 ONLY (full HUC8
     polygon, not Alabama-clipped) from those grids.
  3. Patches the 24 pending rows for this HUC8 in the Task 2 depth table.
  4. Patches the 96 pending rows for this HUC8 in the Task 2 scenario table.

Findings confirmed by direct inspection on 2026-07-08:
  - Official GIS grid directory: https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/
  - Region code "orb" = Ohio River Basin and Surrounding States (Volume 2),
    confirmed via https://hdsc.nws.noaa.gov/pub/hdsc/data/metadata/orb_metadata.xml
    (title: "Precipitation Frequency for Ohio River Basin, USA - NOAA Atlas
    14 Volume 2"; covers DE, DC, IL, IN, KY, MD, NJ, NC, OH, PA, SC, TN, VA, WV)
  - Same file naming convention as Volume 9: orb<RP>yr<duration_code><bound>.zip
  - CRS: EPSG:4322 (WGS72 geographic) - DIFFERENT from Volume 9's EPSG:4269
    (NAD83). Confirmed from the .prj file inside a downloaded sample
    (orb100yr24ha.zip).
  - NODATA_value = -999 for Volume 2 grids (Volume 9 uses -9). Values are
    still stored in 1000ths of an inch.
  - All 24 combinations required (6 return periods x 4 durations, estimate
    bound) were confirmed present in the official orb/ directory listing
    before this script was written.

This script does NOT overwrite the pre-existing Task 2 outputs blindly - the
calling workflow is expected to have already produced a timestamped backup
under data/metadata/backups/ before this script is run (see
scripts/README_task2_atlas14_extraction.md).

Usage:
  python scripts/supplement_sequatchie_volume2_atlas14.py
"""

import argparse
import csv
import os
import urllib.error
import urllib.request
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.mask

# --- Section: project defaults (documented, not hidden) ---
TARGET_HUC8_ID = "06020004"
TARGET_HUC8_NAME = "Sequatchie"

HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
HUC_ID_FIELD = "HUC8"
HUC_NAME_FIELD = "NAME"

REGION_CODE = "orb"  # Ohio River Basin and Surrounding States (Volume 2)
ATLAS14_VOLUME = "2"
BASE_GRID_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/"
GRID_METADATA_XML_URL = "https://hdsc.nws.noaa.gov/pub/hdsc/data/metadata/orb_metadata.xml"

RAW_DIR_DEFAULT = "data/raw/atlas14_volume2"
EXTRACTED_DIR_DEFAULT = "data/raw/atlas14_volume2/extracted"

RETURN_PERIODS_YEAR = [5, 10, 50, 100, 200, 500]
DURATIONS_HOUR = [6, 12, 24, 96]
DURATION_CODE_MAP = {6: "06h", 12: "12h", 24: "24h", 96: "04d"}
GRID_UNIT_SCALE = 1000.0
RAINFALL_DEPTH_UNIT = "in"
GRID_CRS = "EPSG:4322"  # WGS72 geographic, confirmed from orb .prj file

GEOMETRY_SCOPE = "full HUC8 polygon"
SELECTION_RULE = "intersects Alabama"
STATE_CLIPPED = False
EXTRACTION_METHOD = "GIS grid zonal statistics (full HUC8 polygon)"
RAINFALL_DEPTH_SOURCE = "NOAA Atlas 14 GIS grid (Volume 2, Ohio River Basin and Surrounding States)"

DEPTH_TABLE_PATH_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)
SCENARIO_TABLE_PATH_DEFAULT = (
    "data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv"
)
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


def extract_zip(zip_path, extract_dir):
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(extract_dir)
        return True, "extracted"
    except zipfile.BadZipFile as e:
        return False, f"bad_zip: {e}"


def zonal_mean_for_polygon(dataset, geometry):
    out_image, _ = rasterio.mask.mask(dataset, [geometry], crop=True, all_touched=False)
    band = out_image[0]
    masked = np.ma.masked_equal(band, dataset.nodata)
    if masked.count() == 0:
        return None
    return float(np.ma.mean(masked))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--raw-dir", default=RAW_DIR_DEFAULT)
    parser.add_argument("--extracted-dir", default=EXTRACTED_DIR_DEFAULT)
    parser.add_argument("--depth-table", default=DEPTH_TABLE_PATH_DEFAULT)
    parser.add_argument("--scenario-table", default=SCENARIO_TABLE_PATH_DEFAULT)
    parser.add_argument("--skip-existing", action="store_true", default=True)
    args = parser.parse_args()

    os.makedirs(args.raw_dir, exist_ok=True)
    os.makedirs(args.extracted_dir, exist_ok=True)

    if not os.path.exists(args.huc_shapefile):
        raise FileNotFoundError(f"HUC shapefile not found: {args.huc_shapefile}")
    if not os.path.exists(args.depth_table):
        raise FileNotFoundError(f"Depth table not found: {args.depth_table}")
    if not os.path.exists(args.scenario_table):
        raise FileNotFoundError(f"Scenario table not found: {args.scenario_table}")

    # --- Section 1: download Volume 2 grids (region metadata + 24 estimate grids) ---
    manifest_rows = []
    meta_dest = os.path.join(args.raw_dir, "orb_metadata.xml")
    if args.skip_existing and os.path.exists(meta_dest):
        manifest_rows.append({"file": "orb_metadata.xml", "url": GRID_METADATA_XML_URL,
                               "status": "already_present", "detail": "skipped"})
    else:
        ok, msg = download_file(GRID_METADATA_XML_URL, meta_dest)
        manifest_rows.append({"file": "orb_metadata.xml", "url": GRID_METADATA_XML_URL,
                               "status": "downloaded" if ok else "failed", "detail": msg})

    grid_paths = {}  # (return_period, duration_hour) -> .asc path
    for return_period in RETURN_PERIODS_YEAR:
        for duration_hour in DURATIONS_HOUR:
            dur_code = DURATION_CODE_MAP[duration_hour]
            filename = f"{REGION_CODE}{return_period}yr{dur_code}a.zip"
            url = BASE_GRID_URL + filename
            dest_path = os.path.join(args.raw_dir, filename)

            if args.skip_existing and os.path.exists(dest_path):
                status, detail = "already_present", "skipped download"
            else:
                ok, msg = download_file(url, dest_path)
                status, detail = ("downloaded" if ok else "failed"), msg

            if status in ("downloaded", "already_present") and os.path.exists(dest_path):
                ok_x, msg_x = extract_zip(dest_path, args.extracted_dir)
                detail += f"; {msg_x}" if ok_x else f"; extract_failed: {msg_x}"

            manifest_rows.append({"file": filename, "url": url, "status": status, "detail": detail})
            asc_name = f"{REGION_CODE}{return_period}yr{dur_code}a.asc"
            asc_path = os.path.join(args.extracted_dir, asc_name)
            if os.path.exists(asc_path):
                grid_paths[(return_period, duration_hour)] = asc_path

    n_ok = sum(1 for r in manifest_rows if r["status"] in ("downloaded", "already_present"))
    n_fail = sum(1 for r in manifest_rows if r["status"] == "failed")
    print(f"Volume 2 grid files ready: {n_ok}. Failed downloads: {n_fail}.")
    if n_fail:
        print("WARNING: some Volume 2 grids failed to download. Affected combinations will remain pending.")

    # Write a manifest specific to this supplement run (does not touch the Volume 9 manifest).
    supplement_manifest_path = "data/metadata/atlas14_volume2_grid_download_manifest.csv"
    with open(supplement_manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "url", "status", "detail"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote {supplement_manifest_path}")

    # --- Section 2: extract HUC8 06020004 geometry and compute zonal mean per combination ---
    huc_gdf = gpd.read_file(args.huc_shapefile)
    target = huc_gdf[huc_gdf[HUC_ID_FIELD] == TARGET_HUC8_ID]
    if target.empty:
        raise ValueError(f"HUC8 {TARGET_HUC8_ID} not found in {args.huc_shapefile}")
    target_grid_crs = target.to_crs(GRID_CRS)
    huc_polygon_crs = str(huc_gdf.crs)
    geometry = target_grid_crs.geometry.iloc[0]

    extracted_values = {}  # (return_period, duration_hour) -> (depth_in, source_file)
    for (return_period, duration_hour), asc_path in grid_paths.items():
        with rasterio.open(asc_path) as dataset:
            value = zonal_mean_for_polygon(dataset, geometry)
        if value is not None:
            extracted_values[(return_period, duration_hour)] = (
                round(value / GRID_UNIT_SCALE, 3), os.path.basename(asc_path)
            )

    print(f"Extracted {len(extracted_values)} / {len(RETURN_PERIODS_YEAR) * len(DURATIONS_HOUR)} "
          f"return_period x duration combinations for HUC8 {TARGET_HUC8_ID}.")

    # --- Section 3: patch the depth table (24 target rows only) ---
    depth_df = pd.read_csv(args.depth_table, dtype={"huc8_id": str})
    # pandas 2.x/3.x infer_string defaults object-like columns to a strict
    # "str" dtype that rejects assigning floats/bools into mixed-type cells
    # (e.g. rainfall_depth holds both numbers and the string "TBD"). Cast the
    # columns we mutate back to plain object dtype so mixed assignment works.
    mutable_depth_cols = [
        "huc8_name", "geometry_scope", "selection_rule", "state_clipped",
        "rainfall_depth", "rainfall_depth_unit", "rainfall_depth_statistic",
        "confidence_bound", "atlas14_volume", "atlas14_source_file",
        "extraction_method", "crs_polygon", "crs_grid", "status", "notes",
    ]
    for col in mutable_depth_cols:
        depth_df[col] = depth_df[col].astype(object)
    depth_mask = depth_df["huc8_id"] == TARGET_HUC8_ID
    n_patched_depth = 0
    for idx in depth_df[depth_mask].index:
        rp = depth_df.at[idx, "return_period_year"]
        dur = depth_df.at[idx, "duration_hour"]
        key = (int(rp), int(dur))
        if key not in extracted_values:
            continue  # leave this row pending; do not invent a value
        depth_in, source_file = extracted_values[key]
        depth_df.at[idx, "huc8_name"] = TARGET_HUC8_NAME
        depth_df.at[idx, "geometry_scope"] = GEOMETRY_SCOPE
        depth_df.at[idx, "selection_rule"] = SELECTION_RULE
        depth_df.at[idx, "state_clipped"] = STATE_CLIPPED
        depth_df.at[idx, "rainfall_depth"] = depth_in
        depth_df.at[idx, "rainfall_depth_unit"] = RAINFALL_DEPTH_UNIT
        depth_df.at[idx, "rainfall_depth_statistic"] = "mean"
        depth_df.at[idx, "confidence_bound"] = "estimate"
        depth_df.at[idx, "atlas14_volume"] = ATLAS14_VOLUME
        depth_df.at[idx, "atlas14_source_file"] = source_file
        depth_df.at[idx, "extraction_method"] = EXTRACTION_METHOD
        depth_df.at[idx, "crs_polygon"] = huc_polygon_crs
        depth_df.at[idx, "crs_grid"] = GRID_CRS
        depth_df.at[idx, "status"] = "extracted"
        depth_df.at[idx, "notes"] = (
            "Filled using NOAA Atlas 14 Volume 2 (Ohio River Basin and Surrounding "
            "States) because this HUC8 falls outside Volume 9 (Southeastern States) "
            "grid coverage. All other HUC8s in this table use Volume 9. "
            "Geometry remains full HUC8 polygon, not Alabama-clipped."
        )
        n_patched_depth += 1
    depth_df.to_csv(args.depth_table, index=False)
    print(f"Patched {n_patched_depth} / {depth_mask.sum()} depth-table rows for HUC8 {TARGET_HUC8_ID}.")

    # --- Section 4: patch the scenario table (96 target rows: 24 combos x 4 temporal patterns) ---
    scenario_df = pd.read_csv(args.scenario_table, dtype={"huc8_id": str})
    mutable_scenario_cols = [
        "huc8_name", "rainfall_depth", "rainfall_depth_unit", "rainfall_depth_source",
        "rainfall_depth_extraction_method", "rainfall_depth_statistic",
        "geometry_scope", "selection_rule", "state_clipped", "status", "notes",
    ]
    for col in mutable_scenario_cols:
        scenario_df[col] = scenario_df[col].astype(object)
    scenario_mask = scenario_df["huc8_id"] == TARGET_HUC8_ID
    n_patched_scenario = 0
    for idx in scenario_df[scenario_mask].index:
        rp = scenario_df.at[idx, "return_period_year"]
        dur = scenario_df.at[idx, "duration_hour"]
        key = (int(rp), int(dur))
        if key not in extracted_values:
            continue  # leave this row pending; do not invent a value
        depth_in, _ = extracted_values[key]
        scenario_df.at[idx, "huc8_name"] = TARGET_HUC8_NAME
        scenario_df.at[idx, "rainfall_depth"] = depth_in
        scenario_df.at[idx, "rainfall_depth_unit"] = RAINFALL_DEPTH_UNIT
        scenario_df.at[idx, "rainfall_depth_source"] = RAINFALL_DEPTH_SOURCE
        scenario_df.at[idx, "rainfall_depth_extraction_method"] = EXTRACTION_METHOD
        scenario_df.at[idx, "rainfall_depth_statistic"] = "mean"
        scenario_df.at[idx, "geometry_scope"] = GEOMETRY_SCOPE
        scenario_df.at[idx, "selection_rule"] = SELECTION_RULE
        scenario_df.at[idx, "state_clipped"] = STATE_CLIPPED
        scenario_df.at[idx, "status"] = "atlas14_depth_extracted"
        scenario_df.at[idx, "notes"] = (
            "Filled using NOAA Atlas 14 Volume 2 (Ohio River Basin and Surrounding "
            "States); all other HUC8s use Volume 9 (Southeastern States)."
        )
        n_patched_scenario += 1
    scenario_df.to_csv(args.scenario_table, index=False)
    print(f"Patched {n_patched_scenario} / {scenario_mask.sum()} scenario-table rows for HUC8 {TARGET_HUC8_ID}.")

    remaining_pending = 24 - len(extracted_values)
    if remaining_pending:
        print(f"WARNING: {remaining_pending} return_period x duration combinations remain pending "
              f"(grid unavailable) for HUC8 {TARGET_HUC8_ID}. These were left untouched, not invented.")


if __name__ == "__main__":
    main()
