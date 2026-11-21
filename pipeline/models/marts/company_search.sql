-- ---------------------------------------------------------------------------
-- company_search.sql: the MART the app searches, and the source of a
-- report's header. One row per company.
--
-- Why it exists next to entity_lookup: entity_lookup is the company register
-- shaped for matching inside the warehouse. The web app reads a copy of THIS
-- table in Postgres, and everything the app states about a company must be a
-- fact with a source address and a fetch time (CLAUDE.md rule 3, Phase C
-- working rule W1). That includes the company's own status, date on record
-- and address, not only the flags. entity_lookup has neither column, and an
-- existing mart is never changed, so they are added here.
--
-- What each row carries:
--   the company      document_number, entity_name, name_key, status_code,
--                    filing_type, file_date and the four principal address
--                    columns, exactly as entity_lookup has them
--   published_on     the date the STATE published the file the row came from
--   source_url       where a reader checks the record. No source we use
--                    offers a link to one record, so this is Sunbiz's
--                    search-by-document-number page, and the document number
--                    finds the record (ruling R9; the page is the row
--                    sunbiz_cor of the seed search_page_sources)
--   fetched_at       when Datum fetched that file, in UTC, from the fetch
--                    manifest
--   fetched_at_is_approximate
--                    TRUE when that time is a file's modification time and
--                    not a measured fetch. Today it is TRUE on every row: the
--                    corporate files were pulled by hand in October 2026,
--                    before the manifest existed. The report then says
--                    "about".
--
-- Names: entity_name and name_key are REGISTERED BUSINESS names from the
-- state's corporate register, never a person's name. This table is one of
-- the three named exceptions in tests/assert_no_name_columns_past_staging.sql.
-- No officer, registered agent or owner is here, and none may be added.
--
-- Grain: one row per company (document_number is unique).
-- Becomes the table DATUM.DEV_MARTS.COMPANY_SEARCH.
-- ---------------------------------------------------------------------------

-- depends_on: {{ ref('search_page_sources') }}
-- This model does not READ that seed: its address comes from a project
-- variable, and the test assert_company_search_cites_the_approved_search_page
-- compares the two, so they stay independent (the reasoning of ruling R28).
-- The line above only tells dbt the seed belongs to this model's build.


with companies as (
    -- STEP 1: every company, one row each. entity_lookup already keeps the
    -- newest published row per company.
    select
        document_number,                             -- the state's ID for the company
        entity_name,                                 -- the legal name exactly as filed
        name_key,                                    -- the simplified name the search compares against
        status_code,                                 -- A = active, I = inactive
        filing_type,                                 -- the state's code for the kind of company (FLAL, DOMP ...)
        file_date,                                   -- the date on record with the state
        principal_address_1,                         -- street
        principal_city,
        principal_state,
        principal_zip,
        published_on,                                -- the date the state published the file this row came from
        source_file                                  -- that file's name in raw; used below to find its fetch time, and not output
    from {{ ref('entity_lookup') }}
),

corporate_files as (
    -- STEP 2: when each corporate file was fetched (ruling R23). One row per
    -- file: stg_datum__fetch_manifest keeps the latest fetch of each.
    select
        file_name,                                   -- the file's name as fetched, e.g. cordata0.txt
        fetched_at_utc,                              -- the fetch time, UTC
        is_approximate                               -- TRUE when that time is a modification time
    from {{ ref('stg_datum__fetch_manifest') }}
    where source = 'sunbiz_cor'                      -- the state's corporate files only
)

-- STEP 3: each company with the fetch time of the file it came from.
select
    c.document_number,
    c.entity_name,
    c.name_key,
    c.status_code,
    c.filing_type,
    c.file_date,
    c.principal_address_1,
    c.principal_city,
    c.principal_state,
    c.principal_zip,
    c.published_on,

    '{{ var("sunbiz_company_search_url") }}'         as source_url,
    -- The same address on every row: Sunbiz's search-by-document-number page.

    f.fetched_at_utc                                 as fetched_at,
    -- NULL when the company's file has no manifest row. A not_null test
    -- then fails the build: a company with no fetch time can't be shown.

    f.is_approximate                                 as fetched_at_is_approximate

from companies as c
left join corporate_files as f
    on f.file_name = regexp_replace(c.source_file, '\\.gz$', '')
-- LEFT JOIN, so a company whose file is missing from the manifest is kept
-- and the test catches it, where an inner join would drop it without a word.
--
-- Why not join on the manifest's own source_file column: the staging model
-- builds that column by adding .gz to the file name, because PUT compresses
-- a file as it uploads it. That holds for the ten quarterly files
-- (cordata0.txt.gz) and not for the daily file, which was loaded as it was
-- (20261009c.txt). So both sides are compared without the ending.
-- regexp_replace(text, pattern, '') removes what the pattern matches; in
-- '\\.gz$' the two backslashes reach the pattern as one, which makes the dot
-- a literal dot, and $ is the end of the text.
