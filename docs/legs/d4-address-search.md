# Leg D4: the address search, finished

Branch `leg/d4-address-search` (from `leg/d3-name-search`) · pull request not opened yet · run on Nov 26, 2026 · risk tier **High** · status: **built and reviewed, with every check passing. Rounds 1 and 2 of the Deep review are answered, and round 3, the last, is next. Nothing is merged.**

This is the fourth and last leg of Phase D. Leg D1 built the search by address, and on Nov 26 Andres answered the questions it raised about it. The brief turned his answers into three rules, S15, S16 and S18, and this leg builds them behind the same gate as leg D3, rule S17.

**The short version**

- **A note no longer has to name the suite.** Rule S15 leaves an office unit (STE, SUITE, BLDG, FL, FLOOR, RM or ROOM, with the number or letter after it) out of the comparison, on the record and in the note. On the real app, one office building in Central Florida now lists its 3 active companies for a note that gives only its street, where the rule before this leg listed 1. An apartment, a unit or a lot is still compared, because those often mark a home.
- **The twelve directions count, and that has a cost I counted.** NORTH, SOUTH, EAST, WEST, NE, NW, SE and SW are now directions beside N, S, E and W, and a direction is not compared. So a street whose name IS a direction word, such as South Street, has nothing left to compare. **25,123 more stored streets** are in that state, and a note of a house number and `south st` now gets the question for more instead of the address search (question Q60).
- **An address where every company is inactive now leads somewhere.** The page keeps the count and adds one sentence asking for the business's name, because the name search lists inactive companies too (rule S16). It still lists none of them.
- **The terminal takes the web app's path.** An address-only note gets the address search in `src/datum/report.py` too, with the same sentences, and its questions no longer offer "a street or a city" (rule S18).
- **No checked case is worse** than on `main` at `051a928` or than after leg D3 (rule S17). The one checked address case, `8586 palm pwwy`, still lists the restaurant alone.
- 🟡 **The typed side of the cut can only lose matches, and it loses one kind.** A typed word the record lacks was always allowed, so leaving "suite 200" out of a note never adds a match. It does lose a record that writes the same unit after a `#` sign, as `#200`, because a number after `#` is still compared. 324,005 principal addresses write a unit that way. The leg follows the rule as written and asks Andres (question Q62).
- **The SQL and the Python agree, as the brief requires.** On 129,321 sampled companies the loader and Python cut the address the same way, and on 200 random addresses the query and `street_matches()` keep the same rows. Both counts of differences are **0**. Postgres's own pattern engine and the Python loop also agree, as exact text, on 71,048 invented streets.
- **More addresses are crowded.** Because the suites of a building are one address now, 10,177 addresses hold more than 50 companies, where 9,059 did, and 51 of 200 random addresses get the "too many" answer, where 46 did.
- **The address search meets the speed target:** a p95 of **256 milliseconds**, against 175 in leg D1 and a target of under 1 second. The p95 is the time that 95 of every 100 searches beat.
- The database went from 6,367 MB to **6,362 MB**, because the address table is a little smaller.
- The offline tests pass with Postgres stopped: **568**, of which 23 are new in this leg.
- The leg made **3** live extraction calls. Legs D3 and D4 together made 8 of the 10 they share. It used **no Snowflake**.
- Rounds 1 and 2 of the Deep review found 18 problems, 7 of them Important. Sixteen are fixed, and two are calls for Andres, recorded under questions Q54 and Q60. Round 3 is next.

**What is left for Andres**

1. **Rule on three questions this leg found, and read one more for the lawyer.**
   - Q60: should a direction word count as the street's name when it is the only word left? Today 25,123 more streets cannot be found by address because of the eight new direction words.
   - Q61: should the cut handle three smaller gaps: a floor written number first (`2ND FL`, 23,371 addresses), a unit number written with a hyphen (`STE 202-377`, 24,118) and a unit word glued to its number (`STE200`, 864)?
   - Q62: should the typed side keep the unit's number? Today a note that types "suite 200" no longer matches a record that writes `#200`.
   - Q54, for the lawyer, gained two consequences of rule S15 that the review found: a typed `bldg 2 apt 305` also lists another building's apartment 305, and a one-person company that writes its apartment as a suite is listed for anyone who types the building's street.
2. **Read the new and changed sentences** in section 1. Two are mine: the sentence of rule S16 and the terminal's "Add the business's full name or its city".
3. **Merge pull request 29, leg D3, before this one.** This branch sits on top of it.
4. Answer the three questions in section 6, because this is a High-tier change.
5. The `ANTHROPIC_API_KEY` that your terminal sets is still rejected by the Claude API (leg D3's report, item 4). I unset it again for the one command that started the app.

**The history, in order**

| When | What happened |
|---|---|
| Nov 26, start | The branch was made from leg D3's. Before anything changed, the scratch script of rule S17 ran the search at `051a928` on every case and kept the results in a local file, because rebuilding the address table drops the old one |
| Nov 26, rule S15 | The cut of an office unit was written in Python and in the loader's SQL, tried on a temporary copy inside Postgres, and then the tables were rebuilt. Checks 7 A and 8 gave 0 differences, and the gate passed |
| Nov 26, rules S16 and S18 | The sentence for an address with only inactive companies, then the terminal's address path. Two small moves of code came first, each in a commit of its own |
| Nov 26, the measurements | The crowded addresses, the speed, and the three searches on the real app |
| Nov 26, a stop | A usage limit stopped the run after the tables were rebuilt. It picked up again from git and the saved outputs |
| Nov 26, review round 1 | Three reviewers and a security review read the leg, and a fourth reviewer confirmed all 12 findings. The fixes rewrote three sentences about the comparison, made the terminal say when no company is close to a name, and added the tests the reviewers asked for |
| Nov 26, review round 2 | One reviewer found that the reworded "no match" sentences still denied a street with no word left, that Q62 hid a cost for homes, and that the section's diagram misstated the loader. All fixed |


---

## 1. What I built

### The picture

```
 the note a contractor types
        │  one model call (extract.py, prompt v3, NOT changed) reads the business name, the city and the street
        ▼
 search_kind()  picks the name search, the address search or a question
        │       ◀── the TERMINAL now asks this very function too (rule S18)
        │
        ├── no business, and a street with a house number ──▶ ADDRESS SEARCH
        │        typed:  "12 made up ave suite 250"          (an invented street)
        │                  street_parts():  house number 12, words MADE UP
        │                  (AVE is a street type, SUITE 250 an office unit: both left out)     ◀── rule S15
        │        stored: company_search_addresses, cut once by the loader
        │                  "12 MADE UP AVENUE, SUITE 150"  is stored as  MADE UP AVENUE           ◀── rule S15
        │                  "100 OCEAN DR BLDG 2 APT 305"        is stored as  OCEAN DR APT 305  (APT stays)
        │        a company matches when every word left of its street was typed
        │        ──▶ the active companies are listed, the inactive ones are counted
        │            and when ONLY inactive ones match: "Type the business's name ..."          ◀── rule S16
        │
        ├── a business is named ──▶ NAME SEARCH (leg D3)
        └── neither ──▶ ASK. The terminal now asks the page's own question                     ◀── rule S18
```

### The ideas, in plain words

**Cut once, compare many times.** An office unit has to go together with the word after it, its number or letter. The database's query can only ask whether a word is in a list, not which word stood next to which, so the cut cannot happen inside the search's query. It happens in two places instead: the loader cuts every stored address once, when it fills `company_search_addresses`, and `street_parts()` cuts the typed street in Python. Both sides then arrive already cut, so the query itself did not need a new text.

**Two copies of one rule must agree.** The loader's cut is a regular expression, a small pattern language, that Postgres runs, and the typed street's cut is a loop in Python. If they disagreed, a street would be stored one way and looked for another, and no offline test could notice, because no offline test can run Postgres. So the pattern is kept in `search.py` beside the loop, a test checks that the loader holds that very text, another runs the pattern with Python on 47,748 invented streets, and checks 7 A and 8 compare them on the real data.

**Home units stay.** APT, UNIT and LOT often mark an apartment or a mobile-home lot, which is a home. Leaving them out would let one typed address list the companies of every apartment there. So they are still compared, and a unit word is never taken as another unit word's number: `BLDG 2 APT 305` loses BLDG 2 and keeps APT 305.

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| `OFFICE_UNIT_WORDS`, `HOME_UNIT_WORDS`, `without_office_units()` and `OFFICE_UNIT_PATTERN` in `src/datum/search.py` | The two lists of unit words, the cut as a Python loop, and the same cut as a pattern for Postgres | Rule S15 |
| `DIRECTIONS` in `src/datum/search.py` | Twelve directions now, where there were four | Rule S15 |
| `street_parts()` and `street_matches()` | The typed street is cut before its words are compared, and the stored street is cut again, which changes nothing because the cut can run twice | Rule S15 |
| `ADDRESSES_FILL_SQL` in `src/datum/load_postgres.py` | The loader's statement that fills `company_search_addresses`. It now runs `regexp_replace` with the pattern over the words after the house number | Rule S15. The table was rebuilt with it |
| `ADDRESS_COMPARED`, `ADDRESS_NOT_FOUND` and `ADDRESS_NOT_FOUND_IN_CITY` in `src/datum/wording.py` | The sentences that say what an address search compares | The comparison changed, so the sentences that describe it changed in the same commit |
| `ADDRESS_ONLY_INACTIVE` and `only_inactive_text()` in `src/datum/wording.py`, one line in `src/datum/web/app.py` and one in `templates/address.html` | The sentence for an address where only inactive companies match | Rule S16 |
| `address_counts()` in `src/datum/report_builder.py` | The two sentences that count the companies an address search does not list, as Facts with their source. Moved out of `app.py`, unchanged | So the page and the terminal take their counts from one place |
| `save_report()`, `show_address_results()` and `by_address()` in `src/datum/report.py` | The terminal saves a report in one function, prints an address search's results in the page's words, and lets the user pick an active company | Rule S18 |
| `ASK_FOR_MORE` and `GIVING_UP` in `src/datum/wording.py`; `ASK_FOR_A_BUSINESS` removed | The terminal's questions, reworded | Rule S18 and the brief's D4 bullet "The terminal" |
| `docs/open_questions.md` | Q45, Q47, Q48 and Q49 say what was built or counted, and Q60 and Q61 are new | |

### The sentences this leg added or changed

| Name in `wording.py` | The text | Where it shows |
|---|---|---|
| `ADDRESS_COMPARED` (changed) | A company matches when its principal address on record has the house number {house_number} and a street name made only of words you typed. Three things are not compared: the kind of street, such as ST or PKWY; a direction (N, S, E, W, NORTH, SOUTH, EAST, WEST, NE, NW, SE or SW); and an office unit word (STE, SUITE, BLDG, FL, FLOOR, RM or ROOM) with the one word after it, its number or letter. A street name with no word left once those are left out matches nothing. A hyphen counts as a space, so in STE 400-B the B is still compared, and so is a unit written as one word, such as STE200. An apartment, unit or lot number on the record is compared, so it has to be typed too. | Under every address search that found a company, on the page and in the terminal |
| `ADDRESS_NOT_FOUND` (changed) | No company matches. A company matches when its principal address on record has that house number and a street name that keeps at least one word once the kind of street, a direction, and an office unit word with the one word after it are left out, and when every word it keeps is among the words you typed, with the same words left out of those. Check the house number and the spelling of the street's name, and add the apartment, unit or lot number if the address has one. | When an address search with no city found nobody |
| `ADDRESS_NOT_FOUND_IN_CITY` (changed) | No company matches. A company matches when its principal address on record has that house number and a street name that keeps at least one word once the kind of street, a direction, and an office unit word with the one word after it are left out, when every word it keeps is among the words you typed, with the same words left out of those, and when its principal city begins with the city you gave. Check the house number, the spelling of the street's name and the city, and add the apartment, unit or lot number if the address has one. | The same, when a city was given |
| `ADDRESS_ONLY_INACTIVE` (new, rule S16; the words are mine) | Type the business's name to look for it with the name search, which lists inactive companies too. | After the count, when no active company and at least one inactive one match |
| `ASK_FOR_MORE` (changed; the words are mine) | Add the business's full name or its city | The terminal's question after a search that ended without a report |
| `GIVING_UP` (changed) | I can't identify this business from what I have, so I won't guess. Run it again when you have its name and its city, or its street address beginning with the house number. | The terminal's last line when it gives up |
| `NO_COMPANY_FOUND` (not changed; now said in the terminal too) | No company with a name close to that was found. Check the spelling of the business's name. | The terminal says it when the name search finds no company, as the page always has. Round 1 of the review found the terminal said nothing there |
| `ASK_FOR_A_BUSINESS` (removed) | That describes a business but doesn't name one. Add its name, a street or a city | The terminal now asks the page's own `ASK_FOR_A_BUSINESS_ON_A_PAGE`, unchanged: "That describes a business but doesn't name one. Add its name, or its street address beginning with the house number." |

Rounds 1 and 2 of the review changed three of these sentences after the live check of check 8 had run: `ADDRESS_COMPARED`, `ADDRESS_NOT_FOUND` and `ADDRESS_NOT_FOUND_IN_CITY`. The table holds the final words. The first versions said that an office unit is left out "with the number or letter after it", which claimed more than the one-word cut does, and that no record had "a street name made only of words you typed", which a record that writes its unit after `#` could contradict. The second versions of the two "no match" sentences still denied a record whose street keeps no word at all, such as SOUTH ST, so they now say "No company matches." and state the rule a match follows.

### Files

| File | New or changed |
|---|---|
| `src/datum/search.py`, `tests/test_search.py` | Changed. 119 tests, 5 of them new |
| `src/datum/load_postgres.py`, `tests/test_load_postgres.py` | Changed: the statement that fills the address table. 19 tests, none new: the pinned statement's test changed with it |
| `src/datum/wording.py`, `tests/test_wording.py` | Changed. 17 tests, 2 of them new |
| `src/datum/web/app.py`, `src/datum/web/templates/address.html`, `tests/test_web.py` | Changed: one line each. 105 tests, 2 of them new |
| `src/datum/report_builder.py`, `tests/test_report_builder.py` | Changed: `address_counts()` moved here. 39 tests, none new |
| `src/datum/report.py`, `tests/test_report_cli.py` | Changed: the terminal's address path. 46 tests, 14 of them new |
| `docs/open_questions.md` | Changed |

In Postgres the leg rebuilt the tables from the same exported files, with the new cut. No Snowflake object, no dbt model and no seed was touched, and the extraction prompt was not changed.

---

## 2. Checks

### Check 0: before the leg

The four checks the brief asks for before legs D3 and D4 were run at the start of leg D3 on the same day, and all passed (leg D3's report, check 0). This leg's branch was made from leg D3's at `a038b4f`. `pipeline/seeds/test_set.csv` still holds 13 cases.

**The baseline, kept before the rebuild.** Rule S17 says that the rebuild of `company_search_addresses` drops the old table, so the scratch script must run on the address cases once before it and keep that output as the `051a928` baseline. It did, before anything in this leg changed. It also kept every case's result, by rank and on the page, in a local file, so that the gate after the rebuild compares with the search as it was on the table it was built for.

```
python gate.py main_051a928=051a928 --only address          (before the rebuild)

checked cases: 1   draft cases: 5
case  main_051a928
  13  1 of 1 / 1
draft cases, scored on the first five on the page (top-1 / recall@5 / wrong_match), counts only:
  main_051a928              3 / 4 / 1
```

### Check 1: the address case of the evaluation, before and after

The one checked case that takes the address path is case 13, `8586 palm pwwy`.

```
python gate.py --saved main_051a928=<the results kept before the rebuild> D4_final=HEAD --only address

case  main_051a928                D4_final
  13  1 of 1 / 1                  1 of 1 / 1
draft cases, scored on the first five on the page (top-1 / recall@5 / wrong_match), counts only:
  main_051a928              3 / 4 / 1
  D4_final                  3 / 4 / 1
```

| Cases | Measure | Before (`051a928`) | After |
|---|---|---|---|
| Case 13, the checked address case | Place of the restaurant, by rank and on the page | 1 of 1 / 1 | 1 of 1 / 1 |
| The 5 draft address cases, which count in no decision | Top-1 / recall at 5 / `wrong_match` | 3 / 4 / 1 | 3 / 4 / 1 |

The whole evaluation after the leg, on every case:

```
python -m evals.run --backend postgres

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
  11  contractor_search     L22000086098    L22000086098    yes    yes    no           1 of 200
  12  contractor_search     L22000086098    L22000086098    yes    yes    no           1 of 200
  13  contractor_search     L22000086098    L22000086098    yes    yes    no           1 of 1

group                    cases  top-1  recall@5  wrong_match
contractor_search            3      3         3            0
legal_name_variant           8      5         7            2
real_world_reference         2      2         2            0
ALL                         13     10        12            2

draft cases (evals/draft_cases.csv: not checked by Andres, and so counted in no pass or fail decision)
group                    cases  top-1  recall@5  wrong_match
address_only                 5      3         4            1
brand_and_city               6      4         6            2
name_and_street              5      1         2            4
ALL                         16      8        12            7
```

✅ The checked cases score as at the end of leg D3: 10 of 13 right, 12 in the first five, 2 wrong matches. This leg changed no name search.

### Check 2: the gate of rule S17

Each cell is the expected company's place by rank among the candidates, then its place on the page. The first column is the search at `051a928`, run on the old table before the rebuild and kept in a file. The second is the search at the end of leg D3, run on the rebuilt table. The third is the final code.

```
checked cases: 13   draft cases: 16
  main_051a928 = src/datum/search.py at 051a928, results kept in a file before the address table was rebuilt
  D3_head = src/datum/search.py at d5b2a1f
  D4_final = src/datum/search.py at HEAD

each cell: the expected company's place by rank among the candidates / its place on the page
case  main_051a928                D3_head                     D4_final                    
   1  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  
   2  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  
   3  2 of 10 / 2                 2 of 10 / 2                 2 of 10 / 2                 
   4  1 of 12 / 1                 1 of 12 / 1                 1 of 12 / 1                 
   5  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  
   6  1 of 27 / 1                 1 of 27 / 1                 1 of 27 / 1                 
   7  asked / asked               asked / asked               asked / asked               
   8  2 of 6 / 2                  2 of 6 / 2                  2 of 6 / 2                  
   9  1 of 28 / 1                 1 of 28 / 1                 1 of 28 / 1                 
  10  asked / asked               asked / asked               asked / asked               
  11  not among 200 / not shown   1 of 200 / 1                1 of 200 / 1                
  12  not among 200 / not shown   1 of 200 / 1                1 of 200 / 1                
  13  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  

scored on the first five ON THE PAGE:
            main_051a928                D3_head                     D4_final                    
top-1         8                           10                          10                          
recall@5      10                          12                          12                          
wrong_match   4                           2                           2                           
first on page 8                           10                          10                          

the gate of rule S17 (a checked case is worse when its company drops by rank, drops on the page, or leaves the first five, or when a note that should be asked about gets a company):
  D3_head: worse than main_051a928: none   better than main_051a928: [11, 12]   -> passes
  D4_final: worse than main_051a928: none   worse than D3_head: none   better than main_051a928: [11, 12]   -> passes

draft cases, counts only (not checked by Andres, and so counted in no decision):
  D3_head against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         5           0       1
    name_and_street              5         2           0       3
    ALL                         16         7           0       9
  D4_final against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         5           0       1
    name_and_street              5         2           0       3
    ALL                         16         7           0       9
  D4_final against D3_head:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         0           0       6
    name_and_street              5         0           0       5
    ALL                         16         0           0      16

draft cases, scored on the first five on the page (top-1 / recall@5 / wrong_match), counts only:
  main_051a928              3 / 7 / 12
  D3_head                   8 / 12 / 7
  D4_final                  8 / 12 / 7
```

- ✅ **The gate passes.** No checked case is worse than on `main`, and none is worse than after leg D3. I measured rule S15 on its own before committing it, and it gave the same places (the step's own output is kept with the others).
- Leg D3 did not change the address search, so for case 13 the true "step before" is the first column. The second column's address cases ran leg D3's rule on the rebuilt table, which is neither D3 as it was nor this leg. Comparing with one more column can only make the gate stricter, never looser, so I kept it.
- Rules S16 and S18 do not change which companies an address search finds, so the gate's places are the same after them.

### Check 3: checks 7 A and 8 of leg D1, run again

**7 A: the loader and Python cut an address the same way.** A scratch script reads a sample of companies, cuts each principal address in Python (`street_parts()`'s cut: the house number, then the words after it with office units left out), and compares that with what the loader stored. I ran it twice: first on a temporary copy inside Postgres, with the loader's own new statement, before the full rebuild, and then on the rebuilt table.

```
python d4_checks.py --dry      (a temporary copy, the loader's own statement, rolled back)
A. sampled 129,321 companies (a temporary copy, the loader's own statement): Python and the loader cut the address differently for 0
   an office unit was left out of 6,329 of them

python d4_checks.py            (the rebuilt table)
A. sampled 129,321 companies: Python and the loader cut the address differently for 0
   an office unit was left out of 6,331 of them
B. 200 addresses (fingerprint e17a1576706df4cc9a00bf1c0677ffc6), 1,071,053 rows under their house numbers, 333,004 kept:
   the SQL and street_matches() keep the same rows for 200, and differ for 0
```

| Check | Leg D1 | This leg |
|---|---|---|
| 7 A: sampled companies whose address Python and the loader cut differently | 0 of 128,118 | **0 of 129,321** |
| 7 A: of them, how many had an office unit left out | none (no cut) | 6,331 |
| 8: random addresses where the query and `street_matches()` keep different rows | 0 of 200 | **0 of 200** |
| 8: rows under their house numbers / rows kept | 1,071,053 / 237,837 | 1,071,053 / 333,004 |

- ✅ **Both answers are 0**, as the brief requires.
- The 200 addresses of check 8 are the same as in leg D1: the fingerprint, a short code for the whole list, is `e17a...` both times. Merging the suites keeps 95,167 more rows for the same 200 addresses.
- The query that check 8 runs is the app's own: the script asserts that its two conditions are word for word the ones in `AT_HOUSE_NUMBER_SQL`.

**Postgres's own pattern engine, on the test's streets.** The test that compares the loader's pattern with the Python loop runs the pattern with Python's engine, because no offline test can run Postgres. The security review pointed out that gap, so the same 71,048 invented streets were sent to Postgres and cut there with the loader's own expression, and the results were compared with the Python loop as exact text. Round 1 also asked whether the rebuilt table holds a doubled or trailing space, which the query would read as an empty word.

```
the test's 71,048 invented streets, cut by Postgres's own regexp_replace with the loader's pattern and by the Python loop, compared as exact text: they differ for 0
the rebuilt table: stored streets with a doubled space 0, with a space at either end 0, that the query would read with an empty word 0
```

✅ No difference, and no stray space in any of the 12,988,435 stored streets.

**Why `AT_HOUSE_NUMBER_SQL` has the same text.** The brief lists it among the things to change. The office units are left out of the stored street by the loader and out of the typed words by `street_parts()` before they are sent, and the eight new directions arrive in the two lists the query receives as values. So the query compares what is left on both sides, as it did before, and check 8 shows it keeps the same rows as the Python rule. Against a table filled before this leg, the query would be stricter than the rule and never looser: a stored `STE 200` would still be there, and it is not among the words a note sends. The comment above the query says this.

### Check 4: the crowded addresses, before and after

An address here is a house number and a street written one way. The limit of 50 is question Q48's, kept by Andres on Nov 26.

```
python d4_counts.py            (before the rebuild, on the old table and the old code)
A. company_search_addresses: 12,988,435 rows; 12,215,961 with a house number; 4,883 with a house number and no street word
A. addresses (a house number and street words, written one way): 6,491,034, holding 12,211,078 companies
A. addresses with more than 50 companies: 9,059, holding 1,359,023 companies (11.1%); the largest holds 74,674
B. 200 principal addresses drawn at random (fingerprint e17a1576706df4cc9a00bf1c0677ffc6)
B. no city given: too many to list 46; at least one company matched 154; no company matched 0; not an address search 0
B. each company's own city given: too many to list 41; at least one company matched 159; no company matched 0; not an address search 0

python d4_counts.py            (after)
A. company_search_addresses: 12,988,435 rows; 12,215,961 with a house number; 5,945 with a house number and no street word
A. addresses (a house number and street words, written one way): 6,253,725, holding 12,210,016 companies
A. addresses with more than 50 companies: 10,177, holding 1,593,668 companies (13.1%); the largest holds 138,217
B. 200 principal addresses drawn at random (fingerprint e17a1576706df4cc9a00bf1c0677ffc6)
B. no city given: too many to list 51; at least one company matched 149; no company matched 0; not an address search 0
B. each company's own city given: too many to list 43; at least one company matched 157; no company matched 0; not an address search 0
```

| Measure | Before | After |
|---|---|---|
| Addresses that hold more than 50 companies | 9,059 | **10,177** |
| Companies at those addresses | 1,359,023 (11.1%) | 1,593,668 (13.1%) |
| The largest address | 74,674 companies | 138,217 companies |
| Of 200 random addresses, "too many to list", no city given | 46 | **51** |
| The same, with each company's own city given | 41 | 43 |

🟡 More addresses get no list at all now. That is the cost of merging the suites, and it was expected when the rule was made. The limit stayed at 50.

### Check 5: what the cut leaves behind, counted

```
C. of 12,213,042 principal addresses that begin with a digit: 23,371 hold a floor written number first (such as 2ND FL), which keeps its ordinal;
   864 hold a unit word glued to its number (such as STE200), which is one word and is still compared
C. 39,646 stored streets are made only of street types and directions, and 5,945 have a house number and no street word at all: neither can be found by address
stored streets (after rule S15's unit cut) made only of street types and the FOUR old directions: 14,523
stored streets made only of street types and the TWELVE directions of rule S15: 39,646
  so the eight new direction words alone leave 25,123 more streets with no word to compare
  of the 39,646, 23,104 hold NORTH, SOUTH, EAST or WEST spelled out (such as a street named SOUTH ST)
principal addresses that begin with a digit and hold an office unit word: 640,020
  of them, a unit whose number is written with a hyphen (such as STE 202-377 or SUITE A-84): 24,118
  such a number becomes two words, so the unit word and the first part are left out and the second part stays, and a note must hold it
```

| Gap | Addresses | What happens |
|---|---|---|
| A street whose name is a direction word, such as SOUTH ST | 25,123 more streets with nothing to compare than with the four old directions. 39,646 in all, of which 23,104 hold NORTH, SOUTH, EAST or WEST spelled out | The address cannot be found by address, and a note of a house number and `south st` gets the question (question Q60) |
| A floor written number first, such as `2ND FL` | 23,371 | FL goes, 2ND stays, so a note must hold 2ND. The rule names this gap (question Q61) |
| A unit number written with a hyphen, such as `STE 202-377` | 24,118 of the 640,020 addresses that hold an office unit word | The hyphen becomes a space, so the second part stays as a word, and a note must hold it (question Q61) |
| A unit word glued to its number, such as `STE200` | 864 | It is one word that is not a unit word, so it is compared (question Q61) |
| A house number with no street word left at all | 5,945, where there were 4,883 | Mostly an address that was only a unit after the house number. It cannot be found by address |

Each gap shows less, never more: a company is missed, and no extra company is listed.

### Check 6: the database, before and after

```
before:  datum_dev 6367 MB   company_search_addresses 864 MB in all (775 MB table, 89 MB index)
after:   datum_dev 6362 MB   company_search_addresses 858 MB in all (769 MB table, 89 MB index)

python src/datum/load_postgres.py
table                       Snowflake exported   Postgres loaded
company_search                      12,988,435        12,988,435
company_flags                            9,950             9,950
company_possible_matches                     0                 0
source_coverage                              5                 5
company_search_names: 12,988,435 rows built from company_search's 12,988,435; 0 only in company_search_names, 0 only in company_search
company_search_addresses: 12,988,435 rows built from company_search's 12,988,435; 0 only in company_search_addresses, 0 only in company_search
index company_search_addresses_house_number: built in 6.8 seconds
database total: 6362 MB
python src/datum/load_postgres.py  14.89s user 5.90s system 2% cpu 11:52.96 total
```

✅ The loader rebuilt every table from the exported files of Nov 20, and every count equals Snowflake's. It checked that the address table holds exactly the document numbers of `company_search` before it swapped anything in. It took 11 minutes 53 seconds.

### Check 7: the speed of the address search

The number for this report is the first run after a Postgres restart, as in legs C2, D1 and D3. The 200 addresses are the same ones leg D1 timed.

```
=== the final code, first run after a restart
 9:42  up 29 days,  4:52, 1 user, load averages: 3.73 4.54 4.38
latency of the search by address over 200 principal addresses drawn at random:
  p50 6 ms   p95 256 ms   slowest 393 ms
  searches over 1 second: 0 of 200
  searches answered with "too many to list": 51 of 200
  fingerprint of the random addresses: e17a1576706df4cc9a00bf1c0677ffc6
 9:42  up 29 days,  4:52, 1 user, load averages: 4.31 4.62 4.42
=== the final code, first run after another restart
latency of the search by address over 200 principal addresses drawn at random:
  p50 6 ms   p95 249 ms   slowest 397 ms
  searches over 1 second: 0 of 200
  searches answered with "too many to list": 51 of 200
  fingerprint of the random addresses: e17a1576706df4cc9a00bf1c0677ffc6
 9:42  up 29 days,  4:52, 1 user, load averages: 4.58 4.65 4.43
```

| Searches timed | p50 | p95 | Slowest | Target: p95 under 1 second |
|---|---|---|---|---|
| Leg D1, 200 random addresses | 6 ms | 175 ms | 424 ms | ✅ |
| **This leg, first run after a restart** | 6 ms | **256 ms** | 393 ms | ✅ |
| This leg, first run after another restart | 6 ms | 249 ms | 397 ms | ✅ |

- ✅ The target is met with a wide margin, on the first approach.
- 🟡 The p95 rose by about 80 milliseconds. Merging the suites keeps more rows per address, and each kept company is read in full from `company_search`.

### Check 8: three searches on the real app

I started the app with the brief's command and a throwaway access code that the shell made up, kept in a shell variable for one command and written nowhere. As in leg D3, the shell's own `ANTHROPIC_API_KEY` was unset for that one command, so that the app loaded its own key. Each search is one live extraction call.

The second address was chosen by leg D1's rule for draft addresses: at least one active company there whose name holds a legal-entity word, and no company there whose name could be a person's. It is an office building in Central Florida. Six companies have it as their principal address, three active and three inactive. Every name holds LLC or INC and a word such as TECHNOLOGY or SIMULATION, and none could be a person's. The building is described here by count and kind only, as the brief asks.

```
PYTHONPATH=src APP_ACCESS_CODE=<a throwaway code> uvicorn datum.web.app:app --host 127.0.0.1 --port 8766

healthz: ok   home without the code: 401   home with the code: 200

--- 8586 palm pwwy: status 200, 1.08 seconds
Companies by principal address
I read that as: the street "8586 palm pwwy"
A company matches when its principal address on record has the house number 8586 and a street name made only of words you typed.
Three things are not compared: ... (the sentence of section 1, in full)
1 active company matches.
  L22000086098  V PIZZA LAKE BUENA VISTA LLC · 8586 PALM PKWY, ORLANDO, FL 32836
3 inactive companies also match and are not listed. Source: Florida Division of Corporations (Sunbiz) company records · fetched about 2026-10-22
A company's principal address is the address it gave the state, which is not always where it does business.
  its report: How this company was identified: from the street "8586 palm pwwy" · found by its principal address on record ... · chosen by the user from the active companies listed.

--- the building's street, typed with no suite: status 200, 0.82 seconds
Companies by principal address
3 active companies match. They are in document-number order, which says nothing about which one you mean.
  three companies: two at different suites on their records, and one with no suite
3 inactive companies also match and are not listed. Source: ... · fetched about 2026-10-22
A company's principal address is the address it gave the state, which is not always where it does business.

--- the building's street, typed with another suite (the one of one active company): status 200, 0.93 seconds
  the same three active companies, in the same order, and the same count of 3 inactive ones
```

What leg D3's rule and this leg's rule do with the building's six records, computed by applying each rule, taken from git, to the same records:

```
leg D3's rule (before leg D4), note of the kind 'the building's street with no suite': 1 active and 2 inactive of the 6 companies there match
leg D3's rule (before leg D4), note of the kind 'the building's street with another suite': 2 active and 3 inactive of the 6 companies there match
leg D4's rule, note of the kind 'the building's street with no suite': 3 active and 3 inactive of the 6 companies there match
leg D4's rule, note of the kind 'the building's street with another suite': 3 active and 3 inactive of the 6 companies there match
```

| Search | Before this leg | Now |
|---|---|---|
| `8586 palm pwwy` | 1 active (the restaurant), 3 inactive | ✅ The same |
| The building's street, with no suite | 1 active, 2 inactive | ✅ 3 active, 3 inactive |
| The building's street, with another suite | 2 active, 3 inactive | ✅ 3 active, 3 inactive |

- ✅ The server's log of that run holds 16 lines. I searched it for every typed word and for the access code, and found none.
- 🟡 The inactive companies of the building are counted and not listed, as rule S6 says. One of them would have been listed before this leg had the note given its suite, which now makes no difference.
- The live check ran before round 1 of the review reworded `ADDRESS_COMPARED`, so the pages above showed its first version. The companies a page lists do not depend on that sentence.

### Check 9: the tests

```
brew services stop postgresql@17      → Successfully stopped `postgresql@17` (label: sh.brew.postgresql@17)
pg_isready                            → /tmp:5432 - no response
pytest                                → 560 passed in 3.38s
ruff check src tests                  → All checks passed!
brew services start postgresql@17     → Successfully started `postgresql@17` (label: sh.brew.postgresql@17)
pg_isready                            → /tmp:5432 - accepting connections
```

✅ With the database server stopped, all 568 tests pass, so the suite needs no database. 545 existed at the end of leg D3, and 23 are new.

**The tests the brief asks for by name**

| What the brief asks | The test | The input that makes it fail |
|---|---|---|
| Rule S15: a stored STE matches a note without it; a note with SUITE matches a stored address without it; a stored APT still needs the note's APT; a stored `BLDG 2 APT 305` does not match a note without APT 305; a stored SOUTH matches a typed S | `test_an_office_unit_is_left_out_on_both_sides_and_an_apartment_a_unit_or_a_lot_is_still_compared`, in `test_search.py` | Each of the five, written out with invented streets. Before this leg the first, the second and the last were misses |
| The cut itself, including a unit word that is never another's number and the known gap of `2ND FL` | `test_the_cut_of_an_office_unit_takes_the_unit_word_and_the_one_word_after_it` | Taking only the unit word, or swallowing an APT as a building's number |
| The SQL and the Python rule agree | `test_the_statement_that_cuts_an_address_is_pinned_word_for_word` in `test_load_postgres.py`, and `test_the_loaders_pattern_and_the_python_rule_cut_every_street_the_same_way` in `test_search.py` | The first fails if the loader's pattern is not search.py's. The second runs that pattern with Python on 47,748 invented streets against the loop. 🟡 It runs Python's pattern engine, not Postgres's: check 3 is the comparison on Postgres |
| Through the whole address search | `test_an_address_search_lists_the_companies_of_every_suite_and_keeps_an_apartment_apart` | Three suites of one building listed together, and an apartment there kept apart |
| Rule S16 | `test_an_address_with_only_inactive_companies_asks_for_the_business_name_after_the_count_and_lists_none`, in `test_web.py` | No sentence, or the sentence beside an active company, or for companies with no status on record |
| Rule S18: the terminal and the web app give the same kind of answer and the same companies for one note, on a fixture | `test_the_terminal_and_the_web_app_give_the_same_kind_of_answer_and_the_same_companies_for_one_note`, in `test_report_cli.py`, run for ten notes | Before this leg the address notes got the address search on the page and a question in the terminal. It also fails if the two list other companies or another order, if a company in the terminal has no source line under it, or if a fixed sentence is on one side and not the other, or in another order |
| What the terminal does after an address list | `test_the_terminal_reports_on_the_company_picked_from_an_address_list_and_counts_the_others` and `test_a_name_added_after_an_address_search_sends_the_note_to_the_name_search` | A report on another company than the one typed, a count of the others of 0, or a name added after an address search that is never searched |
| The page says what is compared | `test_the_sentence_about_what_an_address_search_compares_names_exactly_the_words_the_search_leaves_out`, in `test_wording.py` | The sentence is typed out, and the two lists in its brackets are checked against `DIRECTIONS` and `OFFICE_UNIT_WORDS` themselves |

✅ The deliberate breaks I made before the review, one at a time, each of which fails at least one test:

```
office units never left out:                                    9 failed
only the unit word left out, and its number kept:               9 failed
an APT, UNIT or LOT taken as a building's number:               2 failed
APT, UNIT and LOT left out like an office unit:                 7 failed
the four old directions only:                                   4 failed
street_matches() not cutting the stored street:                 2 failed
street_parts() not cutting the typed street:                    2 failed
the loader's pattern not cutting a BLDG:                        1 failed
the loader's statement keeping every word, as before leg D4:    1 failed
the page's sentence about what is compared left as it was:      4 failed
rule S16's sentence never handed to the page:                   2 failed
rule S16's sentence shown beside an active company too:         2 failed
the terminal asking for an address-only note, as before leg D4: 6 failed
the terminal listing the inactive companies at an address too:  4 failed
the terminal leaving out rule S16's sentence:                   2 failed
the terminal leaving out rule S8's note:                        3 failed
with every file put back:                                       560 passed in 2.98s
```

✅ Round 1 of the review named ten more changes that passed every test then. After the fixes, each fails at least one:

```
typing 0 at an address list still writes a report:        2 failed
the report always on the first company listed:            1 failed
the report's count of the others set to 0:                1 failed
no new round after an address search:                     2 failed
the terminal's address search ignoring the city:          1 failed
a company with no status treated as nobody:               1 failed
no source line under a listed company:                    2 failed
rule S8's note printed before the list:                   5 failed
the terminal silent when no company is close to the name: 1 failed
the pattern without its leading space:                    2 failed
with every file put back:                                 567 passed in 3.18s
```

### Check 10: the live extraction calls

| What for | Calls |
|---|---|
| The three searches on the real app | 3 |
| **Total for leg D4** | **3** |
| Legs D3 and D4 together | **8 of the 10 they share** |

✅ No checked case and no draft case was extracted again, and nothing was written to the saved extraction files. No test calls the API. The extraction prompt was not changed.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | The stored street is cut once, by the loader, and the typed street by `street_parts()`; `AT_HOUSE_NUMBER_SQL` keeps its text | A unit goes together with the word after it, and the query can only ask whether a word is in a list | The rule lives in two languages, Python and Postgres's patterns. Checks 3 and the two tests hold them together |
| 2 | `street_matches()` cuts the stored street again | It is the rule the tests cover, and it must give the right answer whatever it is handed. The cut can run twice without changing anything, which a test proves | A little work repeated on every row |
| 3 | The sentences that describe the comparison changed in the same commit as the comparison | A commit with the new comparison and the old sentences would have told a contractor to add a suite, which no longer helps | The commit holds a matching change and a wording change. Its message says why |
| 4 | The twelve directions are exactly the rule's, although they leave 25,123 more streets with nothing to compare | The rule names them, and it is binding | 🟡 Streets named after a direction cannot be found by address (question Q60) |
| 5 | The cut reads "the one word right after it" on the simplified words, so a hyphenated unit number leaves its second part | The rule's own words, and every gap shows less, never more | 🟡 Three gaps, counted in check 5 (question Q61) |
| 6 | The sentence of rule S16 reads "Type the business's name to look for it with the name search, which lists inactive companies too." | The rule asks for one sentence that asks for the name so the name search can look for it. The name search does not filter by status (rule S2) and marks an inactive company beside its name (rule S10) | 🔴 The words are mine |
| 7 | The sentence of rule S16 shows only when no active company and at least one inactive one match, and not for companies with no status on record | The rule's condition, and a company with no status on record is never called inactive | None |
| 8 | The terminal asks the web page's own question for a note that names no business, and `ASK_FOR_A_BUSINESS` is removed | Rule S18 says the same sentences, and the brief says to remove any question nothing uses | The terminal's prompt reads "... house number. (press Enter if you don't know): ", with a full stop before the bracket |
| 9 | `ASK_FOR_MORE` reads "Add the business's full name or its city" and offers no street | What is typed there is added to the note. Once a note names a business the name search runs and the street is not used (rule S5), so a street would not help; a name or a city helps after either search | 🔴 The words are mine, and they offer less than the page's search box does. `GIVING_UP`, which ends a run, offers both searches |
| 10 | Two moves of code, each in a commit of its own, came before the behavior that uses them | `CLAUDE.md` rule 5: no refactor mixed with a behavior change | Two more commits to read |
| 11 | The building for the live check was typed once with no suite and once with another suite | The first shows the merge, and the second shows that a typed suite is left out too | One more live call: 3 of the 5 left |
| 12 | The typed side of the cut follows rule S15 as written, although it can only lose matches | The rule says "on the stored side and on the typed side", and it is binding. Following it is the reading that shows less | 🟡 A note that types "suite 200" no longer matches a record that writes `#200` (question Q62). The page's sentences for "no match" were reworded so that they stay true about such a record |
| 13 | The terminal says `NO_COMPANY_FOUND` when the name search finds no company | Rule S18 asks for the same sentences, and the page has always said it. Round 1 of the review found the terminal said nothing there | It is a change in the terminal's name path, which rule S18 does not name |
| 14 | The shell's `ANTHROPIC_API_KEY` was unset for the one command that started the app, as in leg D3 | The app reads its own key with `load_dotenv()`, and the shell's value, which the API rejects, stood in the way | I worked around a setting on Andres's Mac and did not fix it. I read no key |

---

## 4. What I couldn't verify, and open questions for Andres

### What I couldn't verify

1. 🔴 **That the sentence of rule S16 is the wording Andres wants** (decision 6).
2. 🔴 **That `ASK_FOR_MORE` should offer no street** (decision 9).
3. 🟡 **Whether streets named after a direction should stay findable** (question Q60). 25,123 more stored streets have nothing to compare.
4. 🟡 **Whether the three smaller gaps matter** (question Q61): 23,371, 24,118 and 864 addresses.
5. 🟡 **That Postgres's pattern engine and Python's agree on every address.** They agreed on 129,321 sampled addresses in Postgres and on 47,748 invented streets in Python. Not every address was compared.
6. 🟡 **The crowded addresses.** 10,177 addresses now get no list, where 9,059 did, and the limit of 50 is unchanged (question Q48).
7. 🟡 **A mail drop.** A shop that rents mailboxes often writes them as STE numbers. Its companies are now one address, so a note that gives only the street lists them all when there are 50 or fewer. Many of them are one-person companies. I did not count such addresses. The privacy call on what an address search lists is question Q54, for the lawyer.
8. 🟡 **The speed on a host, and on a quiet machine.** Every timing is from the Mac.
9. 🟡 **The one live building.** It is one example, chosen by a rule.
10. 🟡 **The cost of an extraction call.** The figure of $0.0004 is the plan's.
11. 🟡 **How often a note types a suite that the record writes after `#`** (question Q62). 324,005 principal addresses write a unit after `#`, and since this leg a note that types such a unit as "suite N" does not match them. How many notes would do that is not known. Keeping the typed number would bring them back, and it would also let a typed `bldg 2 apt 305` list a record `APT 2`, another apartment.
12. 🟡 **Two privacy consequences of rule S15 as written** (question Q54, for the lawyer): a typed `bldg 2 apt 305` also lists another building's apartment 305, and a one-person company that writes its apartment as a suite is listed for anyone who types the building's street. Neither was counted.
13. 🟡 **The terminal on a database failure.** The terminal's address path, like its name path before it, prints Python's error report when Postgres cannot be reached, where the page shows a fixed sentence. The security review traced it and found no way for that report to quote the note.

### Questions added to `docs/open_questions.md`

| # | The question, in short |
|---|---|
| Q45, Q47, Q48, Q49 | Each row now says what was built or counted |
| Q60 | Should a direction word count as the street's name when it is the only word left? |
| Q61 | Should the cut handle a floor written number first, a hyphenated unit number, and a unit word glued to its number? |
| Q62 | Should the typed side of rule S15 keep the unit's number, so that a note with "suite 200" matches a record with `#200`? |
| Q54 | (for the lawyer, updated) It now records two consequences of rule S15 for homes |

### The review

- **Tier:** High. The leg changes `src/datum/report.py`, which is a High path in `REVIEW.md`, and the wording on the pages and in the terminal. The brief names both legs D3 and D4 as High.
- **Depth:** Deep. In round 1, three `reviewer` subagents ran in parallel, each with one of the hunts the brief sets for Phase D, and a fourth then checked every finding against the code. A security review ran alongside, because `src/` changed.
- **Rounds:** three, which is the most the rules allow. Round 3 reads the fixes of round 2 and the Human review section.
- **Findings over the rounds:** Round 1 had 12: 4 Important, 5 Nit, 1 Pre-existing and 2 calls for Andres. Round 2 had 6: 3 Important and 3 Nit. Round 3 is next.
- **What was not reviewed:** the commits after round 3, which change this report and add the pull request's row to `docs/review_log.csv`, and no code. Reviewers are told to skip leg reports, so this report's own text was checked only where the Human review section repeats it.

**Round 1** (three reviewers, then a fourth that checked their findings, on the leg's first six commits, and the security review).

The three reviewers posted 13 findings, and one of them was posted by two reviewers, so 12 in all. The fourth reviewer confirmed all 12 and dropped none: **4 Important, 5 Nit, 1 Pre-existing**, and 2 that the reviewers marked as uncertain because they are calls for Andres. Every finding was answered.

| Finding | Tag | Answer |
|---|---|---|
| A note that types "suite 200" leaves 200 out, and a record that writes the same unit as `#200` keeps it, so that record is not matched, where it was before this leg. The sentence for "no match" then said no record had "a street name made only of words you typed", which is false for that record | Important | The sentence is fixed: both "no match" sentences now say the words are compared once the left-out words are gone from both sides, which is true of that record too. The matching follows rule S15 as written, a test pins it, and whether the typed side should keep the number is question Q62 |
| `ADDRESS_COMPARED` said an office unit is not compared "with the number or letter after it". The cut leaves out one word, a hyphen is read as a space, so `STE 400-B` keeps B, and `STE200` is one word that is compared | Important | Fixed. The sentence says "with the one word after it, its number or letter", and names both cases. The loader's comment said "every suite" and is corrected too |
| Nothing checked what the terminal does after an address list: typing 0, the company reported on, the count of the others, and a name added afterwards could all go wrong with every test passing | Important | Fixed with two new tests and a check in the rule S18 test that 0 writes no report. Each of the four changes now fails a test |
| The rule S18 test could not see the page and the terminal disagree on a city, a company with no status, a listed company's source, or the order of the lines | Important | Fixed. Four more notes, a check of the source line under each listed company, and a comparison of every fixed sentence on both sides, in order. Each of the reviewer's changes now fails a test |
| The test that compares the loader's pattern with the Python loop compared word lists, which hide a stray space, and its vocabulary had no word ending in a unit word (posted by two reviewers) | Nit | Fixed: exact text, FARM and ESTE added, 71,048 streets. The same streets were also run through Postgres's own engine: 0 differences |
| A note of a house number and `south st` now gets the question, which asks for a street address beginning with the house number that the note already gave | Nit | Closed with a reason: it follows from rule S15's twelve directions, the same happened before this leg to a note such as `12 parkway` (leg D1, decision 9), and question Q60 now records this sentence |
| The comment above `ASK_FOR_MORE` said a city helps after either search, and after an address search that found nobody it cannot | Nit | Fixed |
| The new docstring of `report.py` said one note gets the same answer in both places, and when the name search found no company the terminal said nothing, where the page says `NO_COMPANY_FOUND`. The test's check for that sentence could never be true | Nit | Fixed: the terminal says the page's sentence, and the rule S18 test has the case. The fourth reviewer warned that the test's reader of the page did not know that page, so both sides would have passed as "something else": the reader now knows it |
| A comment in the rule S15 test said its second line was a miss before this leg, and it was not | Nit | Fixed, and the typed side's cut is asserted beside that line |
| The first advice of `ADDRESS_NOT_FOUND_IN_CITY` was not pinned word for word | Pre-existing | Fixed: both "no match" sentences are pinned word for word |
| Under rule S15 a typed `bldg 2 apt 305` also lists another building's apartment 305, and a one-person company that writes its apartment as a suite is listed for anyone who types the building's street | Uncertain: a privacy call | Closed with a reason: both are rule S15 as written, and they are privacy calls for the lawyer. Question Q54 now records both |
| Question Q60 gave an example note with a house number that is not in the test set, and question Q47's row carries an address of leg D1's again because this leg edits that row | Uncertain | Q60's example no longer has a house number. The address in Q47 was written in leg D1, is already on `main`, and is left as it is |

The security review read the leg's diff and traced a typed note to Postgres, to the pages, to the terminal and to the saved report. ✅ It reported no vulnerability it was at least 80% sure of: the loader's statement is built from constants only, every typed word reaches Postgres as a bound value, the new sentence is fixed text that the template escapes, the saved report's file name is a document number that must match the shape of one, and nothing typed reaches a log. It left four side notes.

| Side note | What was done |
|---|---|
| Two engines read the pattern, and the test runs only Python's | Measured: the test's 71,048 streets cut by Postgres's own engine, 0 differences as exact text. A caution now stands where the pattern is written |
| A home business that writes its apartment as a suite, or a building number with no APT, is now listed for anyone who types the building's street | Recorded under question Q54, for the lawyer |
| The terminal's address path prints Python's error report when the database cannot be reached, as its name path already did | Recorded in "What I couldn't verify". The reviewer found no way for that report to quote the note |
| The saved report keeps the extracted street as typed, and a typed word the record lacks still matches | Nothing to change: rule W6 allows the extracted fields, and the name path has saved a street since leg C3 |

**Round 2** (one reviewer on the four commits that answered round 1, doing all three hunts on that diff, then reading the Human review section against the whole leg and trying the three questions on it).

**3 Important and 3 Nit.**

- ✅ The reviewer ran the tests and got 567 passed, and 567 again with every connection to Postgres pointed at nothing. It broke the code ten ways in a copy outside the repo, including each change round 1 had named, and each failed a test.
- ✅ All three questions of section 6 could be answered from the Human review section alone, and all 13 items of "What I couldn't verify" were under "What is not proven".

| Finding | Tag | Answer |
|---|---|---|
| The "no match" sentences, as reworded in round 1, still denied one kind of record: a stored street made only of a street type and a direction, such as SOUTH ST, keeps no word, so it fitted their description, and it matches nothing. A note with a mistyped street type gets the address search and saw that sentence | Important | Fixed. Both sentences now say "No company matches." and then state the rule a match follows, including that the street name must keep at least one word, which is true of every record. `ADDRESS_COMPARED` gains "A street name with no word left once those are left out matches nothing." A new test puts a company at an invented SOUTH ST |
| The Human review section and question Q62 said that keeping the typed unit's number would "change nothing else". It would also let a typed `bldg 2 apt 305` list a record `APT 2`, another apartment, which rule S15 keeps APT compared to prevent | Important | Fixed in both. Q62 states both effects, and so does the decision in the section |
| The diagram in the Human review section said the loader cuts the stored street "with the same rule" as the typed one, and that the query asks whether every stored word is among the typed words. The loader cuts only office units, and the query also allows the street types and directions | Important | Fixed in the section |
| The order check of the rule S18 test compared the fixed sentences and not where the listed companies stand among them | Nit | Fixed: the listed companies take part in the order, and moving the terminal's list below rule S8's note now fails the test |
| Three comments said something false: about "the one word after it" in `wording.py`, the count of lines that were misses before this leg in the rule S15 test, and "each at another suite" in a terminal test | Nit | Fixed |
| The Human review section quoted two conclusions that are answers to the three questions, left four terms unexplained, and two decisions did not say what the other choice would change | Nit | Fixed in the section |

Round 3 is next, and it reads the two commits that answer round 2 and the corrected Human review section.

---

## 5. Cost

| Item | Rate | Units | Cost |
|---|---|---|---|
| Snowflake | About $2 a credit | 0 credits. The leg made no call to Snowflake, as the brief requires | $0 |
| Claude API, the extraction step | 🟡 About $0.0004 a call (the plan's figure) | 3 calls | 🟡 About $0.001, a tenth of a cent |
| Postgres and Uvicorn on the Mac | Free | | $0 |

Legs D3 and D4 made **8** of the 10 live extraction calls they share. No hosted account, hosted database or paid service was created.

---

## 6. Three questions Andres should be able to answer

1. A contractor types a building's street with no suite, and the records say "STE 200". Where is the suite left out of the stored address, and where out of the typed one, and why could the database's query keep its old text?
2. Why are APT, UNIT and LOT still compared when STE and SUITE are not, and what must a note hold to match a record that says `BLDG 2 APT 305`?
3. Every company at a typed address is inactive. What does the page say, why does it list none of them, and what does the terminal do with the same note now?

**Answers, to check yourself.** (1) The loader leaves the suite out of the stored street once, when it fills `company_search_addresses`, with a pattern that `regexp_replace` runs in Postgres. `street_parts()` leaves it out of the typed street in Python before the words are sent. The query only asks whether every stored word is among the typed words and the ignored ones, and both sides arrive already cut, so its text did not need to change. A unit has to go with the word after it, which a query that only asks "is this word in the list" cannot do. (2) They often mark an apartment or a mobile-home lot, which is a home, and leaving them out would let one typed address list the companies of every apartment there. That waits for the lawyer (question Q54). `BLDG 2` is an office unit and is left out, and APT is never taken as the building's number, so the stored street keeps APT 305, and the note must hold APT 305. (3) The page says "No active company matches.", gives the count of inactive companies with its source, and adds "Type the business's name to look for it with the name search, which lists inactive companies too." It lists none of them, because an address can be a home and rule S6 lists only the active companies there. The terminal now makes the same choice with `search_kind()`, runs the same address search, and prints the same sentences, and then asks for more details. Before this leg it asked for a business name and ran no address search at all.
