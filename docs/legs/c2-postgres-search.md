# Leg C2: the Postgres copy and the search

Branch `leg/c2-postgres-search` · pull request [#16](https://github.com/andrescamacho57/datum/pull/16) · run on Nov 20 and 21, 2026, and again on Nov 24 for a third approach to the search speed · risk tier **Medium** · status: **every check now passes. The search missed its speed target under the first two approaches, and so the leg stopped on Nov 21. On Nov 24 Andres ruled that one more approach should be tried, the narrow search table. It meets the target, and it returns the same companies as the approach before it on all 208 searches.**

The branch was stacked on `leg/c1-serving-marts`. Pull request 15 was merged on Nov 24, and so this pull request now shows only this leg's commits.

**The short version**

- **The speed target is met by the third approach.** The target is a p95 under 1 second. The p95 is the time that 95 of every 100 searches beat, and the p50 is the time that half of them beat. With the narrow search table, the 208 searches have a p50 of **129 milliseconds**, a p95 of **574 milliseconds** and a slowest search of **2,335 milliseconds**. That is the run measured the way the first two approaches were. I timed the narrow table six times in all, three of them with the Mac's memory emptied of the database first, and the p95 was under 1 second every time: between 430 and 869 milliseconds.
- **The answers did not change.** The second approach and the narrow table were run on the same 208 searches, and all **208** returned the same companies in the same order. **0** differ.
- **One number does not add up, and you should know it.** The second approach missed the target on Nov 21 with a p95 of 1,229 milliseconds. Timed again on Nov 24, on the same 208 searches, it came in under 1 second in all four runs, between 545 and 916 milliseconds. I could not reproduce its miss and I cannot say why (check 3 has what I know). So the measured gain of the narrow table is smaller than the Nov 21 number suggests. Timed from a cold start, the narrow table had a p95 of 560, 520 and 869 milliseconds, against 847 and 863 for the second approach, which makes it faster in two cold runs of three and level in the third. Its slowest search was about half as slow in every run.
- **A few searches are still slow.** Between 2 and 7 of the 208 searches took longer than 1 second, depending on the run. They are names built from one long, common word and one or two very short ones. Check 3 explains them.
- Everything else the leg asks for is done and checked.
  - The four marts are in Postgres, and every table's row count equals Snowflake's: **12,988,435** companies, **9,950** shown flags, **0** possible matches and **5** source rows.
  - No hidden record left Snowflake. **14,263** hidden flags and all **9,651** possible matches stayed behind.
  - The search scores at least as well as Snowflake on the test set: top-1 **7** of 10 against 6, recall at 5 **9** against 9, and wrong_match **2** against 3.
  - The offline tests pass with Postgres stopped: 264 passed.
- On Nov 21 something outside the run switched the working folder to the branch `main`, and four commits landed on local `main`. Nothing was pushed, and the commits were moved to this branch. It did not happen on Nov 24, when every commit was preceded by a check of the branch name. Section 4 has the details.

**What is left for Andres**

1. **Decide whether to drop the old trigram index.** The index on `company_search.name_key` takes 588 MB, and only the second approach reads it now. I kept it so that the second approach could be timed again. Dropping it is one line in the loader.
2. **Know the new size before you pick a host.** The database grew from 4,213 MB to **5,503 MB**, because the narrow table and its index were added (check 4).
3. Read section 3, which holds the calls I made where the brief did not say. Decisions 13 to 18 are the new ones.

The condition you set for going on to legs C3 and C4 is met: the p95 is under 1 second, and all 208 searches return the same companies.

**The history, in order**

| When | What happened |
|---|---|
| Nov 20 and 21 | The leg was built. Two approaches to the search were timed, with a p95 of 11,212 and of 1,229 milliseconds. Both missed the target, and so the leg stopped, as the brief requires |
| Nov 21 | Three review rounds. The fix for the third round's finding, commit `d2e51f1`, was not reviewed, because no fourth round is allowed |
| Nov 24 | Andres ruled that a third approach should be tried: option A, the narrow search table. It was built, timed and compared, and the new commits were reviewed from round 1, together with `d2e51f1` |

---

## 1. What I built

### The picture

```
 Snowflake marts                                  Postgres on the Mac (database datum_dev)
   company_search ─────────┐
   company_flags (shown) ──┤  script 23           load_postgres.py
   possible matches (0) ───┼──────────▶ data/export/*.csv.gz ──────────▶ four tables, swapped in one transaction
   source_coverage ────────┘  + a counts file                            + company_search_names, the narrow table (Nov 24):
                                                                           document number and name only, with the trigram index
                                                                              │
                                                             search.py:  RETRIEVE a pool by trigram from the narrow table,
                                                                           then read those 200 companies from company_search
                                                                         RERANK the pool by Jaro-Winkler (plain Python)
                                                                              │
                                                             evals/run.py scores it against the test set,
                                                             on Postgres and on Snowflake
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| Postgres 17 | A database server, installed with Homebrew and running on the Mac only. The database is `datum_dev`, with the `pg_trgm` extension turned on | Decision d18: lookups read Postgres, and builds run in Snowflake |
| `snowflake/23_export_marts.sql` | Copies the four marts out of Snowflake as compressed CSV (comma-separated values) files, plus a fifth small file holding each table's row count. The two flag marts are filtered to rows with `is_shown` true | Working rule W9: a hidden record never leaves Snowflake |
| `src/datum/load_postgres.py` | Checks the files, loads each table under a temporary name, counts the rows, builds the narrow table and checks it, builds the indexes, and then swaps every table in with one transaction | A load that fails halfway must never leave the app reading half a table |
| `company_search_names` (added Nov 24) | The narrow search table. It has one row per company, holding the document number and the simplified name and nothing else, and the rows are written in name order. The loader builds it inside Postgres from the company rows it has just loaded | The third approach to the search speed. A row here is 69 bytes against 241 in `company_search`, and so checking thousands of candidate names reads far fewer pages |
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
 STEP 1  RETRIEVE   Postgres, trigram index on the narrow table: up to 200 companies whose
                    name CONTAINS something close to the typed name (word similarity at 0.75
                    or more). Only their document numbers leave the narrow table, and each
                    company is then read in full from company_search by that number
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
| `src/datum/load_postgres.py`, `tests/test_load_postgres.py` | New. 14 tests, 4 of them added on Nov 24 for the narrow table |
| `src/datum/search.py`, `tests/test_search.py`, `tests/fixtures/search/` | New. 93 tests, 61 of them one per fixture pair, and 1 added on Nov 24 for the narrow-table query |
| `evals/run.py`, `tests/test_evals_run.py` | New. 16 tests, 4 of them added on Nov 24 for the comparison of two approaches |
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
- ✅ On Nov 24 the changed loader ran again from the same exported files, and it printed the same four counts. No new export was made, and so the Snowflake side of this check is the one from Nov 20. Check 9 has the line the loader now prints for the narrow table.

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
- ✅ On Nov 24 the Postgres run was repeated with the narrow table, and it gave the same ten lines and the same three totals. The Snowflake run was not repeated, because nothing on that side changed.

### Check 3: p50 and p95 search time. **The first two approaches miss the target, and the third meets it**

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

Per the brief, I did not try a third approach on Nov 21 and I did not change the target. Section 4 has the options that were put to Andres.

#### The third approach: the narrow search table (Nov 24)

Andres ruled on Nov 24 that one more approach should be tried, and named it: option A of section 4, a narrow search table.

**What it is.** The loader builds a second table, `company_search_names`, with one row per company that holds only the document number and the simplified name. The trigram index the search reads is on that table. The question asked of the index did not change: it is still word similarity at 0.75 with the legal suffix left out. What changed is where Postgres goes to check the answer.

```
 approach 2                                   approach 3 (the narrow table)

 index ──▶ thousands of candidate rows        index ──▶ thousands of candidate rows
           in company_search                            in company_search_names
           (241 bytes a row, 3.0 GB,                    (69 bytes a row, 0.85 GB,
            rows in no useful order)                     rows in name order)
              │ check each, keep 200                       │ check each, keep 200 document numbers
              ▼                                            ▼
           the pool                                     200 lookups in company_search by its
                                                        primary key ──▶ the pool
```

**How it was measured.** The command is the one that timed the first two approaches, on the same 208 searches: the 8 specific test inputs and the 200 company names the fixed seed draws.

- ✅ The 200 drawn names are the same ones before and after the loader ran again on Nov 24. A fingerprint of the drawn names (an MD5 hash, which is a short code that changes when any name changes) was `29e32d4a94b0a803614ddf7256322a37` both times.
- 🟡 Nothing recorded the fingerprint on Nov 21. The command, the seed and the exported files are the same as then, and so I take the draw to be the same, and I cannot prove it.
- Before timing anything, I decided which run would be the number for this report: the first run after Postgres is restarted, with the narrow table timed before the second approach. A restart empties Postgres's own memory. That is the closest match to "the first run" of Nov 21.
- That first pair showed the second approach under 1 second too, which meant the conditions were not as cold as on Nov 21. So I added a stricter kind of run, called "cold" below. Postgres is stopped, the Mac is told to forget its cached copy of every database file, a check confirms that 0 MB of those files is left in memory, and Postgres is started again. Every search in a cold run reads from disk the first time it needs a page.

```
python -m evals.run --backend postgres --latency 200                    (approach 3, first run after a restart)
latency over 208 searches (8 test inputs + 200 random company names, pool of 200):
  p50 129 ms   p95 574 ms   slowest 2335 ms
  searches over 1 second: 3 of 208

python -m evals.run --backend postgres --latency 200 --retrieve word    (approach 2, straight after)
  p50 180 ms   p95 545 ms   slowest 5007 ms
  searches over 1 second: 5 of 208

(Postgres stopped)  328 files, 5,505 MB: in memory before 612 MB, after 0 MB  (Postgres started)
python -m evals.run --backend postgres --latency 200                    (approach 3, cold)
  p50 120 ms   p95 560 ms   slowest 2464 ms
  searches over 1 second: 3 of 208

(Postgres stopped)  328 files, 5,505 MB: in memory before 1,162 MB, after 0 MB  (Postgres started)
python -m evals.run --backend postgres --latency 200 --retrieve word    (approach 2, cold)
  p50 148 ms   p95 847 ms   slowest 5402 ms
  searches over 1 second: 8 of 208
```

Every timed run of Nov 24, in the order it was made. None is left out.

| # | Approach | State before the run | p50 | p95 | Slowest | Over 1 second |
|---|---|---|---|---|---|---|
| 1 | **3, the narrow table** | **Postgres restarted. This is the run chosen in advance** | **129 ms** | **574 ms** | **2,335 ms** | 3 of 208 |
| 2 | 2 | Straight after run 1 | 180 ms | 545 ms | 5,007 ms | 5 of 208 |
| 3 | 2 | Postgres restarted | 173 ms | 916 ms | 5,757 ms | 8 of 208 |
| 4 | 3, the narrow table | Straight after run 3 | 128 ms | 459 ms | 3,154 ms | 2 of 208 |
| 5 | 3, the narrow table | Cold | 120 ms | 560 ms | 2,464 ms | 3 of 208 |
| 6 | 2 | Cold | 148 ms | 847 ms | 5,402 ms | 8 of 208 |
| 7 | 2 | Cold | 152 ms | 863 ms | 5,335 ms | 8 of 208 |
| 8 | 3, the narrow table | Cold | 118 ms | 520 ms | 2,369 ms | 4 of 208 |
| 9 | 3, the narrow table | Cold | 156 ms | 869 ms | 4,291 ms | 7 of 208 |
| 10 | 3, the narrow table | Straight after run 9, so everything was in memory | 128 ms | 430 ms | 1,823 ms | 2 of 208 |

| Approach | Runs | p95, lowest to highest | Target: p95 under 1 second |
|---|---|---|---|
| 1. Plain similarity (Nov 21) | 1 | 11,212 ms | ❌ |
| 2. Word similarity on `company_search` (Nov 21) | 1 that counts | 1,229 ms | ❌ |
| 2 again (Nov 24) | 4 | 545 to 916 ms | ✅ on that day, which the Nov 21 run contradicts |
| **3. Word similarity on the narrow table (Nov 24)** | **6** | **430 to 869 ms** | ✅ **in every run** |

**What these numbers do and do not show.**

- ✅ The narrow table meets the target. Its p95 was under 1 second in all six runs, cold or not.
- ✅ In the matched runs it is the faster of the two. After a restart, 574 milliseconds against 916. Cold, 560, 520 and 869 against 847 and 863. Its slowest search took between 1.8 and 4.3 seconds, against 5.0 to 5.8 for the second approach.
- 🟡 **The second approach's miss of Nov 21 did not happen again.** It measured 1,229 milliseconds then, and 545 to 916 on Nov 24, even cold. A p95 over 208 searches is the 198th fastest time, and so it moves from under 1 second to over it when three or four searches near the line get slower. I do not know what made them slower on Nov 21. The honest reading is that the second approach sits close to the line, and the narrow table sits further under it.
- 🟡 **Run 9 is the narrow table's worst, at 869 milliseconds, and I cannot say what slowed it.** The Mac was busy with its own night-time work while I timed (photo analysis and other system tasks, with a load average of about 9, which means about nine programs wanted the processor at any moment). I did not stop those tasks. They make every number here a little worse than a quiet machine would give, and they make the runs differ from each other.
- 🟡 These are timings on the Mac. The host that will run the app has a different disk and a different amount of memory, and nothing here measures it.

**Why the narrow table is faster.** The search for SMITH shows it. The index gives the same 14,864 candidate rows in both tables. To check them, Postgres read 14,406 pages of `company_search` and 5,563 pages of the narrow table, and a page is 8 kilobytes. Fewer pages hold the same names because each row is narrower, and because names that start alike sit together.

```
explain (analyze, buffers) ... 'SMITH' <% name_key ...                          (approach 2, Nov 24)
  Bitmap Index Scan on company_search_name_key_trgm (actual time=48.120..48.120 rows=14864)
  Bitmap Heap Scan on company_search (actual time=49.660..2729.311 rows=14094)
    Heap Blocks: exact=14406
  Execution Time: 2735.763 ms

explain (analyze, buffers) ... 'SMITH' <% name_key ...                          (approach 3, Nov 24)
  Bitmap Index Scan on company_search_names_name_key_trgm (actual time=41.631..41.631 rows=14864)
  Bitmap Heap Scan on company_search_names (actual time=42.377..909.565 rows=14094)
    Heap Blocks: exact=5563
  Index Scan using company_search_pkey on company_search c (actual time=0.488..0.488 rows=1 loops=200)
  Execution Time: 1011.014 ms
```

The last line of the second plan is the price of the narrow table: 200 lookups in `company_search` by document number, at about half a millisecond each when nothing is in memory. Both plans were taken once, with the Mac busy, and so the two times show the gap and are not a measurement of SMITH.

The narrow table does not help a search whose time goes on reading the index itself. FERGUSON AIR CONDITIONING took 401 milliseconds on the narrow table and 510 on `company_search`, and in both nearly all of that was the index scan, which finds 26 candidates.

**The searches that are still slow.** I timed each of the 208 searches once more and read the query plan of the six slowest. Their names are not printed here, because they are drawn company names.

| What the six slowest have in common | The numbers |
|---|---|
| The name has two or three words: one long word of 9 to 14 letters, and one or two short words of 1 to 5 letters | Five of the six. The sixth has three words, of 3, 8 and 11 letters |
| The index returns thousands of candidate rows. 🟡 My reading is that the long word is a common one and the short words add almost nothing to tell names apart. I read the counts and not the names | Between 8,394 and 182,812 candidates. The search for FERGUSON AIR CONDITIONING returns 26 |
| Postgres has to open and check every candidate, and that work is what takes the time | 1.0 to 2.4 seconds on the narrow table, and 1.8 to 9.2 seconds on `company_search` for the same six |

🟡 The narrow table shortens these searches and does not remove them. Making them fast would need a different question asked of the index, which is a change to what the search retrieves and not only to its speed. I did not try that, because the ruling was for one more approach.

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

**The sizes after the narrow table was added (Nov 24).** The table above is the state of Nov 20. This is the loader's output today.

```
python src/datum/load_postgres.py

index company_search_name_key_trgm: built in 75.0 seconds
index company_search_names_name_key_trgm: built in 66.6 seconds
table company_search                                 2986 MB
table company_search_names                            850 MB
index company_search_pkey                             625 MB
index company_search_name_key_trgm                    588 MB
index company_search_names_name_key_trgm              441 MB
table company_flags                                  4200 kB
index company_flags_document_number                   232 kB
index source_coverage_pkey                             16 kB
index company_possible_matches_document_number    8192 bytes
table source_coverage                             8192 bytes
table company_possible_matches                       0 bytes
database total: 5503 MB
```

| What | Size | Note |
|---|---|---|
| The whole database | **5,503 MB** | It was 4,213 MB. This is the number that picks a host |
| `company_search_names`, the narrow table | 850 MB | 12,988,435 rows of 69 bytes each, against 241 bytes a row in `company_search` |
| Its trigram index | 441 MB | Built in **66.6 seconds**. It is smaller than the 588 MB index on `company_search`, which holds the same names. 🟡 I think that is because the rows are in name order, and I did not test it |
| The old trigram index on `company_search` | 588 MB | Only the second approach reads it now. Dropping it would bring the database to about 4,915 MB, and that is your call |

The whole load now takes 6 minutes 13 seconds, which is about 2 minutes more than before. The extra time goes on sorting 13 million names, comparing the two tables and building the second index.

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

✅ The same check was run again on Nov 24, after the narrow table's commits, and 264 tests passed.

```
brew services stop postgresql@17      → Successfully stopped `postgresql@17`
pg_isready                            → /tmp:5432 - no response
pytest                                → 264 passed in 0.59s
ruff check src tests                  → All checks passed!
brew services start postgresql@17     → Successfully started `postgresql@17`
pg_isready                            → /tmp:5432 - accepting connections
```

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

### Check 8: the second approach and the narrow table return the same companies (Nov 24)

The ruling asks for this check. Both approaches were run on the same 208 searches, and for each search the companies returned were compared: the same document numbers, in the same order, with the same details.

```
python -m evals.run --backend postgres --compare 200

compared 208 searches (8 test inputs, then 200 random company names): the second approach (company_search) against the app's search (company_search_names)
  the same companies in the same order: 208 of 208
  differing: 0
  the second approach returned 5 companies for 100 searches, 1 to 4 for 108, and none for 0
```

- ✅ **0 of the 208 searches differ.** There is no difference to explain.
- The search shows five companies at most. For 100 of the searches both approaches returned the same five. For the other 108 fewer than five companies passed the first step, and both approaches returned the same one to four. No search came back empty, so no pair matched only because both were empty.
- This is the expected result, and here is why. Both approaches ask the same question (word similarity at 0.75), in the same order (nearest name first, then document number), of two tables that hold the same names. Check 9 is what proves that last part.
- The comparison covers the companies that are returned, which is what a contractor would see. It does not compare the whole pool of 200 that each approach hands to the rerank step.

### Check 9: the narrow table and `company_search` hold the same document numbers (Nov 24)

The ruling asks for a test of this. It is in two places, because the offline test suite may not open a database (`CLAUDE.md` rule 4).

| Where | What it proves | How |
|---|---|---|
| The loader, on the real data, at every load | The narrow table it has just built holds exactly the companies of `company_search`. If it does not, nothing is swapped in | One query, `NAMES_CHECK_SQL`, returns four numbers: the rows in each table, the rows of the narrow table with no company of that document number and name, and the companies with no row in the narrow table |
| `tests/test_load_postgres.py`, offline | That query notices every kind of difference, and the loader stops on each | The test runs the loader's own query in SQLite, a small database that ships inside Python and runs in memory, against tables that differ in five ways: a company missing, a company added, a different number, a number twice, and the right number under another name |

```
python src/datum/load_postgres.py        (the line it prints for the narrow table)
company_search_names: 12,988,435 rows built from company_search's 12,988,435; 0 only in company_search_names, 0 only in company_search

pytest tests/test_load_postgres.py -q
14 passed in 0.13s
```

- ✅ On the real data both tables have 12,988,435 rows, and no document number is in one and not in the other.
- ✅ Each new test was made to fail once. With the loader changed to ignore the row counts, the test of the loader failed. With the query changed to ignore the name, the test of the query failed. Both changes were then undone.
- The check compares the document number and the name together, which is more than the ruling asks. A narrow table with the right numbers and a wrong name would send the search to the wrong company, and so it is refused too.

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

Decisions 13 to 18 were made on Nov 24, for the narrow table.

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 13 | The narrow table's rows are written in name order | Postgres keeps rows in the order they arrive. Names that start alike then share a page, and the candidates of one search are mostly names that start alike. I chose this before timing anything | The load sorts 13 million names. 🟡 I built the table one way only, so I cannot say how much of the gain comes from the narrow rows and how much from their order |
| 14 | The narrow table has no source address, no fetch time and no primary key | It states no fact to anybody. The search reads it only to learn which document numbers to fetch, and every company it then returns is read from `company_search`, with its source address and fetch time. A test holds the query to that. A primary key would be a second index of about 600 MB that nothing would read | Nothing in Postgres itself stops a document number appearing twice in the narrow table. The loader's check does that job at every load (check 9) |
| 15 | The check that the two tables hold the same companies lives in the loader, and it runs before the swap | The offline suite may not open a database (`CLAUDE.md` rule 4), so a test of the live tables could not be part of it. In the loader the check runs on the real data every time, and a failure leaves the old tables in place | The check adds about 20 seconds to a load 🟡 (I did not time it apart from the rest) |
| 16 | The old trigram index on `company_search` is kept | The ruling asks for the second approach to be run again, and it needs that index. The brief for this leg also names that index | 588 MB that the app's search no longer reads. Dropping it is your call |
| 17 | The number for this report is the first run after a restart, chosen before any timing. The cold runs were added afterwards, and every run is listed | A number picked after seeing ten runs could be the one that flatters. Naming it first, and then listing all ten, lets you check that it was not | The cold runs use a small script that tells macOS to forget its cached copy of the database files. 🟡 It is in this run's scratch folder and not in the repo, because it is specific to macOS and has no test. `sudo purge` does the same for the whole Mac and needs your password |
| 18 | The comparison checks the companies each search returns, and not the whole pool of 200 | The ruling asks whether each search returns the same five companies in the same order. The returned companies are what the evaluation scores and what a contractor would see | Two pools could differ below the companies returned and the check would not see it. With the same question asked of the same names that cannot happen, and check 9 proves the names are the same |

---

## 4. What I couldn't verify, and open questions for Andres

### The speed target: what was asked on Nov 21, and what was decided on Nov 24

**The outcome.** On Nov 24 Andres chose option A below, the narrow search table. It was built and measured, and it meets the target (check 3). Question Q33 in `docs/open_questions.md` is answered.

What follows is the question as it was put on Nov 21, kept as it was written.

The search misses a p95 of 1 second by 0.23 seconds under the better of two approaches. These are the options I can see. I did not build or measure any of them, because the brief says to stop after two.

| Option | What it is | What it costs | My read |
|---|---|---|---|
| **A. A narrow search table** (recommended) | A second table with only the document number and the name, about 0.9 GB against 3.0 GB, with the trigram index on it. Step 1 reads the narrow table, and the 200 full rows are then fetched by document number | One more table in the loader and about 0.9 GB of disk. It is a third approach, so it needs your word | 🟡 It goes at the measured cause: the slow searches spend their time fetching scattered rows from a table too big to stay in memory. I expect it to pass, and I have not measured it |
| B. More memory for Postgres | Postgres is using its default of 128 MB of its own memory. Raising `shared_buffers` to a few GB keeps more of the table in memory | A setting on your Mac's Postgres, and on a host a plan with enough memory | 🟡 The second run suggests a p95 near 0.77 seconds when the pages are in memory. It fixes the machine and not the design, and a host with less memory would bring the problem back |
| C. Keep the target and measure on the host | Leave the search as it is for the local demo, and measure again where the app will really run | Nothing now. It leaves the target open | This is a decision to wait, and it is yours. It is not something I may choose, because it amounts to loosening the target for now |

If you choose A, tell me to run it as one more approach in this leg. I will measure it the same way and report the number whichever way it falls.

**How the estimate for option A held up.** The table above guessed the narrow table at about 0.9 GB, and it is 850 MB. It said the slow searches spend their time fetching scattered rows, and the plans for SMITH bear that out (14,406 pages against 5,563). It did not foresee that the second approach would come in under 1 second when timed again.

### Something outside this run switched the branch

- At 00:28 Eastern time on Nov 21 I created this branch from C1.
- At 00:32:57 and again at 00:34:01 the git log of branch changes (the reflog) shows a checkout of `main`. I did not run either one. No hook in the repo switches branches.
- My next four commits therefore landed on local `main`. Nothing was pushed, and `origin/main` was never touched.
- At 00:58 I noticed it, because the security review's snapshot said "On branch main". I moved the four commits to this branch with `git cherry-pick`, set local `main` back to `origin/main` with `git branch -f main origin/main`, and reran the tests (243 passed at that point).
- From then on every commit command first checks that the branch is `leg/c2-postgres-search`.

🔴 I do not know what switched the branch. The same thing happened once at the very start of this session, before my first command. If it was you, or another Claude session working in `~/datum`, nothing is lost. If it was not, it is worth finding out what it was before the next unattended run, because a run that does not notice would commit to `main`.

✅ On Nov 24 the branch did not change during the run. Every commit command first checked that the branch was `leg/c2-postgres-search`.

### What I couldn't verify

This is the full list as of Nov 24. Items 1 to 4 are new, and items 5 to 9 stand from Nov 21.

1. 🟡 **Why the second approach missed the target on Nov 21 and met it on Nov 24.** It measured 1,229 milliseconds then and 545 to 916 now, on the same 208 searches (check 3).
2. 🟡 **The speed on a host.** Every timing is from the Mac, which was busy with its own night-time tasks while I timed. A host has a different disk and a different amount of memory.
3. 🟡 **The searches that are still slow.** Between 2 and 7 of the 208 take longer than 1 second. I read the plans of the six slowest and not their names (check 3).
4. 🟡 **That the 208 searches are the very ones of Nov 21.** The command, the seed and the exported files are the same, and the fingerprint of the drawn names did not change across the load of Nov 24. Nothing recorded it on Nov 21.
5. 🟡 **That a pool of 200 always holds the best five.** It does for the ten test cases. A larger test set is the real check, and the 90% bar on the 50-case set is yours.
6. 🟡 **The cost of the 0.75 threshold on names with typing mistakes** (decision 1).
7. 🔴 **The definition of `wrong_match`** (decision 4).
8. 🟡 **Host limits.** The database is now 5.5 GB and I checked no host.
9. 🔴 **What switched the branch on Nov 21.** It is still unknown.

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
- ✅ **The work of Nov 24 used no credits.** It made no call to Snowflake: the loader read the files exported on Nov 20, and every timing and the comparison ran against Postgres on the Mac, which is free. The leg's total stays at about 0.15 credits.
- 🟡 These numbers come from `information_schema`, which is current to the minute. The slower `account_usage` view may show a slightly different total tomorrow.

---

## 6. Three questions Andres should be able to answer

These were rewritten on Nov 24, so that two of the three are about the narrow table.

1. The search has two steps, retrieve and rerank. Which step runs in Postgres and which in Python, and why not do the careful scoring on all 13 million names the way Snowflake does?
2. The narrow table holds the same names as `company_search`, and both have a trigram index on those names. Why is the search for `SMITH` faster on the narrow table? Use the numbers 14,864, 14,406 and 5,563.
3. The narrow table has no source address and no fetch time. Why does that not break the rule that every fact carries both, and what stops the search from finding a company in the narrow table that `company_search` does not hold?

**Answers, to check yourself.** (1) Postgres retrieves a pool of up to 200 names from the trigram index, and Python reranks that pool by Jaro-Winkler, then city, then document number. Scoring 13 million names carefully takes Snowflake many seconds and bills the warehouse, while scoring 200 takes Python about a millisecond. (2) The index only says which rows might match, and for `SMITH` it names the same 14,864 candidate rows in both tables. Postgres then has to open each one to check it. In `company_search` those rows are spread over 14,406 pages. In the narrow table a row is 69 bytes and not 241, and names that start alike sit together, so the same rows are on 5,563 pages, and fewer pages means less to read. (3) The narrow table states no fact. The search takes only document numbers from it, and every company it returns is read from `company_search`, which has the source address and the fetch time. At every load, before any table is swapped in, the loader checks that the two tables hold the same document numbers and names, and it refuses the load when they do not.
