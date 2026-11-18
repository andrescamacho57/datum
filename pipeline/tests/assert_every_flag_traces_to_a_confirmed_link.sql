-- ---------------------------------------------------------------------------
-- assert_every_flag_traces_to_a_confirmed_link.sql: a SINGULAR test (returns
-- the BAD rows; zero rows = PASS).
--
-- The rule (spec A7, decision d19): flags attach only to CONFIRMED links.
-- Accusing the wrong company of a lien is the most expensive error Datum can
-- make, so an AMBIGUOUS or NO_MATCH link must never produce a flag.
--
-- How it checks: it rebuilds the list of CONFIRMED links from the four link
-- models and looks for any flag that has no partner in it. It also catches a
-- flag built from a lien that ruling R7 says to leave out.
-- ---------------------------------------------------------------------------

with confirmed_links as (
    -- Every CONFIRMED link, labelled with the flag type(s) it may produce.
    select 'federal_tax_lien' as flag_family, source_record_id, document_number
    from {{ ref('int_federal_lien_links') }} where link_status = 'CONFIRMED'
    union
    select 'dbpr_license_inactive', source_record_id, document_number
    from {{ ref('int_dbpr_license_links') }} where link_status = 'CONFIRMED'
    union
    select 'dbpr_discipline', source_record_id, document_number
    from {{ ref('int_dbpr_discipline_links') }} where link_status = 'CONFIRMED'
    union
    select 'duval', source_record_id, document_number
    from {{ ref('int_duval_party_links') }} where link_status = 'CONFIRMED'
    -- union (without "all") removes duplicates: a lien with two confirmed
    -- debtors for one company appears once.
),

flags as (
    select
        *,
        case when flag_type like 'duval_%' then 'duval' else flag_type end as flag_family
        -- The three Duval flag types all come from the one Duval link model.
    from {{ ref('company_flags') }}
)

select
    f.document_number,
    f.flag_type,
    f.source_record_id,
    case
        when c.document_number is null then 'no CONFIRMED link behind this flag'
        else 'flag built from a lien ruling R7 excludes'
    end as problem
from flags as f
left join confirmed_links as c                   -- keep every flag, matched or not
    on  c.flag_family = f.flag_family
    and c.source_record_id = f.source_record_id
    and c.document_number = f.document_number
left join {{ ref('int_federal_liens_status') }} as s
    on  f.flag_type = 'federal_tax_lien'
    and s.filing_doc_number = f.source_record_id
where c.document_number is null                  -- no CONFIRMED link
   or coalesce(s.is_unexplained, false)          -- or an R7 lien that should have been skipped
