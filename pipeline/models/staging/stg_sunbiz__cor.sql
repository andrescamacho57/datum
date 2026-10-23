-- ---------------------------------------------------------------------------
-- stg_sunbiz__cor.sql: the STAGING model for Sunbiz corporate filings.
--
-- What a model is: one .sql file containing one SELECT statement. dbt runs
-- it and saves the result in Snowflake under the file's name. This one
-- becomes the view DATUM.DEV_STAGING.STG_SUNBIZ__COR (a view, because
-- dbt_project.yml says staging models are views).
--
-- What this model does: each raw row is one long 1440-character line. This
-- model cuts each line into named columns (document number, name, status...)
-- by character position, and trims the padding spaces. That's all. It holds
-- no business logic (no matching, no scoring). Staging only makes the raw
-- data readable.
--
-- Where the positions come from: the state's published layout, recorded in
-- docs/access/sunbiz.md and confirmed on a real file on 2026-10-12.
-- Each line = 1436 characters of content + 4 invisible NUL padding bytes.
--
-- File name: "stg_" = staging layer, "sunbiz" = source, "__cor" = the
-- corporate file. The convention is stg_<source>__<table>.
-- ---------------------------------------------------------------------------


-- The query is built in steps called CTEs (common table expressions).
-- `with name as ( ... )` defines a named, temporary result that later steps
-- can read from. Read them top to bottom, like a recipe.

with daily as (
    -- STEP 1a: the daily files (one day's new filings each).
    select
        line,                                        -- the full 1440-character line from the state file
        source_file,                                 -- which file the line came from (provenance)
        loaded_at,                                   -- when COPY loaded it (provenance)
        'daily' as source_kind,                      -- a label: which kind of state file this row came from
        try_to_date(left(source_file, 8), 'YYYYMMDD') as published_on
        -- The date the STATE published this file. Daily files are named for
        -- their date: 20261009c.txt → left(…, 8) takes the first 8 characters,
        -- "20261009", and try_to_date reads them as year-month-day.
    from {{ source('sunbiz', 'sunbiz_cor_daily') }}
    -- The double curly braces around source(...) mark Jinja, dbt's template
    -- language. dbt fills it in BEFORE sending the SQL to Snowflake.
    -- (Never write double curly braces inside a comment: dbt reads Jinja
    -- everywhere in a file, comments included.)
),

quarterly as (
    -- STEP 1b: the quarterly full snapshot (every company, active or not).
    select
        line,
        source_file,
        loaded_at,
        'quarterly' as source_kind,
        '2026-10-07'::date as published_on
        -- The snapshot's files are named cordata0-9 with no date in the name,
        -- so the date is written here. It comes from the state's own file
        -- timestamps inside cordata.zip (`unzip -l`, all 2026-10-07).
        -- `::date` converts the text '2026-10-07' to a DATE value.
        -- REVISIT when the January 2027 snapshot arrives: one hardcoded date
        -- can't describe two snapshots. Then the date moves into raw at COPY time.
    from {{ source('sunbiz', 'sunbiz_cor_quarterly') }}
),

source as (
    -- STEP 1c: stack the two into one set of rows.
    select * from daily
    union all
    select * from quarterly
    -- union all = put the rows of the second query under the first. Both must
    -- have the same columns in the same order (they do: 5 each).
    -- "all" keeps every row, including duplicates; plain `union` would
    -- de-duplicate, which costs a sort over 13M rows and could silently merge
    -- rows. Deduping is the mart's job, done on purpose with a rule.
),

parsed as (
    -- STEP 2: cut each line into columns.
    --
    -- The building block: substr(line, start, length).
    --   substr = substring: take a piece of text.
    --   start  = position to start from. Positions count from 1, not 0.
    --   length = how many characters to take.
    -- trim(...) removes the padding spaces around the piece. Fixed-width
    -- files pad every field to its full width, so "ACME LLC" arrives as
    -- "ACME LLC" followed by 184 spaces.
    -- `as name` gives the resulting column its name.
    select
        trim(substr(line, 1, 12))                     as document_number,
        -- Characters 1–12: the state's unique ID for the company,
        -- e.g. L26000514010. Every other fact hangs off this ID.

        trim(substr(line, 13, 192))                   as entity_name,
        -- Characters 13–204 (192 long): the legal name as filed.

        substr(line, 205, 1)                          as status_code,
        -- Character 205: A = active, I = inactive. A single character, so it
        -- has no padding and needs no trim.

        trim(substr(line, 206, 15))                   as filing_type,
        -- Characters 206–220: the kind of company, e.g.
        -- FLAL = Florida limited liability company (LLC),
        -- DOMP = domestic (Florida) profit corporation.

        trim(substr(line, 221, 42))                   as principal_address_1,
        -- Characters 221–262: first street line of the main business address.

        trim(substr(line, 305, 28))                   as principal_city,
        -- Characters 305–332: city of the main business address.

        trim(substr(line, 333, 2))                    as principal_state,
        -- Characters 333–334: two-letter state code.

        trim(substr(line, 335, 10))                   as principal_zip,
        -- Characters 335–344: ZIP code (room for ZIP+4).

        try_to_date(substr(line, 473, 8), 'MMDDYYYY') as file_date,
        -- Characters 473–480: a date stored as 8 digits, e.g. 10052026.
        -- try_to_date turns that text into a real DATE value using the
        -- pattern 'MMDDYYYY' (month, day, 4-digit year). The "try_" version
        -- returns NULL (empty) instead of failing the whole query when a
        -- value doesn't fit the pattern.
        -- Caution: some values are future dates, so this may be an EFFECTIVE
        -- date rather than the filing date. Not verified yet.

        nullif(trim(substr(line, 481, 14)), '')       as fei_number,
        -- Characters 481–494: the company's federal tax ID (FEI/EIN, federal
        -- employer identification number), when the company provided one.
        -- nullif(x, '') returns NULL when x is an empty string. A missing
        -- value is then a true NULL, not a blank that looks like data.

        length(line) >= 1436                          as is_well_formed,
        -- A TRUE/FALSE column. length(line) counts the line's characters.
        -- A complete line is at least 1436 long (1440 with the padding).
        -- A shorter line is damaged, for example split by a stray line break,
        -- which the state warns can happen. We FLAG those lines instead of
        -- deleting them, so a data problem shows up instead of quietly
        -- disappearing.

        source_kind,
        published_on,
        source_file,
        loaded_at
        -- Carried through unchanged, so every value can be traced to the
        -- exact state file it came from, and when the state published it.

    from source
    -- Read from STEP 1 above.

    where trim(line) <> ''
    -- Skip lines that are completely blank. <> means "not equal to".
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from parsed
