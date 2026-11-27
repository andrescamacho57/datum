# Leg D3: the name search finds the company

Branch `leg/d3-name-search` (from `main`) · pull request [#29](https://github.com/andrescamacho57/datum/pull/29) · run on Nov 26, 2026 · risk tier **High** · status: **built and reviewed, with every check passing. The Deep review ran its three rounds. Rounds 1 and 2 found 13 problems, 4 of them posted as Important, and round 3 found none. No Important finding is open. Nothing is merged. After the pull request opened, a deep review found one more problem, now fixed, and the review of its fix left a decision for Andres, question Q64 (section 7).**

This is the third leg of Phase D. Legs D1 and D2 fixed the search by address and the layout of the report, and left the name search failing for the restaurant Andres tried on Nov 24: `v pizza orlando` did not show V PIZZA LAKE BUENA VISTA LLC at all. On Nov 26 Andres answered the questions leg D1 had raised, and the brief turned his answers into four rules, S11 to S14, to be built one step at a time behind a gate, rule S17. This leg builds them.

**The short version**

- **The name search now finds the restaurant.** On the real app, `v pizza orlando` puts **V PIZZA LAKE BUENA VISTA LLC first**. So does `v pizza lake buena vista`, on two live runs in which the extraction step read the note two different ways.
- **All four rules passed the gate, and all four are kept.** The gate (rule S17) says a step is kept only when no checked case is worse than on `main` at commit `051a928`, and none is worse than after the step before, by rank or on the page. A checked case is one of the 13 rows of `pipeline/seeds/test_set.csv`, which Andres has confirmed by hand.

| What was built, in order | The gate | What it did to the two failing cases |
|---|---|---|
| Rule S11: the first step of the search keeps the names that hold every typed word before the nearest names. Rule S12: the page shows its five companies in rank order | ✅ passes | The right company enters the 200 candidates, at 17th and 20th. It is not on the page yet |
| Rule S13: the candidates are ranked by rule S2 (every typed word, then the city, then similarity) | ✅ passes | `v pizza orlando` is **first** |
| Rule S14: a city whose words are in the company's name also counts as the city agreeing, for the order only | ✅ passes | `v pizza lake buena vista` is **first** |

- **The evaluation went from 8 to 10 of 13 checked cases right.**

| Measure, on the 13 checked cases | On `main` at `051a928` | After this leg |
|---|---|---|
| Top-1: the first company on the page is the right one | 8 | **10** |
| Recall at 5: the right company is among the five on the page | 10 | **12** |
| `wrong_match`: the search answered, and its first company is the wrong one | 4 | **2** |

- 🟡 **`v pizza durbin` is still fourth of five.** The extraction step returned the business name "V Pizza" and no city, so the word "durbin" never reached the search. The brief says not to add a rule to make it pass, and it is a draft case, not a checked one. Question Q55.
- **The speed target is met, on the second approach.** The target is a p95 under 1 second, where the p95 is the time that 95 of every 100 searches beat. My first version of rule S11's query measured **1,052 milliseconds**, on a Mac that was very busy at that moment. The second version gives the same 200 candidates for every search and measured **599 milliseconds**. `main` measured 456 milliseconds the same hour (check 5).
- **Of 210 searches, 5 pages now show a company with a lower match level above one with a higher level,** and each of those pages carries the new sentence of rule S12 (check 4).
- The offline tests pass with Postgres stopped: **547**, of which 17 are new in this leg: 545 and 15 when the leg's review ended, and two more from the deep review's fix (section 7).
- The leg made **5** live extraction calls of the 10 that legs D3 and D4 share, and used **no Snowflake**. Five earlier requests were refused by the Claude API before any extraction ran, which item 4 below explains.
- The Deep review ran three rounds. Round 1 found 7 problems in the code and its tests, 1 of them posted as Important. Round 2 found nothing in the code and 6 problems in the text that opens the pull request, 3 of them Important. Round 3 found nothing. Eleven are fixed and two are questions for Andres (Q58 and Q59).

**What is left for Andres**

1. **Read the two new sentences** in section 1. One is the brief's, word for word. The other is mine, and question Q56 asks whether it is right.
2. **Rule on five questions** this leg could not decide. Each has a row in `docs/open_questions.md`.
   - Q55: the extraction step can drop a place altogether, which is why `v pizza durbin` is still fourth. Should the extraction prompt change?
   - Q56: is the wording of the new reason right, and should the terminal print the sentence of rule S12 too?
   - Q57: the evaluation's Snowflake backend no longer reproduces the app. Should it score the old order, be rebuilt, or be retired?
   - Q58: the right company is now first, and it is still rated Possible or Likely, because rule S4 keeps the match levels as they were. Should a level take the new signals into account?
   - Q59: when the place is in the typed name and also comes back as the city, the principal city stops breaking ties. Should such a city still count as found in the name?
3. **Look at one page: `cinemark durbin park` (checked case 9).** The right company is first, rated Possible, with the caution "This is only a POSSIBLE match". A company whose name is exactly "Cinemark" plus a legal ending is third, rated Strong. That is rule S12 doing what it says, and it is the page where the new sentence matters most.
4. **Fix or remove the `ANTHROPIC_API_KEY` that your shell sets.** The terminal I ran in already held a value for that variable, and the Claude API rejects it. The app reads its own key from the project's secrets file with `load_dotenv()`, which never replaces a value that is already set, so the app used the shell's key and every search answered "unavailable". For the live check I started the app with that one variable unset, for that one command. I did not read or print either key, and I did not look for where the shell sets it. Until it is fixed, `uvicorn` started from that kind of terminal will answer "The search is unavailable right now".
5. Answer the three questions in section 6, because this is a High-tier change.
6. The 16 draft cases of leg D1 are still waiting for your check. They are in `evals/draft_cases.csv` on your Mac.

**The history, in order**

| When | What happened |
|---|---|
| Nov 26, start | The four checks the brief asks for before the leg passed. The evaluation was run on the untouched branch and its output kept |
| Nov 26, step 1 | Rules S11 and S12 were built and measured together. No checked case was worse than on `main`, so both were kept |
| Nov 26, step 2 | Rule S13 was switched on and measured. It passed, and `v pizza orlando` came out first |
| Nov 26, step 3 | Rule S14 was built and measured. It passed, and `v pizza lake buena vista` came out first |
| Nov 26, the speed check | The first run missed the target. A second way of writing rule S11's query, with the same answers, met it. The gate was measured again on that final code |
| Nov 26, the live check | Five requests were refused by the Claude API because of the shell's key. With that variable unset the five searches ran |
| Nov 26, review round 1 | Three reviewers and a security review read the leg, and a fourth reviewer confirmed all 7 findings. Five were fixed, and two became questions Q58 and Q59 |
| Nov 26, review rounds 2 and 3 | Round 2 found nothing in the code and 6 problems in the Human review section, which were fixed. Round 3 found nothing |

---

## 1. What I built

### The picture

```
 the note a contractor types
        │  one model call (extract.py, prompt v3, NOT changed) reads the business name, the city and the street
        ▼
 search_kind()  picks the name search, the address search or a question   (NOT changed)
        │
        ▼  NAME SEARCH
 step 1  Postgres: the names that are close to the typed name pass.
         200 of them are kept:
            before   the 200 nearest to the typed name as a whole
            now      FIRST the names that hold every typed word, THEN the nearest    ◀── rule S11
        │
        ▼
 step 2  rank() puts the 200 in order:
            before   similarity, then the city, then the document number
            now      every typed word, then the city, then similarity, then the number ◀── rule S13 (rule S2 switched on)
                     "the city" = the principal city agrees, OR the city's words
                     are in the company's name                                         ◀── rule S14
        │
        ▼
 the page shows the best five:
            before   re-sorted by match level, Strong first
            now      in rank order, each with its level beside it                      ◀── rule S12
                     and one sentence under the list when a lower level stands above a higher one
```

### The ideas, in plain words

**Retrieve, then rerank.** A careful comparison of the typed name with 13 million company names would take too long, so the search works in two steps. Step 1 is a fast, rough query in Postgres that brings back 200 candidates. Step 2 puts those 200 in order in plain Python. The weak point of this pattern is that step 2 can only order what step 1 brought back. For `v pizza orlando`, 10,062 names passed step 1, the right company stood 2,861st among them, and so it was never one of the 200. That is why rule S11 changes step 1 and not the order.

**Two places for one company.** A company has a place by rank, which is where `rank()` puts it among the candidates, and a place on the page, which is where a contractor sees it. Until this leg the page re-sorted its five companies by match level, so the two could differ. Rule S12 makes them the same list, and the evaluation now scores the companies on the page.

**The order and the level are two different things.** The order says which company the search puts first. The level (Strong, Likely or Possible) is a claim to the contractor about how much of the record agrees with what was typed. Rule S4 keeps the levels exactly as they were. So this leg moves the right company to the top and does not make the page claim more about it.

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| `PostgresBackend.NEAREST_SQL` in `src/datum/search.py` | Step 1's query. Its `ORDER BY` has one more term, in front of the trigram distance: a name that holds every typed word comes first. `nearest()` sends the typed words and the list of legal endings as values | Rule S11. It is `holds_every_word()` written in SQL, so that the database can apply it before it cuts the list to 200 |
| `shortlist()` and `Shortlist.lower_level_above_higher` in `src/datum/search.py` | The five companies a page shows. They are no longer re-sorted by level. The best level is now looked for wherever it stands on the list, and a new property says whether a lower level stands above a higher one | Rule S12. The tie count of rule W7 used to read the first card's level, which was the best one only because of the sort |
| `RANK_ORDER` in `src/datum/search.py` | The one line that says which order the app uses. It now names `by_words_then_city`, which is rule S2 | Rule S13 |
| `city_in_name()`, `city_agrees_for_order()` and the field `Candidate.city_in_name` in `src/datum/search.py` | Whether every word of the city the extraction returned is among the words of the company's name, legal endings left out. The sort key of rule S2 reads it beside the principal city. `match_level()` does not read it | Rule S14. The extraction step moves a place out of the business name even when the place is part of the registered name |
| One more line in `evidence()` | The reasons shown beside a company get a line when the city's words are in its name. The line about the principal city stays beside it | Rule S14 says the evidence list says so |
| `src/datum/wording.py` | Two new sentences, in the table below | Every sentence a contractor can be shown lives in this one file |
| `src/datum/web/templates/shortlist.html`, `src/datum/web/app.py`, `src/datum/report.py` | The page and the terminal show the sentence of rule S12 under the list, when it applies | Rule S12 names the page. The terminal prints the same list, so I made it say the same sentence (decision 4) |
| `evals/run.py` | The evaluation. It now scores the companies on the page. `--try-order` gained `v1`, the old order, so the old order can still be scored beside the app's. Every docstring and help text that these changes made untrue is corrected | Rule S12 says top-1 means first on the page, and rule S17 says to correct the text in the same commit |

### The two sentences this leg added

| Name in `wording.py` | The text | Where it shows |
|---|---|---|
| `SHORTLIST_SEARCH_ORDER` (rule S12, word for word) | The list is in search order. The level beside each company says how much of the record agrees with what you typed. | Once, under the five companies, and only when a company with a lower level stands above one with a higher level. On the web page and in the terminal |
| `EVIDENCE_CITY_IN_NAME` (rule S14; the words are mine) | every word of the city you gave is in the company's name | In a company's list of reasons on the shortlist, in the terminal's question about a Possible match, and in the line of a report that says how the company was identified |

No other sentence changed. The second sentence says "city" because the two reasons beside it say "the city you gave", and it says "every word ... is in" because that is exactly what is compared: whole words, in any order. For a place such as Lake Buena Vista, which is not a city, "city" reads a little oddly (question Q56).

### Files

| File | New or changed |
|---|---|
| `src/datum/search.py`, `tests/test_search.py` | Changed. 114 tests, 9 of them new |
| `src/datum/wording.py`, `tests/test_wording.py` | Changed: two sentences and one small function. 15 tests, 2 of them new |
| `src/datum/web/app.py`, `src/datum/web/templates/shortlist.html`, `tests/test_web.py` | Changed: one line each in the app and the template. 103 tests, 2 of them new |
| `src/datum/report.py`, `tests/test_report_cli.py` | Changed: two lines in the terminal command. 32 tests, 1 of them new |
| `evals/run.py`, `tests/test_evals_run.py` | Changed. 34 tests, 1 of them new |
| `docs/open_questions.md` | Changed: Q46 and Q50 to Q52 say what was built, and Q55 to Q58 are new |

The extraction prompt, `pipeline/seeds/`, the loader and the database were not touched. No table was rebuilt in this leg. No Snowflake object and no dbt model was touched.

---

## 2. Checks

### Check 0: the four things the brief says to check before the leg

| What the brief asks | Result |
|---|---|
| Pull requests 25 and 26 are merged | ✅ `origin/main` contains commit `051a928`, and `src/datum/search.py` there defines `RANK_ORDER` and `address_search` |
| Postgres holds the data | ✅ `company_search` in `datum_dev` has 12,988,435 rows, and `company_search_addresses` has 12,988,435 |
| The exported files are still on the Mac | ✅ `data/export/` holds the folders `company_search`, `company_flags`, `source_coverage` and `export_counts` |
| Count the checked cases | ✅ `pipeline/seeds/test_set.csv` holds 13 cases, as on `main`. Andres had promoted no draft, so there was no extraction to copy and no commit for this check |

The branch was made from `origin/main` at `143d82c`, which is three commits after `ccef8da`: pull request 28, a documentation change, had been merged in between.

### Check 1: the evaluation, at `051a928` and after the leg

The first run is on the branch before any change to the search. The second is on the final code. Neither calls the Claude API: the evaluation reads the extractions saved in `pipeline/seeds/extracted_inputs.csv`.

```
python -m evals.run --backend postgres                (on the branch, before the first change)

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
```

```
python -m evals.run --backend postgres                (after the leg)

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

| Cases | Measure | At `051a928` | After the leg |
|---|---|---|---|
| The 13 checked cases | Top-1 | 8 | **10** |
| | Recall at 5 | 10 | **12** |
| | `wrong_match` | 4 | **2** |
| The 16 draft cases, which count in no decision | Top-1 | 3 | 8 |
| | Recall at 5 | 7 | 12 |
| | `wrong_match` | 12 | 7 |

- ✅ Cases 11 and 12, the two V Pizza name searches, went from "not among 200" to first. Nothing else moved.
- The three cases that are still not right are older ones. Case 7 is a note the extraction step judged too vague, so the search asks. Cases 3 and 8 each have the right company second, behind a company with a nearly identical name. This leg changed neither their rank nor their place on the page.
- The draft cases got better too. They decided nothing, and I did not look at any of them one by one (rule S1).

### Check 2: the gate of rule S17, step by step

Rule S17 asks for one scratch script, not committed, that runs the search as it is at `051a928` and the search after each step, against the same Postgres in the same run.

**What the script does.** It takes a list of git commits. For each one it reads `src/datum/search.py` exactly as that commit has it, with `git show`, and loads it as a module of its own. So "the search at `051a928`" is that commit's own query, its own rank order and its own way of putting the page in order, and not a copy I typed again. It then sends every checked case and every draft case through each version, the way `evals/run.py` does, and prints each checked case's place by rank and on the page. For the draft cases it prints counts only. It calls a checked case worse by the rule's own test, using `moved()` from `evals/run.py`: the company drops by rank, drops on the page or leaves the first five, or a note that should be asked about gets a company.

Each cell below is the expected company's place by rank among the candidates, then its place on the page. The five versions are: `main` at `051a928`; rules S11 and S12 (commit `e9290c0`); rule S13 (`1d16ba0`); rule S14 (`fa8546b`); and and the final code (`11431f7`), which rewrites rule S11's query for speed and holds the answers to round 1 of the review.

```
checked cases: 13   draft cases: 16
  main_051a928 = src/datum/search.py at 051a928
  S11_and_S12 = src/datum/search.py at e9290c0
  S13 = src/datum/search.py at 1d16ba0
  S14 = src/datum/search.py at fa8546b
  final = src/datum/search.py at 11431f7

each cell: the expected company's place by rank among the candidates / its place on the page
case  main_051a928                S11_and_S12                 S13                         S14                         final                       
   1  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  
   2  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  
   3  2 of 10 / 2                 2 of 10 / 2                 2 of 10 / 2                 2 of 10 / 2                 2 of 10 / 2                 
   4  1 of 12 / 1                 1 of 12 / 1                 1 of 12 / 1                 1 of 12 / 1                 1 of 12 / 1                 
   5  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  
   6  1 of 27 / 1                 1 of 27 / 1                 1 of 27 / 1                 1 of 27 / 1                 1 of 27 / 1                 
   7  asked / asked               asked / asked               asked / asked               asked / asked               asked / asked               
   8  2 of 6 / 2                  2 of 6 / 2                  2 of 6 / 2                  2 of 6 / 2                  2 of 6 / 2                  
   9  1 of 28 / 1                 1 of 28 / 1                 1 of 28 / 1                 1 of 28 / 1                 1 of 28 / 1                 
  10  asked / asked               asked / asked               asked / asked               asked / asked               asked / asked               
  11  not among 200 / not shown   17 of 200 / not shown       1 of 200 / 1                1 of 200 / 1                1 of 200 / 1                
  12  not among 200 / not shown   20 of 200 / not shown       15 of 200 / not shown       1 of 200 / 1                1 of 200 / 1                
  13  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  1 of 1 / 1                  

scored on the first five ON THE PAGE:
            main_051a928                S11_and_S12                 S13                         S14                         final                       
top-1         8                           8                           9                           10                          10                          
recall@5      10                          10                          11                          12                          12                          
wrong_match   4                           4                           3                           2                           2                           
first on page 8                           8                           9                           10                          10                          

the gate of rule S17 (a checked case is worse when its company drops by rank, drops on the page, or leaves the first five, or when a note that should be asked about gets a company):
  S11_and_S12: worse than main_051a928: none   better than main_051a928: [11, 12]   -> passes
  S13: worse than main_051a928: none   worse than S11_and_S12: none   better than main_051a928: [11, 12]   -> passes
  S14: worse than main_051a928: none   worse than S13: none   better than main_051a928: [11, 12]   -> passes
  final: worse than main_051a928: none   worse than S14: none   better than main_051a928: [11, 12]   -> passes

draft cases, counts only (not checked by Andres, and so counted in no decision):
  S11_and_S12 against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         2           1       3
    name_and_street              5         2           0       3
    ALL                         16         4           1      11
  S13 against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         3           0       3
    name_and_street              5         2           0       3
    ALL                         16         5           0      11
  S13 against S11_and_S12:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         3           0       3
    name_and_street              5         2           0       3
    ALL                         16         5           0      11
  S14 against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         5           0       1
    name_and_street              5         2           0       3
    ALL                         16         7           0       9
  S14 against S13:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         4           0       2
    name_and_street              5         0           0       5
    ALL                         16         4           0      12
  final against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         5           0       1
    name_and_street              5         2           0       3
    ALL                         16         7           0       9
  final against S14:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         0           0       6
    name_and_street              5         0           0       5
    ALL                         16         0           0      16

draft cases, scored on the first five on the page (top-1 / recall@5 / wrong_match), counts only:
  main_051a928              3 / 7 / 12
  S11_and_S12               3 / 8 / 12
  S13                       5 / 9 / 10
  S14                       8 / 12 / 7
  final                     8 / 12 / 7
```

- ✅ **Every step passes.** No checked case is worse than on `main`, and none is worse than after the step before.
- ✅ **Case 9, `cinemark durbin park`, stays first on the page under rule S2.** In leg D1 this order moved it to second on the page, which is why it was not switched on. Rule S12 removed the cause.
- I measured each step before I committed it, on the files as they were on disk, and the table above is one more run over the commits afterwards. The earlier runs gave the same places.
- I also measured rule S11 alone, before rule S12 was built: it gave 17th and 20th for cases 11 and 12 and moved 4 drafts up and 1 down, which are exactly the numbers leg D1's scratch script had reported for this change.
- 🟡 Between "S11 and S12" and "S13", and again at "S14", draft cases moved up and none moved down. With rule S11 and S12 alone, one draft of the kind "a brand and a place" stood lower than on `main`. I did not look into which or why, because a draft may not shape the search, and the next step moved it back up.

### Check 3: rule S11 in the query and `holds_every_word()` in Python give the same answer

Rule S11 lives in SQL, and no offline test can run SQL. If the query's term and the Python function disagreed, the pool would be filled by one rule and ranked by another, and no test would notice. So a scratch script compared them on the real data. For each of the 210 searches of the speed check it read every name that passes step 1's `WHERE`, and compared the query's term, taken from the app's own query text, with `holds_every_word()`, name by name.

```
B. 210 searches, 558,647 names that pass the first step's WHERE, 3,876 of them hold every typed word by the SQL term: the SQL term and holds_every_word() differ for 0
```

✅ They agree on all 558,647 names. Only 3,876 of those names hold every typed word, which is why the term can be cheap (check 5).

### Check 4: how often a page now shows a lower level above a higher one

The brief asks for this count on the 200 randomly drawn names of the speed check.

```
A. pages that show a lower level above a higher one: 5 of 210 (3 of the 200 random names, 2 of the 10 checked cases); pages with at least one company: 210
```

- **3 of the 200 random names, and 2 of the 10 checked cases that are searched by name.** Every such page carries the sentence of rule S12.
- The two checked cases are 6 and 9. For case 9 the five levels down the page read Possible, Possible, Strong, Possible, Possible: the right company is first and rated Possible, and a company whose name is exactly the typed name is third and rated Strong. For case 6 they read Strong, Possible, Possible, Likely, Possible, and the right company is the Strong one at the top.
- 🟡 The random names are full legal names, typed exactly, with no city. A contractor types a short trade name and a town, as in case 9, so a real mix of searches will show this more often than 3 in 200. I have no measure of how much more.

### Check 5: the speed of the name search

The target is a p95 under 1 second. As in legs C2 and D1, the number for this report is the first run after Postgres is restarted, and I chose that before timing anything. The 210 searches are the same ones leg D1 timed: the 10 checked cases that are searched by name, and 200 company names drawn at random. The fingerprint, a short code for the whole list of names, is the same as in leg D1.

**The first approach missed the target.**

```
brew services restart postgresql@17
python -m evals.run --backend postgres --latency 200          (rule S11 as first committed, 2b111a7 to fa8546b)
latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 172 ms   p95 1052 ms   slowest 5065 ms
  searches over 1 second: 11 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37
```

Two things were wrong, and I measured both.

- **The Mac was very busy.** Its load average was between 12 and 20 at that moment. The load average is the number of programs that want the processor at once, and this Mac is comfortable below about 8. A macOS Bluetooth service and the Spotlight indexer were using the processor. They are not mine to stop, so I waited.
- **My query was slower than it had to be.** It cut the legal endings off every name that passed step 1's `WHERE`, with a pattern match, and only then looked for the typed words. For a common word tens of thousands of names pass.

**The second approach.** A cheap test now stands in front of the pattern match: does the whole name, legal endings included, hold every typed word? The pattern runs only for a name that does. Cutting the endings off a name only removes words, so a name that fails the cheap test fails the real one too, and the answer for every name is the same. The two tests are joined with `CASE`, which is how SQL promises that the second is worked out only when the first is true.

A scratch script timed four ways of writing step 1's query on the same 210 searches, back to back, twice. It also checked that each one keeps the same 200 document numbers in the same order as my first version.

```
round 1  old (nearest only)                                             p50   129 ms  p95   649 ms  slowest  4707 ms  over 1 s: 7
round 1  S11 as committed (regexp on every name)                        p50   112 ms  p95   419 ms  slowest  3791 ms  over 1 s: 2
round 1  words first, regexp only when they are all there               p50   117 ms  p95   359 ms  slowest  3070 ms  over 1 s: 2
round 1  CASE: regexp only when the words are all there (the code now)  p50   106 ms  p95   328 ms  slowest  2898 ms  over 1 s: 2
round 1  words only, no regexp (NOT the same rule)                      p50   108 ms  p95   343 ms  slowest  2759 ms  over 1 s: 2
round 2  old (nearest only)                                             p50   105 ms  p95   333 ms  slowest  2797 ms  over 1 s: 2
round 2  S11 as committed (regexp on every name)                        p50   108 ms  p95   370 ms  slowest  3831 ms  over 1 s: 2
round 2  words first, regexp only when they are all there               p50   105 ms  p95   334 ms  slowest  2816 ms  over 1 s: 2
round 2  CASE: regexp only when the words are all there (the code now)  p50   105 ms  p95   331 ms  slowest  2749 ms  over 1 s: 2
round 2  words only, no regexp (NOT the same rule)                      p50   105 ms  p95   320 ms  slowest  2799 ms  over 1 s: 2
same 200 document numbers in the same order as S11 as committed: 168 of 210   <- old (nearest only)
same 200 document numbers in the same order as S11 as committed: 210 of 210   <- S11 as committed (regexp on every name)
same 200 document numbers in the same order as S11 as committed: 210 of 210   <- words first, regexp only when they are all there
same 200 document numbers in the same order as S11 as committed: 210 of 210   <- CASE: regexp only when the words are all there (the code now)
same 200 document numbers in the same order as S11 as committed: 209 of 210   <- words only, no regexp (NOT the same rule)
```

- ✅ The `CASE` form, which is the code now, keeps the same 200 companies in the same order as the first version for all 210 searches.
- In the second round, on a calmer machine, the query before rule S11 had a p95 of 333 milliseconds, my first version 370, and the `CASE` form 331.
- The last line is a form that leaves the pattern out altogether. It is not the same rule, and it gives a different pool for 1 search of 210, so I did not use it.

**The number for this report.** It was taken at commit `0164869`, the commit that rewrote the query. The commits after it change comments, tests and the one sort key the app does not use, so the search the app runs is the same.

```
=== HEAD 0164869, first run after a restart
 3:17  up 28 days, 22:27, 1 user, load averages: 4.34 9.61 12.70
latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 134 ms   p95 599 ms   slowest 3565 ms
  searches over 1 second: 4 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37
 3:18  up 28 days, 22:28, 1 user, load averages: 4.39 8.64 12.12
=== main at 051a928, first run after a restart (for comparison on the same machine, the same hour)
latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 114 ms   p95 456 ms   slowest 3169 ms
  searches over 1 second: 2 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37
 3:18  up 28 days, 22:28, 1 user, load averages: 4.40 8.06 11.73
=== HEAD 0164869, first run after another restart
latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 118 ms   p95 589 ms   slowest 4076 ms
  searches over 1 second: 3 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37
 3:19  up 28 days, 22:29, 1 user, load averages: 5.53 7.81 11.42
```

| What was timed | p50 | p95 | Slowest | Searches over 1 second | Target: p95 under 1 second |
|---|---|---|---|---|---|
| Rule S11 as first committed, on a very busy Mac | 172 ms | 1,052 ms | 5,065 ms | 11 of 210 | ❌ |
| **The final code, first run after a restart** | 134 ms | **599 ms** | 3,565 ms | 4 of 210 | ✅ |
| The final code, first run after another restart | 118 ms | 589 ms | 4,076 ms | 3 of 210 | ✅ |
| `main` at `051a928`, the same hour, the same way | 114 ms | 456 ms | 3,169 ms | 2 of 210 | ✅ |

- ✅ The target is met, and the brief's stop rule did not apply: it stops the leg when two different approaches both miss.
- 🟡 **The final code is slower than `main` in this measurement, 599 against 456 milliseconds, and I cannot fully say why.** Timed back to back, step 1's query is as fast as before (331 against 333). The whole search also reads 200 full company rows and ranks them, and under rule S11 those 200 are other companies, on other pages of the table, right after a restart. That is my best explanation and I did not prove it. Leg D1 measured 515 milliseconds for `main`'s search on Nov 25.
- 🟡 The Mac was still busier than usual during the final runs, with a load average between 4 and 6. Every number here is a little worse than a quiet machine would give.
- 🟡 Three or four searches still take longer than 1 second, as in legs C2 and D1. They are names made of one long common word and one or two short ones.

### Check 6: the five searches on the real app

I started the app with the brief's command and a throwaway access code that the shell made up, kept in a shell variable for one command and written nowhere. Each search is one live extraction call. Only the two companies the brief names are named here, with their document numbers. Every other company on a list is given by its place, its level and its status, and no more, because a company the page happened to show may be the expected answer of a draft case, and the drafts stay off GitHub.

```
PYTHONPATH=src APP_ACCESS_CODE=<a throwaway code> uvicorn datum.web.app:app --host 127.0.0.1 --port 8765
(started with the shell's ANTHROPIC_API_KEY unset for this one command, so that the app loaded its own key)

healthz: ok   home without the code: 401   home with the code: 200

--- v pizza orlando: status 200, 2.24 seconds
I read that as: the business name "V Pizza", the city "Orlando"
2 companies on this list match at the level Likely. Check which one you mean before you open a report.
  1. L22000086098  Likely    active      V PIZZA LAKE BUENA VISTA LLC, ORLANDO
  2. Likely    inactive    a company in Orlando whose name holds the words PIZZA and V in another order
  3. Possible  inactive    another V Pizza company, in another city
  4. Possible  active      another V Pizza company, in another city
  5. Possible  active      another V Pizza company, in another city

--- v pizza lake buena vista, first run: status 200, 0.93 seconds
I read that as: the business name "V Pizza", the city "Buena Vista", the street "Lake"
5 companies on this list match at the level Possible. Check which one you mean before you open a report.
  1. L22000086098  Possible  active      V PIZZA LAKE BUENA VISTA LLC, ORLANDO
                   reasons: name is similar (85/100); principal city on record is ORLANDO, and that spelling does not
                   begin with the city you gave; every word of the city you gave is in the company's name; ACTIVE
  2. Possible  inactive    another V Pizza company
  3. Possible  active      another V Pizza company
  4. Possible  active      another V Pizza company
  5. L25000541856  Possible  active      V PIZZA DURBIN, LLC

--- 8586 palm pwwy: status 200, 0.93 seconds
Companies by principal address
I read that as: the street "8586 palm pwwy"
1 active company matches.
  L22000086098  V PIZZA LAKE BUENA VISTA LLC · Principal address 8586 PALM PKWY, ORLANDO, FL 32836
3 inactive companies also match and are not listed.

--- v pizza durbin: status 200, 0.96 seconds
I read that as: the business name "V Pizza"
5 companies on this list match at the level Possible. Check which one you mean before you open a report.
  1. Possible  inactive    another V Pizza company
  2. Possible  active      another V Pizza company
  3. Possible  active      another V Pizza company
  4. L25000541856  Possible  active      V PIZZA DURBIN, LLC
  5. Possible  inactive    a company with a similar name

--- v pizza lake buena vista, second run: status 200, 0.97 seconds
I read that as: the business name "V Pizza", the city "Lake Buena Vista"
5 companies on this list match at the level Possible. Check which one you mean before you open a report.
  1. L22000086098  Possible  active      V PIZZA LAKE BUENA VISTA LLC, ORLANDO
  (the same four companies under it, in the same order as in the first run)

--- the report of L22000086098, opened from the second run's list: status 200, 0.01 seconds
How this company was identified: from the business name "V Pizza", the city "Lake Buena Vista" · match level Possible
(name is similar (85/100); principal city on record is ORLANDO, and that spelling does not begin with the city you gave;
every word of the city you gave is in the company's name; ACTIVE) · chosen by the user from a shortlist.
4 other companies on the shortlist matched equally well.
```

| Search | The company the brief expects | Result |
|---|---|---|
| `v pizza orlando` | L22000086098 | ✅ First, rated Likely. On Nov 24 and Nov 25 it was not on the list |
| `v pizza lake buena vista`, first run | L22000086098 | ✅ First. The extraction read the city as "Buena Vista" and the street as "Lake" |
| `v pizza lake buena vista`, second run | L22000086098 | ✅ First. The extraction read the city as "Lake Buena Vista" |
| `8586 palm pwwy` | L22000086098 | ✅ The only company listed, as in leg D1. This leg did not change the address search |
| `v pizza durbin` | L25000541856 | 🟡 Fourth of five, as in leg D1. The extraction returned no city, so "durbin" never reached the search (question Q55) |

- ✅ **The two runs of one note were read two different ways, and both put the same company first.** That is what rule S14 is for. The brief warned that the second run might read the note the same way as the first and then show nothing new. It did not.
- ✅ The server's log of that run holds 21 lines. I searched it for "pizza", "palm", "pwwy", "durbin" and "buena", and for the access code, and found none.
- 🟡 **The right company is first and is still rated Possible** for `v pizza lake buena vista`, with the caution "This is only a POSSIBLE match", and the page says that 5 companies match at that level. Rule S4 keeps the levels as they were (question Q58).
- 🟡 For `v pizza orlando` the second company on the list is an inactive company in Orlando whose name holds the two typed words in another order. It ranks above the other V Pizza companies because it holds every typed word and its principal city is Orlando. That is rule S2 as written.
- 🟡 The report's line says "chosen by the user". In this check a command followed the link. Nobody chose.
- **Five requests before these were refused.** My first start of the app answered 503, "unavailable", five times. The app's log named the error kind, `AuthenticationError`, and nothing else. The cause is in "What is left for Andres", item 4. No extraction ran in those five requests, so I do not count them as live extraction calls, and I say so here so that the count can be checked.

### Check 7: the two backends of the evaluation now differ, by design

`WideTableBackend` in `evals/run.py` is leg C2's comparison baseline, and the brief says to leave its query as it is. So `--compare` no longer checks that two queries agree. It now counts how many searches rule S11 changes.

```
python -m evals.run --backend postgres --compare 200

compared 210 searches (10 test inputs, then 200 random company names): the second approach (company_search) against the app's search (company_search_names)
  the same companies in the same order, in the five returned and in the whole pool: 200 of 210
  differing: 10
    3 searches: different companies (5 companies against 5)
    7 searches: the same companies returned, and a different pool behind them (5 companies against 5)
  the second approach returned 5 companies for 105 searches, 1 to 4 for 105, and none for 0
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37
```

Rule S11 changes the five companies returned for 3 of these 210 searches, and only the pool behind them for 7 more. The command prints one line per differing search with its position in the list, and I have grouped those ten lines into two here. The docstring of `WideTableBackend` and the help of `--compare` now say that a difference is not a fault.

### Check 8: the tests

```
brew services stop postgresql@17      → Successfully stopped `postgresql@17` (label: sh.brew.postgresql@17)
pg_isready                            → /tmp:5432 - no response
pytest                                → 545 passed in 3.15s
ruff check src tests                  → All checks passed!
brew services start postgresql@17     → Successfully started `postgresql@17` (label: sh.brew.postgresql@17)
pg_isready                            → /tmp:5432 - accepting connections
```

✅ With the database server stopped, all 545 tests pass, so the suite needs no database. 530 existed before this leg and 15 are new.

**The tests the brief asks for by name**

| What the brief asks | The test | The input that makes it fail |
|---|---|---|
| Rule S11, failing on the old behavior | `test_the_first_step_keeps_the_names_that_hold_every_typed_word_before_the_nearest_names`, in `test_search.py` | The query's text is pinned word for word, because no offline test can run it. With the old `ORDER BY`, which began with the trigram distance, it fails. It also fails when `nearest()` stops sending the typed words or the list of legal endings. What the term does on real data is check 2 and check 3 |
| Rule S12, failing on the old behavior | `test_the_shortlist_shows_its_companies_in_rank_order_each_with_its_level` | Three invented companies whose rank order is Possible, Likely, Likely. The old sort by level put the two Likely ones first |
| Five companies whose levels come out Possible, Likely, Likely, Possible, Possible: the tie count reads the best level (Likely, two tied), and the sentence appears | `test_a_tie_reads_the_best_level_on_the_list_when_a_lower_level_is_shown_first` in `test_search.py`, run under the old order and under rule S2. `test_a_list_with_a_lower_level_above_a_higher_one_is_in_rank_order_and_says_so_once_under_the_list` in `test_web.py`. `test_the_terminal_lists_the_companies_in_rank_order_and_says_so_when_a_lower_level_comes_first` in `test_report_cli.py` | Five invented companies that give those levels under both orders. A count that read the first card's level would say three companies match at the level Possible. The page test fails unless the sentence, typed out in the test, is there exactly once, after the last company and before the search box, and fails if it shows on a list whose levels already go from best to worst. Since round 1 of the review it also has a list that reads Likely, Possible, Likely, where the first card is already the best |
| Rule S13, failing on the old behavior | `test_rank_orders_by_every_word_then_city_then_similarity_then_document_number` and `test_a_long_legal_name_that_holds_the_typed_trade_name_ranks_above_a_shorter_namesake_elsewhere` | Both now call `rank()` with no order, so they test the app's own. With `RANK_ORDER` put back to the old order, 5 tests fail |
| Rule S14, both ways the extraction read the note | `test_a_place_in_the_company_name_reaches_the_same_company_whichever_way_the_note_was_read`, run three times | Four invented pizza companies. The note is read with the place as the city, with the place left in the business name, and the third way a live call read it on Nov 25. The same company must be first each time. The test also sorts the candidates by rule S2 as it was before rule S14, and fails unless that puts another company first |
| The evidence line appears only when the city's words are in the name, and the level is the same with and without it | `test_the_reason_about_a_place_in_the_name_is_given_only_when_it_applies_and_never_changes_the_level` | The line, typed out in the test, must be among the reasons of the company whose name holds the place and of no other, and not at all when no city was given. The level of that company is worked out with the field on and off and must be the same |
| The match levels of rule S4 come out as before under the new order | `test_match_level_follows_the_three_rules` | The same four companies and five expected levels the test has had since leg C2. `rank()` is called with no order, so since rule S13 they are worked out under the new order. Two more companies show that holding every typed word, or having the place in the name, moves a company and never raises its level. With a place in the name made to raise a level, 4 tests fail |

Two more tests are worth naming. `test_the_page_is_in_rank_order_so_a_company_first_by_rank_is_first_on_the_page`, in `test_evals_run.py`, builds checked case 9's shape from invented companies and fails if the five are ever sorted by level again. `test_a_place_that_is_in_a_companys_name_puts_it_first_and_the_card_and_the_report_say_why`, in `test_web.py`, takes rule S14 through the web app: the company is first, its card and its report carry the new reason, and its level is still Possible.

✅ The deliberate breaks I made on the final code, each of which fails at least one test:

```
the every-word term taken out of the first step's query:              2 failed
nearest() no longer sends the typed words:                            2 failed
the five sorted by level again:                                       8 failed
the tie reading the first card's level:                               6 failed
the sentence's condition reading only the first card:                 2 failed
the sentence never handed to the page:                                1 failed
the sentence shown on every shortlist page:                           1 failed
the terminal not saying the sentence:                                 1 failed
RANK_ORDER put back to search version 1's order:                      9 failed
rule S2 reading the principal city alone (no rule S14):               6 failed
the new reason left out:                                              2 failed
the new reason given whenever a city was given:                       6 failed
a place in the name raising the match level:                          4 failed
the variant reading a city in the name:                               2 failed
legal endings counted as words of the name when a city is looked for: 1 failed
with every file put back:                                             545 passed in 2.75s
```

### Check 9: the live extraction calls

| What for | Calls |
|---|---|
| The five searches on the real app | 5 |
| **Total for leg D3** | **5 of the 10 that legs D3 and D4 share** |

✅ No checked case and no draft case was extracted again. `pipeline/seeds/extracted_inputs.csv` and `evals/draft_extracted.csv` were not written to. The results of the five live calls are reported here and saved nowhere. No test calls the API. The extraction prompt was not changed.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | Rule S11's term compares the name with its legal endings cut off, by sending Python's own pattern to Postgres as a value | The rule says "the same words that `holds_every_word()` compares", and that function leaves the legal endings out of both names. Sending the one pattern means there is one list of endings | Two engines now read one pattern, Python's and Postgres's. For this pattern they agree, and check 3 found 0 differences on 558,647 names. A later edit that used Python-only syntax would make them disagree, and the comment at that line says so |
| 2 | The term is written as a cheap test in front of the pattern match, joined with `CASE` | The first version missed the speed target, and the brief allows a second approach before the leg stops | The term is longer to read. Its comment explains each piece, and why the cheap test cannot change the answer |
| 3 | I counted the first speed run as a miss, although the Mac was very busy when it ran | I had chosen beforehand that the first run after a restart is the number. Throwing it out afterwards because of the machine would be choosing the number after seeing it | The report carries a failed measurement that was mostly the machine's fault. The back-to-back timings show how much was the query's |
| 4 | The terminal prints the sentence of rule S12 too | The rule names the shortlist page. `report.py` prints the same `Shortlist`, so since this leg its list is in rank order as well, and a list in that order with no explanation would be the same gap in another place | 🔴 The reading is mine. It adds two lines to `report.py`, a High-tier file. Question Q56 |
| 5 | The new reason reads "every word of the city you gave is in the company's name" | The rule says the line says the place is part of the company's name and gives no words. The comparison is whole words in any order, and the other reasons say "the city you gave" | 🔴 The words are mine. "Part of the name" would be shorter and would claim a little more than is compared. Question Q56 |
| 6 | The reason is given beside the line about the principal city, never in its place, and also when both apply | A contractor should see what the record says about the principal city whatever the name holds. Dropping that line would hide a fact | A company's reasons can be four lines long |
| 7 | A city in the name counts for rule S2 only. The unused variant of rule S2 and search version 1's order still read the principal city alone | Rule S14 amends step (2) of rule S2 and nothing else. My first version changed the variant too, and round 1 of the review pointed out that the brief does not ask for that, and that `--try-order s2-city-first` would then no longer score what leg D1 measured | The variant is no longer exactly "rule S2 with two parts swapped". The app uses neither it nor version 1's order |
| 8 | Legal endings are left out of the company's name when the city's words are looked for | Rule S2 leaves them out when it looks for the typed words, and a legal ending is not a place | A city that is spelled like a legal ending could never be found in a name. No Florida city is |
| 9 | The evaluation scores the companies on the page, and still keeps both places | Rule S12 says top-1 means first on the page. Keeping the place by rank as well means a later change that pulls the two apart again fails the comparison | For the name search the two columns now always hold the same number for the first five |
| 10 | `--try-order` gained `v1`, and `--before` is now described as "with no search by address" | After rule S13, trying `s2` compares the app with itself. After rule S11, `--before` no longer runs the name search of before Phase D. Rule S17 says to correct such text in the same commit | The headings of `--before`'s tables changed, and one test with them |
| 11 | I corrected rule S11's commit after making it, before anything was pushed | I had left the text of `--before` untrue in that commit, and rule S17 says the correction belongs in the same commit. I also corrected a wrong count in the message of rule S13's commit | Two commit ids changed. Nothing had been pushed, and nothing was force-pushed |
| 12 | I started the app for the live check with the shell's `ANTHROPIC_API_KEY` unset for that one command | The app is built to read its key from the project's secrets file with `load_dotenv()`. The shell's value stood in the way and the API rejects it | I worked around a broken setting on Andres's Mac and did not fix it. I read no key. Item 4 of "What is left for Andres" |
| 13 | I did not look into why one draft case stood lower after step 1, or which drafts moved | Rule S1: a draft may not shape the search | A real fault that only a draft shows would not be seen until Andres checks the drafts |
| 14 | In check 6 the companies a page showed are given by place, level and status, and only the two the brief names have their document numbers. I replaced this report's own commit once, before anything was pushed, to make it so | My first version listed every company's document number, as leg D1's report did. A check I ran before pushing found that one of those numbers is the expected answer of a draft case, and rule S1 keeps the drafts off GitHub. A later commit would have left the number in the history GitHub publishes | The live output is harder to check against the app. One commit id changed. Nothing had been pushed, and nothing was force-pushed. 🟡 Leg D1's report, already on `main`, lists document numbers the same way, and I did not check them against the drafts |

---

## 4. What I couldn't verify, and open questions for Andres

### What I couldn't verify

1. 🔴 **That the terminal should print the sentence of rule S12** (decision 4). The rule names the page.
2. 🔴 **That the wording of the new reason is what Andres wants** (decision 5).
3. 🟡 **Why the final code measured 599 milliseconds where `main` measured 456** (check 5). The query alone is as fast as before. My explanation, that the 200 full rows it then reads are other rows, is not proven.
4. 🟡 **The speed on a quiet machine, and on a host.** Every timing is from the Mac, which was busy.
5. 🟡 **How often a real search shows a lower level above a higher one** (check 4). The count of 3 in 200 is on full legal names with no city.
6. 🟡 **That rule S2 is better for searches the 13 checked cases do not cover.** The gate proves that no checked case got worse. It cannot prove more than that with 13 cases, 3 of which are the same restaurant.
7. 🟡 **What the extraction step returns for a real contractor's note.** It read one note two ways again today, and it dropped "durbin" again (question Q55).
8. 🟡 **The evaluation's Snowflake backend** (question Q57). It was not run, because this phase uses no Snowflake. Its pool is built for the old order.
9. 🟡 **The shortlist page on a phone with the new sentence.** No screenshot was made in this leg. The sentence is one paragraph of text under the list, with the page's ordinary style.
10. 🟡 **Where the shell's `ANTHROPIC_API_KEY` comes from, and whether it is an old key.** I did not look (decision 12).
11. 🟡 **The cost of an extraction call.** The figure of $0.0004 is the plan's.
12. 🟡 **That Postgres and Python will keep reading the legal-endings pattern the same way** (decision 1). Check 3 proves it for today's pattern on 558,647 names.
13. 🟡 **What rule S14 should do when the place is both in the typed name and read as the city** (question Q59). Then every company that holds the typed words also agrees on the city, and the principal city stops telling them apart. A reviewer found this by reading the code. On today's data no checked case changes: case 5, which has this shape, has one candidate.
14. 🟡 **Whether three sentences should change now that a Possible company can carry the new reason** (question Q58): the caution on a Possible card, the sentence of rule S12, and the brackets in a report's line. All three understate.
15. 🟡 **Whether leg D1's report, already on `main`, holds a draft case's expected document number** (decision 14). It lists the companies of its live searches by document number, as my first version of this report did. I did not check it against the drafts, because that file is merged and is not this leg's to change.

### Questions added to `docs/open_questions.md`

| # | The question, in short |
|---|---|
| Q46, Q50, Q51, Q52 | Each row now says what was built for it and that it passed the gate |
| Q55 | The extraction step can drop a place altogether. Should the prompt keep it? |
| Q59 | When the place is in the typed name and also comes back as the city, should it still count as found in the company's name? |
| Q56 | Is the wording of the new reason right, and should the terminal print the sentence of rule S12? |
| Q57 | The evaluation's Snowflake backend no longer reproduces the app. What should it do? |
| Q58 | The right company is first and its level did not rise. Should a level take the new signals into account? |

### The review

- **Tier:** High. The leg changes `src/datum/report.py`, which is a High path in `REVIEW.md`, and it adds a reason that a report shows in its line about how the company was identified, which is wording on a report. The brief names both legs D3 and D4 as High.
- **Depth:** Deep. In round 1, three `reviewer` subagents ran in parallel, each with one of the hunts the brief sets for Phase D, and a fourth then checked every finding against the code. A security review ran alongside, because `src/` changed.
- **Rounds:** three, which is the most the rules allow. Round 3 found nothing.
- **Findings over the rounds:** 13 over the three rounds. Round 1 had 7, of which 1 was posted as Important and judged a Nit by the fourth reviewer. Round 2 had 3 Important and 3 Nit, all in the Human review section and none in the code. Round 3 had none. Eleven are fixed, and two are closed with a reason because they are questions for Andres (Q58 and Q59).
- **What was not reviewed:** the commits after round 3, which change this report and add the pull request's row to `docs/review_log.csv`, and no code. That includes decision 14, item 15 of "What I couldn't verify" and the clause about it in the Human review section, all written after round 3. Reviewers are told to skip leg reports, so this report's own text was checked only where the Human review section repeats it.

**Round 1** (three reviewers, then a fourth that checked their findings, on the leg's first six commits, and the security review).

The three reviewers posted 7 findings: 1 Important and 6 Nit. The fourth reviewer confirmed all 7 and dropped none. It judged the one posted as Important to be a Nit, because the code is right today and the gap was in the tests. I fixed it as if it were Important. Every finding was answered.

| Finding | Tag | Answer |
|---|---|---|
| No test had a list whose first company already has the best level and which is still out of order further down, such as Likely, Possible, Likely. A rule for the new sentence that looked only at the first card passed every test, and it would have dropped the sentence from such a list | Posted as Important, judged a Nit by the fourth reviewer | Fixed. Such a list is tested in `shortlist()` and on the page, and that wrong rule now fails 2 tests |
| The unused variant of rule S2, `by_city_then_words`, had been made to read a city in the company's name. Rule S14 amends step (2) of rule S2 only, and `--try-order s2-city-first` would no longer score what leg D1 measured | Nit | Fixed. The variant reads the principal city alone again, and a test fails if it does not |
| When the place is in the typed business name and also comes back as the city, as in checked case 5's saved extraction, every company that holds the typed words also agrees on the city, so the principal city stops breaking ties | Nit. The reviewer was not sure of it, and called it a question for Andres | Closed with a reason: the code does what rule S14 says, and no checked case changes on today's data. It is question Q59, and a test pins what the code does so that a change is a decision |
| Three assertions could not fail once the line before them had passed: two that re-read a query text already pinned word for word, and a loop over a sentence already pinned word for word. A loop over rank orders in the test of the match levels could not fail on any order | Nit | Fixed. The three are removed, and the loop is back to the two orders it had before this leg |
| A Possible card can now carry the new reason, and three sentences then sit oddly beside it: the caution "nothing else confirms it is the company you mean", the sentence of rule S12, and the brackets of a report's line "match level Possible (...)" | Nit. The reviewer was not sure of it | Closed with a reason: all three understate, the second is the rule's own sentence, and changing any of them needs a ruling. Question Q58 now quotes all three |
| A comment in `wording.py` said eight of the nine reasons are behind a match level. Five are | Nit, and partly Pre-existing: the older comment said the same | Fixed, in the comment and in the docstring of `evidence()` |
| One invented company in a test, used to show a name that does not hold the typed words, had a name that could be a real company's | Nit. The reviewer could not check it | Fixed: it has an invented stem now. I also looked up the 17 company names this leg invented for its tests: none is the exact name of a registered company |

The security review read the leg's diff and traced a typed note to Postgres and to the pages. ✅ It reported no vulnerability it was at least 80% sure of: every typed value, the new list of typed words included, reaches Postgres as a parameter; the new sentence and the new reason are fixed texts that the templates escape; the access-code gate was not touched; and nothing typed reaches a log, an address or a file. It left four side notes.

| Side note | What was done |
|---|---|
| The list of legal endings is sent to Postgres as a pattern that Postgres runs. It is safe because it is a constant, and it must never become something a caller supplies | A comment at that line now says so |
| Two engines, Python's and Postgres's, now read that one pattern. A later edit with Python-only syntax would make the database's pool and Python's rule disagree without any error | The same comment says which syntax is safe. Check 3 compared the two on 558,647 real names and found no difference |
| `WideTableBackend` in `evals/run.py` inherits `nearest()`, so it now receives two values its query does not name. The reviewer believed the driver ignores them and had not run it | Confirmed by running it: `python -m evals.run --backend postgres --compare 200` uses that backend and ran to the end (check 7) |
| The new reason confirms a fact about the extracted city, and it is kept in memory for up to an hour with the other reasons of a shortlist | Nothing to change. It travels the path the other reasons already took (question Q44), and the extracted city was already shown on the page |

✅ After the fixes I made fifteen deliberate breaks on the final code, one at a time, and each fails at least one test. They are listed in check 8.

**Round 2** (one reviewer on the two commits that answered round 1, doing all three hunts on that diff, then reading the Human review section and trying the three questions on it).

**3 Important and 3 Nit, all six in the Human review section. Nothing in the code.**

- ✅ The reviewer ran the tests and got 545 passed. It then broke the code in a copy of its own, and the new tests caught each break: the variant made to read a city in the name again (2 tests failed), and the new sentence's condition made to read only the first card (2 tests failed).
- ✅ It confirmed that the assertions removed in round 1 could not fail, that the query's text and the new reason are still compared word for word, and that the saved extraction of checked case 5 is what question Q59 says it is.
- ✅ All three questions of section 6 could be answered from the Human review section alone.

| Finding | Tag | Answer |
|---|---|---|
| The section said the count of pages with a lower level above a higher one, 5 of 210, "is on full legal names". Two of the five are checked cases 6 and 9, which are short notes. Only the 3 among the 200 random names come from full legal names | Important | Fixed in the section, which now gives both numbers |
| The section spoke of "the sentence about the list's order" and "the caution on a Possible card" and quoted neither, so two decisions could not be made from the section alone | Important | Fixed. The section quotes rule S12's sentence and says when it shows, and quotes the caution where question Q58 is raised |
| The section said High asks Andres to "read this section and the diff". `REVIEW.md` says he reads the report and the diff | Important. The reviewer was not sure of it, because the brief means the section to work without the leg report | Fixed. The sentence now says what `REVIEW.md` says |
| Several terms were not explained at first use, and "2,861st of 10,062" did not say 10,062 of what | Nit | Fixed in the section |
| "If you open the code" named four places, and the rule allows three | Nit | Fixed: three places |
| The decision about the evaluation's Snowflake backend did not say what the choices are, and the facts behind two decisions sat only in a lumped sentence | Nit | Fixed. Each decision now says what the other choice would change, and those two facts have bullets of their own |

No code changed in answer to round 2. The six fixes are all in the text that opens the pull request.

**Round 3** (one reviewer on the corrected Human review section, and the three questions again). No code had changed since round 2.

**0 findings: nothing to fix.**

- ✅ The reviewer found all six fixes of round 2 in place, and every sentence the section quotes from the app word for word what `src/datum/wording.py` holds.
- ✅ It found every fact of the section in the diff or in this report, all 14 items of "What I couldn't verify" under "What is not proven", and each decision in line with what questions Q55 to Q59 ask.
- ✅ All three questions could again be answered from the section alone.

No Important finding is open. The commits made after round 3 change this report and add the pull request's row to `docs/review_log.csv`. They change no code, and no round read them, which the Human review section says. One thing in them is new and was read by no reviewer: after round 3 I found a draft case's expected document number in this report's live output and took it out (decision 14), and I added item 15 to "What I couldn't verify" and one clause about it to the Human review section.

---

## 5. Cost

| Item | Rate | Units | Cost |
|---|---|---|---|
| Snowflake | About $2 a credit | 0 credits. The leg made no call to Snowflake, as the brief requires | $0 |
| Claude API, the extraction step | 🟡 About $0.0004 a call (the plan's figure) | 5 calls | 🟡 About $0.002, a fifth of a cent |
| Postgres and Uvicorn on the Mac | Free | | $0 |

Legs D3 and D4 share 10 live extraction calls, and leg D3 used **5**. No hosted account, hosted database or paid service was created.

---

## 6. Three questions Andres should be able to answer

1. The name search works in two steps. Leg D1 built a new order for the second step, and it could not put the right company first for `v pizza orlando`. What did this leg change in the first step, and why did the fix have to be there?
2. Rule S2 was built in leg D1 and left switched off, because it moved the right company of one checked case from first to second on the page. This leg switched it on. What changed about the page that made that safe, and what had to be measured before the switch was kept?
3. For `v pizza lake buena vista` the right company is now first, and the page still calls it a Possible match. Why did its place change and its level not, and what does the new line in its reasons say?

**Answers, to check yourself.** (1) Step 1, in Postgres, lets every name pass that is close to the typed name and keeps 200 of them. Step 2, `rank()` in Python, puts those 200 in order. Step 1 used to keep the 200 names nearest to the typed name as a whole, and a long legal name is far from a short trade name: for "V PIZZA", 10,062 names passed and the right company stood 2,861st, so step 2 never saw it. This leg added one term to step 1's `ORDER BY`, so that the names that hold every typed word are kept first and the nearest names after them (rule S11). The fix had to be in step 1 because the second step can only order what the first one hands it. This pattern is called retrieve-then-rerank. (2) The page used to take the best five by rank and re-sort them by match level, so a company with exactly the typed name, rated Strong, could be shown above the right company although it ranked below it. That is what happened to case 9 under rule S2. Rule S12 makes the page show the five in rank order, each with its level, so first by rank is first on the page. The gate, rule S17, then had to be measured: one script ran the search as it is on `main` at `051a928` and the search after each step against the same database, and a step was kept only if no checked case was worse than on `main` or than after the step before, by rank or on the page. Every step passed. (3) Its place changed because of rule S14: the extraction step read "Lake Buena Vista" as the city, the company's principal city is Orlando, and the rule now also counts the city as agreeing when every word of it is in the company's name. That counts for the order only. The level is still worked out from the name and the principal city (rule S4): the name is similar and not the same, and the principal city does not agree, so the level is Possible. The new line says "every word of the city you gave is in the company's name", and it stands beside the line that says the principal city on record is Orlando.

## 7. After the pull request opened: the deep review of Nov 26, 2026, and its fix

This section was added after the pull request opened. Sections 1 to 6 describe the leg as it was when its three review rounds ended, and they are left as they were, apart from the count of tests in the short version at the top.

### What the deep review found

On the night of Nov 26 a deep review read this pull request with one fresh-context reviewer. Its report is `docs/reviews/2026-11-26_deep_review.md`, on the branch `docs/deep-review-nov26`. It found one Important problem here. `name_key()` turns "&" into a space, so a registered "A&B ROOFING LLC" can never hold a typed AND, and a registered name never holds a THE that a contractor types and the name lacks. Since rule S13, holding every typed word comes before the city and the similarity. So for a typed "A and B Roofing" in Tampa, a company in Ocala whose name spells out AND came first, and the company in Tampa came second.

### The fix, and Andres's answer

- **Commit `cc39913`.** `typed_words()` and `FILLER_WORDS` in `src/datum/search.py` leave AND and THE out of the words the every-word test looks for. The same words go to `holds_every_word()` and to the `words` value that step 1's query reads, so the two cannot drift apart. The nearness to the typed name, the key that step 1's `WHERE` and its trigram distance read, still holds every typed word. A typed name made only of those two words keeps them, as a name that is only a legal ending keeps its word. The new test is `test_a_typed_and_or_the_is_not_a_word_the_company_name_must_hold`. On the code at `a038b4f` its two pools put the wrong company first, and the fix puts the company meant first.
- **Commit `ae4fcdd`.** Andres answered on Nov 26, 2026, recorded as question Q63: keep it. It also covers a registered name with no "&" at all, such as A B ROOFING, and a THE that a contractor types and the registered name lacks.
- **Commit `17e9a19`.** The High-tier review of the fix found the cost of that answer, recorded as question Q64 for Andres, with a test that pins today's order. Its detail is under "The review of the fix" below.

### The checks, run again

The checks ran on the branch at `ae4fcdd`, whose search is the search at `cc39913`. None of them called the Claude API, and none used Snowflake.

**Check 1, the evaluation.** The scores are the leg's own: 10 of the 13 checked cases have the right company first, 12 have it among the first five, and 2 are wrong matches.

```
python -m evals.run --backend postgres

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

**Check 2, the gate of rule S17, with the fix as one more step after `a038b4f`.** The script is the one legs D3 and D4 used, which runs every checked case through the search as each commit has it. The column for `main` at `051a928` comes from results kept before leg D4 rebuilt the address table, as in leg D4's check 2, because the search at `051a928` cannot be run against the table as it is now.

```
python gate.py --saved main_051a928=<the results kept before the rebuild> d3_head=a038b4f nightly_fix=cc39913

checked cases: 13   draft cases: 16
  main_051a928 = src/datum/search.py at 051a928, results kept in a file before the address table was rebuilt
  d3_head = src/datum/search.py at a038b4f
  nightly_fix = src/datum/search.py at cc39913

each cell: the expected company's place by rank among the candidates / its place on the page
case  main_051a928                d3_head                     nightly_fix                 
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
            main_051a928                d3_head                     nightly_fix                 
top-1         8                           10                          10                          
recall@5      10                          12                          12                          
wrong_match   4                           2                           2                           
first on page 8                           10                          10                          

the gate of rule S17 (a checked case is worse when its company drops by rank, drops on the page, or leaves the first five, or when a note that should be asked about gets a company):
  d3_head: worse than main_051a928: none   better than main_051a928: [11, 12]   -> passes
  nightly_fix: worse than main_051a928: none   worse than d3_head: none   better than main_051a928: [11, 12]   -> passes

draft cases, counts only (not checked by Andres, and so counted in no decision):
  d3_head against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         5           0       1
    name_and_street              5         2           0       3
    ALL                         16         7           0       9
  nightly_fix against main_051a928:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         5           0       1
    name_and_street              5         2           0       3
    ALL                         16         7           0       9
  nightly_fix against d3_head:
    group                    cases  moved up  moved down  stayed
    address_only                 5         0           0       5
    brand_and_city               6         0           0       6
    name_and_street              5         0           0       5
    ALL                         16         0           0      16

draft cases, scored on the first five on the page (top-1 / recall@5 / wrong_match), counts only:
  main_051a928              3 / 7 / 12
  d3_head                   8 / 12 / 7
  nightly_fix               8 / 12 / 7
```

- ✅ The fix passes. No checked case is worse than on `main` or than at `a038b4f`, and no draft case moved against `a038b4f`.

**Check 3, rule S11 in the query against `holds_every_word()` in Python.** It is leg D3's script with one change: the values it sends to the query's term are recorded from the app's own `PostgresBackend.nearest()`, not rebuilt, because the fix changed them. The line A is check 4's count, which did not change.

```
the term compared with Python: (case when string_to_array(name_key, ' ') @> %(words)s::text[] then string_to_array(regexp_replace(name_key, %(suffixes)s, ''), ' ') @> %(words)s::text[] else false end)
210 searches: 10 specific checked cases, then 200 random company names (fingerprint 29e32d4a94b0a803614ddf7256322a37)
A. pages that show a lower level above a higher one: 5 of 210 (3 of the 200 random names, 2 of the 10 checked cases); pages with at least one company: 210
B. 210 searches (12 of them type AND or THE), 558,647 names that pass the first step's WHERE, 3,876 of them hold every typed word by the SQL term: the SQL term and holds_every_word() differ for 0
```

- ✅ The query's term and the Python rule still agree on every one of the 558,647 names.
- One more count, from a scratch script: the 12 searches that type AND or THE are all among the 200 random company names, and the search before the fix and the fix keep the same 200 candidates and show the same page for all 12. They are full legal names, which spell the word out.

**Check 5, the speed of the name search**, as the first run after a Postgres restart, the way section 2 measured it.

```
brew services restart postgresql@17
python -m evals.run --backend postgres --latency 200
22:19  load averages: 4.03 4.87 5.05
latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 129 ms   p95 608 ms   slowest 2498 ms
  searches over 1 second: 5 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37

(after another restart)
22:20  load averages: 3.37 4.55 4.91
latency over 210 searches (10 test inputs + 200 random company names, pool of 200):
  p50 122 ms   p95 599 ms   slowest 2449 ms
  searches over 1 second: 3 of 210
  fingerprint of the random names: 29e32d4a94b0a803614ddf7256322a37
```

| What was timed | p50 | p95 | Slowest | Searches over 1 second | Target: p95 under 1 second |
|---|---|---|---|---|---|
| The leg's final code, first run after a restart | 134 ms | 599 ms | 3,565 ms | 4 of 210 | ✅ |
| **With the fix, first run after a restart** | 129 ms | **608 ms** | 2,498 ms | 5 of 210 | ✅ |
| With the fix, first run after another restart | 122 ms | 599 ms | 2,449 ms | 3 of 210 | ✅ |

**The tests.** With the database server stopped: `pytest` gave **547 passed** in 3.61 seconds at `e972020`, and `ruff check src tests evals` passed. The leg ended with 545, and the review added two: the fix's test and the test that pins question Q64's order.

### The review of the fix

The fix's review was High tier, in three rounds.

- **Round 1.** Three reviewers ran in parallel, each hunting one thing: a wrong company first or a sentence that claims too much, a person's data or a secret, and a test that cannot fail. A fourth then checked every finding against the code. For this pull request it confirmed two findings, and neither is Important.
  - **A call for Andres, now question Q64.** With AND and THE left out, a near name that lacks the typed word joins the exact name's group, and with no city the similarity decides, which counts the legal ending. For "Lords of the Lawn", LORDS OF LAWN (Possible) comes before LORDS OF THE LAWN L.L.C. (Strong), and for "Gator Heating and Air", GATOR HEATING & AIR INC (Possible) comes before GATOR HEATING AND AIR CORPORATION (Strong). No sentence becomes false, and the page says the list is in search order. The fourth reviewer found that the order cannot change without a new matching rule. The one narrow rule it found, an exact name first after the city but only when AND or THE was typed, would need the gate. It is answered by the Q64 row in `docs/open_questions.md` and by `test_a_typed_the_or_and_no_longer_keeps_an_exact_name_above_a_near_name_that_lacks_it`, which pins today's order (commits `17e9a19` and `e972020`).
  - **Pre-existing.** Step 1's `WHERE` still compares the whole typed name, THE included, so a short name can miss the candidates: in Postgres, "THE ACME GROUP" against ACME GROUP LLC scores 0.733, under the threshold of 0.75. It is recorded in Q64, and the new test's THE case holds in the ordering step only.
  - A security review of the new lines in `src/` found no vulnerability. The new words reach Postgres only as a bound value, and no pattern is built from what was typed.
- **Round 2.** One reviewer read the new commits, the Human review section, which is in the pull request's text, and the three questions. For this pull request it found two Important problems in the section, a bold sentence that said a typed "and" or "the" no longer counts against the right company anywhere, while step 1 still reads THE, and test counts given "with Postgres stopped" that had been measured with it running. It also found a Nit: the test that pins Q64 held only the THE example. All three are fixed. All three questions were answerable from the section.
- **Round 3.** It had one reviewer on the corrections. In pull request 30's section it found one Important problem, a count of merges ("two merges") that round 3's own merge had made stale, and one Nit, a sentence that read as if the wording test covered the collections of strings in `wording.py`. Both are corrected, and as three rounds is the most `REVIEW.md` allows, no round read those two corrections. It found nothing more in this pull request's section.

### What the fix does not prove

- 🟡 It changes nothing the evaluation can see. No checked case's name search types AND or THE (checked case 10's note holds "the", but the search asks about that note and runs no name search), and the 12 searches of the speed check that do keep their results, so its benefit rests on the new test's invented companies.
- 🟡 Question Q64: a near name that lacks the typed word now joins the exact name's group, and with no city the similarity decides. For "Lords of the Lawn", LORDS OF LAWN, rated Possible, comes before LORDS OF THE LAWN L.L.C., rated Strong. No sentence becomes false, and the page says the list is in search order.
- 🟡 Step 1's `WHERE` still compares the whole typed name, THE included. In Postgres, "THE ACME GROUP" against ACME GROUP LLC scores 0.733, under the threshold of 0.75, so for a short name the company meant can miss the 200 candidates, and the new test's THE case holds in the ordering step only.
- 🟡 The timings come from a Mac with a load average between 3 and 5.
