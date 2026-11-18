-- ---------------------------------------------------------------------------
-- stg_sunbiz__flr_secured.sql: the STAGING model for federal tax lien SECURED
-- PARTIES.
--
-- What a secured party is: the creditor that holds the lien. On federal tax
-- liens that is nearly always the IRS ("IRS JACKSONVILLE" on 20,385 of 20,448
-- snapshot rows); the rest are pension plans and one other federal bureau.
--
-- What this model does: each raw row is one 206-character line naming one
-- secured party on one lien. The layout is identical to the debtors file, so
-- the cuts below are the same as stg_sunbiz__flr_debtors with different
-- column names.
--
-- Grain: one secured party on one lien, as it appeared in one state file.
--
-- Not filtered by name_format: the brief filters debtors only. Staging may
-- hold every row; nothing past staging may carry a person's name, so Phase B
-- must apply name_format = 'C' before using secured_name.
--
-- Positions: docs/access/sunbiz_flr.md.
-- Becomes the view DATUM.DEV_STAGING.STG_SUNBIZ__FLR_SECURED.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and label each row with its file kind and
    -- the state's publish date (same logic as stg_sunbiz__flr_filings).
    select
        line,                                        -- the full 206-character line from the state file
        source_file,                                 -- which staged file the line came from (provenance)
        loaded_at,                                   -- when COPY loaded it (provenance)

        case                                         -- if the file name starts with 8 digits + "flr" it's a daily file
            when regexp_like(source_file, '[0-9]{8}flr.*') then 'daily'
            else 'quarterly'                         -- otherwise it's the snapshot, FLRS.TXT.gz
        end as source_kind,

        case
            when regexp_like(source_file, '[0-9]{8}flr.*')
                then try_to_date(left(source_file, 8), 'YYYYMMDD')  -- daily: the date is in the name
            else '2026-10-03'::date                  -- quarterly: snapshot date from `unzip -l` (REVISIT in January 2027)
        end as published_on
    from {{ source('sunbiz', 'sunbiz_flr_secured') }}
),

parsed as (
    -- STEP 2: cut each line into columns with substr(line, start, length).
    select
        substr(line, 1, 1)                               as filing_type,
        -- Character 1: F = federal lien.

        trim(substr(line, 2, 12))                        as filing_doc_number,
        -- Characters 2–13: the lien this secured party belongs to. Joins to
        -- stg_sunbiz__flr_filings.filing_doc_number.

        trim(substr(line, 14, 55))                       as secured_name,
        -- Characters 14–68: the creditor's name, e.g. IRS JACKSONVILLE.

        substr(line, 69, 1)                              as name_format,
        -- Character 69: C = corporate, P = personal.

        nullif(trim(substr(line, 70, 44)), '')           as address_1,
        -- Characters 70–113: first address line. nullif(x, '') makes a blank a true NULL.

        nullif(trim(substr(line, 114, 44)), '')          as address_2,
        -- Characters 114–157: second address line.

        nullif(trim(substr(line, 158, 28)), '')          as city,
        -- Characters 158–185: city.

        nullif(trim(substr(line, 186, 2)), '')           as state,
        -- Characters 186–187: two-letter state code.

        nullif(trim(substr(line, 188, 9)), '')           as zip,
        -- Characters 188–196: ZIP+4 with no dash.

        nullif(trim(substr(line, 188, 5)), '')           as zip5,
        -- The first 5 characters of the same field: the 5-digit ZIP.

        nullif(trim(substr(line, 197, 2)), '')           as country,
        -- Characters 197–198: country code.

        try_to_number(substr(line, 199, 5))              as secured_seq,
        -- Characters 199–203: this party's sequence number within the lien.

        nullif(trim(substr(line, 204, 1)), '')           as relation_to_filing,
        -- Character 204: C = currently on the lien.

        nullif(trim(substr(line, 205, 1)), '')           as original_party,
        -- Character 205: marks a party named on the original filing.

        substr(line, 206, 1)                             as filing_status,
        -- Character 206: the lien's status repeated on this row
        -- (A active, L lapsed, T terminated).

        length(line) = 206                               as is_well_formed,
        -- TRUE when the line is exactly the documented length.

        source_kind,                                 -- 'quarterly' or 'daily'
        published_on,                                -- the date the state published the file
        source_file,                                 -- provenance: the exact file
        loaded_at                                    -- provenance: when we loaded it

    from source
    -- Read from STEP 1 above.

    where trim(line) <> ''
    -- Skip completely blank lines.
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from parsed
