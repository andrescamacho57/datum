-- 19_sample_confirmed_links.sql: draw 20 CONFIRMED links for Andres to check by hand.

-- Why: a CONFIRMED link is a claim: "this lien (or license, or recorded document) belongs to this
-- company". Flags are built only on CONFIRMED links, so a wrong one puts a lien on the wrong
-- company's report. The linkage gate in the plan is 0 wrong among hand-checked CONFIRMED links
-- (spec A10). This script draws the sample; a person checks each row on the official search page.
--
-- What it draws: 8 federal lien links, 6 DBPR license links and 6 Duval links, picked in a fixed
-- pseudo-random order from the link models of leg B1.
--
-- Run it from the VS Code terminal. `--format csv` makes the CLI print comma-separated text
-- and `>` sends that text into the file:
--     cd ~/datum
--     snow sql -c datum -f snowflake/19_sample_confirmed_links.sql --format csv > evals/link_sample_20.csv
--
-- This script is ONE statement on purpose, with no USE ROLE / USE WAREHOUSE lines: every statement
-- prints a result, and extra results would end up inside the CSV file. The `datum` connection
-- already defaults to role SYSADMIN and warehouse DATUM_WH (the cost-capped X-Small).
--
-- The output file names real companies next to lien, license and instrument numbers, and the links
-- are NOT yet verified. evals/link_sample_20.csv is in .gitignore: it stays on this machine until
-- it has been checked and Andres decides what may be published. The Duval rows fall under ruling
-- R20 (nothing from Duval is shown outside this repo), and this repo is public.
--
-- How to check a row: open official_search_page, look up source_record_id, and compare the name
-- and address on the official record with the company you find by typing document_number into
-- company_search_page. Then fill in verdict (right / wrong / unsure), verified_on and notes.

WITH confirmed AS (                                        -- step 1: every CONFIRMED link from the three sources, with how many to take
  SELECT 'federal_lien' AS source,                         -- a label for the source
         source_record_id,                                 -- the lien's filing number
         document_number,                                  -- the company it was confirmed against
         matched_on,                                       -- name_zip or unique_name
         source_date,                                      -- the day the lien was filed
         8 AS rows_to_take                                 -- the brief asks for 8 federal lien links
  FROM datum.dev_intermediate.int_federal_lien_links
  WHERE link_status = 'CONFIRMED'
  UNION ALL                                                -- stack the next source underneath
  SELECT 'dbpr_license', source_record_id, document_number, matched_on, source_date, 6
  FROM datum.dev_intermediate.int_dbpr_license_links
  WHERE link_status = 'CONFIRMED'
    AND source_record_id NOT LIKE 'QB-%'                   -- contractor licenses only: a QB record has no number anyone can look up
  UNION ALL
  SELECT 'duval', source_record_id, document_number, matched_on, source_date, 6
  FROM datum.dev_intermediate.int_duval_party_links
  WHERE link_status = 'CONFIRMED'
),
one_per_link AS (                                          -- step 2: a lien with two debtors confirmed to one company is ONE link to check
  SELECT DISTINCT source, source_record_id, document_number, matched_on, source_date, rows_to_take
  FROM confirmed
),
shuffled AS (                                              -- step 3: number the links of each source in a fixed pseudo-random order
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY source                             -- restart the numbering for each source
           ORDER BY MD5(source || '|' || source_record_id || '|' || document_number || '|sample-2026-11-18')
         ) AS pick                                         -- MD5 scrambles the text, so sorting by it is as good as shuffling, and repeatable
  FROM one_per_link
)
SELECT e.entity_name                     AS "company_name_as_registered",   -- the legal name on Sunbiz
       s.document_number                 AS "document_number",            -- the company's Sunbiz document number
       s.source                          AS "source",                     -- federal_lien, dbpr_license or duval
       s.source_record_id                AS "source_record_id",           -- lien filing number, license number or Clerk's instrument number
       s.matched_on                      AS "matched_on",                 -- how the link was confirmed
       s.source_date                     AS "source_record_date",           -- lien filed / license period began / document recorded
       k.file_date                       AS "company_filing_date",          -- the company's own filing date (ruling R2: never after the record's date)
       CASE s.source                                                      -- where to look the record up (the same addresses as vars in pipeline/dbt_project.yml)
         WHEN 'federal_lien' THEN 'https://dos.fl.gov/sunbiz/search/'
         WHEN 'dbpr_license' THEN 'https://www.myfloridalicense.com/wl11.asp'
         WHEN 'duval'        THEN 'https://or.duvalclerk.com/'
       END                               AS "official_search_page",
       'https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber' AS "company_search_page",   -- where to look the company up
       ''                                AS "verdict",                      -- for the checker: right / wrong / unsure
       ''                                AS "verified_on",                  -- for the checker: the date checked
       ''                                AS "notes"                         -- for the checker
FROM shuffled AS s
JOIN datum.dev_marts.entity_lookup AS e                    -- the company's registered name
  ON e.document_number = s.document_number
JOIN datum.dev_intermediate.int_company_match_keys AS k    -- the company's filing date
  ON k.document_number = s.document_number
WHERE s.pick <= s.rows_to_take                             -- the first 8, 6 and 6
ORDER BY s.source, s.pick;                                 -- grouped by source, in draw order


-- Syntax: an alias in double quotes (AS "verdict") keeps its lower-case spelling; without the quotes Snowflake would print the column header as VERDICT. ROW_NUMBER() OVER (PARTITION BY a ORDER BY b) numbers the rows 1, 2, 3 ... separately inside each value of a, in the order of b. MD5(text) returns a 32-character checksum of the text. CASE x WHEN 'a' THEN ... END compares one expression with a list of values. DISTINCT removes repeated rows.

-- Concept: a hand-checked sample is how a matching rule is measured. The rule cannot grade itself: its tests only prove that it does what it was written to do. Twenty links checked against the official record estimate how often what it was written to do is actually right. Zero wrong in 20 does not prove zero wrong in 10,000, which is why the plan asks for at least 30 over time and for the count of wrong ones, not a pass mark.

-- Design decision: the order is pseudo-random and fixed (sorted by a checksum that includes the text 'sample-2026-11-18'), not ORDER BY RANDOM() as in script 08. A fixed draw means the file can be regenerated exactly, and that a second person checking the sample checks the same 20 links. To draw a fresh sample, change that text. The sample is stratified: 8, 6 and 6 by source, as the brief asks, so each source gets looked at even though DBPR has ten times more links. The tradeoff: 20 rows cannot say much about any one source, and the draw ignores how the link was matched; nearly every lien and license link is name_zip, so the few unique_name links outside Duval will rarely be drawn. QB business records are left out because the state gives them no number to look up.
