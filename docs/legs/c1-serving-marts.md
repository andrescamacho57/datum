# Leg C1: the marts the app reads

Branch `leg/c1-serving-marts` (from `origin/main`) · run on Nov 20, 2026, Pacific time · risk tier **High** · status: **done. Every check passes, and the Deep review ended after two rounds with no Important finding left open.**

This is the first of the four legs of Phase C. It builds the tables that the web app will read, and it builds nothing of the app itself. A mart is a finished table shaped for one use, and these four are shaped for the app.

**The short version**

- Every company now has a source address and a fetch time. The fetch manifest, which is the list of every file Datum downloaded and when, gained the state's corporate files, and so all **12,988,435** companies carry a fetch time. Every one of those times is an estimate, and the tables say so.
- Four tables are ready for the app. `company_search` is new, `company_flags` gained one column, `company_possible_matches` is new and every one of its **9,651** rows is hidden, and `source_coverage` is new and has **5** rows.
- `company_flags` did not change apart from its one new column. It has the same **24,213** rows and the same checksum over its thirteen existing columns before and after.
- Open question Q28 is sized. **75** companies have a match key that is very likely one letter short, and **no** CONFIRMED link points at any of them.
- Nothing in the brief was left undone, and no stop condition was met.

**What is left for Andres**

- Decide which reasons for a possible match may be shown. That is the new question Q29 in `docs/open_questions.md`, and section 4 below has the counts.
- Read section 3, which holds the calls I made where the brief did not say.
- Answer the three questions in section 6, because this is a High-tier change.

**The three checks before the first leg** (the brief asks for them before anything is built)

| Check | Result |
|---|---|
| Pull request 13 is merged, and ruling R30 is on `origin/main` | ✅ `git show origin/main:docs/phase_b_rulings.md` holds R30 on line 93 |
| The newer material was read | ✅ `docs/legs/c0-link-rules.md`, questions Q26 to Q28, and sections 1, 3 and 4 and Days 5 to 7 of `docs/mvp_plan_nov8.md` |
| At least 2 of the month's 10 credits are left | ✅ `warehouse_metering_history` showed **2.33** credits used in November before this leg started, so about 7.67 were left |

---

## 1. What I built

### The picture

```
 the state's corporate files (pulled by hand in October)
        │   src/datum/sunbiz_cor.py writes one manifest row per file, marked "estimate"
        ▼
 datum.raw.fetch_manifest ── script 21 loads it ──▶ stg_datum__fetch_manifest
        │
        ├──▶ company_search            13.0M rows   one per company, with source_url and fetched_at
        ├──▶ company_flags             24,213 rows  one new column: fetched_at_is_approximate
        ├──▶ company_possible_matches   9,651 rows  every row hidden (rule W3)
        └──▶ source_coverage                5 rows  which sources a report checked
                    │
                    ▼
        exposure datum_web_app   (dbt's record that the app reads these four)
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| `src/datum/sunbiz_cor.py` | A small Python module that writes one manifest row for each corporate file still on disk. A daily file takes its own modification time. Each of the ten files inside the snapshot `cordata.zip` takes the zip's modification time. Every row is marked approximate | `CLAUDE.md` rule 3 says every fact carries a source address and a UTC (Coordinated Universal Time) fetch time, and no company's status, date or address had one |
| `snowflake/21_fetch_manifest_sunbiz_cor.sql` | Loads the manifest again and checks the eleven new rows two ways | The brief asks for a new numbered script, because scripts 01 to 20 stay as they are |
| `company_search` | One row per company, with the columns the search and the report header need, plus `source_url`, `fetched_at` and `fetched_at_is_approximate` | The app reads a copy of this table, and an existing mart (`entity_lookup`) may not be changed |
| `pipeline/macros/flag_rules.sql` | The rules that turn a linked lien or license into a flag row, moved out of `company_flags.sql` without a change | Two marts must apply the same rules, and so the rules live in one place |
| `company_flags` | The same table as before, plus the column `fetched_at_is_approximate` at the end | The page says "fetched about" when the fetch time is an estimate (rule W1) |
| `company_possible_matches` | One row per record on an AMBIGUOUS link that would be a shown flag if the link were CONFIRMED. It has the columns of `company_flags` plus `link_reason` | Rule W3. The app will read it once Andres switches a reason on |
| `possible_match_reasons` (seed) | Nine rows, one per reason an AMBIGUOUS link can have, each with `is_shown` false and a plain-English meaning | A seed is a small CSV file, so turning a reason on is a one-line change that anyone can review |
| `source_coverage` | One row per loaded source: its label, whether its flags are shown, the date its data runs through, the official search page and its newest fetch time | Rule W5. The report's "checked" and "not checked" lists come from it |
| `_exposures.yml` | Declares the web app as a reader of the four marts | It puts the app on dbt's lineage graph, and `dbt build --select +exposure:datum_web_app` builds everything the app depends on |
| `snowflake/22_size_q28_spaced_suffix.sql` | Three counts for open question Q28. It prints no name and changes nothing | The brief asks for the size and no change |

### The three places the new source name was added

The brief allows the source `sunbiz_cor` to be added wherever the fetch manifest lists its allowed sources. Those places are `SOURCES` in `src/datum/manifest.py`, the `accepted_values` test in `pipeline/models/staging/_datum__models.yml`, and the `accepted_values` test on the seed `search_page_sources` in `pipeline/seeds/_seeds.yml`. The seed gained one row, as the brief allows.

### Files

| File | New or changed |
|---|---|
| `src/datum/sunbiz_cor.py`, `tests/test_sunbiz_cor.py` | New. 10 tests |
| `src/datum/manifest.py` | Changed: `sunbiz_cor` is an allowed source, and the `backfill` command runs it |
| `snowflake/21_fetch_manifest_sunbiz_cor.sql`, `snowflake/22_size_q28_spaced_suffix.sql` | New |
| `pipeline/macros/flag_rules.sql` | New: four macros |
| `pipeline/models/marts/company_search.sql`, `company_possible_matches.sql`, `source_coverage.sql`, `_exposures.yml` | New |
| `pipeline/models/marts/company_flags.sql` | Changed: it calls the macros, and it has one new column |
| `pipeline/models/marts/_marts.yml` | Changed: tests for the three new marts and the new column |
| `pipeline/seeds/possible_match_reasons.csv` | New |
| `pipeline/seeds/search_page_sources.csv`, `pipeline/seeds/_seeds.yml`, `pipeline/dbt_project.yml` | Changed: one seed row, one project variable, and the settings for the new seed |
| `pipeline/tests/` | 10 new singular tests, and one changed (`assert_no_name_columns_past_staging.sql`) |
| `docs/open_questions.md` | Changed: Q28 has its counts, and Q29 to Q32 are new |

Nothing existing was dropped or altered in Snowflake. Three new tables exist in `datum.dev_marts`, one new table in `datum.dev_reference`, and `datum.raw.fetch_manifest` holds one more load of the manifest.

---

## 2. Checks

### Check 1: the corporate files' fetch times

The files that are still on disk are the daily file `20261009c.txt` and the snapshot `cordata.zip`. The ten snapshot files had been deleted after they were loaded, and the zip that was fetched is still there, and so each of the ten was read straight out of the zip to get its size and checksum.

```
python src/datum/manifest.py backfill

dbpr: added 0 approximate row(s)
duval: added 0 approximate row(s)
sunbiz_flr: added 0 approximate row(s)
sunbiz_cor: added 10 approximate row(s)
manifest now has 2781 row(s)
```

The daily file's row had been added by an earlier run of the same command, which then stopped at the zip (section 3, decision 2). So the source has 11 rows in all.

```
snow sql -c datum -q "PUT file:///Users/anfelca2/datum/data/raw/fetch_manifest.csv @datum.raw.fetch_manifest_stage AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
snow sql -c datum -f snowflake/21_fetch_manifest_sunbiz_cor.sql

CHECK 1: every corporate file in raw has a manifest row, and the reverse
| FILE_NAME     | RAW_TABLE            | ROWS_IN_RAW | IN_MANIFEST | IN_RAW | FETCHED_AT_UTC       | IS_APPROXIMATE |
| 20261009c.txt | sunbiz_cor_daily     | 834         | True        | True   | 2026-10-12T19:33:39Z | true           |
| cordata0.txt  | sunbiz_cor_quarterly | 1298631     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata1.txt  | sunbiz_cor_quarterly | 1298943     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata2.txt  | sunbiz_cor_quarterly | 1298877     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata3.txt  | sunbiz_cor_quarterly | 1298863     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata4.txt  | sunbiz_cor_quarterly | 1298859     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata5.txt  | sunbiz_cor_quarterly | 1298693     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata6.txt  | sunbiz_cor_quarterly | 1298685     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata7.txt  | sunbiz_cor_quarterly | 1298711     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata8.txt  | sunbiz_cor_quarterly | 1298685     | True        | True   | 2026-10-22T19:31:31Z | true           |
| cordata9.txt  | sunbiz_cor_quarterly | 1298654     | True        | True   | 2026-10-22T19:31:31Z | true           |

CHECK 2: each file was fetched before it was loaded
| FILE_NAME     | FETCHED_AT_UTC      | LOADED_AT_UTC              | FETCHED_BEFORE_LOADED |
| 20261009c.txt | 2026-10-12 19:33:39 | 2026-10-13 11:03:08.793000 | True                  |
| cordata0.txt  | 2026-10-22 19:31:31 | 2026-10-22 22:03:50.180000 | True                  |
  (the other nine snapshot files show the same two times, and True)
```

- ✅ All 11 corporate files in raw have a manifest row, and the manifest names no file that raw lacks.
- ✅ Every file's estimated fetch time is earlier than its load time, which is what a real download time has to be.
- ✅ The size of each snapshot file in the manifest equals the size `unzip -l` prints for it, for example 1,872,625,902 bytes for `cordata0.txt`.

### Check 2: the build of the four marts and everything they depend on

```
cd pipeline && dbt build --select +exposure:datum_web_app

 Succeeded seed  DEV_reference.possible_match_reasons (table) [1 of 230 in 2.07s]
 Succeeded seed  DEV_reference.search_page_sources (table) [2 of 230 in 1.83s]
 Succeeded model DEV_marts.entity_lookup (table) [54 of 230 in 35.04s]
 Succeeded model DEV_marts.source_coverage (table) [80 of 230 in 5.50s]
 Succeeded model DEV_intermediate.int_company_match_keys (table) [109 of 230 in 12.38s]
 Succeeded model DEV_marts.company_search (table) [110 of 230 in 13.65s]
 Succeeded model DEV_intermediate.int_duval_party_links (table) [118 of 230 in 7.99s]
 Succeeded model DEV_intermediate.int_dbpr_license_links (table) [119 of 230 in 9.13s]
 Succeeded model DEV_intermediate.int_federal_lien_links (table) [120 of 230 in 8.63s]
 Succeeded model DEV_marts.company_flags (table) [179 of 230 in 2.71s]
 Succeeded model DEV_marts.company_possible_matches (table) [203 of 230 in 2.56s]
    Warned test  warn_flr_filings_year_out_of_range
    Warned test  accepted_values_stg_sunbiz__flr_debtors_filing_status__A__L__T
    Warned test  accepted_values_stg_sunbiz__flr_secured_filing_status__A__L__T
Finished 'build' with 3 warnings for target 'dev' [1m 38s]
Processed: 23 models | 191 tests | 4 seeds | 12 unit tests
Summary: 230 total | 227 success | 3 warn
```

The `+` in front of `exposure:datum_web_app` means "everything this depends on", so the selection is the four marts and every model, seed and test upstream of them. The three warnings are the three tests that Phase A set to warn and not fail: 28 liens with a year out of range, and the party rows with status `C` that ruling R7 covers. They are unchanged by this leg.

The tests this leg added, all passing in that build:

| Test | What makes it fail |
|---|---|
| `not_null` on `source_url` and `fetched_at` in `company_search`, `company_possible_matches` and `source_coverage` | A company whose file has no manifest row, or a source with no approved search page |
| `unique` on `company_search.document_number` | A company listed twice |
| `relationships` from `company_flags` and from `company_possible_matches` to `company_search` | A flag or possible match about a company the app cannot find |
| `accepted_values` on `company_possible_matches.link_reason`, and `relationships` from it to the seed | A reason code that nobody has made a decision about |
| `assert_possible_matches_stay_hidden` | Any possible match whose `is_shown` is not the literal `false` (proven in check 5) |
| `assert_every_possible_match_traces_to_an_ambiguous_link` | A row with no AMBIGUOUS link behind it, a lien that ruling R7 leaves out, a license that is not inactive, or a record that is already a flag on that company |
| `assert_every_ambiguous_record_is_a_possible_match` (added in review round 1) | A record that should be a possible match and has no row in the mart. Proven in check 5 |
| `assert_possible_matches_one_row_per_reason` | The same company, record, kind and reason on two rows |
| `assert_possible_matches_cite_an_approved_search_page` | A possible match, shown or hidden, that cites any address other than its source's approved one |
| `assert_company_search_cites_the_approved_search_page` | The project variable and the seed disagreeing about the Sunbiz address |
| `assert_company_search_has_every_company` | A company in `entity_lookup` and not in `company_search`, the reverse, or a differing name, status, date or address |
| `assert_flags_mark_an_estimated_fetch_time` | A flag whose own file has an estimated fetch time and whose `fetched_at_is_approximate` is not true |
| `assert_source_coverage_agrees_with_the_flags` | A hidden source listed as checked, a shown source listed as not checked, the table and `company_flags` disagreeing, or a source missing |
| `assert_source_coverage_dates_claim_no_more_than_the_data` (added in review round 1) | A "data through" date later than the fetch, a company-record date that is not the snapshot's, a lien or discipline date that differs from the flags' caveats, or a newest fetch time or estimate mark that disagrees with the manifest. Proven in check 5 |

### Check 3: `company_flags` before and after

The same query ran four times: before the leg, after the rules moved into macros, after the new column, and after the last build.

```
select count(*) n,
       hash_agg(document_number, flag_type, fact_date, status, status_note, source, source_record_id,
                source_url, citation, source_file, fetched_at, caveat, is_shown) h
from datum.dev_marts.company_flags
```

| When | Rows | Checksum over the thirteen existing columns |
|---|---|---|
| Before the leg (the table as `main` built it) | 24,213 | -6111098779153045487 |
| After the flag rules moved into `flag_rules.sql` | 24,213 | -6111098779153045487 |
| After the column `fetched_at_is_approximate` was added | 24,213 | -6111098779153045487 |
| After the last full build | 24,213 | -6111098779153045487 |

`hash_agg` folds every value of the listed columns in every row into one number, and the order of the rows does not matter. If one cell in one row had changed, the number would differ.

A second proof for the two moves: the SQL that dbt compiles for `company_flags` was saved before and after each one and compared line by line, ignoring blank lines and comment lines.

```
after the first move:   lines of SQL before: 155 after: 155 identical: True
after the second move:  lines of SQL before: 160 after: 160 identical: True
after the switch for possible matches was added to the macros: before 160 after 160 identical: True
```

The new column, by kind of flag:

| Source | Flag type | Estimated fetch time | Measured fetch time |
|---|---|---|---|
| `sunbiz_flr` | `federal_tax_lien` | 9,721 | 205 |
| `dbpr` | `dbpr_license_inactive` | 24 | 0 |
| `dbpr` | `dbpr_discipline` (hidden) | 378 | 0 |
| `duval` | three kinds (hidden) | 13,780 | 105 |

The 205 liens with a measured time are the ones that arrived in a daily file that the downloader fetched on Nov 18.

### Check 4: possible matches by source and reason, with 0 shown

```
select source, flag_type, link_reason, is_shown, count(*), count(distinct source_record_id), count(distinct document_number)
from datum.dev_marts.company_possible_matches group by 1, 2, 3, 4

| SOURCE     | FLAG_TYPE             | LINK_REASON                    | IS_SHOWN | POSSIBLE_MATCHES | RECORDS | COMPANIES |
| dbpr       | dbpr_license_inactive | before_company_filed           | False    | 1                | 1       | 1         |
| dbpr       | dbpr_license_inactive | no_entity_word                 | False    | 19               | 19      | 2         |
| dbpr       | dbpr_license_inactive | several_companies              | False    | 21               | 4       | 14        |
| dbpr       | dbpr_license_inactive | several_companies_same_zip     | False    | 6                | 3       | 6         |
| dbpr       | dbpr_license_inactive | zip_differs                    | False    | 436              | 403     | 73        |
| sunbiz_flr | federal_tax_lien      | before_company_filed           | False    | 34               | 34      | 18        |
| sunbiz_flr | federal_tax_lien      | several_companies_same_zip     | False    | 987              | 431     | 529       |
| sunbiz_flr | federal_tax_lien      | several_similar_names_same_zip | False    | 22               | 22      | 11        |
| sunbiz_flr | federal_tax_lien      | zip_differs                    | False    | 8124             | 6039    | 4818      |
| sunbiz_flr | federal_tax_lien      | zip_unreadable                 | False    | 1                | 1       | 1         |

| TOTAL | SHOWN |
| 9651  | 0     |
```

A possible match is one row per company per record per reason, so one lien that could belong to three companies is three rows. "Records" counts the liens or licenses, and "companies" counts the companies they might belong to.

### Check 5: the tests can fail

A test that cannot fail reassures and proves nothing, so the three tests that guard the riskiest rules were each run against a deliberately wrong input.

**The test that keeps possible matches hidden.** I set one seed row to true (`zip_unreadable`), built the seed and the mart, and then put the row back.

```
dbt build --select possible_match_reasons company_possible_matches

    Failed test  assert_possible_matches_stay_hidden (tests/assert_possible_matches_stay_hidden.sql)
Test failed (1 failed row(s)): assert_possible_matches_stay_hidden
Summary: 30 total | 29 success | 1 error
```

✅ One row failed, which is the one lien with that reason. With the seed row back to false, the same build passes: `Summary: 30 total | 30 success`.

**The two tests added in review round 1.** Each test's compiled SQL was run with the table it checks swapped for a wrong version of that table. Nothing in Snowflake was changed. "Bad rows" is what the test returns, and any number above 0 is a failure.

| Test | The input | Bad rows |
|---|---|---|
| `assert_every_ambiguous_record_is_a_possible_match` | The mart as built | 0 |
| | The mart without the reason `zip_unreadable` | 1 |
| | An empty mart | 9,651 |
| `assert_source_coverage_dates_claim_no_more_than_the_data` | The table as built | 0 |
| | The company record dated by the daily file, 2026-10-09 | 1 |
| | The DBPR license date set after the fetch | 1 |
| | The lien date one day off | 1 |
| | The discipline date one day off | 1 |
| | The company record's estimate mark set to false | 1 |
| | Duval's newest fetch time moved one hour earlier | 1 |

**The no-names test, widened in review round 1.** With its one exception for `PARTY_SEQ` taken out, it returns the four `PARTY_SEQ` columns of the link models, which shows that the new patterns are read. As written it returns 0.

### Check 6: the rows of `source_coverage`

| Source | Label | Shown, so "checked" | Data through | Newest fetch (UTC) | Fetch time is an estimate |
|---|---|---|---|---|---|
| `sunbiz_cor` | Florida Division of Corporations company record (Sunbiz) | yes | 2026-10-07 | 2026-10-22 19:31:31 | yes |
| `sunbiz_flr` | Federal tax liens filed with the Florida Department of State | yes | 2026-11-16 | 2026-11-18 07:10:58 | no |
| `dbpr_license` | Florida DBPR construction contractor licenses | yes | 2026-11-10 | 2026-11-12 06:49:42 | yes |
| `dbpr_discipline` | Florida DBPR discipline records against construction license holders | no | 2026-07-17 | 2026-11-12 06:49:53 | yes |
| `duval` | Duval County recorded liens, tax warrants and judgments | no | 2026-11-16 | 2026-11-18 07:12:07 | no |

Each row also carries a note saying what kind of date "data through" is, and the official search page. The five notes, word for word, because a contractor will read them:

| Source | The note |
|---|---|
| `sunbiz_cor` | The date of the state's latest quarterly snapshot of every company. A change to a company after that date is not covered. |
| `sunbiz_flr` | The date of the newest daily federal lien file loaded. A lien or a release filed after that date is not covered. |
| `dbpr_license` | The newest license issue date in DBPR's licensee file. DBPR publishes no date for the file itself, and it leaves out delinquent, null-and-void and involuntarily inactive licenses. |
| `dbpr_discipline` | The newest discipline date in DBPR's published discipline files. |
| `duval` | The date of the newest daily recording index file loaded from the Duval County Clerk. Files dated 2025-01-01 onward are loaded. |

### Check 7: how many companies have a measured fetch time, an estimated one, or none

```
select case when fetched_at is null then 'none' when fetched_at_is_approximate then 'estimated' else 'measured' end, count(*)
from datum.dev_marts.company_search group by 1

| FETCH_TIME | COMPANIES |
| estimated  | 12988435  |
```

| Fetch time | Companies |
|---|---|
| Measured | 0 |
| Estimated | 12,988,435 |
| None | 0 |

Every company's file was pulled by hand before the manifest existed, so no company has a measured time. 12,987,601 companies come from the snapshot, fetched on about Oct 22, 2026, and 834 come from the daily file, fetched on about Oct 12, 2026. This is open question Q31.

### Check 8: the two Q28 counts

```
snow sql -c datum -f snowflake/22_size_q28_spaced_suffix.sql

CHECK 1: companies whose match key lost four spaced letters
| LETTERS_REMOVED | HOW_THE_NAME_WRITES_IT       | COMPANIES | REST_ENDS_IN_ONE_LETTER |
| L L L P         | spaces only                  | 1         | 0                       |
| L L L P         | one unit, apart from the name | 445      | 13                      |
| L L L P         | (subtotal)                   | 446       | 13                      |
| P L L C         | comma after the first letter | 75        | 60                      |
| P L L C         | spaces only                  | 37        | 20                      |
| P L L C         | one unit, apart from the name | 1307     | 118                     |
| P L L C         | (subtotal)                   | 1419      | 198                     |
| (total)         |                              | 1865      | 211                     |

CHECK 2: CONFIRMED links that point at one of them
| SOURCE       | HOW_THE_NAME_WRITES_IT | CONFIRMED_LINK_ROWS | RECORDS | COMPANIES |
| dbpr_license | one unit, apart from the name | 3            | 3       | 3         |
| (total)      |                        | 3                   | 3       | 3         |

CHECK 3: the same misreading one size down
| COMPANIES_WITH_A_COMMA_INSIDE_L_L_C_OR_L_L_P | CONFIRMED_LINKS_POINTING_AT_THEM |
| 21                                           | 0                                |
```

| The count the brief asks for | Number |
|---|---|
| Companies whose match key was shortened by reading spaced single letters as a longer suffix | **1,865** at the widest. On 1,752 of them the registered name itself writes the four letters as one unit that stands apart from the name (`, P.L.L.C.`), so the reading is right. No name runs the letters together with dotted initials. **75** have a comma after the first letter, which is the shape Q28 describes, and 38 can be read either way |
| CONFIRMED links that point at one of them | **3**, all DBPR license links, and all three point at a company whose name writes the letters as one unit, apart from the name. **0** point at any of the 75 or the 38 |

Both counts are in Q28's row in `docs/open_questions.md`.

### Check 9: the offline checks

```
pytest                                  → 141 passed in 0.55s
ruff check src tests                    → All checks passed!
bash tests/hooks/test_block_secrets.sh  → failed cases: 0
```

---

## 3. Decisions I made and why

The brief said to take the most cautious reading when something was unclear, which in this phase is the one that shows less to a contractor and claims less.

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | The ten snapshot files got their manifest rows from `cordata.zip`, although the unpacked files are no longer on disk | The brief says to backfill files "still on disk" from their modification time, and not to estimate a time from anything else. The file that was fetched is the zip, it is on disk, and its modification time is the same evidence ruling R23 used for the lien snapshot. The size and checksum of each row are of the unpacked file, read out of the zip | 🔴 I assumed a zip on disk counts as its ten files being on disk. If that reading is wrong, the fix is to delete eleven manifest rows, and then `company_search` fails its `not_null` test, which is the "leave this bullet undone" outcome |
| 2 | The zip is read with the `unzip` program, not with Python's `zipfile` | The state packs the zip with a method called Deflate64, which `zipfile` can list and cannot unpack. The first run stopped with that error | The module depends on a program outside Python. macOS and Linux both ship it, and the test suite runs it on a small zip |
| 3 | `company_search` joins to the manifest on the file name with any trailing `.gz` removed | The staging model builds its join key by adding `.gz`, which fits the ten quarterly files and not the daily file, which was loaded uncompressed. Changing the staging model is not allowed | The join is written differently from the one the flag marts use. The header of `company_search.sql` says why |
| 4 | The no-names test allows exactly two columns of `company_search`, `entity_name` and `name_key`, and not the whole table | The existing exception for `entity_lookup` skips every column of that table, which the review of pull request 6 called a nit. A narrower exception means a new name-like column in `company_search` still fails the build | The exception is one line longer |
| 5 | `fetched_at_is_approximate` is true when either file behind a flag has an estimated fetch time: the file the record came from, or the file its release came from | A closed lien rests on both files. Marking only the later one would let "fetched Nov 18" stand on a lien whose own file's time is a guess | A lien from the snapshot that a measured daily file closed says "about", although the newer of its two times was measured |
| 6 | The new column sits after every existing column in `company_flags` | The brief says to add one column and move nothing. A column in the middle would shift every later column for anything that reads the table by position | The estimate mark is not next to `fetched_at` |
| 7 | The flag rules moved into macros, not into a new intermediate table | With a macro, `company_flags` compiles to the very same SQL as before, which is the strongest proof that nothing moved. A new table would have changed how `company_flags` is built | A macro is harder to read than a table, because the SQL is in another file. Each call site names the macro and the file |
| 8 | A possible match is one row per company, record, kind and reason | Two debtors on one lien can be AMBIGUOUS for the same company for different reasons, and each reason is decided on its own in the seed | One record can appear twice for one company. That is question Q30 |
| 9 | A record that is already a flag on a company is not also a possible match for it | A lien with one CONFIRMED debtor and one AMBIGUOUS debtor for the same company would otherwise be shown twice, once as a flag and once as "possible" | One more step in the mart, and one more line in its test |
| 10 | A reason that is missing from the seed is hidden, and a `relationships` test then fails the build | Hidden is the safe default, and the failing test makes sure somebody is asked | None |
| 11 | `source_coverage` holds the five loaded sources only. Court cases, UCC (Uniform Commercial Code) filings, other counties and fictitious names are not rows | Each row is a fact about data Datum holds, and the brief asks for `not_null` on `source_url` and `fetched_at` in every new mart. Those four things have no file behind them. They will be fixed wording in the app, in leg C3 | The "not checked" list comes from two places: this table's hidden rows, and the app's wording module |
| 12 | "Data through" for the company record is the snapshot date, 2026-10-07, although one daily file dated 2026-10-09 is loaded | A daily file holds only that day's new filings. Printing Oct 9 would claim that status changes through Oct 9 are covered, and they are not | A company that first appears in the daily file shows its own `published_on` of Oct 9 under a source line that says Oct 7 |
| 13 | "Data through" for DBPR licenses is the newest license issue date inside the file | 🟡 DBPR publishes no date for the file. The newest date in the data is the only date the data gives. Question Q32 | It is evidence of freshness and not a statement by DBPR |
| 14 | The Sunbiz address is a project variable and a seed row, and a test compares them | The same two-edit rule as ruling R28: a test that read the variable the model reads would agree with whatever it says | Changing the address means changing two files |
| 15 | Q28 is sized in a numbered script, and at three widths | The widest count says how many records a fix could touch, and the narrowest says how many are probably wrong today | The script reads the registered name to tell the widths apart. It prints none |

---

## 4. What I couldn't verify, and open questions for Andres

### Open questions (all four are in `docs/open_questions.md`)

1. **Q29: which reasons for a possible match may be shown?** This is the one the brief asks for. The counts are in check 4. `zip_differs` is 8,560 of the 9,651 rows.
2. **Q30: one record, one company, two reasons.** See decision 8.
3. **Q31: every company's fetch time is an estimate.** See check 7.
4. **Q32: the date to print for DBPR's licensee file.** See decision 13.

### What I couldn't verify

- 🔴 **That a zip on disk counts as its files being on disk** (decision 1).
- 🟡 **That a file's modification time is its download time.** It is the same assumption ruling R23 made. The evidence here is that both times fall after the state published the file and before Snowflake loaded it (check 1).
- 🟡 **The Sunbiz search page was not opened.** The brief says not to fetch it, because the site blocks automated access. The address is the one `docs/access/sunbiz.md` recorded as live on Sept 15, 2026.
- 🟡 **The 38 "spaces only" companies in Q28** cannot be sorted into right and wrong from the name alone.
- 🟡 **The session time zone in script 21's second check** is written as `America/Los_Angeles`, which `show parameters like 'TIMEZONE' in account` confirmed for this account today. If the account's time zone ever changes, old `loaded_at` values keep the old zone and that check would need both.

### The review

- **Tier:** High. The leg touches `pipeline/models/marts/`, `pipeline/macros/`, `pipeline/seeds/` and `pipeline/dbt_project.yml`, and each of those is High in `REVIEW.md`.
- **Depth:** Deep. Round 1 ran three `reviewer` subagents in parallel, each hunting one of the three things the brief names for Phase C, and then a fourth that checked every finding against the code. Round 2 ran one reviewer on the five fix commits only.
- **Rounds:** 2. No Important finding is open, and so no third round was needed.
- **Findings in all:** 2 Important, 5 Nit, 1 Pre-existing.

**Round 1** (three reviewers, then a verifier). The reviewers reported 7 findings, and the verifier confirmed all 7. It narrowed one of them and found that the fix one reviewer proposed would have broken the build.

| Reviewer's hunt | Finding | Tag | Answer |
|---|---|---|---|
| A sentence the data does not support | Script 22's group "written as one unit" also matched a name that runs the four letters together with dotted initials, so the Q28 row claimed more than the script counted. A column comment said "names made of initials" for a count that includes a name such as SMITH J | Nit | Fixed. The pattern is tighter, such names get a group of their own, and the comment is corrected. ✅ The counts did not change: 1,752 names stand apart and 0 are run together |
| A person's data or a hidden record leaking | The no-names test only caught a column named NAME, LICENSEE, RESPONDENT or DBA. A column named for a role, such as `debtor` or `officer`, would have passed | Pre-existing | Fixed all the same, because this leg adds three marts. The test now also fails on eight role words. The verifier found that the proposed pattern `%PARTY%` would have failed on the link models' existing `PARTY_SEQ` column, and so that one column is the stated exception |
| A test that cannot fail | No test could see a record that is MISSING from `company_possible_matches`. If the mart read the wrong links, it would be empty with every test green | Important | Fixed: the new test `assert_every_ambiguous_record_is_a_possible_match`, proven against an empty mart in check 5 |
| A test that cannot fail | The only test on `data_through` was `not_null`. Dating the company record by the daily file, which claims more than the data holds, failed nothing. The lien and discipline dates were worked out a second time and could drift from the flags' caveats, and the tie-break on the newest fetch time had no test | Important | Fixed: the new test `assert_source_coverage_dates_claim_no_more_than_the_data`, with six parts, each proven in check 5. `source_coverage` now takes the lien date from the macro `company_flags` uses |
| A test that cannot fail | The damaged-zip test exercised only one half of the check in `sunbiz_cor.py`, and the early return in `backfill_manifest` had no test | Nit | Fixed: two new tests |
| A test that cannot fail | One label in `assert_every_possible_match_traces_to_an_ambiguous_link` could never be reached, so such a row would be reported under the wrong problem | Nit | Fixed: that branch now comes first |
| A test that cannot fail | Eight `not_null` tests sit on columns that are a fixed value in the model, such as `company_search.source_url`, and so they cannot fail today. The verifier dropped the same claim about the `accepted_values` and `unique` tests, which can fail | Nit | Not changed. Each costs a fraction of a second, and each starts to matter the day someone replaces the fixed value with a join. The real guard on each column is another test, named in the table in check 2 |

One reviewer also raised a point it was not sure of and did not count: 19 of the possible matches are inactive licenses whose business name has no legal-entity word, so that name may be a person's, and each is tied to a company's document number in a mart. Rule W3 asks for these rows to be built and hidden, and they are hidden three ways. Whether that fits ruling R19 ("goes no further") is listed under "what a person should look at" in the pull request.

**Round 2** (one reviewer on the five fix commits).

| Finding | Tag | Answer |
|---|---|---|
| Script 22's comments and the Q28 row said "a space or a comma" in front of the four letters, and the pattern accepts any character that is not a letter, a digit or a period. One example in a comment could never reach its group | Nit | Fixed: the comments and the Q28 row now say what the pattern does. No SQL that runs changed |

The round 2 reviewer also answered, for every new test, what input makes it fail, and found no test that cannot. It noted that the two new SQL tests return nothing when a source has no flags at all, which is a pass on nothing and not a false alarm.

---

## 5. Credits used

**About 0.47 credits** on `datum_wh` (X-Small), roughly $0.95 at the $2 per credit the earlier reports use. That is the sum of the two lines below, read at 21:26 Pacific after the last query of the leg. The warehouse then idles for up to 60 seconds before it suspends, which can add at most 0.017. This is a one-time cost.

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATE_TRUNC('hour', DATEADD('hour', -12, CURRENT_TIMESTAMP())), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"

| START_TIME                | END_TIME                  | CREDITS_USED |
| 2026-11-20 20:00:00-08:00 | 2026-11-20 21:00:00-08:00 | 0.176424167  |
| 2026-11-20 21:00:00-08:00 | 2026-11-20 22:00:00-08:00 | 0.297818611  |
```

- Both lines are this leg. Nothing else ran on the warehouse in those two hours, and the first query was the credit check itself.
- The brief estimated 0.3 to 0.6 credits for this leg, and the leg landed inside that.
- The full build ran once (1 minute 38 seconds, with its 12 unit tests), and the smaller builds ran on one or two models each. The second hour cost more than the first because the review fixes and their ten proofs kept the warehouse awake in short bursts, and each burst is billed for at least 60 seconds.
- November stood at 2.33 credits before the leg, so it is at about 2.80 of the monthly cap of 10. Phase C has used 0.47 of its cap of 3.

---

## 6. Three questions Andres should be able to answer

1. A federal tax lien names two debtors. The first is CONFIRMED as company X. The second is AMBIGUOUS for company X with the reason `zip_differs`, and AMBIGUOUS for company Y with the same reason. How many rows does this lien produce in `company_flags`, and how many in `company_possible_matches`? Which rule decides the answer for company X?
2. Why does `assert_possible_matches_stay_hidden` compare `is_shown` with the word `false` written in the test, when the mart takes `is_shown` from a seed? What exactly would go wrong if the test read the seed too?
3. `source_coverage` says the company record runs through 2026-10-07, and yet 834 companies come from a file dated 2026-10-09. Why is Oct 7 the honest date to print, and what would a contractor wrongly conclude from Oct 9?

**Answers, to check yourself.** (1) One row in `company_flags`, for company X. One row in `company_possible_matches`, for company Y. Company X gets no possible match, because the same lien is already a flag on it (the `not exists` step at the end of `company_possible_matches.sql`, decision 9). (2) The seed is the switch. A test that read the same switch would pass whatever it said, and so changing one cell of a CSV file would show thousands of records with every test green. With the literal, showing a reason takes two reviewed edits, which is ruling R28. (3) The daily file holds only the companies that were newly filed that day. It says nothing about a status change to an older company on Oct 8 or Oct 9. Printing Oct 9 would tell a contractor that an older company's status is current through Oct 9, which the data does not support.
