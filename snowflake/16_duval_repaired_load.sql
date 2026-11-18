-- 16_duval_repaired_load.sql: load the REPAIRED copies of the 13 Duval files that failed verification (ruling R15).

-- Background: 13 of the Clerk's daily files had more lines than their EOF trailer said, so script 15
-- never loaded them. The cause: a line break inside a legal description spreads one record over two
-- or three lines (12 documents files), and one links file holds a blank line. The repair joins those
-- lines back together in a COPY and keeps the copy only if its row count equals the Clerk's own count.
-- The files as sent stay in data/raw/duval/rejected/. Details: docs/access/duval-recording-index.md.
--
-- Before this script, from the VS Code terminal:
--   1. Make the repaired copies (prints one OK line per file; a file that still mismatches stays out):
--        cd ~/datum
--        python src/datum/duval.py repair
--   2. Upload them to the SAME stages script 15 uses. The copies keep the original file names, so
--      staging still reads each file's date from its name.
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/duval/repaired/d*.16 @datum.raw.duval_documents_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/duval/repaired/l*.16 @datum.raw.duval_links_stage     AUTO_COMPRESS=TRUE"
--   3. Run this script, and read the three CHECKs at the bottom:
--        snow sql -c datum -f snowflake/16_duval_repaired_load.sql
--
-- New daily files (days after 2026-11-11) are NOT this script's job: download them with
-- `python src/datum/duval.py download`, PUT them as script 15's header shows, and rerun script 15.
--
-- Safe to rerun: COPY remembers which files it loaded into a table and skips them.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- COPY: the same statements as script 15, limited to the repaired files by name.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.duval_documents                        -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7,                       -- fields 1–7
         $8, $9, $10, $11, $12, $13, $14,                  -- fields 8–14
         METADATA$FILENAME,                                -- the staged file's name, e.g. d2025090201id.16.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.duval_documents_stage                    -- the stage script 15 created
)
FILES = (                                                  -- load ONLY these 12 files: the repaired documents files
  'd2025090201id.16.gz', 'd2025090301id.16.gz', 'd2026010901id.16.gz', 'd2026011501id.16.gz',
  'd2026021901id.16.gz', 'd2026022501id.16.gz', 'd2026031401id.16.gz', 'd2026040801id.16.gz',
  'd2026061101id.16.gz', 'd2026072801id.16.gz', 'd2026081201id.16.gz', 'd2026101601id.16.gz'
);

COPY INTO datum.raw.duval_links                            -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,          -- fields 1–10
         METADATA$FILENAME,                                -- l2026021901id.16.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.duval_links_stage                        -- the stage script 15 created
)
FILES = ('l2026021901id.16.gz');                           -- the one repaired links file

-- ---------------------------------------------------------------------------
-- CHECK 1: each repaired file, rows loaded against the Clerk's own EOF count.
-- Expected: 13 rows, matches = TRUE on every one, and the rows column equal to what
-- `python src/datum/duval.py repair` printed (documents total 18,386; links 2,563).
-- ---------------------------------------------------------------------------
WITH repaired AS (                                         -- the 13 file names, as a small inline table
  SELECT column1 AS source_file                            -- VALUES names its columns column1, column2 ...
  FROM VALUES
    ('d2025090201id.16.gz'), ('d2025090301id.16.gz'), ('d2026010901id.16.gz'), ('d2026011501id.16.gz'),
    ('d2026021901id.16.gz'), ('d2026022501id.16.gz'), ('d2026031401id.16.gz'), ('d2026040801id.16.gz'),
    ('d2026061101id.16.gz'), ('d2026072801id.16.gz'), ('d2026081201id.16.gz'), ('d2026101601id.16.gz'),
    ('l2026021901id.16.gz')
),
per_file AS (                                              -- rows and trailer count for every documents and links file
  SELECT source_file,
         COUNT_IF(record_type <> 'EOF')                                  AS data_rows,   -- rows that are not the trailer
         MAX(IFF(record_type = 'EOF', TRY_TO_NUMBER(county_code), NULL)) AS eof_count    -- the Clerk's count, from the trailer row
  FROM datum.raw.duval_documents
  GROUP BY source_file
  UNION ALL
  SELECT source_file,
         COUNT_IF(instrument_number <> 'EOF'),                           -- links files: the trailer shows up in field 1
         MAX(IFF(instrument_number = 'EOF', TRY_TO_NUMBER(book), NULL))
  FROM datum.raw.duval_links
  GROUP BY source_file
)
SELECT r.source_file,                                      -- one output row per repaired file
       p.data_rows,                                        -- NULL here would mean the file was not loaded at all
       p.eof_count,
       COALESCE(p.data_rows = p.eof_count, FALSE) AS matches   -- COALESCE turns "not loaded" (NULL) into FALSE
FROM repaired AS r
LEFT JOIN per_file AS p USING (source_file)                -- LEFT JOIN keeps a repaired file even if it has no rows
ORDER BY r.source_file;

-- ---------------------------------------------------------------------------
-- CHECK 2: every loaded file of every kind, data rows = its EOF trailer (script 15's check, rerun).
-- Expected: the same number of files in all four tables, files_mismatched = 0, files_without_one_trailer = 0.
-- ---------------------------------------------------------------------------
WITH per_file AS (                                         -- step 1: one row per file, for all four tables
  SELECT 'documents' AS raw_table, source_file,
         COUNT_IF(record_type <> 'EOF')                                  AS data_rows,
         COUNT_IF(record_type = 'EOF')                                   AS trailer_rows,   -- must be exactly 1
         MAX(IFF(record_type = 'EOF', TRY_TO_NUMBER(county_code), NULL)) AS eof_count
  FROM datum.raw.duval_documents
  GROUP BY source_file
  UNION ALL
  SELECT 'parties', source_file,
         COUNT_IF(record_type <> 'EOF'), COUNT_IF(record_type = 'EOF'),
         MAX(IFF(record_type = 'EOF', TRY_TO_NUMBER(county_code), NULL))
  FROM datum.raw.duval_parties
  GROUP BY source_file
  UNION ALL
  SELECT 'links', source_file,
         COUNT_IF(instrument_number <> 'EOF'), COUNT_IF(instrument_number = 'EOF'),
         MAX(IFF(instrument_number = 'EOF', TRY_TO_NUMBER(book), NULL))
  FROM datum.raw.duval_links
  GROUP BY source_file
  UNION ALL
  SELECT 'doc_types', source_file,
         COUNT_IF(doc_type_code <> 'EOF'), COUNT_IF(doc_type_code = 'EOF'),
         MAX(IFF(doc_type_code = 'EOF', TRY_TO_NUMBER(doc_type_family), NULL))
  FROM datum.raw.duval_doc_types
  GROUP BY source_file
)
SELECT raw_table,                                          -- step 2: roll the files up to one row per table
       COUNT(*)                                              AS files_loaded,
       SUM(data_rows)                                        AS data_rows,
       SUM(eof_count)                                        AS sum_of_eof_counts,
       COUNT_IF(data_rows <> eof_count OR eof_count IS NULL) AS files_mismatched,          -- expected 0
       COUNT_IF(trailer_rows <> 1)                           AS files_without_one_trailer, -- expected 0
       MIN(SUBSTR(source_file, 2, 8))                        AS first_file_date,           -- characters 2–9 of the name are the date
       MAX(SUBSTR(source_file, 2, 8))                        AS last_file_date
FROM per_file
GROUP BY raw_table
ORDER BY raw_table;

-- ---------------------------------------------------------------------------
-- CHECK 3: orphans. A party row or a link row whose document is not loaded.
-- Before the repair: 45,173 party rows and 14,464 link rows, all from the 12 rejected days.
-- Expected now: 0 and 0.
-- ---------------------------------------------------------------------------
WITH documents AS (                                        -- every instrument number that has a document row
  SELECT DISTINCT TRIM(instrument_number) AS instrument_number
  FROM datum.raw.duval_documents
  WHERE record_type <> 'EOF'                               -- not the trailer rows
)
SELECT 'parties' AS raw_table,
       COUNT(*)                            AS data_rows,   -- every party row
       COUNT_IF(d.instrument_number IS NULL) AS orphan_rows  -- party rows with no document: expected 0
FROM datum.raw.duval_parties AS p
LEFT JOIN documents AS d ON d.instrument_number = TRIM(p.instrument_number)   -- keep every party row, matched or not
WHERE p.record_type <> 'EOF'
UNION ALL
SELECT 'links',
       COUNT(*),
       COUNT_IF(d.instrument_number IS NULL)               -- link rows with no document: expected 0
FROM datum.raw.duval_links AS l
LEFT JOIN documents AS d ON d.instrument_number = TRIM(l.instrument_number)
WHERE l.instrument_number <> 'EOF';


-- Syntax: FILES = ('a', 'b') on a COPY names the staged files to load and ignores everything else in the stage. FROM VALUES ('x'), ('y') builds a small table inline, with columns named column1, column2 and so on. USING (source_file) is shorthand for ON a.source_file = b.source_file when both sides call the join column the same. COALESCE(a, b) returns the first value that is not NULL.

-- Concept: repair in a copy, verify against the source's own count. The Clerk's trailer says how many records each file holds, so a repair can be proved: after joining the broken lines, the row count must equal the trailer exactly. If it does not, the copy is thrown away and the file stays out. The file as sent is never edited; it stays in rejected/ as evidence, and the repair can be redone from it at any time.

-- Design decision: the repaired copies go into the same stages and tables as every other file, under their original names, and nothing in raw marks them as repaired. That keeps staging unchanged (it reads the file date from the name) and keeps one table per file kind. The record of which files were repaired, and how, lives in docs/access/duval-recording-index.md and in the repair's own output. The tradeoff: looking at raw alone, a repaired row can't be told from an untouched one, and its legal description carries one extra space where the line break was (staging trims it at the end of the field). FILES = (...) is used instead of loading "whatever is in the stage" so this script does exactly one thing: script 15 stays the script for new daily files.
