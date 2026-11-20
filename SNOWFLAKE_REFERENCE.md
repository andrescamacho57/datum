# Snowflake Reference — Datum

Running reference for Snowflake on Datum. Appended to as we go.
Concepts (why) live in `CONCEPTS.md`; this file is the how.
**I run SQL from VS Code** (Snowflake extension or `snow sql`), not Snowsight
worksheets. Scripts live in `snowflake/`, numbered in run order.

---

## Datum's Objects

```
Account (<org>-<account>)
├── Warehouse  DATUM_WH            X-Small, 60s auto-suspend, under DATUM_MONTHLY
├── Resource monitor DATUM_MONTHLY 10 credits/month, notify 80%, suspend 100%
└── Database   DATUM
    ├── Schema RAW
    │   ├── File format FIXED_WIDTH          one field per line, Latin-1
    │   ├── Stage SUNBIZ_STAGE               daily corporate files
    │   ├── Stage SUNBIZ_COR_QUARTERLY_STAGE quarterly full snapshot
    │   └── Table SUNBIZ_COR_DAILY           line, source_file, loaded_at
    ├── Schema DEV_STAGING   (built by dbt)  view STG_SUNBIZ__COR
    └── Schema DEV_MARTS     (built by dbt)  table ENTITY_LOOKUP
```

**Fully qualified name:** `database.schema.object` → `datum.raw.sunbiz_cor_daily`.
Unquoted names are stored UPPERCASE; `datum` and `DATUM` are the same object.

---

## Scripts (run in order)

| Script | Does | Run |
|---|---|---|
| `01_cost_guardrails.sql` | Resource monitor + warehouse | Once, ACCOUNTADMIN for the monitor |
| `02_raw_layer.sql` | Database, schema, file format, daily stage, raw table | Once, SYSADMIN |
| `03_load_sunbiz_cor_daily.sql` | COPY daily file(s) into raw + checks | After each upload |
| `04_sunbiz_cor_quarterly_stage.sql` | Stage for the full snapshot | Once |
| `05_validate_entity_lookup.sql` | Known-answer check on the mart | After `dbt build` |

Run a script from the VS Code terminal:
```bash
snow sql -c datum -f snowflake/03_load_sunbiz_cor_daily.sql
```

---

## Context (always first)

```sql
USE ROLE SYSADMIN;        -- the role that owns DATUM
USE WAREHOUSE datum_wh;   -- the capped warehouse. COMPUTE_WH bypasses the monitor
```

Resource monitors need **ACCOUNTADMIN** to create. Everything else: **SYSADMIN**.

---

## Cost Guardrails

```sql
CREATE RESOURCE MONITOR datum_monthly
  WITH CREDIT_QUOTA = 10 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;

CREATE WAREHOUSE datum_wh
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

ALTER WAREHOUSE datum_wh SET RESOURCE_MONITOR = datum_monthly;
```

`SUSPEND` lets running queries finish; `SUSPEND_IMMEDIATE` kills them.

---

## File Format for Fixed-Width Lines

```sql
CREATE FILE FORMAT datum.raw.fixed_width
  TYPE = CSV                        -- closest built-in to "plain text lines"
  FIELD_DELIMITER = NONE            -- never split a line
  ESCAPE_UNENCLOSED_FIELD = NONE    -- backslashes are ordinary characters
  ENCODING = 'ISO-8859-1';          -- one byte per character, positions stay exact
```

---

## Stage, PUT, LIST

```sql
CREATE STAGE datum.raw.sunbiz_stage FILE_FORMAT = datum.raw.fixed_width;
LIST @datum.raw.sunbiz_stage;       -- what files are waiting
REMOVE @datum.raw.sunbiz_stage/20261009c.txt.gz;   -- delete a staged file
```

PUT runs from the **VS Code terminal**, not a worksheet:
```bash
snow sql -c datum -q "PUT file://$PWD/cordata*.txt @datum.raw.sunbiz_cor_quarterly_stage AUTO_COMPRESS=TRUE PARALLEL=8"
```
- `file://` + an absolute path (`$PWD` fills in the current folder)
- `*` matches all ten `cordata0.txt`…`cordata9.txt`
- `AUTO_COMPRESS=TRUE` gzips during upload (default is TRUE)
- `PARALLEL=8` uses 8 upload threads (default 4, max 99). Large files are split
  into chunks and the threads send chunks concurrently. Home upload speed caps
  the benefit
- Result shows each file as `UPLOADED` or `SKIPPED` (already there)

---

## COPY with a Transform

```sql
COPY INTO datum.raw.sunbiz_cor_daily (line, source_file, loaded_at)
FROM (
  SELECT $1, METADATA$FILENAME, CURRENT_TIMESTAMP()
  FROM @datum.raw.sunbiz_stage
);
```
- `$1` — the first (only) field of each line
- `METADATA$FILENAME` — the staged file's name: free provenance
- Safe to rerun: load metadata skips files loaded in the last 64 days

**Validate before loading** (dry run, loads nothing):
```sql
COPY INTO ... FROM @stage VALIDATION_MODE = RETURN_ERRORS;
```

---

## Validating a Load

```sql
SELECT COUNT(*) AS line_count,
       MIN(LENGTH(line)) AS shortest,
       MAX(LENGTH(line)) AS longest
FROM datum.raw.sunbiz_cor_daily;
-- daily: 834 / 1440 / 1440
```

Per-file counts:
```sql
SELECT source_file, COUNT(*) FROM datum.raw.sunbiz_cor_daily GROUP BY 1 ORDER BY 1;
```

Load history (what COPY did, per file):
```sql
SELECT file_name, row_count, row_parsed, first_error_message, last_load_time
FROM TABLE(information_schema.copy_history(
  table_name => 'DATUM.RAW.SUNBIZ_COR_DAILY',
  start_time => DATEADD(day, -7, CURRENT_TIMESTAMP())));
```

---

## Known-Answer Check

```sql
SELECT document_number, entity_name, status_code, filing_type, principal_city, source_file
FROM datum.dev_marts.entity_lookup
WHERE name_key LIKE '%DINATALE VENTURES%';
-- L26000514010 | DINATALE VENTURES LLC | A | FLAL | PALM BEACH GARDENS | 20261009c.txt
```

---

## Useful Functions

| Function | Does |
|---|---|
| `substr(s, start, len)` | Piece of text; positions start at 1 |
| `trim(s)` | Remove leading/trailing spaces |
| `length(s)` | Number of characters |
| `try_to_date(s, 'MMDDYYYY')` | Text → date, NULL instead of an error |
| `nullif(x, '')` | NULL when x is empty |
| `upper(s)` | Uppercase |
| `regexp_replace(s, pattern, repl)` | Replace every regex match |
| `row_number() over (...)` | Number rows within groups |
| `count_if(cond)` | Count rows where cond is true |

---

## Gotchas

- **PUT doesn't work in a worksheet.** It needs a client on your machine.
- **Snowflake can't read .zip.** Unzip first (or gzip, which it reads natively).
- **Worksheets default to COMPUTE_WH**, which isn't under the resource monitor.
  Always `USE WAREHOUSE datum_wh`.
- **LENGTH counts NUL bytes.** Both daily (LF) and quarterly (CRLF) lines load as 1440:
  the default record delimiter strips `\r\n` as one line ending (verified 2026-10-22).
- **Load metadata expires after 64 days** — after that, COPY would reload a file.
- **Trial ends ~Nov 15** with ~$362 credit left. Decide on upgrade before then.

---

## CLI: `snow`

Installed with `pipx install snowflake-cli --python python3.12` (v3.30.0).
Connection `datum` in `~/.snowflake/connections.toml` (key-pair, SYSADMIN, DATUM_WH).

```bash
snow connection test -c datum            # prove the connection works
snow sql -c datum -q "SELECT 1"          # run one statement
snow sql -c datum -f path/to/file.sql    # run a script
```

---

## Not Yet Used (add detail when we get there)

- Streams and Tasks (automated incremental loads)
- Snowpipe (auto-load files as they land)
- Search optimization / clustering (if name lookups get slow at 13M rows)
- PROD schemas and a read-only role for the app
