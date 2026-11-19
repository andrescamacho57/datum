-- ---------------------------------------------------------------------------
-- stg_duval__documents.sql: the STAGING model for Duval County recorded
-- documents.
--
-- What this model does: the raw table has one text column per field of the
-- Clerk's daily documents file. This model drops the EOF trailer rows, trims
-- the text, turns blanks into NULLs, and turns the date, page-count and
-- amount text into real dates and numbers. No business logic: it doesn't
-- decide which documents are liens or which liens are open. That's Phase B.
--
-- Grain (what one row is): one recorded document as it appeared in one daily
-- file. The Clerk re-indexes old documents, so the same instrument number
-- can appear in more than one day's file, and file_date is NOT the recording
-- date. Use recorded_date for "when was this recorded".
--
-- People: this index covers everything recorded in the county, including
-- marriage licenses, death certificates and criminal judgments. Those rows
-- are allowed here and must go no further than staging.
--
-- Not for display outside this repo until Andres clears the Clerk's terms.
--
-- Becomes the view DATUM.DEV_STAGING.STG_DUVAL__DOCUMENTS.
-- ---------------------------------------------------------------------------


with source as (
    -- STEP 1: read the raw table and drop each file's trailer row.
    select * from {{ source('duval', 'duval_documents') }}
    where record_type <> 'EOF'
    -- Every file ends with a line EOF|<row count>. It was loaded into raw so
    -- the load could be checked against it (script 15); it isn't a document.
),

cleaned as (
    -- STEP 2: trim, blank → NULL, text → date / number.
    select
        trim(instrument_number)                            as instrument_number,
        -- The Clerk's ID for the document, e.g. 2025900001: the year it was
        -- recorded followed by a running number. Parties and links point here.

        nullif(trim(doc_type_code), '')                    as doc_type_code,
        -- The kind of document as a short code: LN lien, N/C notice of
        -- commencement, JDG judgment, RELEASE, SAT satisfaction, LP lis pendens...

        nullif(trim(doc_type_name), '')                    as doc_type_name,
        -- The same thing in words, e.g. NOTICE COMMENCEMENT.

        nullif(trim(legal_description), '')                as legal_description,
        -- Free text typed by the Clerk: a parcel and lot, a case number, or a note.

        nullif(trim(book_type), '')                        as book_type,
        -- OR = Official Records.

        nullif(trim(book), '')                             as book,
        nullif(trim(page), '')                             as page,
        -- Where the document sits in the Official Records books. Kept as
        -- text: they are labels, not numbers to do arithmetic on.

        try_to_number(trim(page_count))                    as page_count,
        -- How many pages the document has. try_to_number returns NULL
        -- instead of failing when the text isn't a number.

        try_to_date(trim(record_date), 'MM/DD/YYYY')       as recorded_date,
        -- The day the document was recorded. try_to_date returns NULL
        -- instead of failing when the text isn't a date.

        nullif(trim(record_time), '')                      as recorded_time_raw,
        -- The time of day as the Clerk writes it: digits with no leading
        -- zero, e.g. 113841 = 11:38:41 and 12347 = 1:23:47. Left as text;
        -- nothing needs it as a real time yet.

        try_to_number(trim(amount), 14, 2)                 as amount,
        -- The dollar amount indexed on the document; 0.00 when there is none.
        -- (14, 2) = up to 14 digits with 2 after the decimal point.

        try_to_date(substr(source_file, 2, 8), 'YYYYMMDD') as file_date,
        -- The date in the file's name (d2025010301id.16.gz → characters 2–9).
        -- The day the Clerk produced the file, not the recording date.

        source_file,                                       -- provenance: the exact staged file
        loaded_at                                          -- provenance: when COPY loaded it
        -- Not carried: record_type (always DDA), county_code (always 16) and
        -- unused_10 (always empty). They stay in raw.

    from source
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from cleaned
