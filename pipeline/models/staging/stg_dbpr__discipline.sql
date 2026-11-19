-- ---------------------------------------------------------------------------
-- stg_dbpr__discipline.sql: the STAGING model for DBPR discipline against
-- licensed contractors.
--
-- What this model does: trims the raw text columns, turns blanks into NULLs
-- and date text into dates, and splits the one combined column
-- ("06/11/2026 - Fine") into a date and a description.
--
-- Grain (what one row is): one discipline line on one complaint. A complaint
-- that ended in a fine, costs and education appears as three rows with the
-- same complaint_number.
--
-- People: every respondent is an individual licensee (the name is always
-- "LAST, FIRST"). That is allowed in staging and must go no further. To
-- reach a business, Phase B has to go license number → the license row in
-- stg_dbpr__licenses → that row's dba_name.
--
-- Join caution: license_number here is NOT zero-padded (27000) while the
-- license file pads to 7 digits (0027000), and the kind of license is given
-- in words here (license_type) but as a code there (occupation_code).
--
-- Becomes the view DATUM.DEV_STAGING.STG_DBPR__DISCIPLINE.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table as it is (all five fiscal-year files).
    select * from {{ source('dbpr', 'dbpr_discipline') }}
),

cleaned as (
    -- STEP 2: trim, blank → NULL, text → date.
    select
        nullif(trim(license_type), '')                     as license_type,
        -- The kind of license in words, e.g. Certified General Contractor.

        nullif(trim(license_nbr), '')                      as license_number,
        -- Digits, not zero-padded. See "Join caution" above.

        nullif(trim(respondent_name), '')                  as respondent_name,
        -- The licensee the complaint is against. A person's name.

        nullif(trim(address_line_1), '')                   as address_line_1,
        -- A street address, or the words "Private Address".
        nullif(trim(address_line_2), '')                   as address_line_2,
        nullif(trim(address_line_3), '')                   as address_line_3,

        nullif(trim(city), '')                             as city,
        nullif(trim(state), '')                            as state,
        nullif(trim(zip_code), '')                         as zip,
        nullif(trim(county), '')                           as county,
        -- County NAME here (DUVAL); the license file has a number instead.

        nullif(trim(complaint_nbr), '')                    as complaint_number,
        -- DBPR's case number, e.g. 2025900001 (an invented number in the real shape). The citable record ID.

        nullif(trim(classification), '')                   as classification,
        -- Almost always "Licensed Activity".

        try_to_date(trim(entered_date), 'MM/DD/YYYY')      as entered_date,
        -- When DBPR entered the complaint.

        nullif(trim(disposition), '')                      as disposition,
        -- How the case ended, e.g. Final Order, Citation filed, Dismissed.

        try_to_date(trim(disposition_date), 'MM/DD/YYYY')  as disposition_date,
        -- When it ended. NULL when the state left it blank.

        try_to_date(left(trim(discipline_description), 10), 'MM/DD/YYYY') as discipline_date,
        -- The raw column looks like "06/11/2026 - Fine". left(x, 10) takes
        -- the first 10 characters, the date.

        nullif(trim(substr(trim(discipline_description), 14)), '') as discipline_action,
        -- The same column from character 14 on: what was imposed ("Fine",
        -- "COSTS", "Education"). 10 date characters + 3 for " - " = 13, so
        -- the words start at 14.

        nullif(trim(violation_code), '')                   as violation_code,
        -- Mostly blank.

        regexp_substr(source_file, '[0-9]{4}')             as fiscal_year_code,
        -- regexp_substr pulls out the first piece of text that fits a
        -- pattern: here four digits in a row. contractor_disc_lic_2526.csv.gz
        -- gives '2526' = the state's fiscal year July 2025 – June 2026.

        source_file,                                       -- provenance: the exact staged file
        loaded_at                                          -- provenance: when COPY loaded it

    from source
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from cleaned
