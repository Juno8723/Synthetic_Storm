"""
Task 3B: Assign each HUC8 to a NOAA Atlas 14 temporal distribution area.

Reads the full HUC8 polygons (not Alabama-clipped) and the official NOAA
Atlas 14 Volume 9 temporal distribution area shapefile
(Vol_9_Temporal_Regions.shp, downloaded in Task 2D), reprojects both to an
equal-area CRS, and computes the overlap area/fraction between each HUC8 and
each temporal distribution area (Region 1 = Mississippi Valley region,
Region 2 = Southeast region - confirmed in this session by comparing each
region polygon's centroid longitude against known geography: Region 1
centroid ~-89.4 deg (west, Mississippi Valley), Region 2 centroid ~-81.7 deg
(east, peninsular FL/GA, Southeast)).

HUC8 06020004 (Sequatchie) is handled separately: its rainfall_depth was
sourced from NOAA Atlas 14 Volume 2 (Ohio River Basin and Surrounding
States) in Task 2, because it falls outside Volume 9 GIS-grid coverage.
Volume 2's temporal distribution page offers only ONE temporal distribution
area ("general") for the entire Ohio River Basin region (no separate area
shapefile exists for Volume 2 - confirmed from the "orbSub" selector on
https://hdsc.nws.noaa.gov/pfds/pfds_temporal.html, which has a single
option, value="1", and the JS's fallback branch names the download token
"general"). To keep rainfall depth and temporal distribution sourced from
the same Atlas 14 volume for this HUC8, Sequatchie is assigned to Volume 2's
single "general" area directly, rather than via spatial overlap with the
Volume 9 shapefile.

This is the Task 3 Final version of this script (Step 2). It writes to new
"_final" output paths and does not overwrite the original Task 3 partial
outputs (data/metadata/huc8_temporal_distribution_assignment.csv and the
original task3_hyetograph_summary.gpkg / shapefiles_task3/ remain as they
were).

Outputs:
  data/metadata/huc8_temporal_distribution_assignment_final.csv
  data/processed/gis/task3_final_hyetograph_summary.gpkg (layer: huc8_temporal_distribution_assignment_final)
  data/processed/gis/shapefiles_task3_final/huc8_temporal_distribution_assignment_final.shp

Usage:
  python scripts/assign_huc8_temporal_regions.py
"""

import argparse
import os

import geopandas as gpd
import pandas as pd

# --- Section: project defaults (documented, not hidden) ---
HUC_SHAPEFILE_DEFAULT = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
HUC_ID_FIELD = "HUC8"
HUC_NAME_FIELD = "NAME"

TEMPORAL_AREA_SHAPEFILE_DEFAULT = (
    "data/raw/atlas14_temporal_distributions/extracted/Vol_9_Temporal_Regions.shp"
)
DEPTH_TABLE_PATH_DEFAULT = (
    "data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv"
)

OUTPUT_CSV_DEFAULT = "data/metadata/huc8_temporal_distribution_assignment_final.csv"
GPKG_PATH_DEFAULT = "data/processed/gis/task3_final_hyetograph_summary.gpkg"
SHAPEFILE_PATH_DEFAULT = "data/processed/gis/shapefiles_task3_final/huc8_temporal_distribution_assignment_final.shp"

EQUAL_AREA_CRS = "EPSG:5070"  # NAD83 / Conus Albers - standard CONUS equal-area CRS

SEQUATCHIE_HUC8_ID = "06020004"
VOLUME9_REGION_NAMES = {1: "Mississippi Valley region", 2: "Southeast region"}

GEOMETRY_SCOPE = "full HUC8 polygon"
SELECTION_RULE = "intersects Alabama"
STATE_CLIPPED = False

# Below this overlap fraction, most of the HUC8 lies outside every mapped
# Volume 9 temporal distribution area (commonly Tennessee River basin HUC8s
# that clip the Volume 9 temporal-area shapefile's edge). The rainfall-depth
# grid can still have valid data there (different NOAA product, different
# mapped extent), so we still assign the best-overlap region but flag it.
LOW_CONFIDENCE_OVERLAP_THRESHOLD = 0.5

SHAPEFILE_FIELD_MAP = {
    "huc8_id": "huc8_id",
    "huc8_name": "huc8_name",
    "atlas14_volume_rainfall_depth": "a14v_rain",
    "atlas14_volume_temporal_distribution": "a14v_temp",
    "temporal_distribution_area": "tda_area",
    "temporal_distribution_region_name": "tda_name",
    "temporal_region_assignment_method": "tda_method",
    "assigned_overlap_area": "ovl_area",
    "total_huc8_area": "tot_area",
    "assigned_overlap_fraction": "ovl_frac",
    "secondary_temporal_distribution_area": "sec_area",
    "secondary_overlap_fraction": "sec_frac",
    "geometry_scope": "geom_scope",
    "selection_rule": "sel_rule",
    "state_clipped": "state_clip",
    "status": "status",
    "notes": "notes",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--huc-shapefile", default=HUC_SHAPEFILE_DEFAULT)
    parser.add_argument("--temporal-area-shapefile", default=TEMPORAL_AREA_SHAPEFILE_DEFAULT)
    parser.add_argument("--depth-table", default=DEPTH_TABLE_PATH_DEFAULT)
    parser.add_argument("--output-csv", default=OUTPUT_CSV_DEFAULT)
    parser.add_argument("--gpkg", default=GPKG_PATH_DEFAULT)
    parser.add_argument("--shapefile", default=SHAPEFILE_PATH_DEFAULT)
    args = parser.parse_args()

    for path in (args.huc_shapefile, args.temporal_area_shapefile, args.depth_table):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required input not found: {path}")

    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    os.makedirs(os.path.dirname(args.gpkg), exist_ok=True)
    os.makedirs(os.path.dirname(args.shapefile), exist_ok=True)

    # --- Section: load HUC8 polygons (full, not Alabama-clipped) and temporal areas ---
    huc_gdf = gpd.read_file(args.huc_shapefile)[[HUC_ID_FIELD, HUC_NAME_FIELD, "geometry"]].copy()
    huc_gdf = huc_gdf.rename(columns={HUC_ID_FIELD: "huc8_id", HUC_NAME_FIELD: "huc8_name"})
    original_crs = huc_gdf.crs

    temporal_gdf = gpd.read_file(args.temporal_area_shapefile)

    # Reproject both to an equal-area CRS before computing overlap areas/fractions.
    huc_eq = huc_gdf.to_crs(EQUAL_AREA_CRS)
    temporal_eq = temporal_gdf.to_crs(EQUAL_AREA_CRS)
    huc_eq["total_huc8_area"] = huc_eq.geometry.area

    # --- Section: volume attribution from the Task 2 depth table (per-HUC8, already resolved) ---
    depth_df = pd.read_csv(args.depth_table, dtype={"huc8_id": str})
    volume_lookup = depth_df.groupby("huc8_id")["atlas14_volume"].first().to_dict()

    # --- Section: compute overlap area between each HUC8 and each temporal region ---
    rows = []
    for _, huc in huc_eq.iterrows():
        huc8_id = huc["huc8_id"]
        huc8_name = huc["huc8_name"]
        total_area = huc["total_huc8_area"]
        rainfall_volume = str(volume_lookup.get(huc8_id, ""))

        if huc8_id == SEQUATCHIE_HUC8_ID:
            # --- Volume attribution override: keep depth and temporal source consistent ---
            rows.append({
                "huc8_id": huc8_id,
                "huc8_name": huc8_name,
                "atlas14_volume_rainfall_depth": rainfall_volume,
                "atlas14_volume_temporal_distribution": "2",
                "temporal_distribution_area": "general",
                "temporal_distribution_region_name": "Ohio River Basin and Surrounding States (single area)",
                "temporal_region_assignment_method": "volume_consistency_override_single_area",
                "assigned_overlap_area": total_area,
                "total_huc8_area": total_area,
                "assigned_overlap_fraction": 1.0,
                "secondary_temporal_distribution_area": "",
                "secondary_overlap_fraction": "",
                "geometry_scope": GEOMETRY_SCOPE,
                "selection_rule": SELECTION_RULE,
                "state_clipped": STATE_CLIPPED,
                "status": "assigned",
                "notes": (
                    "Rainfall depth for this HUC8 was extracted from NOAA Atlas 14 Volume 2 "
                    "(Ohio River Basin and Surrounding States) because it lies outside Volume 9 "
                    "GIS-grid coverage (see Task 2 supplement). Volume 2 provides only a single "
                    "temporal distribution area ('general') for its entire domain - there is no "
                    "separate area shapefile to compute spatial overlap against. Assigned directly "
                    "to keep rainfall-depth and temporal-distribution sources from the same volume, "
                    "per project instruction not to force Volume 9 temporal curves onto this HUC8."
                ),
            })
            continue

        geom = huc["geometry"]
        overlaps = []
        for _, region in temporal_eq.iterrows():
            inter_area = geom.intersection(region.geometry).area
            if inter_area > 0:
                overlaps.append((int(region["Region"]), inter_area))
        overlaps.sort(key=lambda x: x[1], reverse=True)

        if not overlaps:
            rows.append({
                "huc8_id": huc8_id,
                "huc8_name": huc8_name,
                "atlas14_volume_rainfall_depth": rainfall_volume,
                "atlas14_volume_temporal_distribution": "",
                "temporal_distribution_area": "",
                "temporal_distribution_region_name": "",
                "temporal_region_assignment_method": "spatial_overlap_max_area",
                "assigned_overlap_area": 0,
                "total_huc8_area": total_area,
                "assigned_overlap_fraction": 0.0,
                "secondary_temporal_distribution_area": "",
                "secondary_overlap_fraction": "",
                "geometry_scope": GEOMETRY_SCOPE,
                "selection_rule": SELECTION_RULE,
                "state_clipped": STATE_CLIPPED,
                "status": "no_overlap_found",
                "notes": (
                    "No overlap found between this HUC8 and the Volume 9 temporal distribution "
                    "area shapefile. Requires manual review before temporal pattern assignment."
                ),
            })
            continue

        primary_area, secondary_area = overlaps[0], overlaps[1] if len(overlaps) > 1 else None
        primary_region_num, primary_overlap = primary_area
        overlap_fraction = round(primary_overlap / total_area, 4) if total_area else 0.0

        if overlap_fraction < LOW_CONFIDENCE_OVERLAP_THRESHOLD:
            status = "low_confidence_overlap_assignment"
            notes = (
                f"Only {overlap_fraction:.1%} of this HUC8's area falls within any mapped "
                "Volume 9 temporal distribution area (the rest lies outside the Volume 9 "
                "temporal-area shapefile's mapped extent, commonly because this is a Tennessee "
                "River basin HUC8 near the Volume 9/Volume 2 boundary). The rainfall-depth GIS "
                "grid still returned valid data here (a different NOAA product with a "
                "different mapped extent), so a rainfall_depth value exists, but this temporal "
                "region assignment should be treated as low-confidence and reviewed before "
                "relying on it for a final hyetograph."
            )
        else:
            status = "assigned"
            notes = ""

        rows.append({
            "huc8_id": huc8_id,
            "huc8_name": huc8_name,
            "atlas14_volume_rainfall_depth": rainfall_volume,
            "atlas14_volume_temporal_distribution": "9",
            "temporal_distribution_area": str(primary_region_num),
            "temporal_distribution_region_name": VOLUME9_REGION_NAMES.get(primary_region_num, ""),
            "temporal_region_assignment_method": "spatial_overlap_max_area",
            "assigned_overlap_area": primary_overlap,
            "total_huc8_area": total_area,
            "assigned_overlap_fraction": overlap_fraction,
            "secondary_temporal_distribution_area": str(secondary_area[0]) if secondary_area else "",
            "secondary_overlap_fraction": (
                round(secondary_area[1] / total_area, 4) if secondary_area and total_area else ""
            ),
            "geometry_scope": GEOMETRY_SCOPE,
            "selection_rule": SELECTION_RULE,
            "state_clipped": STATE_CLIPPED,
            "status": status,
            "notes": notes,
        })

    assignment_df = pd.DataFrame(rows)
    assignment_df.to_csv(args.output_csv, index=False)
    print(f"Wrote {len(assignment_df)} rows to {args.output_csv}")
    print(assignment_df["temporal_distribution_area"].value_counts(dropna=False).to_string())

    # --- Section: write GIS layer (GeoPackage + shapefile) with full HUC8 geometry (original CRS) ---
    gis_gdf = huc_gdf.merge(assignment_df, on=["huc8_id", "huc8_name"], how="left")
    gis_gdf = gpd.GeoDataFrame(gis_gdf, geometry="geometry", crs=original_crs)

    gis_gdf.to_file(args.gpkg, layer="huc8_temporal_distribution_assignment_final", driver="GPKG")
    print(f"Wrote layer huc8_temporal_distribution_assignment_final ({len(gis_gdf)} rows) to {args.gpkg}")

    shp_gdf = gis_gdf.rename(columns=SHAPEFILE_FIELD_MAP)
    keep_cols = [SHAPEFILE_FIELD_MAP[c] for c in SHAPEFILE_FIELD_MAP if c in shp_gdf.columns] + ["geometry"]
    shp_gdf = shp_gdf[[c for c in keep_cols if c in shp_gdf.columns]]
    shp_gdf.to_file(args.shapefile, driver="ESRI Shapefile")
    print(f"Wrote shapefile {args.shapefile} ({len(shp_gdf)} rows)")


if __name__ == "__main__":
    main()
