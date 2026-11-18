-- ---------------------------------------------------------------------------
-- assert_link_rows_are_consistent.sql: a SINGULAR test (returns the BAD
-- rows; zero rows = PASS).
--
-- Every link model promises the same shape. This test checks the promises on
-- all four at once:
--   1. A CONFIRMED row names a company and says what it matched on.
--   2. Only a CONFIRMED row has matched_on.
--   3. A NO_MATCH row names no company.
--   4. A source party never has the same company twice.
--   5. A CONFIRMED source party has exactly ONE row: once a record is
--      confirmed against a company, no other company is offered for it.
--   6. A Duval link is never matched on name_zip: the Clerk's index has no
--      address, so only the unique-name branch applies (ruling R3).
-- ---------------------------------------------------------------------------

with links as (
    -- All four link models stacked, labelled with their source.
    select 'federal_lien' as link_source, source_record_id, party_seq, document_number, link_status, matched_on
    from {{ ref('int_federal_lien_links') }}
    union all
    select 'dbpr_license', source_record_id, party_seq, document_number, link_status, matched_on
    from {{ ref('int_dbpr_license_links') }}
    union all
    select 'dbpr_discipline', source_record_id, party_seq, document_number, link_status, matched_on
    from {{ ref('int_dbpr_discipline_links') }}
    union all
    select 'duval', source_record_id, party_seq, document_number, link_status, matched_on
    from {{ ref('int_duval_party_links') }}
),

counted as (
    -- Add two counts to every row, computed per source party.
    select
        *,
        count(*) over (
            partition by link_source, source_record_id, party_seq
        ) as rows_for_party,
        -- how many rows this source party has in all
        count(*) over (
            partition by link_source, source_record_id, party_seq, document_number
        ) as rows_for_party_and_company
        -- how many of them name this same company (must be 1)
    from links
)

select
    link_source,
    source_record_id,
    party_seq,
    document_number,
    link_status,
    case                                         -- which promise the row breaks
        when link_status = 'CONFIRMED' and (document_number is null or matched_on is null) then '1 confirmed without company or matched_on'
        when link_status <> 'CONFIRMED' and matched_on is not null                         then '2 matched_on on a row that is not confirmed'
        when link_status = 'NO_MATCH' and document_number is not null                      then '3 no_match that names a company'
        when rows_for_party_and_company > 1                                                then '4 same company twice for one party'
        when link_status = 'CONFIRMED' and rows_for_party > 1                              then '5 confirmed party with more than one row'
        when link_source = 'duval' and matched_on = 'name_zip'                             then '6 duval matched on name_zip'
    end as broken_promise
from counted
where broken_promise is not null                 -- Snowflake lets WHERE use a column defined in the same SELECT
