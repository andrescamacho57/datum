# Leg A1: federal tax liens (Sunbiz), raw to staging

Branch `leg/a1-federal-liens` · run 2026-11-12 (UTC) · status: **done, all done-when checks pass**

## 1. What I built

The state publishes federal tax liens as four fixed-width text files: the liens themselves (filings), who owes (debtors), who is owed (secured parties, nearly always the IRS), and what happened afterwards (events, such as a release). Each comes as a quarterly full snapshot plus small daily files.

- **`snowflake/13_federal_liens_raw.sql`**: four stages and four raw tables in `datum.raw` (`sunbiz_flr_filings`, `_debtors`, `_events`, `_secured`). Each table has the usual three columns (`line`, `source_file`, `loaded_at`) and holds both the snapshot and the 2026-11-04 daily file. It reuses the `fixed_width` file format from script 02. The script ends with two checks: rows and line length per file, and whether every daily release points at a lien in the snapshot.
- **Four staging views** in `pipeline/models/staging/`: `stg_sunbiz__flr_filings`, `_debtors`, `_events`, `_secured`. Each cuts the line into named columns at the positions in `docs/access/sunbiz_flr.md`, parses dates with `TRY_TO_DATE(x, 'MMDDYYYY')`, and adds `source_kind` (quarterly or daily) and `published_on` (2026-10-03 for the snapshot; the date in the file name for dailies). The debtors view keeps corporate rows only (`name_format = 'C'`).
- **Four source entries** appended to `pipeline/models/staging/_sunbiz__sources.yml`.
- **Tests**: `pipeline/models/staging/_sunbiz__flr_models.yml` (13 column tests) and two single-file tests in `pipeline/tests/`: one row per lien per file, and a warning when an assessment or expiration year falls outside 1990–2040.
- **`docs/access/sunbiz_flr.md`**: four new findings from the loaded data (items 9–12).

The join key is named `filing_doc_number` in all four views, so it can't be mistaken for a company's `document_number`.

## 2. Checks

**Before loading: line counts and record lengths on disk**

```
$ cd data/raw/sunbiz/flr && for f in ...; do awk '{sub(/\r$/,""); n[length($0)]++} END{...}' $f; done
FLRF.TXT            len=82  rows=20444
FLRD.TXT            len=206 rows=22173
FLRE.TXT            len=135 rows=97256
FLRS.TXT            len=206 rows=20448
20261104flrf.txt    len=82  rows=42
20261104flrd.txt    len=206 rows=46
20261104flre.txt    len=135 rows=29
20261104flrs.txt    len=206 rows=42
```

Every line in every file is the documented length, and the counts equal the source totals in `docs/access/sunbiz_flr.md`.

**Raw rows and line length per file** (`snow sql -c datum -f snowflake/13_federal_liens_raw.sql`, CHECK 1)

```
+-------------------------------------------------------------------+
| RAW_TABLE | SOURCE_FILE         | LINE_COUNT | SHORTEST | LONGEST |
|-----------+---------------------+------------+----------+---------|
| debtors   | 20261104flrd.txt.gz | 46         | 206      | 206     |
| debtors   | FLRD.TXT.gz         | 22173      | 206      | 206     |
| events    | 20261104flre.txt.gz | 29         | 135      | 135     |
| events    | FLRE.TXT.gz         | 97256      | 135      | 135     |
| filings   | 20261104flrf.txt.gz | 42         | 82       | 82      |
| filings   | FLRF.TXT.gz         | 20444      | 82       | 82      |
| secured   | 20261104flrs.txt.gz | 42         | 206      | 206     |
| secured   | FLRS.TXT.gz         | 20448      | 206      | 206     |
+-------------------------------------------------------------------+
```

All eight match the done-when table.

**Every daily `COR` event joins to a snapshot filing** (same script, CHECK 2; the same query on the staging views gives 29 / 29)

```
+--------------------------------------------------------------+
| DAILY_COR_EVENTS | FOUND_IN_SNAPSHOT | MISSING_FROM_SNAPSHOT |
|------------------+-------------------+-----------------------|
| 29               | 29                | 0                     |
+--------------------------------------------------------------+
```

**dbt tests** (`cd pipeline && dbt build --select stg_sunbiz__flr_filings stg_sunbiz__flr_debtors stg_sunbiz__flr_events stg_sunbiz__flr_secured`)

```
 Succeeded model DEV_staging.stg_sunbiz__flr_events (view)
 Succeeded model DEV_staging.stg_sunbiz__flr_secured (view)
 Succeeded model DEV_staging.stg_sunbiz__flr_debtors (view)
 Succeeded model DEV_staging.stg_sunbiz__flr_filings (view)
    Passed test  not_null_stg_sunbiz__flr_filings_filing_doc_number
    Passed test  assert_flr_filings_unique_per_file
    Passed test  accepted_values_stg_sunbiz__flr_filings_filing_status__A__L__T
    Passed test  not_null_stg_sunbiz__flr_filings_filing_date
    Passed test  not_null_stg_sunbiz__flr_filings_published_on
    Warned test  warn_flr_filings_year_out_of_range
    Passed test  not_null_stg_sunbiz__flr_debtors_filing_doc_number
    Passed test  not_null_stg_sunbiz__flr_debtors_debtor_name
    Passed test  accepted_values_stg_sunbiz__flr_debtors_name_format__C
    Warned test  accepted_values_stg_sunbiz__flr_debtors_filing_status__A__L__T
    Passed test  not_null_stg_sunbiz__flr_events_event_doc_number
    Passed test  not_null_stg_sunbiz__flr_events_filing_doc_number
    Passed test  not_null_stg_sunbiz__flr_events_action_code
    Passed test  not_null_stg_sunbiz__flr_events_event_filing_date
    Passed test  not_null_stg_sunbiz__flr_secured_filing_doc_number
    Warned test  accepted_values_stg_sunbiz__flr_secured_filing_status__A__L__T
Finished 'build' with 3 warnings for target 'dev' [18.3s]
Summary: 20 total | 17 success | 3 warn
```

(Lines reordered by model for reading; dbt prints them in completion order.)

The three warnings:
- `warn_flr_filings_year_out_of_range`: 28 rows, the known count.
- The two status tests on debtors and secured parties: 1 row each, an undocumented value `C` (see section 3).

**Staging row counts**

```
| M                | SOURCE_KIND | PUBLISHED_ON | N     | MALFORMED |
| debtors (C only) | daily       | 2026-11-04   | 46    | 0         |
| debtors (C only) | quarterly   | 2026-10-03   | 22171 | 0         |
| events           | daily       | 2026-11-04   | 29    | 0         |
| events           | quarterly   | 2026-10-03   | 97256 | 0         |
| filings          | daily       | 2026-11-04   | 42    | 0         |
| filings          | quarterly   | 2026-10-03   | 20444 | 0         |
| secured          | daily       | 2026-11-04   | 42    | 0         |
| secured          | quarterly   | 2026-10-03   | 20448 | 0         |
```

Debtors: 22,173 − 2 personal-format rows = 22,171. No filing, assessment or expiration date failed to parse (0 NULLs in 20,486 filings).

**Offline checks**: `ruff check src` → `All checks passed!`. `pytest` → `no tests ran` (the repo has no Python tests yet, and this leg adds no Python).

## 3. Decisions I made and why

| Decision | Why | Tradeoff |
|---|---|---|
| Script 13 is run twice: once to create the stages, then again after `PUT` to load | The brief asks for one script, and a stage must exist before `PUT`. `IF NOT EXISTS` and COPY's load history make the second run safe | The first run prints empty checks; the header says so |
| Appended the four tables to the existing `sunbiz` source in `_sunbiz__sources.yml` | dbt allows a source name in one file only, and the model names (`stg_sunbiz__…`) say the source is `sunbiz` | It edits an existing file, but only by adding lines; nothing existing changed |
| "Unique per source file" is a single-file test, not the built-in `unique` | The same lien may appear in the snapshot and in a daily file, so plain `unique` would fail for the wrong reason. No dbt package is installed, and I didn't add one | One more file in a new `pipeline/tests/` folder |
| Status tests on debtor and secured rows are `warn` | One snapshot row in each file holds `C`, which the state's layout doesn't list. The line length and every other field are right, so it's the state's data. I didn't add `C` to the accepted list because I don't know what it means | The build stays green with a visible warning |
| Secured parties are not filtered to corporate rows | The brief filters debtors only. The header of the model says Phase B must filter before using the name | A personal-format secured party, if one exists, sits in staging (allowed) |
| The file-kind and publish-date logic is repeated in all four models | Each model reads top to bottom on its own, like `stg_sunbiz__cor` | Four places to change when the January 2027 snapshot arrives; a macro would be one |
| Internal index keys in the events file (positions 1, 45, 46) get no column | They mean nothing outside the state's system | Still in raw if ever needed |

## 4. What I couldn't verify, and open questions for Andres

1. **Party-row status disagrees with the filings file.** All 20,486 filings say `A`, but 5 debtor rows and 4 secured rows on those liens say `T`, `L` or `C`. I'd read status from filings only in Phase B. Agree?
2. **What does status `C` mean?** Not in the state's definitions. Worth a question to the Division of Corporations.
3. **One active lien has a cancellation date.** Unknown what that means for "active".
4. **Snapshot date is hardcoded** (2026-10-03) in four models, as in `stg_sunbiz__cor`. It needs a real fix before the January 2027 snapshot.
5. **Only one day of dailies is loaded** (2026-11-04). "Active between snapshots" in Phase B needs every daily since 2026-10-03. Should a later leg pull them, or do you?
6. Still open from the access doc: whether a `COD` (discharge) clears a lien, and the per-record Sunbiz URL for citations.
7. `pytest` has nothing to run. CLAUDE.md lists it as a proof command; the first Python tests arrive with leg A2.

## 5. Credits used

**0.063 credits** on `datum_wh` (X-Small), about $0.13 at $2 per credit.

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH'))"
| 2026-11-11 21:46:04-08:00 | 2026-11-11 22:46:04-08:00 | 0.063368056  |
```

The warehouse's first query in that 12-hour window was this leg's first statement (22:38:54 Pacific), so the whole figure belongs to this leg. It was measured at the last query; the warehouse then idles until auto-suspend, which may add a little.

## 6. Three questions you should be able to answer

1. A lien appears in both `FLRF.TXT` and `20261104flrf.txt`. Why would the built-in `unique` test on `filing_doc_number` be the wrong test, and what does the single-file test check instead?
2. In CHECK 2 of script 13, the condition `f.source_file = 'FLRF.TXT.gz'` sits in the `ON` clause, not in `WHERE`. What would the result show if it were moved to `WHERE` and one release pointed at a lien that isn't in the snapshot?
3. Why is the year-range test `warn` and the filings status test `error`, when both look at the state's data?
