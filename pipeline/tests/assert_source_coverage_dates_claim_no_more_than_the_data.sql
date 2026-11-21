-- ---------------------------------------------------------------------------
-- assert_source_coverage_dates_claim_no_more_than_the_data.sql: a SINGULAR
-- test (returns the BAD rows; zero rows = PASS).
--
-- The rule (Phase C working rule W5, CLAUDE.md rule 2): the report prints
-- "data through <date>" for each source it checked, and that date must never
-- claim more than the data holds. The not_null test on data_through only
-- proves a date is there. This test checks WHICH date, six ways:
--   1. no source's data runs past the day its newest file was fetched
--   2. the company record's date is the date of the quarterly snapshot files
--      (cordata0.txt to cordata9.txt), found here by FILE NAME. The mart
--      finds it by the label source_kind, so the two routes are independent.
--      A daily file holds only that day's new filings, so its later date
--      would claim that status changes are covered when they are not
--   3. the federal lien date is the date every lien flag's caveat prints
--   4. the discipline date is the date every discipline flag's caveat prints
--   5. each source's newest fetch time is the newest among its files in the
--      fetch manifest
--   6. that time is marked as an estimate whenever ANY file fetched at that
--      newest time has an estimated fetch time
-- For 5 and 6 the DBPR files are told apart by file name, where the mart
-- tells them apart by which staging model reads them.
-- ---------------------------------------------------------------------------

with coverage as (
    select source, data_through, fetched_at, fetched_at_is_approximate
    from {{ ref('source_coverage') }}
),

snapshot_date as (
    -- The publish date of the company rows that came from a snapshot file.
    select max(published_on) as published_on
    from {{ ref('stg_sunbiz__cor') }}
    where source_file ilike 'cordata%'           -- cordata0.txt.gz to cordata9.txt.gz. ilike = like, ignoring upper/lower case
),

manifest_files as (
    -- Every fetched file, labelled with the coverage source it belongs to.
    select
        case
            when source = 'dbpr' and file_name ilike 'CONSTRUCTIONLICENSE%' then 'dbpr_license'
            when source = 'dbpr' and file_name ilike 'contractor_disc%'     then 'dbpr_discipline'
            when source = 'dbpr' then 'a DBPR file this test does not know: ' || file_name
            else source
        end as coverage_source,
        fetched_at_utc,
        is_approximate
    from {{ ref('stg_datum__fetch_manifest') }}
),

newest as (
    -- Per source: the newest fetch time, and whether any file fetched at
    -- that time has an estimated time. boolor_agg is TRUE when the condition
    -- is true on at least one row of the group.
    select
        m.coverage_source,
        max(m.fetched_at_utc) as fetched_at,
        boolor_agg(m.is_approximate and m.fetched_at_utc = n.newest_time) as any_estimate_at_the_newest_time
    from manifest_files as m
    inner join (
        select coverage_source, max(fetched_at_utc) as newest_time
        from manifest_files
        group by coverage_source
    ) as n
        on n.coverage_source = m.coverage_source
    group by m.coverage_source
)

select source, 'the data runs past the day its newest file was fetched' as problem      -- 1
from coverage
where data_through > fetched_at::date            -- ::date drops the time of day

union all
select c.source, 'the company record''s date is not the date of the quarterly snapshot files'   -- 2
from coverage as c
cross join snapshot_date as s
where c.source = 'sunbiz_cor'
  and c.data_through is distinct from s.published_on

union all
select c.source, 'a lien flag''s caveat prints a different date'                        -- 3
from coverage as c
inner join {{ ref('company_flags') }} as f
    on f.flag_type = 'federal_tax_lien'
where c.source = 'sunbiz_flr'
  and not contains(f.caveat, 'published through ' || to_char(c.data_through, 'YYYY-MM-DD') || '.')
group by c.source                                -- one row, not one per flag
-- contains(text, piece) is TRUE when the piece appears anywhere in the text.

union all
select c.source, 'a discipline flag''s caveat prints a different date'                  -- 4
from coverage as c
inner join {{ ref('company_flags') }} as f
    on f.flag_type = 'dbpr_discipline'
where c.source = 'dbpr_discipline'
  and not contains(f.caveat, 'run through ' || to_char(c.data_through, 'YYYY-MM-DD') || '.')
group by c.source

union all
select coalesce(c.source, n.coverage_source), 'the newest fetch time is not the newest in the fetch manifest'   -- 5
from coverage as c
full outer join newest as n                      -- also catches a source on one side only
    on n.coverage_source = c.source
where c.fetched_at is distinct from n.fetched_at

union all
select c.source, 'the newest fetch time is an estimate and is not marked as one'        -- 6
from coverage as c
inner join newest as n
    on n.coverage_source = c.source
where n.any_estimate_at_the_newest_time
  and c.fetched_at_is_approximate is distinct from true
