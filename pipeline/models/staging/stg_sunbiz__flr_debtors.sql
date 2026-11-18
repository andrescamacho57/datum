-- ---------------------------------------------------------------------------
-- stg_sunbiz__flr_debtors.sql: the STAGING model for federal tax lien DEBTORS.
--
-- What this model does: each raw row is one 206-character line naming one
-- debtor (the party that owes the tax) on one lien. This model cuts the line
-- into named columns by character position.
--
-- Businesses only: the file marks each name C (corporate) or P (personal).
-- This model keeps ONLY the C rows. Datum reports on businesses, never on
-- individuals (CLAUDE.md rule 2), so a person's name stops at raw.
--
-- Grain: one corporate debtor on one lien, as it appeared in one state file.
-- A lien can have several debtors (debtor_seq tells them apart).
--
-- Positions: docs/access/sunbiz_flr.md. Secured parties use the same layout
-- (stg_sunbiz__flr_secured).
--
-- Becomes the view DATUM.DEV_STAGING.STG_SUNBIZ__FLR_DEBTORS.
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
            else 'quarterly'                         -- otherwise it's the snapshot, FLRD.TXT.gz
        end as source_kind,

        case
            when regexp_like(source_file, '[0-9]{8}flr.*')
                then try_to_date(left(source_file, 8), 'YYYYMMDD')  -- daily: the date is in the name
            else '2026-10-03'::date                  -- quarterly: snapshot date from `unzip -l` (REVISIT in January 2027)
        end as published_on
    from {{ source('sunbiz', 'sunbiz_flr_debtors') }}
),

parsed as (
    -- STEP 2: cut each line into columns with substr(line, start, length).
    select
        substr(line, 1, 1)                               as filing_type,
        -- Character 1: F = federal lien.

        trim(substr(line, 2, 12))                        as filing_doc_number,
        -- Characters 2–13: the lien this debtor belongs to. Joins to
        -- stg_sunbiz__flr_filings.filing_doc_number.

        trim(substr(line, 14, 55))                       as debtor_name,
        -- Characters 14–68: the debtor's name as the IRS wrote it.

        substr(line, 69, 1)                              as name_format,
        -- Character 69: C = corporate, P = personal. Filtered to C below.

        nullif(trim(substr(line, 70, 44)), '')           as address_1,
        -- Characters 70–113: first address line. nullif(x, '') makes a blank a true NULL.

        nullif(trim(substr(line, 114, 44)), '')          as address_2,
        -- Characters 114–157: second address line, usually blank.

        nullif(trim(substr(line, 158, 28)), '')          as city,
        -- Characters 158–185: city.

        nullif(trim(substr(line, 186, 2)), '')           as state,
        -- Characters 186–187: two-letter state code.

        nullif(trim(substr(line, 188, 9)), '')           as zip,
        -- Characters 188–196: ZIP+4 with no dash, e.g. 322561234.

        nullif(trim(substr(line, 188, 5)), '')           as zip5,
        -- The first 5 characters of the same field: the 5-digit ZIP. Phase B
        -- links a debtor to a company on name + zip5 (decision d19), so it
        -- gets its own column here.

        nullif(trim(substr(line, 197, 2)), '')           as country,
        -- Characters 197–198: country code.

        try_to_number(substr(line, 199, 5))              as debtor_seq,
        -- Characters 199–203: this debtor's sequence number within the lien
        -- (1 for the first debtor, 2 for the second...).

        nullif(trim(substr(line, 204, 1)), '')           as relation_to_filing,
        -- Character 204: C = currently on the lien.

        nullif(trim(substr(line, 205, 1)), '')           as original_party,
        -- Character 205: marks a debtor named on the original filing.

        substr(line, 206, 1)                             as filing_status,
        -- Character 206: the lien's status repeated on the debtor row
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

-- STEP 3: keep corporate debtors only.
select * from parsed
where name_format = 'C'
-- C = corporate. Rows marked P (personal) stay in raw and go no further.
-- On the 2026-10-03 snapshot that drops 2 of 22,173 rows.
