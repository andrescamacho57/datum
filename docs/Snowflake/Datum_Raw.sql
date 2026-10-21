USE ROLE SYSADMIN;                              -- owner role for everything below
USE WAREHOUSE datum_wh;                         -- the compute these statements run on

CREATE DATABASE IF NOT EXISTS datum;            -- top-level container for the project
CREATE SCHEMA IF NOT EXISTS datum.raw;          -- raw layer: data exactly as it arrived

CREATE FILE FORMAT IF NOT EXISTS datum.raw.fixed_width  -- tells Snowflake how to read the file
  TYPE = CSV                                    -- the closest built-in type to plain text lines
  FIELD_DELIMITER = NONE                        -- never split: each whole line becomes one field
  ESCAPE_UNENCLOSED_FIELD = NONE                -- treat backslashes as ordinary characters
  ENCODING = 'ISO-8859-1';                      -- Latin-1: exactly one byte per character

CREATE STAGE IF NOT EXISTS datum.raw.sunbiz_stage   -- a holding area inside Snowflake for uploaded files
  FILE_FORMAT = datum.raw.fixed_width;          -- files here are read with the format above

CREATE TABLE IF NOT EXISTS datum.raw.sunbiz_cor_daily (
  line        VARCHAR,                          -- the full 1440-character line, untouched
  source_file VARCHAR,                          -- which file it came from (provenance)
  loaded_at   TIMESTAMP_NTZ                     -- when it was loaded (provenance)
);

-- Syntax: database.schema.object is the fully qualified name. A stage is written as @name when you use it later.

-- Concept: Sunbiz files are fixed-width, meaning each field sits at a set character position. Snowflake has no fixed-width file type, so the standard approach is to load each whole line as one field and cut it into columns later.

-- Design decision: raw stores each line exactly as downloaded, and dbt does the parsing. If a field position is ever wrong, you fix one SQL file and rebuild; nothing has to be downloaded again. Latin-1 encoding means one character always equals one byte, so position 205 really is byte 205. source_file and loaded_at start provenance (where each fact came from and when) at the very first layer.



-- Load the file into the raw table

USE ROLE SYSADMIN;                                            -- act as SYSADMIN, the role that owns the datum objects

USE WAREHOUSE datum_wh;                                       -- run on the small, cost-capped warehouse

LIST @datum.raw.sunbiz_stage;                                 -- show files in the stage; expect 20261009c.txt


COPY INTO datum.raw.sunbiz_cor_daily (line, source_file, loaded_at)   -- destination table and the 3 columns to fill
FROM (
  SELECT $1,                                                  -- 1st field of each line; with no delimiter, that's the whole line
         METADATA$FILENAME,                                   -- Snowflake-supplied: name of the file this line came from
         CURRENT_TIMESTAMP()                                  -- the moment the load runs
  FROM @datum.raw.sunbiz_stage                                -- read every file in the stage (just one today)
);

SELECT COUNT(*)          AS line_count,                       -- number of rows loaded; expect 834
       MIN(LENGTH(line)) AS shortest,                         -- shortest line, in characters; expect 1436 or 1440
       MAX(LENGTH(line)) AS longest                           -- longest line; should equal shortest
FROM datum.raw.sunbiz_cor_daily;


select * from datum.raw.sunbiz_cor_daily;DATUM