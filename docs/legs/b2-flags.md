# Leg B2: open or closed, then the flags mart

Branch `leg/b2-flags` (stacked on `leg/b1-links`) · run 2026-11-18 (UTC) · status: **done, all tests pass. One address I could not verify (section 4, item 1) and one place where the data differs from what a ruling expected (section 4, item 2)**

Rulings implemented: R5, R6, R7, R9, R12, R16, R18, R20, R21, R22, and R27 and R28 after review round 1 (`docs/phase_b_rulings.md`).

## 1. What I built

Leg B1 said which company a record belongs to. This leg answers two more questions and then puts the answers in one table the app can read.

```
int_federal_lien_links ─┐                                  ┌─ federal_tax_lien        shown
int_federal_liens_status┴──────────────┐                   │
int_dbpr_license_links + stg licenses ─┼─▶ company_flags ──┼─ dbpr_license_inactive   shown
int_dbpr_discipline_links ─────────────┤   (mart, table)   ├─ dbpr_discipline         HIDDEN (R12)
int_duval_party_links ─┐               │                   └─ duval_lien / duval_tax_warrant / duval_judgment   HIDDEN (R20)
int_duval_document_status ─────────────┘
stg_datum__fetch_manifest ─▶ fetched_at on every row
```

**Is a federal lien open or closed?** `int_federal_liens_status`, one row per lien (ruling R6). A lien is open if it is in the latest quarterly snapshot or in a daily file after it, and no certificate of release has been published since. The status letter comes from the filings file only (R5). A certificate of discharge closes nothing; its date is carried as a fact. Liens we can't explain are marked `is_unexplained` and produce no flag (R7).

**Is a Duval lien, warrant or judgment open or closed?** `int_duval_document_status`, one row per document (ruling R18). A document is closed when a release or satisfaction links to it, by instrument number, or by book and page when the link has no instrument number. A partial release is counted and dated, and closes nothing.

**The flags mart.** `company_flags`, one row per fact on a CONFIRMED link.

| Column | What it holds |
|---|---|
| `document_number` | The company |
| `flag_type` | `federal_tax_lien`, `dbpr_license_inactive`, `dbpr_discipline`, `duval_lien`, `duval_tax_warrant`, `duval_judgment` |
| `fact_date` | The date of the fact: lien filed, license period began, complaint closed, document recorded |
| `status` | `open` or `closed`; `inactive` for a license |
| `status_note` | The events on the record, as sentences of fact: "Certificate of release filed 2026-11-16." |
| `source` | `sunbiz_flr`, `dbpr` or `duval` |
| `source_record_id` | The record's own number: filing number, license number, complaint number, instrument number. DBPR's search takes a license number, so a complaint's citation carries its license number as well (R27) |
| `source_url` | The official search page. No source offers a link to one record, so one ruling per source allows it: R9 for federal liens, R21 for Duval, R27 for DBPR. The approved addresses are the seed `search_page_sources` |
| `citation` | The record in words: "Duval County Official Records instrument 2010293806, book 15465 page 290" |
| `source_file` | The exact file the fact came from |
| `fetched_at` | When we fetched that file, in UTC, from the fetch manifest |
| `caveat` | What the reader must know before relying on the line |
| `is_shown` | May the app display it? False for Duval and for discipline |

Example rows (no names are in the mart):

| `flag_type` | `status_note` | `citation` |
|---|---|---|
| `federal_tax_lien` | Certificate of release filed 2026-11-16. | Florida Department of State federal lien filing 16FLR0010010 |
| `dbpr_license_inactive` | License CGC1508861: inactive, expires 2028-08-31. | Florida DBPR license CGC1508861 |
| `duval_lien` | Closed by RELEASE instrument 2026175757, recorded 2026-07-29. | Duval County Official Records instrument 2010293806, book 15465 page 290 |

| New or changed file | What it is |
|---|---|
| `pipeline/models/intermediate/int_federal_liens_status.sql` | One row per lien: `lien_status`, `closed_reason`, `released_on`, `discharge_recorded_on`, `is_unexplained`, the source files |
| `pipeline/models/intermediate/int_duval_document_status.sql` | One row per document: `document_status`, what closed it and when, partial releases, `recorded_before_window`, book and page |
| `pipeline/models/marts/company_flags.sql` | The mart |
| `pipeline/dbt_project.yml` | + `vars`: `show_duval: false`, `show_dbpr_discipline: false`, and the three search-page addresses |
| `pipeline/models/intermediate/_intermediate__models.yml`, `pipeline/models/marts/_marts.yml` | Column tests for the three models; two unit tests |
| `pipeline/tests/assert_every_flag_traces_to_a_confirmed_link.sql` | Every flag has a CONFIRMED link behind it, and none comes from an R7 lien |
| `pipeline/tests/assert_duval_flags_respect_the_allowlist.sql` | Every Duval flag is an allowlisted type; no flagged judgment has the State of Florida on the FRM side |
| `pipeline/tests/assert_hidden_flags_stay_hidden.sql` | Duval and discipline flags have `is_shown = false`, compared with the literal `false` and not with the two switches (R28, review round 1) |
| `pipeline/tests/assert_company_flags_one_row_per_flag.sql` | A company has a record as a flag at most once |

New in Snowflake: tables `DEV_INTERMEDIATE.INT_FEDERAL_LIENS_STATUS`, `DEV_INTERMEDIATE.INT_DUVAL_DOCUMENT_STATUS`, `DEV_MARTS.COMPANY_FLAGS`. Nothing existing changed.

## 2. Checks

### The done-when numbers

**Flags by type and by `is_shown`**

`snow sql -c datum -q "SELECT flag_type, is_shown, COUNT(*) flags, COUNT_IF(status='open') open_flags, COUNT_IF(status='closed') closed_flags, COUNT_IF(status='inactive') inactive_flags, COUNT(DISTINCT document_number) companies FROM datum.dev_marts.company_flags GROUP BY 1,2 ORDER BY 2 DESC, 1"`

```
| FLAG_TYPE             | IS_SHOWN | FLAGS | OPEN_FLAGS | CLOSED_FLAGS | INACTIVE_FLAGS | COMPANIES |
| dbpr_license_inactive | True     | 24    | 0          | 0            | 24             | 24        |
| federal_tax_lien      | True     | 9948  | 9864       | 84           | 0              | 5460      |
| dbpr_discipline       | False    | 379   | 9          | 370          | 0              | 318       |
| duval_judgment        | False    | 4528  | 4270       | 258          | 0              | 2251      |
| duval_lien            | False    | 7616  | 5885       | 1731         | 0              | 3577      |
| duval_tax_warrant     | False    | 1970  | 1213       | 757          | 0              | 1428      |
```

| | Flags | Companies |
|---|---|---|
| `is_shown = true` (federal liens, inactive licenses) | 9,972 | 5,484 |
| `is_shown = false` (Duval, discipline) | 14,493 | 6,920 |
| **All flags** | **24,465** | **12,295** |

**12,295 companies carry at least one flag.** 5,484 of them carry at least one that may be shown today. Of the 12,295, 6,232 are active on Sunbiz and 6,063 inactive. 109 companies have both a federal lien flag and a Duval flag.

**Open versus closed liens per source**

| Source | Records | Open | Closed |
|---|---|---|---|
| Federal tax liens, all 20,874 in `int_federal_liens_status` | 20,874 | 20,698 | 176 |
| Federal tax liens that became flags (CONFIRMED link) | 9,892 | 9,808 | 84 |
| Duval documents, all 22,021 in `int_duval_document_status` | 22,021 | 18,585 | 3,436 |
| Duval documents that became flags (CONFIRMED link) | 12,917 | 10,345 | 2,572 |

By Duval type, all documents in the status model: `LN` 9,483 open and 2,212 closed · `WRT` 1,412 and 897 · `JDG` 7,174 and 298 · `CCCJUDG` 516 and 29.

**Federal lien status in detail**

```
| LIEN_STATUS | CLOSED_REASON          | IS_UNEXPLAINED | UNEXPLAINED_REASON                                 | LIENS | WITH_DISCHARGE |
| open        | None                   | False          | None                                               | 20695 | 7              |
| closed      | certificate_of_release | False          | None                                               | 176   | 0              |
| open        | None                   | True           | release_recorded_before_the_snapshot_that_lists_it | 2     | 0              |
| open        | None                   | True           | cancellation_date_on_an_active_lien                | 1     | 0              |
```

176 closed = the 176 daily releases that point at a lien we hold (leg B0). All seven discharges are on open liens and show as "Certificate of discharge recorded on 2022-09-21." The three unexplained liens each had a CONFIRMED link, and none became a flag.

### dbt

`cd pipeline && dbt build --select "int_federal_liens_status int_duval_document_status company_flags"`

```
    Passed unit_test DEV_intermediate_dbt_test__audit.duval_status_follows_ruling_r18
    Passed unit_test DEV_intermediate_dbt_test__audit.lien_status_follows_rulings_r5_r6_and_r7
 Succeeded model DEV_intermediate.int_federal_liens_status (table)
 Succeeded model DEV_intermediate.int_duval_document_status (table)
 Succeeded model DEV_marts.company_flags (table)
    Passed test  not_null_company_flags_source_url
    Passed test  not_null_company_flags_fetched_at
    Passed test  not_null_company_flags_source_record_id
    Passed test  accepted_values_company_flags_flag_type__federal_tax_lien__dbpr_license_inactive__dbpr_discipline__duval_lien__duval_tax_warrant__duval_judgment
    Passed test  accepted_values_company_flags_source__sunbiz_flr__dbpr__duval
    Passed test  assert_duval_flags_respect_the_allowlist
    Passed test  assert_every_flag_traces_to_a_confirmed_link
    Passed test  assert_hidden_flags_stay_hidden
    Passed test  assert_company_flags_one_row_per_flag
    Passed test  assert_no_name_columns_past_staging
    ... (23 more passing column tests, left out here)
Finished 'build' successfully for target 'dev' [17.9s]
Processed: 3 models | 33 tests | 2 unit tests
Summary: 38 total | 38 success
```

The tests the brief names are the first seven lines after the models: `not_null` on `source_url`, `fetched_at` and `source_record_id`; `accepted_values` on `flag_type` and `source`; the Duval allowlist test; the CONFIRMED-link test.

**What the two unit tests prove** (made-up rows, no real data):
- `lien_status_follows_rulings_r5_r6_and_r7`: eight liens. Nothing filed since → open. A later daily release → closed, with its date and file. A discharge only → open, date carried. A release older than the snapshot that lists the lien → open and unexplained. Filed and released in dailies → closed. A cancellation date → unexplained. A status-`C` party row → unexplained. Filing status `L` → closed. A party-row status of `T` and an amendment event change nothing.
- `duval_status_follows_ruling_r18`: five documents. No link → open. A `RELEASE` by instrument number → closed. A `SAT` whose link gives only `-OR 012292/1479` → closed, matched to book 12292 page 1479. A partial release → open, counted. A release of some other document → nothing.

### Offline checks

```
$ pytest
60 passed in 0.22s
$ ruff check src tests
All checks passed!
```

### Every flag has a fetch time

`fetched_at` is never NULL (tested). It runs from 2026-11-05 18:14 UTC (the lien snapshot) to 2026-11-18 07:12 UTC (today's files). For a closed lien or document it is the later of two fetch times: the file the record came from and the file its release came from.

## 3. Decisions I made and why

| Decision | Why | Tradeoff |
|---|---|---|
| **A "later" release means one published after the file that lists the lien** | R6 says "no later COR exists". Two liens in the active snapshot have a release recorded years before the snapshot (2017 and 2023), each followed by an amendment, and the state still lists them as active. Reading every release as closing would contradict the filings file, which R5 makes the authority | Those two liens are open in the status model |
| **Those two liens produce no flag** | I can't explain a lien that is released and still active. R7's rule for the other oddities is "don't show what we can't explain", and I applied the same rule here. This is my addition, not a ruling | Two confirmed liens are withheld. They are marked, with the reason, in `int_federal_liens_status` |
| **Only `inactive` makes a license flag** (`secondary_status = 'I'`) | The flags table says "linked license with an inactive status". 137 CONFIRMED licenses are active but on probation (85) or suspended (52). Those two states come from discipline against the license holder, which R12 keeps off the report | 137 licenses with a disciplinary status produce no flag. Counted here so the choice is visible |
| **An active license is not a row in the mart** | The summary line counts flags ("2 flags found"), and an active license is not one. The brief: "one row per flag" | Spec A4 wants the report to show the status of any linked license. The app must read active licenses from `int_dbpr_license_links` and staging, or a small second mart is needed (section 4, item 5) |
| **"Inactive with the state" and "new company" are not in the mart** | They are in the plan's flags table, but they come from the company's own record, not from a link, and the brief's test says every flag traces to a CONFIRMED link | The app reads those two from `entity_lookup` |
| Two columns beyond the brief's list: `citation` and `source_file` | R9 wants the source file name in a federal lien's citation, and R21 wants book and page for Duval. `source_url` can only be a search page, so the specifics need somewhere to live | 13 columns, not 11 |
| The three search-page addresses are project variables | When a per-record link is found (Q9, Q11), one line changes | A reader looks in `dbt_project.yml` for the address |
| Duval status covers only documents with a business party on the TO side | R19: a document whose parties are all individuals goes no further than staging | 22,021 documents, not all 138,062 allowlisted ones |
| A Duval document recorded before 2025-01-01 gets an extra sentence in its caveat | Our files start on that day. A release recorded earlier can't be seen, so "open" is weaker for those documents (section 4, item 3) | A longer caveat on 7,248 open documents |
| The Duval caveat does not say liens lapse after a year | Q5 in the open-questions log: not stated on the report until counsel confirms | The plan's draft wording for that caveat is not used |
| The lien caveat states the date the lien files run through | "Open" is only known up to the last file the state published (2026-11-16), and the state publishes about weekly | The text changes whenever new files load |
| When a new quarterly snapshot is loaded, a lien that is only in an older one is closed | R6: "in the latest snapshot". Today there is one snapshot, so this branch is not yet exercised by real data; the unit test covers the status letter, not this case | Unproven on real data until January 2027 |
| Discipline `status` is `closed` when DBPR recorded a disposition date, else `open` | The plan's example is "Discipline case closed 2025-01-10" | 9 complaints have no disposition date |

## 4. What I couldn't verify, and open questions for Andres

1. **The federal lien search address is not verified.** 🟡 R9 says to cite "the Sunbiz federal lien search page". The state's site refuses automated requests (HTTP 403), so I could not open it. I used the state's search hub, `https://dos.fl.gov/sunbiz/search/`, which lists the federal lien search and which a web search confirms exists. Please open it in your browser, click through to the federal lien search by document number, and give me that page's address. It is one line in `pipeline/dbt_project.yml` (`sunbiz_lien_search_url`). The other two addresses are verified: `https://www.myfloridalicense.com/portalsearches/VerifyLicensee` ✅ (the address DBPR gives in its own ReadMe, quoted in `docs/access/dbpr.md`; it answered HTTP 200 on Nov 19) and `https://or.duvalclerk.com/` ✅ (in `docs/access/duval-official-records.md`). *Corrected in review round 1: this report first used `https://www.myfloridalicense.com/wl11.asp` for DBPR and leaned on R9 and R21, which cover federal liens and Duval only. Ruling R27 (Nov 19) now covers DBPR.*
2. **R18 expected 10,674 links that carry only book and page. The data has about 890.** When a link has no instrument number, the Clerk's file leaves the book and page columns empty and writes text into the last field instead. Of 10,717 such links: 9,021 say `-NONE`, 890 give a book and page I can read (`-OR 12292/1479`, `-O 12292/1479` or `-12292/1479`), and about 800 hold other text (`-NA`, a lone number, a place name). I followed the ruling: the 890 are matched by book and page. The effect is small: **8 of the 3,436 closed documents were closed through book and page**; 3,428 through an instrument number. A release whose link says `-NONE` can't close anything: 1,540 release-family rows are like that.
3. **"Open" is weak for old documents.** 7,248 of the 18,585 open Duval documents (6,808 of them liens) were recorded before 2025-01-01 and appear in our files only because the Clerk re-indexed them. A release recorded before 2025 is not in any file we hold, so some of these are surely released. The ruling says closed needs a linking document, so they are open, with a caveat sentence and the marker `recorded_before_window`. Before Duval is ever displayed, this needs a decision: load older files, or don't show documents recorded before the window.
4. **Only 24 inactive-license flags.** Inactive licenses rarely name a business (497 of 12,592), and 24 of those are CONFIRMED. The license flag is close to empty; the useful DBPR line for a contractor is probably "license active, expires …", which is information, not a flag.
5. **Active licenses have no home in the mart** (see section 3). Phase C needs them for spec A4. A second small mart (`company_licenses`) is the clean answer; it was not in this leg's brief.
6. **Federal liens and Duval liens may count the same IRS lien twice** (Q19). 109 companies have both. Not examined here.
7. **Status is as of 2026-11-16 for liens and 2026-11-16 for Duval.** Nothing reloads these on a schedule yet.
8. `fetched_at` for the eight lien files pulled by hand on Nov 5 is an estimate from file times (leg B0).

## 5. Credits used

**About 0.170 credits** on `datum_wh` (roughly $0.34).

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"
after B1 (23:34 Pacific, Nov 17):  0.275495278
after B2 (23:44 Pacific, Nov 17):  0.445662778
```

Phase B running total: 0.45 of the 3-credit cap.

## 6. Three questions you should be able to answer

1. A certificate of discharge (`COD`) is on seven open liens. Why does the status model leave them open, and what does the flag say about the discharge instead?
2. `company_flags` has 14,493 rows with `is_shown = false`. Which two project variables control them, and where do they live? The test `assert_hidden_flags_stay_hidden` first read the same two variables: what mistake could it NOT catch, and how does comparing with the literal `false` (R28) close that gap?
3. A Duval lien recorded in 2010 shows as `open`. Give the reason it might really have been released, and say which column and which sentence warn the reader.
