-- 18_fetch_manifest.sql: load the fetch manifest, one row per file Datum downloaded (ruling R23).

-- Why: CLAUDE.md rule 3 says every fact carries a source URL and a UTC fetch timestamp. The raw
-- tables record when Snowflake LOADED a file (loaded_at), which is not when we FETCHED it from the
-- source. The manifest records the fetch: file name, exact address, UTC time, size and checksum.
-- The three downloaders (src/datum/dbpr.py, duval.py, sunbiz_flr.py) write it as they download.
--
-- This script is safe to rerun, and it is meant to be run TWICE the first time (same pattern as
-- scripts 13–15):
--   1. Run it once to create the format, stage and table (the COPY finds no file).
--        snow sql -c datum -f snowflake/18_fetch_manifest.sql
--   2. From the VS Code terminal, add rows for files that were on disk before the manifest existed
--      (their fetch time is the file's modification time, marked is_approximate = true), then upload.
--      OVERWRITE=TRUE because the manifest keeps one name while it grows.
--        cd ~/datum
--        python src/datum/manifest.py backfill
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/fetch_manifest.csv @datum.raw.fetch_manifest_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
--   3. Run this script again to load, and read the CHECK at the bottom.
-- After every later download: repeat the PUT and run this script again.
--
-- The manifest is ONE file that grows. When it changes, COPY loads the whole file again, so the raw
-- table then holds the earlier rows twice. That is expected: raw is append-only, and the staging
-- view stg_datum__fetch_manifest keeps one row per file.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- File format, stage and raw table.
-- ---------------------------------------------------------------------------

CREATE FILE FORMAT IF NOT EXISTS datum.raw.manifest_csv    -- how to read the manifest: an ordinary CSV that we write ourselves
  TYPE = CSV                                               -- delimited text
  FIELD_DELIMITER = ','                                    -- a comma separates fields
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'                       -- Python's csv module quotes a field only when it contains a comma or a quote
  SKIP_HEADER = 1                                          -- line 1 holds the column names: skip it
  TRIM_SPACE = FALSE                                       -- keep every character as written
  ERROR_ON_COLUMN_COUNT_MISMATCH = TRUE                    -- a row without exactly 7 fields stops the load instead of shifting columns
  ENCODING = 'UTF8';                                       -- manifest.py writes UTF-8

CREATE STAGE IF NOT EXISTS datum.raw.fetch_manifest_stage  -- holding area for fetch_manifest.csv
  FILE_FORMAT = datum.raw.manifest_csv;                    -- read with the format above

LIST @datum.raw.fetch_manifest_stage;                      -- after PUT: expect fetch_manifest.csv.gz

CREATE TABLE IF NOT EXISTS datum.raw.fetch_manifest (      -- one row per line of the manifest: one fetched file
  source          VARCHAR,                                 -- field 1: which source the file belongs to: dbpr, duval or sunbiz_flr
  file_name       VARCHAR,                                 -- field 2: the fetched file's name on disk, e.g. d2026110501id.16
  source_url      VARCHAR,                                 -- field 3: the exact address it came from
  fetched_at_utc  VARCHAR,                                 -- field 4: when the download finished, UTC, as text: 2026-11-18T07:10:39Z
  size_bytes      VARCHAR,                                 -- field 5: the file's size as fetched
  sha256          VARCHAR,                                 -- field 6: checksum of the bytes as fetched
  is_approximate  VARCHAR,                                 -- field 7: 'true' when the fetch time is a file modification time, not a measured one
  source_file     VARCHAR,                                 -- which staged file THIS ROW came from (always fetch_manifest.csv.gz): raw's usual provenance column
  loaded_at       TIMESTAMP_NTZ                            -- when COPY loaded it (provenance)
);

-- ---------------------------------------------------------------------------
-- COPY: stage → raw table. Every field stays text; staging gives them types.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.fetch_manifest                         -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7,                       -- the manifest's 7 fields, in file order
         METADATA$FILENAME,                                -- fetch_manifest.csv.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.fetch_manifest_stage
);

-- ---------------------------------------------------------------------------
-- CHECK: per source, files in the manifest next to files in the raw tables.
-- A raw table's source_file is the staged name, which is the fetched file's name plus ".gz".
-- Expected: raw_files_without_manifest_row = 0 for every source.
-- manifest_files_not_in_raw may be above 0: a file that holds no rows (an empty daily events
-- file) loads nothing, so it has a manifest row and no rows in raw.
-- ---------------------------------------------------------------------------
WITH manifest AS (                                         -- one row per fetched file: duplicates from a reloaded manifest collapse here
  SELECT DISTINCT source,
         file_name || '.gz'                AS source_file, -- the name the raw tables know the file by
         is_approximate
  FROM datum.raw.fetch_manifest
),
raw_files AS (                                             -- every distinct file that has rows in a raw table, for the three sources
  SELECT 'dbpr' AS source, source_file FROM datum.raw.dbpr_licenses          GROUP BY 2
  UNION ALL SELECT 'dbpr',       source_file FROM datum.raw.dbpr_discipline     GROUP BY 2
  UNION ALL SELECT 'duval',      source_file FROM datum.raw.duval_documents     GROUP BY 2
  UNION ALL SELECT 'duval',      source_file FROM datum.raw.duval_parties       GROUP BY 2
  UNION ALL SELECT 'duval',      source_file FROM datum.raw.duval_links         GROUP BY 2
  UNION ALL SELECT 'duval',      source_file FROM datum.raw.duval_doc_types     GROUP BY 2
  UNION ALL SELECT 'sunbiz_flr', source_file FROM datum.raw.sunbiz_flr_filings  GROUP BY 2
  UNION ALL SELECT 'sunbiz_flr', source_file FROM datum.raw.sunbiz_flr_debtors  GROUP BY 2
  UNION ALL SELECT 'sunbiz_flr', source_file FROM datum.raw.sunbiz_flr_events   GROUP BY 2
  UNION ALL SELECT 'sunbiz_flr', source_file FROM datum.raw.sunbiz_flr_secured  GROUP BY 2
)
SELECT COALESCE(m.source, r.source)                                AS source,
       COUNT(m.source_file)                                        AS manifest_files,                  -- files the manifest knows
       COUNT_IF(m.is_approximate = 'true')                         AS approximate_fetch_time,          -- backfilled from a modification time
       COUNT(r.source_file)                                        AS distinct_source_files_in_raw,    -- files with rows in raw
       COUNT_IF(r.source_file IS NULL)                             AS manifest_files_not_in_raw,       -- fetched but holding no rows
       COUNT_IF(m.source_file IS NULL)                             AS raw_files_without_manifest_row   -- expected 0
FROM manifest AS m
FULL OUTER JOIN raw_files AS r                             -- FULL OUTER JOIN keeps a file that appears on either side only
  ON r.source = m.source AND r.source_file = m.source_file
GROUP BY 1                                                 -- one output row per source
ORDER BY 1;


-- Syntax: FULL OUTER JOIN keeps every row from BOTH sides; where one side has no partner, its columns come back NULL. That makes it the natural join for a reconciliation, where the question is "what is on one list and not the other". COUNT(column) counts the non-NULL values, so COUNT(m.source_file) and COUNT(r.source_file) count each side separately in one pass. GROUP BY 2 inside the small SELECTs groups by the second output column (source_file), which de-duplicates the file names.

-- Concept: provenance has two clocks. loaded_at is when a row entered the warehouse; the fetch time is when the file left the source. They can be minutes or weeks apart, and only the fetch time tells a reader how fresh a fact is. A manifest written by the downloader at the moment of download is the standard way to keep it, together with a checksum that proves later that the file on disk is still the file that was fetched.

-- Design decision: one manifest for all sources, one small raw table, and no changes to the existing raw tables: a fact reaches its fetch time by joining its source_file to the manifest. Adding a fetched_at column to eleven raw tables would have changed tables that are already loaded. The manifest is a single growing file loaded whole each time, so raw collects repeats and staging de-duplicates; the alternative, one manifest file per download run, would avoid repeats but leave dozens of tiny files to track. Rows backfilled for files downloaded before the manifest existed carry is_approximate = true, so an estimated fetch time can never pass for a measured one. A repaired Duval file has the manifest row of the file it was repaired from: the checksum there is of the file as the Clerk sent it, not of the repaired copy. The Sunbiz corporate files (scripts 03 and 06) were pulled by hand before any downloader existed and are not in the manifest yet.
