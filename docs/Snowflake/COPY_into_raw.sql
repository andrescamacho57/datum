USE ROLE SYSADMIN;                                          -- owner role
USE WAREHOUSE datum_wh;                                     -- guarded warehouse

LIST @datum.raw.sunbiz_stage;                               -- confirm the file is there (20261009c.txt)

COPY INTO datum.raw.sunbiz_cor_daily (line, source_file, loaded_at)   -- destination table and columns
FROM (``
  SELECT $1,                                                -- the whole line (the only field)
         METADATA$FILENAME,                                 -- which file it came from
         CURRENT_TIMESTAMP()                                -- load time
  FROM @datum.raw.sunbiz_stage                              -- every file in the stage (one today)
);

SELECT COUNT(*)          AS line_count,                     -- expect 834
       MIN(LENGTH(line)) AS shortest,                       -- expect 1436 or 1440
       MAX(LENGTH(line)) AS longest
FROM datum.raw.sunbiz_cor_daily;