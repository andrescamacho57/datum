-- ---------------------------------------------------------------------------
-- assert_flr_filings_unique_per_file.sql: a SINGULAR test.
--
-- A singular test is one .sql file in pipeline/tests/ holding one SELECT that
-- returns the BAD rows. dbt runs it during `dbt build`: zero rows = PASS.
--
-- The rule: within one state file, a lien's document number appears once.
-- The built-in `unique` test can't say "unique per file": the same lien is
-- allowed to appear in the quarterly snapshot AND in a daily file, so a plain
-- `unique` on filing_doc_number would fail for the wrong reason.
-- ---------------------------------------------------------------------------

select
    source_file,                                 -- the state file holding the duplicate
    filing_doc_number,                           -- the lien that appears more than once in it
    count(*) as times_seen                       -- how many times
from {{ ref('stg_sunbiz__flr_filings') }}
-- ref('model') in double curly braces points at another dbt model; dbt fills
-- in the real view name and learns that this test depends on that model.
group by source_file, filing_doc_number          -- one group per lien per file
having count(*) > 1                              -- having filters GROUPS (where filters rows): keep only duplicates
