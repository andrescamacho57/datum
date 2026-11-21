-- ---------------------------------------------------------------------------
-- int_federal_lien_links.sql: which company does each federal tax lien
-- debtor point at?
--
-- What this model does: takes every corporate debtor on a federal tax lien
-- (stg_sunbiz__flr_debtors) and looks for the company with the same match
-- key, following rulings R1, R2, R29 and R30:
--   CONFIRMED  the match key and the 5-digit ZIP code both agree with exactly
--              one company (name_zip); or the debtor row has no ZIP code,
--              exactly one company of any status has the match key, and the
--              debtor's name carries a legal-entity word (unique_name). In
--              both cases no other company may be a near-namesake (R30)
--   AMBIGUOUS  the name matches but the ZIP code doesn't, or several
--              companies fit, or the lien is older than the company (R2),
--              or the debtor row has a ZIP code that is not 5 digits and so
--              can't be read (R29), or another company's name differs only
--              by a leading THE, by AND versus &, or by trailing legal
--              suffixes (R30)
--   NO_MATCH   no company has that match key
-- The rule itself is the macro link_to_companies (macros/company_matching.sql),
-- shared by all four link models.
--
-- No names (ruling R4): the debtor's name is used to compute the match and is
-- not written to this table. To see it, join back to staging on the lien
-- number and debtor sequence.
--
-- Columns (the same in every link model):
--   source_record_id  the lien's filing number, e.g. 26FLR0004110
--   party_seq         the debtor's sequence number on that lien
--   document_number   the company's Sunbiz document number; NULL on NO_MATCH
--   link_status       CONFIRMED / AMBIGUOUS / NO_MATCH
--   matched_on        name_zip or unique_name on a CONFIRMED row, else NULL
--   link_reason       why the row got its status
--   source_date       the date the lien was filed with the state
--
-- Grain: one row per debtor per candidate company. A CONFIRMED debtor has
-- exactly one row; an AMBIGUOUS one has a row for each possible company.
--
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_FEDERAL_LIEN_LINKS.
-- ---------------------------------------------------------------------------


with filings as (
    -- STEP 1: one row per lien, for its filing date. A lien appears in the
    -- snapshot or in one daily file; if it ever appears in both, the newest
    -- published row wins.
    select
        filing_doc_number,
        filing_date
    from {{ ref('stg_sunbiz__flr_filings') }}
    qualify row_number() over (
        partition by filing_doc_number
        order by published_on desc, loaded_at desc
    ) = 1
),

debtors as (
    -- STEP 2: one row per debtor per lien. Staging already keeps corporate
    -- (name format C) debtors only. One lien in the snapshot repeats the same
    -- debtor sequence numbers many times with the same name; the qualify
    -- keeps one row per (lien, sequence).
    select
        filing_doc_number,
        debtor_seq,
        debtor_name,
        zip5,
        zip
        -- The whole 9-character ZIP field, trimmed. It is only used in STEP 3,
        -- to tell "no ZIP code" apart from "a ZIP code we can't read".
    from {{ ref('stg_sunbiz__flr_debtors') }}
    qualify row_number() over (
        partition by filing_doc_number, debtor_seq
        order by published_on desc, loaded_at desc
    ) = 1
),

source_names as (
    -- STEP 3: the five columns the linking macro expects.
    select
        d.filing_doc_number                          as source_record_id,
        d.debtor_seq                                 as party_seq,
        {{ name_key('d.debtor_name') }}              as source_name_key,
        -- The debtor's name simplified the same way company names are. It
        -- lives only inside this query: the macro below does not output it.
        coalesce(d.zip5, d.zip)                      as source_zip5,
        -- coalesce returns its first value that is not NULL. zip5 is the first
        -- five characters of the state's ZIP field, and it is NULL when those
        -- five are blank. If something still follows the blanks, the field is
        -- not empty, and so the leftover (four characters at most, never a
        -- 5-digit ZIP code) is passed on. The macro then sees a ZIP code it
        -- can't read, and ruling R29 keeps the link from being CONFIRMED on
        -- the name alone. No row in the files loaded so far is like that.
        f.filing_date                                as source_date
    from debtors as d
    left join filings as f
        on f.filing_doc_number = d.filing_doc_number
    -- LEFT JOIN: a debtor whose lien is missing from the filings file is
    -- kept, with a NULL date. Ruling R2 then keeps it from being CONFIRMED.
),

-- STEP 4: apply rulings R1 and R2. The macro adds its own CTEs and the final
-- SELECT; `true` means "this source has a ZIP code, so use it".
{{ link_to_companies('source_names', true) }}
