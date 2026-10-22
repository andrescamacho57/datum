-- 05_validate_entity_lookup.sql: known-answer checks on the dbt mart.
-- Run after `dbt build`. DINATALE VENTURES LLC is line 1 of 20261009c.txt.

USE ROLE SYSADMIN;                         -- owner role (not ACCOUNTADMIN)
USE WAREHOUSE datum_wh;                    -- cost-capped warehouse (not COMPUTE_WH)

SELECT document_number,                    -- the company's state ID
       entity_name,                        -- legal name as filed
       status_code,                        -- A = active, I = inactive
       filing_type,                        -- FLAL = Florida LLC
       principal_city,                     -- city of the main business address
       source_file                         -- which state file this row came from
FROM datum.dev_marts.entity_lookup         -- the mart table dbt built
WHERE name_key LIKE '%DINATALE%'           -- name contains DINATALE anywhere
LIMIT 20;                                  -- at most 20 rows
-- Expected (2026-10-21): L26000514010 | DINATALE VENTURES LLC | A | FLAL | PALM BEACH GARDENS
