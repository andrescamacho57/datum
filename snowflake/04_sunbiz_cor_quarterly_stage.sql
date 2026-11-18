-- 04_sunbiz_cor_quarterly_stage.sql: stage for the quarterly FULL corporate snapshot.

-- One stage per file type (decision 2026-10-12): the quarterly snapshot is a different
-- kind of file from the daily delta, even though each line has the same 1440-byte layout.
--
-- Upload from the VS Code terminal (PUT only runs from a client on your machine):

--   cd ~/datum/data/raw/sunbiz/quarterly
--   snow sql -c datum -q "PUT file://$PWD/cordata*.txt @datum.raw.sunbiz_cor_quarterly_stage AUTO_COMPRESS=TRUE PARALLEL=8"

-- Note: quarterly lines end in CRLF (\r\n). Snowflake strips both, so each loads as 1440 characters (verified 2026-10-22).

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped warehouse

CREATE STAGE IF NOT EXISTS datum.raw.sunbiz_cor_quarterly_stage   -- a new holding area, just for quarterly corporate files
  FILE_FORMAT = datum.raw.fixed_width;                     -- read files with the same one-field-per-line format as before

LIST @datum.raw.sunbiz_cor_quarterly_stage;                -- after PUT: expect cordata0.txt.gz ... cordata9.txt.gz
