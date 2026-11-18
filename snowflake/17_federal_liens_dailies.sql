-- 17_federal_liens_dailies.sql: load every daily federal tax lien file published since the 2026-10-03 snapshot (ruling R8).

-- Why: the snapshot lists the liens that were active on 2026-10-03. Releases since then arrive only
-- in the daily EVENTS files, and new liens only in the daily FILINGS files. Script 13 loaded one day
-- of dailies (2026-11-04). "Is this lien still open?" needs all of them.
--
-- The stages and tables already exist (script 13). This script only loads into them and checks.
--
-- Before this script, from the VS Code terminal:
--   1. Download the dailies and inspect them (every line must be the documented length, or the file
--      is quarantined and never uploaded). Prints the same file-date table CHECK 1 prints below.
--        cd ~/datum
--        python src/datum/sunbiz_flr.py download
--   2. Upload them. One PUT per kind; the letter after "flr" picks the stage. A file already staged
--      is skipped.
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/sunbiz/flr/2026*flrf.txt @datum.raw.sunbiz_flr_filings_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/sunbiz/flr/2026*flrd.txt @datum.raw.sunbiz_flr_debtors_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/sunbiz/flr/2026*flre.txt @datum.raw.sunbiz_flr_events_stage  AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/sunbiz/flr/2026*flrs.txt @datum.raw.sunbiz_flr_secured_stage AUTO_COMPRESS=TRUE"
--   3. Run this script, and read the two CHECKs at the bottom:
--        snow sql -c datum -f snowflake/17_federal_liens_dailies.sql
--
-- Safe to rerun: COPY remembers which files it loaded into a table and skips them. Run it again
-- whenever step 1 brings new files.
--
-- Inspected before loading (2026-11-18): 24 daily files on 6 days, every line the documented
-- length. One file, 20261029flre.txt, is empty (no events that day): it loads zero rows, so it
-- never appears in the raw table.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- COPY: stage → raw table, the same four statements as script 13.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.sunbiz_flr_filings (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- field 1 = the whole line (the fixed_width format never splits)
         METADATA$FILENAME,                                -- the staged file's name, e.g. 20261116flrf.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_filings_stage                 -- every file in the filings stage not loaded before
);

COPY INTO datum.raw.sunbiz_flr_debtors (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- the whole line
         METADATA$FILENAME,                                -- e.g. 20261116flrd.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_debtors_stage                 -- every new file in the debtors stage
);

COPY INTO datum.raw.sunbiz_flr_events (line, source_file, loaded_at)   -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- the whole line
         METADATA$FILENAME,                                -- e.g. 20261116flre.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_events_stage                  -- every new file in the events stage
);

COPY INTO datum.raw.sunbiz_flr_secured (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- the whole line
         METADATA$FILENAME,                                -- e.g. 20261116flrs.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_flr_secured_stage                 -- every new file in the secured-party stage
);

-- ---------------------------------------------------------------------------
-- CHECK 1: rows loaded per file date, one column per kind, plus the line lengths.
-- Expected: the same table `python src/datum/sunbiz_flr.py inspect` prints, and
-- line lengths of exactly 82 (filings), 206 (debtors), 135 (events), 206 (secured).
-- The first row is the quarterly snapshot.
-- ---------------------------------------------------------------------------
WITH every_line AS (                                       -- all four raw tables stacked, each line labelled with its kind
  SELECT 'filings' AS kind, source_file, LENGTH(line) AS line_length FROM datum.raw.sunbiz_flr_filings
  UNION ALL
  SELECT 'debtors', source_file, LENGTH(line) FROM datum.raw.sunbiz_flr_debtors
  UNION ALL
  SELECT 'events',  source_file, LENGTH(line) FROM datum.raw.sunbiz_flr_events
  UNION ALL
  SELECT 'secured', source_file, LENGTH(line) FROM datum.raw.sunbiz_flr_secured
)
SELECT COALESCE(TO_CHAR(TRY_TO_DATE(LEFT(source_file, 8), 'YYYYMMDD')), 'snapshot') AS file_date,   -- dailies start with their date; the snapshot files don't
       COUNT_IF(kind = 'filings')                        AS filings,             -- rows of each kind for that date
       COUNT_IF(kind = 'debtors')                        AS debtors,
       COUNT_IF(kind = 'events')                         AS events,
       COUNT_IF(kind = 'secured')                        AS secured,
       COUNT(DISTINCT source_file)                       AS files_with_rows,     -- 4 on a normal day; 3 when one kind's file was empty
       COUNT_IF(   (kind = 'filings' AND line_length <> 82)                      -- lines that are NOT the documented length
                OR (kind IN ('debtors', 'secured') AND line_length <> 206)
                OR (kind = 'events'  AND line_length <> 135)) AS lines_wrong_length   -- expected 0 on every row
FROM every_line
GROUP BY 1                                                 -- GROUP BY 1 = group by the first output column
ORDER BY IFF(file_date = 'snapshot', '0', file_date);      -- the snapshot first, then the dailies oldest to newest

-- ---------------------------------------------------------------------------
-- CHECK 2: every COR (certificate of release) event in a daily file points at a lien we have:
-- in the snapshot, or in a daily filings file published before the event's own file.
-- A release of a lien we have never seen can mean a daily file is missing, so "missing" is read
-- every run. On 2026-11-18: 178 events, 171 found in the snapshot, 5 in an earlier daily, 2 missing.
-- The 2 are releases filed 2026-10-30 against liens from 2014 and 2018 (14FLR0013922, 18FLR0008457)
-- that are not in the snapshot at all: the snapshot holds ACTIVE liens only, so these had already
-- left it (lapsed or released before). They can't make a loaded lien look open, so they are
-- explained, not an error. A missing lien numbered 26FLR... WOULD point at a missing daily file.
-- ---------------------------------------------------------------------------
WITH daily_cor AS (                                        -- one row per COR event in the daily events files
  SELECT SUBSTR(line, 14, 12)                               AS filing_doc_number,   -- the lien the event acts on (events 14–25)
         TRY_TO_DATE(LEFT(source_file, 8), 'YYYYMMDD')      AS event_file_date      -- the day the state published the event
  FROM datum.raw.sunbiz_flr_events
  WHERE REGEXP_LIKE(source_file, '[0-9]{8}flr.*')          -- daily files only: the name starts with 8 digits
    AND SUBSTR(line, 60, 3) = 'COR'                        -- action code at 60–62: COR = release
),
filings AS (                                               -- one row per lien: where we first saw it
  SELECT SUBSTR(line, 1, 12)                                AS filing_doc_number,   -- the lien's number (filings 1–12)
         MAX(IFF(source_file = 'FLRF.TXT.gz', 1, 0))        AS in_snapshot,         -- 1 when the lien is in the quarterly snapshot
         MIN(TRY_TO_DATE(LEFT(source_file, 8), 'YYYYMMDD')) AS first_daily_date     -- the earliest daily file holding it, NULL if none
  FROM datum.raw.sunbiz_flr_filings
  GROUP BY 1
)
SELECT COUNT(*)                                                                    AS daily_cor_events,
       COUNT_IF(f.in_snapshot = 1)                                                 AS found_in_snapshot,
       COUNT_IF(f.in_snapshot = 0 AND f.first_daily_date <  c.event_file_date)     AS found_in_earlier_daily,
       COUNT_IF(f.in_snapshot = 0 AND f.first_daily_date >= c.event_file_date)     AS found_only_in_same_or_later_daily,   -- would be odd: released before it was filed
       COUNT_IF(f.filing_doc_number IS NULL)                                       AS missing,                             -- 2 on 2026-11-18, explained above
       COUNT_IF(f.filing_doc_number IS NULL AND LEFT(c.filing_doc_number, 2) = '26') AS missing_filed_this_year            -- expected 0: a 2026 lien we never saw = a missing file
FROM daily_cor AS c
LEFT JOIN filings AS f USING (filing_doc_number);          -- LEFT JOIN keeps every event, matched or not


-- Syntax: COUNT_IF(condition) counts the rows where the condition is true, so one pass over the stacked lines fills four columns: a "pivot" done by hand. GROUP BY 1 and ORDER BY 1 refer to output columns by position. TRY_TO_DATE returns NULL instead of failing when the text isn't a date, which is how the snapshot files (FLRF.TXT.gz, no date in the name) fall out as 'snapshot' through COALESCE.

-- Concept: snapshot plus deltas. A snapshot is the full state at one moment; a delta (here a daily file) is what changed after it. The current state is the snapshot with every later delta applied in order. Miss one delta and the state is silently wrong, which is why CHECK 2 asks whether any release points at a lien we have never seen: it is a cheap test for a missing file.

-- Design decision: the dailies go into the same four raw tables as the snapshot (script 13's choice), told apart by source_file, so staging and everything after it read one table per kind. The COPY statements are repeated here instead of rerunning script 13, because script 13's checks expect exactly its 8 files; this script has its own two checks, which stay true as more days arrive. The state only publishes a daily file when there was activity, and one events file was empty: the row counts are checked against the local inspection, not against a calendar. The tradeoff of loading by "whatever is new in the stage": a file re-published under the same name with different content would load a second time, so CHECK 1 should be read after every run.
