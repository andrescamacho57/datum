-- 20_draft_lookup_cases.sql: draft 40 lookup test cases from names other people typed.

-- Why: the lookup test set (pipeline/seeds/test_set.csv) has 10 cases, written by hand. It needs
-- more, and the best inputs are real strings typed by SOMEONE ELSE: the IRS writing a debtor's name
-- on a lien, a contractor writing a business name on a license. Those spell a company's name the
-- way the real world does, not the way the register does.
--
-- What it drafts: 20 cases from federal lien debtor names and 20 from DBPR license business names,
-- each with the company the CONFIRMED link of leg B1 says it is. Half of each 20 are names whose
-- words differ from the registered name (a different or missing legal suffix), half are the same
-- words with different punctuation.
--
-- THESE ARE DRAFTS. The expected answer is the link model's belief, not a checked fact. Do not
-- add them to pipeline/seeds/test_set.csv until each expected_document_number has been checked
-- on Sunbiz.
--
-- Run it from the VS Code terminal (same pattern as script 19):
--     cd ~/datum
--     snow sql -c datum -f snowflake/20_draft_lookup_cases.sql --format csv > evals/draft_test_cases_40.csv
--
-- One statement, no USE lines, for the reason given in script 19. The output file is in
-- .gitignore: its expected answers are unverified.
--
-- The notes column is neutral on purpose: "DRAFT, not verified. Company status on Sunbiz: A."
-- It never says where a spelling came from. test_set.csv is public, and "from a federal lien
-- debtor name" next to a real company would publish a lien link nobody has checked.
--
-- Businesses only: a name is used only if it contains a legal-entity word (LLC, INC, CORP ...),
-- the same test the link models use. The columns match test_set.csv, but a checked row is NOT
-- pasted in as it is. First fill in verified_on, replace the DRAFT sentence in notes, and give the
-- row a new case_id: here ids 101 to 120 are the lien spellings and 121 to 140 the license
-- spellings, so an id kept from this file would still say where the name came from.

WITH lien_debtors AS (                                     -- step 1a: one row per corporate debtor on a lien (the same de-duplication as the link model)
  SELECT filing_doc_number, debtor_seq, debtor_name
  FROM datum.dev_staging.stg_sunbiz__flr_debtors
  QUALIFY ROW_NUMBER() OVER (PARTITION BY filing_doc_number, debtor_seq ORDER BY published_on DESC, loaded_at DESC) = 1
),
source_names AS (                                          -- step 1b: every CONFIRMED source name with the company it points at
  SELECT 'a federal lien debtor name' AS drawn_from,       -- where the spelling comes from
         d.debtor_name                AS source_name,      -- the name as the IRS wrote it
         l.document_number                                 -- the company the link model confirmed
  FROM datum.dev_intermediate.int_federal_lien_links AS l
  JOIN lien_debtors AS d
    ON d.filing_doc_number = l.source_record_id AND d.debtor_seq = l.party_seq
  WHERE l.link_status = 'CONFIRMED'
  UNION                                                    -- UNION (no ALL) also removes repeated rows: the same name on two liens is one case
  SELECT 'a DBPR license business name',
         lic.dba_name,                                     -- the business name on the license, never the license holder's name
         ll.document_number
  FROM datum.dev_intermediate.int_dbpr_license_links AS ll
  JOIN datum.dev_staging.stg_dbpr__licenses AS lic
    ON lic.alternate_license_number = ll.source_record_id AND lic.record_kind = 'contractor_license'
  WHERE ll.link_status = 'CONFIRMED'
),
compared AS (                                              -- step 2: compare each source spelling with the registered name
  SELECT n.drawn_from,
         n.source_name,
         n.document_number,
         e.entity_name,                                    -- the registered name
         e.status_code,                                    -- A active, I inactive
         TRIM(REGEXP_REPLACE(UPPER(n.source_name), '[^A-Z0-9]+', ' ')) AS source_name_key,   -- the source name simplified the way name_key is
         e.name_key,
         k.match_key
  FROM source_names AS n
  JOIN datum.dev_marts.entity_lookup AS e                  ON e.document_number = n.document_number
  JOIN datum.dev_intermediate.int_company_match_keys AS k  ON k.document_number = n.document_number
),
labelled AS (                                              -- step 3: keep business names only, and say how each differs
  SELECT *,
         CASE
           WHEN source_name = entity_name   THEN 'identical'                       -- letter for letter: a dull test case, left out below
           WHEN source_name_key = name_key  THEN 'punctuation or spacing differs'  -- same words once simplified
           ELSE 'legal suffix written differently'                                 -- same match key, another ending: INC vs INCORPORATED, INC vs LLC ...
         END AS case_type
  FROM compared
  WHERE REGEXP_LIKE(source_name_key, '(.* )?(P L L C|L L C|INCORPORATED|CORPORATION|COMPANY|LIMITED|LLLP|PLLC|LLC|LLP|INC|CORP|LTD|PLC|CO|LC|LP|PA|PC|PL)( .*)?')   -- the entity-word test of macros/company_matching.sql
),
one_per_company AS (                                       -- step 4: a company appears once, so 40 cases are 40 different companies
  SELECT *
  FROM labelled
  WHERE case_type <> 'identical'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY document_number ORDER BY MD5(source_name || '|' || drawn_from || '|cases-2026-11-18')) = 1   -- drawn_from is in the checksum so a name spelled the same on a lien and on a license does not tie
),
shuffled AS (                                              -- step 5: number the cases inside each (origin, kind of difference) group, in a fixed pseudo-random order
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY drawn_from, case_type
           ORDER BY MD5(document_number || '|' || source_name || '|cases-2026-11-18')
         ) AS pick
  FROM one_per_company
)
SELECT 100 + ROW_NUMBER() OVER (ORDER BY drawn_from DESC, case_type, pick) AS "case_id",   -- 101 to 140: clear of the ids already in test_set.csv; draft ids only, lien spellings first (see the header)
       'source_spelling_draft'                                AS "case_group",
       source_name                                            AS "input_text",             -- what the lookup will be given
       document_number                                        AS "expected_document_number",
       entity_name                                            AS "expected_entity_name",
       case_type                                              AS "case_type",
       ''                                                     AS "verified_on",            -- empty until a person checks the row on Sunbiz
       'DRAFT, not verified. Company status on Sunbiz: ' || status_code || '.' AS "notes"   -- neutral: no word about which source the spelling came from
FROM shuffled
WHERE pick <= 10                                           -- 10 per group; 2 origins x 2 kinds of difference = 40
ORDER BY "case_id";                                        -- a quoted alias must be quoted the same way wherever it is used


-- Syntax: an alias in double quotes (AS "case_id") keeps its lower-case spelling in the file's header row, matching test_set.csv. QUALIFY filters on a window function, the way WHERE filters on a column: here it keeps row number 1 of each group. UNION stacks two results and drops repeated rows (UNION ALL keeps them). A window function can sit directly in the SELECT list, as the case_id does. REGEXP_LIKE must match the whole text, which is why the pattern allows anything before and after the entity word.

-- Concept: an eval case is an input plus the answer a correct system must give. Where the inputs come from decides what the eval can find. Cases written by the person who built the search tend to be cases the search already handles. Names written by a third party (here the IRS and license holders) bring spellings nobody on the project thought of. The expected answer still has to be checked by a person, because the link that supplies it is itself a model's output: grading a search with unchecked labels measures agreement between two guesses.

-- Design decision: the draft takes only CONFIRMED links and only names with a legal-entity word, so every row is a business and has one expected company. Letter-for-letter identical names are left out: they test nothing. The 40 are split evenly by origin and by kind of difference so that the harder kind (a legal suffix written differently) is not crowded out by the common kind. The tradeoff is that these are all near-exact names: no typos, no abbreviations, no vague notes, no "needs more information" cases. The plan asks for those kinds too (at least 5 each of NEEDS_MORE_INFO, inactive companies and near-twins); the hard ones come from the 5,814 lien debtors that matched no company at all, and they have no expected answer until a person finds one.
