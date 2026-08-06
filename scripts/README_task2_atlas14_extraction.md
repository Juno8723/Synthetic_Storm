# Task 2: NOAA Atlas 14 Rainfall-Depth Extraction Workflow

This document describes the reproducible workflow that extracts NOAA Atlas 14
precipitation-frequency rainfall depths for every Alabama-intersecting full
HUC8 watershed and joins them into the Task 1 storm scenario template.

## Spatial scope (read this first)

The local HUC8 shapefile (`USGS_Alabama_WBD_HUC8/AlabamaHUC8.shp`) contains
**full HUC8 watershed polygons that intersect Alabama** - they are not
clipped or masked to the Alabama state boundary. Every Task 2 output
therefore carries three fixed columns so this is never ambiguous downstream:

- `geometry_scope = full HUC8 polygon`
- `selection_rule = intersects Alabama`
- `state_clipped = false`

Do not describe any Task 2 rainfall statistic as "Alabama-clipped."

## Task 2A/2B findings: GIS grids vs. PFDS point query

NOAA Atlas 14 GIS grids **are** available for Volume 9 (Southeastern States,
which covers Alabama), confirmed by direct inspection on 2026-07-08:

- Official directory: `https://hdsc.nws.noaa.gov/pub/hdsc/data/se/`
- Format: zipped Arc/Info ASCII grid (`.asc`) + `.prj` + FGDC `.xml` metadata
- Naming convention: `se<return_period>yr<duration_code><bound>[_ams].zip`
  - duration codes used by this project: `06h`, `12h`, `24h`, `04d` (=96h)
  - bound: `a` = estimate, `al` = lower 90% CI, `au` = upper 90% CI
  - (`_ams` is the annual-maximum-series alternative; this project uses the
    default partial-duration-series estimates, matching standard PFDS values)
- CRS: `EPSG:4269` (NAD83 geographic), confirmed from the `.prj` file
- Units: 1000ths of an inch; `NODATA_value = -9`
- All 72 files needed by this project (6 return periods x 4 durations x 3
  confidence bounds) were confirmed present in the official directory
  listing before any script was written.

**PFDS point query is not the only method, and GIS grids are the preferred
method for this project.** Two extraction methods were compared:

| Method | Description | Verdict |
|---|---|---|
| 1. HUC8-centroid PFDS point estimate | One point per HUC8 queried via the PFDS web interface | Simple, but a single point cannot represent rainfall variability across large HUC8 polygons |
| 2. GIS-grid-based full-HUC8 zonal statistics | Official Atlas 14 ASCII grids, zonal mean computed over each full HUC8 polygon | **Used in this project** - defensible at statewide HUC8 scale, uses the full polygon, and NOAA-official grids were confirmed accessible |

Method 2 was used because official grids were accessible. If NOAA grids ever
become unreachable, fall back to Method 1 and clearly relabel outputs
`extraction_method = "PFDS point estimate (centroid)"`.

## Scripts

1. **`inventory_atlas14_gis_sources.py`**
   Documents (does not download) every required grid source URL, naming
   convention, and format. Writes `data/metadata/atlas14_gis_inventory.csv`
   (73 rows: 72 grid combinations + 1 region metadata XML row).
   ```
   python scripts/inventory_atlas14_gis_sources.py
   python scripts/inventory_atlas14_gis_sources.py --verify-urls   # live HEAD check
   ```

2. **`download_or_register_atlas14_grids.py`**
   Downloads the official grid zips into `data/raw/atlas14/` and extracts
   them (unmodified content) into `data/raw/atlas14/extracted/`. Writes a
   manifest to `data/metadata/atlas14_grid_download_manifest.csv` and always
   (re)writes `data/metadata/atlas14_manual_download_instructions.md` as a
   fallback reference. On the run performed for this project, all 24
   estimate grids (6 return periods x 4 durations) plus the region metadata
   XML downloaded successfully (25/25, 0 failures, ~281 MB total).
   ```
   python scripts/download_or_register_atlas14_grids.py
   python scripts/download_or_register_atlas14_grids.py --include-ci   # also fetch 90% CI grids
   ```

3. **`extract_atlas14_huc8_depths.py`**
   Reads the HUC8 shapefile, reprojects it to the grid CRS (EPSG:4269), and
   computes a zonal statistic (mean, by default) over each full HUC8 polygon
   for every return_period x duration combination. Writes
   `data/processed/atlas14_depth_tables/alabama_intersecting_full_huc8_atlas14_depths.csv`.
   ```
   python scripts/extract_atlas14_huc8_depths.py
   python scripts/extract_atlas14_huc8_depths.py --statistic mean --include-ci
   ```
   **Expected row count: 1,416** (59 HUC8 x 6 return periods x 4 durations,
   estimate only). This script alone produced 1,392 `extracted` rows and 24
   `pending_atlas14_grid_download` rows (HUC8 06020004, Sequatchie). Those 24
   rows were subsequently filled by the supplement script below - see
   `alabama_intersecting_full_huc8_atlas14_depths.csv` for the current state
   (all 1,416 rows `extracted`).

4. **`update_scenarios_with_atlas14_depths.py`**
   Joins the depth table into the Task 1 scenario template on
   `(huc8_id, return_period_year, duration_hour)` and repeats the same
   `rainfall_depth` across all four `temporal_pattern` rows (rainfall depth
   does not vary by temporal pattern). Never overwrites the Task 1 template;
   writes a new file:
   `data/processed/storm_scenarios/atlas14_controlled_storm_scenarios_with_depths.csv`.
   ```
   python scripts/update_scenarios_with_atlas14_depths.py
   ```
   **Expected row count: 5,664** (59 HUC8 x 6 return periods x 4 durations x
   4 temporal patterns). This script alone produced 5,568
   `atlas14_depth_extracted` rows and 96 `pending_atlas14_depth` rows (HUC8
   06020004, Sequatchie). Those 96 rows were subsequently filled by the
   supplement script below - see
   `atlas14_controlled_storm_scenarios_with_depths.csv` for the current state
   (all 5,664 rows `atlas14_depth_extracted`).

5. **`supplement_sequatchie_volume2_atlas14.py`** (Task 2 supplement)
   Fills the 24 depth-table rows / 96 scenario-table rows for HUC8 06020004
   (Sequatchie) that were left pending because this HUC8 falls outside
   Volume 9 (Southeastern States) coverage. Investigated and confirmed NOAA
   Atlas 14 **Volume 2 (Ohio River Basin and Surrounding States)** grids are
   officially available at `https://hdsc.nws.noaa.gov/pub/hdsc/data/orb/`
   (same `<region><RP>yr<duration_code><bound>.zip` naming, prefix `orb`),
   with grid CRS `EPSG:4322` (WGS72 geographic) and `NODATA=-999` - both
   different from Volume 9. Downloads the 24 required Volume 2 estimate
   grids into `data/raw/atlas14_volume2/`, computes full-HUC8 zonal-mean
   depth **for HUC8 06020004 only**, and patches ONLY that HUC8's rows
   in-place in the two Task 2 output files (all other HUC8s/rows are left
   untouched). Writes a Volume-2-specific manifest to
   `data/metadata/atlas14_volume2_grid_download_manifest.csv`.
   ```
   python scripts/supplement_sequatchie_volume2_atlas14.py
   ```
   Before running this for the first time, timestamped backups of the two
   Task 2 output files were saved under `data/metadata/backups/`. Result:
   24/24 depth rows and 96/96 scenario rows patched; 0 remaining pending.

6. **`validate_task2_outputs.py`**
   Runs the full set of quality checks (row counts, duplicate scenario_id,
   depth consistency across temporal patterns, populated units/method/scope
   fields, no invented values, official source URLs). Exits non-zero if any
   check fails.
   ```
   python scripts/validate_task2_outputs.py
   ```

7. **`inventory_atlas14_temporal_distributions.py`** (Task 2D, additional
   reproducibility script not explicitly required as one of the 5 core
   scripts above, but included for consistency)
   Documents temporal distribution data availability only - no hyetograph
   generation, no HUC8 assignment. Writes
   `data/metadata/atlas14_temporal_distribution_inventory.csv`.
   ```
   python scripts/inventory_atlas14_temporal_distributions.py
   ```

## How to rerun the whole workflow later

```
python scripts/inventory_atlas14_gis_sources.py
python scripts/download_or_register_atlas14_grids.py
python scripts/extract_atlas14_huc8_depths.py
python scripts/update_scenarios_with_atlas14_depths.py
python scripts/supplement_sequatchie_volume2_atlas14.py
python scripts/inventory_atlas14_temporal_distributions.py
python scripts/validate_task2_outputs.py
```
`download_or_register_atlas14_grids.py` skips files already present in
`data/raw/atlas14/`, so rerunning the whole chain is cheap once grids are
downloaded. Likewise `supplement_sequatchie_volume2_atlas14.py` skips
Volume 2 grids already present in `data/raw/atlas14_volume2/`. Note that
`update_scenarios_with_atlas14_depths.py` regenerates the scenario table
from the depth table and the Task 1 template, so if you rerun it after the
Sequatchie supplement has already patched the depth table, its Volume 2
values will carry through correctly; if you rerun
`extract_atlas14_huc8_depths.py` afterward, it will reset HUC8 06020004
back to `pending_atlas14_grid_download` (Volume 9 still has no data there)
and you must rerun the supplement script again to refill it.

## Adapting to HUC12 or another state

All five core scripts expose command-line arguments so they are not hard-wired
to Alabama HUC8:

- `--huc-shapefile` / `--huc-id-field` / `--huc-name-field`: point at a HUC12
  shapefile or another state's HUC8/HUC12 layer (any field names).
- `--atlas14-grid-dir` / `--region-code` / `--atlas14-volume`: point at a
  different NOAA Atlas 14 volume's grid directory (e.g. `mw` for Volume 8,
  Midwestern States) if the new area falls outside Volume 9.
- `--return-periods` / `--durations` / `--statistic`: change the scenario
  dimensions or the zonal statistic (mean/median/min/max).
- `--geometry-scope` / `--selection-rule`: relabel the spatial-scope columns
  to match the new area's selection rule (e.g. `"intersects Georgia"`).

For HUC12, expect a much larger polygon count and correspondingly longer
zonal-statistics runtime (each `rasterio.mask.mask` call is per-polygon).

## Known limitations

- **HUC8 06020004 (Sequatchie)** lies primarily in the Tennessee River /
  Ohio River basin, outside Volume 9 (Southeastern States) grid coverage
  (all pixels `NODATA` there). This is **resolved**: the supplement script
  `supplement_sequatchie_volume2_atlas14.py` fills this HUC8's 24
  depth-table rows and 96 scenario-table rows using NOAA Atlas 14 **Volume
  2** (Ohio River Basin and Surrounding States) grids instead. All other 58
  HUC8s remain filled from Volume 9. If this HUC8 straddles the Volume 2/9
  boundary in a way that makes a single volume's estimate imprecise near the
  edge, that residual uncertainty is not further quantified here - the
  zonal mean is computed over the full HUC8 polygon against whichever
  volume's grid has valid data.
- **Temporal distribution comma-delimited tables** (per area, per duration)
  are served via a JavaScript form on the PFDS temporal page; no static
  per-file URL was found, so those specific files require a manual
  interactive download (documented in
  `data/metadata/atlas14_temporal_distribution_inventory.csv`). The temporal
  distribution AREA *boundaries* (shapefile) were downloaded successfully.
- Grid downloads default to the "estimate" (partial-duration-series) grids
  only; lower/upper 90% CI grids are available and can be pulled with
  `--include-ci`, but are not part of the default Task 2 run.

## GIS grid download status

**Direct programmatic download is available and was used**, for both
volumes. All 24 required Volume 9 grid files (plus the region metadata XML)
were downloaded successfully with zero failures, and all 24 required
Volume 2 grid files (plus its region metadata XML) were also downloaded
successfully with zero failures. Manual download instructions are still
documented in `data/metadata/atlas14_manual_download_instructions.md` as a
fallback for environments without network access.

## Volume attribution summary

| Coverage | HUC8 count | Atlas 14 volume | Region code | Grid CRS | NODATA |
|---|---|---|---|---|---|
| 58 of 59 HUC8s | 58 | Volume 9, Southeastern States | `se` | EPSG:4269 (NAD83) | -9 |
| 1 of 59 HUC8s (06020004, Sequatchie) | 1 | Volume 2, Ohio River Basin and Surrounding States | `orb` | EPSG:4322 (WGS72) | -999 |

Every row in the depth table and scenario table records which source file
(and therefore which volume) it came from via `atlas14_source_file` /
`rainfall_depth_source`, so this attribution is traceable per row, not just
asserted in this document.
