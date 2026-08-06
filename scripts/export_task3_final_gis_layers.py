"""
Task 3 Final Step 8: Export GIS-ready layers for Product A (main NOAA-native
50th-percentile ensemble) and Product B (full NOAA temporal sensitivity
archive).

Writes two separate GeoPackages (Product A and Product B are kept apart so
Product A - the recommended Task 4 input - stays a manageable size, while
Product B's much larger archive lives in its own file), plus representative
shapefiles for both. Every layer uses the full HUC8 polygon geometry (not
Alabama-clipped).

Outputs:
  data/processed/gis/task3_hyetograph_summary_main_noaa_native.gpkg
  data/processed/gis/task3_hyetograph_summary_full_temporal_sensitivity.gpkg
  data/processed/gis/shapefiles_task3_main_noaa_native/*.shp
  data/processed/gis/shapefiles_task3_full_temporal_sensitivity/*.shp
  data/processed/gis/README_task3_main_noaa_native_gis_outputs.md
  data/processed/gis/README_task3_full_temporal_sensitivity_gis_outputs.md

Usage:
  python scripts/export_task3_final_gis_layers.py
"""

import argparse
import os

import geopandas as gpd
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
HUC_ID_FIELD = "HUC8"
HUC_NAME_FIELD = "NAME"

ASSIGNMENT_TABLE_DEFAULT = "data/metadata/huc8_temporal_distribution_assignment_final.csv"
SUMMARY_A_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_main_noaa_native_summary.csv"
SUMMARY_B_DEFAULT = "data/processed/hyetographs/atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_summary.csv"

GPKG_A_DEFAULT = "data/processed/gis/task3_hyetograph_summary_main_noaa_native.gpkg"
GPKG_B_DEFAULT = "data/processed/gis/task3_hyetograph_summary_full_temporal_sensitivity.gpkg"
SHAPEFILE_DIR_A_DEFAULT = "data/processed/gis/shapefiles_task3_main_noaa_native"
SHAPEFILE_DIR_B_DEFAULT = "data/processed/gis/shapefiles_task3_full_temporal_sensitivity"

# Product A representative layers: (layer_name, return_period, duration_hour, temporal_case_final)
REPRESENTATIVE_LAYERS_A = [
    ("hyeto_100yr_24hr_first_quartile_peak_p50", 100, 24, "first_quartile_peak_p50"),
    ("hyeto_100yr_24hr_second_quartile_peak_p50", 100, 24, "second_quartile_peak_p50"),
    ("hyeto_100yr_24hr_third_quartile_peak_p50", 100, 24, "third_quartile_peak_p50"),
    ("hyeto_100yr_24hr_fourth_quartile_peak_p50", 100, 24, "fourth_quartile_peak_p50"),
    ("hyeto_100yr_24hr_all_cases_p50", 100, 24, "all_cases_p50"),
    ("hyeto_100yr_6hr_second_quartile_peak_p50", 100, 6, "second_quartile_peak_p50"),
    ("hyeto_100yr_6hr_third_quartile_peak_p50", 100, 6, "third_quartile_peak_p50"),
    ("hyeto_100yr_12hr_second_quartile_peak_p50", 100, 12, "second_quartile_peak_p50"),
    ("hyeto_100yr_12hr_third_quartile_peak_p50", 100, 12, "third_quartile_peak_p50"),
    ("hyeto_100yr_96hr_all_cases_p50", 100, 96, "all_cases_p50"),
    ("hyeto_500yr_24hr_all_cases_p50", 500, 24, "all_cases_p50"),
]

# Product B representative layers: 100yr/24hr, 5 cases x {p10, p50, p90} (all confirmed available)
QUARTILE_SLUGS = ["first_quartile", "second_quartile", "third_quartile", "fourth_quartile", "all_cases"]
QUARTILE_SHORT = {"first_quartile": "q1", "second_quartile": "q2", "third_quartile": "q3",
                   "fourth_quartile": "q4", "all_cases": "all_cases"}
REPRESENTATIVE_PERCENTILES_B = ["10", "50", "90"]
REPRESENTATIVE_LAYERS_B = [
    (f"hyeto_100yr_24hr_{QUARTILE_SHORT[case]}_p{pct}", 100, 24, f"{case}_p{pct}")
    for case in QUARTILE_SLUGS for pct in REPRESENTATIVE_PERCENTILES_B
]

SUMMARY_LAYER_FIELDS = [
    "huc8_id", "huc8_name", "return_period_year", "duration_hour", "temporal_case_final",
    "noaa_temporal_case", "noaa_percentile_or_curve", "rainfall_depth", "max_incremental_rainfall",
    "time_of_max_incremental_rainfall", "number_of_time_steps", "time_step_hour",
    "temporal_distribution_area", "temporal_distribution_region_name", "status",
]
ASSIGNMENT_LAYER_FIELDS = [
    "huc8_id", "huc8_name", "atlas14_volume_rainfall_depth", "atlas14_volume_temporal_distribution",
    "temporal_distribution_area", "temporal_distribution_region_name", "temporal_region_assignment_method",
    "assigned_overlap_area", "total_huc8_area", "assigned_overlap_fraction",
    "secondary_temporal_distribution_area", "secondary_overlap_fraction",
    "geometry_scope", "selection_rule", "state_clipped", "status", "notes",
]

SHAPEFILE_FIELD_MAP_SUMMARY = {
    "huc8_id": "huc8_id", "huc8_name": "huc8_name", "return_period_year": "return_prd",
    "duration_hour": "duration_h", "temporal_case_final": "temp_case", "noaa_temporal_case": "noaa_case",
    "noaa_percentile_or_curve": "noaa_pctl", "rainfall_depth": "rain_depth",
    "max_incremental_rainfall": "max_incr", "time_of_max_incremental_rainfall": "t_max_incr",
    "number_of_time_steps": "n_tsteps", "time_step_hour": "tstep_hr",
    "temporal_distribution_area": "tda_area", "temporal_distribution_region_name": "tda_name",
    "status": "status",
}
SHAPEFILE_FIELD_MAP_ASSIGNMENT = {
    "huc8_id": "huc8_id", "huc8_name": "huc8_name",
    "atlas14_volume_rainfall_depth": "a14v_rain", "atlas14_volume_temporal_distribution": "a14v_temp",
    "temporal_distribution_area": "tda_area", "temporal_distribution_region_name": "tda_name",
    "temporal_region_assignment_method": "tda_method", "assigned_overlap_area": "ovl_area",
    "total_huc8_area": "tot_area", "assigned_overlap_fraction": "ovl_frac",
    "secondary_temporal_distribution_area": "sec_area", "secondary_overlap_fraction": "sec_frac",
    "geometry_scope": "geom_scope", "selection_rule": "sel_rule", "state_clipped": "state_clip",
    "status": "status", "notes": "notes",
}


def write_shapefile(gdf, field_map, path):
    shp_gdf = gdf.rename(columns=field_map)
    keep_cols = [field_map[c] for c in field_map if c in shp_gdf.columns] + ["geometry"]
    shp_gdf = shp_gdf[[c for c in keep_cols if c in shp_gdf.columns]]
    shp_gdf.to_file(path, driver="ESRI Shapefile")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--assignment-table", default=ASSIGNMENT_TABLE_DEFAULT)
    parser.add_argument("--summary-a", default=SUMMARY_A_DEFAULT)
    parser.add_argument("--summary-b", default=SUMMARY_B_DEFAULT)
    parser.add_argument("--gpkg-a", default=GPKG_A_DEFAULT)
    parser.add_argument("--gpkg-b", default=GPKG_B_DEFAULT)
    parser.add_argument("--shapefile-dir-a", default=SHAPEFILE_DIR_A_DEFAULT)
    parser.add_argument("--shapefile-dir-b", default=SHAPEFILE_DIR_B_DEFAULT)
    args = parser.parse_args()

    for path in (args.huc_shapefile, args.assignment_table, args.summary_a, args.summary_b):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    for d in (os.path.dirname(args.gpkg_a), os.path.dirname(args.gpkg_b),
              args.shapefile_dir_a, args.shapefile_dir_b):
        os.makedirs(d, exist_ok=True)

    huc_full = gpd.read_file(args.huc_shapefile)[[HUC_ID_FIELD, HUC_NAME_FIELD, "geometry"]].copy()
    huc_full = huc_full.rename(columns={HUC_ID_FIELD: "huc8_id", HUC_NAME_FIELD: "huc8_name"})
    huc_crs = huc_full.crs
    huc_geom_only = huc_full[["huc8_id", "geometry"]]

    # =========================================================================
    # PRODUCT A GeoPackage
    # =========================================================================
    assignment_df = pd.read_csv(args.assignment_table, dtype={"huc8_id": str, "temporal_distribution_area": str})
    assign_gdf = huc_full.merge(assignment_df.drop(columns=["huc8_name"]), on="huc8_id", how="left")
    assign_gdf = gpd.GeoDataFrame(assign_gdf, geometry="geometry", crs=huc_crs)
    assign_gdf = assign_gdf[[c for c in ASSIGNMENT_LAYER_FIELDS if c in assign_gdf.columns] + ["geometry"]]
    assign_gdf.to_file(args.gpkg_a, layer="huc8_temporal_distribution_assignment_final", driver="GPKG")
    print(f"[A] Wrote layer huc8_temporal_distribution_assignment_final ({len(assign_gdf)} features)")
    write_shapefile(assign_gdf, SHAPEFILE_FIELD_MAP_ASSIGNMENT,
                     os.path.join(args.shapefile_dir_a, "huc8_temporal_distribution_assignment_final.shp"))

    summary_a = pd.read_csv(args.summary_a, dtype={"huc8_id": str, "temporal_distribution_area": str})
    all_a_gdf = huc_geom_only.merge(summary_a, on="huc8_id", how="right")
    all_a_gdf = gpd.GeoDataFrame(all_a_gdf, geometry="geometry", crs=huc_crs)
    all_a_gdf.to_file(args.gpkg_a, layer="hyetograph_summary_main_noaa_native_all", driver="GPKG")
    print(f"[A] Wrote layer hyetograph_summary_main_noaa_native_all ({len(all_a_gdf)} features)")
    if len(all_a_gdf) != 7080:
        print(f"  WARNING: expected 7080 features, got {len(all_a_gdf)}")

    for layer_name, rp, dur, case in REPRESENTATIVE_LAYERS_A:
        subset = summary_a[
            (summary_a["return_period_year"] == rp) & (summary_a["duration_hour"] == dur)
            & (summary_a["temporal_case_final"] == case)
        ]
        gdf = huc_geom_only.merge(subset, on="huc8_id", how="right")
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=huc_crs)
        gdf = gdf[[c for c in SUMMARY_LAYER_FIELDS if c in gdf.columns] + ["geometry"]]
        gdf.to_file(args.gpkg_a, layer=layer_name, driver="GPKG")
        print(f"[A] Wrote layer {layer_name} ({len(gdf)} features)")
        if len(gdf) != 59:
            print(f"  WARNING: expected 59 features for {layer_name}, got {len(gdf)}")
        write_shapefile(gdf, SHAPEFILE_FIELD_MAP_SUMMARY, os.path.join(args.shapefile_dir_a, f"{layer_name}.shp"))

    # =========================================================================
    # PRODUCT B GeoPackage
    # =========================================================================
    summary_b = pd.read_csv(args.summary_b, dtype={"huc8_id": str, "temporal_distribution_area": str})
    all_b_gdf = huc_geom_only.merge(summary_b, on="huc8_id", how="right")
    all_b_gdf = gpd.GeoDataFrame(all_b_gdf, geometry="geometry", crs=huc_crs)
    all_b_gdf.to_file(args.gpkg_b, layer="hyetograph_summary_full_temporal_sensitivity_all", driver="GPKG")
    print(f"[B] Wrote layer hyetograph_summary_full_temporal_sensitivity_all ({len(all_b_gdf)} features)")
    if len(all_b_gdf) != len(summary_b):
        print(f"  WARNING: feature count {len(all_b_gdf)} != summary row count {len(summary_b)}")

    for layer_name, rp, dur, case in REPRESENTATIVE_LAYERS_B:
        subset = summary_b[
            (summary_b["return_period_year"] == rp) & (summary_b["duration_hour"] == dur)
            & (summary_b["temporal_case_final"] == case)
        ]
        if subset.empty:
            print(f"[B] SKIPPED layer {layer_name}: no rows found for temporal_case_final={case} "
                  f"(curve not available - not fabricating an empty layer silently, see notes)")
            continue
        gdf = huc_geom_only.merge(subset, on="huc8_id", how="right")
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=huc_crs)
        gdf = gdf[[c for c in SUMMARY_LAYER_FIELDS if c in gdf.columns] + ["geometry"]]
        gdf.to_file(args.gpkg_b, layer=layer_name, driver="GPKG")
        print(f"[B] Wrote layer {layer_name} ({len(gdf)} features)")
        if len(gdf) != 59:
            print(f"  WARNING: expected 59 features for {layer_name}, got {len(gdf)}")
        write_shapefile(gdf, SHAPEFILE_FIELD_MAP_SUMMARY, os.path.join(args.shapefile_dir_b, f"{layer_name}.shp"))

    print("Done.")


if __name__ == "__main__":
    main()
