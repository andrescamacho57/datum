# Runbook — First Slice: one Sunbiz file, end to end

**Goal:** a lookup on a dbt-built table returns DINATALE VENTURES LLC.
**Path:** file → Snowflake stage → raw table → dbt staging → dbt mart → lookup.
**Last updated:** 2026-10-12

## Status

| Step | What | Where | Status |
|---|---|---|---|
| A1 | Cost guardrails: `datum_wh` (X-Small, 60-second auto-suspend) + `datum_monthly` monitor (10 credits) | Snowflake worksheet | ✅ 2026-10-12 |
| A2 | `datum` database, `raw` schema, `fixed_width` file format, `sunbiz_stage`, `sunbiz_cor_daily` table | Snowflake worksheet | ✅ 2026-10-12 |
| B | `data/` folder; `.gitignore` covers data/, target/, logs/, .venv/ | VS Code terminal | ✅ 2026-10-12 |
| C | Download `doc/cor/20261009c.txt` over SFTP; verify 834 lines, layout confirmed | VS Code terminal | ✅ 2026-10-12 |
| D | Upload the file to `sunbiz_stage` (Snowsight: Ingestion → Add data → Load files into a Stage) | Browser | ✅ 2026-10-12 |
| E | COPY the stage into the raw table: 834 rows, every line 1440 bytes | Snowflake worksheet | ✅ 2026-10-13 |
| F | dbt project files (written to `pipeline/` by Claude; reviewed in VS Code) + `datum` profile (key-pair login) | VS Code | ✅ 2026-10-20 |
| G | `dbt debug` and `dbt build`: 2 models + 3 tests, 5/5 passed (dbt 2.0.8) | VS Code terminal | ✅ 2026-10-20 |
| H | Look up DINATALE VENTURES LLC | Snowflake worksheet | ⏭ |

---

## E. COPY into raw (Snowflake worksheet)

```sql
USE ROLE SYSADMIN;                                          -- owner role
USE WAREHOUSE datum_wh;                                     -- guarded warehouse

LIST @datum.raw.sunbiz_stage;                               -- confirm the file is there (20261009c.txt)

COPY INTO datum.raw.sunbiz_cor_daily (line, source_file, loaded_at)   -- destination table and columns
FROM (
  SELECT $1,                                                -- the whole line (the only field)
         METADATA$FILENAME,                                 -- which file it came from
         CURRENT_TIMESTAMP()                                -- load time
  FROM @datum.raw.sunbiz_stage                              -- every file in the stage (one today)
);

SELECT COUNT(*)          AS line_count,                     -- expect 834
       MIN(LENGTH(line)) AS shortest,                       -- expect 1436 or 1440
       MAX(LENGTH(line)) AS longest
FROM datum.raw.sunbiz_cor_daily;
```

- **Syntax:** `COPY INTO … FROM (SELECT …)` adds columns while loading; `$1` is the first field.
- **Concept:** COPY remembers which files it loaded (64 days) and skips them on a rerun, so it's idempotent.
- **Design decision:** one stage per Sunbiz file type, so each COPY reads its whole stage with no filters.

## F. dbt project files

### F1. Make the folders (VS Code terminal)

```bash
mkdir -p ~/datum/pipeline/models/staging ~/datum/pipeline/models/marts   # dbt finds models here
```

### F2. `~/.dbt/profiles.yml`: add next to your existing profiles

```yaml
datum:                                  # profile name; dbt_project.yml points to it
  target: dev                           # default output
  outputs:
    dev:
      type: snowflake                   # adapter
      account: <org>-<account>          # your account identifier: organization name, a hyphen, account name, from your Snowsight URL
      user: <user>                      # your Snowflake username
      private_key_path: <copy from your credit_stream profile>
      # Key-pair login (confirmed 2026-10-20): dbt signs in with a private key
      # file on your Mac instead of a password. Same key as credit_stream,
      # because Snowflake ties the key to your USER, not to a project.
      role: SYSADMIN
      warehouse: DATUM_WH
      database: DATUM
      schema: DEV                       # custom schemas are added after it: DEV_STAGING, DEV_MARTS
      threads: 4                        # models built at the same time
```

### F3. `~/datum/pipeline/dbt_project.yml`

**What this file is:** the project's control file. When you run `dbt build`, dbt reads this file first to learn three things: what the project is called, how to connect to Snowflake, and how to build each folder of models. Every dbt project has exactly one, and it sits at the project's root folder (`~/datum/pipeline/`).

**How to read YAML (the format of this file):**
- Each line is a `key: value` pair. The key is the setting's name, and the value is what you set it to.
- Indentation shows nesting. A line indented under another line belongs to it, like a sub-bullet in an outline. Use two spaces per level and never tabs.
- `#` starts a comment. dbt ignores everything from `#` to the end of the line.

```yaml
# ---------------------------------------------------------------------------
# PART 1: Who this project is
# ---------------------------------------------------------------------------

name: datum
# The project's name. dbt uses it in two places: in its log messages, and as
# the key under `models:` at the bottom of this file. Those two must match,
# so that dbt knows the settings at the bottom belong to this project.
# Lowercase letters and underscores only.

version: "0.1.0"
# OUR version label for this project. dbt doesn't use it for anything; it's
# a note for humans. The quotes make it text. Without them, YAML could try to
# read 0.1.0 as a number.

config-version: 2
# Which version of dbt's config-file FORMAT this file is written in. Version 2
# is the current format. This is dbt's version number, not ours. Always 2 for
# a modern project.

# ---------------------------------------------------------------------------
# PART 2: How to connect to Snowflake
# ---------------------------------------------------------------------------

profile: datum
# The name of a connection profile in ~/.dbt/profiles.yml (step F2).
# This file holds NO passwords or account details. It only names the profile,
# and dbt looks the profile up in your home folder, outside the repo.
# That separation is deliberate: this file goes into git and onto GitHub,
# while your credentials never do.

# ---------------------------------------------------------------------------
# PART 3: Where the models live
# ---------------------------------------------------------------------------

model-paths: ["models"]
# The folder dbt searches for models. A model is one .sql file containing
# one SELECT statement, and dbt turns each one into a view or table in
# Snowflake. The square brackets make this a LIST, because a project can
# have several model folders. We have one, "models", next to this file.

# ---------------------------------------------------------------------------
# PART 4: How to build each folder of models
# ---------------------------------------------------------------------------

models:
  # Everything below configures models. Settings apply by folder, so we don't
  # have to repeat them inside every .sql file.

  datum:
    # This must match `name: datum` at the top. It means "the models in THIS
    # project." (Packages you install later have their own names here.)

    staging:
      # Applies to every model in the folder models/staging/.
      # The staging layer cleans the raw data: it cuts each fixed-width line
      # into named columns. It contains no business logic.

      +schema: staging
      # Which Snowflake schema to build these models in. A schema is a folder
      # inside a database that holds tables and views.
      # dbt doesn't use "staging" as-is. It adds it after the base schema from
      # your profile (DEV), so the real schema is DEV_STAGING. The DEV_ prefix
      # keeps your development work separate from a future production schema.
      # The `+` means "this is a setting." Without it, dbt would read
      # `schema` as the name of a subfolder.

      +materialized: view
      # HOW dbt builds each model in Snowflake. Materialization is the dbt
      # word for "what kind of object gets created."
      #   view  = Snowflake saves only the SELECT statement and reruns it every
      #           time someone queries the view. It costs no storage and always
      #           shows the latest raw data.
      # Staging is a view because it's cheap and nobody queries it directly.

    marts:
      # Applies to every model in the folder models/marts/.
      # The marts layer is the final, shaped data that the app and your
      # lookups actually query.

      +schema: marts
      # Built in the schema DEV_MARTS (DEV + "_" + marts). This is why your
      # lookup query reads FROM datum.dev_marts.entity_lookup.

      +materialized: table
      #   table = Snowflake runs the SELECT once, during `dbt build`, and saves
      #           the result rows. Queries then read the saved rows directly,
      #           which is fast. The trade-off is that the data only updates
      #           when you run `dbt build` again.
      # Marts are tables because they get queried often and should answer fast.
```

**Concept: layers.** Data moves through three layers, each with one job:
1. **Raw** holds the source lines exactly as the state published them. COPY fills it, and dbt never changes it.
2. **Staging** cleans: it cuts lines into named columns and trims spaces.
3. **Marts** shape the data for a specific use, here looking up a company by name.

If something goes wrong, you can trace any value backward through the layers to the original line.

**Design decision: views for staging, tables for marts.** Staging is an intermediate step that nobody queries directly, so a view's free storage and always-current data win. Marts are what people and the app query, so storing the results makes every lookup fast. This is the standard dbt pattern, and the reason to follow it is cost: storage and compute are only spent where speed actually matters.

### F4. `~/datum/pipeline/models/staging/_sunbiz__sources.yml`

**What this file is:** a declaration of the tables dbt reads but did **not** build. Our models have to start from something, and that's the raw table you filled with COPY in step E. dbt didn't create it, so it doesn't know the table exists until this file declares it.

**How it connects:** the staging model (F5) reads the raw table through `{{ source('sunbiz', 'sunbiz_cor_daily') }}`. The two names inside `source()` come straight from this file: `sunbiz` is the source name, and `sunbiz_cor_daily` is the table name.

```yaml
# ---------------------------------------------------------------------------
# _sunbiz__sources.yml: tells dbt about tables that dbt did NOT build.
#
# dbt builds models (our .sql files). But our models have to start from
# somewhere, and here that's the raw table you filled with COPY in Snowflake
# (step E). dbt didn't create that table, so it doesn't know it exists until
# we declare it here. This file is that declaration.
#
# Once a table is declared, a model can refer to it as
#     source('sunbiz', 'sunbiz_cor_daily')   (wrapped in double curly braces)
# instead of hardcoding datum.raw.sunbiz_cor_daily. Two benefits:
#   1. If the table ever moves, you change it here, once, and every model
#      that uses it follows automatically.
#   2. dbt can draw the dependency graph: raw table → staging → mart. It uses
#      that graph to build things in the right order.
#
# File name: the leading underscore sorts it to the top of the folder, and
# "sunbiz__sources" (double underscore) is the common dbt naming convention
# for "<source system>__<what this file holds>".
# ---------------------------------------------------------------------------

version: 2
# The version of dbt's FORMAT for property files like this one. Always 2.
# (It's dbt's version number, not ours, the same idea as config-version
# in dbt_project.yml.)

sources:
# The start of a list of source systems. A project can read from several:
# Sunbiz now, DBPR (Department of Business and Professional Regulation)
# licenses later. Each one is an item in this list.

  - name: sunbiz
    # The `-` (dash) starts one item in a YAML list. This item is the Sunbiz
    # source system.
    # `name` is the label you use in SQL: the FIRST argument of source().
    # It's our label, not a Snowflake name. We picked "sunbiz" because
    # that's where the data comes from.

    database: datum
    # The Snowflake database where this source's tables live.

    schema: raw
    # The Snowflake schema inside that database. With the database above,
    # dbt now knows to look in datum.raw.

    tables:
    # The list of tables from this source that our models use.

      - name: sunbiz_cor_daily
        # One table. This name must match the real Snowflake table exactly,
        # because dbt combines it with the database and schema above:
        #     datum + raw + sunbiz_cor_daily  →  datum.raw.sunbiz_cor_daily
        # It's also the SECOND argument of source('sunbiz', 'sunbiz_cor_daily').

        description: One row per line of a Sunbiz daily corporate file, untouched.
        # Plain-English documentation. dbt shows it on the auto-generated
        # docs site (`dbt docs generate`). It doesn't change any behavior,
        # but it tells the next person what's in the table.
```

**Concept: sources vs. models.** A **source** is data that arrives from outside dbt (here, COPY loads it). A **model** is something dbt builds from a SELECT. dbt treats them differently: it never builds or changes a source; it only reads it.

**Design decision:** declare sources instead of hardcoding table names in SQL. The table's location then lives in one place, and dbt can see where the data starts. It uses that to build models in the right order and to draw the lineage graph (which table feeds which) in its docs.

### F5. `~/datum/pipeline/models/staging/stg_sunbiz__cor.sql`

**What this file is:** the **staging model**, the first transformation. It turns each unreadable 1440-character raw line into named columns. dbt saves it as the view `DATUM.DEV_STAGING.STG_SUNBIZ__COR`.

**How it connects:** it reads the raw table (declared in F4) and is read by the mart (F6).

```sql
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

with source as (
    -- STEP 1: read the raw table, just the three columns we need.
    select
        line,          -- the full 1440-character line from the state file
        source_file,   -- which file the line came from (provenance)
        loaded_at      -- when COPY loaded it (provenance)
    from {{ source('sunbiz', 'sunbiz_cor_daily') }}
    -- The double curly braces around source(...) mark Jinja, dbt's template
    -- language. dbt fills it in BEFORE sending the SQL to Snowflake.
    -- source() looks up the table declared in _sunbiz__sources.yml and
    -- becomes datum.raw.sunbiz_cor_daily.
    -- (Never write double curly braces inside a comment: dbt reads Jinja
    -- everywhere in a file, comments included.)
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

        source_file,
        loaded_at
        -- Carried through unchanged, so every value can be traced to the
        -- exact state file it came from.

    from source
    -- Read from STEP 1 above.

    where trim(line) <> ''
    -- Skip lines that are completely blank. <> means "not equal to".
)

-- STEP 3: the model's final output: every column from STEP 2.
select * from parsed
```

**Concept: fixed-width parsing.** Florida doesn't separate fields with commas. Instead, every field always sits at the same character positions. Parsing a fixed-width file means "take characters X through Y" for each field, which is exactly what `substr` does. The positions come from the state's published layout, and we confirmed them on a real file.

**Design decision:** staging only *cleans*; it doesn't *decide*. No filtering of damaged lines (they're flagged with `is_well_formed`), no deduplication, no matching. Those are choices about how the data gets *used*, so they belong in marts. Keeping staging this plain means that if a mart ever looks wrong, you can check staging and know you're looking at the source data faithfully cut into columns.

### F6. `~/datum/pipeline/models/marts/entity_lookup.sql`

**What this file is:** the **mart**, the table your lookups query. dbt saves it as the table `DATUM.DEV_MARTS.ENTITY_LOOKUP`.

**How it connects:** it reads the staging model (F5) through `ref()`, and the tests in F7 check it.

```sql
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

    source_file,
    loaded_at
    -- Provenance stays with every row, even in the final layer, so any fact
    -- Datum ever shows can be traced to the exact state file.

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
    order by loaded_at desc
) = 1
-- Keep exactly one row per company. Read it in pieces:
--   row_number()            numbers rows 1, 2, 3, ...
--   over ( ... )            ... but within the groups defined inside:
--   partition by document_number
--                           one group per company (restart numbering at 1
--                           for each document_number)
--   order by loaded_at desc number each group newest first (desc = descending)
--   = 1                     keep row number 1: the newest row per company
--   qualify                 filters on that number. It's like WHERE, but WHERE
--                           can't see window functions like row_number();
--                           QUALIFY can.
-- Why: once you load more daily files, the same company can appear several
-- times (for example, when its status changes). The lookup should show the
-- latest version, once.
```

**Concept: `ref()` and the DAG.** Every `ref()` tells dbt that this model depends on that one. dbt collects all of those into a **DAG** (directed acyclic graph): a map of what feeds what, with no loops. `dbt build` walks that map in order: source → staging → mart → tests. You never tell dbt the order yourself; it works it out from `ref()` and `source()`.

**Design decision:** deduplicate in the mart, not in staging. Staging keeps every row it receives, so history isn't lost. The mart answers "what is this company *now*?", so it keeps one row per company. If we later need "what changed over time," a different mart can read the same staging data without the dedupe.

### F7. `~/datum/pipeline/models/marts/_marts.yml`

**What this file is:** the **tests** for the mart. After `dbt build` creates `entity_lookup`, it runs these checks against it automatically.

**How it connects:** each test names a model (`entity_lookup`) and a column. dbt turns each one into a small SQL query that searches for rows that break the rule.

```yaml
# ---------------------------------------------------------------------------
# _marts.yml: TESTS for the mart models.
#
# What a dbt test is: an automatic check that dbt runs after building a model.
# Under the hood, each test is a SQL query that looks for BAD rows:
#   - it finds zero bad rows → the test PASSES
#   - it finds any           → the test FAILS, and `dbt build` reports it and
#                              skips anything that depends on the bad model
#
# Why tests matter here: Datum's promise is being right about who a company
# is. These tests are the first automatic guard on that promise. If one
# company ever showed up twice, a lookup could return two conflicting answers.
# ---------------------------------------------------------------------------

version: 2
# dbt's property-file format version. Always 2.

models:
# A list of models we're describing. Each item names one model and its checks.

  - name: entity_lookup
    # Which model these tests apply to. It must match the file name
    # entity_lookup.sql, without the .sql.

    columns:
    # The columns we're putting tests on.

      - name: document_number
        data_tests:
        # The checks for this column. (`data_tests:` is the current dbt
        # name; older guides call it `tests:`.)

          - not_null
          # Fails if any row has an empty document_number. Every company
          # must have its ID.

          - unique
          # Fails if any document_number appears more than once. This proves
          # the one-row-per-company step in entity_lookup.sql actually worked.

      - name: status_code
        data_tests:
          - accepted_values:
              arguments:
                values: ['A', 'I']
          # Fails if status_code holds anything other than A (active) or
          # I (inactive). An unexpected value usually means the field
          # positions shifted, so this test also guards the parsing.
          # `arguments:` holds the test's settings. dbt 2.0 requires this
          # nesting; older dbt let `values:` sit directly under the test name.
```

**Concept: tests are queries that look for bad rows.** `unique` on `document_number` becomes, roughly, "find any document_number that appears more than once." Zero results means pass. Because dbt runs tests as part of every build, a broken assumption stops the pipeline instead of reaching a contractor.

**Design decision:** start with three cheap tests that guard what the lookup depends on: every row has an ID, no company appears twice, and status is a known value. This connects to the evaluation chapters of your reading (Chip Huyen): these tests check *data* quality. *Matching* accuracy (the 90% bar on the 50-name test set) is a separate evaluation we build later.

## G. Build (VS Code terminal)

**What this step does:** dbt reads every file above, works out the build order, creates the view and the table in Snowflake, then runs the tests.

```bash
cd ~/datum/pipeline     # move into the dbt project folder
dbt debug               # check the setup before building anything
dbt build               # build every model and run every test, in dependency order
```

| Piece | Meaning |
|---|---|
| `cd` | **C**hange **d**irectory: move the terminal into a folder. |
| `~/datum/pipeline` | `~` = `/Users/anfelca2`. dbt must run from the folder containing `dbt_project.yml`, or it won't find the project. |
| `dbt debug` | A health check. It confirms that `dbt_project.yml` is valid, that the `datum` profile exists in `~/.dbt/profiles.yml`, and that dbt can actually connect to Snowflake. It builds nothing. Run it first, so a connection problem shows up clearly on its own. |
| `dbt build` | Does everything, in DAG order: builds `stg_sunbiz__cor` (a view), then `entity_lookup` (a table), then runs its 3 tests. If a test fails, anything downstream of it is skipped. |

**What success looks like** (🟡 exact wording varies by dbt version):
- `dbt debug` ends with `All checks passed!`
- `dbt build` ends with something like `Completed successfully` and `PASS=5 WARN=0 ERROR=0 SKIP=0 TOTAL=5`: 2 models + 3 tests = 5.

If anything says `ERROR` or `FAIL`, paste the full output. The error message names the exact file and line.

## H. Lookup (Snowflake worksheet)

**What this step does:** the known-answer test for the whole path. DINATALE VENTURES LLC is line 1 of the file you downloaded. If it comes back from the mart, the data made it through every layer intact: file → stage → raw → staging → mart.

```sql
SELECT document_number,           -- the company's state ID
       entity_name,               -- legal name as filed
       status_code,               -- A active, I inactive
       filing_type,               -- FLAL = Florida LLC
       principal_city,            -- main business address city
       source_file                -- which state file this row came from
FROM datum.dev_marts.entity_lookup    -- the mart table dbt built in G
WHERE name_key LIKE '%DINATALE%'      -- name contains DINATALE anywhere
LIMIT 20;                             -- return at most 20 rows
```

| Piece | Meaning |
|---|---|
| `FROM datum.dev_marts.entity_lookup` | database `datum`, schema `dev_marts`, table `entity_lookup`. The schema name is `DEV` + `_` + `marts`, from dbt's naming rule. Snowflake ignores upper/lower case here. |
| `WHERE` | Keep only rows that meet the condition. |
| `LIKE '%DINATALE%'` | Pattern match. `%` means "any characters, or none," so this finds DINATALE anywhere in `name_key`. |
| `LIMIT 20` | Return at most 20 rows. A safety habit when exploring, so a broad search can't flood the screen. |

**Done when:** one row comes back: DINATALE VENTURES LLC, document number L26000514010, status A, filing type FLAL, source file `sunbiz_stage/20261009c.txt`.

**Concept: a known-answer test.** You picked an answer you already know (line 1 of the file), then checked that the system returns it. It's the simplest version of the 50-name test set you'll build later. That set is the same idea, just 50 known answers instead of one.

## Then commit (VS Code terminal)

```bash
cd ~/datum && git add -A && git commit -m "pipeline: first Sunbiz daily file end to end"   # stage all changes, then save a snapshot
```

## Later, not needed for this slice

```bash
brew install pipx              # installs Python command-line apps in isolated environments
pipx ensurepath                # puts pipx's apps folder on your PATH
pipx install snowflake-cli     # the `snow` command, for scripted uploads (PUT) and scheduled loads
```
