# Task 3 Final: NOAA-Native Temporal Distribution and Synthetic Hyetograph Database

## Purpose

Task 3 converts Task 2's NOAA Atlas 14 rainfall depths (a single inches
value per HUC8/return-period/duration) into time-varying synthetic
hyetographs by applying official NOAA Atlas 14 temporal distribution
curves. An initial Task 3 run used project-defined labels
(early_peak/middle_peak/late_peak/balanced) and could not resolve
`middle_peak`, because NOAA Atlas 14 does not use that terminology - it
uses quartile-based temporal cases. **This final build replaces that
scheme entirely** with NOAA's own five case labels, eliminating the
ambiguity, and adds a second product archiving every officially available
NOAA percentile curve for future sensitivity analysis. This task does
**not** run HEC-HMS or any flood inundation model.

## Precipitation depth vs. cumulative/incremental rainfall vs. intensity vs. volume

- **Precipitation depth** (`rainfall_depth`, inches): total rainfall over
  the entire storm duration for a return period - what Task 2 extracted.
  No timing information.
- **Cumulative rainfall depth** (`cumulative_rainfall`, inches): running
  total from storm start to time `t`. Equals
  `rainfall_depth x cumulative_fraction(t)`.
- **Incremental rainfall depth** (`incremental_rainfall`, inches): rainfall
  during one time step - `cumulative_rainfall(t) - cumulative_rainfall(t-1)`.
  This is the actual hyetograph value fed to a hydrologic model.
- **Rainfall intensity** (inches/hour): `incremental_rainfall / time_step_hour`
  - not computed or stored directly here; derivable downstream.
- **Rainfall volume** (e.g. acre-feet): depth x watershed area - never
  computed anywhere in this project. Units stay in **inches** throughout.

## NOAA temporal distribution curves are cumulative-percentage curves

Each NOAA file tabulates five groups per duration: First/Second/Third/
Fourth-Quartile Case (conditioned on which quarter of the duration held
the greatest precipitation fraction) and All Cases (the combined,
case-independent distribution). Within each case, **nine** percentile
curves (10%-90%, confirmed by inventory - not assumed) describe the spread
of realizations; the 50th-percentile is the median/typical curve.

Two file layouts were parsed: Volume 9 files are "long" format with
absolute-hour time steps (0.5-hour resolution); Volume 2 files are
"wide"/transposed with a fixed 13-point percent-of-duration axis,
algebraically rescaled to absolute hours (`time_hour = percent_of_duration/100
* duration_hour` - an exact rescaling of the file's own axis, not
interpolation).

## Volume 9 temporal distribution area 1 and 2

- **Area 1 = Mississippi Valley region** (western part of the Volume 9
  domain; confirmed via centroid ~-89.4 deg longitude).
- **Area 2 = Southeast region** (eastern/peninsular part; centroid
  ~-81.7 deg longitude).

## HUC8 temporal region assignment method

Full HUC8 polygons and the Volume 9 temporal-area shapefile were both
reprojected to EPSG:5070 (equal-area) and overlap area was computed; each
HUC8 was assigned to the area with the largest overlap (secondary overlap
preserved). All 58 Volume-9-covered HUC8s were assigned to Area 1
(Alabama's full extent lies west of the Area 1/2 boundary). **HUC8
06020004 (Sequatchie)** is assigned directly to Volume 2's single
"general" temporal area (no separate area shapefile exists for Volume 2)
to stay consistent with its Task 2 Volume-2-sourced rainfall depth. Four
Tennessee-basin HUC8s are flagged `low_confidence_overlap_assignment` in
`huc8_temporal_distribution_assignment_final.csv` where most of their area
falls outside the mapped Volume 9 temporal-area extent.

## Why NOAA quartile cases, not early/middle/late/balanced

The original Task 3 scheme invented four labels that do not correspond
1:1 to NOAA's five native cases: `early_peak` and `late_peak` map cleanly
to First- and Fourth-Quartile Case, but `middle_peak` had two equally
valid NOAA candidates (Second- and Third-Quartile Case) with no documented
tiebreaker. This final build uses NOAA's own five case labels directly -
**first_quartile_peak, second_quartile_peak, third_quartile_peak,
fourth_quartile_peak, all_cases** - so every case has an exact, unambiguous
NOAA identity. No case is dropped, invented, or merged.

## Product A: main NOAA-native 50th-percentile ensemble

Recommended for Task 4 HEC-HMS input preparation. Uses the 50th-percentile
(median) curve for each of NOAA's 5 native cases:
`first_quartile_peak_p50`, `second_quartile_peak_p50`,
`third_quartile_peak_p50`, `fourth_quartile_peak_p50`, `all_cases_p50`.
**7,080 scenarios** (59 HUC8 x 6 return periods x 4 durations x 5 cases),
all fully resolved - no ambiguity, no pending scenarios.

## Product B: full NOAA temporal sensitivity archive

A database/archive for future temporal-shape sensitivity analysis - not
necessarily the default Task 4 input. Uses **every** officially available
NOAA percentile curve, inventoried dynamically rather than assumed: 5
cases x **9** percentiles (10%-90%, confirmed present - not just 10/50/90)
= 45 curves per HUC8/return-period/duration. **63,720 scenarios** (59 HUC8
x 6 RP x 4 dur x 45 curves), all fully resolved.

## Input files

- `data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv` (Task 2)
- `data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv` (Task 2)
- `USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp` (Task 1, read-only, never modified)
- `data/metadata/task3_temporal_file_inventory.csv`, `huc8_temporal_distribution_assignment.csv`,
  `atlas14_temporal_distribution_templates.csv` (original Task 3 run - preserved, not overwritten)
- `data/raw/atlas14_temporal_distributions/` (raw NOAA files, never modified)

## Output files

**Metadata:** `task3_final_temporal_file_inventory.csv` (549 rows: 540
curve rows + 9 shapefile-component rows),
`huc8_temporal_distribution_assignment_final.csv` (59 rows),
`task3_main_noaa_native_temporal_curve_mapping.csv` (5 rows),
`task3_full_sensitivity_temporal_curve_inventory.csv` (540 rows), plus 4
validation report/summary pairs.

**Templates:** `atlas14_temporal_distribution_templates_final.csv` (19,440 rows).

**Scenario tables:** `atlas14_controlled_storm_scenarios_main_noaa_native.csv`
(7,080 rows), `atlas14_controlled_storm_scenarios_full_temporal_sensitivity.csv`
(63,720 rows).

**Hyetographs:** `..._main_noaa_native_long.csv` (322,080 rows),
`..._main_noaa_native_summary.csv` (7,080 rows),
`..._full_temporal_sensitivity_long.csv` (2,898,720 rows, ~1.1 GB),
`..._full_temporal_sensitivity_summary.csv` (63,720 rows).

**GIS:** two GeoPackages (`task3_hyetograph_summary_main_noaa_native.gpkg`,
1.6 GB; `task3_hyetograph_summary_full_temporal_sensitivity.gpkg`, 12.9 GB)
plus representative shapefiles and two GIS READMEs - see
`data/processed/gis/README_task3_main_noaa_native_gis_outputs.md` and
`README_task3_full_temporal_sensitivity_gis_outputs.md`.

**Figures:** 5 Product A + 5 Product B PNGs in `figures/task3_main_noaa_native/`
and `figures/task3_full_temporal_sensitivity/`, plus plot inventories.

## Python scripts (run in this order)

```
python scripts/inspect_atlas14_temporal_distribution_files.py
python scripts/assign_huc8_temporal_regions.py
python scripts/build_atlas14_temporal_templates.py
python scripts/create_task3_main_noaa_native_scenarios.py
python scripts/generate_atlas14_hyetographs_main_noaa_native.py
python scripts/create_task3_full_sensitivity_scenarios.py
python scripts/generate_atlas14_hyetographs_full_temporal_sensitivity.py
python scripts/export_task3_final_gis_layers.py
python scripts/plot_task3_final_hyetographs.py
python scripts/validate_task3_final_hyetographs.py
python scripts/validate_task3_final_gis_outputs.py
```

Steps 1-3 write to new `_final` filenames and do not overwrite the
original Task 3 partial-run outputs (which remain on disk, e.g.
`data/metadata/huc8_temporal_distribution_assignment.csv` vs. this run's
`..._final.csv`).

## Validation logic

`validate_task3_final_hyetographs.py` checks, per product: scenario count,
every scenario has a hyetograph, mass balance (sum of increments and final
cumulative rainfall equal `rainfall_depth`, tolerance 0.02in), final
cumulative percent = 100, monotonicity, duration match, no duplicate time
steps, `rainfall_depth` matches the Task 2 depth table exactly, required
fields populated, Sequatchie uses Volume 2, no invented values, and (for
Product B) every percentile identifier traces to an official NOAA curve.
Uses vectorized pandas groupby aggregation throughout (not per-scenario
Python loops) to stay fast at Product B's ~2.9M-row scale.

**A genuine, diagnosed finding during validation:** NOAA's own published
`cumulative_percent` tables (rounded to 2 decimals) occasionally contain a
tiny non-monotonic dip near a curve's tail (e.g. 99.67% -> 99.66% -> 99.67%
for Volume 9/Area 1/96-hour/Third-Quartile Case/80th-percentile - confirmed
present in the raw source file, within `build_atlas14_temporal_templates.py`'s
own 0.5-point validation tolerance). Per project rules, curves are never
smoothed to hide this. Monotonicity is instead validated in
percentage-point space (depth-independent, tolerance 0.05 points) rather
than a fixed inches cutoff, since the inches-domain wobble scales with
`rainfall_depth` - this correctly passes all 7,080 + 63,720 scenarios
while still catching genuine bugs (which would produce far larger
violations).

`validate_task3_final_gis_outputs.py` checks layer presence, feature
counts, geometry validity, CRS, populated fields, full (non-clipped) HUC8
geometry, and documented shapefile field-name mapping - for Product B's
63,720-feature `_all` layer, geometry/CRS/feature-count checks use
attribute-only reads (`pyogrio`, no geometry decode) to avoid a multi-GB
memory spike, with geometry validity instead confirmed via the 59
deduplicated source HUC8 polygons (every feature's geometry is a verbatim
copy, never independently computed).

## Known limitations

1. Product B's `hyetograph_summary_full_temporal_sensitivity_all` GIS
   layer is ~12.9 GB (63,720 features x full HUC8 polygon geometry) -
   functionally correct and validated, but impractical to open directly in
   desktop GIS software; use the 15 representative layers or the tabular
   CSVs instead (see the Product B GIS README).
2. Four Tennessee-basin HUC8s have low-confidence Volume 9 temporal-area
   overlap (documented, still assigned and usable).
3. NOAA's own published cumulative-percent rounding produces sub-tolerance
   non-monotonicity noise near some curves' tails (documented above, not a
   defect).
4. Only Volume 9 (Area 1) and Volume 2 (general) temporal data are used,
   matching the two volumes actually needed by Task 2's rainfall-depth
   attribution; Volume 9 Area 2 curves were parsed and inventoried but are
   not joined to any HUC8 (none is assigned there).

## Viewing outputs in ArcGIS Pro

See `data/processed/gis/README_task3_main_noaa_native_gis_outputs.md` and
`README_task3_full_temporal_sensitivity_gis_outputs.md`, section "Opening
in ArcGIS Pro." For Product B, load representative layers individually -
not the 12.9 GB `_all` layer.

## Connection to Task 4 (HEC-HMS input preparation)

**Use Product A** (`atlas14_controlled_storm_hyetographs_main_noaa_native_long.csv`,
filtered to `status = atlas14_hyetograph_generated` - all 7,080 scenarios
qualify) as the primary Task 4 input: incremental rainfall time series per
HUC8/return-period/duration/NOAA-case, ready to format into HEC-HMS
meteorological model input. **Use Product B**
(`atlas14_controlled_storm_hyetographs_full_temporal_sensitivity_long.csv`)
only for future temporal-shape sensitivity studies, not as the default
Task 4 input. **Task 3 outputs remain rainfall input data only - they are
not flood inundation maps**, and running HEC-HMS or any inundation model
is explicitly out of scope for this task.
