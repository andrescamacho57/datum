-- ---------------------------------------------------------------------------
-- entity_lookup.sql: the MART for looking up a company by name.
--
-- What it becomes: the TABLE DATUM.DEV_MARTS.ENTITY_LOOKUP (a table, because
-- dbt_project.yml says mart models are tables).
--
-- What it does, on top of staging:
--   1. Keeps only well-formed rows (drops the damaged lines staging flagged).
--   2. Keeps exactly ONE row per company, even after many daily files have
--      been loaded.
--   3. Adds name_key, a simplified version of the name that makes searching
--      easier.
--
-- Why a separate layer: staging describes the data as it IS. A mart shapes it
-- for a USE. This mart's use is "find a company by name." A later mart for
-- reports would shape the same staging data differently.
-- ---------------------------------------------------------------------------

select
    document_number,
    -- The state's company ID. After the dedupe below, it's unique in this
    -- table, and the tests in _marts.yml check that.

    entity_name,
    -- The legal name exactly as filed. Kept for display.

    trim(regexp_replace(upper(entity_name), '[^A-Z0-9]+', ' ')) as name_key,
    -- A simplified name for searching. Read it inside out:
    --   upper(entity_name)       → all capitals: "Acme, L.L.C." → "ACME, L.L.C."
    --   regexp_replace(x, pattern, ' ')
    --                            → replace every match of the pattern with a space.
    --     The pattern '[^A-Z0-9]+' means:
    --       [ ... ]  one character from this set
    --       ^        (inside brackets) NOT in this set
    --       A-Z0-9   capital letters and digits
    --       +        one or more in a row
    --     So every run of punctuation and spaces becomes ONE space:
    --       "ACME, L.L.C." → "ACME L L C "
    --   trim(...)                → remove the space left at the end.
    -- This is a first, crude step. Real name matching (removing LLC, INC and
    -- so on) comes later and gets tested against the whole register.

    status_code,
    filing_type,
    principal_city,
    principal_state,
    file_date,
    -- Passed through from staging unchanged.

    source_kind,
    published_on,
    source_file,
    loaded_at
    -- Provenance stays with every row, even in the final layer, so any fact
    -- Datum ever shows can be traced to the exact state file and its date.

from {{ ref('stg_sunbiz__cor') }}
-- ref() = "read from another dbt model." dbt replaces it with the real name,
-- datum.dev_staging.stg_sunbiz__cor. It also records that this model DEPENDS
-- on staging, so `dbt build` always builds staging first.
-- (source() is for tables dbt didn't build; ref() is for models it did.)

where is_well_formed
-- Keep only rows where the staging flag is TRUE. Damaged lines are left out
-- here, but they're still visible in staging if you want to inspect them.

qualify row_number() over (
    partition by document_number
    order by published_on desc, loaded_at desc
) = 1
-- Keep exactly one row per company. Read it in pieces:
--   row_number()            numbers rows 1, 2, 3, ...
--   over ( ... )            ... but within the groups defined inside:
--   partition by document_number
--                           one group per company (restart numbering at 1
--                           for each document_number)
--   order by published_on desc, loaded_at desc
--                           number each group newest first (desc = descending),
--                           by the date the STATE published the record. If two
--                           rows tie on that date, the one loaded last wins.
--                           (Ordering by loaded_at alone was a bug: the Oct 7
--                           snapshot, loaded on Oct 22, would beat the Oct 9
--                           daily file, loaded on Oct 13.)
--   = 1                     keep row number 1: the newest row per company
--   qualify                 filters on that number. It's like WHERE, but WHERE
--                           can't see window functions like row_number();
--                           QUALIFY can.
-- Why: once you load more daily files, the same company can appear several
-- times (for example, when its status changes). The lookup should show the
-- latest version, once.
