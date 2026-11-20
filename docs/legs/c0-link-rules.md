# Leg C0: two link rules from the review of pull request 5 (R29 and R30)

Branch `leg/c0-link-rules` (from `origin/main`) · run on Nov 19, 2026, Pacific time · risk tier **High** · status: **done. Every check passes, and the Deep review ended after three rounds with no Important finding left open.**

This is one extra leg that runs before Phase C. It changes the rule that decides whether a public record belongs to a company, and it changes nothing else.

**The short version**

- Two rulings that Andres made on Nov 19, 2026 are now in the linking macro, which is the one piece of SQL that all four link models share. A link model is a table that says which company a lien, a license, a complaint or a county record belongs to.
- **R29** stops a record whose ZIP code is malformed from being confirmed on its name alone. It turned exactly **30** CONFIRMED links AMBIGUOUS, which is the number the sizing predicted.
- **R30** stops a record from being confirmed when a second company has almost the same name. It turned **21** lien links and **344** license links AMBIGUOUS, against about 21 and about 346 predicted.
- R30 also turned **229 Duval links** and **1 discipline link** AMBIGUOUS. The sizing never counted those two sources. All 230 sit behind flags that are hidden today.
- No link became CONFIRMED because of this leg, and no link row was added or removed.
- All **20** links that Andres checked by hand are still CONFIRMED.

**What is left for Andres**

- Read section 3, which holds the calls I made where the rulings did not say, and section 4, which holds four open questions.
- Answer the three questions in section 6, because this is a High-tier change.

---

## 1. What I built

### The two rulings in plain English

The linking macro takes a name from a public record, strips it down to a **match key** (the name in capitals, without punctuation, minus one trailing legal suffix such as LLC or INC), and looks for companies with the same match key. It then decides between three answers: CONFIRMED, AMBIGUOUS or NO_MATCH.

Before this leg the macro had two gaps.

| Gap | What happened before | What happens now |
|---|---|---|
| A ZIP code that is present but is not 5 digits, such as `3225` | The macro treated the record as if it had no ZIP code, and it could confirm the link on the name alone | The link is AMBIGUOUS, with the reason `zip_unreadable` (ruling R29) |
| A second company with almost the same name, such as THE ACME next to ACME | The two names have different match keys, and so each looked like the only one | The macro counts near-namesakes on a looser key, and the link is AMBIGUOUS when it finds one (ruling R30) |

### The rule after this leg, top to bottom

The macro asks these questions in order for each record, and the first one that fits decides the outcome. The three rows marked **new** are this leg.

| # | The question | The outcome | Reason code |
|---|---|---|---|
| 1 | Does no company in Florida have this match key? | NO_MATCH | `no_company_with_this_match_key` |
| 2 | **New (R29).** Did the record give a ZIP code that is not 5 digits? | AMBIGUOUS | `zip_unreadable` |
| 3 | Is the ZIP code 5 digits, is exactly one company with this match key at that ZIP code, and is no near-namesake at that ZIP code? | May be CONFIRMED | `name_zip` |
| 4 | **New (R30).** The same as row 3, except that a near-namesake is at that ZIP code | AMBIGUOUS | `several_similar_names_same_zip` |
| 5 | Is the ZIP code 5 digits, and are two or more such companies at that ZIP code, or none? | AMBIGUOUS | `several_companies_same_zip`, `zip_differs` |
| 6 | No ZIP code. Do two or more companies have this match key? | AMBIGUOUS | `several_companies` |
| 7 | No ZIP code. Does the record's name lack a legal-entity word such as LLC? | AMBIGUOUS | `no_entity_word` |
| 8 | No ZIP code, one company with this match key, and no near-namesake anywhere in Florida | May be CONFIRMED | `unique_name` |
| 9 | **New (R30).** The same as row 8, except that a near-namesake exists somewhere in Florida | AMBIGUOUS | `several_similar_names` |

Ruling R2 still runs after this table. A record dated before the company's own filing date is never CONFIRMED.

### The looser key that counts near-namesakes

The new macro `namesake_key` builds the looser key from the match key. It is used only to count. The matching itself still uses the match key, which is why this leg cannot create a new CONFIRMED link.

| Step | What it does | Example |
|---|---|---|
| 1 | Every whole word AND becomes a space. An `&` was already turned into a space when the name was simplified, so the two now look the same | `SMITH AND SONS` and `SMITH & SONS` both become `SMITH SONS` |
| 2 | Runs of spaces become one space | |
| 3 | Every leading THE is removed | `THE ACME` becomes `ACME` |
| 4 | Every trailing legal suffix is removed. The match key removed only one | `ACME CO` (from ACME CO INC) becomes `ACME` |

A name made only of THE, AND and legal-form words, such as THE LIMITED INC, ends up with an empty key that all such names share. Section 3 explains why.

### Files

| File | What changed |
|---|---|
| `pipeline/macros/company_matching.sql` | The new macro `namesake_key`, the new flag `source_zip_is_unreadable`, three new steps that count near-namesakes, and three new branches in the rule |
| `pipeline/models/intermediate/int_federal_lien_links.sql` | Passes the whole ZIP field to the macro when its first five characters are blank (see section 3, decision 8). Its header comment now names R29 and R30 |
| `pipeline/models/intermediate/_intermediate__models.yml` | Seven new unit tests. A unit test runs a model's SQL on a handful of made-up rows and compares the result with the rows we expect |
| `docs/phase_b_rulings.md` | Rulings R29 and R30, under the new heading "Review of pull request 5 (decided by Andres, Nov 19, 2026)" |
| `docs/open_questions.md` | Questions Q26 to Q28 |
| `docs/legs/c0-link-rules.md`, `docs/review_log.csv` | This report, and the pull request's row in the review log |

Nothing new exists in Snowflake. The seven tables downstream of the macro were rebuilt in place, as every `dbt build` does. `src/datum/report.py` was not touched.

How the four link models pick the rulings up:

```
company_matching.sql (the macro)
   ├─▶ int_federal_lien_links      calls the macro, with ZIP codes
   ├─▶ int_dbpr_license_links      calls the macro, with ZIP codes
   │      └─▶ int_dbpr_discipline_links   does not call the macro: a complaint takes
   │                                      the status and reason of its license's link
   └─▶ int_duval_party_links       calls the macro, with no ZIP codes (R30 only)
```

---

## 2. Checks

### Check 1: new tests for each ruling, each proven able to fail

Seven new unit tests, all in `pipeline/models/intermediate/_intermediate__models.yml`:

| Test | Model | What it covers |
|---|---|---|
| `lien_links_follow_ruling_r29` | federal liens | Eight debtors: a ZIP code of four digits, one of five characters that are not digits, three kinds of empty ZIP code (NULL, an empty text, only spaces), a malformed ZIP code with two companies, one with no company, and a ZIP field that starts with blanks |
| `dbpr_license_links_follow_ruling_r29` | DBPR licenses | A contractor license and a `QB` business record with a malformed ZIP code, and a license with none |
| `lien_links_follow_ruling_r30` | federal liens | Eleven debtors: a near-namesake by THE (from both sides), by AND versus &, and by a suffix, at the same ZIP code and with no ZIP code, plus three controls that must stay CONFIRMED |
| `dbpr_license_links_follow_ruling_r30` | DBPR licenses | One near-namesake at the same ZIP code, one elsewhere, one control |
| `duval_links_follow_ruling_r30` | Duval | Two near-namesakes (THE, and a suffix), one control |
| `lien_links_namesake_key_edge_cases` | federal liens | Nine cases, one for each part of the namesake key |
| `lien_links_namesake_key_names_of_only_the_and_legal_words` | federal liens | THE LIMITED INC next to THE LIMITED, and THE THE INC next to THE INC |

DBPR discipline has no test of its own here, and section 4 says why.

**Against the old macro, every test fails.** I put the macro from `origin/main` back in place, ran the seven tests, and then restored the new macro and ran them again.

```
git show origin/main:pipeline/macros/company_matching.sql > pipeline/macros/company_matching.sql
cd pipeline && dbt test --select lien_links_follow_ruling_r29 dbpr_license_links_follow_ruling_r29 lien_links_follow_ruling_r30 dbpr_license_links_follow_ruling_r30 duval_links_follow_ruling_r30 lien_links_namesake_key_edge_cases lien_links_namesake_key_names_of_only_the_and_legal_words

    Failed unit_test dbpr_license_links_follow_ruling_r29 [2 of 7 in 3.37s]
    Failed unit_test lien_links_follow_ruling_r29 [4 of 7 in 3.87s]
    Failed unit_test lien_links_namesake_key_names_of_only_the_and_legal_words [6 of 7 in 3.72s]
    Failed unit_test dbpr_license_links_follow_ruling_r30 [1 of 7 in 3.90s]
    Failed unit_test lien_links_namesake_key_edge_cases [5 of 7 in 3.68s]
    Failed unit_test lien_links_follow_ruling_r30 [3 of 7 in 4.45s]
    Failed unit_test duval_links_follow_ruling_r30 [7 of 7 in 5.51s]
Summary: 7 total | 7 error
```

Each failure is the right one. In dbt's output, `expected -> actual` marks a cell that differs. This is the R29 lien test against the old macro, as it stood when the ruling was first written (the eighth debtor was added during review):

```
Test failed: lien_links_follow_ruling_r29
| SOURCE_RECORD_ID | PARTY_SEQ | DOCUMENT_NUMBER | LINK_STATUS            | MATCHED_ON          | LINK_REASON                         |
| Z1               | 1.0       | C21             | AMBIGUOUS -> CONFIRMED | NULL -> unique_name | zip_unreadable -> unique_name       |
| Z2               | 1.0       | C22             | AMBIGUOUS -> CONFIRMED | NULL -> unique_name | zip_unreadable -> unique_name       |
| Z3               | 1.0       | C23             | CONFIRMED              | unique_name         | unique_name                         |
| Z4               | 1.0       | C24             | CONFIRMED              | unique_name         | unique_name                         |
| Z5               | 1.0       | C25             | CONFIRMED              | unique_name         | unique_name                         |
| Z6               | 1.0       | C26             | AMBIGUOUS              | NULL                | zip_unreadable -> several_companies |
| Z6               | 1.0       | C27             | AMBIGUOUS              | NULL                | zip_unreadable -> several_companies |
| Z7               | 1.0       | NULL            | NO_MATCH               | NULL                | no_company_with_this_match_key      |
```

The old macro confirmed Z1 and Z2, the two debtors with a malformed ZIP code, and it left the three debtors with an empty ZIP code alone, which is what the test expects of them.

**Against the new macro, every test passes.**

```
git checkout pipeline/macros/company_matching.sql
cd pipeline && dbt test --select <the same seven tests>

    Passed unit_test dbpr_license_links_follow_ruling_r29 [1 of 7 in 4.22s]
    Passed unit_test duval_links_follow_ruling_r30 [3 of 7 in 3.95s]
    Passed unit_test lien_links_follow_ruling_r29 [4 of 7 in 4.37s]
    Passed unit_test lien_links_namesake_key_names_of_only_the_and_legal_words [5 of 7 in 3.95s]
    Passed unit_test dbpr_license_links_follow_ruling_r30 [2 of 7 in 4.76s]
    Passed unit_test lien_links_follow_ruling_r30 [7 of 7 in 4.61s]
    Passed unit_test lien_links_namesake_key_edge_cases [6 of 7 in 4.33s]
Summary: 7 total | 7 success
```

**Each part of the namesake key has a case that needs it.** The review asked for this (section 4). A throwaway script took one part out of the macro at a time, ran the three lien tests that cover R30, and put the macro back. Every removal made at least one case fail.

```
without the + on the suffix step (one or more suffixes): Summary: 3 total | 2 success | 1 error | cases that changed: E3
without the $ that pins the suffixes to the end: Summary: 3 total | 2 success | 1 error | cases that changed: E8
without the space put in front before the suffix step: Summary: 3 total | 2 success | 1 error | cases that changed: E1
without the + on the THE step (one or more THEs): Summary: 3 total | 2 success | 1 error | cases that changed: E11
without the ^ that pins THE to the start: Summary: 3 total | 2 success | 1 error | cases that changed: E6
without the space after THE: Summary: 3 total | 1 success | 2 error | cases that changed: E7, E11
without the space put on the end before the THE step: Summary: 3 total | 2 success | 1 error | cases that changed: E1
without the trim after AND is removed: Summary: 3 total | 2 success | 1 error | cases that changed: E4
without the step that turns runs of spaces into one: Summary: 3 total | 2 success | 1 error | cases that changed: N3, N7
without both word edges around AND: Summary: 3 total | 2 success | 1 error | cases that changed: E5, E9, E10
without the word edge in front of AND: Summary: 3 total | 2 success | 1 error | cases that changed: E9
without the word edge behind AND: Summary: 3 total | 2 success | 1 error | cases that changed: E10
without the whole AND step: Summary: 3 total | 1 success | 2 error | cases that changed: E4, N3, N5, N7
```

The existing unit tests were not edited, and they still pass. That is the evidence that the old behavior is unchanged wherever the rulings did not ask for a change.

### Check 2: `dbt build` on every model downstream of the macro

```
cd pipeline && dbt build --select int_company_match_keys+

 Succeeded model DEV_intermediate.int_company_match_keys (table) [1 of 81 in 7.83s]
 Succeeded model DEV_intermediate.int_federal_lien_links (table) [8 of 81 in 7.99s]
 Succeeded model DEV_intermediate.int_duval_party_links (table) [5 of 81 in 9.05s]
 Succeeded model DEV_intermediate.int_dbpr_license_links (table) [6 of 81 in 9.84s]
 Succeeded model DEV_intermediate.int_dbpr_discipline_links (table) [42 of 81 in 1.64s]
 Succeeded model DEV_intermediate.int_duval_document_status (table) [29 of 81 in 6.74s]
 Succeeded model DEV_marts.company_flags (table) [55 of 81 in 3.13s]
Finished 'build' successfully for target 'dev' [42.5s]
Processed: 7 models | 63 tests | 11 unit tests
Summary: 81 total | 81 success
```

The `+` after the model name means "this model and everything built from it". `int_company_match_keys` is the first model that uses the macro file, so the selection covers all four link models, the Duval status model and the flags mart. The 63 data tests include the ones that guard the flags mart:

```
    Passed test  assert_link_rows_are_consistent
    Passed test  assert_no_confirmed_link_before_company_filed
    Passed test  assert_every_flag_traces_to_a_confirmed_link
    Passed test  assert_hidden_flags_stay_hidden
    Passed test  assert_shown_flags_cite_an_approved_search_page
    Passed test  assert_company_flags_one_row_per_flag
    Passed test  assert_duval_flags_respect_the_allowlist
    Passed test  assert_dbpr_citations_carry_the_license_number
    Passed test  assert_no_name_columns_past_staging
```

This build ran at the branch's last code commit. I ran the same build four times in all (after the first version and after each review round), and every one passed.

### Check 3: the offline checks

```
source .venv/bin/activate
pytest                                  → 90 passed in 0.22s
ruff check src tests                    → All checks passed!
bash tests/hooks/test_block_secrets.sh  → 13 lines of "ok", then "failed cases: 0"
```

### Check 4: links and flags, before and after

"Before" is the tables as they stood at the start of the leg, built from `main` on Nov 18. Their CONFIRMED totals equal the ones in the sizing comment (10,046 lien and 120,672 license). "After" is the final build. Each number counts source records (a lien debtor, a license, a complaint, a party on a Duval document), not table rows.

| Source | link_status | matched_on | link_reason | Before | After | Change |
|---|---|---|---|---|---|---|
| federal_lien | CONFIRMED | `name_zip` | `name_zip` | 10,043 | 10,022 | -21 |
| federal_lien | CONFIRMED | `unique_name` | `unique_name` | 3 | 1 | -2 |
| federal_lien | AMBIGUOUS | (none) | `before_company_filed` | 35 | 34 | -1 |
| federal_lien | AMBIGUOUS | (none) | `several_companies_same_zip` | 433 | 433 |  |
| federal_lien | AMBIGUOUS | (none) | `several_similar_names_same_zip` | 0 | 22 | +22 |
| federal_lien | AMBIGUOUS | (none) | `zip_differs` | 6,204 | 6,204 |  |
| federal_lien | AMBIGUOUS | (none) | `zip_unreadable` | 0 | 2 | +2 |
| federal_lien | NO_MATCH | (none) | `no_company_with_this_match_key` | 5,814 | 5,814 |  |
| dbpr_license | CONFIRMED | `name_zip` | `name_zip` | 119,561 | 119,241 | -320 |
| dbpr_license | CONFIRMED | `unique_name` | `unique_name` | 1,111 | 1,059 | -52 |
| dbpr_license | AMBIGUOUS | (none) | `before_company_filed` | 6,764 | 6,701 | -63 |
| dbpr_license | AMBIGUOUS | (none) | `no_entity_word` | 129 | 127 | -2 |
| dbpr_license | AMBIGUOUS | (none) | `several_companies` | 310 | 306 | -4 |
| dbpr_license | AMBIGUOUS | (none) | `several_companies_same_zip` | 4,985 | 4,985 |  |
| dbpr_license | AMBIGUOUS | (none) | `several_similar_names` | 0 | 29 | +29 |
| dbpr_license | AMBIGUOUS | (none) | `several_similar_names_same_zip` | 0 | 377 | +377 |
| dbpr_license | AMBIGUOUS | (none) | `zip_differs` | 83,157 | 83,157 |  |
| dbpr_license | AMBIGUOUS | (none) | `zip_unreadable` | 0 | 35 | +35 |
| dbpr_license | NO_MATCH | (none) | `no_company_with_this_match_key` | 11,828 | 11,828 |  |
| dbpr_discipline | CONFIRMED | `name_zip` | `name_zip` | 374 | 373 | -1 |
| dbpr_discipline | CONFIRMED | `unique_name` | `unique_name` | 5 | 5 |  |
| dbpr_discipline | AMBIGUOUS | (none) | `before_company_filed` | 68 | 67 | -1 |
| dbpr_discipline | AMBIGUOUS | (none) | `several_companies` | 1 | 1 |  |
| dbpr_discipline | AMBIGUOUS | (none) | `several_companies_same_zip` | 23 | 23 |  |
| dbpr_discipline | AMBIGUOUS | (none) | `several_similar_names_same_zip` | 0 | 2 | +2 |
| dbpr_discipline | AMBIGUOUS | (none) | `zip_differs` | 265 | 265 |  |
| dbpr_discipline | NO_MATCH | (none) | `no_company_with_this_match_key` | 52 | 52 |  |
| duval | CONFIRMED | `unique_name` | `unique_name` | 14,121 | 13,892 | -229 |
| duval | AMBIGUOUS | (none) | `before_company_filed` | 153 | 140 | -13 |
| duval | AMBIGUOUS | (none) | `several_companies` | 2,620 | 2,620 |  |
| duval | AMBIGUOUS | (none) | `several_similar_names` | 0 | 242 | +242 |
| duval | NO_MATCH | (none) | `no_company_with_this_match_key` | 7,304 | 7,304 |  |

The same table by status only:

| Source | CONFIRMED before | CONFIRMED after | Change | AMBIGUOUS before | AMBIGUOUS after | NO_MATCH (unchanged) |
|---|---|---|---|---|---|---|
| federal_lien | 10,046 | 10,023 | -23 | 6,672 | 6,695 | 5,814 |
| dbpr_license | 120,672 | 120,300 | -372 | 95,345 | 95,717 | 11,828 |
| dbpr_discipline | 379 | 378 | -1 | 357 | 358 | 52 |
| duval | 14,121 | 13,892 | -229 | 2,773 | 3,002 | 7,304 |

**Where each changed link came from.** I saved every link row before the leg and after it to two local files and compared them row by row. The script prints counts only.

```
rows before 317668 rows after 317668
row keys only before 0 only after 0
rows whose status or reason changed: 714
dbpr_discipline  AMBIGUOUS before_company_filed         -> AMBIGUOUS several_similar_names_same_zip   1
dbpr_discipline  CONFIRMED name_zip                     -> AMBIGUOUS several_similar_names_same_zip   1
dbpr_license     AMBIGUOUS before_company_filed         -> AMBIGUOUS several_similar_names            5
dbpr_license     AMBIGUOUS before_company_filed         -> AMBIGUOUS several_similar_names_same_zip   57
dbpr_license     AMBIGUOUS before_company_filed         -> AMBIGUOUS zip_unreadable                   1
dbpr_license     AMBIGUOUS no_entity_word               -> AMBIGUOUS zip_unreadable                   2
dbpr_license     AMBIGUOUS several_companies            -> AMBIGUOUS zip_unreadable                   9
dbpr_license     CONFIRMED name_zip                     -> AMBIGUOUS several_similar_names_same_zip   320
dbpr_license     CONFIRMED unique_name                  -> AMBIGUOUS several_similar_names            24
dbpr_license     CONFIRMED unique_name                  -> AMBIGUOUS zip_unreadable                   28
duval            AMBIGUOUS before_company_filed         -> AMBIGUOUS several_similar_names            13
duval            CONFIRMED unique_name                  -> AMBIGUOUS several_similar_names            229
federal_lien     AMBIGUOUS before_company_filed         -> AMBIGUOUS several_similar_names_same_zip   1
federal_lien     CONFIRMED name_zip                     -> AMBIGUOUS several_similar_names_same_zip   21
federal_lien     CONFIRMED unique_name                  -> AMBIGUOUS zip_unreadable                   2
rows that BECAME confirmed: 0
```

This output reads as follows.

- ✅ The same 317,668 link rows exist before and after. No row was added or removed.
- ✅ No row became CONFIRMED.
- ✅ 625 rows went from CONFIRMED to AMBIGUOUS (21 + 2 lien, 320 + 24 + 28 license, 1 discipline, 229 Duval).
- ✅ The other 89 rows were already AMBIGUOUS and only changed their reason code, because a new branch now sits earlier in the rule than the branch that used to catch them (section 3, decisions 1 and 5).

**Expected size against real size**

| Ruling | Source | Expected | Real | Difference |
|---|---|---|---|---|
| R29 | Federal liens | exactly 2 | 2 | none |
| R29 | DBPR licenses | exactly 28 | 28 | none |
| R29 | DBPR discipline | "any of the 5" the sizing did not cover | 0 of the 5 | The 5 discipline links confirmed on a unique name are all still CONFIRMED, so none of their licenses has a malformed ZIP code |
| R30 | Federal liens | about 21 | 21 | none |
| R30 | DBPR licenses | about 346 | 344 | -0.6% |
| R30 | DBPR discipline | not sized | 1 | |
| R30 | Duval | not sized | 229 | |

Every sized number is within the 10% the brief allows, so no explanation was owed. Two notes all the same.

- ✅ The 2 missing license links are not missing. The sizing counted 26 license links confirmed on a unique name that have a near-namesake. Of the 28 links that R29 turned, 2 are among those 26 (a count query on those 28 links returned 2). R29 comes first in the rule, so it claimed them, and 24 + 2 = 26.
- ✅ On every link that R30 turned, the sizing query's key and the macro's key agree. A query checked each of the 670 link rows that now carry an R30 reason code (22 lien, 406 license, 242 Duval) against the looser key exactly as the sizing query Q3 wrote it, and Q3's key finds a near-namesake on all 670. The macro's key is written differently (section 3, decision 3), and this is the evidence that the difference changes nothing in today's data.

The Duval number is new information. Every Duval link is confirmed on a unique name, because the Clerk's index has no address, and that is the branch where a near-namesake anywhere in Florida counts. 229 of 14,121 is 1.6%. For comparison, 26 of the 1,111 license links confirmed on a unique name had a near-namesake, which is 2.3%, so the Duval share is in line.

**Flags, before and after**

A flag is one row of `company_flags`, the table the report will read. Only CONFIRMED links produce flags.

| Source | Shown today? | Flags before | Flags after | Change | Companies before | Companies after |
|---|---|---|---|---|---|---|
| `sunbiz_flr` (federal tax liens) | shown | 9,948 | 9,926 | -22 | 5,460 | 5,450 |
| `dbpr` (inactive license) | shown | 24 | 24 | 0 | 24 | 24 |
| `dbpr` (discipline) | hidden (R12) | 379 | 378 | -1 | 318 | 317 |
| `duval` (liens, tax warrants, judgments) | hidden (R20) | 14,114 | 13,885 | -229 | 6,609 | 6,506 |
| All | | 24,465 | 24,213 | -252 | | |

- Shown flags went from 9,972 to 9,950.
- 🟡 23 lien links turned AMBIGUOUS and 22 lien flags went away. The mart keeps one flag per lien per company and leaves out the liens ruling R7 excludes, so one of the 23 links had no flag of its own. I did not check which of the two reasons applies.
- ✅ 372 license links turned AMBIGUOUS and no shown license flag changed, so none of those licenses was an inactive one.

The commands: the counts come from one query over the four link tables, grouped by source, status, `matched_on` and reason, taking one row per source record, and from `select source, flag_type, is_shown, count(*), count(distinct document_number) from datum.dev_marts.company_flags group by 1, 2, 3`. Both ran with `snow sql -c datum -f <file>` before the first build and after the last one.

### Check 5: the 20 hand-checked links

`evals/link_sample_20.csv` is a local file that is not in git. A throwaway script matched each of its rows to the link tables on source, record number and company, and printed counts only.

```
links in the sample: 20
verdicts Andres typed: {'correct': 20}
still CONFIRMED: 20 of 20
```

✅ All 20 are still CONFIRMED, so there is no case id to list. The file has no case id column, and so a case id would have been the row's position in the file, 1 to 20.

### Check 6: credits

Section 5.

---

## 3. Decisions I made and why

The brief said to take the most cautious reading when something was unclear, which is the reading that confirms fewer links. Decisions 1, 3, 6, 7 and 8 are where I applied that.

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | Every record with a malformed ZIP code and at least one candidate company gets `zip_unreadable`, including records that were already AMBIGUOUS for another reason | R29 says such a row "never gets the unique-name branch". In the macro's own comments, that phrase means the whole path for records without a ZIP code, not only its confirming end | 12 license rows that were already AMBIGUOUS changed their reason code. The count of `zip_unreadable` records (37) is therefore larger than the 30 links R29 turned |
| 2 | The reason codes are `zip_unreadable`, `several_similar_names` and `several_similar_names_same_zip` | They follow the existing codes: `date_unknown`, `several_companies`, `several_companies_same_zip` | None |
| 3 | The namesake key is built from the match key, and it removes the whole word AND wherever it stands. The sizing query built its key from the full name and removed ` AND ` only between two other words | Building from the match key guarantees that every company with a record's match key also has the record's namesake key, so the near-namesake count can never miss the candidate itself. The match key has already cut one suffix, which can leave AND as the last word (`SMITH AND CO` becomes `SMITH AND`), so AND has to be removed at the end of a name too | The key is not letter for letter the one in the sizing comment. ✅ On every link R30 turned, the two keys agree (check 4) |
| 4 | The near-namesake counts are computed inside the macro, not stored as new columns on `int_company_match_keys` | The existing unit tests keep working unchanged, which proves the old behavior is intact. No existing model changes shape, and the whole rule stays in one file | Each of the three link models that call the macro works out the key for all 12,988,435 companies again. The whole build of 81 steps still takes about 43 seconds |
| 5 | The new R30 branch for records without a ZIP code comes last, after `several_companies` and `no_entity_word` | The existing reason codes stay where they were, so only records that would have been confirmed get the new code | A record with no legal-entity word and a near-namesake says `no_entity_word`, not `several_similar_names`. Both are AMBIGUOUS |
| 6 | An AMBIGUOUS link caused by a near-namesake still lists only the companies with the record's own match key. The near-namesake is counted, and it does not get a row | No link row is added or removed by this leg, which made the before-and-after comparison exact. The link tables keep their meaning: a row is a company whose match key equals the record's | A reader of an AMBIGUOUS row sees the reason code and not the other company. This is question Q27 for Phase C |
| 7 | A name made only of THE, AND and legal-form words gets an empty namesake key, shared with every other such name | The review found that THE LIMITED INC and THE LIMITED got different keys, and that the obvious fix broke the mirror pair, CORPORATION LLC and THE CORPORATION INC. The match key has already cut a suffix off such names, so no order of the steps pairs up both. One shared key does | 169 of the 12,988,435 companies have such a name, and they now all count as each other's near-namesakes. ✅ No CONFIRMED link pointed at any of them, so no link changed |
| 8 | The lien link model passes the whole 9-character ZIP field to the macro when the first five characters are blank | Staging cuts the 5-digit ZIP code from the first five characters. A field with five blanks and then something would have looked like "no ZIP code" and slipped past R29 | One more line in a High-tier model. ✅ 0 lien rows have this shape today, and the DBPR staging model does not have the gap |
| 9 | The two new conditions are written as "the count equals 1", not "the count is not more than 1" | If a count were ever missing, "equals 1" is not true, and the link is not confirmed. The rule fails toward AMBIGUOUS | None |
| 10 | R29 and R30 are separate commits, each with its tests, after one commit that records the two rulings | CLAUDE.md rule 5: one concern per commit, with its test | None |

---

## 4. What I couldn't verify, and open questions for Andres

### Open questions

1. **Duval and discipline were outside the sizing.** R30 turned 229 Duval links and 1 discipline link AMBIGUOUS, and both sources are hidden today. I applied the ruling as written, to every link model. If 229 is more than you expected, the place to look is the revisit clause of R30.
2. **R30's revisit clause has no evidence yet, either way.** It says to revisit "if the hand checks show the looser key blocking links that are clearly right". All 20 hand-checked links are still CONFIRMED, so the sample says nothing about the 595 links R30 turned (21 lien, 344 license, 1 discipline, 229 Duval). A hand check of ten or so of those would be the first real evidence.
3. **Spaced single letters can be read two ways (Q26).** The key reads the match key `L L C` as the suffix LLC and empties it. The first version of the key read it as the letter L followed by the suffix LC, which grouped it with companies whose match key is `L`. ✅ In the data this affects one group: 4 companies with the match key `L L C` and 19 with `L`. No link changes because of it. Round 3 of the review found the same class and tagged it Pre-existing and uncertain. I left the reviewed code as it is.
4. **A near-namesake is counted and not listed (Q27).** See decision 6. Phase C should decide whether the report ever shows AMBIGUOUS candidates, and if so, whether the near-namesake belongs in the list.
5. **Something I noticed and did not change (Q28).** The existing match key, from leg B1, can read the end of a name made of spaced initials as a longer suffix. A name such as `A.B.C.P., L.L.C.` simplifies to `A B C P L L C`, and the match key removes `P L L C` as if it were the suffix PLLC, which leaves `A B C`. That company would then share a match key with a company called `A.B.C., INC.`. 🟡 A count found one group in the data whose keys have this shape. I worked the cause out from the keys and did not look at the name, and I did not size it further, because it is not part of R29 or R30.

### What I couldn't verify

- 🟡 **DBPR discipline has no unit test for the two rulings.** A complaint takes its license's link status and reason, and the discipline model does not call the macro. A unit test for it would pass against the old macro, and the brief asks for tests that fail against it. The evidence is the data: the discipline counts in check 4 moved with the license counts (1 link turned, and the 5 unique-name links unchanged), and the build's consistency tests pass.
- 🟡 **Which of two reasons explains 22 lien flags for 23 lien links** (check 4).
- 🔴 **I assumed "empty" means NULL or only spaces.** Staging already turns a blank ZIP code into NULL, so in practice only NULL arrives. The macro treats both as empty, and the test covers both.

### The review

- **Tier:** High, set by `pipeline/macros/company_matching.sql`.
- **Depth:** Deep. Round 1 ran three `reviewer` subagents in parallel, each hunting one thing, and then a fourth that checked every finding against the code. Rounds 2 and 3 ran one reviewer on the new commits only, hunting the same three things, as round 2 of pull request 6 did.
- **Rounds:** 3, the most the rules allow. No Important finding is open.
- **Findings in all:** 4 Important, 5 Nit, 1 Pre-existing.

**Round 1** (three reviewers, then a verifier). The reviewers reported 6 findings. The verifier confirmed 5, raised one from Nit to Important, and dropped 1 as a duplicate.

| Reviewer | Finding | Tag | Answer |
|---|---|---|---|
| A person's data past staging | 0 findings: nothing to fix | | |
| A test that cannot fail | No test needed the "one or more" on the suffix step. Three test comments claimed to cover two suffixes and did not | Important | Fixed: case E3, a company whose match key still ends in two suffixes |
| A test that cannot fail | Four more parts of the key could be removed with no test failing | Nit | Fixed: cases E4 to E8 |
| A test that cannot fail, and a wrong link | When a near-namesake blocks a link, a company with the same match key at another ZIP code gets no row. No test said so, and the macro's description said otherwise | Nit | Fixed: the description now matches, and case N1 has such a company and expects one row. The behavior did not change |
| A wrong link | A lien ZIP field that starts with five blanks counted as "no ZIP code" | Nit | Fixed: decision 8 and case Z8. ✅ 0 rows today |
| A wrong link | THE LIMITED INC and THE LIMITED got different keys, so a link R30 forbids could be CONFIRMED | Important (the verifier raised it, and showed that the fix the reviewer proposed would break the mirror pair) | Fixed: decision 7. ✅ No link changed |

**Round 2** (one reviewer on the four fix commits).

| Finding | Tag | Answer |
|---|---|---|
| The round 1 fix removed a leading THE only once, so THE THE INC and THE INC got different keys, a pair the first version had kept together | Important | Fixed: the key removes every leading THE, with case E11, which failed before the fix |
| The case for THE LIMITED INC could not fail on its own part of the key, because other companies in the same test shared the empty key | Important | Fixed: the case moved to a test of its own |
| The control for AND inside a word only failed when both word edges were removed | Nit | Fixed: two more controls, one for a word that ends in AND and one for a word that starts with it |

**Round 3** (one reviewer on the two round 2 commits).

| Finding | Tag | Answer |
|---|---|---|
| The description of case E2 claimed the case guards more than it does | Nit | Fixed: the description now says exactly what the case catches. No test row and no SQL changed |
| Match keys made only of spaced suffix letters (`L L C`, `L L L C`) no longer share a key with each other in every case | Pre-existing, and the reviewer was not sure it matters | Not changed. It is open question 3 above and Q26 |

After each round I rebuilt everything downstream of the macro and compared every link row with the first build. ✅ No row's status or reason changed in any round, so every number in check 4 held from the first build to the last.

---

## 5. Credits used

**About 0.64 credits** on `datum_wh` (X-Small), roughly $1.29 at the $2 per credit the earlier reports use. That is the sum of the last two lines below, 0.076 and 0.567, read at 18:36 Pacific after the last query of the leg. The warehouse then idles for up to 60 seconds before it suspends, which can add at most 0.017. This is a one-time cost, and nothing in this leg recurs.

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATE_TRUNC('hour', DATEADD('hour', -12, CURRENT_TIMESTAMP())), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"

| START_TIME                | END_TIME                  | CREDITS_USED |
| 2026-11-19 11:00:00-08:00 | 2026-11-19 12:00:00-08:00 | 0.023448056  |
| 2026-11-19 16:00:00-08:00 | 2026-11-19 17:00:00-08:00 | 0.111603611  |
| 2026-11-19 17:00:00-08:00 | 2026-11-19 18:00:00-08:00 | 0.076167500  |
| 2026-11-19 18:00:00-08:00 | 2026-11-19 19:00:00-08:00 | 0.567453611  |
```

- The first two lines are not this leg. The second one holds the sizing queries for pull request 5, which finished at 16:58 Pacific. My first query ran at 17:54, so everything from the 17:00 hour on is this leg.
- This leg cost more than any earlier one, and the reason is the testing, not the data. A dbt unit test runs in Snowflake, and the warehouse stays awake for 60 seconds after each query. The leg ran the unit tests about fifty times: twice for each fail-then-pass proof, once after each edit, and once for each part of the key that was taken out (six parts in round 1, then thirteen in round 2). The warehouse was therefore awake for most of the time after 18:00. The four full builds took about 43 seconds each.
- A cheaper habit for next time is fewer runs: trace a change through the SQL by hand first, and run each proof once at the end of a round, so that the warehouse can go back to sleep in between.
- 🟡 Phase B stood at about 0.96 credits before this leg, going by what the leg reports and the sizing comment record (four legs at 0.54, two review rounds at 0.29 and 0.06, and the sizing at 0.07). With this leg the total is about 1.60, against the cap of 3 that the brief sets for Phase B.

---

## 6. Three questions Andres should be able to answer

1. A lien is filed against `ACME LLC` at ZIP code 32256. Florida has `ACME INC` at 32256, `THE ACME LLC` at 32256 and `ACME CORP` at 33101. What does the macro return, with which reason code, and how many rows? What would it have returned before this leg?
2. Why does the macro count near-namesakes on the looser key and still match on the match key? What could go wrong if it matched on the looser key too?
3. A record's ZIP code is `3225`. Why is "this ZIP code is unreadable" a different fact from "this record has no ZIP code", and which rule in `CLAUDE.md` says the macro may not treat them the same?

**Answers, to check yourself.** (1) AMBIGUOUS, `several_similar_names_same_zip`, one row, for `ACME INC`. Exactly one company with the match key `ACME` is at 32256, so the company at 33101 gets no row, and `THE ACME LLC` is a near-namesake at the same ZIP code. Before this leg it was CONFIRMED on `name_zip`. (2) Counting can only take a confirmation away. Matching on the looser key could add one: a record for `ACME` could be pinned on `THE ACME`. (3) An empty ZIP code means there is nothing to compare, and R1 then allows a unique name to confirm. A malformed one means the source said something we can't read. Rule 3 says never to fill a gap with an inference.
