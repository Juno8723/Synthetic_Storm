"""
Task 1 - Step 3: Build the processed HUC8 summary table.

Reads the existing local Alabama HUC8 shapefile (read-only) and writes a
flat CSV summary to data/processed/huc_summary/alabama_huc8_summary.csv.

This table is a lightweight reference used downstream when building the
storm scenario template. It does not alter the source shapefile.
"""

import geopandas as gpd

SHAPEFILE_PATH = "USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp"
SOURCE_FOLDER = "USGS_Alabama_WBD_HUC8/"
OUTPUT_PATH = "data/processed/huc_summary/alabama_huc8_summary.csv"


def main():
    gdf = gpd.read_file(SHAPEFILE_PATH)
    crs_string = str(gdf.crs)

    # Note for HUC8s whose STATES attribute does not list 'AL' — these are
    # boundary-adjacent watersheds included in the source extract.
    def make_note(states):
        if "AL" not in states:
            return f"Border-adjacent HUC8 included in extract (STATES={states}, no 'AL')"
        return ""

    summary = gdf[["HUC8", "NAME", "STATES", "AREASQKM", "AREAACRES"]].copy()
    summary = summary.rename(
        columns={
            "HUC8": "huc8_id",
            "NAME": "huc8_name",
            "STATES": "states",
            "AREASQKM": "area_sqkm",
            "AREAACRES": "area_acres",
        }
    )
    summary["source_folder"] = SOURCE_FOLDER
    summary["geometry_available"] = gdf.geometry.notnull() & ~gdf.geometry.is_empty
    summary["crs"] = crs_string
    summary["notes"] = gdf["STATES"].apply(make_note)

    # Column order per task spec (required cols first, extras retained for context)
    ordered_cols = [
        "huc8_id",
        "huc8_name",
        "source_folder",
        "geometry_available",
        "crs",
        "notes",
        "states",
        "area_sqkm",
        "area_acres",
    ]
    summary = summary[ordered_cols].sort_values("huc8_id").reset_index(drop=True)

    summary.to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {len(summary)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
