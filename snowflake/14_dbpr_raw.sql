-- 14_dbpr_raw.sql: raw landing area for the DBPR construction license and discipline files.

-- DBPR = Florida Department of Business and Professional Regulation. Two kinds of file:
--   licenses    CONSTRUCTIONLICENSE_1.csv          no header row, 22 fields per row
--   discipline  contractor_disc_lic_<years>.csv    one header row, 17 fields per row, one file per fiscal year
-- Where they come from, layouts and terms: docs/access/dbpr.md.
--
-- Before this script: download and VALIDATE the files (nothing is loaded that failed validation):
--     python src/datum/dbpr.py download
--
-- This script is safe to rerun, and it is meant to be run TWICE (same pattern as script 13):
--   1. Run it once to create the formats, stages and tables (the COPYs find no files).
--        snow sql -c datum -f snowflake/14_dbpr_raw.sql
--   2. Upload the 6 files from the VS Code terminal:
--        cd ~/datum/data/raw/dbpr
--        snow sql -c datum -q "PUT file://$PWD/CONSTRUCTIONLICENSE_1.csv @datum.raw.dbpr_licenses_stage AUTO_COMPRESS=TRUE"
--        snow sql -c datum -q "PUT file://$PWD/contractor_disc_lic_*.csv @datum.raw.dbpr_discipline_stage AUTO_COMPRESS=TRUE"
--   3. Run this script again to load, and read the CHECK at the bottom.
--
-- Expected rows (data lines = file lines minus the header, from `python src/datum/dbpr.py validate`, 2026-11-12):
--   CONSTRUCTIONLICENSE_1.csv 263,337 | disc 2122 1,109 | 2223 1,534 | 2324 1,878 | 2425 1,541 | 2526 395

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- File formats: how Snowflake should read a quote/comma delimited file.
-- Compare with fixed_width (script 02), which never splits a line at all.
-- ---------------------------------------------------------------------------

CREATE FILE FORMAT IF NOT EXISTS datum.raw.dbpr_csv        -- for the license file, which has NO header row
  TYPE = CSV                                               -- delimited text
  FIELD_DELIMITER = ','                                    -- a comma separates fields (fixed_width used NONE here)
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'                       -- fields are wrapped in double quotes, so a comma inside a name isn't a separator
  SKIP_HEADER = 0                                          -- line 1 is data: skip nothing
  ESCAPE_UNENCLOSED_FIELD = NONE                           -- treat backslashes as ordinary characters (3 addresses contain one)
  TRIM_SPACE = FALSE                                       -- keep padding spaces: raw stays exactly as sent, staging trims
  ERROR_ON_COLUMN_COUNT_MISMATCH = TRUE                    -- a row with the wrong number of fields stops the load instead of shifting columns
  ENCODING = 'UTF8';                                       -- the file is valid UTF-8 (checked 2026-11-12; 43 rows have accented letters)

CREATE FILE FORMAT IF NOT EXISTS datum.raw.dbpr_csv_header -- for the discipline files, which START with a header row
  TYPE = CSV                                               -- delimited text
  FIELD_DELIMITER = ','                                    -- comma between fields
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'                       -- fields wrapped in double quotes
  SKIP_HEADER = 1                                          -- the ONE difference: drop line 1, the column names
  ESCAPE_UNENCLOSED_FIELD = NONE                           -- backslashes are ordinary characters
  TRIM_SPACE = FALSE                                       -- keep padding spaces
  ERROR_ON_COLUMN_COUNT_MISMATCH = TRUE                    -- wrong field count stops the load
  ENCODING = 'UTF8';                                       -- these files are plain ASCII, which is also valid UTF-8

-- ---------------------------------------------------------------------------
-- Stages: one per file kind (decision d9), each tied to its format.
-- ---------------------------------------------------------------------------

CREATE STAGE IF NOT EXISTS datum.raw.dbpr_licenses_stage   -- holding area for CONSTRUCTIONLICENSE_1.csv
  FILE_FORMAT = datum.raw.dbpr_csv;                        -- no header

CREATE STAGE IF NOT EXISTS datum.raw.dbpr_discipline_stage -- holding area for the contractor_disc_lic_*.csv files
  FILE_FORMAT = datum.raw.dbpr_csv_header;                 -- skip the header row

LIST @datum.raw.dbpr_licenses_stage;                       -- after PUT: expect CONSTRUCTIONLICENSE_1.csv.gz
LIST @datum.raw.dbpr_discipline_stage;                     -- after PUT: expect 5 files, contractor_disc_lic_2122.csv.gz ... 2526.csv.gz

-- ---------------------------------------------------------------------------
-- Raw tables: one column per field, every column text, plus the two provenance columns.
-- Column names follow the state's own layout list ("File Layout Information" on its download page).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS datum.raw.dbpr_licenses (       -- one row per line of the construction licensee file
  board_number             VARCHAR,                        -- field 1: always 06, the Construction Industry Licensing Board
  occupation_code          VARCHAR,                        -- field 2: the kind of record, e.g. CGC general contractor, QB business
  licensee_name            VARCHAR,                        -- field 3: a person ("LAST, FIRST") or, on QB rows, a business
  dba_name                 VARCHAR,                        -- field 4: "doing business as" name, usually the contractor's company
  class_code               VARCHAR,                        -- field 5: sub-class of the license, mostly blank
  address_line_1           VARCHAR,                        -- field 6: mailing address, line 1
  address_line_2           VARCHAR,                        -- field 7: line 2
  address_line_3           VARCHAR,                        -- field 8: line 3
  city                     VARCHAR,                        -- field 9
  state                    VARCHAR,                        -- field 10
  zip                      VARCHAR,                        -- field 11: 5 digits, or ZIP+4 with a dash
  county_code              VARCHAR,                        -- field 12: DBPR's own county number (not a FIPS code)
  license_number           VARCHAR,                        -- field 13: digits only, zero-padded; BLANK on QB rows
  primary_status           VARCHAR,                        -- field 14: C current, P probation, S suspended
  secondary_status         VARCHAR,                        -- field 15: A active, I inactive, or blank
  original_licensure_date  VARCHAR,                        -- field 16: MM/DD/YYYY as text; staging turns it into a date
  effective_date           VARCHAR,                        -- field 17: MM/DD/YYYY as text
  expiration_date          VARCHAR,                        -- field 18: MM/DD/YYYY as text; blank on QB rows
  blank_field              VARCHAR,                        -- field 19: the layout calls it "Blank"; always empty
  renewal_period           VARCHAR,                        -- field 20: always empty in this file
  alternate_license_number VARCHAR,                        -- field 21: the number as printed on a license, e.g. CGC1505679
  trailing_field           VARCHAR,                        -- field 22: not in the layout; an empty field at the end of every row
  source_file              VARCHAR,                        -- which staged file the row came from (provenance)
  loaded_at                TIMESTAMP_NTZ                   -- when COPY loaded it (provenance)
);

CREATE TABLE IF NOT EXISTS datum.raw.dbpr_discipline (     -- one row per data line of a licensed-contractor discipline file
  license_type             VARCHAR,                        -- field 1: the license kind in words, e.g. Certified General Contractor
  license_nbr              VARCHAR,                        -- field 2: digits, NOT zero-padded (differs from the license file)
  respondent_name          VARCHAR,                        -- field 3: the licensee the complaint is against (a person)
  address_line_1           VARCHAR,                        -- field 4: or the words "Private Address"
  address_line_2           VARCHAR,                        -- field 5
  address_line_3           VARCHAR,                        -- field 6
  city                     VARCHAR,                        -- field 7
  state                    VARCHAR,                        -- field 8
  zip_code                 VARCHAR,                        -- field 9
  county                   VARCHAR,                        -- field 10: county NAME here (the license file has a code)
  complaint_nbr            VARCHAR,                        -- field 11: DBPR's case number, e.g. 2025900001 (an invented number in the real shape)
  classification           VARCHAR,                        -- field 12: e.g. Licensed Activity
  entered_date             VARCHAR,                        -- field 13: MM/DD/YYYY, when the complaint was entered
  disposition              VARCHAR,                        -- field 14: how the case ended, e.g. Final Order
  disposition_date         VARCHAR,                        -- field 15: MM/DD/YYYY, may be blank
  discipline_description   VARCHAR,                        -- field 16: "MM/DD/YYYY - what was imposed", e.g. "06/11/2026 - Fine"
  violation_code           VARCHAR,                        -- field 17: mostly blank
  source_file              VARCHAR,                        -- which staged file the row came from (provenance); also tells the fiscal year
  loaded_at                TIMESTAMP_NTZ                   -- when COPY loaded it (provenance)
);

-- ---------------------------------------------------------------------------
-- COPY: stage → raw table. $1, $2 ... are the fields of each row, in file order.
-- ---------------------------------------------------------------------------

COPY INTO datum.raw.dbpr_licenses                          -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,     -- fields 1–11
         $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22,  -- fields 12–22
         METADATA$FILENAME,                                -- the staged file's name
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.dbpr_licenses_stage                      -- the license file
);

COPY INTO datum.raw.dbpr_discipline                        -- every column, in the table's order
FROM (
  SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,     -- fields 1–11
         $12, $13, $14, $15, $16, $17,                     -- fields 12–17
         METADATA$FILENAME,                                -- e.g. contractor_disc_lic_2526.csv.gz
         CURRENT_TIMESTAMP()                               -- the moment this COPY ran
  FROM @datum.raw.dbpr_discipline_stage                    -- all five fiscal-year files
);

-- ---------------------------------------------------------------------------
-- CHECK: rows per file. Each must equal the file's data lines (see the header of this script).
-- ---------------------------------------------------------------------------
SELECT 'licenses' AS raw_table,                            -- a label so both tables share one result
       source_file,                                        -- one output row per file
       COUNT(*) AS rows_loaded                             -- compare with the validator's "data rows"
FROM datum.raw.dbpr_licenses
GROUP BY source_file                                       -- group rows by file before counting
UNION ALL                                                  -- stack the discipline result underneath
SELECT 'discipline', source_file, COUNT(*)                 -- same three columns
FROM datum.raw.dbpr_discipline
GROUP BY source_file
ORDER BY 1 DESC, 2;                                        -- licenses first, then discipline files by name


-- Syntax: $1 ... $22 name a staged file's fields by position; they only work when reading from a stage. A file format is a saved, named set of reading rules, and a stage can carry one so every COPY from it uses the same rules. FIELD_OPTIONALLY_ENCLOSED_BY = '"' tells Snowflake that quotes wrap a field and are not part of its value.

-- Concept: delimited vs fixed-width. In a fixed-width file a field is "characters 14 to 68", so the file loads as one column and SQL cuts it later. In a delimited file a separator marks where each field ends, so Snowflake can split it at load time and raw gets one column per field. Quoting exists because the data itself can contain the separator ("SMITH, JOHN"). SKIP_HEADER matters because a header row is text, not data: loaded by mistake it becomes one bogus row.

-- Design decision: two file formats that differ in one line (SKIP_HEADER), because the license file has no header and the discipline files do. One format with a COPY-time override would hide that difference inside the COPY. Every raw column is VARCHAR, dates included: raw records what the state sent, and staging does the typing with TRY_TO_DATE, so a bad date becomes a visible NULL in staging instead of a failed load. All five discipline years share one table and are told apart by source_file. The tradeoff of loading the license file as a full replacement each week is that raw keeps every weekly copy only if file names differ; today the name never changes, so COPY skips a re-upload of the same name. A dated folder in the stage path fixes that when weekly refreshes start.
