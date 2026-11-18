-- ---------------------------------------------------------------------------
-- assert_dbpr_license_key_unique.sql: a SINGULAR test.
--
-- A singular test is one .sql file in pipeline/tests/ holding one SELECT that
-- returns the BAD rows. dbt runs it during `dbt build`: zero rows = PASS.
--
-- The rule: within one file, occupation_code + license_number appears once.
-- license_number ALONE is not unique: DBPR numbers each kind of license
-- separately, so 0001234 can be a general contractor and also a roofing
-- contractor. The pair is the real key.
--
-- QB rows are left out: the state's file gives them no license number, so
-- there is nothing to be unique.
-- ---------------------------------------------------------------------------

select
    source_file,                                 -- the file holding the duplicate
    occupation_code,                             -- the kind of license
    license_number,                              -- the number that appears more than once for that kind
    count(*) as times_seen                       -- how many times
from {{ ref('stg_dbpr__licenses') }}
-- ref('model') in double curly braces points at another dbt model; dbt fills
-- in the real view name and learns that this test depends on that model.
where occupation_code <> 'QB'                    -- QB rows have no number (see above)
group by source_file, occupation_code, license_number   -- one group per key per file
having count(*) > 1                              -- having filters GROUPS (where filters rows): keep only duplicates
