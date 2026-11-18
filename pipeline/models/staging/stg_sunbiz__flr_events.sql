-- ---------------------------------------------------------------------------
-- stg_sunbiz__flr_events.sql: the STAGING model for federal tax lien EVENTS.
--
-- What an event is: anything filed against a lien after the lien itself, such
-- as a certificate of release (the IRS says the debt is settled), a discharge,
-- an amendment or a refiling. This is how a lien stops being active between
-- quarterly snapshots.
--
-- What this model does: each raw row is one 135-character line describing one
-- action on one lien. This model cuts the line into named columns by character
-- position. It does NOT decide whether the lien is still open: that rule
-- (snapshot + daily filings − later releases) belongs to Phase B.
--
-- Grain: one action of one event on one lien, as it appeared in one state
-- file. The events file carries no names, only document numbers and codes.
--
-- Positions: docs/access/sunbiz_flr.md.
-- Becomes the view DATUM.DEV_STAGING.STG_SUNBIZ__FLR_EVENTS.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and label each row with its file kind and
    -- the state's publish date (same logic as stg_sunbiz__flr_filings).
    select
        line,                                        -- the full 135-character line from the state file
        source_file,                                 -- which staged file the line came from (provenance)
        loaded_at,                                   -- when COPY loaded it (provenance)

        case                                         -- if the file name starts with 8 digits + "flr" it's a daily file
            when regexp_like(source_file, '[0-9]{8}flr.*') then 'daily'
            else 'quarterly'                         -- otherwise it's the snapshot, FLRE.TXT.gz
        end as source_kind,

        case
            when regexp_like(source_file, '[0-9]{8}flr.*')
                then try_to_date(left(source_file, 8), 'YYYYMMDD')  -- daily: the date is in the name
            else '2026-10-03'::date                  -- quarterly: snapshot date from `unzip -l` (REVISIT in January 2027)
        end as published_on
    from {{ source('sunbiz', 'sunbiz_flr_events') }}
),

parsed as (
    -- STEP 2: cut each line into columns with substr(line, start, length).
    -- Position 1 and positions 45–46 are the state's internal index keys;
    -- they mean nothing outside its system, so they aren't given columns.
    -- They are still in raw if ever needed.
    select
        trim(substr(line, 2, 12))                        as event_doc_number,
        -- Characters 2–13: the event's OWN document number, e.g. 26FLR0004150.

        trim(substr(line, 14, 12))                       as filing_doc_number,
        -- Characters 14–25: the lien this event acts on. Joins to
        -- stg_sunbiz__flr_filings.filing_doc_number.

        try_to_number(substr(line, 26, 1))               as action_count,
        -- Character 26: how many actions this event contains.

        try_to_number(substr(line, 27, 1))               as event_seq,
        -- Character 27: the event's sequence number on the lien.

        try_to_number(substr(line, 28, 1))               as pages,
        -- Character 28: pages in the event form.

        try_to_date(substr(line, 29, 8), 'MMDDYYYY')     as event_filing_date,
        -- Characters 29–36: the date the event was filed with the state.

        try_to_date(substr(line, 37, 8), 'MMDDYYYY')     as create_date,
        -- Characters 37–44: the date the state created the record.

        nullif(trim(substr(line, 47, 12)), '')           as action_event_number,
        -- Characters 47–58: the state's tracking number for the action.

        try_to_number(substr(line, 59, 1))               as action_seq,
        -- Character 59: this action's sequence number within the event.

        trim(substr(line, 60, 3))                        as action_code,
        -- Characters 60–62: what happened. COR = certificate of release,
        -- COD = certificate of discharge, AGI = amendment, RNC/RNL = refiling.

        trim(substr(line, 63, 70))                       as action_text,
        -- Characters 63–132: the same thing in words, e.g. CERTIFICATE OF RELEASE.

        nullif(trim(substr(line, 133, 1)), '')           as old_name_seq,
        -- Character 133: for a name change, the sequence number of the old name.

        nullif(trim(substr(line, 134, 1)), '')           as new_name_seq,
        -- Character 134: for a name change, the sequence number of the new name.

        nullif(trim(substr(line, 135, 1)), '')           as name_type,
        -- Character 135: D = the action concerns a debtor, S = a secured party.

        length(line) = 135                               as is_well_formed,
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
