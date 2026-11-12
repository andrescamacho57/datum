-- ---------------------------------------------------------------------------
-- stg_duval__parties.sql: the STAGING model for parties on Duval County
-- recorded documents.
--
-- What this model does: drops the EOF trailer rows from the raw parties
-- table, trims the text and names the columns. One row says "this name is
-- on this document, on the FROM side or the TO side".
--
-- Grain: one party on one document, as it appeared in one daily file.
--
-- People: most party names are individuals. They are allowed in staging and
-- must go no further: no intermediate model, mart, report or sample file may
-- carry a person's name. Phase B has to pick out business names first.
--
-- FRM and TO: the Clerk indexes each document with a "from" side and a "to"
-- side. Which side is the debtor depends on the document type (on a lien,
-- on a release...). That reading is Phase B's, and it is not assumed here.
--
-- Not for display outside this repo until Andres clears the Clerk's terms.
--
-- Becomes the view DATUM.DEV_STAGING.STG_DUVAL__PARTIES.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and drop each file's trailer row.
    select * from {{ source('duval', 'duval_parties') }}
    where record_type <> 'EOF'
    -- The EOF|<row count> line at the end of every file isn't a party.
),

cleaned as (
    -- STEP 2: trim, blank → NULL, text → number.
    select
        trim(instrument_number)                            as instrument_number,
        -- The document this party is on. Joins to
        -- stg_duval__documents.instrument_number.

        try_to_number(trim(party_seq))                     as party_seq,
        -- The party's sequence number on the document (1, 2, 3 ...).

        nullif(trim(party_role), '')                       as party_role,
        -- FRM = the "from" side, TO = the "to" side.

        nullif(trim(party_name), '')                       as party_name,
        -- The name as the Clerk indexed it: a person or a business.

        try_to_date(substr(source_file, 2, 8), 'YYYYMMDD') as file_date,
        -- The date in the file's name (p2025010301id.16.gz → characters 2–9).

        source_file,                                       -- provenance: the exact staged file
        loaded_at                                          -- provenance: when COPY loaded it

    from source
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from cleaned
