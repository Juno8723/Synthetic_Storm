# Synthetic Storm — NOAA Atlas 14 Controlled Storm Ensemble

## Task 1: Synthetic Storm Input Data Preparation

### HUC8 boundary data
The Alabama HUC8 watershed boundary dataset used for this project already existed
locally in `USGS_Alabama_WBD_HUC8/` (USGS Watershed Boundary Dataset, shapefile
`AlabamaHUC8.shp`). No new HUC8 dataset was downloaded. The shapefile was read
only for inspection (`scripts/inspect_huc8_shapefile.py`) and was not modified.

Key facts about the source shapefile:
- HUC8 ID field: `HUC8`
- Watershed name field: `NAME`
- Area fields: `AREASQKM`, `AREAACRES`
- State coverage field: `STATES`
- CRS: `EPSG:26916` (NAD83 / UTM Zone 16N)
- 59 HUC8 units, all with valid, non-empty polygon geometries and unique HUC8 IDs
- A few HUC8s (e.g. Sequatchie, Pascagoula) are border-adjacent watersheds whose
  `STATES` value does not include `AL`; these were included in the original
  extract and are flagged in the summary table's `notes` column rather than
  removed.

### Processed HUC8 summary
`data/processed/huc_summary/alabama_huc8_summary.csv` is a flat-table summary
derived from the shapefile (via `scripts/build_huc8_summary.py`), containing
`huc8_id`, `huc8_name`, `source_folder`, `geometry_available`, `crs`, and
`notes` for each of the 59 HUC8 units.

### Storm scenario template
`data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_template.csv`
was generated (via `scripts/build_storm_scenario_template.py`) as the full
cross-product of:
- All 59 Alabama HUC8 IDs
- Return periods: 5, 10, 50, 100, 200, 500 years
- Durations: 6, 12, 24, 96 hours
- Temporal patterns: early_peak, middle_peak, late_peak, balanced

This produces 5,664 scenario rows. **This table is a scenario design table,
not a final rainfall forcing file.** No rainfall depth values have been
invented or estimated: `rainfall_depth` is set to `TBD`, `rainfall_depth_source`
is set to `"NOAA Atlas 14 PFDS - to be extracted"`,
`temporal_distribution_source` is set to
`"NOAA Atlas 14 temporal distribution - to be assigned"`, and `status` is set
to `"pending_atlas14_depth"` for every row.

### Data inventory
`data/metadata/data_inventory.csv` tracks all datasets used or planned for
this project, including the local HUC8 boundary data, the derived summary and
scenario tables, and the NOAA Atlas 14 precipitation-frequency and temporal
distribution datasets that still need to be obtained.

### Next step
The next step is **NOAA Atlas 14 rainfall-depth extraction** — completed in
Task 2 below.

## Task 2: Reproducible NOAA Atlas 14 Rainfall-Depth Extraction

### Spatial scope
The local HUC8 shapefile contains **full HUC8 watershed polygons that
intersect Alabama** — they are not clipped or masked to the Alabama state
boundary. Every Task 2 rainfall-depth output therefore carries three fixed
columns to keep this unambiguous: `geometry_scope = full HUC8 polygon`,
`selection_rule = intersects Alabama`, `state_clipped = false`. Rainfall-depth
values in this project represent statistics over the **full HUC8 watershed**,
not Alabama-clipped statistics.

### GIS-grid extraction was investigated and used
NOAA Atlas 14 GIS grids were investigated as an alternative to the PFDS
point-query interface and found to be officially available for Volume 9
(Southeastern States, which covers Alabama) at
`https://hdsc.nws.noaa.gov/pub/hdsc/data/se/` — zipped Arc/Info ASCII grids
(`.asc`) with `.prj` and FGDC `.xml` metadata, CRS EPSG:4269 (NAD83
geographic). **PFDS point query is not the only possible method.** Two
methods were compared (HUC8-centroid PFDS point estimate vs. GIS-grid-based
full-HUC8 zonal statistics); the **preferred method for this project is
full-HUC8 zonal statistics using the official NOAA Atlas 14 GIS grids**,
since the polygons are large enough that a single centroid point would not
represent spatial rainfall variability well, and the official grids were
confirmed directly downloadable. See
`scripts/README_task2_atlas14_extraction.md` for the full comparison and
rationale.

### Outputs
- `data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv`
  — 1,416 rows (59 HUC8 x 6 return periods x 4 durations), zonal mean rainfall
  depth per full HUC8 polygon. **All 1,416 rows now have `status = extracted`.**
- `data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv`
  — 5,664 rows, the Task 1 template joined with extracted depths. **All 5,664
  rows now have `status = atlas14_depth_extracted`.** The same `rainfall_depth`
  is repeated across `early_peak`, `middle_peak`, `late_peak`, and `balanced`
  for a given HUC8/return-period/duration, since rainfall depth does not vary
  by temporal pattern. The original Task 1 template file was **not**
  overwritten.

### Supplement: HUC8 06020004 (Sequatchie) filled using Volume 2
HUC8 06020004 (Sequatchie) intersects Alabama but falls primarily in the
Tennessee River / Ohio River Basin, outside NOAA Atlas 14 Volume 9
(Southeastern States) grid coverage. It was initially left `pending`. A
supplement step (`scripts/supplement_sequatchie_volume2_atlas14.py`)
investigated and confirmed that **NOAA Atlas 14 Volume 2 (Ohio River Basin
and Surrounding States) GIS grids are officially available** at
`https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/`, in the same zipped
Arc/Info-ASCII-grid format as Volume 9, but with a different native CRS
(`EPSG:4322`, WGS72 geographic, vs. Volume 9's `EPSG:4269`, NAD83) and a
different NODATA value (`-999` vs. `-9`). All 24 required Volume 2 grids
(6 return periods x 4 durations) were downloaded and used to compute
full-HUC8 zonal-mean rainfall depths **for HUC8 06020004 only** — no other
HUC8's values were touched or recomputed.

- **HUC8 06020004 (Sequatchie): filled using NOAA Atlas 14 Volume 2** (Ohio
  River Basin and Surrounding States).
- **All other 58 HUC8s: filled using NOAA Atlas 14 Volume 9** (Southeastern
  States), as in the original Task 2 run.
- Geometry scope is unchanged: `full HUC8 polygon`, `intersects Alabama`,
  `state_clipped = false` — Sequatchie's values are still a full-HUC8-polygon
  statistic, not clipped to Alabama or Tennessee.
- Backups of the pre-supplement depth and scenario tables were saved under
  `data/metadata/backups/` before either file was modified in place.

See `scripts/README_task2_atlas14_extraction.md` for full details.

### Temporal distributions were only inventoried
Task 2D checked NOAA Atlas 14 temporal distribution availability for Volume 9
(6-, 12-, 24-, 96-hour durations; 2 temporal distribution regions) and
recorded the results in
`data/metadata/atlas14_temporal_distribution_inventory.csv`. The region
*boundary* shapefile was downloaded and confirmed; the per-area,
per-duration comma-delimited distribution tables require a manual
interactive download (no static URL exists). **No temporal pattern has been
assigned to any HUC8 yet, and no hyetographs have been generated** — both
are Task 3 items.

### GIS-ready Task 2 outputs
The completed Task 2 rainfall-depth table was exported into GIS-ready
spatial layers so results can be opened directly in QGIS or ArcGIS Pro:
`data/processed/gis/atlas14_huc8_rainfall_depths.gpkg` (GeoPackage). Start
with the **`atlas14_depths_100yr_24hr`** layer as the recommended first
inspection view. As with every Task 2 output, these are **full HUC8
polygons intersecting Alabama, not Alabama-clipped polygons**, and they show
**design rainfall depth by watershed — not flood inundation extent or
depth**. See `data/processed/gis/README_gis_outputs.md` for the full layer
list, shapefile field-name mapping, and symbology guidance.

## Task 3: NOAA Temporal Distribution and Synthetic Hyetograph Generation

### What was done
Task 3 converted Task 2's rainfall depths (a single inches value per
HUC8/return-period/duration) into time-varying synthetic hyetographs by
applying official NOAA Atlas 14 temporal distribution curves. This
required: (1) a correction to Task 2D's finding that temporal CSVs needed
manual download — the client-side JavaScript on the NOAA temporal page
revealed a deterministic, directly-downloadable URL pattern, confirmed
working for all 12 required files; (2) assigning each full HUC8 polygon to
a NOAA temporal distribution area (Mississippi Valley or Southeast region
for Volume 9, via equal-area overlap; Sequatchie assigned to Volume 2's
single area to stay consistent with its Task 2 rainfall-depth source);
(3) parsing two different NOAA file layouts into one unified curve table;
(4) mapping this project's 4 temporal-pattern labels to NOAA's 5 case
groups; and (5) generating incremental/cumulative rainfall hyetographs.

### Unresolved ambiguity: `middle_peak`
`early_peak`, `late_peak`, and `balanced` map unambiguously to NOAA's
First-Quartile Case, Fourth-Quartile Case, and All Cases respectively.
**`middle_peak` does not resolve cleanly**: NOAA provides two distinct
"middle-timing" cases (Second-Quartile, Third-Quartile) with no documented
tiebreaker, and a PDF-based documentation check could not be completed
(no PDF-text-extraction tool installed, not requested for this narrow
purpose). Per instructions, this was **not silently guessed** — it is
marked `mapping_review_required` in
`data/metadata/task3_temporal_pattern_mapping.csv`, and no hyetograph was
generated for `middle_peak` scenarios (1,416 of 5,664, i.e. 25%). This is
the single largest open item — see
`scripts/README_task3_hyetograph_generation.md` for how to resolve it.

### Scripts created
`inspect_atlas14_temporal_distribution_files.py`,
`assign_huc8_temporal_regions.py`, `build_atlas14_temporal_templates.py`,
`create_task3_temporal_pattern_mapping.py`,
`generate_atlas14_hyetographs.py`, `export_task3_gis_layers.py`,
`plot_sample_hyetographs.py`, `validate_task3_hyetographs.py`,
`validate_task3_gis_outputs.py` — all under `scripts/`, each with CLI
arguments and documented defaults.

### Results created
- `data/metadata/task3_temporal_file_inventory.csv`,
  `huc8_temporal_distribution_assignment.csv`,
  `task3_temporal_pattern_mapping.csv`
- `data/processed/hyetograph_templates/atlas14_temporal_distribution_templates.csv`
  (19,440 parsed curve-value rows)
- `data/processed/hyetographs/atlas14_controlled_storm_hyetographs_long.csv`
  (194,664 rows: full time series for 4,248 resolved scenarios + 1,416
  placeholder rows for pending `middle_peak` scenarios)
- `data/processed/hyetographs/atlas14_controlled_storm_hyetographs_summary.csv`
  (5,664 rows — one per scenario)

### GIS visualization outputs created
`data/processed/gis/task3_hyetograph_summary.gpkg` — 10 layers
(`huc8_temporal_distribution_assignment` plus `hyetograph_summary_all` and
8 representative scenario layers), plus 9 shapefiles in
`data/processed/gis/shapefiles_task3/`. See
`data/processed/gis/README_task3_gis_outputs.md`. Four of the 8
representative layers use `middle_peak` and have null
`max_incremental_rainfall`/`time_of_max_incremental_rainfall` (by design,
not error) pending the mapping resolution above.

### Diagnostic figures created
5 curated PNGs in `figures/task3_hyetographs/` (not one per scenario):
three location comparisons (north/central/south Alabama, 100yr/24hr,
early/late/balanced), one duration comparison (only the resolvable
96hr/balanced combination plotted), and one placeholder figure for the
return-period comparison (fully blocked — all 6 requested combinations are
`middle_peak`). See `figures/task3_hyetographs/task3_plot_inventory.csv`.

### Validation results
Tabular validation (`validate_task3_hyetographs.py`): **all 14 checks
PASS** across all 4,248 resolved scenarios (mass balance, non-decreasing
cumulative rainfall, no duplicates, rainfall_depth consistency with Task 2,
Sequatchie Volume 2 attribution, no invented values for pending scenarios).
GIS validation (`validate_task3_gis_outputs.py`): **all 15 checks PASS**
(layer/feature counts, geometry validity, CRS, populated fields, full
non-clipped HUC8 geometry, documented shapefile field-name mapping).

### Unresolved issues
1. **`middle_peak` temporal-case mapping** — the primary open item (see above).
2. Four Tennessee-basin HUC8s (Upper Elk, Lower Elk, Middle
   Tennessee-Chickamauga, Lower Tennessee-Beech) have low-confidence
   temporal-area overlap with the Volume 9 shapefile, flagged
   `low_confidence_overlap_assignment` — still assigned and usable, but
   worth review.

### Whether Task 4 can begin
**Partially.** Task 4 (HEC-HMS input preparation) can begin now for the
4,248 resolved scenarios (`early_peak`, `late_peak`, `balanced` — 75% of
all scenarios). It cannot proceed for `middle_peak` scenarios until a
human reviewer resolves the NOAA quartile-case ambiguity documented above
and reruns `scripts/generate_atlas14_hyetographs.py` onward. As always,
these are rainfall input datasets only — not flood inundation maps.

**Superseded by "Task 3 Final" below**, which resolves the `middle_peak`
ambiguity entirely by switching to NOAA-native case terminology.

## Task 3 Final: NOAA-Native Temporal Distribution and Synthetic Hyetograph Database

### What was done
The `middle_peak` ambiguity above was resolved not by picking a case
arbitrarily, but by discarding the early/middle/late/balanced scheme
entirely and using **NOAA's own five native temporal case labels**
directly: `first_quartile_peak`, `second_quartile_peak`,
`third_quartile_peak`, `fourth_quartile_peak`, `all_cases`. Since every
NOAA case now maps to exactly one final label, there is no leftover "which
case is the middle one" question. Two final products were built:

- **Product A** (`*_main_noaa_native_*`): the 50th-percentile curve for
  each of the 5 NOAA cases. **7,080 scenarios** (59 HUC8 x 6 return
  periods x 4 durations x 5 cases), all fully resolved. **Recommended for
  Task 4.**
- **Product B** (`*_full_temporal_sensitivity_*`): every officially
  available NOAA percentile curve - inventoried dynamically and found to
  be 9 percentiles per case (10%-90%, not just 10/50/90), giving 45 curves
  per HUC8/return-period/duration. **63,720 scenarios**, all fully
  resolved. A sensitivity-analysis archive, not the default Task 4 input.

The original Task 3 partial-run outputs (early/middle/late/balanced) were
left untouched on disk; all Task 3 Final outputs use new `_final` /
`_main_noaa_native` / `_full_temporal_sensitivity` filenames.

### Scripts created
`create_task3_main_noaa_native_scenarios.py`,
`generate_atlas14_hyetographs_main_noaa_native.py`,
`create_task3_full_sensitivity_scenarios.py`,
`generate_atlas14_hyetographs_full_temporal_sensitivity.py`,
`export_task3_final_gis_layers.py`, `plot_task3_final_hyetographs.py`,
`validate_task3_final_hyetographs.py`, `validate_task3_final_gis_outputs.py`,
`README_task3_final_hyetograph_generation.md`. Three original Task 3
scripts (`inspect_atlas14_temporal_distribution_files.py`,
`assign_huc8_temporal_regions.py`, `build_atlas14_temporal_templates.py`)
were updated in place to also write new `_final` outputs alongside their
original (preserved) outputs.

### Results created
`task3_final_temporal_file_inventory.csv` (549 rows),
`huc8_temporal_distribution_assignment_final.csv` (59 rows),
`task3_main_noaa_native_temporal_curve_mapping.csv` (5 rows),
`task3_full_sensitivity_temporal_curve_inventory.csv` (540 rows),
`atlas14_temporal_distribution_templates_final.csv` (19,440 rows), two
scenario tables (7,080 + 63,720 rows), and four hyetograph tables:
Product A long/summary (322,080 / 7,080 rows), Product B long/summary
(2,898,720 / 63,720 rows).

### GIS visualization outputs created
Two GeoPackages: `task3_hyetograph_summary_main_noaa_native.gpkg` (1.6 GB,
13 layers) and `task3_hyetograph_summary_full_temporal_sensitivity.gpkg`
(12.9 GB, 16 layers), plus representative shapefiles in
`shapefiles_task3_main_noaa_native/` and
`shapefiles_task3_full_temporal_sensitivity/`. See
`data/processed/gis/README_task3_main_noaa_native_gis_outputs.md` and
`README_task3_full_temporal_sensitivity_gis_outputs.md`. Product B's
63,720-feature `_all` layer is real and fully valid but impractical to
open directly in desktop GIS - use the 15 representative layers instead.

### Diagnostic figures created
5 Product A PNGs (3 locations x 5 NOAA cases, 1 duration comparison, 1
return-period comparison - all fully resolved, no blocked/placeholder
figures this time) in `figures/task3_main_noaa_native/`, and 5 Product B
PNGs (percentile-sensitivity comparison per NOAA case) in
`figures/task3_full_temporal_sensitivity/`, plus two plot inventories.

### Validation results
Tabular (`validate_task3_final_hyetographs.py`): **all checks PASS** for
both products (16 checks x 2 products), including mass balance across all
7,080 + 63,720 scenarios. One genuine finding along the way: NOAA's own
published cumulative-percent tables (2-decimal rounding) contain tiny
non-monotonic dips near some curves' tails - confirmed present in the raw
source file, not a bug. Per project rules the curves were never smoothed;
instead the validation tolerance was corrected to check monotonicity in
percentage-point space (depth-independent) rather than a fixed inches
cutoff, since the earlier fixed-inches check incorrectly scaled with
rainfall depth. GIS (`validate_task3_final_gis_outputs.py`): **all checks
PASS** for both products (16 + 15 checks) - Product B's huge `_all` layer
was validated via attribute-only reads to avoid a multi-GB memory spike
that occurred on the first validation attempt.

### Unresolved issues
Only the same minor, previously-documented items: 4 Tennessee-basin HUC8s
with low-confidence Volume 9 temporal-area overlap, and Product B's `_all`
GIS layer being large (not a defect, just not meant for direct desktop-GIS
loading). **The `middle_peak` ambiguity itself is fully resolved** - no
outstanding mapping questions remain.

### Recommended files for Task 4
**Task 4 main analysis:** `data/processed/hyetographs/atlas14_controlled_storm_hyetographs_main_noaa_native_long.csv`
(Product A, all 7,080 scenarios resolved).
**Future temporal sensitivity analysis:** `data/processed/hyetographs/atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_long.csv`
(Product B, 63,720 scenarios across all 45 NOAA percentile curves) - not
the default Task 4 input.
