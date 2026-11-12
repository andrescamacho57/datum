# Florida master brief (for Fable 5.2 in Claude Code)

Kickoff line Andres types: `Read docs/prompts/florida_master.md. Run Phase A only.`
Later: `Run Phase B.` then `Run Phase C.` Never start a phase you weren't told to run.

## 1. What you're building and for whom

Datum checks a small trade contractor's commercial client before a job: is it a real, active Florida company, and what's on the public record against it? You are building the Florida data pipeline and app. Andres Camacho owns the repo. He is learning data engineering through this project, so he reviews every leg and must be able to explain what you built. Write for that reader.

## 2. Read these first

- `CLAUDE.md` (rules and the commands that prove work)
- `docs/mvp_plan_nov8.md` (spec A1–A12, decisions d15–d21, architecture, flags table). Its dates are targets, not deadlines. Never cut scope to hit a date.
- `docs/access/sunbiz_flr.md` (federal lien layouts and verified counts)
- `snowflake/01`–`12` and `pipeline/models/` (the style to match)

## 3. Rules for every leg

**Git**
- One branch per leg, named `leg/a1-federal-liens` and so on. One pull request per leg with `gh pr create`. Never commit to `main`, never merge, never force-push.
- One concern per commit, with its test.

**Code style**
- Snowflake SQL goes in `snowflake/` as the next numbered script (the next free number is 13). Run it with `snow sql -c datum -f snowflake/NN_name.sql`.
- Comment every line. End each SQL script with `-- Syntax`, `-- Concept` and `-- Design decision` sections, like scripts 01–12. dbt models get the same header-and-inline style as `stg_sunbiz__cor.sql`.
- Raw = one `line` (or one column per field for delimited files) plus `source_file` and `loaded_at`. Staging names and types the fields. Never change or drop existing tables, models or seeds; only add.

**Safety**
- Never read, print or edit `.env`, `~/.dbt/profiles.yml`, `~/.snowflake/` or `*.p8`. Python reads secrets with `load_dotenv()`; nothing else touches them.
- `data/` is gitignored. Raw data never goes to git.
- Businesses only. Records about individuals may sit in raw and staging, and go no further: no intermediate model, mart, report or sample file may contain a person's name. Keep criminal judgments out of everything past staging.
- Inspect before loading: count lines, check record lengths or delimiters, and compare to the source's own totals before any `COPY`.

**Cost**
- Use only warehouse `datum_wh` (X-Small). Don't resize it, create another, or change the resource monitor.
- After each leg, record credits used (query `snowflake.account_usage.warehouse_metering_history` or `information_schema`) in the leg report.
- No new paid services or accounts.

**When to stop**
- A check still fails after two fix attempts: stop that leg, write the report with what failed, and move to the next independent leg.
- You need a credential, a login, a purchase or a product decision: stop and ask in the leg report.
- Anything about a source's terms of use, or the FCRA (Fair Credit Reporting Act): stop and flag it. Don't decide it.

**Leg report**: for every leg, write `docs/legs/<leg-name>.md` and put the same text in the pull request body:
1. What I built (files, tables, models), in plain English a new engineer could repeat out loud
2. Checks: each check, the command, and its pasted output
3. Decisions I made and why, with the tradeoff
4. What I couldn't verify, and open questions for Andres
5. Credits used
6. Three questions Andres should be able to answer after reviewing

## 4. Phase A: three sources, raw to staging

The three legs are independent. Run them one after another, each on its own branch from `main`.

### A1. Federal tax liens (Sunbiz)

Files are already in `data/raw/sunbiz/flr/`: quarterly `FLRF.TXT`, `FLRD.TXT`, `FLRE.TXT`, `FLRS.TXT` (upper case; globs are case-sensitive) and the `20261104` dailies.

Build:
- `snowflake/13_federal_liens_raw.sql`: 4 stages and 4 raw tables in `datum.raw` (`sunbiz_flr_filings`, `_debtors`, `_events`, `_secured`), reusing the `fixed_width` file format and `METADATA$FILENAME`. Each table holds quarterly and daily rows. `PUT` the 8 files with `snow sql -c datum -q "PUT ..."`.
- dbt sources plus `stg_sunbiz__flr_filings`, `_debtors`, `_events`, `_secured`, cut by the positions in `docs/access/sunbiz_flr.md`. Dates with `TRY_TO_DATE(x, 'MMDDYYYY')`. Add `source_kind` and `published_on` the way `stg_sunbiz__cor` does (quarterly snapshot date 2026-10-03).
- `stg_sunbiz__flr_debtors` keeps only `name_format = 'C'` (corporate).

Done when:
| Table | Quarterly rows | Daily 20261104 rows | Line length |
|---|---|---|---|
| filings | 20,444 | 42 | 82 |
| debtors | 22,173 | 46 | 206 |
| events | 97,256 | 29 | 135 |
| secured | 20,448 | 42 | 206 |
- dbt tests pass: `not_null` and `unique` on the filing document number per source file; `accepted_values` A/L/T on status; a `warn`-severity test that assessment and expiration years fall in 1990–2040 (28 known bad rows).
- Every `COR` event in the daily file joins to a filing in the snapshot (29 of 29).

### A2. DBPR (Department of Business and Professional Regulation) contractor licenses

Recon first, then build. Known starting points (verify them; don't trust them):
- Construction licensee extract: `https://www2.myfloridalicense.com/sto/file_download/extracts//CONSTRUCTIONLICENSE_1.csv`
- Discipline reports: `contractor_disc_lic_[fiscal year].csv` under `/pro/cilb/reports/`
- The licensee file is reported to exclude delinquent and involuntarily inactive licenses. Confirm and document.

Build:
- `docs/access/dbpr.md`: where the files are, the layout, update cadence, what's excluded, and what the site's terms and robots rules say about automated download. If they forbid it, stop and report.
- `src/datum/dbpr.py`: a small `DbprFile` class that downloads a file to `data/raw/dbpr/`, then validates it before anything is loaded (expected header, column count on every row, row count). One request per file, no retries in a loop.
- Next numbered Snowflake script: a CSV file format, stage, raw tables, `COPY`.
- `stg_dbpr__licenses` and `stg_dbpr__discipline`, with tests.

Done when:
- Rows in each raw table = data lines in the file (file lines minus header). Paste both numbers.
- License number is `not_null`; duplicates are either zero or explained in the report.
- The report states how many licenses are business-held versus individual-held, and which column tells them apart.

### A3. Duval County recorded documents

What's known (from four sample files Andres pulled by hand):
- Site `https://ftp.duvalclerk.com`, folder `Recording Indexes`. One set of files per day since 2019-07-31, published about 3 AM the next day.
- Pipe-delimited text, CRLF line endings, each file ends with a trailer `EOF|<row count>`. A 7-byte file is `EOF|0` (nothing recorded).
- `dYYYYMMDD01id.16` documents: `DDA|16|instrument|type code|type name|legal description|OR|book|page||pages|record date MM/DD/YYYY|time|amount|`
- `pYYYYMMDD01id.16` parties: `DPA|16|instrument|seq|FRM or TO|name|`
- `lYYYYMMDD01id.16` links: `instrument|book|page|OR|type|linked instrument|book|page|OR|linked type` (`NONE` when no link). A `RELEASE` linked to an `LN` means that lien was released.
- `mYYYYMMDD01d.16` document-type lookup: `code|family|`
- Daily files can contain old instrument numbers (re-indexing). Don't assume a file's date equals the recording date.

Access: Andres has put `DUVAL_FTP_USER` and `DUVAL_FTP_PASSWORD` in `.env`. Your download script reads them with `load_dotenv()` and never prints them. Work out the transfer protocol (try SFTP, then FTPS) with at most two attempts each. If neither works, stop and report; don't probe further. Use one connection, sequential downloads, and a short pause between files.

Scope: files dated 2025-01-01 onward.

Build:
- `docs/access/duval-recording-index.md`: protocol, file kinds, layouts, counts.
- `src/datum/duval.py`: download to `data/raw/duval/`, then verify every file's row count against its `EOF` trailer before loading. A mismatch fails that file loudly.
- Next numbered Snowflake script: pipe-delimited file format, 4 stages, 4 raw tables.
- `stg_duval__documents`, `stg_duval__parties`, `stg_duval__links`, `stg_duval__doc_types`, with tests (`not_null` instrument; relationships from parties and links to documents, `warn` severity because of re-indexed rows).

Done when:
- For every loaded file: rows loaded = its `EOF` count. Report the totals and any mismatches.
- The report lists document counts by type family for liens, judgments, releases, satisfactions, notices of commencement and lis pendens.
- The report says what share of party names look like businesses (LLC, INC, CORP and similar) versus individuals. This is a count only; write no names in the report.

Flag in the report, don't resolve: the Clerk has not yet answered whether terms of use apply to this data. Nothing from Duval is shown to anyone outside this repo until Andres says so.

## 5. Phase B: link to companies, then flags (only when told)

- Intermediate models that link federal lien debtors to `entity_lookup` on normalized name plus ZIP5, and Duval business parties on normalized name. Outcome per link: CONFIRMED, AMBIGUOUS or NO_MATCH (decision d19). Duval has no addresses, so a Duval link is CONFIRMED only when exactly one active Florida entity has that normalized name.
- Open-lien logic: a federal lien is active if it's in the latest snapshot or a later daily filing, and no later `COR` event exists. A Duval lien is open if no release or satisfaction links to it.
- A flags mart per the flags table in the plan, CONFIRMED links only, each row carrying its source and record identifiers for citation.
- `evals/link_sample_20.csv`: 20 random CONFIRMED links (businesses only) for Andres to hand-check. Done when he finds 0 wrong.
- Draft 40 more lookup test cases from real lien debtor and license names into a file for Andres to verify. Don't add them to `pipeline/seeds/test_set.csv` yourself.

## 6. Phase C: serving and app (only when told)

Per the plan, Days 5–8: Postgres with `pg_trgm` for lookups, FastAPI + Jinja + Pico CSS (search → shortlist → report with cited flags), offline tests with a fake backend, GitHub Actions running ruff and pytest. Stop and ask before creating any hosted account or spending money; deployment waits for Andres.
