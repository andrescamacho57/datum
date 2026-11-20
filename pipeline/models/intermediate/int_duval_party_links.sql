-- ---------------------------------------------------------------------------
-- int_duval_party_links.sql: which company does a party on a Duval County
-- lien, tax warrant or judgment point at?
--
-- NOT FOR DISPLAY outside this repo until Andres clears the Clerk's terms
-- (ruling R20). The flags mart marks every Duval flag is_shown = false.
--
-- What comes in, and what is kept out before any matching:
--   Document types   only the four "flag" codes in the seed
--                    duval_doc_type_allowlist: LN (lien), WRT (tax warrant),
--                    JDG and CCCJUDG (judgments). An allowlist can't leak a
--                    type nobody thought of (ruling R16).
--   State judgments  a JDG or CCCJUDG with the State of Florida on the FRM
--                    side is left out: that marks a criminal or fines matter
--                    (ruling R16).
--   Side             only parties on the TO side. On these four types the TO
--                    side is the debtor, taxpayer or defendant (ruling R17,
--                    measured in docs/phase_b_rulings.md).
--   Businesses       only names that carry a legal-entity word (LLC, INC,
--                    CORP ...). A name without one may be a person, and an
--                    individual's party row goes no further than staging
--                    (ruling R19). Such a name could never be CONFIRMED
--                    anyway (ruling R1).
--
-- The match: the Clerk's index has no address, so only the unique-name
-- branch of ruling R1 applies (ruling R3): CONFIRMED when exactly one company
-- of any status in Florida has the party's match key. Ruling R2 then compares
-- the recording date with the company's filing date.
--
-- No names (ruling R4): the party's name is used to compute the match and is
-- not written to this table.
--
-- Columns (the same in every link model):
--   source_record_id  the Clerk's instrument number, e.g. 2025900001
--   party_seq         the party's sequence number on the TO side
--   document_number   the company's Sunbiz document number; NULL on NO_MATCH
--   link_status       CONFIRMED / AMBIGUOUS / NO_MATCH
--   matched_on        unique_name on a CONFIRMED row, else NULL
--   link_reason       why the row got its status
--   source_date       the day the document was recorded
--
-- Grain: one row per TO-side business party per candidate company.
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_DUVAL_PARTY_LINKS.
-- ---------------------------------------------------------------------------


with documents as (
    -- STEP 1: one row per document. The Clerk re-indexes documents, so an
    -- instrument number can appear in several daily files; the newest file
    -- wins.
    select
        instrument_number,
        doc_type_code,
        case when recorded_date >= '1900-01-01' then recorded_date end as recorded_date
        -- Ruling R22: a recording date before 1900 is a placeholder and
        -- becomes NULL past staging.
    from {{ ref('stg_duval__documents') }}
    qualify row_number() over (
        partition by instrument_number
        order by file_date desc, loaded_at desc
    ) = 1
),

flag_documents as (
    -- STEP 2: keep only the document types that can become a flag.
    select d.*
    from documents as d
    inner join {{ ref('duval_doc_type_allowlist') }} as a
        on  a.doc_type_code = d.doc_type_code
        and a.used_for = 'flag'
),

parties as (
    -- STEP 3: the parties of those documents, from the newest file that
    -- lists each document's parties.
    select
        p.instrument_number,
        p.party_role,                                -- FRM or TO
        p.party_seq,
        {{ name_key('p.party_name') }}               as party_name_key
        -- The simplified name. It is used below and never output.
    from {{ ref('stg_duval__parties') }} as p
    inner join flag_documents as d
        on d.instrument_number = p.instrument_number
    qualify dense_rank() over (
        partition by p.instrument_number
        order by p.file_date desc
    ) = 1
    -- dense_rank gives every row of the newest file rank 1 (row_number would
    -- keep only one party). So all parties of that file stay, and older
    -- files' copies go.
),

state_judgments as (
    -- STEP 4: documents with the State of Florida on the FRM side. The Clerk
    -- writes it "FLORIDA STATE OF" (4,838 of the judgment party rows); the
    -- same party also appears as "FLORIDA STATE OF ETAL" and, a few times,
    -- "STATE OF FLORIDA". All three are caught. State AGENCIES (the
    -- Department of Revenue and others) are different parties and are not.
    select distinct instrument_number
    from parties
    where party_role = 'FRM'
      and (   party_name_key = 'FLORIDA STATE OF'
           or party_name_key like 'FLORIDA STATE OF %'
           or party_name_key = 'STATE OF FLORIDA')
),

source_names as (
    -- STEP 5: the five columns the linking macro expects: TO-side parties
    -- with a legal-entity word, on documents that passed STEPs 2 and 4.
    select
        p.instrument_number                          as source_record_id,
        p.party_seq                                  as party_seq,
        p.party_name_key                             as source_name_key,
        cast(null as varchar)                        as source_zip5,
        -- The Clerk's index carries no address.
        d.recorded_date                              as source_date
    from parties as p
    inner join flag_documents as d
        on d.instrument_number = p.instrument_number
    where p.party_role = 'TO'
      and {{ has_entity_word('p.party_name_key') }}
      -- The macro returns TRUE when the name holds LLC, INC, CORP ... as a
      -- whole word (macros/company_matching.sql).
      and not (
          d.doc_type_code in ('JDG', 'CCCJUDG')
          and p.instrument_number in (select instrument_number from state_judgments)
      )
      -- Leave out judgments the State of Florida brought. Liens and warrants
      -- are not affected by this test.
),

-- STEP 6: apply rulings R1 and R2. `false` = this source has no ZIP code, so
-- every row takes the unique-name branch (ruling R3).
{{ link_to_companies('source_names', false) }}
