-- ---------------------------------------------------------------------------
-- stg_dbpr__licenses.sql: the STAGING model for DBPR construction licensees.
--
-- DBPR = Florida Department of Business and Professional Regulation.
--
-- What this model does: the raw table already has one text column per field
-- (the file is comma-delimited, so Snowflake split it at load time). This
-- model trims the padding, turns blanks into NULLs, turns the date text into
-- real dates, and labels each row with the kind of record it is. No linking
-- to companies: that's Phase B.
--
-- Grain (what one row is): one record in the state's file. The file mixes
-- four kinds of record, told apart by occupation_code:
--   contractor licenses   (CGC, CBC, CCC ... 25 codes)  held by a PERSON; the
--                         person's company, if any, is in dba_name
--   QB                    "Construction Business Information": a BUSINESS.
--                         These rows carry NO license number in the file
--   FRO                   financially responsible officer: a person
--   PVDR, CRS1            education course providers and courses: not licenses
-- Code meanings: DBPR's "Understanding DBPR Codes" page (docs/access/dbpr.md).
--
-- People: licensee_name is a person's name on most rows. That is allowed in
-- staging and must go no further. Phase B may carry dba_name and QB rows only.
--
-- Not in this file: null-and-void, delinquent and involuntarily inactive
-- licenses (the state leaves them out).
--
-- Becomes the view DATUM.DEV_STAGING.STG_DBPR__LICENSES.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table as it is.
    select * from {{ source('dbpr', 'dbpr_licenses') }}
    -- select * is fine here: the next step names every column it uses.
),

cleaned as (
    -- STEP 2: trim, blank → NULL, text → date.
    -- nullif(trim(x), '') is the pattern on almost every line: trim removes
    -- padding spaces, then nullif turns an empty result into a true NULL, so
    -- "no value" never looks like data.
    select
        trim(board_number)                                 as board_number,
        -- Always '06': the Construction Industry Licensing Board.

        trim(occupation_code)                              as occupation_code,
        -- The kind of record, e.g. CGC = certified general contractor,
        -- QB = construction business information.

        case                                               -- case = SQL's if / else
            when trim(occupation_code) = 'QB'              then 'business'
            when trim(occupation_code) = 'FRO'             then 'financial_officer'
            when trim(occupation_code) in ('PVDR', 'CRS1') then 'education'
            else 'contractor_license'
        end                                                as record_kind,
        -- The four kinds from the header, as a readable label. This is the
        -- column that tells business records from individual-held licenses.
        -- A new, unknown code would fall into 'contractor_license', so the
        -- accepted_values test on occupation_code guards this.

        nullif(trim(licensee_name), '')                    as licensee_name,
        -- A person ("LAST, FIRST MIDDLE") on license rows; a business on QB rows.

        nullif(trim(dba_name), '')                         as dba_name,
        -- "Doing business as": on a contractor's row, usually the company.

        nullif(trim(class_code), '')                       as class_code,
        -- A sub-class of some licenses (e.g. A / B / C for air conditioning).

        nullif(trim(address_line_1), '')                   as address_line_1,
        nullif(trim(address_line_2), '')                   as address_line_2,
        nullif(trim(address_line_3), '')                   as address_line_3,
        -- The mailing address the licensee gave DBPR.

        nullif(trim(city), '')                             as city,
        nullif(trim(state), '')                            as state,

        nullif(trim(zip), '')                              as zip,
        -- As sent: 5 digits, ZIP+4 with a dash, or (15 rows) 9 digits.

        nullif(left(trim(zip), 5), '')                     as zip5,
        -- The first 5 characters: the 5-digit ZIP, for linking in Phase B.

        nullif(trim(county_code), '')                      as county_code,
        -- DBPR's own county number (e.g. 26 = Duval), not a FIPS code.

        nullif(trim(license_number), '')                   as license_number,
        -- Digits only, zero-padded, e.g. 0099990. NULL on every QB row: the
        -- state's file gives business records no number. Not unique on its
        -- own: the same digits are reused under different occupation codes,
        -- so the key is occupation_code + license_number.

        nullif(trim(alternate_license_number), '')         as alternate_license_number,
        -- The number as printed on a license, e.g. CBC099990. NULL on QB rows.

        trim(primary_status)                               as primary_status,
        -- C = current, P = probation, S = suspended.

        nullif(trim(secondary_status), '')                 as secondary_status,
        -- A = active, I = inactive, or NULL when the state left it blank.

        try_to_date(trim(original_licensure_date), 'MM/DD/YYYY') as original_licensure_date,
        -- The text 09/16/2024 becomes a real DATE. try_to_date returns NULL
        -- instead of failing when the text is blank or not a date.

        try_to_date(trim(effective_date), 'MM/DD/YYYY')    as effective_date,
        -- When the current license period started.

        try_to_date(trim(expiration_date), 'MM/DD/YYYY')   as expiration_date,
        -- When the license expires. NULL on QB rows.

        source_file,                                       -- provenance: the exact staged file
        loaded_at                                          -- provenance: when COPY loaded it
        -- Not carried: blank_field, renewal_period and trailing_field. They
        -- are empty on all 263,337 rows; they stay in raw.

    from source
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from cleaned
