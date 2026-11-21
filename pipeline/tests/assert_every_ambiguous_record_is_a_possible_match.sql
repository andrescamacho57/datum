-- ---------------------------------------------------------------------------
-- assert_every_ambiguous_record_is_a_possible_match.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule (Phase C working rule W3): EVERY record on an AMBIGUOUS link that
-- would be a shown flag if the link were CONFIRMED is a possible match.
--
-- Why this test exists: its sister, assert_every_possible_match_traces_to_an_
-- ambiguous_link, looks at each row that IS in the mart and asks whether it
-- belongs there. It cannot see a row that is missing. If the mart read the
-- wrong links, or its last step dropped too much, the mart would be short or
-- empty, and a test that only inspects the rows present would find nothing
-- wrong. The review of leg C1 found that gap. Once a reason is switched on, a
-- missing row is a missing "possible match: verify" line on a report.
--
-- How it checks: it builds the list of records that SHOULD be in the mart,
-- straight from the link models and not through the macros the mart uses,
-- and returns every one that has no row there. The one thing it shares with
-- the mart is company_flags, which both read to leave out a record that is
-- already a flag. company_flags has its own test for holding only CONFIRMED
-- links (assert_every_flag_traces_to_a_confirmed_link).
--   liens      an AMBIGUOUS link whose lien is not one that ruling R7 leaves out
--   licenses   an AMBIGUOUS link whose license is an inactive contractor license
--   neither    when the same record is already a flag on the same company
-- ---------------------------------------------------------------------------

with expected as (
    -- Federal tax liens: one row per company, lien and reason.
    select distinct
        l.document_number,
        'federal_tax_lien'                           as flag_type,
        l.source_record_id,
        l.link_reason
    from {{ ref('int_federal_lien_links') }} as l
    inner join {{ ref('int_federal_liens_status') }} as s
        on s.filing_doc_number = l.source_record_id
    where l.link_status = 'AMBIGUOUS'
      and not s.is_unexplained                       -- ruling R7

    union all

    -- Inactive contractor licenses: one row per company, license and reason.
    select distinct
        ll.document_number,
        'dbpr_license_inactive',
        ll.source_record_id,
        ll.link_reason
    from {{ ref('int_dbpr_license_links') }} as ll
    inner join {{ ref('stg_dbpr__licenses') }} as lic
        on  lic.alternate_license_number = ll.source_record_id
        and lic.record_kind = 'contractor_license'
    where ll.link_status = 'AMBIGUOUS'
      and lic.secondary_status = 'I'                 -- I = inactive in DBPR's file
)

select
    e.document_number,
    e.flag_type,
    e.source_record_id,
    e.link_reason                                -- the possible match that is missing from the mart
from expected as e
left join {{ ref('company_flags') }} as f        -- is the record already a flag on this company?
    on  f.document_number  = e.document_number
    and f.flag_type        = e.flag_type
    and f.source_record_id = e.source_record_id
left join {{ ref('company_possible_matches') }} as p   -- is it in the mart?
    on  p.document_number  = e.document_number
    and p.flag_type        = e.flag_type
    and p.source_record_id = e.source_record_id
    and p.link_reason      = e.link_reason
where f.document_number is null                  -- not already a flag, so it should be a possible match ...
  and p.document_number is null                  -- ... and the mart has no row for it
