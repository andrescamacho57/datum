-- 21_fetch_manifest_sunbiz_cor.sql: load the fetch-manifest rows for the state's CORPORATE files (Phase C, leg C1).

-- Why: the fetch manifest (script 18, ruling R23) covered three sources and left out the Sunbiz corporate
-- files, which are the company register itself. So no company's status, date on record or address had a
-- fetch time, and CLAUDE.md rule 3 says every fact carries a source URL and a UTC fetch timestamp.
-- src/datum/sunbiz_cor.py now writes one manifest row for each corporate file still on disk: the daily
-- file 20261009c.txt and the ten files inside the quarterly snapshot cordata.zip. Every one of those
-- rows is marked is_approximate = true, because its time is a file's modification time, not a measured fetch.
--
-- This script creates nothing. The format, the stage and the table are the ones script 18 made, and
-- scripts 01 to 20 are left as they are. It only loads the manifest again and checks the new source.
--
-- How to run it, from the VS Code terminal:
--   1. Add the rows to the manifest on disk (it skips any file that already has a row):
--        cd ~/datum
--        source .venv/bin/activate
--        python src/datum/manifest.py backfill
--   2. Upload the manifest. OVERWRITE=TRUE because the manifest keeps one name while it grows.
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/fetch_manifest.csv @datum.raw.fetch_manifest_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
--   3. Run this script and read the two CHECKs at the bottom.
--        snow sql -c datum -f snowflake/21_fetch_manifest_sunbiz_cor.sql
-- Safe to rerun: when the staged manifest has not changed, COPY loads nothing the second time.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

LIST @datum.raw.fetch_manifest_stage;                      -- after the PUT: expect one file, fetch_manifest.csv.gz

-- ---------------------------------------------------------------------------
-- COPY: stage → raw table. The same statement as script 18. The manifest is one growing file, so the
-- whole file loads again and raw then holds the earlier rows twice. That is expected: raw is
-- append-only, and the staging view stg_datum__fetch_manifest keeps one row per file.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.fetch_manifest                         -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7,                       -- the manifest's 7 fields, in file order
         METADATA$FILENAME,                                -- fetch_manifest.csv.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.fetch_manifest_stage
);

-- ---------------------------------------------------------------------------
-- CHECK 1: every corporate file with rows in raw has a manifest row, and the reverse.
-- Expected: 11 rows, in_manifest and in_raw both TRUE on every row, is_approximate 'true' on every row.
-- The two raw tables name their files differently: the quarterly files were compressed by PUT and end
-- in .gz (cordata0.txt.gz), and the daily file was loaded as it was (20261009c.txt). So the join
-- compares the names with any trailing .gz taken off.
-- ---------------------------------------------------------------------------
WITH manifest AS (                                         -- one row per corporate file in the manifest; repeats from a reloaded manifest collapse here
  SELECT DISTINCT file_name,                               -- the file's name as it was on disk, e.g. cordata0.txt
         fetched_at_utc,                                   -- the fetch time, still text in raw
         is_approximate                                    -- 'true' on every corporate row
  FROM datum.raw.fetch_manifest
  WHERE source = 'sunbiz_cor'                              -- only the new source
),
raw_files AS (                                             -- every distinct corporate file that has rows in raw, with its row count
  SELECT REGEXP_REPLACE(source_file, '\\.gz$', '') AS file_name,   -- the name without a trailing .gz. \\. is a literal dot and $ is the end of the text
         'sunbiz_cor_quarterly'                    AS raw_table,   -- which raw table the file is in
         COUNT(*)                                  AS rows_in_raw  -- how many lines of that file were loaded
  FROM datum.raw.sunbiz_cor_quarterly
  GROUP BY 1                                               -- one output row per file
  UNION ALL
  SELECT REGEXP_REPLACE(source_file, '\\.gz$', ''), 'sunbiz_cor_daily', COUNT(*)
  FROM datum.raw.sunbiz_cor_daily
  GROUP BY 1
)
SELECT COALESCE(m.file_name, r.file_name)  AS file_name,   -- the file, whichever side knows it
       r.raw_table,                                        -- NULL when the manifest names a file that has no rows in raw
       r.rows_in_raw,
       m.file_name IS NOT NULL             AS in_manifest, -- expected TRUE
       r.file_name IS NOT NULL             AS in_raw,      -- expected TRUE
       m.fetched_at_utc,                                   -- the estimated fetch time, UTC
       m.is_approximate                                    -- expected 'true'
FROM manifest AS m
FULL OUTER JOIN raw_files AS r                             -- keeps a file that appears on either side only
  ON r.file_name = m.file_name
ORDER BY 1;

-- ---------------------------------------------------------------------------
-- CHECK 2: each file was fetched before it was loaded. A fetch time later than the load time would
-- mean the modification time is not a download time after all.
-- Expected: fetched_before_loaded TRUE on all 11 rows.
-- loaded_at was written by CURRENT_TIMESTAMP() into a column with no time zone, so it holds the
-- session's local clock time. CONVERT_TIMEZONE turns it into UTC before the comparison.
-- ---------------------------------------------------------------------------
WITH manifest AS (                                         -- the same eleven manifest rows as CHECK 1, with the time as a real timestamp
  SELECT DISTINCT file_name,
         TO_TIMESTAMP_NTZ(fetched_at_utc, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS fetched_at_utc   -- the T and the Z are literal characters, so they sit in double quotes
  FROM datum.raw.fetch_manifest
  WHERE source = 'sunbiz_cor'
),
loads AS (                                                 -- when each corporate file was first loaded
  SELECT REGEXP_REPLACE(source_file, '\\.gz$', '') AS file_name,
         MIN(loaded_at)                            AS loaded_at    -- the earliest load of that file
  FROM datum.raw.sunbiz_cor_quarterly
  GROUP BY 1
  UNION ALL
  SELECT REGEXP_REPLACE(source_file, '\\.gz$', ''), MIN(loaded_at)
  FROM datum.raw.sunbiz_cor_daily
  GROUP BY 1
)
SELECT m.file_name,
       m.fetched_at_utc,                                                           -- estimated fetch time, UTC
       CONVERT_TIMEZONE('America/Los_Angeles', 'UTC', l.loaded_at) AS loaded_at_utc,   -- three arguments: from this zone, to that zone, this timestamp
       m.fetched_at_utc < CONVERT_TIMEZONE('America/Los_Angeles', 'UTC', l.loaded_at) AS fetched_before_loaded   -- expected TRUE
FROM manifest AS m
INNER JOIN loads AS l                                      -- only files on both sides; CHECK 1 already reports the others
  ON l.file_name = m.file_name
ORDER BY 1;


-- Syntax: REGEXP_REPLACE(text, pattern, replacement) swaps every match of the pattern for the replacement. In '\\.gz$' the two backslashes reach the pattern as one, which makes the dot a literal dot (a bare dot means "any character"), and $ pins the match to the end of the text, so only a trailing .gz is removed. CONVERT_TIMEZONE with three arguments reads a timestamp that has no zone as a clock time in the first zone and returns the same moment as a clock time in the second. FULL OUTER JOIN keeps every row from both sides, which is the natural join for comparing two lists.

-- Concept: backfilling provenance. Provenance is the record of where a piece of data came from and when. When a file was fetched before the bookkeeping existed, the honest repair is to write down the best evidence that survives (here the file's modification time) and to mark it as an estimate, so that a reader can always tell a measured time from a reconstructed one. The report will say "fetched about Oct 22, 2026" for these rows, not "fetched Oct 22, 2026".

-- Design decision: no new table, stage or format. The manifest already had a source column, so a fourth source is eleven more rows in the same file, loaded by the same COPY, and the staging view picks them up without changing. The alternative was a separate table for the corporate files, which would have meant a second place to look for a fetch time and a second join in every mart. The cost of reusing the manifest is that its staging model builds the join key by adding .gz to the file name, which is right for the ten quarterly files and wrong for the one daily file that was loaded uncompressed. The company_search mart therefore joins on the file name with any trailing .gz removed, and CHECK 1 above does the same. The session time zone in CHECK 2 is written out as America/Los_Angeles because that is this account's default, and every loaded_at in raw was written under it.
