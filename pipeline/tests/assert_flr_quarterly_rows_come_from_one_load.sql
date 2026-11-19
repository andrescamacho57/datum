-- ---------------------------------------------------------------------------
-- assert_flr_quarterly_rows_come_from_one_load.sql: a SINGULAR test (returns
-- the BAD rows; zero rows = PASS).
--
-- The problem it guards: the quarterly lien file's name (FLRF.TXT.gz) carries
-- no date, so stg_sunbiz__flr_filings writes ONE hardcoded date, 2026-10-03,
-- as published_on for every quarterly row (ruling R26 replaces it by
-- Dec 15, 2026).
--
-- int_federal_liens_status closes a lien that is "in an older snapshot but
-- not in the latest one" by comparing published_on dates. If a second
-- snapshot were loaded while the date is still hardcoded, both snapshots
-- would carry the same date, no lien would look "older", and a lien the
-- state dropped from its active list would stay OPEN on a report.
--
-- So this test fails the moment quarterly rows that share one published_on
-- come from more than one load. loaded_at is set once per COPY statement, so
-- two values mean two loads; two file names mean two files in one load.
-- Today there is one load of one file, and it passes.
--
-- When it fails: do not loosen it. Fix the date first (ruling R26), so each
-- snapshot gets its own published_on, and it will pass again.
-- ---------------------------------------------------------------------------

select
    published_on,                                -- the date every one of these rows was stamped with
    count(distinct loaded_at)   as loads,        -- how many separate loads share it (must be 1)
    count(distinct source_file) as files,        -- how many file names share it (must be 1)
    min(loaded_at)              as first_load,
    max(loaded_at)              as latest_load,
    count(*)                    as quarterly_rows
from {{ ref('stg_sunbiz__flr_filings') }}
where source_kind = 'quarterly'
group by published_on
having count(distinct loaded_at) > 1             -- having filters GROUPS: keep only a date shared by two loads
    or count(distinct source_file) > 1
