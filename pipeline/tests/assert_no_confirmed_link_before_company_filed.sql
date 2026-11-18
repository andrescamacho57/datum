-- ---------------------------------------------------------------------------
-- assert_no_confirmed_link_before_company_filed.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule (ruling R2): a record dated before the company's own filing date
-- on Sunbiz is never CONFIRMED. A company can't owe a lien from before it
-- existed; when the dates say it does, the record almost always belongs to
-- an older, dissolved company whose name a newer one took.
--
-- The link models already apply this rule. This test checks the RESULT
-- independently: it re-reads every CONFIRMED link in all four models and
-- compares the two dates itself. A CONFIRMED link with either date missing
-- is also bad: R2 could not have been checked for it.
-- ---------------------------------------------------------------------------

with confirmed as (
    -- Every CONFIRMED link, from all four link models, labelled with its source.
    select 'federal_lien' as link_source, source_record_id, party_seq, document_number, source_date
    from {{ ref('int_federal_lien_links') }} where link_status = 'CONFIRMED'
    union all
    select 'dbpr_license', source_record_id, party_seq, document_number, source_date
    from {{ ref('int_dbpr_license_links') }} where link_status = 'CONFIRMED'
    union all
    select 'dbpr_discipline', source_record_id, party_seq, document_number, source_date
    from {{ ref('int_dbpr_discipline_links') }} where link_status = 'CONFIRMED'
    union all
    select 'duval', source_record_id, party_seq, document_number, source_date
    from {{ ref('int_duval_party_links') }} where link_status = 'CONFIRMED'
)

select
    l.link_source,                               -- which link model the bad row is in
    l.source_record_id,                          -- the source record
    l.document_number,                           -- the company it was confirmed against
    l.source_date,                               -- the record's date
    c.file_date as company_file_date             -- the company's filing date on Sunbiz
from confirmed as l
left join {{ ref('int_company_match_keys') }} as c   -- keep the link even if the company is missing
    on c.document_number = l.document_number
where l.source_date is null                      -- R2 could not be checked
   or c.file_date is null                        -- R2 could not be checked
   or l.source_date < c.file_date                -- the record is older than the company
