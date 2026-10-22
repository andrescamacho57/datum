-- 06_load_sunbiz_cor_quarterly.sql: load the quarterly FULL corporate snapshot into raw.
-- Run after 04 (stage exists) and after PUT uploaded cordata0-9 (done 2026-10-22, all UPLOADED).
-- Run from the VS Code terminal:  snow sql -c datum -f snowflake/06_load_sunbiz_cor_quarterly.sql
-- Expected: 12,987,601 rows (file size / 1442 bytes per line, exact for all 10 files).

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped warehouse (never COMPUTE_WH)

LIST @datum.raw.sunbiz_cor_quarterly_stage;                -- expect 10 files, cordata0.txt.gz ... cordata9.txt.gz

CREATE TABLE IF NOT EXISTS datum.raw.sunbiz_cor_quarterly (  -- a separate raw table for the snapshot
  line        VARCHAR,                                     -- the full record line, untouched
  source_file VARCHAR,                                     -- which staged file it came from (provenance)
  loaded_at   TIMESTAMP_NTZ                                -- when COPY loaded it (provenance)
);

COPY INTO datum.raw.sunbiz_cor_quarterly (line, source_file, loaded_at)  -- destination table and its 3 columns
FROM (
  SELECT $1,                                               -- field 1 = the whole line (the format never splits)
         METADATA$FILENAME,                                -- the staged file's name, e.g. cordata0.txt.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.sunbiz_cor_quarterly_stage               -- every file in the quarterly stage
);

-- CHECK 1: row count per file. Expected (file size / 1442):
--   cordata0 1,298,631 | cordata1 1,298,943 | cordata2 1,298,877 | cordata3 1,298,863 | cordata4 1,298,859
--   cordata5 1,298,693 | cordata6 1,298,685 | cordata7 1,298,711 | cordata8 1,298,685 | cordata9 1,298,654
SELECT source_file,                                        -- one output row per file
       COUNT(*) AS line_count                              -- how many lines that file produced
FROM datum.raw.sunbiz_cor_quarterly
GROUP BY source_file                                       -- group rows by file before counting
ORDER BY source_file;                                      -- cordata0 first

-- CHECK 2: total and line lengths. Expected 12,987,601 rows; lengths 1441 (1440 + the kept \r).
SELECT COUNT(*)          AS total_lines,                   -- all rows in the table
       MIN(LENGTH(line)) AS shortest,                      -- anything under 1436 = a damaged line
       MAX(LENGTH(line)) AS longest
FROM datum.raw.sunbiz_cor_quarterly;

-- CHECK 3: the open question. Does the "active data" snapshot include inactive companies?
SELECT SUBSTR(line, 205, 1) AS status_code,                -- character 205: A = active, I = inactive
       COUNT(*)             AS companies                   -- how many of each
FROM datum.raw.sunbiz_cor_quarterly
GROUP BY 1                                                 -- 1 = the first column in the SELECT list
ORDER BY 2 DESC;                                           -- 2 = the second column; biggest count first


-- Syntax: METADATA$FILENAME is a column Snowflake provides for every staged file, readable only inside a COPY or a SELECT on a stage. GROUP BY 1 / ORDER BY 2 refer to SELECT columns by position, a shorthand that saves retyping an expression.

-- Concept: COPY reads files in parallel (roughly one file per thread), so 10 equal-sized files load faster than one 18.7 GB file would. COPY also decompresses the .gz files as it reads them. Load metadata makes this script safe to rerun: files already loaded into THIS table are skipped.

-- Design decision: a separate raw table, not sunbiz_cor_daily. The snapshot and the daily deltas are different kinds of data (full register vs one day's new filings). Keeping them apart means each raw table stays an exact record of one source, and staging decides how to combine them. Status is counted with SUBSTR on raw because staging doesn't read this table yet.
