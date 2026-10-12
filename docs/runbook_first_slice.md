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
| E | COPY the stage into the raw table | Snowflake worksheet | ⏭ |
| F | Create the dbt project files | VS Code | ⏭ |
| G | `dbt debug` and `dbt build` | VS Code terminal | ⏭ |
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
      account: <your_account_identifier>   # copy from a profile that already works
      user: <your_username>
      authenticator: externalbrowser    # browser login; no password stored
      role: SYSADMIN
      warehouse: DATUM_WH
      database: DATUM
      schema: DEV                       # custom schemas are added after it: DEV_STAGING, DEV_MARTS
      threads: 4                        # models built at the same time
```

### F3. `~/datum/pipeline/dbt_project.yml`

```yaml
name: datum                             # project name
version: "0.1.0"
config-version: 2
profile: datum                          # which profiles.yml entry to use
model-paths: ["models"]                 # where models live
models:
  datum:
    staging:
      +schema: staging                  # → DEV_STAGING
      +materialized: view               # cheap, always current
    marts:
      +schema: marts                    # → DEV_MARTS
      +materialized: table              # stored, fast to query
```

### F4. `~/datum/pipeline/models/staging/_sunbiz__sources.yml`

```yaml
version: 2
sources:
  - name: sunbiz                        # used as source('sunbiz', ...)
    database: datum
    schema: raw
    tables:
      - name: sunbiz_cor_daily          # raw table from A2
        description: One row per line of a Sunbiz daily corporate file, untouched.
```

### F5. `~/datum/pipeline/models/staging/stg_sunbiz__cor.sql`

```sql
-- Layout: docs/access/sunbiz.md. Positions confirmed on a real file 2026-10-12.
with source as (
    select line, source_file, loaded_at
    from {{ source('sunbiz', 'sunbiz_cor_daily') }}          -- compiles to datum.raw.sunbiz_cor_daily
),

parsed as (
    select
        trim(substr(line, 1, 12))                     as document_number,     -- 1–12: state company ID
        trim(substr(line, 13, 192))                   as entity_name,         -- 13–204: legal name
        substr(line, 205, 1)                          as status_code,         -- 205: A active, I inactive
        trim(substr(line, 206, 15))                   as filing_type,         -- 206–220: FLAL, DOMP, ...
        trim(substr(line, 221, 42))                   as principal_address_1, -- 221–262
        trim(substr(line, 305, 28))                   as principal_city,      -- 305–332
        trim(substr(line, 333, 2))                    as principal_state,     -- 333–334
        trim(substr(line, 335, 10))                   as principal_zip,       -- 335–344
        try_to_date(substr(line, 473, 8), 'MMDDYYYY') as file_date,           -- 473–480; meaning unverified (see recon note)
        nullif(trim(substr(line, 481, 14)), '')       as fei_number,          -- 481–494: federal tax ID; blank → null
        length(line) >= 1436                          as is_well_formed,      -- full layout present (with or without NUL padding)
        source_file,
        loaded_at
    from source
    where trim(line) <> ''                                                    -- skip empty lines
)

select * from parsed
```

### F6. `~/datum/pipeline/models/marts/entity_lookup.sql`

```sql
select
    document_number,
    entity_name,
    trim(regexp_replace(upper(entity_name), '[^A-Z0-9]+', ' ')) as name_key,  -- uppercase; runs of symbols → one space
    status_code,
    filing_type,
    principal_city,
    principal_state,
    file_date,
    source_file,                                    -- provenance carried to the queryable layer
    loaded_at
from {{ ref('stg_sunbiz__cor') }}                   -- depend on the staging model
where is_well_formed                                -- only rows with a trusted layout
qualify row_number() over (
    partition by document_number                    -- each company's rows together
    order by loaded_at desc                         -- newest first
) = 1                                               -- one row per company
```

### F7. `~/datum/pipeline/models/marts/_marts.yml`

```yaml
version: 2
models:
  - name: entity_lookup
    columns:
      - name: document_number
        data_tests:
          - not_null                    # every row has an ID
          - unique                      # no company twice
      - name: status_code
        data_tests:
          - accepted_values:
              values: ['A', 'I']        # only active or inactive
```

## G. Build (VS Code terminal)

```bash
cd ~/datum/pipeline                     # run dbt from the folder with dbt_project.yml
dbt debug                               # checks the profile, the connection and the project
dbt build                               # builds the models, then runs their tests in dependency order
```

If dbt 1.10+ warns about `arguments:`, nest `values:` under an `arguments:` key in F7.

## H. Lookup (Snowflake worksheet)

```sql
SELECT document_number, entity_name, status_code, filing_type, principal_city, source_file
FROM datum.dev_marts.entity_lookup          -- DEV + _MARTS, from dbt's naming rule
WHERE name_key LIKE '%DINATALE%'            -- line 1 of the file; a known-answer test
LIMIT 20;
```

**Done when:** H returns DINATALE VENTURES LLC, document number L26000514010, status A, filing type FLAL.

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
