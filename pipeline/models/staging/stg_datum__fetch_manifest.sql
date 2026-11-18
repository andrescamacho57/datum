-- ---------------------------------------------------------------------------
-- stg_datum__fetch_manifest.sql: the STAGING model for the fetch manifest.
--
-- What the manifest is: one row for every file Datum downloaded from a
-- source, written by the downloader at the moment of download (ruling R23,
-- src/datum/manifest.py). It answers "when did we fetch this file, and from
-- exactly where?", which loaded_at in the raw tables can't: that is when
-- Snowflake loaded the file, sometimes days later.
--
-- What this model does: gives the text columns real types, adds source_file
-- (the name the raw tables know each file by) and keeps ONE row per file.
--
-- Why one row per file needs a rule: the manifest is a single growing CSV.
-- Every time it changes it is loaded whole again, so raw holds repeats. And
-- a file downloaded twice has two rows on purpose. This model keeps the
-- LATEST fetch of each file.
--
-- How it is used: any fact reaches its fetch time by joining its own
-- source_file (and source) to this model. CLAUDE.md rule 3: every fact
-- carries a source URL and a UTC fetch timestamp.
--
-- Grain: one fetched file per source.
-- Becomes the view DATUM.DEV_STAGING.STG_DATUM__FETCH_MANIFEST.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table as it is.
    select * from {{ source('datum', 'fetch_manifest') }}
),

typed as (
    -- STEP 2: text → real types, plus the join key to the raw tables.
    select
        trim(source)                                       as source,
        -- Which source the file belongs to: dbpr, duval or sunbiz_flr.

        trim(file_name)                                    as file_name,
        -- The file's name as fetched, e.g. d2026110501id.16.

        trim(file_name) || '.gz'                           as source_file,
        -- The name the raw tables carry in THEIR source_file column: PUT
        -- compresses each file and adds .gz. || joins two pieces of text.
        -- This is the column to join on.

        trim(source_url)                                   as source_url,
        -- The exact address the file came from.

        to_timestamp_ntz(fetched_at_utc, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') as fetched_at_utc,
        -- The text 2026-11-18T07:10:39Z becomes a real timestamp. The T and
        -- the Z are literal characters, so the pattern wraps them in double
        -- quotes. _ntz = "no time zone" stored; the column NAME says it is UTC.

        to_number(size_bytes)                              as size_bytes,
        -- The file's size in bytes, as fetched.

        trim(sha256)                                       as sha256,
        -- Checksum of the bytes as fetched: 64 hexadecimal characters.

        to_boolean(is_approximate)                         as is_approximate,
        -- TRUE when fetched_at_utc is the file's modification time (a file
        -- downloaded before the manifest existed), not a measured fetch time.

        loaded_at                                          as manifest_loaded_at
        -- When this manifest row was loaded into Snowflake (provenance of
        -- the manifest itself). Renamed so it can't be confused with the
        -- loaded_at of the data file the row describes.

    from source
)

-- STEP 3: one row per file: the latest fetch, and among repeats of that
-- fetch (the manifest reloaded), the copy loaded last.
select * from typed
qualify row_number() over (
    partition by source, file_name
    order by fetched_at_utc desc, manifest_loaded_at desc
) = 1
-- row_number() numbers the rows inside each (source, file_name) group,
-- newest fetch first; qualify keeps number 1. Same pattern as entity_lookup.
