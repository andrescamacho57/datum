-- ---------------------------------------------------------------------------
-- company_possible_matches.sql: the MART of possible matches. One row = one
-- record on the public record that MAY belong to a company, reached through
-- an AMBIGUOUS link, with the reason the link is not CONFIRMED.
--
-- What a possible match is (Phase C working rule W3): a record on an
-- AMBIGUOUS link that would be a SHOWN flag if the link were CONFIRMED.
-- Decision d19 says such a record shows as "possible match: verify" and is
-- never counted as a flag.
--
-- EVERY ROW HERE IS HIDDEN TODAY. Since d19, the linking rule has gained
-- reason codes (zip_differs, before_company_filed, no_entity_word and the
-- rest), and nobody has decided which reasons are safe to show. Showing a
-- record that predates the company, or one filed under a name with no
-- legal-entity word (which may be a person's name), could accuse the wrong
-- company or surface a person's record. So is_shown comes from the seed
-- possible_match_reasons, where every reason is false, and the test
-- assert_possible_matches_stay_hidden fails the build if any row here is not
-- false. Andres turns a reason on with a ruling.
--
-- Which records can be a possible match: only the two kinds of flag that are
-- shown today.
--   federal_tax_lien       a lien whose debtor is AMBIGUOUS for this company
--   dbpr_license_inactive  an inactive contractor license whose business name
--                          is AMBIGUOUS for this company
-- DBPR discipline and Duval records are hidden as flags (rulings R12 and
-- R20), so they would not be shown flags on a CONFIRMED link either, and
-- they produce no row here.
--
-- The same rules as company_flags, from the same place: both marts call the
-- macros in macros/flag_rules.sql. So a lien that ruling R7 leaves out of
-- the flags is left out here too, and the fact, the status note, the
-- citation and the caveat read the same in both tables.
--
-- A record that is already a flag is not also a possible match. A lien can
-- name two debtors: if one is CONFIRMED as a company and the other is
-- AMBIGUOUS for the same company, company_flags already holds that lien for
-- that company, and STEP 4 below drops it here.
--
-- A near-namesake is counted and not listed (open question Q27). When a
-- near-namesake turns a link AMBIGUOUS (ruling R30), the link model has a row
-- for the company with the record's own match key, and none for the
-- namesake. So the namesake gets no row here either.
--
-- No names: nothing here names a debtor, a license holder or a party.
--
-- Columns: those of company_flags, in the same order, plus link_reason.
-- Grain: one row per company per source record per flag type per link
-- reason. Two debtors on one lien can be AMBIGUOUS for the same company for
-- two different reasons, and each reason is kept, because each is decided
-- separately in the seed.
-- Becomes the table DATUM.DEV_MARTS.COMPANY_POSSIBLE_MATCHES.
-- ---------------------------------------------------------------------------

-- depends_on: {{ ref('search_page_sources') }}
-- This model does not READ that seed. The line above tells dbt the seed
-- belongs to this model's build, as it does in company_flags.


with manifest as (
    -- STEP 1: when each source file was fetched (ruling R23). The same
    -- SELECT company_flags uses.
    {{ fetch_manifest_rows() }}
),

lien_files_through as (
    -- STEP 2: the date of the newest federal lien file loaded. The same
    -- SELECT company_flags uses.
    {{ lien_files_through_rows() }}
),

federal_lien_possible_matches as (
    -- STEP 3a: the lien rule of company_flags, on AMBIGUOUS links.
    -- possible_match=true is the one switch the macro has (see its header).
    {{ federal_lien_flag_rows(possible_match=true) }}
),

license_possible_matches as (
    -- STEP 3b: the inactive-license rule of company_flags, on AMBIGUOUS links.
    {{ dbpr_license_flag_rows(possible_match=true) }}
),

stacked as (
    -- Stack the two kinds. Same columns, same order, in both blocks.
    select * from federal_lien_possible_matches
    union all
    select * from license_possible_matches
)

-- STEP 4: keep a possible match only when the same record is not already a
-- flag on the same company.
select p.*
from stacked as p
where not exists (
    select 1
    from {{ ref('company_flags') }} as f
    where f.document_number  = p.document_number
      and f.flag_type        = p.flag_type
      and f.source_record_id = p.source_record_id
)
-- not exists (subquery) is true when the subquery finds no row. The
-- subquery looks in company_flags for the same company, kind of flag and
-- record. `select 1` is a convention: only whether a row exists matters,
-- not what it holds.
