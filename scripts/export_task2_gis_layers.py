"""
Task 2 supplement: export GIS-ready Atlas 14 rainfall-depth layers.

Reads the existing (already validated) Task 2 outputs - the local HUC8
shapefile and the extracted rainfall-depth CSV - and joins them into
spatial layers that can be opened directly in QGIS or ArcGIS Pro. This
script does NOT recompute or alter any rainfall-depth value; it is a pure
join + export step over existing Task 2 outputs.

Important spatial definition (see data/processed/gis/README_gis_outputs.md):
  - Geometries are FULL HUC8 watershed polygons that intersect Alabama.
  - They are NOT clipped or masked to the Alabama state boundary.
  - rainfall_depth values are full-HUC8-watershed zonal statistics.

Outputs:
  data/processed/gis/atlas14_huc8_rainfall_depths.gpkg
    - atlas14_depths_all           (1,416 rows: all HUC8 x RP x duration)
    - atlas14_depths_100yr_24hr    (59 rows)
    - atlas14_depths_500yr_24hr    (59 rows)
    - atlas14_depths_100yr_6hr     (59 rows)
    - atlas14_depths_100yr_96hr    (59 rows)
    - atlas14_depths_50yr_24hr     (59 rows)
  data/processed/gis/shapefiles/
    - atlas14_depths_100yr_24hr.shp
    - atlas14_depths_500yr_24hr.shp
    - atlas14_depths_100yr_6hr.shp
    - atlas14_depths_100yr_96hr.shp

Usage:
  python scripts/export_task2_gis_layers.py
"""

import argparse
import os

import geopandas as gpd
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
HUC_ID_FIELD = "HUC8"
HUC_NAME_FIELD = "NAME"

DEPTH_TABLE_PATH_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)
OUTPUT_DIR_DEFAULT = "data/processed/gis"
GEOPACKAGE_NAME = "atlas14_huc8_rainfall_depths.gpkg"
SHAPEFILE_SUBDIR = "shapefiles"

# Fields carried into every GIS layer, in order (must exist in the joined table).
OUTPUT_FIELDS = [
    "huc8_id", "huc8_name", "return_period_year", "duration_hour",
    "rainfall_depth", "rainfall_depth_unit", "rainfall_depth_statistic",
    "confidence_bound", "atlas14_volume", "atlas14_source_file",
    "extraction_method", "geometry_scope", "selection_rule", "state_clipped",
    "status", "notes", "geometry",
]

# Single-scenario layers to extract from the "all" table: (layer_name, return_period, duration_hour)
SINGLE_SCENARIO_LAYERS = [
    ("atlas14_depths_100yr_24hr", 100, 24),
    ("atlas14_depths_500yr_24hr", 500, 24),
    ("atlas14_depths_100yr_6hr", 100, 6),
    ("atlas14_depths_100yr_96hr", 100, 96),
    ("atlas14_depths_50yr_24hr", 50, 24),
]

# Layers (name, return_period, duration_hour) exported additionally as shapefiles.
# Shapefile field names are truncated to 10 characters by the format itself;
# this mapping documents the shortened names for the GIS README.
SHAPEFILE_LAYERS = [
    "atlas14_depths_100yr_24hr",
    "atlas14_depths_500yr_24hr",
    "atlas14_depths_100yr_6hr",
    "atlas14_depths_100yr_96hr",
]

# Explicit shapefile field-name mapping (full name -> <=10 char shapefile name).
# Documented here so the script and the GIS README stay in sync.
SHAPEFILE_FIELD_MAP = {
    "huc8_id": "huc8_id",
    "huc8_name": "huc8_name",
    "return_period_year": "return_prd",
    "duration_hour": "duration_h",
    "rainfall_depth": "rain_depth",
    "rainfall_depth_unit": "rain_unit",
    "rainfall_depth_statistic": "rain_stat",
    "confidence_bound": "conf_bound",
    "atlas14_volume": "a14_volume",
    "atlas14_source_file": "a14_srcfil",
    "extraction_method": "extr_meth",
    "geometry_scope": "geom_scope",
    "selection_rule": "sel_rule",
    "state_clipped": "state_clip",
    "status": "status",
    "notes": "notes",
}


def normalize_huc8_id(series):
    """Normalize HUC8 IDs to zero-padded 8-character strings."""
    return series.astype(str).str.strip().str.zfill(8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--huc-id-field", default=HUC_ID_FIELD)
    parser.add_argument("--huc-name-field", default=HUC_NAME_FIELD)
    parser.add_argument("--depth-table", default=DEPTH_TABLE_PATH_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    args = parser.parse_args()

    if not os.path.exists(args.huc_shapefile):
        raise FileNotFoundError(
            f"HUC shapefile not found: {args.huc_shapefile}. This script only "
            "reads existing Task 1/Task 2 outputs and does not create HUC data."
        )
    if not os.path.exists(args.depth_table):
        raise FileNotFoundError(
            f"Depth table not found: {args.depth_table}. Run the Task 2 "
            "extraction scripts first."
        )

    os.makedirs(args.output_dir, exist_ok=True)
    shapefile_dir = os.path.join(args.output_dir, SHAPEFILE_SUBDIR)
    os.makedirs(shapefile_dir, exist_ok=True)

    # --- Section: load and normalize HUC8 geometry (read-only, shapefile never modified) ---
    huc_gdf = gpd.read_file(args.huc_shapefile)
    huc_gdf = huc_gdf[[args.huc_id_field, args.huc_name_field, "geometry"]].copy()
    huc_gdf = huc_gdf.rename(columns={args.huc_id_field: "huc8_id_geom"})
    huc_gdf["huc8_id_geom"] = normalize_huc8_id(huc_gdf["huc8_id_geom"])
    huc_crs = huc_gdf.crs

    # --- Section: load rainfall-depth table (read-only input, never modified) ---
    depth_df = pd.read_csv(args.depth_table, dtype={"huc8_id": str})
    depth_df["huc8_id"] = normalize_huc8_id(depth_df["huc8_id"])

    # --- Section: join depth records to HUC8 geometry by huc8_id ---
    joined = huc_gdf.merge(depth_df, left_on="huc8_id_geom", right_on="huc8_id", how="right")
    joined = joined.drop(columns=["huc8_id_geom"])
    joined = gpd.GeoDataFrame(joined, geometry="geometry", crs=huc_crs)

    missing_geom = joined["geometry"].isna().sum()
    if missing_geom:
        print(f"WARNING: {missing_geom} depth rows had no matching HUC8 geometry (huc8_id mismatch).")

    joined = joined[[c for c in OUTPUT_FIELDS if c in joined.columns]]

    if len(joined) != 1416:
        print(f"WARNING: joined 'all' layer has {len(joined)} rows, expected 1416.")

    # --- Section: write the GeoPackage with all layers ---
    gpkg_path = os.path.join(args.output_dir, GEOPACKAGE_NAME)
    joined.to_file(gpkg_path, layer="atlas14_depths_all", driver="GPKG")
    print(f"Wrote layer atlas14_depths_all ({len(joined)} rows) to {gpkg_path}")

    for layer_name, return_period, duration_hour in SINGLE_SCENARIO_LAYERS:
        subset = joined[
            (joined["return_period_year"] == return_period)
            & (joined["duration_hour"] == duration_hour)
        ].copy()
        subset.to_file(gpkg_path, layer=layer_name, driver="GPKG")
        n_huc = subset["huc8_id"].nunique()
        print(f"Wrote layer {layer_name} ({len(subset)} rows, {n_huc} unique HUC8s) to {gpkg_path}")
        if len(subset) != 59:
            print(f"  WARNING: expected 59 rows for {layer_name}, got {len(subset)}.")

        # --- Section: also export the four most useful layers as shapefiles ---
        if layer_name in SHAPEFILE_LAYERS:
            shp_gdf = subset.rename(columns=SHAPEFILE_FIELD_MAP)
            # ESRI Shapefile field names must be <= 10 characters; drop any
            # field not explicitly mapped rather than let GDAL silently truncate it.
            keep_cols = [SHAPEFILE_FIELD_MAP[c] for c in OUTPUT_FIELDS if c in SHAPEFILE_FIELD_MAP] + ["geometry"]
            shp_gdf = shp_gdf[[c for c in keep_cols if c in shp_gdf.columns]]
            shp_path = os.path.join(shapefile_dir, f"{layer_name}.shp")
            shp_gdf.to_file(shp_path, driver="ESRI Shapefile")
            print(f"Wrote shapefile {shp_path} ({len(shp_gdf)} rows)")

    print("Done.")


if __name__ == "__main__":
    main()
