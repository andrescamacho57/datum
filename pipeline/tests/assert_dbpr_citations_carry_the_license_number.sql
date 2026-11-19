-- ---------------------------------------------------------------------------
-- assert_dbpr_citations_carry_the_license_number.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule (ruling R27): a DBPR flag cites DBPR's "verify a license" search
-- page, and that page searches by LICENSE number. So every DBPR citation,
-- on a discipline flag as well as a license flag, must carry the license
-- number, or the reader cannot find the record. A complaint number alone
-- cannot be typed into the search.
--
-- How it checks, on every DBPR flag, shown or hidden:
--   1. The citation holds a license number ("license CGC1508861"), and that
--      number is a contractor license in DBPR's own file.
--   2. On a license flag, it is the flag's own record.
--   3. On a discipline flag, it is the license the complaint is against:
--      the same KIND of license and the same number, read again from
--      STAGING so this test does not trust the link model. The kind
--      matters because DBPR reuses the same digits under different kinds
--      (CGC0006231 and CBC0006231 are two licenses).
--
-- What it can't see: the discipline files name the kind in words, and the
-- seed dbpr_license_type_map turns the words into a code. This test uses
-- that seed too, so a wrong row in the seed would pass here. The seed is 19
-- lines, reviewed by hand, with its own tests (ruling R14).
-- ---------------------------------------------------------------------------

with dbpr_flags as (
    select
        document_number,
        flag_type,
        source_record_id,
        citation,
        regexp_substr(citation, 'license ([A-Z0-9]+)', 1, 1, 'e', 1) as cited_license
        -- regexp_substr with 'e' returns one bracketed group of the pattern:
        -- here the letters and digits right after the word "license".
        -- NULL when the citation has no such text.
    from {{ ref('company_flags') }}
    where source = 'dbpr'
),

licenses as (
    -- Every contractor license in DBPR's file: its printed number
    -- (CGC1508861), its kind as a code (CGC) and its 7-digit number (1508861).
    select distinct
        alternate_license_number,
        occupation_code,
        license_number
    from {{ ref('stg_dbpr__licenses') }}
    where record_kind = 'contractor_license'
),

complaint_licenses as (
    -- The license each complaint is against, as the discipline files give
    -- it: the kind in words, turned into a code by the seed, and the digits,
    -- padded here to 7 the way the license file writes them.
    select distinct
        d.complaint_number,
        m.occupation_code,
        case
            when length(d.license_number) < 7 then lpad(d.license_number, 7, '0')
            else d.license_number
        end as license_number
    from {{ ref('stg_dbpr__discipline') }} as d
    inner join {{ ref('dbpr_license_type_map') }} as m
        on m.license_type = d.license_type
    -- INNER JOIN: a kind the seed does not list has no row here, so a
    -- discipline flag built from it would fail check 3.
)

select
    f.document_number,
    f.flag_type,
    f.source_record_id,
    f.citation,
    case
        when l.alternate_license_number is null then '1 no license number from DBPR''s file in the citation'
        when f.flag_type = 'dbpr_license_inactive' then '2 the cited license is not the flag''s own record'
        else '3 the cited license is not the one the complaint is against'
    end as problem
from dbpr_flags as f
left join licenses as l
    on l.alternate_license_number = f.cited_license
left join complaint_licenses as c
    on  f.flag_type = 'dbpr_discipline'
    and c.complaint_number = f.source_record_id
    and c.occupation_code = l.occupation_code    -- the same kind of license
    and c.license_number = l.license_number      -- and the same number
where l.alternate_license_number is null
   or (f.flag_type = 'dbpr_license_inactive' and f.cited_license <> f.source_record_id)
   or (f.flag_type = 'dbpr_discipline' and c.complaint_number is null)
