# Leg D1: search the way contractors search

Branch `leg/d1-contractor-search` (from `main`) · pull request [#25](https://github.com/andrescamacho57/datum/pull/25) · run on Nov 25, 2026 · risk tier **High** · status: **built and reviewed, with every check passing. The Deep review ran its three rounds. The third found one Important fault, in a test, and it is fixed. That last fix was not reviewed, because no fourth round is allowed. Nothing is merged.**

This is the first of the two legs of Phase D. On Nov 24 Andres tried the web app on a restaurant he knows, and it failed him twice: `v pizza orlando` did not show the right company, and `8586 palm pwwy` found nothing. This leg adds test cases for both, builds a search by address, and builds and measures the new order the brief asked for.

**The short version**

- **The address search works. The name search still fails for the restaurant, and the new ranking is built but not switched on. Read these three first.**
  1. **`8586 palm pwwy` now finds the restaurant.** On the real app it shows **V PIZZA LAKE BUENA VISTA LLC**, alone, in 1.05 seconds, and says that 3 inactive companies also match and are not listed.
  2. **`v pizza orlando` still does not show it, and a new order could not have fixed that.** The brief said the cause was the order in `rank()`. It is one step earlier. The search has two steps: step 1 asks the database for the 200 names nearest to what was typed, and step 2, `rank()`, puts those 200 in order. For "V PIZZA", **10,062** names pass step 1, and the right company stands **2,861st** in step 1's own order. It is never among the 200, so no order of the 200 can put it first.
  3. **Rule S2, the new order, is built and tested, and the app does not use it.** S2 left every checked case's rank exactly where it was. On the page a contractor sees, it moved checked case 9's right company from first to second. The one variant that rule S3 allows does the same. Rule S3 says what to do then: keep the old ranking, record both results, and put this first in the report. So the app ranks as it did before this leg.
- 🔴 **Fixing `v pizza orlando` takes three decisions, and they are one decision.** I measured them in a scratch script and built none (check 9).
  - Change step 1 so that names holding every typed word come first (question Q46). Alone, it brings the right company to 17th.
  - Switch rule S2 on (question Q52). Together with the first, the right company is **1st**.
  - Decide what to do about case 9, which S2 moves to second on the page because the page shows its five companies by match level (question Q51).
- **The evaluation went from 7 to 8 of 13 right,** and all of the gain is the address case.

| Measure, on the 13 checked cases | Before Phase D | Now |
|---|---|---|
| Top-1: the first answer is the right company | 7 | **8** |
| Recall at 5: the right company is in the first five | 9 | **10** |
| `wrong_match`: the search answered, and with the wrong company | 4 | 4 |

- **Both searches meet the speed target,** a p95 under 1 second. The p95 is the time that 95 of every 100 searches beat. The name search measured **515 milliseconds** over 210 searches and the address search **175 milliseconds** over 200, each on the first run after Postgres was restarted.
- **An address where more than 50 companies match lists none of them.** That limit is mine and not the brief's. Of 200 addresses drawn at random, 46 got that answer (question Q48).
- The database grew from 5,503 MB to **6,367 MB**, because of the new address table.
- The offline tests pass with Postgres stopped: **512**, of which 56 are new.
- The leg made **27** live extraction calls of the 30 the phase allows, and used **no Snowflake**.
- The Deep review ran three rounds and found 8 Important problems. Seven are fixed and one is a privacy decision that is yours (question Q45). The last fix, one line of a test, was not reviewed.

**What is left for Andres**

1. **Rule on questions Q46, Q52 and Q51 together.** Without a ruling, `v pizza orlando` keeps failing. Check 9 has one table with what each choice does to every checked case.
2. **Check the 16 draft cases.** They are in `evals/draft_cases.csv` on your Mac, and git ignores them. Section 7 gives the steps.
3. **Rule on five more questions** this leg could not decide. Each has a row in `docs/open_questions.md`.
   - Q45: should the inactive companies at an address be listed, and should an address that may be a home be searchable at all? The review added a sharper form of it: a one-person company is often named after its owner and registered at the owner's home.
   - Q47: should a suite on the record stop an address from matching?
   - Q48: is 50 the right limit for a crowded address?
   - Q49: should the terminal command get the search by address too?
   - Q50: the extraction step takes a place name out of the business name. Should the search look for it there?
4. **Read the new sentences** in section 1. Wording is your call.
5. Answer the three questions in section 6, because this is a High-tier change.

**The history, in order**

| When | What happened |
|---|---|
| Nov 25, first pass | The three checked cases and the 16 drafts were written and extracted. Rule S2 was built and made the app's order, because by rank it moved no checked case. The address search was built, loaded and measured |
| Nov 25, review round 1 | Three reviewers and a security review read the leg, and a fourth reviewer confirmed 10 of 12 findings. One of them was that the evaluation scores the rank while the page shows the five by match level |
| Nov 25, after round 1 | Following that finding up showed that S2 moves case 9 on the page. The variant was measured and does the same, so the app went back to its old order (rule S3). The evaluation now compares both places. The other findings were fixed, Postgres was loaded again, and every check in this report was run again on the final code |
| Nov 25, rounds 2 and 3 | Round 2 found a sentence that could be false and two wrong sentences in the Human review section. Round 3 found one assertion that could not fail. All four are fixed |

---

## 1. What I built

### The picture

```
 the note a contractor types
        │  one model call (extract.py, prompt v3) reads the business name, the city and the street
        ▼
 search_kind()  decides from those three fields, and never from the note itself
        │
        ├── a business is named ─────────────────▶ NAME SEARCH
        │                                           step 1  Postgres: the 200 names nearest to the typed name   (not changed)
        │                                           step 2  rank(): similarity, then city, then document number  (not changed)
        │                                                   rule S2 and its variant: built, tested, NOT used
        │                                           ──▶ the shortlist of five, as before
        │
        ├── no business, and a street with ──────▶ ADDRESS SEARCH  (new)
        │   a house number and a street name        Postgres: company_search_addresses, by house number
        │                                           street_matches(): every word of the stored street was typed
        │                                           ──▶ the active companies that match, by document number,
        │                                               and a count of the inactive ones
        │
        └── neither ────────────────────────────▶ ASK for a name or an address. No company is shown
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| Three rows in `pipeline/seeds/test_set.csv`, case group `contractor_search` | Checked cases 11, 12 and 13: `v pizza orlando`, `v pizza lake buena vista` and `8586 palm pwwy`. All three expect V PIZZA LAKE BUENA VISTA LLC | The ten older cases are all names, so they could not catch either failure. Andres confirmed the restaurant and its address on Nov 24 |
| `evals/draft_cases.csv` and `evals/draft_extracted.csv` | 16 cases I drafted from the register, and what the extraction step read from each. Git ignores both files | Working rule S1: a case enters the test set only when Andres has checked it |
| `src/datum/extract.py`, prompt v3 | The extraction step. Its street line now asks for the house number and the street exactly as typed. The command now extracts only the case ids it is given and appends their rows | The address search reads the house number from the start of the street. The old command extracted the whole test set again and overwrote the file, which would have replaced the rows prompt v2 made for cases 1 to 10 |
| `by_words_then_city()` and `by_city_then_words()` in `src/datum/search.py` | Rule S2 and its one permitted variant, each as a sort key. S2 puts first the companies whose name holds every typed word, then the ones in the city given, then the higher similarity, then the document number. The variant swaps the first two | Working rules S2 and S3. Both are tested and neither is used. `RANK_ORDER` is the one line that says which order the app uses, and it still names search version 1's |
| `company_search_addresses`, built by `src/datum/load_postgres.py` | A narrow table in Postgres with one row per company: the document number, the house number at the start of its principal address, and the words of the street after it | The address search looks a house number up in an index. Cutting 13 million addresses on every search would be far too slow |
| `street_parts()`, `street_matches()`, `search_kind()` and `address_search()` in `src/datum/search.py` | The rules of the address search, in plain Python | Working rules S5 to S7, and `CLAUDE.md` rule 1: anything a test can assert is plain code |
| `by_address()` in `src/datum/web/app.py`, and two templates | The page a contractor sees for an address | Working rules S5, S6 and S8 |
| `evals/run.py` | The evaluation. It now scores the draft cases in a table of their own, follows the app's three paths, keeps the expected company's place by rank and on the page, and can compare two runs: before Phase D against now, or the app's order against another | Working rules S1 and S3, and the brief's "the evaluation follows the app" |

### How the address search decides that an address matches

The typed street and the stored address are both simplified the same way: capitals, and anything that is not a letter or a digit becomes a space. The first word is the house number when it begins with a digit. A numbered street is the exception: in `4th st south` the first word names the street, so there is no house number. Then three rules apply.

| Rule | Example |
|---|---|
| The house number must be the same | `8586` matches `8586`, and not `8587` or `858` |
| The kind of street and the four directions N, S, E and W are left out on both sides | The typed `palm pwwy` leaves PALM and PWWY. The stored `PALM PKWY` leaves PALM |
| Every word that is left of the STORED street must be among the typed words | PALM is among PALM and PWWY, so they match. The mistyped PWWY does no harm, because nothing has to match it |

The comparison runs one way only. A typed word the record does not have is allowed. A word of the record that was not typed is not, so a suite on the record (`STE 200`) or a word left out of what was typed is a miss. When a city was read from the note, the company's principal city must also begin with it, which is the comparison the name search uses.

The match is loose on purpose, and so the page says "matches" and never "is at this address", and it shows each listed company's own address as the state has it. `8586 palm pkwy` would also list a company at `8586 PALM AVE`, and the reader can see that.

### The sentences this leg added or changed

These are the entries of `src/datum/wording.py` that are new or different. A piece in curly braces is filled in when the sentence is used.

| Name in `wording.py` | The text |
|---|---|
| `SEARCH_HINT` (changed) | A business name and its city, or a street address that begins with its house number. |
| `NOTE_EMPTY` (changed) | Nothing was typed. Type the business's name and its city, or a street address that begins with its house number. |
| `NOTE_TOO_LONG` (changed) | That is too long to search for. Type the business's name and its city, or a street address that begins with its house number. |
| `ASK_FOR_A_BUSINESS_ON_A_PAGE` (changed) | That describes a business but doesn't name one. Add its name, or its street address beginning with the house number. |
| `ADDRESS_HEADING` | Companies by principal address |
| `ADDRESS_COMPARED` | A company matches when its principal address on record has the house number {house_number} and a street name made only of words you typed. The kind of street, such as ST or PKWY, and a direction, N, S, E or W, are not compared. |
| `ADDRESS_COMPARED_CITY` | Its principal city on record also begins with the city you gave. |
| `ADDRESS_COMPARED_NO_CITY` | You gave no city, so a match can be in any city. |
| `ADDRESS_ACTIVE_ONE` | 1 active company matches. |
| `ADDRESS_ACTIVE_MANY` | {count} active companies match. They are in document-number order, which says nothing about which one you mean. |
| `ADDRESS_NO_ACTIVE` | No active company matches. |
| `ADDRESS_INACTIVE_ONE` | 1 inactive company also matches and is not listed. |
| `ADDRESS_INACTIVE_MANY` | {count} inactive companies also match and are not listed. |
| `ADDRESS_NO_STATUS_ONE` | 1 company with no status on record also matches and is not listed. |
| `ADDRESS_NO_STATUS_MANY` | {count} companies with no status on record also match and are not listed. |
| `PRINCIPAL_ADDRESS_NOTE` (rule S8, word for word) | A company's principal address is the address it gave the state, which is not always where it does business. |
| `ADDRESS_NOT_FOUND` | No company matches: none has a principal address on record with that house number and a street name made only of words you typed. Check the house number and the spelling of the street's name, and add the suite or unit if the address has one. |
| `ADDRESS_NOT_FOUND_IN_CITY` | No company matches: none has a principal address on record with that house number, a street name made only of words you typed, and a principal city that begins with the city you gave. Check the house number, the spelling of the street's name and the city, and add the suite or unit if the address has one. |
| `ADDRESS_TOO_MANY` | That house number and street name are on the records of too many companies to list them. Add the business's name. |
| `COMPANY_RECORDS_CITATION` | Florida Division of Corporations (Sunbiz) company records |
| `IDENTIFIED_BY_ADDRESS` | from {fields} · found by its principal address on record (the same house number, and a street name made only of words that were typed) · chosen by the user from the active companies listed. |
| `ADDRESS_OTHERS_ONE` | 1 other active company was listed with it. |
| `ADDRESS_OTHERS_MANY` | {count} other active companies were listed with it. |

The terminal's two questions, `ASK_FOR_A_BUSINESS` and `ASK_FOR_MORE`, still end "a street or a city". The terminal has no search by address (question Q49), so its words were left as they were.

### Files

| File | New or changed |
|---|---|
| `pipeline/seeds/test_set.csv`, `pipeline/seeds/extracted_inputs.csv` | Changed: 3 rows added to each. No existing row was touched |
| `.gitignore` | Changed: the two draft files |
| `src/datum/extract.py`, `tests/test_extract.py` | Changed and new. 7 tests |
| `src/datum/search.py`, `tests/test_search.py` | Changed. 105 tests, 11 of them new |
| `src/datum/load_postgres.py`, `tests/test_load_postgres.py` | Changed. 19 tests, 5 of them new |
| `src/datum/web/app.py`, `src/datum/web/templates/address.html`, `src/datum/web/templates/_address_candidate.html`, `tests/test_web.py` | Changed and new. 95 tests, 11 of them new |
| `src/datum/wording.py`, `tests/test_wording.py` | Changed. 12 tests, 3 of them new |
| `src/datum/models.py`, `tests/test_models.py` | Changed: `AddressCandidate` is new, and `Identification` now says whether a company was found by its name or by its address. 25 tests, 2 of them new |
| `src/datum/report_builder.py`, `tests/test_report_builder.py` | Changed: a report can say that its company was found by its address, and a count of companies is a `Fact`. 31 tests, 3 of them new |
| `evals/run.py`, `tests/test_evals_run.py` | Changed. 33 tests, 14 of them new |
| `docs/open_questions.md` | Changed: Q42 answered in part, and Q45 to Q52 added |

`src/datum/report.py`, the terminal command, was not touched. No Snowflake object and no dbt model was touched. In Postgres the leg added one table, `company_search_addresses`, and one index on it.

---

## 2. Checks

### Check 0: the three things the brief says to check before the first leg

| What the brief asks | Result |
|---|---|
| Pull requests 21 and 22 are merged | ✅ `src/datum/wording.py`, `src/datum/report_builder.py` and `src/datum/web/app.py` are on `origin/main` |
| Postgres holds the data | ✅ `company_search` in `datum_dev` has 12,988,435 rows |
| The exported files are still on the Mac | ✅ `data/export/` holds the files of `company_search` (8 files), `company_flags` (7) and `source_coverage` (1), and the file of row counts. `company_possible_matches` has no file, and that is correct: every possible match is hidden, so the export wrote 0 rows and no file, and the counts file says 0 |

### Check 1: the evaluation, before Phase D and now

The evaluation is a fixed set of cases with known answers. `--before` scores every case twice: with the search as it is now, and with the search as it was before Phase D, when a note that named no business was always asked for more.

```
python -m evals.run --backend postgres --before

backend: postgres (narrow table, word similarity)

checked cases (pipeline/seeds/test_set.csv)
case  group                 expected        answer          top-1  top-5  wrong_match  place of the expected company
   1  legal_name_variant    P98000033661    P98000033661    yes    yes    no           1 of 1
   2  legal_name_variant    L26000514010    L26000514010    yes    yes    no           1 of 1
   3  legal_name_variant    P18000005972    P96000014879    no     yes    YES          2 of 10
   4  legal_name_variant    L14000186157    L14000186157    yes    yes    no           1 of 12
   5  legal_name_variant    L26000480461    L26000480461    yes    yes    no           1 of 1
   6  legal_name_variant    P02000008536    P02000008536    yes    yes    no           1 of 27
   7  legal_name_variant    L22000096579    NEEDS_MORE_INFO no     no     no           asked
   8  legal_name_variant    L26000402102    L09000056609    no     yes    YES          2 of 6
   9  real_world_reference  P24771          P24771          yes    yes    no           1 of 28
  10  real_world_reference  NEEDS_MORE_INFO NEEDS_MORE_INFO yes    yes    no           asked
  11  contractor_search     L22000086098    L21000316955    no     no     YES          not among 200
  12  contractor_search     L22000086098    L21000316955    no     no     YES          not among 200
  13  contractor_search     L22000086098    L22000086098    yes    yes    no           1 of 1

group                    cases  top-1  recall@5  wrong_match
contractor_search            3      1         1            2
legal_name_variant           8      5         7            2
real_world_reference         2      2         2            0
ALL                         13      8        10            4

draft cases (evals/draft_cases.csv: not checked by Andres, and so counted in no pass or fail decision)
group                    cases  top-1  recall@5  wrong_match
address_only                 5      3         4            1
brand_and_city               6      0         2            6
name_and_street              5      0         1            5
ALL                         16      3         7           12

before Phase D, and now: checked cases (the place of the expected company by rank among the candidates, and on the page)
case  group                 by rank, before Phase D   by rank, now              on the page               moved
   1  legal_name_variant    1 of 1                    1 of 1                    1 -> 1                    stayed
   2  legal_name_variant    1 of 1                    1 of 1                    1 -> 1                    stayed
   3  legal_name_variant    2 of 10                   2 of 10                   2 -> 2                    stayed
   4  legal_name_variant    1 of 12                   1 of 12                   1 -> 1                    stayed
   5  legal_name_variant    1 of 1                    1 of 1                    1 -> 1                    stayed
   6  legal_name_variant    1 of 27                   1 of 27                   1 -> 1                    stayed
   7  legal_name_variant    asked                     asked                     asked -> asked            stayed
   8  legal_name_variant    2 of 6                    2 of 6                    2 -> 2                    stayed
   9  real_world_reference  1 of 28                   1 of 28                   1 -> 1                    stayed
  10  real_world_reference  asked                     asked                     asked -> asked            stayed
  11  contractor_search     not among 200             not among 200             not shown -> not shown    stayed
  12  contractor_search     not among 200             not among 200             not shown -> not shown    stayed
  13  contractor_search     asked                     1 of 1                    asked -> 1                up

group                    cases  moved up  moved down  stayed
contractor_search            3         1           0       2
legal_name_variant           8         0           0       8
real_world_reference         2         0           0       2
ALL                         13         1           0      12
checked cases made worse: none

before Phase D, and now: draft cases (counts only: not checked by Andres, and so counted in no pass or fail decision)
group                    cases  moved up  moved down  stayed
address_only                 5         4           0       1
brand_and_city               6         0           0       6
name_and_street              5         0           0       5
ALL                         16         4           0      12
```

| Cases | Measure | Before Phase D | Now |
|---|---|---|---|
| The 13 checked cases | Top-1 | 7 | 8 |
| | Recall at 5 | 9 | 10 |
| | `wrong_match` | 4 | 4 |
| The 16 draft cases, which count in no decision | Top-1 | 0 | 3 |
| | Recall at 5 | 3 | 7 |
| | `wrong_match` | 11 | 12 |

- ✅ **No checked case was made worse.** The command exits with 1 when one is, and for this comparison it found none. "Worse" is working rule S3's test: the company leaves the top five, it drops in rank, or a note that should be asked about gets a company. It also counts a drop on the page, which check 2 explains.
- ✅ The ten cases of October score exactly as they did: 7 right, 9 in the first five, 2 wrong matches. The "before" numbers were also measured on their own, at commit `3efe02e`, before any search change, and they are the same.
- **Case 13, the address alone, went from "asked" to first.** That is the whole gain on the checked cases.
- The column "place of the expected company" is what shows the fault in cases 11 and 12. "not among 200" means the company never reached `rank()`.
- 🟡 The drafts' `wrong_match` rose by one, from 11 to 12. The address search answers 5 drafts that used to be asked about, and for one of them another company comes first.

### Check 2: rule S2 and its variant, scored beside the app's order

`--try-order` scores every case under the app's order and under another order of the name search's candidates. The whole output for `s2` is below. The run for the variant, `s2-city-first`, printed the same places on every line, so only its last lines are pasted.

```
python -m evals.run --backend postgres --try-order s2            (exit code 1)

the app's order, and the order s2: checked cases (the place of the expected company by rank among the candidates, and on the page)
case  group                 by rank, the app's order  by rank, the order s2     on the page               moved
   1  legal_name_variant    1 of 1                    1 of 1                    1 -> 1                    stayed
   2  legal_name_variant    1 of 1                    1 of 1                    1 -> 1                    stayed
   3  legal_name_variant    2 of 10                   2 of 10                   2 -> 2                    stayed
   4  legal_name_variant    1 of 12                   1 of 12                   1 -> 1                    stayed
   5  legal_name_variant    1 of 1                    1 of 1                    1 -> 1                    stayed
   6  legal_name_variant    1 of 27                   1 of 27                   1 -> 1                    stayed
   7  legal_name_variant    asked                     asked                     asked -> asked            stayed
   8  legal_name_variant    2 of 6                    2 of 6                    2 -> 2                    stayed
   9  real_world_reference  1 of 28                   1 of 28                   1 -> 2                    down
  10  real_world_reference  asked                     asked                     asked -> asked            stayed
  11  contractor_search     not among 200             not among 200             not shown -> not shown    stayed
  12  contractor_search     not among 200             not among 200             not shown -> not shown    stayed
  13  contractor_search     1 of 1                    1 of 1                    1 -> 1                    stayed

group                    cases  moved up  moved down  stayed
contractor_search            3         0           0       3
legal_name_variant           8         0           0       8
real_world_reference         2         0           1       1
ALL                         13         0           1      12
checked cases made worse: 9

the app's order, and the order s2: draft cases (counts only: not checked by Andres, and so counted in no pass or fail decision)
group                    cases  moved up  moved down  stayed
address_only                 5         0           0       5
brand_and_city               6         2           0       4
name_and_street              5         0           0       5
ALL                         16         2           0      14

python -m evals.run --backend postgres --try-order s2-city-first  (exit code 1)

   9  real_world_reference  1 of 28                   1 of 28                   1 -> 2                    down
checked cases made worse: 9
ALL                         16         2           0      14     (the draft cases)
```

| Order | Checked cases whose rank changed | Checked cases whose place on the page changed | Draft cases | Rule S3 |
|---|---|---|---|---|
| Rule S2: every typed word, then the city, then similarity | 0 of 13 | 1: case 9, from first to second | 2 up, 0 down, 14 stayed | Makes a checked case worse |
| The variant: the city, then every typed word, then similarity | 0 of 13 | 1: case 9, from first to second | 2 up, 0 down, 14 stayed | Makes a checked case worse |

**What happens in case 9.** The note is `cinemark durbin park`, the extraction step read the business name "Cinemark", and the expected company is the operator, whose registered name is longer than that.

- Under the app's order the best five are the expected company and four names close to "Cinemark". All five are rated Possible, so the expected company is at the top of the page. A company whose name is exactly "Cinemark" plus a legal ending ranks below the five. The page counts it in a line under the list, and it cannot be picked (question Q34).
- Under rule S2 every company whose name holds the word CINEMARK comes before the near-misses, so that exact-name company climbs to third and is among the five. The page then shows the five by match level, and an exact name is rated Strong. So it is shown first, and the expected company second.
- The expected company is first by rank under both orders. That is why the evaluation's own numbers (top-1, recall at 5) did not move, and why my first pass missed it.

**Why this stops S2.** Rule S3 says that when S2 makes a checked case worse, one variant may be tried, and when the variant does too, the old ranking is kept and both results are recorded. No third order may be invented.

- 🔴 **The reading is mine.** Rule S3 says a case is worse when it "drops in rank", and by rank nothing dropped. I read a drop on the page as a drop, because the page is what a contractor sees. It is the reading that calls more changes worse. If you read S3 by rank alone, S2 passes, and switching it on is one line (question Q52).
- **How it was found.** In my first pass I made S2 the app's order, because the evaluation compared ranks only and found nothing worse. A reviewer in round 1 pointed out that the evaluation scores the rank while the page sorts the five by level. I measured the page for every checked case, and case 9 had moved.
- The evaluation now keeps both places for every case, and its comparison calls a case worse when either drops. So this kind of change now fails the command and no longer depends on somebody noticing.

### Check 3: why `v pizza orlando` cannot be fixed by an order, in numbers

The name search's first step runs one query: keep the names that hold something close to the typed name, order them by how near the WHOLE name is to the typed name, and keep the first 200. I asked Postgres how that goes for the key `V PIZZA`.

```
names that pass the first step for the key V PIZZA                 10,062
place of the expected company in the first step's own order         2,861
names that hold the two words V and PIZZA                              34

the 13 companies whose names begin with V PIZZA, by their place in the first step's order:
     4, 62, 124, 236, 649, 650, 651, 1074, 1227, 1230, 1601, 2861, 3589
```

- A name passes the first step when some stretch of it is close to `V PIZZA`. The word PIZZA alone is close enough, so nearly every name with PIZZA in it passes.
- The step then keeps the 200 names that are nearest as a whole, and a short name is nearer to a short typed name than a long one is. `V PIZZA LAKE BUENA VISTA LLC` is the second longest of the 13 names, and it stands 2,861st.
- Only **3** of the 13 are among the 200. The right company is not one of them, so `rank()` never sees it.
- 🔴 The brief says the company "ranked 13th" and that "the cause is in `rank()`". On the app's search it is not ranked at all. It would be near the bottom of the 13 if all of them reached `rank()`, which is likely where that number came from. I could not find out how the 13 was measured.
- Only 34 names hold both words. That is why the change to step 1 in check 9 is small: if the step brought those 34 back first, the right company would be among them.

### Check 4: the four searches on the real app

I started the app with the brief's command and a throwaway access code that was made up by the shell, kept in a shell variable for one command and written nowhere. Each search is one live extraction call. This is the run on the final code. I had run the same four searches once before, while S2 was still the app's order, and the note below says what differed.

```
PYTHONPATH=src APP_ACCESS_CODE=<a throwaway code> uvicorn datum.web.app:app --host 127.0.0.1 --port 8765

healthz: ok   home without the code: 401   home with the code: 200

--- v pizza orlando: status 200, 1.805983 seconds
I read that as: the business name "V Pizza", the city "Orlando"
5 companies on this list match at the level Possible. Check which one you mean before you open a report.
  L21000316955  Possible  inactive
  L17000205773  Possible  active
  L24000348425  Possible  inactive
  L25000541856  Possible  active
  P02000088134  Possible  inactive

--- v pizza lake buena vista: status 200, 1.025395 seconds
I read that as: the business name "V Pizza", the city "Buena Vista", the street "Lake"
  (the same five companies, in the same order)

--- 8586 palm pwwy: status 200, 1.049979 seconds
Companies by principal address
I read that as: the street "8586 palm pwwy"
A company matches when its principal address on record has the house number 8586 and a street name made only of words you typed. The kind of street, such as ST or PKWY, and a direction, N, S, E or W, are not compared. You gave no city, so a match can be in any city.
1 active company matches.
  L22000086098  V PIZZA LAKE BUENA VISTA LLC · Principal address 8586 PALM PKWY, ORLANDO, FL 32836
3 inactive companies also match and are not listed.
A company's principal address is the address it gave the state, which is not always where it does business.

--- v pizza durbin: status 200, 0.970531 seconds
I read that as: the business name "V Pizza"
  (the same five companies, in the same order. L25000541856, fourth, is V PIZZA DURBIN, LLC, the company the brief expects)

--- the report of the company listed for the address: status 200, 0.042456 seconds
How this company was identified: from the street "8586 palm pwwy" · found by its principal address on record (the same house number, and a street name made only of words that were typed) · chosen by the user from the active companies listed.
No flags found in the sources checked.
```

The companies are given by document number, with the level and the status the page showed. Only the two that are named in the brief are named here.

| Search | The company the brief expects | Result |
|---|---|---|
| `v pizza orlando` | L22000086098 | ❌ Not on the list. The list is what Andres saw on Nov 24: the first company is the inactive one in Winter Park |
| `v pizza lake buena vista` | L22000086098 | ❌ Not on the list |
| `8586 palm pwwy` | L22000086098 | ✅ The only company listed |
| `v pizza durbin` | L25000541856 | 🟡 Fourth of five. The extraction step returned the business name "V Pizza" and no city, so the word Durbin never reached the search (question Q50) |

- ✅ The server's log holds 13 request lines. I searched it for "pizza", "palm", "pwwy" and "durbin", and for the access code, and found none.
- 🟡 **The extraction step read the same note two ways.** For `v pizza lake buena vista` it returned the city "Lake Buena Vista" when the case was extracted for the test set, and the city "Buena Vista" with the street "Lake" in this run. The evaluation always scores the saved extraction, so it does not move. A real search can.
- 🟡 The report's line says "chosen by the user". In this check a command followed the link. Nobody chose.
- In the earlier run, with S2 as the order, `v pizza orlando` put another company first: an inactive one in Orlando whose name holds the words V and PIZZA. It was not the company Andres meant either.

### Check 5: the speed of both searches

The target is a p95 under 1 second for each search. Before timing anything I chose which run would be the number for this report: the first run after Postgres is restarted, as leg C2 did. These are the runs on the final code, after the last load.

```
brew services restart postgresql@17
python -m evals.run --backend postgres --latency 200

latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 113 ms   p95 515 ms   slowest 3086 ms
  searches over 1 second: 3 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37

brew services restart postgresql@17
python -m evals.run --backend postgres --address-latency 200

latency of the search by address over 200 principal addresses drawn at random:
  p50 6 ms   p95 175 ms   slowest 424 ms
  searches over 1 second: 0 of 200
  searches answered with "too many to list": 46 of 200
  fingerprint of the random addresses: e17a1576706df4cc9a00bf1c0677ffc6
```

| Search | Searches timed | p50 | p95 | Slowest | Target: p95 under 1 second |
|---|---|---|---|---|---|
| By name | 210: the 10 specific checked cases and 200 random company names | 113 ms | **515 ms** | 3,086 ms | ✅ |
| By address | 200 principal addresses drawn at random | 6 ms | **175 ms** | 424 ms | ✅ |

- ✅ The 200 names are the same ones leg C2 timed. The fingerprint, a short code for the whole list, is `29e3...`, which leg C2's report calls set A. Leg C2 measured a p95 of 574 milliseconds on them with 208 searches.
- ✅ The same two commands ran once before, after the first load of this leg, and gave a p95 of 525 and 178 milliseconds.
- The name search has 2 more test inputs than in leg C2, because cases 11 and 12 are specific. Case 13 is not a name search.
- 🟡 Three name searches still take longer than 1 second. Leg C2 explains them: names made of one long common word and one or two short ones. This leg did not change the first step, so it did not change them.
- 🟡 The Mac was busy while I timed. Every number here is a little worse than a quiet machine would give.
- 🟡 I did not repeat the timed runs cold, as leg C2 did.
- ✅ The security review asked what the slowest possible address query costs. The busiest house number has 162,454 rows under it. A search of it took 73 milliseconds with a two-word street and 368 milliseconds with a street of 250 words, which is more than a note of 500 characters can hold.
- **46 of the 200 random addresses were answered with "too many to list".** A second pass, with each company's own city given, got that answer for 41. The draw picks companies at random, so an address with thousands of companies is drawn far more often than a quiet one. Question Q48.

### Check 6: the loader, on the real data

```
python src/datum/load_postgres.py

table                       Snowflake exported   Postgres loaded
company_search                      12,988,435        12,988,435
company_flags                            9,950             9,950
company_possible_matches                     0                 0
source_coverage                              5                 5
company_search_names: 12,988,435 rows built from company_search's 12,988,435; 0 only in company_search_names, 0 only in company_search
company_search_addresses: 12,988,435 rows built from company_search's 12,988,435; 0 only in company_search_addresses, 0 only in company_search
index company_search_name_key_trgm: built in 68.6 seconds
index company_search_names_name_key_trgm: built in 60.9 seconds
index company_search_addresses_house_number: built in 6.9 seconds
table company_search                                 2986 MB
table company_search_names                            850 MB
table company_search_addresses                        775 MB
index company_search_pkey                             625 MB
index company_search_name_key_trgm                    588 MB
index company_search_names_name_key_trgm              441 MB
index company_search_addresses_house_number            89 MB
database total: 6367 MB
11:01.76 total
```

- ✅ The address table has one row for each of the 12,988,435 companies, and no document number is in one table and not in the other. The loader checks this before it swaps the tables in, and refuses to swap when it fails.
- ✅ The four exported tables loaded with the counts Snowflake exported on Nov 20. No new export was made, because this phase does not use Snowflake.
- The database grew by 864 MB, from 5,503 MB to **6,367 MB**: 775 MB for the table and 89 MB for its index. This is the number that picks a host.
- The load took 11 minutes 2 seconds, and 9 minutes 47 seconds the time before. It took 6 minutes 13 seconds in leg C2.
- **The loader ran three times in this leg, and the first run failed.** My first version of the statement that fills the address table had a fault that only Postgres could see, and the load stopped there after 4 minutes. Nothing had been swapped in, so the app's tables were untouched. The offline tests could not catch it, because they hand the loader a stand-in for the database. Since then I run the loader's own statements against a small temporary copy inside Postgres before a full load, which shows such a fault in seconds. The second run loaded the table. The third followed the review's finding about numbered streets.

### Check 7: what the address table holds

A scratch script counted these on the real data, after the last load. It prints counts only.

```
A. sampled 128,118 companies: Python and the loader cut the address differently for 0
B. 12,988,435 rows; 12,215,961 with a house number; 772,474 without one; 4,883 with a number and no street word
   13,292 have a street made only of street types and directions, so they can never be found by address
C. addresses with 1            companies:  4,716,408 addresses (72.66%)   holding  4,716,408 companies (38.62%)
C. addresses with 2 to 5       companies:  1,582,578 addresses (24.38%)   holding  4,066,092 companies (33.30%)
C. addresses with 6 to 50      companies:    182,989 addresses ( 2.82%)   holding  2,069,555 companies (16.95%)
C. addresses with 51 to 1,000  companies:      8,984 addresses ( 0.14%)   holding  1,112,241 companies ( 9.11%)
C. addresses with over 1,000   companies:         75 addresses ( 0.00%)   holding    246,782 companies ( 2.02%)
   the most companies at one house number and street: 74,674
   the most rows under one house number: 162,454
```

- ✅ **A.** The loader cuts an address in SQL, and the search cuts a typed street in Python. On a sample of 128,118 companies the two cuts gave the same house number and the same words every time.
- **B.** 772,474 companies have a principal address with no house number, such as a post office box, and they cannot be found by address. 1,795 of them begin with a numbered street, such as `4TH ST`.
- **C.** In this table an "address" is a house number and a street written one way. 9,059 of them hold more than 50 companies each, and together they hold 1,359,023 companies, or 11.1%. The largest holds 74,674.
- A separate count: 1,095,222 of the 12,213,042 principal addresses that begin with a digit hold a unit word, such as STE or SUITE (question Q47).

### Check 8: the database's street filter and the Python rule keep the same rows

The Postgres query applies the street rule so that it can cut the list before its limit. `street_matches()` in Python is the rule the tests cover. If the query were stricter than the rule, the search would lose companies and no offline test would notice. So a scratch script compared them on the real data, and the query's text is pinned word for word in a test.

```
200 addresses, 1,071,053 rows under their house numbers, 237,837 kept:
the SQL and street_matches() keep the same rows for 200, and differ for 0
```

✅ For each of 200 addresses drawn at random, the script read every row under that house number and applied the Python rule, and separately ran the query's two conditions. They kept the same rows all 200 times.

### Check 9: what would fix `v pizza orlando`, measured and not built

None of this is in the leg's code. A scratch script scored the checked cases under four combinations of two changes.

- **The change to step 1** (question Q46): among the names that pass the first step, the ones that hold every typed word come first, and then the nearest names as today. It is one more term in the query's ORDER BY.
- **Rule S2** (question Q52): the order that is built in this leg and not switched on.

Each cell is the expected company's place by rank, then its place on the page.

```
case  A  as built, app's order    B  as built, rule S2        C  every word first,        D  every word first,
      (what this leg ships)                                      app's order                 rule S2
   1  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1
   2  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1
   3  2 of 10 / 2                 2 of 10 / 2                 2 of 10 / 2                 2 of 10 / 2
   4  1 of 12 / 1                 1 of 12 / 1                 1 of 12 / 1                 1 of 12 / 1
   5  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1
   6  1 of 27 / 1                 1 of 27 / 1                 1 of 27 / 1                 1 of 27 / 1
   7  asked / asked               asked / asked               asked / asked               asked / asked
   8  2 of 6 / 2                  2 of 6 / 2                  2 of 6 / 2                  2 of 6 / 2
   9  1 of 28 / 1                 1 of 28 / 2                 1 of 28 / 1                 1 of 28 / 2
  10  asked / asked               asked / asked               asked / asked               asked / asked
  11  not among 200 / not shown   not among 200 / not shown   17 of 200 / not shown       1 of 200 / 1
  12  not among 200 / not shown   not among 200 / not shown   20 of 200 / not shown       15 of 200 / not shown
  13  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1
```

| | A: what this leg ships | B: rule S2 alone | C: step 1 alone | D: both |
|---|---|---|---|---|
| Top-1 by rank, of 13 | 8 | 8 | 8 | **9** |
| Recall at 5 | 10 | 10 | 10 | **11** |
| `wrong_match` | 4 | 4 | 4 | **3** |
| Cases where the right company is at the top of the PAGE | 8 | 7 | 8 | 8 |
| `v pizza orlando` (case 11) | not among the candidates | not among the candidates | 17th | **1st** |
| `cinemark durbin park` (case 9), on the page | 1st | 2nd | 1st | 2nd |
| The 16 draft cases, against A | | 2 up, 0 down | 4 up, 1 down | 5 up, 0 down |

- **Neither change fixes `v pizza orlando` alone.** Step 1 brings the company into the pool, at 17th. Rule S2 then puts it first, because its principal city is Orlando.
- **Both together cost case 9 on the page,** unless the page shows its five companies in rank order (question Q51). With all three, every column of D would be at least as good as A. 🔴 I did not measure that third change.
- `v pizza lake buena vista` (case 12) is not fixed by any of them. The extraction step read "Lake Buena Vista" as the city, and the company's principal city is Orlando (question Q50).
- The change to step 1 is not slower. On the same 210 searches, timed back to back, its p95 was 420 and 413 milliseconds, against 485 and 421 for the search as built. 🟡 Those four timings were taken one after another with no restart, so they show "not slower" and are not a measurement to hold a target against.
- 🟡 One draft case moved down under C. I did not look into why, because a draft may not shape the search (rule S1), and nothing here is built.
- I did not build the change to step 1, for three reasons. The brief's rules do not cover the first step and say to build exactly what they describe. `CLAUDE.md` says not to route around a rule. And the brief's own rule S3 handles the nearest case, a ranking that does not work, by finishing the leg, putting the result first and leaving the choice to Andres.

### Check 10: the tests

```
brew services stop postgresql@17      → Successfully stopped `postgresql@17`
pg_isready                            → /tmp:5432 - no response
pytest                                → 512 passed in 2.78s
ruff check src tests                  → All checks passed!
brew services start postgresql@17     → Successfully started `postgresql@17`
pg_isready                            → /tmp:5432 - accepting connections
```

✅ With the database server stopped, all 512 tests pass, so the suite needs no database. 456 existed before this leg and 56 are new.

**The tests the brief asks for by name**

| What the brief asks | The test | The input that makes it fail |
|---|---|---|
| Rule S2, failing on the old behavior | `test_rank_orders_by_every_word_then_city_then_similarity_then_document_number` and `test_a_long_legal_name_that_holds_the_typed_trade_name_ranks_above_a_shorter_namesake_elsewhere`, in `test_search.py` | Six invented companies, each placed by a different part of the rule, with the order passed in. With the app's order in its place, both fail: a near-miss name with the highest similarity comes first. The second test also fails if an inactive company is moved below its active twin. The first also checks the variant |
| Rule S4, the levels as before | `test_match_level_follows_the_three_rules` | The same four companies and five expected levels the test has had since leg C2, looked up by document number, and run again under rule S2 and under its variant. A fifth company shows that holding every word is a reason for a company's place and never for its level |
| Rule S5, failing on the old behavior | `test_a_note_gets_the_name_search_the_address_search_or_a_question`, `test_a_stored_street_matches_when_all_its_words_were_typed_whatever_the_street_type`, and `test_an_address_alone_lists_the_one_active_company_there_and_says_two_inactive_ones_are_not_listed` in `test_web.py` | A note with no business and the street "8586 palm pwwy". Before this leg the page said "That describes a business but doesn't name one" |
| Rule S6, failing on the old behavior | `test_an_address_search_lists_the_active_companies_and_only_counts_the_inactive_ones` and `test_an_address_search_is_in_document_number_order_and_status_never_reorders_it` | One active company and two inactive ones at one address, plus three near-misses: another street, the house next door, and the same street name in another city. The second test hands the companies over unsorted and fails if the search stops sorting them |
| One active and two inactive companies: only the active one is listed, and two inactive ones are said to be there | The same test in `test_web.py` as for rule S5 | It fails if either inactive company's name or number is anywhere on the page, if the sentence "2 inactive companies also match and are not listed." is missing, or if an inactive company's report can be opened with the page's token |
| Rule S7, a street with no house number still asks | `test_a_vague_note_asks_for_a_business_and_shows_no_company`, and `test_a_street_that_gives_nothing_to_look_up_asks_and_claims_no_result`, run for four streets | The app holds a company whose address IS on that street. It fails if either search ran. The four streets are two numbered streets with no house number, and two house numbers with no street name |
| Rule S8, failing on the old behavior | The same test in `test_web.py` as for rule S5 | It fails unless the sentence is on the page exactly once, after the results and before the search box. The sentence is typed out in the test |
| A draft case can never change a gate | `test_a_draft_case_can_never_change_the_pass_or_fail_decision` and `test_the_whole_evaluation_fails_only_when_a_checked_case_is_made_worse`, in `test_evals_run.py` | A fixture with one checked case and drafts that get as bad as a case can get. The decision must be the same with those drafts, with good ones and with none, and it must change when the checked case drops. The second test runs the whole command's logic with a stand-in backend |
| `tests/test_evals_run.py` updated | `test_the_committed_test_set_is_read_and_joined_to_its_extractions` | It now expects 13 cases, and reads the street of case 13 |

One more test is worth naming, because it holds the finding of check 2 in place. `test_a_company_that_keeps_its_rank_and_drops_on_the_page_counts_as_worse` builds case 9's shape from invented companies: the expected company is first by rank under both orders, and second on the page under rule S2. It fails if the comparison calls that "stayed".

### Check 11: the draft cases

The brief asks for the count by kind and how each kind was chosen, and never the cases themselves.

| Kind | Cases | How the cases were chosen |
|---|---|---|
| A brand and a place | 6 | One is given by the brief. For the other five, a query found every company whose name is a brand, then one of 30 Northeast and Central Florida place names, then LLC. It kept the brands with at least four such active companies in at least four places. I picked five brands whose names are plainly a business's, and one active company of each. Each case is typed as the brand and the place in that company's own name |
| An address alone | 5 | For the storefront address of a company found by the brand query, a second query listed every company registered there. I kept an address only when exactly one company there is active, every name there holds LLC, INC or CORP, and no name there could be a person's. Two addresses were dropped by that last test. The five cases are typed with small differences from the record: a street type spelled out, a direction left out, one with a city, and one with a word of the street left out |
| A name with a street | 5 | An active company of one of the same brands, typed as the brand and the street of its principal address. Two have a house number and three do not |

- ✅ Every expected company is active, and all are in Northeast or Central Florida.
- Each row's `notes` column holds the query that picked it, as the brief asks.
- 🟡 The drafts come from six brands, so they are not a broad sample. Three of the 16 expect the same company from different notes.
- What the drafts showed, by count only: the address search finds the expected company first in 3 of 5, and in the first five in 4. The one it misses altogether is the draft with a word of the street left out, which the rule treats as a miss. The name search finds none of the 11 name drafts first.
- 🔴 **During the first pass, three of my committed tests quoted the street of a draft case.** A reviewer and the security review both found it. The branch had not been pushed. I replaced the three streets with invented ones and folded that fix into the commit that had introduced them, so no draft text is in the branch's history. The check is `git log -p main..HEAD`, searched for the three street names: 0 hits.

### Check 12: the live extraction calls

| What for | Calls |
|---|---|
| The three checked cases | 3 |
| The 16 draft cases | 16 |
| The four searches on the real app, in the first pass | 4 |
| The same four searches again, on the final code | 4 |
| **Total** | **27 of the 30 the phase allows** |

✅ The rows of cases 1 to 10 in `pipeline/seeds/extracted_inputs.csv` are unchanged. Prompt v2 made them, and they were not extracted again. The command now refuses to extract a case that already has a row. No test calls the API.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | Rule S2 is not switched on, and neither is its variant | Both move checked case 9's right company from first to second on the page. Rule S3 says to keep the old ranking then | 🔴 The reading that a drop on the page counts as worse is mine (check 2). The two draft cases S2 moved up stay where they were. Question Q52 |
| 2 | I did not change the first step of the name search, although that leaves `v pizza orlando` failing | The brief's rules do not cover it and say to build exactly what they describe. It decides which companies every search can return, which is a matching rule and so Andres's | The leg does not fix the failure it was written for. Question Q46 holds the change and its numbers |
| 3 | The evaluation compares the place on the page as well as the rank, and calls a case worse when either drops | A contractor sees the page. A comparison of ranks alone passed a change that moved a right answer down the page | 🔴 Top-1 and recall at 5 still mean the rank, as script 11 defines them. Whether they should mean the page is question Q51 |
| 4 | An address where more than 50 companies match lists none of them | Rule S6 says to list every active company at an address. At a registered agent's office that is thousands. A list of fifty in document-number order would help nobody find one, and listing none shows less | 🟡 46 of 200 random addresses get this answer. The limit is mine. Question Q48 |
| 5 | A unit on the record is not ignored | Rule S5 lists street types and directions. A suite is neither. Following the rule as written is the reading that shows less | 1,095,222 addresses hold a unit word, and each can only be found when the note has it too. Question Q47 |
| 6 | The directions are exactly N, S, E and W | The rule lists those four | A record that says SOUTH, or SE, only matches a note that says the same |
| 7 | The street types are the brief's sixteen, the other spelling of each, and three more pairs: PL and PLACE, TER and TERRACE, TRL and TRAIL | The brief says "and the like". I added only the next most common ones | A rarer street type, such as LOOP or COVE, is compared as a word of the street's name |
| 8 | A numbered street at the start of an address is not a house number | `4th st south` names a street and no house on it, and rule S7 says such a note is asked about. The review found that my first version read 4TH as a house number | 1,795 companies whose address begins with a numbered street cannot be found by address |
| 9 | A house number with no street name to compare gets the question, not the address search | With nothing to compare, no lookup runs, and a page that said "no company matches" would report a search that never ran | A note such as `12 parkway` is asked for more |
| 10 | The street rule is written twice: in Python, and in the Postgres query | The query has to cut the list before its limit. The Python rule is the one the tests cover, and `address_search()` applies it again to every row that comes back | Two copies can drift. Check 8 compared them on 1,071,053 real rows, and a test pins the query's text |
| 11 | The page says a company "matches", and never that it "has this address" | The comparison ignores the kind of street, and with no city given a match can be in any city. The review found that my first wording claimed more than was compared | The sentences are less natural to read |
| 12 | The count of inactive companies is a `Fact` that cites the state's company records, with the oldest fetch time of the companies counted | `CLAUDE.md` rule 3: a derived value carries its inputs' provenance | 🟡 The sentence cites the state's search page and gives no document numbers, because rule S6 says the companies are not listed. So a reader cannot check the count from the page |
| 13 | A company found by its address has no match level, and the type refuses one | Rule S4 keeps the three levels for the name search. An address match is a different claim | The report of such a company says it was found by its principal address, and how many others were listed |
| 14 | What the extraction step put in the business name of an address-only note is never shown | The note named no business. The model wrote `<UNKNOWN>` there for every such note I extracted | None |
| 15 | The command `extract.py` can no longer extract a whole file, and it will not write another file's cases to the committed seed by default | The brief says cases 1 to 10 are never extracted again, and rule S1 keeps drafts off git. The security review found the second slip | Extracting a new case takes its id: `python src/datum/extract.py --cases 14` |
| 16 | The evaluation refuses a row with no `verified_on` date in the test set, and a row with one among the drafts | Rule S1. A draft pasted into the test set by mistake then stops the run | None |
| 17 | A case whose right answer is to ask is now correct only when no search ran | It used to be marked from the extraction's flag alone. With an address search, a note the extraction calls vague can now get a company, and that must not be scored as correct | 🔴 This is my change to a scoring definition. Cases 7 and 10 score as before |
| 18 | The terminal command was not given the address search, and its two questions were not reworded | The brief names the web app and the evaluation. `report.py` is a High-tier file | The terminal and the web app now answer an address-only note differently. Question Q49 |
| 19 | I rewrote the branch's own history once, before anything was pushed, to take draft text out of it | Rule S1 says a draft stays on the Mac. A later commit that removed the text would have left it in the history that GitHub publishes | The commit ids changed. Nothing had been pushed, and nothing was force-pushed |

---

## 4. What I couldn't verify, and open questions for Andres

### What I couldn't verify

1. 🔴 **That a drop on the page is what rule S3 means by "worse"** (decision 1). By rank, S2 made no checked case worse.
2. 🔴 **That the three changes of check 9 are the right fix.** Two of them were measured on 13 checked cases and 16 drafts in a scratch script, and the third was not measured. None is built, tested or reviewed.
3. 🔴 **How the brief's "ranked 13th" was measured.** On the app's search the company is not among the candidates at all (check 3).
4. 🔴 **The scoring change for a case whose right answer is to ask** (decision 17). The definition is mine.
5. 🟡 **Whether an address is a home.** Nothing in the state's file says. 4,716,408 companies are the only company at their address (question Q45).
6. 🟡 **Whether a company's name at a home address is a person's name** (question Q45). The page shows what the state's record holds. I did not count how many names could be a person's.
7. 🟡 **Whether 50 is the right limit for a crowded address** (question Q48). 46 of 200 random addresses reach it.
8. 🟡 **How many real searches a unit on the record will block** (question Q47). 1,095,222 addresses hold a unit word.
9. 🟡 **What the extraction step returns for a real contractor's note.** The address search runs only when the model says the note names no business. It did so for all 6 address-only notes I extracted. Check 4 shows the model reading one note two ways on two calls.
10. 🟡 **The extraction step's handling of a place name** (question Q50), seen on 27 extractions.
11. 🟡 **The speed on a host, and on a quiet machine.** Every timing is from the Mac, which was busy.
12. 🟡 **The address page on a phone.** No screenshot was made in this leg. Leg D2 makes them.
13. 🟡 **The cost of an extraction call.** The figure of $0.0004 is the plan's.
14. 🟡 **Characters outside A to Z in an address.** Python and Postgres can put such a character in capitals differently before both turn it into a space. The sample of check 7 found no difference.
15. 🟡 **That the drafts are a fair sample.** They come from six brands (check 11).
16. 🟡 **That the count on the address page can be checked by a reader** (decision 12).

### Questions added to `docs/open_questions.md`

| # | The question, in short |
|---|---|
| Q42 | Answered in part: a street is now used when the note names no business and the street has a house number |
| Q45 | Should inactive companies at an address be listed, and should an address that may be a home be searchable at all? |
| Q46 | Should the first step of the name search bring back the names that hold every typed word first? |
| Q47 | Should a suite or unit on the record be ignored? |
| Q48 | Is 50 the right limit for a crowded address? |
| Q49 | Should the terminal command get the search by address? |
| Q50 | Should the search look for the typed place among the words of the company's name? |
| Q51 | Should the page show its five companies in rank order, and should top-1 mean first on the page? |
| Q52 | Should rule S2 be switched on? |

### The review

- **Tier:** High. The leg adds rows to `pipeline/seeds/` and changes wording that a report shows, the line that says how a company was identified. Both are High paths in `REVIEW.md`, and the brief names both legs of Phase D as High.
- **Depth:** Deep. In round 1, three `reviewer` subagents ran in parallel, each with one of the hunts the brief sets for Phase D, and a fourth then checked every finding against the code. A security review ran alongside, because `src/` changed.
- **Rounds:** three, which is the most the rules allow.
- **Findings over the rounds:** 8 Important, 6 Nit and 1 Pre-existing. Round 1 had 4 Important, 5 Nit and 1 Pre-existing, after a fourth reviewer dropped 2 of the 12 that were posted. Round 2 had 3 Important and 1 Nit. Round 3 had 1 Important. Every Important finding is fixed, except one that is closed with a reason because it is a privacy decision.
- **What was not reviewed:** commit `5ecb08a`, which answers round 3 and changes one test and no code. The commits after it change this report and add the pull request's row to `docs/review_log.csv`. Reviewers are told to skip leg reports, so this report's own text was checked only where the Human review section repeats it.

**Round 1** (three reviewers, then a verifier, on the leg's first twelve commits, and the security review).

The three reviewers posted 12 findings. The verifier confirmed 10 and dropped 2: **4 Important, 5 Nit and 1 Pre-existing**. Every confirmed finding was answered, and so were the two that were dropped.

| Finding | Tag | Answer |
|---|---|---|
| A numbered street such as `4th st south` begins with a digit, so its first word was read as a house number. The note then got the address search and not the question, which breaks rule S7 | Important | Fixed. A first word such as 4TH or 101ST is a street and not a house number, in the Python rule and in the loader's statement. Postgres was loaded again. `1st ave` and `12 parkway` now get the question |
| An address search can lead from a place to a person's name. A one-person company is often named after its owner and registered at the owner's home, and the page shows the company's name | Important. The reviewer flagged it and did not decide it | Closed with a reason: it is a privacy call, and those are Andres's. The page shows only what the state's record holds, and rule S6 already lists only active companies. Question Q45 now names this case |
| Nothing tested that the address search puts its answer in document-number order. The test backend sorted its rows first, so three tests could not fail on the order | Important | Fixed. The test backend no longer sorts, and the query's last line is pinned. With the sort removed from `address_search()`, 5 tests now fail |
| Nothing tested the wiring that turns the comparison into the command's exit code. It could have been broken, or fed the drafts, with every test passing | Important | Fixed. The wiring moved into `evaluate()`, which a test runs with a stand-in backend. Two deliberate breaks each fail a test: scoring both runs with the same order, and letting the drafts into the decision |
| The evaluation scores the best five by rank, and the page shows those five by match level, so the first company on a page can be another one. A new comment said otherwise | Pre-existing | Followed up, and it changed the leg. Measuring the page for every checked case showed that rule S2 moves case 9 from first to second there (check 2). The app went back to its old order, the evaluation now keeps both places, and question Q51 asks which one top-1 should mean |
| The sentence for a crowded address said "More than 50 companies", which the search does not establish when it stops reading at its limit, and it gave a count with no source | Nit | Fixed. The sentence gives no count |
| "No company with that principal address on record was found" was shown when nothing had been compared, such as for `12 parkway`, and it did not say what was compared | Nit | Fixed. Such a note now gets the question. The sentence was reworded to say what was compared and to mention a suite |
| No test had a company with no status at an address, so the line that counts such companies could be deleted | Nit | Fixed with a test |
| No test opened the report of a company that was counted and not listed, with the address page's token | Nit | Fixed. Such a report says it was opened by its document number |
| The street rule inside the Postgres query and the statement that cuts an address could be changed with no offline test failing, because no offline test can run them | Nit | Fixed as far as an offline test can. Both statements are pinned word for word in a test, and check 8 compares the query with the Python rule on real rows |

The two findings the verifier dropped, and what I did about each.

- **Three committed tests quoted the street of a draft case.** A reviewer raised it outside its own hunt, and the security review found the same three lines. It was true when it was posted. The verifier dropped it because I had already replaced the three streets by the time it looked. Check 11 says how the text was taken out of the branch's history before anything was pushed.
- **The counts on the address page said a company "has this principal address".** The verifier dropped it, because the sentence above the counts says what was compared. I reworded the counts anyway. The companies that are counted and not shown give the reader nothing to compare, and with no city given a match can be in another city, which the page did not say.

The security review read the leg's whole diff and sent requests at the app inside its own process. ✅ It reported no vulnerability it was at least 80% sure of: every typed value reaches Postgres as a parameter, the two new templates escape what they print, no new address was added, and nothing of a note reaches a log. It left four side notes.

| Side note | What was done |
|---|---|
| Three draft streets were in a committed test | Fixed, as above |
| The extraction command's `--output` defaults to the committed seed, so pointing `--test-set` at the drafts and leaving `--output` out would have written draft notes into a public file | Fixed. The command stops in that case, and a test proves the seed is untouched |
| The two limits bound what is returned and not what Postgres scans. The busiest house number has about 160,000 rows | Measured, and nothing changed: 73 milliseconds for a two-word street and 368 for a street of 250 words (check 5) |
| If the app's new code runs before the loader has built the address table, the address path answers "unavailable" | Nothing to change in the code. On the Mac the table is loaded. The pull request says to run the loader before the app after a fresh checkout |

✅ After the fixes I repeated the changes that had survived, and each now fails a test.

The list is at the end of this section, with the ones from the later rounds.

**Round 2** (one reviewer on the four commits that answered round 1, doing all three hunts on that diff, and reading the Human review section).

**3 Important and 1 Nit.** The reviewer confirmed that the app uses search version 1's order everywhere, that the sort key is exactly the one `main` had, and that the tests my first pass had changed are back to what `main` had or pass the order in. It found no draft text in the new diff, and it found all 16 items of "What I couldn't verify" in the Human review section.

| Finding | Tag | Answer |
|---|---|---|
| The sentence for an address with no match said that no company has that house number and street, also when a city had been given and compared. Companies with that address in another city make it false | Important | Fixed. The sentence has a second form, shown when a city was read from the note, that names the city as one of the three things compared. A test searches Tampa for an address whose companies are all in Orlando |
| The diagram in the Human review section said a street that begins with a house number gets the address search. A house number with no street name is asked about | Important | Fixed in the section, which now also says it in words. Decision 9 gives the reason |
| The Human review section said the leg is High tier because it touches the matching rules and the search pages. Under `REVIEW.md` those files are Medium, and the leg is High because it adds rows to `pipeline/seeds/` and changes wording that a report shows | Important. The reviewer was not sure of the severity, because the tier itself was right | Fixed in the section, and in the first line of this review |
| The pattern for a numbered street does not cover the old short forms 2D and 3D, as in "3D AVE" | Nit | Closed with a reason. 137 stored addresses begin with a word of that shape, and in none of them is it followed by a street type. In this data such a word is a house number that ends in the letter D |

While answering round 2, I repeated three deliberate breaks of the evaluation's wiring, and one survived: nothing tested that a draft cannot change the before-and-now decision, only the try-order one. A test was added for it.

**Round 3** (one reviewer on the round 2 commit, and the Human review section).

**1 Important, and nothing else.**

| Finding | Tag | Answer |
|---|---|---|
| The assertion added for that surviving break could not fail. It looked for a row of the drafts' table in the output of two calls, and the call before it had already printed the same row | Important | Fixed in commit `5ecb08a`. The test forgets the earlier output first and looks only under the drafts' own heading. With the drafts' table removed, or filled with the checked cases' counts, the test now fails. **This fix was not reviewed,** because the rules allow three rounds |

- ✅ The reviewer checked both sentences for an address with no match against every way the code reaches that page, and found each true.
- ✅ It found the two corrected sentences of the Human review section right, the rest of the section in line with the diff, all 16 unproven items present, and no company, person or address named that may not be.
- ✅ It agreed that closing round 2's Nit with a reason is within `REVIEW.md`. It could not check the count of 137.
- The numbers in the section that come from running the app or the database cannot be checked from a diff, and the reviewer listed them and did not call them findings.

✅ The deliberate breaks I repeated on the final code, each of which fails a test:

```
the sort removed from address_search():                              5 failed
the order under trial not applied to the second run:                 1 failed
"before Phase D" scored with the search by address:                  1 failed
the drafts' results added to the before-and-now decision:            1 failed
the drafts' results added to the try-order decision:                 1 failed
the drafts' table not printed:                                       2 failed
the drafts' table filled with the checked cases' counts:             2 failed
```

No Important finding is open. The brief says to stop a leg when Important findings remain after the third round. The one from round 3 is fixed, and its fix is the one commit no round covered, which the Human review section says.

---

## 5. Cost

| Item | Rate | Units | Cost |
|---|---|---|---|
| Snowflake | About $2 a credit | 0 credits. The leg made no call to Snowflake, as the brief requires | $0 |
| Claude API, the extraction step | 🟡 About $0.0004 a call (the plan's figure) | 27 calls | 🟡 About $0.011, a little over one cent |
| Postgres and Uvicorn on the Mac | Free | | $0 |

Phase D has used **27** of its 30 live extraction calls. No hosted account, hosted database or paid service was created.

---

## 6. Three questions Andres should be able to answer

1. The name search has two steps. What does each one do, and why could no new order in the second step put the right company first for `v pizza orlando`?
2. Rule S2 changed no checked case's rank. Why is it not switched on, and what are the two "places" of a company that the evaluation now compares?
3. The note `8586 palm pwwy` has a typing mistake, and the record says `8586 PALM PKWY`. Walk through how the address search decides that they match. Then say what happens for a company whose record says `8586 PALM PKWY STE 200`.

**Answers, to check yourself.** (1) Step 1, in Postgres, brings back the 200 names nearest to the typed name as a whole. Step 2, `rank()` in Python, puts those 200 in order. For "V PIZZA", 10,062 names pass step 1 and the right company stands 2,861st in step 1's order, so it is not among the 200. Step 2 can only order what step 1 handed it. This pattern is called retrieve-then-rerank, and its weak point is exactly this: the rerank cannot recover what the retrieve step dropped. (2) A company has a place by rank, where `rank()` puts it among all the candidates, and a place on the page, where a contractor sees it. The page shows the best five by rank in order of match level, so the two can differ. Under S2, case 9's right company stays first by rank, and a company with exactly the typed name climbs into the five, is rated Strong, and is shown above it. Rule S3 says to keep the old ranking when S2 and its variant both make a checked case worse, and both do. The evaluation's `--try-order s2` shows it. (3) Both texts are put in capitals with punctuation turned into spaces. The house number is the first word, and 8586 equals 8586. The kind of street is left out on both sides, so the record leaves PALM and the note leaves PALM and PWWY. Every word left of the record is among the typed words, so they match, and the mistyped PWWY is never compared with anything. With `STE 200` on the record, the record leaves PALM, STE and 200. STE and 200 were not typed, so it does not match, unless the note says "ste 200" too.

---

## 7. What only Andres can do: check the 16 draft cases

**Why.** A draft's expected answer is my reading of the register. Until you have checked it, it counts in no decision, and it stays off GitHub because an unchecked address may be somebody's home.

1. In VS Code (Visual Studio Code), open the file `evals/draft_cases.csv` in the folder `~/datum`. It has 16 rows and the same columns as `pipeline/seeds/test_set.csv`. The `notes` column says how each case was picked.
2. For each row, open [search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber](https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber) in Chrome, type the row's `expected_document_number`, and check two things: the company is the one a contractor would mean by the text in `input_text`, and nothing about the row names a person or a home.
3. For a row you accept, type today's date in its `verified_on` column, in the form `2026-11-26`. Then move the row to the end of `pipeline/seeds/test_set.csv`, give it the next free `case_id` (14 is the next), and set its `case_group` to `contractor_search`.
4. Move that case's row from `evals/draft_extracted.csv` to the end of `pipeline/seeds/extracted_inputs.csv`, and give it the same new `case_id`. Moving the row keeps the extraction that was already paid for.
5. Delete a row you reject from both draft files.
6. In the VS Code terminal, run `cd ~/datum`, then `source .venv/bin/activate`, then `python -m evals.run --backend postgres`. The first command moves the terminal into the project folder, the second switches it to the project's own Python, and the third scores the search.

**Done when** the evaluation prints your new cases in the table of checked cases, and `pytest` fails on exactly one test: `test_the_committed_test_set_is_read_and_joined_to_its_extractions`, which counts the checked cases. In its line `list(range(1, 14))`, change the 14 to one more than your last `case_id`, and in the line under it change the 3 to the number of `contractor_search` cases, and it passes again.

🟡 I did not run these steps, so treat the first one you move as a test of the instructions too.
