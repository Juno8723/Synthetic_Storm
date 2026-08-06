"""
Task 3F: Export GIS-ready Task 3 hyetograph summary layers.

Joins the full HUC8 polygons (not Alabama-clipped) to the Task 3E
hyetograph summary table and writes:
  - The full "hyetograph_summary_all" layer (one feature per scenario).
  - Eight representative single-scenario layers (one feature per HUC8).
into the same GeoPackage that Task 3B's HUC8-temporal-region-assignment
layer already lives in, plus standalone shapefiles for each representative
layer.

Four of the eight representative layers require temporal_pattern =
"middle_peak", which Task 3D left unresolved (status =
mapping_review_required - NOAA provides two candidate "middle" cases with
no documented tiebreaker). Those four layers are still created with full
HUC8 geometry, rainfall_depth, and status fields (so the spatial structure
and the fact that resolution is pending is visible in GIS), but
max_incremental_rainfall / time_of_max_incremental_rainfall / status are
correctly null and status = "pending_temporal_mapping_review" for those
features - not fabricated.

Outputs:
  data/processed/gis/task3_hyetograph_summary.gpkg
    - hyetograph_summary_all (5,664 features)
    - hyeto_100yr_24hr_early_peak / _middle_peak / _late_peak / _balanced (59 each)
    - hyeto_100yr_6hr_middle_peak, hyeto_100yr_12hr_middle_peak,
      hyeto_100yr_96hr_balanced, hyeto_500yr_24hr_middle_peak (59 each)
  data/processed/gis/shapefiles_task3/hyeto_*.shp

Usage:
  python scripts/export_task3_gis_layers.py
"""

import argparse
import os

import geopandas as gpd
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
HUC_ID_FIELD = "HUC8"
HUC_NAME_FIELD = "NAME"

SUMMARY_TABLE_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_summary.csv"
GPKG_PATH_DEFAULT = "data/processed/gis/task3_hyetograph_summary.gpkg"
SHAPEFILE_DIR_DEFAULT = "data/processed/gis/shapefiles_task3"

REPRESENTATIVE_LAYERS = [
    ("hyeto_100yr_24hr_early_peak", 100, 24, "early_peak"),
    ("hyeto_100yr_24hr_middle_peak", 100, 24, "middle_peak"),
    ("hyeto_100yr_24hr_late_peak", 100, 24, "late_peak"),
    ("hyeto_100yr_24hr_balanced", 100, 24, "balanced"),
    ("hyeto_100yr_6hr_middle_peak", 100, 6, "middle_peak"),
    ("hyeto_100yr_12hr_middle_peak", 100, 12, "middle_peak"),
    ("hyeto_100yr_96hr_balanced", 100, 96, "balanced"),
    ("hyeto_500yr_24hr_middle_peak", 500, 24, "middle_peak"),
]

SUMMARY_LAYER_FIELDS = [
    "huc8_id", "huc8_name", "return_period_year", "duration_hour", "temporal_pattern",
    "rainfall_depth", "max_incremental_rainfall", "time_of_max_incremental_rainfall",
    "number_of_time_steps", "time_step_hour", "temporal_distribution_area",
    "temporal_distribution_region_name", "status",
]

SHAPEFILE_FIELD_MAP = {
    "huc8_id": "huc8_id",
    "huc8_name": "huc8_name",
    "return_period_year": "return_prd",
    "duration_hour": "duration_h",
    "temporal_pattern": "temp_ptrn",
    "rainfall_depth": "rain_depth",
    "max_incremental_rainfall": "max_incr",
    "time_of_max_incremental_rainfall": "t_max_incr",
    "number_of_time_steps": "n_tsteps",
    "time_step_hour": "tstep_hr",
    "temporal_distribution_area": "tda_area",
    "temporal_distribution_region_name": "tda_name",
    "status": "status",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--summary-table", default=SUMMARY_TABLE_DEFAULT)
    parser.add_argument("--gpkg", default=GPKG_PATH_DEFAULT)
    parser.add_argument("--shapefile-dir", default=SHAPEFILE_DIR_DEFAULT)
    args = parser.parse_args()

    if not os.path.exists(args.huc_shapefile):
        raise FileNotFoundError(f"HUC shapefile not found: {args.huc_shapefile}")
    if not os.path.exists(args.summary_table):
        raise FileNotFoundError(
            f"Hyetograph summary table not found: {args.summary_table}. "
            "Run scripts/generate_atlas14_hyetographs.py first."
        )

    os.makedirs(os.path.dirname(args.gpkg), exist_ok=True)
    os.makedirs(args.shapefile_dir, exist_ok=True)

    huc_gdf = gpd.read_file(args.huc_shapefile)[[HUC_ID_FIELD, HUC_NAME_FIELD, "geometry"]].copy()
    huc_gdf = huc_gdf.rename(columns={HUC_ID_FIELD: "huc8_id", HUC_NAME_FIELD: "huc8_name"})
    huc_crs = huc_gdf.crs

    summary_df = pd.read_csv(args.summary_table, dtype={"huc8_id": str})

    # --- Section: hyetograph_summary_all - one feature per scenario ---
    huc_geom_only = huc_gdf[["huc8_id", "geometry"]]
    all_gdf = huc_geom_only.merge(summary_df, on="huc8_id", how="right")
    all_gdf = gpd.GeoDataFrame(all_gdf, geometry="geometry", crs=huc_crs)
    all_gdf.to_file(args.gpkg, layer="hyetograph_summary_all", driver="GPKG")
    print(f"Wrote layer hyetograph_summary_all ({len(all_gdf)} features) to {args.gpkg}")
    if len(all_gdf) != 5664:
        print(f"  WARNING: expected 5664 features, got {len(all_gdf)}")

    # --- Section: eight representative single-scenario layers ---
    for layer_name, return_period, duration_hour, temporal_pattern in REPRESENTATIVE_LAYERS:
        subset = summary_df[
            (summary_df["return_period_year"] == return_period)
            & (summary_df["duration_hour"] == duration_hour)
            & (summary_df["temporal_pattern"] == temporal_pattern)
        ]
        gdf = huc_geom_only.merge(subset, on="huc8_id", how="right")
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=huc_crs)
        gdf = gdf[[c for c in SUMMARY_LAYER_FIELDS if c in gdf.columns] + ["geometry"]]

        gdf.to_file(args.gpkg, layer=layer_name, driver="GPKG")
        n_pending = (gdf["status"] == "pending_temporal_mapping_review").sum()
        print(f"Wrote layer {layer_name} ({len(gdf)} features, {n_pending} pending_temporal_mapping_review) to {args.gpkg}")
        if len(gdf) != 59:
            print(f"  WARNING: expected 59 features for {layer_name}, got {len(gdf)}")

        shp_gdf = gdf.rename(columns=SHAPEFILE_FIELD_MAP)
        keep_cols = [SHAPEFILE_FIELD_MAP[c] for c in SUMMARY_LAYER_FIELDS if c in SHAPEFILE_FIELD_MAP] + ["geometry"]
        shp_gdf = shp_gdf[[c for c in keep_cols if c in shp_gdf.columns]]
        shp_path = os.path.join(args.shapefile_dir, f"{layer_name}.shp")
        shp_gdf.to_file(shp_path, driver="ESRI Shapefile")
        print(f"  Wrote shapefile {shp_path} ({len(shp_gdf)} rows)")

    print("Done.")


if __name__ == "__main__":
    main()
