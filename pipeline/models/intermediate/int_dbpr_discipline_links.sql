-- ---------------------------------------------------------------------------
-- int_dbpr_discipline_links.sql: which company does each DBPR discipline
-- complaint reach, through the license it is against?
--
-- The path (ruling R12): discipline → license → company.
--   1. A discipline row names a license by its kind in WORDS and an unpadded
--      number ("Certified General Contractor", 27000).
--   2. The seed dbpr_license_type_map turns the words into the license
--      file's code (CGC); the number is padded to 7 digits (0027000).
--   3. That finds the license, and int_dbpr_license_links already says which
--      company the license's business name points at.
--
-- BUILT, NOT DISPLAYED (ruling R12): every discipline record is about an
-- individual license holder. The flags mart marks discipline is_shown =
-- false until counsel has reviewed it.
--
-- What is NOT in this model: a complaint whose license kind has no code, or
-- whose license is not in the state's file (it leaves out delinquent and
-- void licenses), or whose license names no business. Those are records
-- about a person with no business attached; they stay in staging. Counts are
-- in the leg report.
--
-- No names (ruling R4): the respondent's name never leaves staging.
--
-- Columns (the same in every link model):
--   source_record_id  DBPR's complaint number, e.g. 2025063352
--   party_seq         always 1
--   document_number   the company's Sunbiz document number; NULL on NO_MATCH
--   link_status       CONFIRMED / AMBIGUOUS / NO_MATCH
--   matched_on        name_zip or unique_name on a CONFIRMED row, else NULL
--   link_reason       why the row got its status
--   source_date       the date DBPR entered the complaint
--
-- Grain: one row per complaint per candidate company.
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_DBPR_DISCIPLINE_LINKS.
-- ---------------------------------------------------------------------------


with complaints as (
    -- STEP 1: one row per complaint. The staging model has one row per
    -- discipline LINE (a fine, costs, education ...); a complaint is against
    -- exactly one license (checked: 3,160 complaints, 3,160 pairs).
    select
        complaint_number,
        license_type,                                -- the kind of license, in words
        license_number,                              -- digits, NOT zero-padded
        min(entered_date)                            as entered_date
        -- The day DBPR entered the complaint: the earliest date on it, so
        -- ruling R2 is applied at its strictest.
    from {{ ref('stg_dbpr__discipline') }}
    group by complaint_number, license_type, license_number
),

licensed as (
    -- STEP 2: words → code (the seed), then the license itself.
    select
        c.complaint_number,
        c.entered_date,
        l.alternate_license_number                   -- the license's printed number: the key of int_dbpr_license_links
    from complaints as c
    inner join {{ ref('dbpr_license_type_map') }} as m
        on m.license_type = c.license_type
    -- INNER JOIN keeps only rows with a partner: a license kind the seed
    -- doesn't list drops out here.
    inner join {{ ref('stg_dbpr__licenses') }} as l
        on  l.occupation_code = m.occupation_code
        and l.license_number = case
                when length(c.license_number) < 7 then lpad(c.license_number, 7, '0')
                else c.license_number
            end
    -- lpad(x, 7, '0') pads x on the left with zeros up to 7 characters:
    -- 27000 → 0027000. It would also CUT a longer number down to 7, so the
    -- case only pads numbers that are too short.
    where l.record_kind = 'contractor_license'
),

linked as (
    -- STEP 3: the license's own link rows. A license with no business name
    -- has no rows in int_dbpr_license_links, so its complaints drop out here.
    select
        d.complaint_number                           as source_record_id,
        1                                            as party_seq,
        ll.document_number,
        ll.link_status                               as license_link_status,
        ll.matched_on                                as license_matched_on,
        ll.link_reason                               as license_link_reason,
        d.entered_date                               as source_date,
        k.file_date                                  as company_file_date
    from licensed as d
    inner join {{ ref('int_dbpr_license_links') }} as ll
        on ll.source_record_id = d.alternate_license_number
    left join {{ ref('int_company_match_keys') }} as k
        on k.document_number = ll.document_number
    -- The company's filing date, to re-apply ruling R2 with the COMPLAINT's
    -- date. LEFT JOIN because a NO_MATCH row has no company.
),

decided as (
    -- STEP 4: the complaint inherits the license's link, with ruling R2
    -- checked again: a complaint entered before the company existed can't be
    -- CONFIRMED against it, even when the license (dated later) is.
    select
        source_record_id,
        party_seq,
        document_number,
        source_date,
        case
            when license_link_status <> 'CONFIRMED'                 then license_link_status
            when source_date is null or company_file_date is null   then 'AMBIGUOUS'
            when source_date < company_file_date                    then 'AMBIGUOUS'
            else 'CONFIRMED'
        end                                          as link_status,
        case
            when license_link_status <> 'CONFIRMED'                 then license_link_reason
            when source_date is null or company_file_date is null   then 'date_unknown'
            when source_date < company_file_date                    then 'before_company_filed'
            else license_link_reason
        end                                          as link_reason
    from linked
)

select
    source_record_id,
    party_seq,
    document_number,
    link_status,
    case when link_status = 'CONFIRMED' then link_reason end as matched_on,
    -- name_zip or unique_name: how the LICENSE was matched to the company.
    link_reason,
    source_date
from decided
