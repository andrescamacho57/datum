-- ---------------------------------------------------------------------------
-- source_coverage.sql: the MART that says which sources a report checked.
-- One row per loaded source.
--
-- Why it exists (Phase C working rule W5): a report lists the sources it
-- checked and the ones it did not. A source counts as "checked" only when
-- its flags may be SHOWN. Listing a hidden source as checked would tell a
-- contractor that Datum looked there and found nothing, when in fact Datum
-- looked and is not allowed to say what it found.
--
-- What each row carries:
--   source         the source's short name. dbpr is split in two, because
--                  its licenses are shown and its discipline records are not
--   label          the source in plain English, as the report prints it
--   is_shown       TRUE = "checked": this source's flags may be shown.
--                  FALSE = loaded, built and hidden, so "not checked"
--   data_through   the date this source's data runs through
--   data_through_note
--                  what that date is, in plain English, because it is a
--                  different kind of date for each source
--   source_url     the official page where a reader checks a record of this
--                  source (the seed search_page_sources)
--   fetched_at     the newest fetch time among this source's files, UTC
--   fetched_at_is_approximate
--                  TRUE when that newest time is an estimate from a file's
--                  modification time (ruling R23)
--
-- What is NOT here: things Datum has never loaded at all, such as court
-- cases, UCC (Uniform Commercial Code) filings, other counties and fictitious
-- names. Each row of this table is a fact about data Datum holds, and a fact
-- needs a source address and a fetch time (CLAUDE.md rule 3). "Court cases:
-- not checked" is a statement about Datum, with no file behind it. Those
-- lines are fixed wording in the app, next to the rows of this table whose
-- is_shown is FALSE.
--
-- Where is_shown comes from: for the two hidden sources, the same project
-- variables company_flags reads (show_duval, show_dbpr_discipline). The test
-- assert_source_coverage_agrees_with_the_flags then compares this table with
-- company_flags itself and with the literal false, so a source cannot be
-- listed as checked while its flags are hidden (ruling R28's two-edit rule).
--
-- No names. Grain: one row per source.
-- Becomes the table DATUM.DEV_MARTS.SOURCE_COVERAGE.
-- ---------------------------------------------------------------------------


with manifest as (
    -- STEP 1: when each source file was fetched (ruling R23). One row per file.
    select
        source,
        source_file,
        fetched_at_utc,
        is_approximate
    from {{ ref('stg_datum__fetch_manifest') }}
),

dbpr_files as (
    -- STEP 2: which DBPR file is which. The manifest files DBPR as one
    -- source, and this table needs licenses and discipline apart, so each
    -- file is labelled by the staging model that reads it.
    select distinct 'dbpr_license' as coverage_source, source_file
    from {{ ref('stg_dbpr__licenses') }}
    union all
    select distinct 'dbpr_discipline', source_file
    from {{ ref('stg_dbpr__discipline') }}
),

files as (
    -- STEP 3: every fetched file, labelled with the coverage source it
    -- belongs to. For the three other sources that is the manifest's own name.
    select
        d.coverage_source,
        m.fetched_at_utc,
        m.is_approximate
    from manifest as m
    inner join dbpr_files as d
        on m.source = 'dbpr' and d.source_file = m.source_file
    union all
    select
        m.source,
        m.fetched_at_utc,
        m.is_approximate
    from manifest as m
    where m.source in ('sunbiz_cor', 'sunbiz_flr', 'duval')
),

newest_fetch as (
    -- STEP 4: per source, the newest fetch time and whether THAT time is an
    -- estimate. max_by(a, b) returns the value of a on the row where b is
    -- largest. Here b is the fetch time written as text, with a 1 added to
    -- the end when the time is an estimate and a 0 when it was measured. So
    -- when two files share the newest time and only one of them is an
    -- estimate, the estimate wins, and the report says "about".
    select
        coverage_source,
        max(fetched_at_utc)                          as fetched_at,
        max_by(is_approximate,
               to_char(fetched_at_utc, 'YYYYMMDDHH24MISS') || iff(is_approximate, '1', '0')) as fetched_at_is_approximate
    from files
    group by coverage_source
),

data_through as (
    -- STEP 5: the date each source's data runs through. A different kind of
    -- date for each source, which is why each has its own note.
    select
        'sunbiz_cor'                                 as coverage_source,
        max(published_on)                            as data_through,
        'The date of the state''s latest quarterly snapshot of every company. A change to a company after that date is not covered.' as data_through_note
        -- The snapshot date, and not the date of a later daily file: a daily
        -- file holds only that day's NEW filings, so it does not carry a
        -- status change to an older company. Claiming a later date would
        -- claim more than the data holds.
    from {{ ref('stg_sunbiz__cor') }}
    where source_kind = 'quarterly'

    union all
    select
        'sunbiz_flr',
        t.through_date,
        'The date of the newest daily federal lien file loaded. A lien or a release filed after that date is not covered.'
        -- The same date the lien caveat in company_flags prints, from the
        -- same macro (macros/flag_rules.sql), so the two cannot drift apart.
    from (
        {{ lien_files_through_rows() }}
    ) as t

    union all
    select
        'dbpr_license',
        max(original_licensure_date),
        'The newest license issue date in DBPR''s licensee file. DBPR publishes no date for the file itself, and it leaves out delinquent, null-and-void and involuntarily inactive licenses.'
        -- DBPR's download page shows no file date (docs/access/dbpr.md), so
        -- the newest date inside the file is the only date the data itself
        -- gives. A date after the fetch would be a typo in the file, so
        -- such dates are left out of the max.
    from {{ ref('stg_dbpr__licenses') }} as lic
    where lic.original_licensure_date <= (
        select max(fetched_at_utc)::date from manifest where source = 'dbpr'
    )

    union all
    select
        'dbpr_discipline',
        max(discipline_date),
        'The newest discipline date in DBPR''s published discipline files.'
        -- The same date the discipline caveat in company_flags prints.
    from {{ ref('stg_dbpr__discipline') }}

    union all
    select
        'duval',
        max(try_to_date(substr(source_file, 2, 8), 'YYYYMMDD')),
        'The date of the newest daily recording index file loaded from the Duval County Clerk. Files dated 2025-01-01 onward are loaded.'
        -- A Duval file is named for its day: d2026111601id.16.gz. substr
        -- takes 8 characters starting at the 2nd, and try_to_date reads them
        -- as year-month-day, giving NULL if they are not a date.
    from {{ ref('stg_duval__documents') }}
),

sources as (
    -- STEP 6: the five loaded sources, their labels and whether their flags
    -- are shown. One row each, written out here so that a new source has to
    -- be added on purpose.
    select 'sunbiz_cor' as source, 'sunbiz_cor' as search_page_source, 1 as list_order,
           'Florida Division of Corporations company record (Sunbiz)' as label,
           true as is_shown
           -- The company's own record: its status, date on record and address.
    union all
    select 'sunbiz_flr', 'sunbiz_flr', 2,
           'Federal tax liens filed with the Florida Department of State',
           true
    union all
    select 'dbpr_license', 'dbpr', 3,
           'Florida DBPR construction contractor licenses',
           true
           -- DBPR = Department of Business and Professional Regulation.
    union all
    select 'dbpr_discipline', 'dbpr', 4,
           'Florida DBPR discipline records against construction license holders',
           {{ var("show_dbpr_discipline") }}
           -- FALSE unless the project variable is switched on (ruling R12).
    union all
    select 'duval', 'duval', 5,
           'Duval County recorded liens, tax warrants and judgments',
           {{ var("show_duval") }}
           -- FALSE unless the project variable is switched on (ruling R20).
)

-- STEP 7: one row per source.
select
    s.source,
    s.label,
    s.is_shown,
    d.data_through,
    d.data_through_note,
    p.search_page_url                                as source_url,
    n.fetched_at,
    n.fetched_at_is_approximate,
    s.list_order
    -- The order the report lists the sources in: the company record first.
from sources as s
left join data_through as d
    on d.coverage_source = s.source
left join newest_fetch as n
    on n.coverage_source = s.source
left join {{ ref('search_page_sources') }} as p
    on p.source = s.search_page_source
-- LEFT JOINs, so a source with no files, no date or no approved search page
-- is kept with a NULL, and a not_null test fails the build. An inner join
-- would drop the source from the report without a word.
