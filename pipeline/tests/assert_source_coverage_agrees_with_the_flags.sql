-- ---------------------------------------------------------------------------
-- assert_source_coverage_agrees_with_the_flags.sql: a SINGULAR test (returns
-- the BAD rows; zero rows = PASS).
--
-- The rule (Phase C working rule W5): a source counts as "checked" only when
-- its flags may be shown. The report's "checked" list is the rows of
-- source_coverage with is_shown TRUE, so this test fails when:
--   1. a hidden source is listed as checked. Ruling R28, applied here: the
--      comparison is with the word false written in THIS file, not with the
--      project variables, which source_coverage itself reads. Showing Duval
--      or DBPR discipline therefore takes one more reviewed edit, here
--   2. one of the three sources that are shown today is listed as not
--      checked, which would hide real coverage by accident
--   3. source_coverage and company_flags disagree: a source is listed as
--      checked while one of its flags is hidden, or the other way round
--   4. a source is missing from the table, or one nobody planned is in it
-- ---------------------------------------------------------------------------

with coverage as (
    select source, is_shown
    from {{ ref('source_coverage') }}
),

flags as (
    -- Each flag, labelled with the coverage source it belongs to. DBPR is
    -- split by flag type, the same way source_coverage splits it.
    select
        case
            when flag_type = 'federal_tax_lien'      then 'sunbiz_flr'
            when flag_type = 'dbpr_license_inactive' then 'dbpr_license'
            when flag_type = 'dbpr_discipline'       then 'dbpr_discipline'
            when flag_type like 'duval_%'            then 'duval'
            else 'a flag type this test does not know: ' || flag_type
        end as coverage_source,
        is_shown
    from {{ ref('company_flags') }}
),

expected_sources as (
    -- The five sources the table must hold. `values` writes rows inline.
    select column1 as source
    from values ('sunbiz_cor'), ('sunbiz_flr'), ('dbpr_license'), ('dbpr_discipline'), ('duval')
)

select source, 'a hidden source is listed as checked' as problem          -- 1
from coverage
where source in ('duval', 'dbpr_discipline')
  and is_shown is distinct from false
-- "is distinct from false" is "<> false" that also catches NULL.

union all
select source, 'a source that is shown today is listed as not checked'    -- 2
from coverage
where source in ('sunbiz_cor', 'sunbiz_flr', 'dbpr_license')
  and is_shown is distinct from true

union all
select f.coverage_source, 'source_coverage and company_flags disagree about whether this source is shown'   -- 3
from flags as f
left join coverage as c
    on c.source = f.coverage_source
where c.source is null                           -- a flag whose source has no coverage row at all
   or f.is_shown is distinct from c.is_shown     -- or one that is shown where its source is not (or the reverse)
group by f.coverage_source                       -- one row per source, not one per flag

union all
select coalesce(e.source, c.source), 'a source is missing from source_coverage, or an unplanned one is in it'   -- 4
from expected_sources as e
full outer join coverage as c
    on c.source = e.source
where e.source is null or c.source is null
