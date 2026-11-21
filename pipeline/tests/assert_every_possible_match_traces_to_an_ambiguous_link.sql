-- ---------------------------------------------------------------------------
-- assert_every_possible_match_traces_to_an_ambiguous_link.sql: a SINGULAR
-- test (returns the BAD rows; zero rows = PASS).
--
-- The rule (Phase C working rule W3): a possible match is a record on an
-- AMBIGUOUS link that would be a shown flag if the link were CONFIRMED.
-- This test checks the four ways a row could break that sentence:
--   1. no AMBIGUOUS link with this reason stands behind the row. A NO_MATCH
--      link has no company, and a CONFIRMED link is a flag, not a possible
--      match
--   2. the row is built from a lien that ruling R7 leaves out of the flags
--   3. the row is built from a license that is not an inactive contractor
--      license, which would not be a flag either
--   4. the same record is already a flag on the same company
--
-- How it checks: it rebuilds the list of AMBIGUOUS links from the two link
-- models, straight from the tables and not through the macros the mart uses,
-- and looks for any row with no partner in it.
-- ---------------------------------------------------------------------------

with ambiguous_links as (
    -- Every AMBIGUOUS link of the two sources that can produce a possible
    -- match, with its reason. union (without "all") removes duplicates.
    select 'federal_tax_lien' as flag_type, source_record_id, document_number, link_reason
    from {{ ref('int_federal_lien_links') }} where link_status = 'AMBIGUOUS'
    union
    select 'dbpr_license_inactive', source_record_id, document_number, link_reason
    from {{ ref('int_dbpr_license_links') }} where link_status = 'AMBIGUOUS'
),

inactive_licenses as (
    -- The contractor licenses DBPR's file marks inactive: the only licenses
    -- that are a flag.
    select distinct alternate_license_number
    from {{ ref('stg_dbpr__licenses') }}
    where record_kind = 'contractor_license'
      and secondary_status = 'I'
)

select
    p.document_number,
    p.flag_type,
    p.source_record_id,
    p.link_reason,
    case
        when p.flag_type not in ('federal_tax_lien', 'dbpr_license_inactive')
                                              then 'a kind of record that is not a shown flag'
        -- This branch comes first on purpose. A row of any other kind has no
        -- partner among the AMBIGUOUS links either, so the next branch would
        -- claim it and name the wrong problem.
        when a.document_number is null        then 'no AMBIGUOUS link with this reason behind this row'
        when coalesce(s.is_unexplained, false) then 'built from a lien ruling R7 excludes'
        when p.flag_type = 'dbpr_license_inactive' and i.alternate_license_number is null
                                              then 'built from a license that is not an inactive contractor license'
        else 'the same record is already a flag on this company'
    end as problem
from {{ ref('company_possible_matches') }} as p
left join ambiguous_links as a                   -- keep every possible match, matched or not
    on  a.flag_type        = p.flag_type
    and a.source_record_id = p.source_record_id
    and a.document_number  = p.document_number
    and a.link_reason      = p.link_reason
left join {{ ref('int_federal_liens_status') }} as s
    on  p.flag_type = 'federal_tax_lien'
    and s.filing_doc_number = p.source_record_id
left join inactive_licenses as i
    on  p.flag_type = 'dbpr_license_inactive'
    and i.alternate_license_number = p.source_record_id
left join {{ ref('company_flags') }} as f
    on  f.document_number  = p.document_number
    and f.flag_type        = p.flag_type
    and f.source_record_id = p.source_record_id
where a.document_number is null                                                  -- 1
   or coalesce(s.is_unexplained, false)                                          -- 2
   or (p.flag_type = 'dbpr_license_inactive' and i.alternate_license_number is null)   -- 3
   or p.flag_type not in ('federal_tax_lien', 'dbpr_license_inactive')           -- 3, for a kind nobody planned
   or f.document_number is not null                                              -- 4
