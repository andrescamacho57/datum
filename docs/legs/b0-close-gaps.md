# Leg B0: close the Phase A gaps

Branch `leg/b0-close-gaps` · run 2026-11-18 (UTC) · status: **done, all done-when checks pass. One command I could not run myself (section 4, item 1). Two findings to read (section 4, items 2 and 3)**

Rulings implemented: R8, R15, R23, R24, R25 (`docs/phase_b_rulings.md`).

## 1. What I built

Five gaps from Phase A, closed one at a time.

**Duval repair (R15).** Thirteen of the Clerk's daily files had failed their row-count check and were never loaded. The cause was a line break inside a legal description, which spread one record over two or three lines. `src/datum/duval.py` now has a `repair` step: it writes a mended copy of each rejected file into `data/raw/duval/repaired/` (a line that does not start a record is joined to the line above with one space, blank lines are dropped) and keeps the copy only if its row count equals the Clerk's own `EOF` count. The files as sent stay in `rejected/`. `snowflake/16_duval_repaired_load.sql` loads the 13 copies and rechecks every file.

**Federal lien dailies (R8).** `src/datum/sunbiz_flr.py` connects once to the state's public file server with the public login the state publishes, lists the four daily folders, downloads every file dated on or after the 2026-10-03 snapshot, and checks that every line is the documented length before anything is uploaded. `snowflake/17_federal_liens_dailies.sql` loads them into the four existing lien tables.

**Fetch manifest (R23).** `src/datum/manifest.py` keeps one row per downloaded file: file name, the exact address it came from, the fetch time in UTC (Coordinated Universal Time), size and checksum. All three downloaders write a row the moment a file lands. Files downloaded before today were backfilled from their modification time and marked `is_approximate = true`. `snowflake/18_fetch_manifest.sql` loads the manifest into `datum.raw.fetch_manifest`, and the staging view `stg_datum__fetch_manifest` gives every raw `source_file` its fetch time.

**`requirements.txt` (R24).** Every package in the virtual environment at its exact version, with `paramiko` pinned at 3.5.1.

**DBPR header check (R25).** `validate()` in `src/datum/dbpr.py` now rejects a license file whose first row is column names.

| New or changed | What it is |
|---|---|
| `src/datum/duval.py` | + `repair_lines`, `repair_file`, `repair_all`, the `repair` command, a manifest row per download, `backfill_manifest` |
| `src/datum/sunbiz_flr.py` (new) | Download and inspect the daily lien files |
| `src/datum/manifest.py` (new) | `FetchRecord`, `record_fetch`, `backfill`, the `backfill` command |
| `src/datum/dbpr.py` | + `looks_like_header`, the header check in `validate()`, a manifest row per download, `backfill_manifest` |
| `snowflake/16_duval_repaired_load.sql` (new) | Load the 13 repaired files; three checks |
| `snowflake/17_federal_liens_dailies.sql` (new) | Load the lien dailies; two checks |
| `snowflake/18_fetch_manifest.sql` (new) | File format, stage, table `datum.raw.fetch_manifest`, load, one check |
| `pipeline/models/staging/stg_datum__fetch_manifest.sql` (new), `_datum__sources.yml`, `_datum__models.yml` | Staging view over the manifest, 7 column tests |
| `pipeline/tests/assert_fetch_manifest_one_row_per_file.sql`, `assert_every_raw_file_has_a_fetch_manifest_row.sql` (new) | Two single-file tests |
| `tests/test_manifest.py`, `tests/test_sunbiz_flr.py` (new); `tests/test_duval.py`, `tests/test_dbpr.py` | 60 tests in all (22 before this leg) |
| `tests/fixtures/duval/rejected/`, `tests/fixtures/sunbiz_flr/`, `tests/fixtures/dbpr/construction_license_with_header.csv` (new) | Fixtures cut from real files |
| `requirements.txt` (new) | 34 pinned packages |
| `docs/access/duval-recording-index.md`, `docs/access/sunbiz_flr.md` | "Repaired files" section; the dailies and findings 13–17 |

Nothing existing was changed or dropped in Snowflake or dbt. Three new objects were created in `datum.raw`: file format `manifest_csv`, stage `fetch_manifest_stage`, table `fetch_manifest`.

## 2. Checks

### Duval: every file dated 2025-01-01 onward is loaded and equals its EOF count

**The number is 2,736 files** (684 of each kind, 2025-01-01 through 2026-11-16). It was 2,716 on 2026-11-11; the Clerk has published five more days since, and I downloaded them so "every file" stays true.

`python src/datum/duval.py download`

```
downloaded 20 files, skipped 2716 already on disk
OK    documents: 672 files, 758877 rows, every file matches its EOF count
OK    parties: 684 files, 2065331 rows, every file matches its EOF count
OK    links: 683 files, 793873 rows, every file matches its EOF count
OK    doc_types: 684 files, 58140 rows, every file matches its EOF count
0 file(s) failed verification now; 13 more already in rejected/
```

`python src/datum/duval.py repair`

```
OK    d2025090201id.16: 460 rows = EOF count; joined 2 line(s), dropped 0 blank line(s)
OK    d2025090301id.16: 1369 rows = EOF count; joined 1 line(s), dropped 0 blank line(s)
OK    d2026010901id.16: 1172 rows = EOF count; joined 2 line(s), dropped 0 blank line(s)
OK    d2026011501id.16: 520 rows = EOF count; joined 2 line(s), dropped 1 blank line(s)
OK    d2026021901id.16: 2492 rows = EOF count; joined 2 line(s), dropped 0 blank line(s)
OK    d2026022501id.16: 2668 rows = EOF count; joined 1 line(s), dropped 0 blank line(s)
OK    d2026031401id.16: 253 rows = EOF count; joined 1 line(s), dropped 0 blank line(s)
OK    d2026040801id.16: 3206 rows = EOF count; joined 1 line(s), dropped 1 blank line(s)
OK    d2026061101id.16: 1343 rows = EOF count; joined 1 line(s), dropped 0 blank line(s)
OK    d2026072801id.16: 1371 rows = EOF count; joined 1 line(s), dropped 0 blank line(s)
OK    d2026081201id.16: 1665 rows = EOF count; joined 3 line(s), dropped 0 blank line(s)
OK    d2026101601id.16: 1867 rows = EOF count; joined 1 line(s), dropped 0 blank line(s)
OK    l2026021901id.16: 2563 rows = EOF count; joined 0 line(s), dropped 1 blank line(s)
0 file(s) could not be repaired and stay out
```

`snow sql -c datum -f snowflake/16_duval_repaired_load.sql`, CHECK 1 (each repaired file against the Clerk's count)

```
| SOURCE_FILE         | DATA_ROWS | EOF_COUNT | MATCHES |
| d2025090201id.16.gz | 460       | 460       | True    |
| d2025090301id.16.gz | 1369      | 1369      | True    |
| d2026010901id.16.gz | 1172      | 1172      | True    |
| d2026011501id.16.gz | 520       | 520       | True    |
| d2026021901id.16.gz | 2492      | 2492      | True    |
| d2026022501id.16.gz | 2668      | 2668      | True    |
| d2026031401id.16.gz | 253       | 253       | True    |
| d2026040801id.16.gz | 3206      | 3206      | True    |
| d2026061101id.16.gz | 1343      | 1343      | True    |
| d2026072801id.16.gz | 1371      | 1371      | True    |
| d2026081201id.16.gz | 1665      | 1665      | True    |
| d2026101601id.16.gz | 1867      | 1867      | True    |
| l2026021901id.16.gz | 2563      | 2563      | True    |
```

Same script, CHECK 2 (every loaded file)

```
| RAW_TABLE | FILES_LOADED | DATA_ROWS | SUM_OF_EOF_COUNTS | FILES_MISMATCHED | FILES_WITHOUT_ONE_TRAILER | FIRST_FILE_DATE | LAST_FILE_DATE |
| doc_types | 684          | 58140     | 58140             | 0                | 0                         | 20250101        | 20261116       |
| documents | 684          | 777263    | 777263            | 0                | 0                         | 20250101        | 20261116       |
| links     | 684          | 796436    | 796436            | 0                | 0                         | 20250101        | 20261116       |
| parties   | 684          | 2065331   | 2065331           | 0                | 0                         | 20250101        | 20261116       |
```

Documents: 758,877 + 18,386 repaired = 777,263. Links: 793,873 + 2,563 = 796,436.

**The two `relationships` tests report 0 orphans.** Script 16, CHECK 3:

```
| RAW_TABLE | DATA_ROWS | ORPHAN_ROWS |
| parties   | 2065331   | 0           |
| links     | 796436    | 0           |
```

and in dbt (`cd pipeline && dbt build --select stg_duval__documents stg_duval__parties stg_duval__links stg_duval__doc_types ...`) both now pass where Phase A had warnings:

```
    Passed test  relationships_stg_duval__parties_instrument_number__instrument_number__ref_stg_duval__documents_
    Passed test  relationships_stg_duval__links_instrument_number__instrument_number__ref_stg_duval__documents_
```

Before the repair: 45,173 and 14,464 orphan rows.

### Federal lien dailies

`python src/datum/sunbiz_flr.py download` (file date by rows, from the files on disk, before upload)

```
downloaded 20 files, skipped 4 already on disk
file date      filings  debtors   events  secured
2026-10-19          44       45       23       44
2026-10-29          70       72        0       70
2026-10-30         131      147       60      131
2026-11-04          42       46       29       42
2026-11-09          71       79       30       71
2026-11-16          72       77       37       72
total              430      466      179      430
OK    24 files on 6 days, every line the documented length filings 82, debtors 206, events 135, secured 206
0 file(s) failed inspection
```

`snow sql -c datum -f snowflake/17_federal_liens_dailies.sql`, CHECK 1 (rows loaded; same numbers)

```
| FILE_DATE  | FILINGS | DEBTORS | EVENTS | SECURED | FILES_WITH_ROWS | LINES_WRONG_LENGTH |
| snapshot   | 20444   | 22173   | 97256  | 20448   | 4               | 0                  |
| 2026-10-19 | 44      | 45      | 23     | 44      | 4               | 0                  |
| 2026-10-29 | 70      | 72      | 0      | 70      | 3               | 0                  |
| 2026-10-30 | 131     | 147     | 60     | 131     | 4               | 0                  |
| 2026-11-04 | 42      | 46      | 29     | 42      | 4               | 0                  |
| 2026-11-09 | 71      | 79      | 30     | 71      | 4               | 0                  |
| 2026-11-16 | 72      | 77      | 37     | 72      | 4               | 0                  |
```

**Missing business days** (Monday to Friday, 2026-10-03 to 2026-11-17, no file in any of the four folders): 26 days.

Oct 5, 6, 7, 8, 9 · Oct 12, 13, 14, 15, 16 · Oct 20, 21, 22, 23 · Oct 26, 27, 28 · Nov 2, 3 · Nov 5, 6 · Nov 10, 11, 12, 13 · Nov 17

The state publishes a lien daily only on days with activity, and that turns out to be about once a week (section 4, item 3).

**Every daily `COR` event joins to a filing in the snapshot or an earlier daily.** Script 17, CHECK 2:

```
| DAILY_COR_EVENTS | FOUND_IN_SNAPSHOT | FOUND_IN_EARLIER_DAILY | FOUND_ONLY_IN_SAME_OR_LATER_DAILY | MISSING | MISSING_FILED_THIS_YEAR |
| 178              | 171               | 5                      | 0                                 | 2       | 0                       |
```

**Found 176, missing 2.** The two are releases filed 2026-10-30 against liens from 2014 and 2018 (`14FLR0013922`, `18FLR0008457`). Neither lien is in the snapshot and neither has a debtor row or an earlier event in our data. The snapshot holds active liens only, so these two had already left it before 2026-10-03. They can't make a lien we hold look open. A missing lien numbered `26FLR…` would mean a missing daily file; that count is 0.

**Is the snapshot complete at its edge?** `python src/datum/sunbiz_flr.py probe`

```
connected over SFTP; 24 in-scope daily files, 245506 bytes
first 20261019flrd.txt, last 20261116flrs.txt
last file dates before the 2026-10-03 snapshot: 2026-09-23, 2026-09-30, 2026-10-01
```

The snapshot's own last filing date and last event date are both 2026-10-01 (read from `FLRF.TXT` and `FLRE.TXT` on disk). So nothing was published between the snapshot's last record and the first daily after it.

### Fetch manifest: one row per loaded file across the three sources

`snow sql -c datum -f snowflake/18_fetch_manifest.sql`, CHECK

```
| SOURCE     | MANIFEST_FILES | APPROXIMATE_FETCH_TIME | DISTINCT_SOURCE_FILES_IN_RAW | MANIFEST_FILES_NOT_IN_RAW | RAW_FILES_WITHOUT_MANIFEST_ROW |
| dbpr       | 6              | 6                      | 6                            | 0                         | 0                              |
| duval      | 2736           | 2716                   | 2736                         | 0                         | 0                              |
| sunbiz_flr | 28             | 8                      | 27                           | 1                         | 0                              |
```

| Source | Manifest rows | Distinct `source_file` in raw | Difference |
|---|---|---|---|
| dbpr | 6 | 6 | 0 |
| duval | 2,736 | 2,736 | 0 |
| sunbiz_flr | 28 | 27 | 1: the empty file `20261029flre.txt` was fetched and holds no rows, so it never appears in raw |

2,770 manifest rows. 2,730 carry an approximate fetch time (files downloaded on Nov 5 and Nov 12, before the manifest existed); the 40 files downloaded today carry a measured one. Every file with rows in raw has a manifest row.

`cd pipeline && dbt build --select stg_datum__fetch_manifest`

```
 Succeeded model DEV_staging.stg_datum__fetch_manifest (view)
    Passed test  not_null_stg_datum__fetch_manifest_source
    Passed test  accepted_values_stg_datum__fetch_manifest_source__dbpr__duval__sunbiz_flr
    Passed test  not_null_stg_datum__fetch_manifest_source_file
    Passed test  not_null_stg_datum__fetch_manifest_source_url
    Passed test  not_null_stg_datum__fetch_manifest_fetched_at_utc
    Passed test  not_null_stg_datum__fetch_manifest_sha256
    Passed test  not_null_stg_datum__fetch_manifest_is_approximate
    Passed test  assert_fetch_manifest_one_row_per_file
    Passed test  assert_every_raw_file_has_a_fetch_manifest_row
Summary: 10 total | 10 success
```

### All staging tests after the new loads

`cd pipeline && dbt build --select stg_duval__documents stg_duval__parties stg_duval__links stg_duval__doc_types stg_sunbiz__flr_filings stg_sunbiz__flr_debtors stg_sunbiz__flr_events stg_sunbiz__flr_secured`

```
Finished 'build' with 3 warnings for target 'dev' [5.1s]
Processed: 8 models | 26 tests
Summary: 34 total | 31 success | 3 warn
```

The three warnings are the ones Phase A reported and R5 and R7 already rule on: 28 liens with an impossible year, and one debtor row and one secured-party row with the undocumented status `C`. No new warning came from the dailies.

### `pytest` and `ruff check src tests`

```
$ pytest
============================== 60 passed in 0.23s ==============================
$ ruff check src tests
All checks passed!
```

### `requirements.txt` equals the environment

```
$ diff <(pip freeze | sort -f) <(grep -v '^\s*#' requirements.txt | sed 's/[[:space:]]*#.*$//' | sed '/^$/d' | sort -f)
(no output: the two lists are identical, 34 packages)
```

### DBPR header check

- The fixture `tests/fixtures/dbpr/construction_license_with_header.csv` is rejected: `test_license_file_that_starts_with_a_header_row_is_rejected` passes.
- The rule gives no false alarm on the real file: I read all 263,337 rows of `data/raw/dbpr/CONSTRUCTIONLICENSE_1.csv` with a throwaway script and counted the rows the rule would call a header: **0**.
- `python src/datum/dbpr.py validate` on the six real files: **not run by me.** See section 4, item 1.

## 3. Decisions I made and why

| Decision | Why | Tradeoff |
|---|---|---|
| Downloaded the 20 Duval files published since Nov 11 | The done-when line says "every Duval file dated 2025-01-01 onward" and "report the number". It was also the only way to prove the manifest with measured fetch times. One connection, sequential, 0.5 s pause | 20 files more than the 2,716 named in the brief |
| Repaired copies keep the original file name and go into the same stages and tables | Staging reads each file's date from its name, and existing models may not change. One table per file kind stays true | Nothing in raw marks a row as repaired; `docs/access/duval-recording-index.md` is the record |
| New Duval days are loaded by rerunning script 15; script 16 loads only the 13 repaired files, by name | Each script does one thing. Script 15 is already "safe to rerun" by design | Two scripts to run after a download that produces a rejected file |
| One manifest file for all sources, loaded whole each time it grows; staging de-duplicates | One small table and one join for any fact. Raw stays append-only | Raw collects repeated rows after each reload. Staging keeps the latest fetch per file |
| The manifest is a separate table joined on `source_file`; no fetch-time column was added to the 11 raw tables | "Never change existing tables" | A fact needs one join to reach its fetch time |
| Backfilled fetch time for the quarterly lien files comes from the zip's modification time, not the unzipped file's | The unzipped `FLRF.TXT` carries the time the state wrote it (2026-10-03 00:00). The zip carries the time it was downloaded (2026-11-05) | Still approximate, and marked so |
| A `FetchRecord` cannot be created without a full address and a time-zone-aware UTC time | CLAUDE.md rule 3: "a fact type constructible without both is a bug in the type" | Callers must pass UTC; a local time raises an error |
| The state's public login is written in `sunbiz_flr.py` | The state publishes it for this purpose and it is already in `docs/access/sunbiz.md`. It is not a secret, so it does not belong in the secrets file | A password-shaped string in the code; the comment says why |
| The state's server key is trusted on first contact and pinned in `data/sunbiz_known_hosts` | Same approach as the Duval downloader. Later connections refuse a different key | The first contact was not verified. Fingerprint: `ssh-ed25519 SHA256:xTpc6X81is5Nyh2QXR6hIRhS7ayx5/BMr162zB73xyQ` |
| "Looks like a header" means every filled cell contains a letter | Data rows always have all-digit cells (board number, ZIP code, county code, dates). Tested against every real row: 0 false alarms | A header made only of numbers would slip through. No real file looks like that |
| The debtors fixture has its name and address fields overwritten | The test only needs line lengths. A public repo has no need to name a tax-lien debtor in a fixture | Not byte-for-byte the state's rows; the fixture README says so |
| Script numbers 16, 17, 18 | Next free numbers, one per concern | Phase B's later scripts start at 19 |
| Each downloader imports the manifest with a `try` / `except` pair | The scripts are run as files (`python src/datum/duval.py`) and also imported by tests (`datum.duval`). The two ways put different folders on the import path | Four lines a reader has to look up once |

Connections made to outside servers: Sunbiz SFTP three times (one probe, one download of 20 files, one more probe after I added the "last dates before the snapshot" line); Duval SFTP once (20 files). No DBPR request.

## 4. What I couldn't verify, and open questions for Andres

1. **I could not run `python src/datum/dbpr.py validate` on the real files.** A privacy guard in this session refuses to run that script because the `USER_AGENT` line near the top of `src/datum/dbpr.py` holds your email address inside the User-Agent (the label a program sends to a website to say who it is). The guard is right to stop me sending your address anywhere, and I did not work around it. Two things for you:
   - Run it yourself from the VS Code terminal: `cd ~/datum && source .venv/bin/activate && python src/datum/dbpr.py validate`. Expect six `OK` lines with the same counts as the Phase A report. It makes no network request.
   - Decide whether your email should stay in that line. The repo is public, so the address is public there too. A generic contact (or none) is the alternative. I left the line as Phase A wrote it; changing it is a separate concern.
2. **The Sunbiz corporate files are not in the manifest.** The 13 million company rows (scripts 03 and 06) were pulled by hand in October, before any downloader existed. So a company fact still has `loaded_at` and `published_on` but no fetch-manifest row. The lien, license and Duval facts that Phase B turns into flags all have one. Backfilling the corporate files from disk is about ten lines; say the word.
3. **Lien dailies come about once a week, not daily.** Six files in 32 business days. Worth knowing for the report's wording: "as of" a lien's status can be up to a week or more behind. The 26 days without a file are listed above; I can't tell a quiet day from a day the state skipped.
4. **Fetch times before today are estimates.** 2,730 of 2,770 manifest rows use the file's modification time. For the Duval and DBPR files that is the true download moment to the second (they match the Phase A reports: 06:49 and 13:10 UTC on Nov 12). For the eight lien files pulled by hand on Nov 5 it is as good as the copy on disk.
5. **When a file is fetched again under the same name** (DBPR's license file is refreshed weekly under one name), the manifest gets a second row and staging keeps the latest. That is right once the new file is loaded, and wrong for the minutes in between. It also meets a Phase A limit: COPY would load the new version next to the old one under the same `source_file`. Fixing that (a date folder in the stage path) belongs with the first DBPR refresh.
6. **Two daily releases point at liens we don't hold** (explained in section 2). I read them as harmless; the state could confirm.
7. The Clerk's and the state's server keys are both trusted on first use. The Sunbiz fingerprint is in section 3 if you want to compare it with what your own `sftp` saw on Oct 12.

## 5. Credits used

**About 0.159 credits** on `datum_wh` (roughly $0.32 at $2 per credit).

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"
before the leg (22:02–23:02 Pacific bucket, Nov 17):  0.000086389
after the leg  (22:20–23:20 Pacific bucket, Nov 17):  0.159036111
```

Measured at this leg's last query; the idle minute before auto-suspend may add a little. Phase B running total: 0.16 of the 3-credit cap.

## 6. Three questions you should be able to answer

1. A repaired Duval file is kept only if its row count equals the `EOF` trailer. Why is that a proof that the repair is right, and what kind of damage could it NOT detect? (Hint: think of two broken lines that both happen to start with `DDA|`.)
2. Raw tables already have `loaded_at`. What question does the fetch manifest answer that `loaded_at` can't, and why is the backfilled time for `FLRF.TXT` taken from `flrf.zip` and not from `FLRF.TXT` itself?
3. The manifest is one CSV that grows, and it is loaded whole every time. What does that do to `datum.raw.fetch_manifest`, and which lines of `stg_datum__fetch_manifest.sql` make the result one row per file anyway?
