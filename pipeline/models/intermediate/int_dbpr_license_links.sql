-- ---------------------------------------------------------------------------
-- int_dbpr_license_links.sql: which company does each DBPR construction
-- license point at?
--
-- DBPR = Florida Department of Business and Professional Regulation.
--
-- How a license reaches a company (ruling R11): in Florida a PERSON holds the
-- license that qualifies a business. The license row names that business in
-- dba_name ("doing business as"). So the link is: the license's business
-- name → the company with the same match key, by rulings R1 and R2.
--
-- Two kinds of record are linked:
--   contractor licenses   through dba_name. A license with no dba_name is an
--                         individual's record with no business on it: it
--                         stays in staging and is not in this model.
--   QB business records   through their own name (ruling R13). The state
--                         gives them no license number, so their identifier
--                         here is a checksum of the row (see STEP 2).
-- Not linked: financial officers (FRO) and education records (PVDR, CRS1).
--
-- No names (ruling R4): neither the license holder's name nor the business
-- name is written to this table.
--
-- Columns (the same in every link model):
--   source_record_id  the license number as printed, e.g. CGC1512345; or
--                     QB- followed by 32 characters for a QB business record
--   party_seq         always 1: a license row names one business
--   document_number   the company's Sunbiz document number; NULL on NO_MATCH
--   link_status       CONFIRMED / AMBIGUOUS / NO_MATCH
--   matched_on        name_zip or unique_name on a CONFIRMED row, else NULL
--   link_reason       why the row got its status
--   source_date       the license's effective date: when its current period
--                     began. Ruling R2 compares it with the company's filing
--                     date.
--
-- Grain: one row per license (or QB record) per candidate company.
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_DBPR_LICENSE_LINKS.
-- ---------------------------------------------------------------------------


with contractor_licenses as (
    -- STEP 1: individual-held contractor licenses that name a business.
    select
        alternate_license_number                     as source_record_id,
        -- The number as printed on the license (unique across the 111,400
        -- contractor licenses), which is what DBPR's own search takes.
        1                                            as party_seq,
        {{ name_key('dba_name') }}                   as source_name_key,
        -- The BUSINESS name, simplified. Never the license holder's name.
        zip5                                         as source_zip5,
        effective_date                               as source_date
    from {{ ref('stg_dbpr__licenses') }}
    where record_kind = 'contractor_license'
      and dba_name is not null
),

business_records as (
    -- STEP 2: QB "Construction Business Information" records.
    select distinct
        'QB-' || md5(
            coalesce(licensee_name, '')            || '|' ||
            coalesce(dba_name, '')                 || '|' ||
            coalesce(address_line_1, '')           || '|' ||
            coalesce(city, '')                     || '|' ||
            coalesce(zip, '')                      || '|' ||
            coalesce(to_char(original_licensure_date), '') || '|' ||
            coalesce(to_char(effective_date), '')  || '|' ||
            coalesce(primary_status, '')           || '|' ||
            coalesce(secondary_status, '')
        )                                            as source_record_id,
        -- The state's file gives a QB row no number, so the identifier is
        -- built from the row itself. md5(text) returns a 32-character
        -- checksum: the same row always gives the same value, and the value
        -- can't be read back into the name. || joins pieces of text, and
        -- coalesce(x, '') swaps a NULL for an empty string, because joining
        -- text with a NULL would make the whole result NULL.
        1                                            as party_seq,
        {{ name_key('licensee_name') }}              as source_name_key,
        -- On a QB row the licensee name IS the business.
        zip5                                         as source_zip5,
        effective_date                               as source_date
    from {{ ref('stg_dbpr__licenses') }}
    where record_kind = 'business'
    -- select distinct: the state's file repeats 7 QB rows exactly; identical
    -- rows give identical checksums and collapse into one.
),

source_names as (
    -- STEP 3: stack the two kinds. Same five columns, same order.
    select * from contractor_licenses
    union all
    select * from business_records
),

-- STEP 4: apply rulings R1 and R2. `true` = this source has a ZIP code.
{{ link_to_companies('source_names', true) }}
