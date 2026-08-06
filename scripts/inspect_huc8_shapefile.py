"""
Task 1 - Step 1: Inspect the existing Alabama HUC8 shapefile.

Read-only inspection. This script does NOT modify the source shapefile.
It reports the schema, CRS, and basic data-quality checks so the results
can be documented in data/metadata and used to build the HUC8 summary
table (see build_huc8_summary.py).
"""

import geopandas as gpd

SHAPEFILE_PATH = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"


def main():
    gdf = gpd.read_file(SHAPEFILE_PATH)

    # --- CRS ---
    print("=== Coordinate Reference System ===")
    print(gdf.crs)
    print()

    # --- Schema ---
    print("=== Fields (dtypes) ===")
    print(gdf.dtypes)
    print()

    # --- Row / geometry counts ---
    print("=== Row count ===")
    print(len(gdf))
    print()

    print("=== Geometry types present ===")
    print(gdf.geometry.geom_type.unique())
    print()

    # --- Data quality checks on key identifier fields ---
    print("=== HUC8 field quality ===")
    print("unique HUC8 values:", gdf["HUC8"].nunique())
    print("null HUC8 values:", gdf["HUC8"].isnull().sum())
    print("null NAME values:", gdf["NAME"].isnull().sum())
    print("invalid geometries:", (~gdf.geometry.is_valid).sum())
    print("empty geometries:", gdf.geometry.is_empty.sum())
    print()

    # --- STATES field: flag HUC8s whose STATES value does not include AL ---
    # These are boundary-adjacent watersheds included in the extract for
    # spatial continuity (e.g., a HUC8 that drains into/borders Alabama).
    non_al = gdf[~gdf["STATES"].str.contains("AL")]
    print("=== HUC8s where STATES does not include 'AL' ===")
    print(non_al[["HUC8", "NAME", "STATES", "AREASQKM"]].to_string(index=False))


if __name__ == "__main__":
    main()
