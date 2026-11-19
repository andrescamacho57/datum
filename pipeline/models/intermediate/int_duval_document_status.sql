-- ---------------------------------------------------------------------------
-- int_duval_document_status.sql: is each Duval County lien, tax warrant or
-- judgment open or closed?
--
-- NOT FOR DISPLAY outside this repo until Andres clears the Clerk's terms
-- (ruling R20).
--
-- Which documents: the ones in int_duval_party_links, that is, allowlisted
-- LN / WRT / JDG / CCCJUDG documents with at least one business party on
-- the TO side, and no judgment the State of Florida brought. A document
-- whose parties are all individuals is not here (ruling R19).
--
-- The rule (ruling R18): a document is CLOSED when any document in the
-- release or satisfaction families links to it. The Clerk records such links
-- by the earlier document's instrument number, or, when the link has no
-- instrument number, by its book and page. Which type codes close is the
-- seed duval_doc_type_allowlist (used_for = 'closes').
--
-- A PARTIAL release (PTL REL) does not close a document. It is counted and
-- dated here so the report can show it as an event.
--
-- What this model can't see: a release recorded before 2025-01-01, the
-- first day of the index files we loaded. About six in ten liens here were
-- recorded before that day (the Clerk re-indexes old documents into new
-- daily files). For those, "open" means "no release in the files since
-- 2025-01-01", so recorded_before_window marks them and the flags mart adds
-- a caveat.
--
-- No names: this model reads documents and links, which hold none.
--
-- Grain: one row per document (instrument_number is unique).
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_DUVAL_DOCUMENT_STATUS.
-- ---------------------------------------------------------------------------


with documents as (
    -- STEP 1: one row per document: the newest daily file wins.
    select
        instrument_number,
        doc_type_code,
        book_type,
        book,
        page,
        case when recorded_date >= '1900-01-01' then recorded_date end as recorded_date,
        -- Ruling R22: a recording date before 1900 is a placeholder.
        source_file
    from {{ ref('stg_duval__documents') }}
    qualify row_number() over (
        partition by instrument_number
        order by file_date desc, loaded_at desc
    ) = 1
),

flag_documents as (
    -- STEP 2: the documents that can carry a flag: those with a row in
    -- int_duval_party_links. That model already applied the allowlist, the
    -- State-of-Florida test and the business-party test.
    select
        d.*,
        a.flag_type                                  -- duval_lien, duval_tax_warrant or duval_judgment
    from documents as d
    inner join {{ ref('duval_doc_type_allowlist') }} as a
        on  a.doc_type_code = d.doc_type_code
        and a.used_for = 'flag'
    where d.instrument_number in (
        select source_record_id from {{ ref('int_duval_party_links') }}
    )
),

closing_links as (
    -- STEP 3: links FROM a release, satisfaction or partial release TO an
    -- earlier document. One row per link.
    select
        l.instrument_number                          as closing_instrument_number,
        l.doc_type_code                              as closing_doc_type_code,
        a.used_for,                                  -- 'closes' or 'partial_release'
        l.linked_instrument_number,                  -- the earlier document, when the Clerk gave its number

        coalesce(
            l.linked_book,
            regexp_substr(l.linked_doc_type_code, '^-(OR |O )?([0-9]+)/([0-9]+)$', 1, 1, 'e', 2)
        )                                            as linked_book,
        coalesce(
            l.linked_page,
            regexp_substr(l.linked_doc_type_code, '^-(OR |O )?([0-9]+)/([0-9]+)$', 1, 1, 'e', 3)
        )                                            as linked_page
        -- When a link has no instrument number, the Clerk's file writes the
        -- book and page into the LAST field as text: "-OR 10659/1002",
        -- "-O 10659/1002" or "-10659/1002". regexp_substr with 'e' returns
        -- one bracketed group of the pattern: group 2 is the book, group 3
        -- the page. Text in any other shape ("-NONE", "-NA") gives NULL.
        -- coalesce takes the first value that is not NULL: the real book and
        -- page columns if the file ever fills them, else the parsed text.
    from {{ ref('stg_duval__links') }} as l
    inner join {{ ref('duval_doc_type_allowlist') }} as a
        on  a.doc_type_code = l.doc_type_code
        and a.used_for in ('closes', 'partial_release')
    where l.has_link
    qualify row_number() over (
        partition by l.instrument_number, l.linked_instrument_number, l.linked_doc_type_code
        order by l.file_date desc, l.loaded_at desc
    ) = 1
    -- The same link can sit in several daily files: keep one copy.
),

matched as (
    -- STEP 4: attach each closing link to the document it points at, by
    -- instrument number first, by book and page otherwise.
    select
        d.instrument_number,
        c.closing_instrument_number,
        c.closing_doc_type_code,
        c.used_for,
        cd.recorded_date                             as closing_recorded_date,
        -- The day the release itself was recorded.
        cd.source_file                               as closing_source_file
        -- The Clerk's file the release came from (provenance).
    from flag_documents as d
    inner join closing_links as c
        on (    c.linked_instrument_number = d.instrument_number )
        or (    c.linked_instrument_number is null
            and try_to_number(c.linked_book) = try_to_number(d.book)
            and try_to_number(c.linked_page) = try_to_number(d.page) )
        -- try_to_number compares 012292 and 12292 as the same book. If
        -- either side isn't a number the result is NULL, and NULL never
        -- equals anything, so nothing matches by accident.
    left join documents as cd
        on cd.instrument_number = c.closing_instrument_number
),

first_closing as (
    -- STEP 5a: for each document, ONE closing document: the first full
    -- release or satisfaction. Its number, type, date and file all come from
    -- that one row, so "closed by" can never pair the number of one document
    -- with the type or file of another.
    select
        instrument_number,
        closing_instrument_number,
        closing_doc_type_code,
        closing_recorded_date,
        closing_source_file
    from matched
    where used_for = 'closes'
    qualify row_number() over (
        partition by instrument_number
        order by
            closing_recorded_date asc nulls last,
            closing_instrument_number asc,
            closing_doc_type_code asc
    ) = 1
    -- row_number() numbers the rows of each document 1, 2, 3 ... in the
    -- order given, and qualify keeps number 1. The order is FULL: earliest
    -- recording date first (a closing document with no date sorts last but
    -- still counts), then the lower instrument number when two were
    -- recorded the same day. An instrument number is unique, so the same
    -- row wins on every run. The type code is a last tiebreak for the one
    -- case left: the same closing document linked twice.
),

closing_counts as (
    -- STEP 5b: per document, how many full and partial releases link to it.
    select
        instrument_number,
        count_if(used_for = 'closes')                                              as closing_document_count,
        count_if(used_for = 'partial_release')                                     as partial_release_count,
        max(case when used_for = 'partial_release' then closing_recorded_date end) as last_partial_release_on
    from matched
    group by instrument_number
)

-- STEP 6: one row per document, open or closed.
select
    d.instrument_number,
    d.doc_type_code,
    d.flag_type,
    d.recorded_date,
    d.book,
    d.page,
    -- Book and page: part of the citation (ruling R21).

    case when coalesce(c.closing_document_count, 0) > 0 then 'closed' else 'open' end as document_status,
    -- Closed when at least one full release or satisfaction links to it.
    -- coalesce(x, 0): a document with no links at all has no row in
    -- closing_counts, so the count is NULL; treat that as 0.

    fc.closing_recorded_date                         as closed_on,
    -- The day the first full release or satisfaction was recorded.
    fc.closing_instrument_number                     as closed_by_instrument_number,
    fc.closing_doc_type_code                         as closed_by_doc_type_code,
    coalesce(c.partial_release_count, 0)             as partial_release_count,
    c.last_partial_release_on,

    coalesce(d.recorded_date < '2025-01-01', true)   as recorded_before_window,
    -- TRUE when the document was recorded before the first index file we
    -- loaded (or has no usable date): an earlier release would be invisible.

    d.source_file,
    -- The Clerk's file the document row came from (provenance; joins to the
    -- fetch manifest).

    fc.closing_source_file                           as closed_by_source_file
    -- The Clerk's file the closing document came from. NULL on an open document.

from flag_documents as d
left join closing_counts as c
    on c.instrument_number = d.instrument_number
left join first_closing as fc
    on fc.instrument_number = d.instrument_number
-- LEFT JOINs: an open document has no row in either.
