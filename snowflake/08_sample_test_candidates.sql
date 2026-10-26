-- 08_sample_test_candidates.sql: pull real Northeast Florida companies to build the test set from.
-- Why: the test set needs companies with KNOWN correct answers. Instead of hunting by hand,
-- let the data hand you candidates; you only judge which look like real trade clients
-- and write the messy text a contractor would type for each.
-- Run from the VS Code terminal:  snow sql -c datum -f snowflake/08_sample_test_candidates.sql

USE ROLE SYSADMIN;                                   -- owner role
USE WAREHOUSE datum_wh;                              -- cost-capped warehouse

SELECT document_number,                              -- the expected answer for the test row
       entity_name,                                  -- legal name as filed
       status_code,                                  -- A = active
       filing_type,                                  -- FLAL = Florida LLC, DOMP = Florida corporation
       principal_address_1,                          -- street address, to picture the business
       principal_city,
       principal_zip
FROM datum.dev_staging.stg_sunbiz__cor               -- staging has the address columns
WHERE source_kind = 'quarterly'                      -- the full register (one row per company)
  AND is_well_formed                                 -- skip damaged lines
  AND status_code = 'A'                              -- active companies: realistic clients
  AND filing_type IN ('FLAL', 'DOMP')                -- Florida LLCs and corporations (most small businesses)
  AND LEFT(principal_zip, 3) IN ('320', '322')       -- ZIP codes starting 320/322 = Northeast Florida
ORDER BY RANDOM()                                    -- shuffle, so every run gives a different sample
LIMIT 30;                                            -- 30 candidates; you keep about 6


-- Syntax: LEFT(text, 3) takes the first 3 characters. IN ('a', 'b') is shorthand for = 'a' OR = 'b'. ORDER BY RANDOM() gives every row a random number and sorts by it, which is a simple way to sample.

-- Concept: the ZIP code is used instead of the city because city names are inconsistently capitalized (Boynton Beach vs PALM BEACH GARDENS); ZIP digits have no casing problem.

-- Design decision: the expected answers come from our own data. That's safe because data correctness was already proven separately (known-answer checks in 05). This test set measures something different: whether SEARCH finds the right company from messy text.
