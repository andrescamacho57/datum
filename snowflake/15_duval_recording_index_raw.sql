-- 15_duval_recording_index_raw.sql: raw landing area for the Duval County Clerk's daily recording index.

-- Four file kinds per day, so four stages and four raw tables (decision d9):
--   d<date>01id.16  documents   one row per recorded document (deed, lien, judgment, release ...)
--   p<date>01id.16  parties     one row per party on a document (FRM = from, TO = to)
--   l<date>01id.16  links       one row per document, pointing at an earlier document it refers to (or NONE)
--   m<date>01d.16   doc types   the Clerk's lookup: document type code → type family
-- Layouts and counts: docs/access/duval-recording-index.md. Scope: files dated 2025-01-01 onward.
--
-- Before this script: download and VERIFY the files (every file's rows must equal its EOF trailer):
--     python src/datum/duval.py download
--
-- This script is safe to rerun, and it is meant to be run TWICE (same pattern as scripts 13 and 14):
--   1. Run it once to create the format, stages and tables (the COPYs find no files).
--        snow sql -c datum -f snowflake/15_duval_recording_index_raw.sql
--   2. Upload from the VS Code terminal. One PUT per kind; the first letter of the name picks the stage.
--        cd ~/datum/data/raw/duval
--        snow sql -c datum -q "PUT file://$PWD/d*.16 @datum.raw.duval_documents_stage AUTO_COMPRESS=TRUE PARALLEL=8"
--        snow sql -c datum -q "PUT file://$PWD/p*.16 @datum.raw.duval_parties_stage   AUTO_COMPRESS=TRUE PARALLEL=8"
--        snow sql -c datum -q "PUT file://$PWD/l*.16 @datum.raw.duval_links_stage     AUTO_COMPRESS=TRUE PARALLEL=8"
--        snow sql -c datum -q "PUT file://$PWD/m*.16 @datum.raw.duval_doc_types_stage AUTO_COMPRESS=TRUE PARALLEL=8"
--   3. Run this script again to load, and read the CHECK at the bottom.
--
-- The EOF trailer: every file ends with a line `EOF|<row count>`. COPY loads that line too, as one
-- extra row per file whose first field is 'EOF'. It is kept on purpose: with the trailer in raw,
-- the CHECK below can compare each file's data rows with the Clerk's own count inside Snowflake.
-- Staging filters the trailer rows out.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- File format: pipe-delimited text, no quoting, no header.
-- ---------------------------------------------------------------------------

CREATE FILE FORMAT IF NOT EXISTS datum.raw.duval_pipe      -- how to read every Duval index file
  TYPE = CSV                                               -- delimited text (the delimiter doesn't have to be a comma)
  FIELD_DELIMITER = '|'                                    -- a pipe separates fields
  FIELD_OPTIONALLY_ENCLOSED_BY = NONE                      -- no quoting: a double quote in a name is just a character
  SKIP_HEADER = 0                                          -- no header row
  ESCAPE_UNENCLOSED_FIELD = NONE                           -- backslashes are ordinary characters
  TRIM_SPACE = FALSE                                       -- keep padding spaces: raw stays as sent
  EMPTY_FIELD_AS_NULL = FALSE                              -- an empty field loads as empty text, not NULL; staging decides what is NULL
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE                   -- rows differ in length: most end with a pipe, the trailer has 2 fields, some lookup rows have 1
  ENCODING = 'ISO-8859-1';                                 -- Latin-1: any byte loads, one byte = one character

-- ---------------------------------------------------------------------------
-- Stages: one per file kind, all using the pipe format.
-- ---------------------------------------------------------------------------

CREATE STAGE IF NOT EXISTS datum.raw.duval_documents_stage -- holding area for the d files
  FILE_FORMAT = datum.raw.duval_pipe;                      -- pipe-delimited

CREATE STAGE IF NOT EXISTS datum.raw.duval_parties_stage   -- holding area for the p files
  FILE_FORMAT = datum.raw.duval_pipe;                      -- pipe-delimited

CREATE STAGE IF NOT EXISTS datum.raw.duval_links_stage     -- holding area for the l files
  FILE_FORMAT = datum.raw.duval_pipe;                      -- pipe-delimited

CREATE STAGE IF NOT EXISTS datum.raw.duval_doc_types_stage -- holding area for the m files
  FILE_FORMAT = datum.raw.duval_pipe;                      -- pipe-delimited

-- ---------------------------------------------------------------------------
-- Raw tables: one text column per field, plus the two provenance columns.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS datum.raw.duval_documents (     -- one row per line of a d file
  record_type        VARCHAR,                              -- field 1: DDA on data rows; EOF on the trailer row
  county_code        VARCHAR,                              -- field 2: 16 = Duval; on the trailer row, the file's row count
  instrument_number  VARCHAR,                              -- field 3: the Clerk's ID for the document, e.g. 2025900001
  doc_type_code      VARCHAR,                              -- field 4: e.g. LN, N/C, JDG, RELEASE
  doc_type_name      VARCHAR,                              -- field 5: the code in words, e.g. NOTICE COMMENCEMENT
  legal_description  VARCHAR,                              -- field 6: free text: parcel, lot, case number ...
  book_type          VARCHAR,                              -- field 7: OR = Official Records
  book               VARCHAR,                              -- field 8: book number
  page               VARCHAR,                              -- field 9: first page in the book
  unused_10          VARCHAR,                              -- field 10: empty in every sample; meaning unknown
  page_count         VARCHAR,                              -- field 11: number of pages
  record_date        VARCHAR,                              -- field 12: MM/DD/YYYY, the day the document was recorded
  record_time        VARCHAR,                              -- field 13: time of day as digits, e.g. 113841 = 11:38:41
  amount             VARCHAR,                              -- field 14: dollar amount on the document, 0.00 when none
  source_file        VARCHAR,                              -- which staged file the row came from (provenance)
  loaded_at          TIMESTAMP_NTZ                         -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.duval_parties (       -- one row per line of a p file
  record_type        VARCHAR,                              -- field 1: DPA on data rows; EOF on the trailer row
  county_code        VARCHAR,                              -- field 2: 16 = Duval; on the trailer row, the file's row count
  instrument_number  VARCHAR,                              -- field 3: the document this party is on
  party_seq          VARCHAR,                              -- field 4: the party's sequence number on the document
  party_role         VARCHAR,                              -- field 5: FRM (from) or TO
  party_name         VARCHAR,                              -- field 6: a person or a business, as indexed
  source_file        VARCHAR,                              -- which staged file the row came from (provenance)
  loaded_at          TIMESTAMP_NTZ                         -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.duval_links (         -- one row per line of an l file
  instrument_number         VARCHAR,                       -- field 1: the new document; EOF on the trailer row
  book                      VARCHAR,                       -- field 2: its book; on the trailer row, the file's row count
  page                      VARCHAR,                       -- field 3: its page
  book_type                 VARCHAR,                       -- field 4: OR
  doc_type_code             VARCHAR,                       -- field 5: its type, e.g. RELEASE
  linked_instrument_number  VARCHAR,                       -- field 6: the earlier document it refers to; empty when none
  linked_book               VARCHAR,                       -- field 7: that document's book
  linked_page               VARCHAR,                       -- field 8: that document's page
  linked_book_type          VARCHAR,                       -- field 9: OR
  linked_doc_type_code      VARCHAR,                       -- field 10: that document's type, e.g. LN; NONE when there is no link
  source_file               VARCHAR,                       -- which staged file the row came from (provenance)
  loaded_at                 TIMESTAMP_NTZ                  -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.duval_doc_types (     -- one row per line of an m file
  doc_type_code      VARCHAR,                              -- field 1: the document type code; EOF on the trailer row
  doc_type_family    VARCHAR,                              -- field 2: the family the code belongs to; on the trailer row, the row count
  source_file        VARCHAR,                              -- which staged file the row came from (provenance)
  loaded_at          TIMESTAMP_NTZ                         -- when COPY loaded it (provenance)
);

-- ---------------------------------------------------------------------------
-- COPY: stage → raw table. $1, $2 ... are each row's fields in file order.
-- A field the row doesn't have (a short row) comes back as NULL.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.duval_documents                        -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7,                       -- fields 1–7
         $8, $9, $10, $11, $12, $13, $14,                  -- fields 8–14 (the empty 15th, after the last pipe, is not read)
         METADATA$FILENAME,                                -- the staged file's name, e.g. d2025010301id.16.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.duval_documents_stage                    -- every d file
);

COPY INTO datum.raw.duval_parties                          -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6,                           -- fields 1–6
         METADATA$FILENAME,                                -- e.g. p2025010301id.16.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.duval_parties_stage                      -- every p file
);

COPY INTO datum.raw.duval_links                            -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,          -- fields 1–10
         METADATA$FILENAME,                                -- e.g. l2025010301id.16.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.duval_links_stage                        -- every l file
);

COPY INTO datum.raw.duval_doc_types                        -- every column, in the table's order
FROM (
  SELECT $1, $2,                                           -- fields 1–2
         METADATA$FILENAME,                                -- e.g. m2025010301d.16.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.duval_doc_types_stage                    -- every m file
);

-- ---------------------------------------------------------------------------
-- CHECK: for every loaded file, data rows = the count in its own EOF trailer.
-- One output row per table. Expected: files_mismatched = 0 and files_without_one_trailer = 0.
-- ---------------------------------------------------------------------------
WITH per_file AS (                                         -- step 1: one row per file, for all four tables
  SELECT 'documents' AS raw_table,                         -- a label
         source_file,
         COUNT_IF(record_type <> 'EOF')                              AS data_rows,     -- rows that are not the trailer
         COUNT_IF(record_type = 'EOF')                               AS trailer_rows,  -- must be exactly 1
         MAX(IFF(record_type = 'EOF', TRY_TO_NUMBER(county_code), NULL)) AS eof_count  -- the Clerk's count, read from the trailer row
  FROM datum.raw.duval_documents
  GROUP BY source_file
  UNION ALL
  SELECT 'parties', source_file,
         COUNT_IF(record_type <> 'EOF'), COUNT_IF(record_type = 'EOF'),
         MAX(IFF(record_type = 'EOF', TRY_TO_NUMBER(county_code), NULL))               -- same idea: field 2 of the trailer
  FROM datum.raw.duval_parties
  GROUP BY source_file
  UNION ALL
  SELECT 'links', source_file,
         COUNT_IF(instrument_number <> 'EOF'), COUNT_IF(instrument_number = 'EOF'),    -- l files have no record-type field: the trailer shows up in field 1
         MAX(IFF(instrument_number = 'EOF', TRY_TO_NUMBER(book), NULL))
  FROM datum.raw.duval_links
  GROUP BY source_file
  UNION ALL
  SELECT 'doc_types', source_file,
         COUNT_IF(doc_type_code <> 'EOF'), COUNT_IF(doc_type_code = 'EOF'),            -- same for m files
         MAX(IFF(doc_type_code = 'EOF', TRY_TO_NUMBER(doc_type_family), NULL))
  FROM datum.raw.duval_doc_types
  GROUP BY source_file
)
SELECT raw_table,                                          -- step 2: roll the files up to one row per table
       COUNT(*)                                    AS files_loaded,
       SUM(data_rows)                              AS data_rows,                -- rows loaded, trailers not counted
       SUM(eof_count)                              AS sum_of_eof_counts,        -- what the Clerk says the files hold
       COUNT_IF(data_rows <> eof_count OR eof_count IS NULL) AS files_mismatched,          -- expected 0
       COUNT_IF(trailer_rows <> 1)                 AS files_without_one_trailer -- expected 0
FROM per_file
GROUP BY raw_table
ORDER BY raw_table;


-- Syntax: WITH name AS (...) defines a named step (a CTE, common table expression) the final SELECT reads from. COUNT_IF(condition) counts the rows where the condition is true. IFF(condition, a, b) is a one-line if / else. MAX over a column that is NULL everywhere except one row is a common trick to "pick out" that one row's value inside a GROUP BY.

-- Concept: a trailer record. Fixed-width and delimited feeds often end with a line that states how many records the file should hold, so the receiver can prove nothing was lost on the way. Checking it twice is deliberate: Python checks the file on disk before upload, and this CHECK proves the same count survived PUT and COPY.

-- Design decision: the trailer row is loaded into raw, not stripped before upload. Stripping would mean editing the Clerk's file, and raw is the file as sent. The cost is one non-data row per file that staging must filter (record_type = 'EOF', or 'EOF' in field 1 for links and doc types). ERROR_ON_COLUMN_COUNT_MISMATCH is off because the rows really do differ in length; the protection against a shifted row is the Python verification plus the staging tests, not the loader. Latin-1 encoding is used because it can't fail on any byte; names with accented letters, if any, should be reviewed before display. The doc-type lookup is loaded for every day, although it rarely changes, so each day's documents can be read with the lookup as it was that day.
