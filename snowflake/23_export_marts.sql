-- 23_export_marts.sql: copy the four marts the web app reads out of Snowflake, as compressed CSV files (Phase C, leg C2).

-- Why: decision d18. Lookups read Postgres and builds run in Snowflake. A lookup against a suspended
-- warehouse costs about $0.03 and takes seconds to wake, and a lookup against a small Postgres table
-- costs nothing and takes milliseconds. So the finished tables are copied out of the warehouse and into
-- the database next to the app. Copying finished data out of a warehouse is called an unload, and
-- sending it to an operational database is called reverse ETL (extract, transform, load).
--
-- What leaves Snowflake, and what does not (Phase C working rule W9):
--   company_search             every row: one per company
--   company_flags              ONLY rows with is_shown = TRUE. Duval flags and DBPR discipline stay behind
--   company_possible_matches   ONLY rows with is_shown = TRUE. Every row is hidden today, so none leaves
--   source_coverage            every row: five rows that describe sources, not records
--   export_counts              one small file: the row count of each of the four, as exported
-- The app cannot show, leak or miscount a row it does not have.
--
-- How to run it, from the VS Code terminal:
--   1. Unload to the stage:
--        cd ~/datum
--        snow sql -c datum -f snowflake/23_export_marts.sql
--   2. Download the files. The folder data/ is ignored by git, so nothing here can be committed.
--        rm -rf data/export && mkdir -p data/export
--        snow stage copy @datum.dev_marts.export_stage data/export --recursive -c datum
--   3. Load them into Postgres:
--        python -m datum.load_postgres
-- Safe to rerun: each run first removes the files of the run before it from the stage.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- File format and stage. Both are new, and nothing existing is changed.
-- ---------------------------------------------------------------------------

CREATE FILE FORMAT IF NOT EXISTS datum.dev_marts.export_csv    -- how the unloaded files are written
  TYPE = CSV                                               -- delimited text
  COMPRESSION = GZIP                                       -- each file is compressed, and its name ends in .gz
  FIELD_DELIMITER = ','                                    -- a comma separates fields
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'                       -- a field is wrapped in double quotes when it needs to be, and a quote inside it is written twice
  NULL_IF = ()                                             -- write a NULL as nothing at all, not as the default \N. An empty text is written as "", so the two stay apart
  ESCAPE_UNENCLOSED_FIELD = NONE;                          -- no backslash escapes: Postgres reads CSV quoting, not backslashes

CREATE STAGE IF NOT EXISTS datum.dev_marts.export_stage    -- a holding area inside Snowflake for the unloaded files
  FILE_FORMAT = datum.dev_marts.export_csv;                -- written with the format above

REMOVE @datum.dev_marts.export_stage;                      -- delete the files of an earlier run. A smaller export would otherwise leave old files next to new ones

-- ---------------------------------------------------------------------------
-- The four unloads. Each SELECT lists its columns by name, in the order the loader expects, so a column
-- added to a mart later does not shift the file. HEADER = TRUE writes the column names as the first
-- line of every file, and the loader refuses a file whose header is not the one it expects.
-- A fetch time is written as text ending in Z (2026-11-18T07:10:58Z), which states in the file itself
-- that the time is UTC. The mart's column has no time zone, and a bare time would leave that to a guess.
-- ---------------------------------------------------------------------------

COPY INTO @datum.dev_marts.export_stage/company_search/company_search    -- the path inside the stage and the start of each file name
FROM (
  SELECT document_number,                                  -- the state's ID for the company
         entity_name,                                      -- the legal name as filed
         name_key,                                         -- the simplified name the search compares against
         status_code,                                      -- A = active, I = inactive
         filing_type,                                      -- the state's code for the kind of company
         file_date,                                        -- the date on record with the state
         principal_address_1,                              -- street
         principal_city,
         principal_state,
         principal_zip,
         published_on,                                     -- the date the state published the file the row came from
         source_url,                                       -- Sunbiz's search-by-document-number page
         TO_CHAR(fetched_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS fetched_at,   -- UTC, written with its Z. The T and the Z are literal characters, so they sit in double quotes
         fetched_at_is_approximate                         -- TRUE when the fetch time is an estimate
  FROM datum.dev_marts.company_search
)
HEADER = TRUE                                              -- first line of each file = the column names
MAX_FILE_SIZE = 268435456;                                 -- about 256 MB per file before compression, so 13 million rows arrive as several files

COPY INTO @datum.dev_marts.export_stage/company_flags/company_flags
FROM (
  SELECT document_number,                                  -- the company the flag is on
         flag_type,                                        -- federal_tax_lien or dbpr_license_inactive: the only kinds that are shown
         fact_date,                                        -- the date of the fact
         status,                                           -- open, closed or inactive
         status_note,                                      -- the events on the record, as facts
         source,                                           -- sunbiz_flr or dbpr
         source_record_id,                                 -- the number a reader types into the official search
         source_url,                                       -- the official search page
         citation,                                         -- the record, named in words
         source_file,                                      -- the file the record came from
         TO_CHAR(fetched_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS fetched_at,
         caveat,                                           -- what the flag cannot tell the reader
         is_shown,                                         -- TRUE on every exported row
         fetched_at_is_approximate
  FROM datum.dev_marts.company_flags
  WHERE is_shown                                           -- rule W9: a hidden flag never leaves Snowflake
)
HEADER = TRUE
MAX_FILE_SIZE = 268435456;

COPY INTO @datum.dev_marts.export_stage/company_possible_matches/company_possible_matches
FROM (
  SELECT document_number, flag_type, fact_date, status, status_note, source, source_record_id, source_url,
         citation, source_file,
         TO_CHAR(fetched_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS fetched_at,
         caveat, is_shown, fetched_at_is_approximate,
         link_reason                                       -- why the link is AMBIGUOUS
  FROM datum.dev_marts.company_possible_matches
  WHERE is_shown                                           -- rule W9. Every row is hidden today, so this unload writes no file at all
)
HEADER = TRUE
MAX_FILE_SIZE = 268435456;

COPY INTO @datum.dev_marts.export_stage/source_coverage/source_coverage.csv.gz   -- with SINGLE = TRUE this text is the whole file name, so the ending is written out
FROM (
  SELECT source,                                           -- the source's short name
         label,                                            -- the source in plain English
         is_shown,                                         -- TRUE = "checked" on a report, FALSE = "not checked"
         data_through,                                     -- the date the source's data runs through
         data_through_note,                                -- what kind of date that is
         source_url,                                       -- the official search page
         TO_CHAR(fetched_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS fetched_at,
         fetched_at_is_approximate,
         list_order                                        -- the order the report lists the sources in
  FROM datum.dev_marts.source_coverage
  ORDER BY list_order
)
HEADER = TRUE
SINGLE = TRUE;                                             -- five rows: one file

-- ---------------------------------------------------------------------------
-- The counts, as one more small file. The loader reads it and refuses to swap a table in unless the
-- rows it loaded equal the count here. A table that exported zero rows writes no file, and without
-- this file the loader could not tell "zero rows" from "the download is missing".
-- The WHERE clauses below are the same ones the four unloads above use.
-- ---------------------------------------------------------------------------
COPY INTO @datum.dev_marts.export_stage/export_counts/export_counts.csv.gz
FROM (
  SELECT 'company_search' AS table_name, COUNT(*) AS row_count FROM datum.dev_marts.company_search
  UNION ALL
  SELECT 'company_flags', COUNT(*) FROM datum.dev_marts.company_flags WHERE is_shown
  UNION ALL
  SELECT 'company_possible_matches', COUNT(*) FROM datum.dev_marts.company_possible_matches WHERE is_shown
  UNION ALL
  SELECT 'source_coverage', COUNT(*) FROM datum.dev_marts.source_coverage
)
HEADER = TRUE
SINGLE = TRUE;

-- ---------------------------------------------------------------------------
-- CHECK 1: what is on the stage. Expect several company_search files, a few company_flags files (Snowflake
-- writes in parallel), no company_possible_matches file, one source_coverage file and one export_counts file.
-- ---------------------------------------------------------------------------
LIST @datum.dev_marts.export_stage;

-- ---------------------------------------------------------------------------
-- CHECK 2: the row counts in Snowflake, exported and held back. Compare "exported" with the counts the
-- loader prints for Postgres. "held_back" is the hidden rows that stay in Snowflake.
-- ---------------------------------------------------------------------------
SELECT 'company_search' AS table_name, COUNT(*) AS rows_in_mart, COUNT(*) AS exported, 0 AS held_back
FROM datum.dev_marts.company_search
UNION ALL
SELECT 'company_flags', COUNT(*), COUNT_IF(is_shown), COUNT_IF(NOT is_shown)   -- COUNT_IF counts the rows where the condition is true
FROM datum.dev_marts.company_flags
UNION ALL
SELECT 'company_possible_matches', COUNT(*), COUNT_IF(is_shown), COUNT_IF(NOT is_shown)
FROM datum.dev_marts.company_possible_matches
UNION ALL
SELECT 'source_coverage', COUNT(*), COUNT(*), 0
FROM datum.dev_marts.source_coverage;


-- Syntax: COPY INTO @stage/path FROM (SELECT ...) is the unload form of COPY: the same statement that loads files into a table, pointed the other way. The text after the stage name is a path and a file-name prefix, and Snowflake adds a number and .csv.gz. HEADER = TRUE writes the column names first. SINGLE = TRUE forces one file whose name is exactly the text given, and without it Snowflake writes several files in parallel, each up to MAX_FILE_SIZE bytes. REMOVE @stage deletes staged files. NULL_IF = () on an unload means "write NULL as an empty field".

-- Concept: OLAP and OLTP. A warehouse such as Snowflake is built for OLAP (online analytical processing): a few heavy queries that scan millions of rows, billed by the second the engine is awake. An app needs OLTP (online transaction processing): many tiny lookups that each touch a handful of rows and must answer in milliseconds, around the clock. One engine does not do both well, so the warehouse builds the tables in batches and a small database serves them. The unload is the bridge between the two, and it runs after each build, not on each lookup.

-- Design decision: the filter that keeps hidden rows out lives HERE, in the export, and not in the app. The app could have been given every row and told to skip the hidden ones, and then one forgotten WHERE clause in one query would put a hidden Duval record on a contractor's phone. With the filter in the export, the hidden rows are not in the app's database at all, and the Postgres tables also refuse a row whose is_shown is false. Every SELECT names its columns, so the file layout is a contract the loader can check line one of every file against. The counts travel with the data as a fifth file, because a missing file and an empty table look the same on disk. The stage is internal to Snowflake, so nothing is written to cloud storage that somebody else manages.
