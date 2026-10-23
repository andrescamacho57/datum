-- 05_validate_entity_lookup.sql: known-answer checks on the dbt mart.
-- Run after `dbt build`:  snow sql -c datum -f snowflake/05_validate_entity_lookup.sql
-- Method: look a company up BY HAND on search.sunbiz.org, write down its document number,
-- name, and status, then confirm the mart returns the same facts for that exact number.

USE ROLE SYSADMIN;                         -- owner role (not ACCOUNTADMIN)
USE WAREHOUSE datum_wh;                    -- cost-capped warehouse (not COMPUTE_WH)

-- CHECK 1: a company from the Oct 9 DAILY file (line 1 of 20261009c.txt).
-- Expected (2026-10-21): L26000514010 | DINATALE VENTURES LLC | A | FLAL | PALM BEACH GARDENS | daily | 2026-10-09
SELECT document_number,                    -- the company's state ID
       entity_name,                        -- legal name as filed
       status_code,                        -- A = active, I = inactive
       filing_type,                        -- FLAL = Florida LLC
       principal_city,                     -- city of the main business address
       source_kind,                        -- which kind of state file won the "newest" ordering
       published_on                        -- the date the state published that file
FROM datum.dev_marts.entity_lookup         -- the mart table dbt built
WHERE document_number = 'L26000514010';    -- EXACT match on the ID: one company, no guessing

-- CHECK 2: a long-established company from the QUARTERLY snapshot.
-- Hand-checked on search.sunbiz.org 2026-10-22:
--   P98000033661 | FERGUSON AIR CONDITIONING & REFRIGERATION, INC. | Active
-- Expected: same number, same name, status A, source_kind quarterly, published_on 2026-10-07.
SELECT document_number,                    -- must equal the number from the website
       entity_name,                        -- must equal the name from the website
       status_code,                        -- website "Active" = A
       filing_type,                        -- expect DOMP = domestic (Florida) profit corporation
       principal_city,                     -- compare to the address on the detail page
       file_date,                          -- expect a 1998 date: P98... = filed in 1998
       source_kind,                        -- expect quarterly (it isn't in the Oct 9 daily file)
       published_on                        -- expect 2026-10-07
FROM datum.dev_marts.entity_lookup
WHERE document_number = 'P98000033661';    -- exact match on the hand-checked ID

-- CHECK 3: the mix of sources in the mart. Expect ~13M quarterly rows and a few hundred daily.
SELECT source_kind,                        -- 'daily' or 'quarterly'
       status_code,                        -- A or I
       COUNT(*) AS companies               -- how many companies in each combination
FROM datum.dev_marts.entity_lookup
GROUP BY 1, 2                              -- group by the first two SELECT columns
ORDER BY 1, 2;                             -- sort the same way


-- Syntax: = 'P98000033661' is an exact comparison; LIKE '%FERGUSON%' is a pattern (% = any characters), useful for FINDING candidates, not for PROVING one.

-- Concept: a known-answer test compares the pipeline's output to a fact verified independently (by hand, at the source). It proves the whole chain at once: download, load, parse by position, dedupe.

-- Design decision: check by document number, not name. The number is the state's identity for a company; names repeat (the Sunbiz search shows several "FERGUSON LLC"s). Name search is a separate problem (matching), measured later by the 50-name test set.
