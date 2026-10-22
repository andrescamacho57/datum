-- 02_raw_layer.sql: the raw landing area for Sunbiz corporate files.
-- Run once, as SYSADMIN, after 01_cost_guardrails.sql.

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
