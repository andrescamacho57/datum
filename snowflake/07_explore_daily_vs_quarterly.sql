-- 07_explore_daily_vs_quarterly.sql: what is actually IN a daily file?
-- Question: are the 834 records in 20261009c.txt brand-new companies, or existing
-- companies whose records changed? Answer it with data instead of guessing.
-- Run from the VS Code terminal:  snow sql -c datum -f snowflake/07_explore_daily_vs_quarterly.sql

USE ROLE SYSADMIN;                                    -- owner role
USE WAREHOUSE datum_wh;                               -- cost-capped warehouse

-- QUERY 1: how many daily companies already existed in the Oct 7 snapshot?
WITH daily AS (                                       -- the 834 rows from the Oct 9 daily file
    SELECT document_number
    FROM datum.dev_staging.stg_sunbiz__cor            -- staging view: both sources, already parsed
    WHERE source_kind = 'daily'
),
quarterly AS (                                        -- the 13M rows from the Oct 7 snapshot
    SELECT document_number
    FROM datum.dev_staging.stg_sunbiz__cor
    WHERE source_kind = 'quarterly'
)
SELECT CASE
         WHEN q.document_number IS NULL               -- no match in the snapshot...
           THEN 'NEW: not in the Oct 7 snapshot'      -- ...so the company is new since then
         ELSE 'EXISTING: also in the Oct 7 snapshot'  -- otherwise its record was re-sent
       END                    AS record_kind,
       COUNT(*)               AS companies            -- how many daily rows fall in each bucket
FROM daily d                                          -- d = short alias for the daily CTE
LEFT JOIN quarterly q                                 -- keep EVERY daily row, matched or not
       ON d.document_number = q.document_number       -- match on the state's company ID
GROUP BY 1;                                           -- group by the first SELECT column (record_kind)

-- QUERY 2: when were the daily companies filed? New companies should be dated around Oct 9.
SELECT YEAR(file_date)        AS filed_year,          -- the year part of the date at positions 473-480
       COUNT(*)               AS companies,
       MIN(file_date)         AS earliest,            -- oldest date in that year
       MAX(file_date)         AS latest               -- newest date in that year
FROM datum.dev_staging.stg_sunbiz__cor
WHERE source_kind = 'daily'
GROUP BY 1
ORDER BY 1;                                           -- oldest year first

-- QUERY 3: the first 10 daily records, to eyeball what kind of companies they are.
SELECT document_number,                               -- L26... = LLC filed in 2026, P26... = corporation
       entity_name,
       status_code,
       filing_type,
       file_date
FROM datum.dev_staging.stg_sunbiz__cor
WHERE source_kind = 'daily'
ORDER BY document_number
LIMIT 10;


-- Syntax: LEFT JOIN keeps every row from the LEFT table (daily) even when the right table (quarterly) has no match; unmatched rows get NULL in the right table's columns. That NULL is how Query 1 detects "new". CASE WHEN ... THEN ... ELSE ... END turns a condition into a label.

-- Concept: this is an anti-join test. "Rows on the left with no partner on the right" is the standard way to find what's new, missing, or orphaned between two datasets.

-- Design decision: the state's documentation says the daily file holds "the filings added to our record that day." That sentence can mean new companies only, or any filing (including updates to existing companies). We don't build on an ambiguous sentence; we test it. If EXISTING > 0, daily files carry updates and "newest record wins" matters for every company, not just new ones.
