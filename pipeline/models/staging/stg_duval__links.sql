-- ---------------------------------------------------------------------------
-- stg_duval__links.sql: the STAGING model for links between Duval County
-- recorded documents.
--
-- What a link is: when a new document refers to an earlier one, the Clerk
-- records the pair. A RELEASE linked to an LN (lien) means that lien was
-- released; a SAT (satisfaction) linked to an MTG means that mortgage was
-- paid off. This is how Phase B will tell an open lien from a released one.
--
-- What this model does: drops the EOF trailer rows, trims the text, turns
-- blanks into NULLs and adds has_link. It does not decide what a link means.
--
-- Grain: one row per document per daily file. A document that refers to
-- nothing still gets a row, with linked_doc_type_code = 'NONE' in the file.
--
-- Becomes the view DATUM.DEV_STAGING.STG_DUVAL__LINKS.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and drop each file's trailer row.
    select * from {{ source('duval', 'duval_links') }}
    where instrument_number <> 'EOF'
    -- Links files have no record-type field, so the trailer line
    -- EOF|<row count> lands with 'EOF' in the first column.
),

cleaned as (
    -- STEP 2: trim and blank → NULL.
    select
        trim(instrument_number)                            as instrument_number,
        -- The NEW document (the release, the satisfaction, the assignment).
        -- Joins to stg_duval__documents.instrument_number.

        nullif(trim(book), '')                             as book,
        nullif(trim(page), '')                             as page,
        nullif(trim(book_type), '')                        as book_type,
        -- Where the new document sits in the Official Records (OR) books.

        nullif(trim(doc_type_code), '')                    as doc_type_code,
        -- The new document's type, e.g. RELEASE, SAT, ASSIGN.

        nullif(trim(linked_instrument_number), '')         as linked_instrument_number,
        -- The EARLIER document it refers to. NULL when there is no link. It
        -- can be many years old, so it is often outside the files we loaded.

        nullif(trim(linked_book), '')                      as linked_book,
        nullif(trim(linked_page), '')                      as linked_page,
        nullif(trim(linked_book_type), '')                 as linked_book_type,
        -- Where the earlier document sits in the books.

        nullif(nullif(trim(linked_doc_type_code), ''), 'NONE') as linked_doc_type_code,
        -- The earlier document's type, e.g. LN or MTG. The file writes the
        -- word NONE when there is no link; the outer nullif turns that into
        -- a true NULL so "no link" can't be mistaken for a type called NONE.

        coalesce(trim(linked_doc_type_code), '') not in ('', 'NONE') as has_link,
        -- TRUE when this row really points at an earlier document.
        -- coalesce(x, '') swaps a NULL for an empty string so the comparison
        -- always gives TRUE or FALSE, never "unknown".

        try_to_date(substr(source_file, 2, 8), 'YYYYMMDD') as file_date,
        -- The date in the file's name (l2025010301id.16.gz → characters 2–9).

        source_file,                                       -- provenance: the exact staged file
        loaded_at                                          -- provenance: when COPY loaded it

    from source
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from cleaned
