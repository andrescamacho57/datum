-- 13_federal_liens_raw.sql: raw landing area for the Sunbiz federal tax lien (FLR) files.

-- Four file kinds (filings, debtors, events, secured parties), so four stages and four raw tables.
-- Each table holds BOTH the quarterly snapshot (FLRF.TXT ...) and the daily files (20261104flrf.txt ...).
-- Layouts and verified counts: docs/access/sunbiz_flr.md.
--
-- This script is safe to rerun, and it is meant to be run TWICE:
--   1. Run it once to create the stages and tables (the COPYs find no files and load nothing).
--        snow sql -c datum -f snowflake/13_federal_liens_raw.sql
--   2. Upload the 8 files from the VS Code terminal (PUT only runs from a client on your machine).
--      Globs are case-sensitive: the quarterly files are UPPER case, the dailies lower case.
--        cd ~/datum/data/raw/sunbiz/flr
--        snow sql -c datum -q "PUT file://$PWD/FLRF.TXT          @datum.raw.sunbiz_flr_filings_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/20261104flrf.txt  @datum.raw.sunbiz_flr_filings_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/FLRD.TXT          @datum.raw.sunbiz_flr_debtors_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/20261104flrd.txt  @datum.raw.sunbiz_flr_debtors_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/FLRE.TXT          @datum.raw.sunbiz_flr_events_stage  AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/20261104flre.txt  @datum.raw.sunbiz_flr_events_stage  AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/FLRS.TXT          @datum.raw.sunbiz_flr_secured_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/20261104flrs.txt  @datum.raw.sunbiz_flr_secured_stage AUTO_COMPRESS=TRUE"
--   3. Run this script again: now the COPYs load the files and the checks at the bottom mean something.
--
-- Inspected before loading (2026-11-12, `awk` line lengths + `wc -l`): every line in every file is
-- exactly the documented length. Expected rows are in the CHECK comments below.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- Stages: one per file kind. Each reuses the fixed_width format from script 02.
-- ---------------------------------------------------------------------------

CREATE STAGE IF NOT EXISTS datum.raw.sunbiz_flr_filings_stage  -- holding area for filings files (FLRF.TXT + yyyymmddflrf.txt)
  FILE_FORMAT = datum.raw.fixed_width;                     -- one field per line, Latin-1, never split

CREATE STAGE IF NOT EXISTS datum.raw.sunbiz_flr_debtors_stage  -- holding area for debtor files (FLRD.TXT + yyyymmddflrd.txt)
  FILE_FORMAT = datum.raw.fixed_width;                     -- same format: the layout differs, the reading rule doesn't

CREATE STAGE IF NOT EXISTS datum.raw.sunbiz_flr_events_stage   -- holding area for event files (FLRE.TXT + yyyymmddflre.txt)
  FILE_FORMAT = datum.raw.fixed_width;                     -- same format

CREATE STAGE IF NOT EXISTS datum.raw.sunbiz_flr_secured_stage  -- holding area for secured-party files (FLRS.TXT + yyyymmddflrs.txt)
  FILE_FORMAT = datum.raw.fixed_width;                     -- same format

LIST @datum.raw.sunbiz_flr_filings_stage;                  -- after PUT: expect FLRF.TXT.gz and 20261104flrf.txt.gz
LIST @datum.raw.sunbiz_flr_debtors_stage;                  -- after PUT: expect FLRD.TXT.gz and 20261104flrd.txt.gz
LIST @datum.raw.sunbiz_flr_events_stage;                   -- after PUT: expect FLRE.TXT.gz and 20261104flre.txt.gz
LIST @datum.raw.sunbiz_flr_secured_stage;                  -- after PUT: expect FLRS.TXT.gz and 20261104flrs.txt.gz

-- ---------------------------------------------------------------------------
-- Raw tables: one per file kind, the same three columns as every raw table.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS datum.raw.sunbiz_flr_filings (  -- one row per line of a filings file: one lien
  line        VARCHAR,                                     -- the full 82-character line, untouched
  source_file VARCHAR,                                     -- which staged file it came from (provenance)
  loaded_at   TIMESTAMP_NTZ                                -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.sunbiz_flr_debtors (  -- one row per line of a debtors file: one debtor on one lien
  line        VARCHAR,                                     -- the full 206-character line, untouched
  source_file VARCHAR,                                     -- which staged file it came from (provenance)
  loaded_at   TIMESTAMP_NTZ                                -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.sunbiz_flr_events (   -- one row per line of an events file: one action on a lien
  line        VARCHAR,                                     -- the full 135-character line, untouched
  source_file VARCHAR,                                     -- which staged file it came from (provenance)
  loaded_at   TIMESTAMP_NTZ                                -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.sunbiz_flr_secured (  -- one row per line of a secured-party file: one creditor on one lien
  line        VARCHAR,                                     -- the full 206-character line, untouched
  source_file VARCHAR,                                     -- which staged file it came from (provenance)
  loaded_at   TIMESTAMP_NTZ                                -- when COPY loaded it (provenance)
);

-- ---------------------------------------------------------------------------
-- COPY: stage → raw table. Files already loaded into a table are skipped on a rerun.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.sunbiz_flr_filings (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- field 1 = the whole line (the format never splits)
         METADATA$FILENAME,                                -- the staged file's name, e.g. FLRF.TXT.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_filings_stage                 -- every file in the filings stage
);

COPY INTO datum.raw.sunbiz_flr_debtors (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- the whole line
         METADATA$FILENAME,                                -- e.g. FLRD.TXT.gz or 20261104flrd.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_debtors_stage                 -- every file in the debtors stage
);

COPY INTO datum.raw.sunbiz_flr_events (line, source_file, loaded_at)   -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- the whole line
         METADATA$FILENAME,                                -- e.g. FLRE.TXT.gz or 20261104flre.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_events_stage                  -- every file in the events stage
);

COPY INTO datum.raw.sunbiz_flr_secured (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- the whole line
         METADATA$FILENAME,                                -- e.g. FLRS.TXT.gz or 20261104flrs.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_secured_stage                 -- every file in the secured-party stage
);

-- ---------------------------------------------------------------------------
-- CHECK 1: rows and line lengths per file, all four tables in one result.
-- Expected (local `wc -l` and docs/access/sunbiz_flr.md):
--   filings  FLRF.TXT.gz 20,444 | 20261104flrf.txt.gz 42 | length 82
--   debtors  FLRD.TXT.gz 22,173 | 20261104flrd.txt.gz 46 | length 206
--   events   FLRE.TXT.gz 97,256 | 20261104flre.txt.gz 29 | length 135
--   secured  FLRS.TXT.gz 20,448 | 20261104flrs.txt.gz 42 | length 206
-- ---------------------------------------------------------------------------
SELECT 'filings' AS raw_table,                             -- a label so the four results can share one output
       source_file,                                        -- one output row per file
       COUNT(*)          AS line_count,                    -- how many lines that file produced
       MIN(LENGTH(line)) AS shortest,                      -- shortest = longest = the layout length means no damaged line
       MAX(LENGTH(line)) AS longest
FROM datum.raw.sunbiz_flr_filings
GROUP BY source_file                                       -- group rows by file before counting
UNION ALL                                                  -- stack the next table's result underneath
SELECT 'debtors', source_file, COUNT(*), MIN(LENGTH(line)), MAX(LENGTH(line))  -- same five columns, debtors
FROM datum.raw.sunbiz_flr_debtors
GROUP BY source_file
UNION ALL
SELECT 'events', source_file, COUNT(*), MIN(LENGTH(line)), MAX(LENGTH(line))   -- same five columns, events
FROM datum.raw.sunbiz_flr_events
GROUP BY source_file
UNION ALL
SELECT 'secured', source_file, COUNT(*), MIN(LENGTH(line)), MAX(LENGTH(line))  -- same five columns, secured parties
FROM datum.raw.sunbiz_flr_secured
GROUP BY source_file
ORDER BY 1, 2;                                             -- by table label, then file name

-- ---------------------------------------------------------------------------
-- CHECK 2: every COR (certificate of release) event in the daily file points at a lien
-- in the quarterly snapshot. Expected: 29 daily COR events, 29 found in the snapshot.
-- ---------------------------------------------------------------------------
SELECT COUNT(*)                       AS daily_cor_events,       -- COR events in the daily events file
       COUNT(f.line)                  AS found_in_snapshot,      -- COUNT(column) skips NULLs: only events that found a lien
       COUNT(*) - COUNT(f.line)       AS missing_from_snapshot   -- expected 0
FROM datum.raw.sunbiz_flr_events AS e                            -- e = the events side
LEFT JOIN datum.raw.sunbiz_flr_filings AS f                      -- LEFT JOIN keeps every event, matched or not
  ON  SUBSTR(f.line, 1, 12) = SUBSTR(e.line, 14, 12)             -- filing doc number: filings 1–12, events 14–25
  AND f.source_file = 'FLRF.TXT.gz'                              -- only the quarterly snapshot counts as "found"
WHERE e.source_file = '20261104flre.txt.gz'                      -- only the daily events file
  AND SUBSTR(e.line, 60, 3) = 'COR';                             -- action code at 60–62: COR = release


-- Syntax: UNION ALL stacks SELECTs that have the same number of columns; column names come from the first SELECT. COUNT(*) counts rows, while COUNT(column) counts only rows where that column is not NULL, which is how one query reports both "events" and "events that matched" after a LEFT JOIN. A join condition can carry a filter on the right-hand table (AND f.source_file = ...); putting that filter in WHERE instead would turn the LEFT JOIN into an inner join and hide the misses.

-- Concept: one-to-many files. A lien (filings) has one or more debtors, one or more secured parties, and zero or more events, each in its own file, all sharing the lien's document number. The state ships them as four files because they are four different shapes. COPY keeps load metadata per TABLE for 64 days, so rerunning this script skips files it already loaded instead of doubling them.

-- Design decision: one stage and one raw table per file kind (decision d9), with quarterly and daily rows together and told apart by source_file. That differs from the corporate files (scripts 03 and 06), where daily and quarterly got separate tables: there the snapshot was 13M rows against a few hundred daily rows; here a kind's snapshot and its dailies are the same layout, small, and always read together, so four tables instead of eight is simpler with nothing lost. Staging derives source_kind and published_on from the file name. The tradeoff: if the state ever re-ships a file under the same name, COPY will skip it; the fix then is a date folder in the stage path. The CHECKs use SUBSTR on raw so this script proves the load on its own, before any dbt model exists.
