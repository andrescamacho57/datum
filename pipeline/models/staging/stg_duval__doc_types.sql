-- ---------------------------------------------------------------------------
-- stg_duval__doc_types.sql: the STAGING model for the Clerk's document-type
-- lookup.
--
-- What it is: a small table the Clerk ships every day that says which FAMILY
-- each document type code belongs to. Many codes share a family: MTG, MTGCU
-- and MTGTF are all mortgages. Counting "liens" or "judgments" means counting
-- by family, so the codes don't have to be listed by hand.
--
-- What this model does: drops the EOF trailer rows, trims the text and turns
-- a blank family into NULL (a few codes have none).
--
-- Grain: one type code per daily file. The same lookup is repeated in every
-- day's file, so a query that wants one row per code should take the latest
-- file_date.
--
-- Becomes the view DATUM.DEV_STAGING.STG_DUVAL__DOC_TYPES.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and drop each file's trailer row.
    select * from {{ source('duval', 'duval_doc_types') }}
    where doc_type_code <> 'EOF'
    -- The trailer line EOF|<row count> lands with 'EOF' in the first column.
),

cleaned as (
    -- STEP 2: trim and blank → NULL.
    select
        trim(doc_type_code)                                as doc_type_code,
        -- The code as it appears on documents, e.g. LN, N/C, RELEASE.

        nullif(trim(doc_type_family), '')                  as doc_type_family,
        -- The family the code belongs to, e.g. MTG. NULL when the Clerk's
        -- file gives the code no family.

        try_to_date(substr(source_file, 2, 8), 'YYYYMMDD') as file_date,
        -- The date in the file's name (m2025010301d.16.gz → characters 2–9).

        source_file,                                       -- provenance: the exact staged file
        loaded_at                                          -- provenance: when COPY loaded it

    from source
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from cleaned
