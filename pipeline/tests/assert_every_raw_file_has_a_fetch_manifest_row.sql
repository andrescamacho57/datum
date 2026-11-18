-- ---------------------------------------------------------------------------
-- assert_every_raw_file_has_a_fetch_manifest_row.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule: every file with rows in a raw table of the three downloaded
-- sources (DBPR, Duval, Sunbiz federal liens) has a row in the fetch
-- manifest. Without one, the facts from that file have no fetch time, which
-- breaks CLAUDE.md rule 3.
--
-- How it fails in practice: someone loads a file that was copied into data/
-- by hand, or runs a download and forgets to upload the manifest again
-- (snowflake/18_fetch_manifest.sql, step 2).
--
-- Not covered: the Sunbiz corporate files (sunbiz_cor_daily and
-- sunbiz_cor_quarterly). They were pulled by hand in October 2026, before
-- any downloader existed.
-- ---------------------------------------------------------------------------

with raw_files as (
    -- Every distinct file name in the raw tables, labelled with its source.
    -- `group by 2` groups by the second output column, which de-duplicates.
    select 'dbpr' as source, source_file from {{ source('dbpr', 'dbpr_licenses') }} group by 2
    union all
    select 'dbpr', source_file from {{ source('dbpr', 'dbpr_discipline') }} group by 2
    union all
    select 'duval', source_file from {{ source('duval', 'duval_documents') }} group by 2
    union all
    select 'duval', source_file from {{ source('duval', 'duval_parties') }} group by 2
    union all
    select 'duval', source_file from {{ source('duval', 'duval_links') }} group by 2
    union all
    select 'duval', source_file from {{ source('duval', 'duval_doc_types') }} group by 2
    union all
    select 'sunbiz_flr', source_file from {{ source('sunbiz', 'sunbiz_flr_filings') }} group by 2
    union all
    select 'sunbiz_flr', source_file from {{ source('sunbiz', 'sunbiz_flr_debtors') }} group by 2
    union all
    select 'sunbiz_flr', source_file from {{ source('sunbiz', 'sunbiz_flr_events') }} group by 2
    union all
    select 'sunbiz_flr', source_file from {{ source('sunbiz', 'sunbiz_flr_secured') }} group by 2
)

select
    r.source,                                    -- which source the unrecorded file belongs to
    r.source_file                                -- the file with no manifest row
from raw_files as r
left join {{ ref('stg_datum__fetch_manifest') }} as m   -- keep every raw file, matched or not
    on  m.source = r.source
    and m.source_file = r.source_file
where m.source_file is null                      -- no partner in the manifest = a bad row
