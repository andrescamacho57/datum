-- ---------------------------------------------------------------------------
-- company_flags.sql: the MART of flags. One row = one fact on the public
-- record about a company, reached through a CONFIRMED link.
--
-- What a flag is: a FACT, never a conclusion (CLAUDE.md rule 2). "Federal tax
-- lien filed 2025-03-14, open" is a flag. "Doesn't pay its taxes" is not, and
-- nothing in this table says anything like it.
--
-- Where flags come from, and the rule for each:
--   federal_tax_lien       a lien whose debtor is CONFIRMED as this company
--                          (int_federal_lien_links), open or closed per
--                          int_federal_liens_status. Liens we can't explain
--                          are left out (ruling R7).
--   dbpr_license_inactive  a contractor license whose business name is
--                          CONFIRMED as this company and whose status in
--                          DBPR's file is inactive. An ACTIVE license is not a
--                          flag: it is good news, shown elsewhere.
--   dbpr_discipline        a DBPR complaint against such a license. BUILT,
--                          NOT DISPLAYED (ruling R12).
--   duval_lien, duval_tax_warrant, duval_judgment
--                          a Duval County recorded document naming this
--                          company on the debtor side (ruling R17). BUILT,
--                          NOT DISPLAYED (ruling R20).
--
-- AMBIGUOUS links produce no row here. They are "possible match: verify",
-- and the app reads them from the link models.
--
-- Not here: "inactive with the state" and "new company". Those come straight
-- from the company's own record (entity_lookup), not from a link.
--
-- Every row carries where the fact came from and when we fetched it
-- (CLAUDE.md rule 3): source, source_record_id, source_url, citation,
-- source_file and fetched_at. Tests fail the build if any is missing.
--
-- No names: nothing here names a debtor, a license holder or a party.
--
-- Grain: one row per company per source record per flag type.
-- Becomes the table DATUM.DEV_MARTS.COMPANY_FLAGS.
-- ---------------------------------------------------------------------------


with manifest as (
    -- When each source file was fetched (ruling R23). Joined below on the
    -- file each fact came from.
    select
        source,
        source_file,
        fetched_at_utc
    from {{ ref('stg_datum__fetch_manifest') }}
),

-- ===========================================================================
-- FEDERAL TAX LIENS
-- ===========================================================================

lien_files_through as (
    -- The date of the newest federal lien file loaded: "open" is only known
    -- up to this day. One row, one column.
    select max(published_on) as through_date
    from {{ ref('stg_sunbiz__flr_events') }}
),

federal_lien_flags as (
    select distinct
        l.document_number,
        'federal_tax_lien'                           as flag_type,
        s.filing_date                                as fact_date,
        -- The day the lien was filed with the Florida Department of State.

        s.lien_status                                as status,
        -- open or closed (ruling R6).

        nullif(array_to_string(array_construct_compact(
            case when s.released_on is not null
                 then 'Certificate of release filed ' || to_char(s.released_on, 'YYYY-MM-DD') || '.' end,
            case when s.discharge_recorded_on is not null
                 then 'Certificate of discharge recorded on ' || to_char(s.discharge_recorded_on, 'YYYY-MM-DD') || '.' end
        ), ' '), '')                                 as status_note,
        -- The events on the lien, as facts. array_construct_compact builds a
        -- list and drops the NULLs; array_to_string joins what is left with
        -- a space; nullif turns an empty result into NULL. A discharge is
        -- stated, not interpreted (ruling R6).

        'sunbiz_flr'                                 as source,
        s.filing_doc_number                          as source_record_id,
        '{{ var("sunbiz_lien_search_url") }}'        as source_url,
        -- No per-record link exists for a federal lien (ruling R9): this is
        -- the state's search page, and the filing number finds the record.
        'Florida Department of State federal lien filing ' || s.filing_doc_number as citation,
        s.filing_source_file                         as source_file,

        greatest(mf.fetched_at_utc, coalesce(mr.fetched_at_utc, mf.fetched_at_utc)) as fetched_at,
        -- The later of two fetch times: the file the lien came from and, if
        -- the lien is closed, the file its release came from. greatest
        -- returns NULL if either side is NULL, so coalesce gives it the
        -- first value again when there is no release.

        'Open or closed is read from the state''s federal lien files published through '
            || to_char(t.through_date, 'YYYY-MM-DD')
            || '. A release filed after that date is not reflected. The state''s files carry no dollar amount.' as caveat,
        -- Two single quotes inside a text value make one apostrophe.

        true                                         as is_shown
    from {{ ref('int_federal_lien_links') }} as l
    inner join {{ ref('int_federal_liens_status') }} as s
        on s.filing_doc_number = l.source_record_id
    cross join lien_files_through as t
    left join manifest as mf
        on mf.source = 'sunbiz_flr' and mf.source_file = s.filing_source_file
    left join manifest as mr
        on mr.source = 'sunbiz_flr' and mr.source_file = s.release_source_file
    where l.link_status = 'CONFIRMED'
      and not s.is_unexplained
      -- Ruling R7: a lien with a cancellation date, a status-C party row or
      -- an unexplained earlier release produces no flag.
    -- select distinct: a lien with two debtors that are both CONFIRMED as
    -- the same company is still ONE flag.
),

-- ===========================================================================
-- DBPR CONTRACTOR LICENSES
-- ===========================================================================

license_flags as (
    select distinct
        ll.document_number,
        'dbpr_license_inactive'                      as flag_type,
        lic.effective_date                           as fact_date,
        -- When the license's current period, and so its current status, began.

        'inactive'                                   as status,
        'License ' || lic.alternate_license_number || ': inactive'
            || coalesce(', expires ' || to_char(lic.expiration_date, 'YYYY-MM-DD'), '')
            || '.'                                   as status_note,
        -- License number, status and expiry: the business fact (ruling R11).
        -- Never the license holder's name.

        'dbpr'                                       as source,
        lic.alternate_license_number                 as source_record_id,
        '{{ var("dbpr_license_search_url") }}'       as source_url,
        'Florida DBPR license ' || lic.alternate_license_number as citation,
        lic.source_file,
        m.fetched_at_utc                             as fetched_at,
        'From DBPR''s construction licensee file, which leaves out delinquent, null-and-void and involuntarily inactive licenses. A license is held by a person who qualifies the business; this line is about the license, not the person.' as caveat,
        true                                         as is_shown
    from {{ ref('int_dbpr_license_links') }} as ll
    inner join {{ ref('stg_dbpr__licenses') }} as lic
        on  lic.alternate_license_number = ll.source_record_id
        and lic.record_kind = 'contractor_license'
    left join manifest as m
        on m.source = 'dbpr' and m.source_file = lic.source_file
    where ll.link_status = 'CONFIRMED'
      and lic.secondary_status = 'I'
      -- I = inactive in DBPR's file. A = active is not a flag. QB business
      -- records never reach here: the state gives them no active/inactive
      -- status that says "inactive".
),

-- ===========================================================================
-- DBPR DISCIPLINE (built, not displayed: ruling R12)
-- ===========================================================================

discipline_files_through as (
    -- The latest discipline date in DBPR's files: they run some months behind.
    select max(discipline_date) as through_date
    from {{ ref('stg_dbpr__discipline') }}
),

complaints as (
    -- One row per complaint, from the discipline lines in staging. No name
    -- column is read.
    select
        complaint_number,
        min(entered_date)                            as entered_date,
        max(disposition_date)                        as disposition_date,
        max(disposition)                             as disposition,
        -- How the case ended, in DBPR's words (Final Order, Dismissed ...).
        max(source_file)                             as source_file
    from {{ ref('stg_dbpr__discipline') }}
    group by complaint_number
),

discipline_flags as (
    select distinct
        dl.document_number,
        'dbpr_discipline'                            as flag_type,
        coalesce(c.disposition_date, c.entered_date) as fact_date,
        -- The day the case ended, or the day it was entered if it hasn't.

        case when c.disposition_date is not null then 'closed' else 'open' end as status,
        'Complaint ' || c.complaint_number || ' entered ' || to_char(c.entered_date, 'YYYY-MM-DD')
            || coalesce('; disposition: ' || c.disposition
                        || coalesce(' on ' || to_char(c.disposition_date, 'YYYY-MM-DD'), ''), '')
            || '.'                                   as status_note,

        'dbpr'                                       as source,
        c.complaint_number                           as source_record_id,
        '{{ var("dbpr_license_search_url") }}'       as source_url,
        'Florida DBPR complaint ' || c.complaint_number as citation,
        c.source_file,
        m.fetched_at_utc                             as fetched_at,
        'A discipline record is against the individual license holder, not the business. DBPR''s published discipline files run through '
            || to_char(t.through_date, 'YYYY-MM-DD') || '.' as caveat,

        {{ var("show_dbpr_discipline") }}            as is_shown
        -- FALSE unless the project variable is switched on (ruling R12).
    from {{ ref('int_dbpr_discipline_links') }} as dl
    inner join complaints as c
        on c.complaint_number = dl.source_record_id
    cross join discipline_files_through as t
    left join manifest as m
        on m.source = 'dbpr' and m.source_file = c.source_file
    where dl.link_status = 'CONFIRMED'
),

-- ===========================================================================
-- DUVAL COUNTY RECORDED DOCUMENTS (built, not displayed: ruling R20)
-- ===========================================================================

duval_flags as (
    select distinct
        pl.document_number,
        s.flag_type,
        -- duval_lien, duval_tax_warrant or duval_judgment, from the allowlist seed.

        s.recorded_date                              as fact_date,
        s.document_status                            as status,
        -- open or closed (ruling R18).

        nullif(array_to_string(array_construct_compact(
            case when s.document_status = 'closed'
                 then 'Closed by ' || s.closed_by_doc_type_code || ' instrument ' || s.closed_by_instrument_number
                      || coalesce(', recorded ' || to_char(s.closed_on, 'YYYY-MM-DD'), '') || '.' end,
            case when s.partial_release_count > 0
                 then 'Partial release recorded'
                      || coalesce(' on ' || to_char(s.last_partial_release_on, 'YYYY-MM-DD'), '') || '.' end
        ), ' '), '')                                 as status_note,
        -- A partial release is shown as an event and does not close the
        -- document (ruling R18).

        'duval'                                      as source,
        s.instrument_number                          as source_record_id,
        '{{ var("duval_official_records_url") }}'    as source_url,
        -- No per-record link exists (ruling R21): the Clerk's search page.
        'Duval County Official Records instrument ' || s.instrument_number
            || coalesce(', book ' || s.book || ' page ' || s.page, '') as citation,
        s.source_file,
        greatest(m.fetched_at_utc, coalesce(mc.fetched_at_utc, m.fetched_at_utc)) as fetched_at,
        -- The later of two fetch times: the file the document came from and,
        -- if it is closed, the file its release came from.

        'Pilot: from the Duval County Clerk''s recording index, files dated 2025-01-01 onward.'
            || case when s.recorded_before_window
                    then ' This document was recorded before 2025-01-01, so a release recorded before that date would not appear here.'
                    else '' end
            || ' Search the Clerk''s Official Records for a later release or satisfaction.' as caveat,

        {{ var("show_duval") }}                      as is_shown
        -- FALSE unless the project variable is switched on (ruling R20).
    from {{ ref('int_duval_party_links') }} as pl
    inner join {{ ref('int_duval_document_status') }} as s
        on s.instrument_number = pl.source_record_id
    left join manifest as m
        on m.source = 'duval' and m.source_file = s.source_file
    left join manifest as mc
        on mc.source = 'duval' and mc.source_file = s.closed_by_source_file
    where pl.link_status = 'CONFIRMED'
    -- select distinct: a document naming the same company twice is one flag.
)

-- ===========================================================================
-- Stack the four kinds. Same columns, same order, in every block.
-- ===========================================================================
select * from federal_lien_flags
union all
select * from license_flags
union all
select * from discipline_flags
union all
select * from duval_flags
