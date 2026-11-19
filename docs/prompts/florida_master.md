# Florida master brief (for Fable 5.2 in Claude Code)

Kickoff line Andres types: `Read docs/prompts/florida_master.md. Run Phase A only.`
Later: `Read docs/prompts/florida_master.md. Run Phase B.` then `Run Phase C.` Never start a phase you weren't told to run.
Phase A finished Nov 12, 2026 (three legs, reports in `docs/legs/`).

## 1. What you're building and for whom

Datum checks a small trade contractor's commercial client before a job: is it a real, active Florida company, and what's on the public record against it? You are building the Florida data pipeline and app. Andres Camacho owns the repo. He is learning data engineering through this project, so he reviews every leg and must be able to explain what you built. Write for that reader.

## 2. Read these first

- `CLAUDE.md` (rules and the commands that prove work)
- `docs/mvp_plan_nov8.md` (spec A1–A12, decisions d15–d21, architecture, flags table). Its dates are targets, not deadlines. Never cut scope to hit a date.
- `docs/access/sunbiz_flr.md` (federal lien layouts and verified counts)
- `snowflake/01`–`12` and `pipeline/models/` (the style to match)
- `docs/phase_b_rulings.md` (decided Nov 18; binding from Phase B on) and `docs/open_questions.md`
- `docs/legs/` (your own Phase A reports)

## 3. Rules for every leg

**Git**
- One branch per leg, named `leg/a1-federal-liens` and so on. One pull request per leg with `gh pr create`. Never commit to `main`, never merge, never force-push.
- One concern per commit, with its test.

**Code style**
- Snowflake SQL goes in `snowflake/` as the next numbered script (Phase A used 13–15, so the next free number is 16). Run it with `snow sql -c datum -f snowflake/NN_name.sql`.
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

**Review before the pull request** (see `REVIEW.md` and `docs/review_process.md`)
- When the leg's checks pass, set its risk tier from the table in `REVIEW.md`. The highest tier of any file it touches wins.
- Review the leg's diff in a fresh context with the `reviewer` subagent, which runs on Opus so the reviewer is a different model from the author:
  - Low: one pass.
  - Medium: one pass, plus `/security-review` when `src/` changed.
  - High: three `reviewer` subagents in parallel, each told to hunt one thing (a wrong link or wrong status; a person's data past staging; a test that cannot fail). Then a fourth checks every finding against the code and drops any it cannot confirm with a file and line.
- Fix every `Important` finding, or answer it with a one-line reason. Review again, looking only at the new diff. Three rounds at most; if `Important` findings remain after the third, stop the leg and say so in the report.
- Open the pull request with `.github/pull_request_template.md` filled in, then the leg report below it.
- Add one row for the pull request to `docs/review_log.csv`.
- Never ask a question or wait for approval during review.

**Leg report**: for every leg, write `docs/legs/<leg-name>.md` and put the same text in the pull request body:
1. What I built (files, tables, models), in plain English a new engineer could repeat out loud
2. Checks: each check, the command, and its pasted output
3. Decisions I made and why, with the tradeoff
4. What I couldn't verify, and open questions for Andres
   (include the review: tier, depth, rounds, and each finding with how it was answered)
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

## 5. Phase B: close the gaps, link to companies, then flags (only when told)

Read `docs/phase_b_rulings.md` before anything else. Its rulings R1–R26 are decided, and each bullet below names the ones it implements. Don't reopen them and don't ask about them. If the data contradicts a ruling, follow the ruling, and report the contradiction with counts in the leg report.

Run unattended. Never stop to ask a question or wait for approval. When something is unclear, take the most cautious reading (the one that shows less on a report), write the assumption in the leg report, and keep going. The stop conditions in section 3 still apply.

Four legs, in order. Each leg depends on the one before it, so stack the branches: `leg/b0-close-gaps` from `main`, `leg/b1-links` from `leg/b0-close-gaps`, and so on. One pull request per leg, each targeting `main`. Andres merges them in order.

Paths: the repo is at `~/Work Streams/datum`, and `~/datum` is a symbolic link to it. Use `~/datum` in commands so no path contains a space.

### B0. Close the Phase A gaps

- **Duval repair (R15).** For the 13 files in `data/raw/duval/rejected/`: write a repaired copy to `data/raw/duval/repaired/` with the same file name. Join a line that doesn't start with the record prefix to the line above it with one space; drop blank lines. The repaired row count must equal the `EOF` trailer, or the file stays out. Extend `duval.py` and its tests (a fixture with a broken record). `PUT` and `COPY` the repaired files with the next numbered script. Add a "Repaired files" section to `docs/access/duval-recording-index.md`.
- **Federal lien dailies (R8).** Download every daily `flrf`, `flrd`, `flre` and `flrs` file published since 2026-10-03 from the state's SFTP (secure file transfer protocol) server, using the public login the state publishes (see `docs/access/sunbiz.md`). Put the download in a small `src/datum/sunbiz_flr.py` with tests. Inspect line lengths before loading, then `PUT` and `COPY` into the existing four tables. One connection, sequential, a short pause between files.
- **Fetch manifest (R23).** Each downloader (`dbpr.py`, `duval.py`, `sunbiz_flr.py`) writes one manifest row per file. Load it into `datum.raw.fetch_manifest`, with a staging view. Backfill files already on disk from their modification time with `is_approximate = true`.
- **`requirements.txt` (R24)** with exact versions from the working environment.
- **DBPR header check (R25)** in `validate()`, with a fixture that must be rejected.

Done when:
- Every Duval file dated 2025-01-01 onward is loaded and equals its `EOF` count (2,716 files as of 2026-11-11; report the number). The two `relationships` tests report 0 orphans, or the remainder is counted and explained.
- Lien dailies: a table of file date by rows loaded for each of the four kinds, every line the documented length, and missing business days listed. Every daily `COR` event joins to a filing in the snapshot or in an earlier daily; report found and missing.
- `fetch_manifest` has one row per loaded file across the three sources. Paste the count per source next to the count of distinct `source_file` values in raw.
- `pytest` and `ruff check src tests` pass.

### B1. Link models (R1–R4, R11, R13, R14, R17, R19)

Add `+schema: intermediate` in `dbt_project.yml`. Models in `pipeline/models/intermediate/`:
- `int_company_match_keys`: one row per company from `entity_lookup` with `match_key` (the `name_key` minus a trailing legal suffix), ZIP5, status, filing date, and `match_key_company_count` across all statuses.
- `int_federal_lien_links`: corporate debtors → companies.
- `int_dbpr_license_links`: licenses → companies through `dba_name`; `QB` rows through their own name.
- `int_dbpr_discipline_links`: discipline → license → company. The words-to-code map is a seed (R14).
- `int_duval_party_links`: TO-side parties on allowlisted documents (R16) → companies. Unique-name branch only (R3).

Every link model has the same columns: the source record's identifier, `document_number`, `link_status` (CONFIRMED, AMBIGUOUS, NO_MATCH), `matched_on` (`name_zip` or `unique_name`), and the source's date. No raw source name (R4).

Tests: `accepted_values` on `link_status`; `relationships` to `entity_lookup` for every non-NO_MATCH row; a singular test that fails if any column named like a name exists in an intermediate model other than `int_company_match_keys`; a singular test for R2 (no CONFIRMED link dated before the company's filing date).

Done when: the report has a table of CONFIRMED, AMBIGUOUS and NO_MATCH counts per source, with the share CONFIRMED by `name_zip` versus `unique_name`. Counts only, no names.

### B2. Open or closed, then the flags mart (R5–R7, R9, R12, R16, R18, R20–R22)

- `int_federal_liens_status`: one row per lien, open or closed per R6, with the date of any `COD`.
- `int_duval_document_status`: one row per allowlisted lien, warrant or judgment, open or closed per R18.
- `company_flags` (mart, table): one row per flag on a CONFIRMED link. Columns: `document_number`, `flag_type`, `fact_date`, `status`, `status_note`, `source`, `source_record_id`, `source_url`, `fetched_at`, `caveat`, `is_shown`. `is_shown` is false for Duval flags unless `show_duval` is true, and false for discipline unless `show_dbpr_discipline` is true; both variables default to false in `dbt_project.yml`.
- Flag types and wording follow the flags table in `docs/mvp_plan_nov8.md` section 4. Facts, never conclusions.

Tests: `not_null` on `source_url`, `fetched_at` and `source_record_id`; `accepted_values` on `flag_type` and `source`; a singular test that every Duval flag's type code is in the allowlist and no flagged judgment has "FLORIDA STATE OF" on the FRM side; a singular test that every flag traces to a CONFIRMED link.

Done when: the report shows flags by type and by `is_shown`, open versus closed liens per source, and how many companies carry at least one flag.

### B3. Samples for Andres's hand checks

- `evals/link_sample_20.csv`: 20 random CONFIRMED links, 8 federal lien, 6 DBPR license and 6 Duval. Columns: company name as registered, `document_number`, source, source record identifier, `matched_on`, the two dates, and the official search page to check it on. Businesses only. Done when Andres finds 0 wrong; you only produce the file.
- `evals/draft_test_cases_40.csv`: 40 draft lookup cases built from real lien debtor and license business names (entity-word names only), each with the expected `document_number`. Don't add them to `pipeline/seeds/test_set.csv`.

Cost: record credits per leg as in Phase A. If Phase B as a whole passes 3 credits, stop after the current leg and say so in the report.

## 6. Phase C: serving and app (only when told)

Per the plan, Days 5–8: Postgres with `pg_trgm` for lookups, FastAPI + Jinja + Pico CSS (search → shortlist → report with cited flags), offline tests with a fake backend, GitHub Actions running ruff and pytest. Stop and ask before creating any hosted account or spending money; deployment waits for Andres.
