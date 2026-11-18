-- ---------------------------------------------------------------------------
-- stg_sunbiz__flr_filings.sql: the STAGING model for federal tax lien FILINGS.
--
-- What this model does: each raw row is one 82-character line describing one
-- lien filed with the Florida Department of State (almost always by the IRS).
-- This model cuts the line into named columns by character position and turns
-- the date and number fields into real dates and numbers. No business logic:
-- it doesn't decide whether a lien is still open and doesn't link it to a
-- company. That's the intermediate layer's job (Phase B).
--
-- Grain (what one row is): one lien, as it appeared in one state file. The
-- same lien can appear in the quarterly snapshot AND in a daily file, so
-- filing_doc_number is unique per source_file, not across the whole model.
--
-- Where the positions come from: the state's "Federal Tax Lien File
-- Definitions", recorded in docs/access/sunbiz_flr.md and confirmed on the
-- real files on 2026-11-05 and again before loading on 2026-11-12.
--
-- Becomes the view DATUM.DEV_STAGING.STG_SUNBIZ__FLR_FILINGS.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and label each row with the kind of state
    -- file it came from and the date the state published that file.
    select
        line,                                        -- the full 82-character line from the state file
        source_file,                                 -- which staged file the line came from (provenance)
        loaded_at,                                   -- when COPY loaded it (provenance)

        case                                         -- case = SQL's if / else
            when regexp_like(source_file, '[0-9]{8}flr.*') then 'daily'
            -- regexp_like(text, pattern) is TRUE when the WHOLE text fits the
            -- pattern. [0-9]{8} = exactly eight digits, then "flr", then
            -- .* = anything. Daily files are named 20261104flrf.txt.gz.
            else 'quarterly'                         -- everything else is the snapshot, FLRF.TXT.gz
        end as source_kind,

        case
            when regexp_like(source_file, '[0-9]{8}flr.*')
                then try_to_date(left(source_file, 8), 'YYYYMMDD')
                -- Daily: the first 8 characters of the name are the date.
            else '2026-10-03'::date
            -- Quarterly: the name carries no date, so it's written here. It
            -- comes from the file timestamps inside the state's zip
            -- (`unzip -l`, all 2026-10-03; docs/access/sunbiz_flr.md).
            -- REVISIT when the January 2027 snapshot arrives, the same
            -- limit stg_sunbiz__cor has: one hardcoded date can't describe
            -- two snapshots.
        end as published_on
    from {{ source('sunbiz', 'sunbiz_flr_filings') }}
    -- One raw table holds both kinds of file (script 13), so there is no
    -- union here, unlike stg_sunbiz__cor.
),

parsed as (
    -- STEP 2: cut each line into columns with substr(line, start, length).
    select
        trim(substr(line, 1, 12))                        as filing_doc_number,
        -- Characters 1–12: the lien's document number, e.g. 26FLR0004110.
        -- Debtors, secured parties and events all point back to it.

        try_to_date(substr(line, 13, 8), 'MMDDYYYY')     as filing_date,
        -- Characters 13–20: the date the lien was filed with the state.
        -- try_to_date returns NULL instead of failing when the text isn't a date.

        try_to_number(substr(line, 21, 5))               as pages,
        -- Characters 21–25: pages in this filing, zero-padded ("00001").
        -- try_to_number turns the text into a number, or NULL if it can't.

        try_to_number(substr(line, 26, 5))               as total_pages,
        -- Characters 26–30: pages across the filing and its later events.

        substr(line, 31, 1)                              as filing_status,
        -- Character 31: A = active, L = lapsed, T = terminated.

        substr(line, 32, 1)                              as filing_type,
        -- Character 32: F = federal lien. (U = UCC lien, not in this feed.)

        try_to_date(substr(line, 33, 8), 'MMDDYYYY')     as assessment_date,
        -- Characters 33–40: the date the IRS assessed the tax.
        -- A few rows carry mistyped years (8200, 9201): they still parse as
        -- dates, so a warn-level test checks the year range.

        try_to_date(substr(line, 41, 8), 'MMDDYYYY')     as cancellation_date,
        -- Characters 41–48: "00000000" when the lien isn't cancelled. That
        -- isn't a date, so try_to_date gives NULL, which is what we want.

        try_to_date(substr(line, 49, 8), 'MMDDYYYY')     as expiration_date,
        -- Characters 49–56: when the lien lapses, about 10 years and 30 days
        -- after the assessment date.

        nullif(trim(substr(line, 57, 1)), '')            as transmitting_utility,
        -- Character 57: Y/N flag, blank on most rows. nullif(x, '') turns a
        -- blank into a true NULL.

        try_to_number(substr(line, 58, 5))               as event_count,
        -- Characters 58–62: how many events (releases, amendments) are on this lien.

        try_to_number(substr(line, 63, 5))               as total_debtor_count,
        -- Characters 63–67: debtors ever named on the lien.

        try_to_number(substr(line, 68, 5))               as total_secured_count,
        -- Characters 68–72: secured parties (creditors) ever named.

        try_to_number(substr(line, 73, 5))               as current_debtor_count,
        -- Characters 73–77: debtors currently on the lien.

        try_to_number(substr(line, 78, 5))               as current_secured_count,
        -- Characters 78–82: secured parties currently on the lien.

        length(line) = 82                                as is_well_formed,
        -- TRUE when the line is exactly the documented length. A damaged
        -- line is flagged, not deleted, so the problem stays visible.

        source_kind,                                 -- 'quarterly' or 'daily'
        published_on,                                -- the date the state published the file
        source_file,                                 -- provenance: the exact file
        loaded_at                                    -- provenance: when we loaded it

    from source
    -- Read from STEP 1 above.

    where trim(line) <> ''
    -- Skip completely blank lines. <> means "not equal to".
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from parsed
