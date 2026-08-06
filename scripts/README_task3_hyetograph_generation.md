# Task 3: NOAA Atlas 14 Temporal Distribution Assignment and Synthetic Hyetograph Generation

## Purpose

Task 2 produced NOAA Atlas 14 precipitation-frequency **rainfall depths**
(a single number in inches per HUC8 x return period x duration). Task 3
converts each of those depths into a **time-varying synthetic hyetograph**
- how that total depth is distributed over the storm duration - by
applying official NOAA Atlas 14 temporal distribution curves. This task
does **not** run HEC-HMS, does **not** run any flood inundation model, and
does **not** produce flood maps. It only assigns temporal distributions,
builds hyetographs, and visualizes hyetograph properties.

## Precipitation depth vs. cumulative/incremental rainfall vs. intensity vs. volume

These five terms are easy to conflate and are used precisely throughout
Task 3:

- **Precipitation depth** (`rainfall_depth`, inches): the total rainfall
  accumulated over the *entire* storm duration for a given return period.
  This is what Task 2 extracted from NOAA Atlas 14 - a single number per
  scenario, with no timing information.
- **Cumulative rainfall depth** (`cumulative_rainfall`, inches): the
  running total of rainfall accumulated from the start of the storm up to
  a given time `t`. Equals `rainfall_depth x cumulative_fraction(t)`, where
  `cumulative_fraction` comes from the NOAA temporal distribution curve.
  Always non-decreasing; equals `rainfall_depth` at the final time step.
- **Incremental rainfall depth** (`incremental_rainfall`, inches): the
  rainfall that fell *during one time step* -
  `cumulative_rainfall(t) - cumulative_rainfall(t-1)`. This is the actual
  hyetograph "bar height" and is what a hydrologic model consumes as input.
- **Rainfall intensity** (inches/hour): `incremental_rainfall / time_step_hour`.
  Task 3 does **not** compute or store intensity directly - the NOAA
  time steps are uneven in a way that makes depth-per-step the more direct
  and less error-prone quantity to carry; intensity can be derived from
  `incremental_rainfall` and `time_step_hour` downstream if needed.
- **Rainfall volume** (e.g., acre-feet or cubic feet): depth multiplied by
  watershed area. Task 3 never computes this - everywhere in this project,
  units stay in **inches** (a depth), never a volume.

## Data sources used

All from the official NOAA Hydrometeorological Design Studies Center:

- PFDS main page: https://hdsc.nws.noaa.gov/pfds/
- Temporal distributions page: https://hdsc.nws.noaa.gov/pfds/pfds_temporal.html
- Volume 9 (Southeastern States) documentation: https://www.weather.gov/media/owp/hdsc_documents/Atlas14_Volume9.pdf
- Volume 2 (Ohio River Basin and Surrounding States) documentation: https://www.weather.gov/media/owp/oh/hdsc/docs/Atlas14_Volume2.pdf
- Direct data files (discovered and confirmed in this task - see
  "Correction to Task 2D" below):
  `https://hdsc.nws.noaa.gov/pub/hdsc/data/se/se_<area>_<dur>h_temporal.csv`
  (Volume 9) and
  `https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/orb_general_<dur>h_temporal.csv`
  (Volume 2)

### Correction to Task 2D

Task 2D concluded that the per-area, per-duration comma-delimited temporal
distribution curve files required manual download because no static URL
pattern could be found. In this task, inspection of the page source of
`pfds_temporal.html` revealed the client-side JavaScript function
`tempDistDL()`, which builds a fully deterministic download URL. Testing
that URL pattern directly confirmed all 12 files needed by this project
(8 for Volume 9: 2 areas x 4 durations; 4 for Volume 2: 1 area x 4
durations) download successfully with HTTP 200. **This corrects Task 2D:
these files are directly, programmatically downloadable; manual download
was never actually required.** (Task 2D's conclusions about the GIS grids
and the temporal-area boundary shapefile were already correct.)

## NOAA temporal distribution curves are cumulative-percentage curves

Each NOAA temporal distribution file tabulates, for a given
duration/region, **five groups** ("cases"):

- First-, Second-, Third-, and Fourth-Quartile Case: conditioned on which
  quarter of the storm duration contained the single greatest fraction of
  total precipitation.
- All Cases: the combined distribution, not conditioned on any quartile.

Within each case, nine **percentile curves** (10% through 90%) describe
the spread of realizations - at each time step, the tabulated value is the
percentage of total storm precipitation that had fallen by that time in
that percentile of historical cases. The 50th-percentile curve is the
median/typical curve for that case. Values are cumulative percentages of
total precipitation (0 to 100), which this project converts to
`cumulative_fraction` (0 to 1) and then to `cumulative_rainfall` (inches)
by multiplying by `rainfall_depth`.

Two different file layouts had to be parsed (see
`scripts/build_atlas14_temporal_templates.py` docstring for full detail):
Volume 9 files are "long" format with absolute-hour time steps (0.5-hour
resolution); Volume 2 files are "wide"/transposed with a fixed 13-point
percent-of-duration axis, algebraically rescaled to absolute hours
(`time_hour = percent_of_duration/100 * duration_hour`) - an exact,
documented rescaling of the file's own axis, not an interpolation.

## Volume 9 temporal distribution areas 1 and 2

Volume 9 (Southeastern States) has two temporal distribution areas, spatially
defined by the official shapefile `Vol_9_Temporal_Regions.shp` (downloaded
in Task 2D):

- **Area 1 = Mississippi Valley region** (western part of the Volume 9
  domain; centroid at approximately -89.4 deg longitude).
- **Area 2 = Southeast region** (eastern/peninsular part; centroid at
  approximately -81.7 deg longitude, covering peninsular Florida and
  eastern Georgia/South Carolina).

This was confirmed independently in this task by inspecting each region
polygon's centroid and bounds against known geography, in addition to
matching the region definition supplied in the task instructions.

## HUC8 temporal region assignment method (Task 3B)

For the 58 HUC8s covered by Volume 9: HUC8 polygons and the temporal-area
shapefile were both reprojected to an equal-area CRS (EPSG:5070, NAD83 /
Conus Albers), then the overlap area between each full HUC8 polygon and
each temporal-distribution-area polygon was computed. Each HUC8 was
assigned to the area with the largest overlap; secondary overlap (if any)
is preserved in `secondary_temporal_distribution_area` /
`secondary_overlap_fraction`.

**HUC8 06020004 (Sequatchie)** is not assigned via spatial overlap. Its
rainfall depth was already sourced from NOAA Atlas 14 **Volume 2** in Task
2 (because it falls outside Volume 9's GIS-grid coverage). Volume 2
provides only a single temporal distribution area ("general") for its
entire domain - there is no separate area shapefile to overlap against.
To keep rainfall depth and temporal distribution sourced from the same
Atlas 14 volume, Sequatchie is assigned directly to Volume 2's single area,
per the project instruction not to force Volume 9 temporal curves onto it.

**Data-quality flag:** four Tennessee-River-basin HUC8s (Upper Elk, Lower
Elk, Middle Tennessee-Chickamauga, Lower Tennessee-Beech) have most of
their area falling *outside* the Volume 9 temporal-area shapefile's mapped
extent, even though the Volume 9 rainfall-depth GRID still returned valid
data there (a different NOAA product with a different mapped boundary).
These four are flagged `status = low_confidence_overlap_assignment` in
`data/metadata/huc8_temporal_distribution_assignment.csv` rather than
silently treated as solid.

## Temporal pattern mapping method (Task 3D) - and the unresolved ambiguity

This project's four scenario labels map to NOAA's five case groups as
follows (see `data/metadata/task3_temporal_pattern_mapping.csv` for the
full 48-row table across every volume/area/duration combination):

| Project label | NOAA case | Curve | Status |
|---|---|---|---|
| `early_peak` | First-Quartile Case | 50th percentile (median) | **resolved** |
| `late_peak` | Fourth-Quartile Case | 50th percentile (median) | **resolved** |
| `balanced` | All Cases | 50th percentile (median) | **resolved** |
| `middle_peak` | Second-Quartile Case **or** Third-Quartile Case | - | **mapping_review_required** |

`early_peak`, `late_peak`, and `balanced` map unambiguously to NOAA's own
case definitions. `middle_peak` does not: NOAA provides **two** distinct
"middle-timing" cases, and this project has only **one** middle label.
Nothing in the official NOAA data files, their embedded documentation, or
the region metadata inspected in Task 3A/3C designates one as "the"
middle case or specifies a combination rule. An attempt was made to consult
the Volume 9 PDF directly for additional guidance, but no PDF
text-extraction tool (`pdftotext`, `pypdf`, `pdfplumber`) is installed in
this environment, and installing one was not requested for this narrow,
uncertain-payoff purpose.

**Per project instructions, this ambiguity was not silently resolved.**
Every `middle_peak` row in the mapping table is marked
`status = mapping_review_required`, `mapping_confidence =
unresolved_ambiguous`, and Task 3E does not generate a final hyetograph
time series for any `middle_peak` scenario. This affects 1,416 of 5,664
scenarios (25%) and four of the eight required GIS representative layers.

**To resolve this ambiguity later:** a human reviewer needs to either (a)
choose Second-Quartile or Third-Quartile as the representative case for
`middle_peak` (with documented justification - e.g., consulting the
Volume 2/9 PDF appendices for the number/proportion of historical storms
in each quartile case, which the NOAA data files' own header text says is
in that documentation), or (b) define and document an explicit combination
rule. Once decided, update
`data/metadata/task3_temporal_pattern_mapping.csv` (set the `middle_peak`
rows' `noaa_temporal_case`, `noaa_percentile_or_curve`, `status =
resolved`) and rerun `scripts/generate_atlas14_hyetographs.py` and
downstream GIS/plotting scripts.

## Input files

- `data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv` (Task 2, 5,664 rows)
- `data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv` (Task 2)
- `USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp` (Task 1, read-only, never modified)
- `data/metadata/atlas14_temporal_distribution_inventory.csv` (Task 2D)
- `data/raw/atlas14_temporal_distributions/` (Task 2D shapefile + Task 3A-downloaded curve CSVs)

## Scripts (run in this order)

1. `scripts/inspect_atlas14_temporal_distribution_files.py` - downloads the
   12 required temporal CSVs (if missing) and inspects every file under
   `data/raw/atlas14_temporal_distributions/`.
   -> `data/metadata/task3_temporal_file_inventory.csv`
2. `scripts/assign_huc8_temporal_regions.py` - equal-area overlap
   assignment of each HUC8 to a temporal distribution area.
   -> `data/metadata/huc8_temporal_distribution_assignment.csv`,
   GPKG layer `huc8_temporal_distribution_assignment`, shapefile
3. `scripts/build_atlas14_temporal_templates.py` - parses both NOAA file
   layouts into one unified long-format curve table, with built-in
   validation (non-decreasing, 0->100, no duplicates, duration match).
   -> `data/processed/hyetograph_templates/atlas14_temporal_distribution_templates.csv`
4. `scripts/create_task3_temporal_pattern_mapping.py` - documents the
   scenario-label -> NOAA-case mapping, including the unresolved
   `middle_peak` ambiguity.
   -> `data/metadata/task3_temporal_pattern_mapping.csv`
5. `scripts/generate_atlas14_hyetographs.py` - joins everything and
   computes cumulative/incremental rainfall for resolved scenarios;
   writes one placeholder row (no invented time series) per pending
   `middle_peak` scenario.
   -> `data/processed/hyetographs/atlas14_controlled_storm_hyetographs_long.csv`,
      `data/processed/hyetographs/atlas14_controlled_storm_hyetographs_summary.csv`
6. `scripts/export_task3_gis_layers.py` - GIS layers and shapefiles.
   -> `data/processed/gis/task3_hyetograph_summary.gpkg`,
      `data/processed/gis/shapefiles_task3/*.shp`
7. `scripts/plot_sample_hyetographs.py` - curated diagnostic plots.
   -> `figures/task3_hyetographs/*.png`,
      `figures/task3_hyetographs/task3_plot_inventory.csv`
8. `scripts/validate_task3_hyetographs.py` - tabular validation.
   -> `data/metadata/task3_hyetograph_validation_report.txt`,
      `data/metadata/task3_hyetograph_validation_summary.csv`
9. `scripts/validate_task3_gis_outputs.py` - GIS validation.
   -> `data/metadata/task3_gis_validation_report.txt`,
      `data/metadata/task3_gis_validation_summary.csv`

Rerun the full chain with:
```
python scripts/inspect_atlas14_temporal_distribution_files.py
python scripts/assign_huc8_temporal_regions.py
python scripts/build_atlas14_temporal_templates.py
python scripts/create_task3_temporal_pattern_mapping.py
python scripts/generate_atlas14_hyetographs.py
python scripts/export_task3_gis_layers.py
python scripts/plot_sample_hyetographs.py
python scripts/validate_task3_hyetographs.py
python scripts/validate_task3_gis_outputs.py
```

## GIS outputs

See `data/processed/gis/README_task3_gis_outputs.md` for the full layer
list, shapefile field-name mapping, symbology guidance, and ArcGIS
Pro/QGIS instructions.

## Diagnostic plots

`figures/task3_hyetographs/` contains 5 curated PNGs (not one per
scenario): three location comparisons (northern/central/southern Alabama
HUC8s, 100yr/24hr, early/late/balanced), one duration comparison (only the
one resolvable combination, 100yr/96hr/balanced, is plotted; the three
`middle_peak` combinations are documented as pending on the same figure),
and one placeholder figure for the return-period comparison (entirely
blocked, since all six requested combinations use `middle_peak`). See
`figures/task3_hyetographs/task3_plot_inventory.csv` for the full list.

## Validation logic

`validate_task3_hyetographs.py` checks, for every resolved scenario: sum
of incremental rainfall equals `rainfall_depth` (tolerance 0.02 in),
final cumulative rainfall equals `rainfall_depth`, final cumulative
percent equals 100, cumulative rainfall is non-decreasing, incremental
rainfall is non-negative, final time step matches `duration_hour`, no
duplicate time steps, `rainfall_depth` matches the Task 2 table exactly,
required fields are populated, Sequatchie uses Volume 2, and no rainfall
value was invented for pending scenarios. `validate_task3_gis_outputs.py`
checks layer presence, feature counts, geometry validity, CRS, populated
fields, and that geometry remains the full (non-Alabama-clipped) HUC8 set.

## Known limitations

1. **`middle_peak` is unresolved** (see above) - affects 1,416/5,664
   scenarios and 4/8 representative GIS layers/plots.
2. Four Tennessee-basin HUC8s have low-confidence temporal-area overlap
   (see "HUC8 temporal region assignment method" above).
3. NOAA time steps are used exactly as published (0.5-hour absolute for
   Volume 9; 13 fixed percent-of-duration points for Volume 2, rescaled to
   hours) - no interpolation to a finer or common time step across
   volumes was performed, so Sequatchie's hyetograph has coarser temporal
   resolution than the other 58 HUC8s.
4. Only the "estimate" (not 90% CI) rainfall depths from Task 2 were used;
   CI-bound hyetographs were not generated.

## Viewing outputs in ArcGIS Pro

See `data/processed/gis/README_task3_gis_outputs.md`, section "Opening in
ArcGIS Pro."

## Connection to Task 4 (HEC-HMS input preparation)

Task 3's resolved hyetographs
(`atlas14_controlled_storm_hyetographs_long.csv`, filtered to
`status = atlas14_hyetograph_generated`) provide the incremental rainfall
time series that Task 4 would format into HEC-HMS meteorological model
input (e.g., gage weight / specified hyetograph tables) for each HUC8 and
scenario. Task 4 cannot proceed for `middle_peak` scenarios until the
mapping ambiguity above is resolved. **Task 3 outputs remain rainfall
input data only - they are not flood inundation maps, and running HEC-HMS
or any inundation model is explicitly out of scope for this task.**
