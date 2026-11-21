# Leg C2: the Postgres copy and the search

Branch `leg/c2-postgres-search` (stacked on `leg/c1-serving-marts`) · pull request PR_LINK · run on Nov 20 and 21, 2026 · risk tier **Medium** · status: **stopped at one check. Everything was built and every other check passes, and the search misses its speed target under both approaches tried. The brief says to record the numbers and stop the leg in that case, and so legs C3 and C4 were not started.**

**The short version**

- **The speed target is not met, and that is why the leg stops.** The target is a p95 under 1 second. The p95 is the time that 95 of every 100 searches beat. The first approach has a p95 of **11,212 milliseconds**, which is over 11 seconds. The second approach, which is the one in the code, has a p50 of **181 milliseconds** and a p95 of **1,229 milliseconds**. That is 0.23 seconds over, and I did not loosen the target.
- Everything else the leg asks for is done and checked.
  - The four marts are in Postgres, and every table's row count equals Snowflake's: **12,988,435** companies, **9,950** shown flags, **0** possible matches and **5** source rows.
  - No hidden record left Snowflake. **14,263** hidden flags and all **9,651** possible matches stayed behind.
  - The search scores at least as well as Snowflake on the test set: top-1 **7** of 10 against 6, recall at 5 **9** against 9, and wrong_match **2** against 3.
  - The offline tests pass with Postgres stopped: 255 passed.
- One thing happened that you should know about. At 00:32 Eastern time on Nov 21, something outside this run switched the working folder to the branch `main`, and my next four commits landed on local `main`. Nothing was pushed. I moved the commits to this branch and set local `main` back to `origin/main`. Section 4 has the details.

**What is left for Andres**

1. **Decide what to do about the speed target.** This is the one decision that holds up the rest of Phase C. Section 4 lays out three options. I recommend the first one, a narrower search table, measured the same way as the two approaches in this report.
2. Read section 3, which holds the calls I made where the brief did not say.
3. Tell me to go on with legs C3 and C4 once the speed question is settled. They read this leg's search module and its Postgres tables, and both are ready.

---

## 1. What I built

### The picture

```
 Snowflake marts                                  Postgres on the Mac (database datum_dev)
   company_search ─────────┐
   company_flags (shown) ──┤  script 23           load_postgres.py
   possible matches (0) ───┼──────────▶ data/export/*.csv.gz ──────────▶ four tables, swapped in one transaction
   source_coverage ────────┘  + a counts file                            + a trigram index on company_search.name_key
                                                                              │
                                                             search.py:  RETRIEVE a pool by trigram (Postgres)
                                                                         RERANK it by Jaro-Winkler (plain Python)
                                                                              │
                                                             evals/run.py scores it against the test set,
                                                             on Postgres and on Snowflake
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| Postgres 17 | A database server, installed with Homebrew and running on the Mac only. The database is `datum_dev`, with the `pg_trgm` extension turned on | Decision d18: lookups read Postgres, and builds run in Snowflake |
| `snowflake/23_export_marts.sql` | Copies the four marts out of Snowflake as compressed CSV (comma-separated values) files, plus a fifth small file holding each table's row count. The two flag marts are filtered to rows with `is_shown` true | Working rule W9: a hidden record never leaves Snowflake |
| `src/datum/load_postgres.py` | Checks the files, loads each table under a temporary name, counts the rows, builds the indexes, and then swaps all four tables in with one transaction | A load that fails halfway must never leave the app reading half a table |
| `src/datum/search.py` | The search. A `SearchBackend` brings back a pool of companies whose names are near the typed one, and plain Python ranks the pool by the rules of search version 1. It also holds the match level, the evidence and the tie count | `CLAUDE.md` rule 1: scoring is plain code. The backend is an interface, so tests use a fake and need no database |
| `tests/fixtures/search/jarowinkler_pairs.csv` | 61 pairs of texts with the score Snowflake's `JAROWINKLER_SIMILARITY` gives each | Proves the plain-Python Jaro-Winkler function gives Snowflake's scores |
| `evals/run.py` | One command that scores the search on the 10-case test set, on either backend, and can time it | The brief's comparison of the two backends, and the p50 and p95 |
| `docs/adr/0001-serving-layer.md` | A one-page record of decision d18, with the cost line | The brief asks for it |

### How the search works

```
 "ferguson ac boynton beach"
        │  extraction (not in this leg; the evaluation reads the saved fields)
        ▼
 business name "Ferguson Air Conditioning", city "Boynton Beach"
        │  name_key(): capitals, punctuation to spaces  →  FERGUSON AIR CONDITIONING
        ▼
 STEP 1  RETRIEVE   Postgres, trigram index: up to 200 companies whose name CONTAINS
                    something close to the typed name (word similarity at 0.75 or more)
        ▼
 STEP 2  RERANK     plain Python: Jaro-Winkler similarity, then a city match, then the
                    document number. The best five are the answer the evaluation scores
        ▼
 SHORTLIST          each candidate gets a level (Strong, Likely, Possible) and its evidence,
                    and the count of candidates that tie at the top level is kept (rule W7)
```

A trigram is a run of three characters, and two names are near when they share many trigrams. Jaro-Winkler is a different measure of how alike two texts are, which gives extra weight to a shared beginning. Step 1 is fast and rough, and step 2 is careful and only has 200 names to look at. This two-step pattern is called retrieve-then-rerank.

### Files

| File | New or changed |
|---|---|
| `snowflake/23_export_marts.sql` | New |
| `src/datum/load_postgres.py`, `tests/test_load_postgres.py` | New. 10 tests |
| `src/datum/search.py`, `tests/test_search.py`, `tests/fixtures/search/` | New. 92 tests, 61 of them one per fixture pair |
| `evals/run.py`, `tests/test_evals_run.py` | New. 12 tests |
| `docs/adr/0001-serving-layer.md` | New |
| `requirements.txt` | Changed: `psycopg` 3.3.9 and `psycopg-binary` 3.3.9, each with a comment (ruling R24) |
| `pytest.ini` | Changed: the repo root is on the import path, so a test can import `evals.run` |

`src/datum/report.py` was not touched, as the brief requires. In Snowflake the leg added one file format and one stage in `datum.dev_marts`, and nothing existing was changed.

### What was installed on the Mac

| What | How | Note |
|---|---|---|
| PostgreSQL 17.12 | `brew install postgresql@17`, then `brew services start postgresql@17` | Free and local. It listens on `localhost` only and needs no password |
| The database `datum_dev` with `pg_trgm` 1.6 | `createdb datum_dev`, then `psql datum_dev -c "CREATE EXTENSION pg_trgm;"` | |
| `psycopg` 3.3.9 | `pip install "psycopg[binary]"` in the project's virtual environment | The Postgres driver for Python |

Homebrew upgraded its own copies of Python 3.12 and OpenSSL while it installed Postgres. The project does not use those copies: its virtual environment is built on the Python from python.org, and `pytest`, `dbt` and `snow` all ran afterwards.

Homebrew does not put `psql` on the command path for this version. To use it from the VS Code terminal, type the full path, `/opt/homebrew/opt/postgresql@17/bin/psql datum_dev`. The loader and the search do not need `psql`.

---

## 2. Checks

### Check 1: row counts in Snowflake and in Postgres, side by side

```
snow sql -c datum -f snowflake/23_export_marts.sql        (the last statement)

| TABLE_NAME               | ROWS_IN_MART | EXPORTED | HELD_BACK |
| company_search           | 12988435     | 12988435 | 0         |
| company_flags            | 24213        | 9950     | 14263     |
| company_possible_matches | 9651         | 0        | 9651      |
| source_coverage          | 5            | 5        | 0         |

python src/datum/load_postgres.py

table                       Snowflake exported   Postgres loaded
company_search                      12,988,435        12,988,435
company_flags                            9,950             9,950
company_possible_matches                     0                 0
source_coverage                              5                 5
```

| Table | In the Snowflake mart | Exported | In Postgres | Held back in Snowflake |
|---|---|---|---|---|
| `company_search` | 12,988,435 | 12,988,435 | 12,988,435 | 0 |
| `company_flags` | 24,213 | 9,950 | 9,950 | 14,263 hidden flags (Duval and DBPR discipline) |
| `company_possible_matches` | 9,651 | 0 | 0 | 9,651, which is all of them (rule W3) |
| `source_coverage` | 5 | 5 | 5 | 0 |

- ✅ Every table's count in Postgres equals the count Snowflake exported. The loader checks this itself and refuses to swap the tables in when one differs.
- ✅ Before loading, the eight company files were counted by hand: 12,988,443 lines, which is 12,988,435 rows plus 8 header lines.

### Check 2: the evaluation on both backends

```
python -m evals.run --backend postgres

case  group                 expected        answer          top-1  top-5  wrong_match
   1  legal_name_variant    P98000033661    P98000033661    yes    yes    no
   2  legal_name_variant    L26000514010    L26000514010    yes    yes    no
   3  legal_name_variant    P18000005972    P96000014879    no     yes    YES
   4  legal_name_variant    L14000186157    L14000186157    yes    yes    no
   5  legal_name_variant    L26000480461    L26000480461    yes    yes    no
   6  legal_name_variant    P02000008536    P02000008536    yes    yes    no
   7  legal_name_variant    L22000096579    NEEDS_MORE_INFO no     no     no
   8  legal_name_variant    L26000402102    L09000056609    no     yes    YES
   9  real_world_reference  P24771          P24771          yes    yes    no
  10  real_world_reference  NEEDS_MORE_INFO NEEDS_MORE_INFO yes    yes    no

group                    cases  top-1  recall@5  wrong_match
legal_name_variant           8      5         7            2
real_world_reference         2      2         2            0
ALL                         10      7         9            2

python -m evals.run --backend snowflake

   9  real_world_reference  P24771          688030          no     yes    YES
   (the other nine lines are the same as on Postgres)

group                    cases  top-1  recall@5  wrong_match
legal_name_variant           8      5         7            2
real_world_reference         2      1         2            1
ALL                         10      6         9            3
```

| Measure | Postgres | Snowflake | The brief's rule | Result |
|---|---|---|---|---|
| Top-1: the first answer is the right company | 7 of 10 | 6 of 10 | Postgres at least as good | ✅ |
| Recall at 5: the right company is in the first five | 9 of 10 | 9 of 10 | Postgres at least as good | ✅ |
| `wrong_match`: the search answered, and with the wrong company | 2 | 3 | Postgres no more than Snowflake | ✅ |

**The one case that differs is case 9** (`cinemark durbin park`). Snowflake ranks every company in Florida by Jaro-Winkler, and the company it puts first is not the expected one, which comes second to fifth. Postgres first keeps only the companies whose names contain something close to CINEMARK, and among those the expected company ranks first. 🟡 I did not look at which company Snowflake put first, beyond its document number.

Three things are worth knowing about these numbers.

- Cases 3 and 8 are a wrong match on both backends. The right company is in the first five and another company outranks it. That is the search rule's doing, not the database's, and this leg does not change the rule.
- Case 7 (`realy good beer`) is a miss on both, and it is not a wrong match. The saved extraction marked the note as not specific, so the search asked for more and answered with no company.
- The Snowflake run was repeated once, after the review changed how its pool is chosen (section 4), and it gave the same ten lines.

### Check 3: p50 and p95 search time. **This is the check that fails**

The measurement is the one the brief defines: the 8 specific test inputs plus 200 company names drawn at random, 208 searches in all, each timed from the typed name to the reranked answer. The 200 names are the same on every run, because the draw uses a fixed seed. No drawn name is printed.

```
python -m evals.run --backend postgres --latency 200 --retrieve plain      (approach 1)
latency over 208 searches (8 test inputs + 200 random company names, pool of 200):
  p50 5101 ms   p95 11212 ms   slowest 17503 ms
  searches over 1 second: 201 of 208

python -m evals.run --backend postgres --latency 200                       (approach 2, first run)
latency over 208 searches (8 test inputs + 200 random company names, pool of 200):
  p50 181 ms   p95 1229 ms   slowest 4438 ms

python -m evals.run --backend postgres --latency 200                       (approach 2, the same 208 inputs again)
  p50 173 ms   p95 766 ms   slowest 3742 ms
  searches over 1 second: 6 of 208
```

| Approach | How step 1 picks its pool | p50 | p95 | Target: p95 under 1 second |
|---|---|---|---|---|
| 1. Plain trigram similarity, threshold 0.3 | Compares the two whole names. This is the query the plan of Oct 30 wrote down | 5,101 ms | **11,212 ms** | ❌ missed by more than 10 seconds |
| 2. Word similarity, threshold 0.75, legal suffix left out of the lookup | Asks whether some stretch of the registered name is close to the typed name. This is the approach in the code | 181 ms | **1,229 ms** | ❌ missed by 229 ms |
| 2 again, the same 208 inputs a second time | The same | 173 ms | 766 ms | Not a fair number: see below |

**Why the second run of approach 2 does not count.** It searched the same 208 names as the first run, a minute later, so the parts of the table those names need were already in memory. A contractor's search is a name nobody searched a minute ago. The first run is the honest number, and it misses.

**Why approach 1 is slow.** The trigram index holds, for each trigram, the list of names that contain it. At a threshold of 0.3 a name can pass by sharing only the common trigrams, such as the ones in ING or CONDITIONING, so Postgres has to read those long lists in full and then fetch every candidate row to check it. For one search it fetched about 100,000 rows to keep 10,000.

```
explain (analyze) ... where name_key % 'FERGUSON AIR CONDITIONING' ...          (approach 1)
  Bitmap Index Scan on company_search_name_key_trgm (actual time=1112.643..1112.643 rows=104651)
  Bitmap Heap Scan on company_search (actual time=1121.372..6607.109 rows=10674)
    Rows Removed by Index Recheck: 93977
  Execution Time: 6612.534 ms
```

**Why approach 2 is faster, and where it is still slow.** At a threshold of 0.75 a match needs most of the typed trigrams, and so the index can skip through the long lists and only stop where the rare trigrams are. The same search found 26 candidate rows where approach 1 found 104,651.

```
explain (analyze) ... where 'FERGUSON AIR CONDITIONING' <% name_key ...          (approach 2)
  Bitmap Index Scan (actual time=432.751..432.753 rows=26)
  Execution Time: 436.148 ms

explain (analyze) ... where 'SMITH' <% name_key ...                              (approach 2, a common word)
  Bitmap Index Scan (actual time=47.353..47.353 rows=14864)
  Parallel Bitmap Heap Scan (actual time=46.655..780.847 rows=4698 loops=3)
  Execution Time: 788.075 ms
```

The slow searches are the ones whose words are all common. The index answers quickly (47 milliseconds for SMITH), and then Postgres has to fetch thousands of rows that are scattered through a 3 GB table, most of which is not in memory (733 milliseconds). 🟡 That reading rests on these query plans and on the gap between the first and second runs. I did not profile all 11 slow searches one by one.

Per the brief, I did not try a third approach and I did not change the target. Section 4 has the options.

### Check 4: table and index sizes, and the index build time

```
python src/datum/load_postgres.py

index company_search_name_key_trgm: built in 77.4 seconds
table company_search                                 2986 MB
index company_search_pkey                             625 MB
index company_search_name_key_trgm                    588 MB
table company_flags                                  4200 kB
index company_flags_document_number                   232 kB
index source_coverage_pkey                             16 kB
index company_possible_matches_document_number    8192 bytes
table source_coverage                             8192 bytes
table company_possible_matches                       0 bytes
database total: 4213 MB
```

| What | Size | Note |
|---|---|---|
| The whole database | **4,213 MB** | This is the number that picks a host, and that choice is yours |
| `company_search`, the table | 2,986 MB | 12,988,435 rows |
| Its primary key index | 625 MB | Finds one company by document number |
| Its trigram index | 588 MB | Built in **77.4 seconds** |
| Everything else | under 5 MB | |

The whole load took 4 minutes 5 seconds: the copy of 13 million rows, the primary key, the trigram index and the swap. 🟡 The plan of Oct 30 guessed that a database under about 4 GB would fit a Railway plan. This one is just over, and I did not check any host's current limits.

### Check 5: the offline suite does not need a database

```
brew services stop postgresql@17      → Successfully stopped `postgresql@17`
pg_isready                            → /tmp:5432 - no response
pytest                                → 255 passed in 0.59s
ruff check src tests                  → All checks passed!
brew services start postgresql@17     → Successfully started `postgresql@17`
pg_isready                            → /tmp:5432 - accepting connections
```

✅ With the database server stopped, all 255 tests pass. The tests hand the search a `FakeBackend` and hand the loader a stand-in connection that records what it is asked, so nothing in the suite opens a database. The server was started again afterwards.

### Check 6: the plain-Python Jaro-Winkler gives Snowflake's scores

```
pytest tests/test_search.py -q -k jaro
62 passed, 30 deselected in 0.03s
```

The fixture is 61 pairs captured from Snowflake with one query that reads no table. The capture taught three things about Snowflake's function that the Python version copies, and each has a pair that fails without it:

| What Snowflake does | The pair that shows it | Snowflake's score |
|---|---|---|
| It cuts the score down to a whole number and never rounds up | `ABCDEF` and `ABCXXX`, exactly 66.67 | 66 |
| It adds the bonus for a shared beginning only when the plain score is above 0.7 | `ABCDEF` and `AXXXXX`, which would be 50 with the bonus | 44 |
| It treats upper and lower case as the same letter | `acme roofing` and `ACME ROOFING` | 100 |

The Python function does its arithmetic in exact fractions. With ordinary floating-point numbers the pair `A` and `AB`, which is exactly 0.85, came out as 84.99 and was cut to 84.

### Check 7: the credits

Section 5.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | Step 1 uses word similarity at a threshold of 0.75, and not plain similarity | Plain similarity punishes a registered name for being longer than what was typed, and a contractor nearly always types less than the legal name. At a high threshold the index can also skip its longest lists. Six trial searches at 0.6 and 0.75 picked the number before the timed run | A name with a typing mistake in a short word can fall below 0.75 and never reach step 2. The test set has no such case after extraction, so the evaluation cannot see this cost |
| 2 | The trailing legal suffix is left out of what is sent to the index | LLC and INC are in millions of names, so their trigrams cost the most and tell no two companies apart. Step 2 still scores the full typed name | A search for a name that is only a suffix sends it as typed |
| 3 | The pool is 200 companies | It is wide enough that the best five by Jaro-Winkler are in it for every test case, and scoring 200 names in Python takes about a millisecond | A pool is a guess. `CANDIDATE_POOL` is one constant |
| 4 | `wrong_match` is defined in `evals/run.py`: the search answered with a company, and it is not the expected one | The brief says to use the definitions in script 11, and script 11 defines top-1 and recall at 5 and not `wrong_match`. `docs/PROJECT_CONTEXT.md` calls it "a wrong confident match". Asking for more is never a wrong match | 🔴 This definition is mine. It counts every wrong first answer, whatever its match level, which is the reading that counts more errors |
| 5 | The export writes each fetch time as text ending in Z, and Postgres stores it as a moment in time | The mart's column has no time zone. A bare time in a file would leave UTC to a guess by whoever loads it | One `TO_CHAR` per table in script 23 |
| 6 | The loader gets the expected row counts from a fifth exported file | A table that exported no rows writes no file, and so a missing file and an empty table look the same on disk. Possible matches are exactly that case today | One more small file |
| 7 | The two flag tables in Postgres carry `CHECK (is_shown)` | Rule W9 is then enforced twice: by the export's filter, and by the database refusing a hidden row | None |
| 8 | The Snowflake backend lives in `evals/run.py`, not in `search.py` | The brief names two implementations for `search.py`. The app never talks to Snowflake, and keeping its driver out of the app's module means the app cannot start a billed query by accident | Three backends in two files |
| 9 | The first approach is kept as `PlainSimilarityBackend` in `evals/run.py`, used only by `--retrieve plain` | So that the number in this report can be measured again | About twenty lines the app does not use |
| 10 | `Company` refuses to be built without a full source address and a time-zone-aware UTC fetch time | `CLAUDE.md` rule 3. The review found that the first version only said UTC in a comment (section 4) | None |
| 11 | The shortlist shows the best five by rank, as `report.py` does, and its tie count also covers exact-name companies further down the pool. It carries those companies, not only their number | Rule W7 says a tie is said out loud. The review found a count over the best five could miss an exact-name company ranked sixth, and then found two faults in my fixes (section 4) | An exact-name company ranked sixth is counted and carried, and it is still not on the list of five. Whether such a company should always be listed is a question for leg C3 and for you |
| 12 | The evidence for a company with no city, or no status, on record says so | 186,666 companies have no city on record. `report.py` would print "registered in None", and would call a company with no status inactive. Every company has a status today, so that second case is a guard | Two wordings that `report.py` does not have. Leg C3 decides all wording |

---

## 4. What I couldn't verify, and open questions for Andres

### The decision this leg needs from you: the speed target

The search misses a p95 of 1 second by 0.23 seconds under the better of two approaches. These are the options I can see. I did not build or measure any of them, because the brief says to stop after two.

| Option | What it is | What it costs | My read |
|---|---|---|---|
| **A. A narrow search table** (recommended) | A second table with only the document number and the name, about 0.9 GB against 3.0 GB, with the trigram index on it. Step 1 reads the narrow table, and the 200 full rows are then fetched by document number | One more table in the loader and about 0.9 GB of disk. It is a third approach, so it needs your word | 🟡 It goes at the measured cause: the slow searches spend their time fetching scattered rows from a table too big to stay in memory. I expect it to pass, and I have not measured it |
| B. More memory for Postgres | Postgres is using its default of 128 MB of its own memory. Raising `shared_buffers` to a few GB keeps more of the table in memory | A setting on your Mac's Postgres, and on a host a plan with enough memory | 🟡 The second run suggests a p95 near 0.77 seconds when the pages are in memory. It fixes the machine and not the design, and a host with less memory would bring the problem back |
| C. Keep the target and measure on the host | Leave the search as it is for the local demo, and measure again where the app will really run | Nothing now. It leaves the target open | This is a decision to wait, and it is yours. It is not something I may choose, because it amounts to loosening the target for now |

If you choose A, tell me to run it as one more approach in this leg. I will measure it the same way and report the number whichever way it falls.

### Something outside this run switched the branch

- At 00:28 Eastern time on Nov 21 I created this branch from C1.
- At 00:32:57 and again at 00:34:01 the git log of branch changes (the reflog) shows a checkout of `main`. I did not run either one. No hook in the repo switches branches.
- My next four commits therefore landed on local `main`. Nothing was pushed, and `origin/main` was never touched.
- At 00:58 I noticed it, because the security review's snapshot said "On branch main". I moved the four commits to this branch with `git cherry-pick`, set local `main` back to `origin/main` with `git branch -f main origin/main`, and reran the tests (243 passed at that point).
- From then on every commit command first checks that the branch is `leg/c2-postgres-search`.

🔴 I do not know what switched the branch. The same thing happened once at the very start of this session, before my first command. If it was you, or another Claude session working in `~/datum`, nothing is lost. If it was not, it is worth finding out what it was before the next unattended run, because a run that does not notice would commit to `main`.

### What I couldn't verify

- 🟡 **Which searches are the slow ones.** See check 3.
- 🟡 **That a pool of 200 always holds the best five.** It does for the ten test cases. A larger test set is the real check, and the 90% bar on the 50-case set is yours.
- 🟡 **The cost of the 0.75 threshold on names with typing mistakes** (decision 1).
- 🔴 **The definition of `wrong_match`** (decision 4).
- 🟡 **Host limits.** The database is 4.2 GB and I checked no host.

### The review

- **Tier:** Medium. The leg touches `src/datum/` (not `report.py`), `snowflake/`, tests and `evals/`.
- **Depth:** Standard, which is one `reviewer` pass, plus a security review because `src/` changed.
- **Rounds:** 3, the most the rules allow.
- **Findings in all:** 4 Important, 5 Nit, 2 Pre-existing. The security review found nothing.
- **How it ended:** the third round found one Important finding. I fixed it, and **that last fix has not been reviewed**, because no fourth round is allowed. `docs/prompts/florida_master.md` says a leg stops when an Important finding remains after the third round. This leg was already stopped at the speed check, so this is a second reason for the same stop, and the pull request says so.

**Round 1** (one reviewer on the first four commits, and the security review).

| Finding | Tag | Answer |
|---|---|---|
| A company's fetch time was documented as UTC and nothing made it so. Postgres hands a moment back in the connection's time zone, which on the Mac is Eastern time, and the tests could not see it because their stand-in always answered in UTC | Important | Fixed. ✅ Checked on the real database: a plain connection returned `15:31:31-04:00`, and through the fixed backend the same moment arrives as `19:31:31+00:00`. `Company` now refuses a missing source address or a fetch time that is not time-zone-aware UTC, with a test for each |
| `evidence()` had dropped the ACTIVE or INACTIVE reason that `report.py` gives, and the brief says to follow `report.py`'s rules | Important | Fixed: the status is the last reason again. I had left it out on purpose and should not have. A company with no status on record is said to have none |
| The tie count saw only the five candidates that survived the cut, so an exact-name company ranked sixth was dropped and no tie was reported | Pre-existing (`report.py` cuts to five the same way) | Fixed, and then fixed again in rounds 2 and 3 |
| `evidence()` printed "registered in None" for a company with no city, as `report.py` does | Pre-existing | Fixed. ✅ 186,666 companies have no city on record |
| The Snowflake reference took the best 200 companies by score, so a tie wider than 200 could drop a company in the right city | Nit | Fixed: the pool is every company in the five highest score levels. ✅ The evaluation was run again and gave the same ten lines |
| `SnowflakeBackend` found the fetch time by its position in the row, with no test | Nit | Fixed: found by name, with a test |

The security review read the same four commits and reported no vulnerability it was more than 80% sure of. It checked that everything a person types reaches SQL only as a parameter the driver sends separately, that nothing read from a file becomes SQL text, that no shell command is built, that no file is written outside the tests, and that no secret or drawn company name is printed.

**Round 2** (one reviewer on the three fix commits).

| Finding | Tag | Answer |
|---|---|---|
| My fix for the tie count went too far. It set a level on the whole pool before cutting to five, so a weak name in the right city could push the best-ranked company off the shortlist. City is a tie-break and never a filter | Important | Fixed: the shortlist shows exactly the best five by rank, which are the five the evaluation scores, and only the Strong level is counted over the whole pool |
| At the Possible or Likely level, a count over the whole pool measured how wide the first step cast its net | Nit | Fixed by the same change: those levels are counted among the five shown |
| The 5,000-row ceiling on the Snowflake reference pool cut by document number, without saying so | Nit | Fixed: reaching the ceiling is an error that names the search key |
| "no city on record" claimed more than the table holds, which is the principal address only | Nit | Fixed: "no principal city on record for this company" |

**Round 3** (one reviewer on the two round 2 commits).

| Finding | Tag | Answer |
|---|---|---|
| The shortlist counted same-name companies that it did not carry. A page could say one more company has this exact name and could not name it or cite it, which is a statement with no source (`CLAUDE.md` rule 3) | Important | Fixed and **not reviewed**: the shortlist now carries those companies in a field `not_shown`, each with its source address and fetch time, and a test checks that every company counted in a tie can be reached from the shortlist |

The round 3 reviewer also checked every case of the shortlist against its description (an empty pool, a short pool, no exact-name match, an exact-name match only outside the five shown, and more than five) and found them consistent.

**One thing I take from this review.** Three rounds found three versions of the same function wrong in three different ways. The shortlist decides what a contractor sees first, so it belongs with the High-tier report code, and leg C3, which is High tier, should read `shortlist()` again with three reviewers before any page uses it.

---

## 5. Credits used

**About 0.15 credits** on `datum_wh` (X-Small), roughly $0.31 at $2 a credit. The Postgres side cost nothing.

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATE_TRUNC('hour', DATEADD('hour', -12, CURRENT_TIMESTAMP())), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"

| START_TIME                | END_TIME                  | CREDITS_USED |
| 2026-11-20 20:00:00-08:00 | 2026-11-20 21:00:00-08:00 | 0.176424167  |
| 2026-11-20 21:00:00-08:00 | 2026-11-20 22:00:00-08:00 | 0.414482500  |
| 2026-11-20 22:00:00-08:00 | 2026-11-20 23:00:00-08:00 | 0.037847222  |
```

How the 0.15 is worked out, since the two legs share an hour:

| Line | Credits | Whose |
|---|---|---|
| The 20:00 hour | 0.176 | Leg C1 |
| The 21:00 hour, up to 21:26 Pacific, when leg C1 took its last reading | 0.298 | Leg C1 |
| The rest of the 21:00 hour (0.414 minus 0.298) | 0.117 | Leg C2 |
| The 22:00 hour, read at 22:16 Pacific | 0.038 | Leg C2 |
| **Leg C2** | **0.155** | |

What used the warehouse in this leg:

| What | Times run | Note |
|---|---|---|
| Script 23, the export of 13 million rows | 2 | The second run fixed two file names |
| The download of the exported files | 1 | It reads the stage and does not need the warehouse for long |
| The one query that captured 61 Jaro-Winkler scores | 1 | It reads no table |
| The evaluation on the Snowflake backend | 2 | 17 seconds each. The second run followed the review's change to the pool |

- The brief estimated about 0.05 credits for the export and up to 0.05 for each evaluation run on Snowflake. Two of each is about 0.2, and the leg used 0.15.
- Phase C has now used about **0.63** of its cap of 3 credits (0.47 in leg C1 and 0.15 in this leg). November stands at about 2.96 of the monthly cap of 10.
- 🟡 These numbers come from `information_schema`, which is current to the minute. The slower `account_usage` view may show a slightly different total tomorrow.

---

## 6. Three questions Andres should be able to answer

1. The search has two steps, retrieve and rerank. Which step runs in Postgres and which in Python, and why not do the careful scoring on all 13 million names the way Snowflake does?
2. Approach 1 and approach 2 use the same trigram index. Why is approach 2 so much faster (a p50 of 181 milliseconds against 5,101)? Use the search for `FERGUSON AIR CONDITIONING` and the numbers 104,651 and 26.
3. The second timing run of approach 2 has a p95 of 766 milliseconds, which is under the target. Why is that not the number this report uses?

**Answers, to check yourself.** (1) Postgres retrieves a pool of up to 200 names from the trigram index, and Python reranks that pool by Jaro-Winkler, then city, then document number. Scoring 13 million names carefully takes Snowflake many seconds and bills the warehouse, while scoring 200 takes Python about a millisecond. (2) At a threshold of 0.3 a name can pass on common trigrams alone, so Postgres reads the long lists in full and fetches 104,651 candidate rows to check them. At 0.75 a match needs most of the typed trigrams, so the index only stops where the rare ones are and finds 26 candidates. (3) It searched the same 208 names a minute after the first run, so the rows those names need were already in memory. A real search is a name nobody just searched, and the first run, 1,229 milliseconds, is the honest measure.
