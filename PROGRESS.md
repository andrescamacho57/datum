# Datum — Progress Tracker

**Owner:** Andres Camacho
**Build started:** 2026-10-12
**Current milestone:** look up any Florida company (full Sunbiz register loaded)
**Status:** First slice proven end to end on one daily file; loading the quarterly snapshot

Approved decisions live on the Agenda dashboard (Decisions tab). This file is the
build log: what got done, what I learned, what's next.

---

## The rules for this project

- **Workflow first.** Plain code for predictable steps, a model call only for close
  name matches, an agent only for long-tail lookups behind human review.
- **Simplest correct solution.** Add complexity only for a problem we actually have.
- **Inspect before loading.** Look at every new file on the laptop before spending
  warehouse credits on it.
- **Nothing shows to a contractor as fact below 90%** on the 50-name test set, and
  every report line links to its official record.

---

## Done

### Day 0 — 2026-10-12: Decisions synced, Snowflake set up, first file staged

**Docs**
- Project docs synced to the Oct 11 decisions: no interview gate on code, v1 source
  order (Sunbiz + DBPR, then one county's liens), stack, 90% accuracy bar, outreach
  = free report + $50 gift card, no trade-first choice

**Snowflake**
- Resource monitor `datum_monthly`: 10 credits/month, notify at 80%, suspend at 100%
- Warehouse `datum_wh`: X-Small, 60-second auto-suspend, owned by SYSADMIN
- Database `datum`, schema `raw`, file format `fixed_width`, stage `sunbiz_stage`,
  table `sunbiz_cor_daily (line, source_file, loaded_at)`

**Data**
- Downloaded `doc/cor/20261009c.txt` from the state's SFTP server: 1.1 MB, 834 records
- Inspected before loading: `wc -l` (834), `head -c 300`, line lengths with `awk`,
  raw bytes with `od -c` → every record is **1440 bytes = 1436 content + 4 NUL padding**
- Spot-checked field positions on 5 records (document number, status, filing type,
  officer title) against the state's published layout
- Uploaded to the stage through Snowsight (the `snow` CLI wasn't installed yet)

**Decision:** one Snowflake stage per Sunbiz file type

**Concepts learned:** fixed-width files and record layouts, SSH trust-on-first-use,
bytes vs characters, NUL padding, why tools disagree about a file's length

### Day 1 — 2026-10-13: Raw table loaded, repo on GitHub

- `COPY INTO` raw: **834 rows, every line 1440 characters** (Snowflake kept the NUL
  padding that macOS `awk` hid)
- Found `~/.config` owned by `root` (from a 2024 `sudo` install) — the reason the
  GitHub CLI could never save a login. Fixed with `chown`; login now persists
- Repo pushed to GitHub (private): `andrescamacho57/datum`

**Concepts learned:** file ownership and permissions, reading `ls -l`, `sudo`/`chown`,
git remotes, COPY idempotency

### Day 2 — 2026-10-20/21: dbt end to end — first slice done

- dbt project in `pipeline/` (dbt 2.0.8, Fusion engine), `datum` profile with
  key-pair auth (same key as credit-stream)
- `stg_sunbiz__cor` (view): cuts each line into named columns by position
- `entity_lookup` (table): well-formed rows only, one row per company, `name_key`
- 3 tests: `not_null` + `unique` on document_number, `accepted_values` on status
- First build failed twice — both my file errors: Jinja braces inside a SQL comment,
  and dbt 2.0 requiring test settings under `arguments:`. Fixed; **5/5 passed**
- Known-answer test: **DINATALE VENTURES LLC (L26000514010)** returned from the mart

**Concepts learned:** sources vs refs, the DAG, materializations (view vs table),
Jinja renders before SQL runs, QUALIFY + ROW_NUMBER for dedupe, normalization and
regex, boolean flag columns, DEV vs PROD environments

### Day 3 — 2026-10-22: Full Florida register loaded and verified

- Installed the Snowflake CLI (`snow`) with pipx. First attempt failed: Homebrew had
  just installed Python 3.15, too new for `pydantic-core` (no prebuilt wheel, and its
  Rust build tool supports ≤3.13). Fixed with `--python python3.12`
- `snow` connection `datum` (key-pair, SYSADMIN, DATUM_WH): test **OK**
- Downloaded `doc/quarterly/cor/cordata.zip`: 1.7 GB → 10 files, **18.7 GB**,
  **12,987,601 records**
- Inspected before loading: quarterly lines are **1442 bytes** (1440 + CRLF), vs 1441
  in the daily file (1440 + LF). No code change needed (`length(line) >= 1436` holds)
- Suspected a duplicate (`cordata6` and `cordata8`: same size, same line count) —
  **disproved with `md5`**. In a fixed-width file, same line count ⇒ same size, so
  it was one coincidence, not two
- Created stage `sunbiz_cor_quarterly_stage`
- Snowflake SQL reorganized into numbered scripts in `snowflake/`; study guide created
- `PUT` all 10 files: 18.7 GB → **1.80 GB gzipped** (~10:1). `cordata6`/`cordata8`:
  same raw size, different compressed size — a second proof they differ
- `COPY` into new table `raw.sunbiz_cor_quarterly`: **12,987,601 rows**, every
  per-file count matched size ÷ 1442 exactly
- Line length **1440**, not the 1441 I predicted — Snowflake strips `\r\n` as one line
  ending. Prediction disproved by the data; docs corrected
- **Status: I = 9,168,902 (71%), A = 3,818,699 (29%).** The "active data" snapshot
  includes inactive companies — the dissolved-client signal is there

**Decision:** separate raw table for the quarterly snapshot (raw = one table per source
kind; staging combines them)

- Deleted the 18.7 GB of `.txt` files (zip kept). Snapshot date from `unzip -l`: **2026-10-07**
- dbt: staging combines daily + quarterly (`union all`) with `source_kind` and
  `published_on`; mart orders "newest" by `published_on`, then `loaded_at` (fixes the
  load-time ordering bug). New `not_null` test on `published_on`
- `dbt build`: **6/6 passed** in 44s; `entity_lookup` = **13.0M companies**, `unique` holds
- Known-answer checks by exact document number (not name):
  - L26000514010 DINATALE VENTURES LLC → A, daily, 2026-10-09 ✅
  - P98000033661 FERGUSON AIR CONDITIONING & REFRIGERATION, INC. → A, DOMP,
    Boynton Beach, filed 1998-04-13, quarterly, 2026-10-07 ✅ (matches search.sunbiz.org)
- Mart mix: daily A 834 · quarterly A 3,818,699 · quarterly I 9,168,902

**Decisions:** separate raw table per Sunbiz file kind; combine in staging; "newest" =
the state's publish date. Snapshot date hardcoded until the January 2027 snapshot.

**Concepts learned:** union all vs union, known-answer tests by identity (ID, not name),
APFS disk percentages, compression ratios, predictions checked against data

---

### Day 4 — 2026-10-24/25: What a daily file actually is

- Anti-join of the Oct 9 daily file against the Oct 7 snapshot (`07_explore_daily_vs_quarterly.sql`):
  **all 834 daily records are new companies** — none existed in the snapshot
- So the daily corporate file = new registrations. Updates to existing companies
  (dissolutions!) come through the separate **events** file or the next quarterly →
  without events, status can be up to ~3 months stale
- The Oct 9 file holds filings dated Oct 1–8: the state processes with a lag
- `file_date` includes 21 records dated 2027-01-01 → it's often an effective date, not
  the filing date
- Designed the search flow: LLM extracts fields → plain-code normalization → SQL
  fuzzy match (`EDITDISTANCE`, `JAROWINKLER_SIMILARITY`) → LLM judges only close
  calls → user confirms

- Test set v0: 10 cases in `pipeline/seeds/test_set.csv` (dbt seed → `DEV_EVALS.TEST_SET`),
  two groups: `legal_name_variant` (8) and `real_world_reference` (2)
- **Baseline search** (`09_score_baseline_search.sql`: normalize input like `name_key`,
  top-1 `JAROWINKLER_SIMILARITY` over all 13M names): **6/10 = 60%**
  (legal-name variants 6/8 = 75%, real-world references 0/2)
- Misses: `ferguson ac…` → FERGUSON MORTGAGE (abbreviation); `kromah properties` →
  KROM PROPERTIES (close competitor name); Cinemark → CINEMAR, INC. (storefront ≠ legal
  entity); `the pool guy off race track rd` → a Central Florida pool company at **91**,
  a confident wrong answer
- Correct matches scored 91–96 and a wrong one scored 91: **similarity is not confidence**.
  No threshold separates right from wrong; we need more signals (location, margin to
  the runner-up) and a user confirmation step

**Concepts learned:** anti-join (LEFT JOIN + IS NULL), full snapshot vs delta,
processing lag, normalize both sides with the same function, dbt seeds, baselines,
Jaro-Winkler (prefix-weighted), similarity ≠ confidence, small eval sets swing 10% per case

### Day 5 — 2026-10-26/27: Search v1 with LLM extraction

- Recall@5 on the baseline (`10_score_baseline_recall_at_5.sql`): **8/10** — a shortlist
  rescues Kromah (#2) and Cinemark (#2). Hughes' top-1 "win" was a 91/91 tie: luck
- Suffix stripping computed offline first (Python Jaro-Winkler reproduced Snowflake's
  scores exactly): flips no test case → **not built**
- `src/datum/extract.py`: Claude API (Haiku) call per input with a forced tool schema →
  `{business_name, city, street, is_specific}` → `pipeline/seeds/extracted_inputs.csv`
- New `.venv` on Python 3.12 + `anthropic` SDK; API key in `~/.zshrc`, never in the repo.
  The SDK rejected `temperature` → repeatability comes from freezing outputs in the CSV
- Prompt v1 broke "really good beer" (→ "Beer") and invented city "Surfside"; prompt v2
  fixed the name. Stopped tuning after 2 rounds (tuning on the test set inflates it)
- **Search v1** (`11_score_search_v1.sql`: extracted name → Jaro-Winkler → city tie-break
  → fixed sort; vague notes → NEEDS_MORE_INFO):

  | | top-1 | recall@5 |
  |---|---|---|
  | v0 baseline | 6/10 | 8/10 |
  | **v1 extraction** | **6/10** | **9/10** |

  Gains: Ferguson (#1, AC → Air Conditioning), pool guy (correctly asks for more).
  Losses: Hughes (#4, HUGHES FINANCIAL GROUP outranks — city only breaks exact ties),
  really good beer (model called it vague → NEEDS_MORE_INFO)

**Next single change:** don't let `is_specific` alone skip the search, and give a city
match more weight than a tie-break. Re-score.

**Concepts learned:** structured output via forced tool use, REST API from Python (SDK),
component-level evaluation, teaching to the test, freezing model outputs, deterministic
tie-breaking, virtual environments and activation

### Day 6 — 2026-10-28: Search v2 tested, v1 kept

- `12_score_search_v2.sql`: retrieve top-20 candidates once, re-rank cheaply; tested two
  changes separately against v1 as the control

  | | top-1 | recall@5 | gained | lost |
  |---|---|---|---|---|
  | v1 (control) | 6/10 | 9/10 | — | — |
  | v2a: vague note still searched if an exact registered name exists | 6/10 | 9/10 | really good beer | pool guy → **POOL LLC** (confident wrong) |
  | v2b: v2a + city ranks first | 5/10 | 9/10 | — | Surfside (invented city promoted SURFSIDE TRUST) |

- Hughes is **genuinely ambiguous**: HUGHES FINANCIAL GROUP and HUGHES FINANCIAL PARTNERS
  are both in Ponte Vedra Beach. The note can't tell them apart → a shortlist case
- The invented city "Surfside" was harmless while city only broke ties, harmful once city
  got weight: upstream errors change cost when downstream rules change
- **Decision: keep v1.** Errors aren't equal: an unnecessary "can you add the city?" costs
  seconds; a confident wrong company costs trust (and maybe money). v1 makes the cheap
  error, v2a the expensive one
- At 10 cases each rule change flips ~1 case each way → stop tuning; grow the test set

**Concepts learned:** retrieve-then-rerank, asymmetric error costs, inherent ambiguity,
component interactions, when an eval set is too small to decide

**First end-to-end report** (`src/datum/report.py`): note → Claude extraction → top 5 from
Snowflake (Python driver, same `datum` key-pair connection) → confidence LEVEL + evidence
(Strong / Likely / Possible, no percentages until calibrated) → pick → one-page report saved
to `data/reports/` (git-ignored)
- `ferguson ac boynton beach` → #1 [Likely] FERGUSON AIR CONDITIONING & REFRIGERATION, INC.,
  "name is similar (91/100); city matches; ACTIVE" → report P98000033661 ✅
- Seen: other FERGUSON names also score 90–91 (Jaro-Winkler rewards the shared start), so
  the evidence level, not the score, separated the right one
- Mart now carries street address + ZIP (dbt build 8/8: 2 models, 2 seeds, 4 tests)
- Manual testing found three flaws, all fixed in `report.py`:
  - **No exit:** a vague note asked "add more" forever → now Enter/"idk" stops, max 3
    asks, and it ends with "I won't guess"
  - **Wrong company as fact:** picking #1 on an all-"Possible" Cinemark list produced a
    clean report on CINEMA WORKS (inactive since 1980) → a Possible pick now needs a
    deliberate `y` (Enter = No)
  - **Lost context:** every report now records how the company was identified (note,
    level, evidence, chosen by the user)
- Also seen: the model returns different fields for the same note on different runs
  ('Pool' / '<UNKNOWN>' / ''); the decision field `is_specific` stayed stable
- Parking lot: search by street (the model reliably extracts "Race Track Rd")

### Day 7 — 2026-11-04 to 11-06: Lien recon, Duval bulk feed, Claude Code harness

**Duval (county liens)**
- Phoned the Clerk; told to email public.info@duvalclerk.com. Sent the Chapter 119 request Nov 4, 2:13 PM
- **Clerk replied in 51 minutes: the full bulk recording index (every public recorded document), free, over their secure FTP server.** Accepted Nov 5 and asked for the layout, update frequency, terms of use and account requirements
- New decision d21 replaces d17: Duval liens come from the bulk feed, not hand collection

**Federal tax liens (Sunbiz)**
- Pulled the four quarterly files (snapshot **2026-10-03**) and the 2026-11-04 dailies; saved the official layout
- Every line is exactly its documented length: filings 82, debtors 206, events 135, secured 206 (+CRLF in quarterly, LF in daily)
- **20,444 liens, all active:** the quarterly filings file drops released liens. Releases arrive as `COR` events in the daily events file
- **No document number, no FEIN, no dollar amount** anywhere → linking to companies must use name + ZIP5 (d19)
- Debtors are businesses: 22,171 of 22,173 corporate; ~6,400 LLCs (LLC liens do land here). 28 old liens have impossible expiry years (2510, 9211)
- Written up in `docs/access/sunbiz_flr.md`
- My `wc`/`awk` loops skipped the quarterly files: zsh globs are case-sensitive, and `*.txt` doesn't match `FLRF.TXT`

**Secrets and tooling**
- `ANTHROPIC_API_KEY` moved from `~/.zshrc` to `~/datum/.env` (gitignored); `extract.py` loads it with python-dotenv
- Installed the Claude Code CLI (native installer); ruff and pytest into `.venv`

**Claude Code harness (built by Claude Code, reviewed here)**
- `CLAUDE.md`: "Commands that prove work" section
- Secrets locked: deny rules in `.claude/settings.json` + a PreToolUse hook that blocks any shell command mentioning `.env`, `profiles.yml`, `.snowflake` or `.p8` (13 test cases)
- Stop hook: `ruff check src` + `dbt parse` before Claude may finish. Proved `dbt parse` never connects by running it against a fake account (`invalid.invalid`): it succeeded
- `ruff.toml` pins lint rules to E4/E7/E9/F: ruff 0.17's default grew to 407 rules, including import-order style
- Prompts now live in `docs/prompts/` (pasting long prompts into the terminal was unreliable)

**Decisions:** d15 (MVP scope, launch-ready Nov 13), d16, d18, d19, d20, d21 approved; d17 replaced by d21.
Use the Claude Code VS Code panel by default; the terminal only for CLI-only features.

**Concepts learned:** hooks (PreToolUse, Stop), deny rules, guardrail vs boundary, pin tool defaults,
proving a negative with a fake profile, snapshot vs event files, case-sensitive globs, secrets in `.env`

### Day 8 — 2026-11-11 to 11-18: Phase A built by an agent, reviewed, and ruled on

**How the work changed.** From Nov 11 the build split in two: Fable 5.2 builds Florida in Claude Code from
`docs/prompts/florida_master.md`, one branch and pull request per leg; I review each leg and own the decisions,
matching rules, privacy calls and hand checks. Georgia is on hold.

**Phase A (built Nov 12, 1:38–8:56 AM, unattended; about 0.31 credits)**
- **A1 federal tax liens:** script 13, 4 raw tables, 4 staging views. 20,444 filings, 22,173 debtors, 97,256 events,
  20,448 secured parties; every line its documented length; all 29 daily releases join to the snapshot
- **A2 DBPR licenses:** script 14, `dbpr.py` (download, then validate before loading), 2 raw tables, 2 staging views.
  263,337 license rows and 6,457 discipline rows. The real key is occupation code + license number
- **A3 Duval County:** script 15, `duval.py` (SFTP download, then check each file against its `EOF` count), 4 raw
  tables, 4 staging views. 2,703 of 2,716 files loaded (3.6M rows); 13 set aside because a line break inside a
  legal description split one record across lines
- 49 dbt models and tests ran: 0 failures, 5 warnings, each explained in the leg reports (`docs/legs/`)

**Review and rulings (Nov 12–18)**
- Leg A1 check 2: the snapshot filter sits in the `ON` clause, not `WHERE`, or the check could never fail
- Measured which side of a Duval record is the debtor instead of assuming it: **TO = debtor, FRM = creditor**,
  the opposite of the grantor/grantee guess. Evidence table in `docs/phase_b_rulings.md`
- 26 rulings (R1–R26) settle every open question from the three legs; 24 questions parked in
  `docs/open_questions.md` for counsel, the sources, or after launch
- Phase B brief rewritten as four stacked legs (B0 close gaps, B1 links, B2 flags, B3 hand-check samples)

**Things that broke, and why**
- Snowflake trial expired Nov 15. Added a card and upgraded the same account (pay only for use; no rebuild needed)
- Moved the repo to `~/Work Streams/datum`. The virtual environment stores its own absolute path, so `pytest` and
  `pip` pointed at a folder that no longer existed. Fix: a symbolic link `~/datum` → the new location
- The A2 branch carried an early copy of `docs/decisions.json`, which conflicted with the newer one on `main`.
  Fixed by merging `main` into the branch and keeping `main`'s copy
- The repo is now public (for interviews). Scanned every branch and the full history: no secrets, no keys

**Concepts learned:** LEFT JOIN filters in `ON` vs `WHERE`, a check that can't fail proves nothing, allowlist vs
blocklist, verify a convention with the data, control totals (`EOF` trailers), add/add merge conflicts, stacked
branches, virtual environments aren't relocatable, symbolic links, on-demand billing

### Day 9 — 2026-11-18 to 11-19: Phase B built, a review process set up, and the first Deep review

**The short version.** Phase B is on `main` except for its last leg. The build agent wrote four legs on
Nov 18, and three of them are merged: B0 closed the gaps left by Phase A, B1 linked each record to a company,
and B2 turned the confirmed links into flags. This was also the day the project got a written review
process, and pull request 6 was the first change to go through all of it.

**What merged, in order**
- **Nov 18, pull request 4 (leg B0):** the Duval files that needed a line-break repair, the daily lien files,
  the fetch manifest (the record of when each source file was downloaded), `requirements.txt`, and a DBPR
  header check.
- **Nov 18, pull request 5 (leg B1):** the four link models. Each link is CONFIRMED, AMBIGUOUS or NO_MATCH.
- **Nov 19, pull request 8 (the review system):** `REVIEW.md`, the risk tiers, the `reviewer` helper agent on
  Opus, the automated checks on GitHub, and `docs/review_log.csv`. I read `REVIEW.md` and pointed out that it
  did not say why each path is in its tier, and that section was added before I merged.
- **Nov 19, pull request 6 (leg B2):** the `company_flags` table that a report will read. The leg report
  counts 24,465 flags on 12,295 companies, and 9,972 of those flags may be shown.

**The Deep review of pull request 6**
- **Round 1.** Three reviewers on Opus read the change separately, and a fourth tried to disprove what they
  found. Two Important findings survived, along with three nits and one problem that was older than the change.
  - A federal lien closed only when its release had a readable date. A release whose date could not be read
    left the lien open, which means a contractor would have seen a lien that had been paid off.
  - The DBPR flags cited a search page that no ruling allowed.
- **Two rulings answered it.** R27 says a DBPR flag cites the address DBPR itself documents, always with the
  license number. R28 says un-hiding a flag takes two reviewed edits, the switch and the test.
- **The fix run.** The build agent fixed each finding in its own commit with a test that fails on the old
  code: 16 commits, about 0.29 Snowflake credits. All 95,488 certificates of release in today's data have a
  readable date, so the lien bug was real but had shown nothing wrong yet.
- **Round 2.** One reviewer read only the fixes and found no Important finding and three nits. I read the three
  files that hold the decisions, explained the lien rule back, and merged.

**Pull request 7 (leg B3) is reviewed and still open.** It holds the two scripts that draw the samples for my
hand checks. Its review found one Important finding: script 19 still sends the DBPR rows to the old search
address, because the branch was written before R27. It gets fixed before I do the hand check.

**Things that went wrong, and what they taught**
- The Claude Code panel went quiet in the middle of the fix run and I said "fixed". It was not finished: it
  was waiting on its own `reviewer` helper agent, and it added 5 more commits afterwards. A run is finished
  when its last message says it pushed, not when the panel stops moving.
- Claude (in the chat) pushed the first 11 commits early because of that. No harm was done, because the later
  commits sat on top of the same history, but the lesson is the same one.
- A helper agent uses the model named in its own file under `.claude/agents/`. If the file names no model,
  the helper uses whatever model the main session is on.

**Still open from the review of pull request 6**
- The test that keeps people's names out of the marts skips the whole `ENTITY_LOOKUP` table. It should skip
  only the two columns that hold registered business names.
- A lien closed by a release with an unreadable date needs its own sentence in the report. I approved this
  wording: "A certificate of release is on file. Its filing date could not be read from the state's file."
- Question Q25 in `docs/open_questions.md`: a garnishee (for example a bank ordered to hand over a debtor's
  money) sits on the same side of a Duval judgment as the debtor. It must be settled before Duval flags are shown.

**Concepts learned:** risk tiers set by the files a change touches, fresh-context review, the
builder-and-critic loop, deciding on whether a record exists and not on one of its values, a test that reads
the same switch as the code it tests, `is distinct from`, `count_if`, a full ordering for `row_number()`

---

### Day 10 — 2026-11-20 to 11-23: stricter link rules merged, Phase C started and stopped at a speed check

**The short version.** Three pull requests merged on Nov 20, the build agent ran Phase C overnight, and it
stopped where the brief told it to: the search works and misses its speed target. Most of these four days
went into understanding what was built and into making reviews something a person can actually do.

**What merged on Nov 20**
- **Pull request 13 (leg C0):** rulings R29 and R30 made the linking rule stricter. 625 links moved from
  CONFIRMED to AMBIGUOUS and none moved the other way.
- **Pull request 10:** the secrets guardrail, after a Deep review.
- **Pull request 14:** the full Phase C brief, in four legs, with ten working rules (W1 to W10).

**Phase C, run unattended on the night of Nov 20**
- **Leg C1 (pull request 15, merged Nov 24):** the four tables the app reads. Every check passed.
- **Leg C2 (pull request 16, open):** the Postgres copy and the search. The copy matches Snowflake row for
  row, and the search scored at least as well as Snowflake on the 10-case test set. Its speed missed: a p95
  of 1,229 milliseconds against a target of 1,000. The agent recorded the numbers and stopped.
- **Legs C3 and C4:** not started.

**What went wrong, and what changed because of it**
- Something checked out `main` in `~/datum` during the run, and four commits landed on local `main`. Nothing
  was pushed. The rule now: no git command that changes the checkout while an agent is working in a folder.
- I merged pull requests 13 and 10 before the explain-back the High tier asks for. I answered the three
  questions for 13 afterward and had one of them backwards (what R30 uses its looser key for).
- The leg reports were too long for me to review. Pull request 17 makes every pull request start with a
  Human review section of at most 250 words.
- On Nov 24, pull request 19 moved the briefs, the review process, the rulings and the plan, which an
  unattended agent builds from, to High tier.
- On Nov 24 I decided the study guide follows credit-stream again: `INTERVIEW_ANSWERS.md` is to become
  private, and the other files stay public. A separate change takes it out of git.
- The `datum-dev` API key was due to expire on Nov 26. I made a new one and put it in `.env`.

**Decisions**
- Keep the 1-second p95 target and try a narrow search table. Revisit if the narrow table also misses.
- Stay on API keys for local work. Revisit identity federation when the app is deployed.

**Concepts added to `CONCEPTS.md`:** where a session runs, API keys and rotation, environment variables,
fetch and pull, one folder one branch, percentiles, the complement rule, trigram indexes, OLAP and OLTP,
vertical partitioning, near-namesakes, the Human review section, where instructions live, risk tiers for agent instructions, and where context lives.

---

## Next

**Nov 19:** dates are targets, not deadlines. When work slips, the dates move and the scope stays.

| Target | Ships |
|---|---|
| Nov 19 | Fix and merge pull request 7 (leg B3); hand-check `evals/link_sample_20.csv` (0 wrong allowed) |
| Nov 20–21 | Verify the 40 draft test cases; the two follow-ups from the review of pull request 6 |
| Nov 22–25 | Phase C: Postgres serving, FastAPI app, offline tests |
| Launch-ready | Moves as needed; counsel review of Q1–Q6 in `docs/open_questions.md` comes first |

Later: name matching to 90% on 50 real inputs, dissolutions via the corporate events file,
move the snapshot date into raw at COPY time before the January 2027 snapshot.

---

## Parking Lot (deliberately not doing yet)

- **Hook test gap:** `tests/hooks/test_offline_checks.sh` runs without `ruff.toml`, so nothing proves
  unsorted imports pass. Fix: link `ruff.toml` into the temp project, add an unsorted-imports case
- **Harness extras deferred:** skills (teach-mode, new-snowflake-script, close-out), CLAUDE.local.md,
  pre-push hook protecting `main`
- `FLRreadme.txt` (2013) on the Sunbiz server: not pulled yet

- **Automate the daily pull in Python** (SFTP with `paramiko`, load with the Snowflake
  connector) instead of manual `sftp` + upload
- **REST API ingestion where a source actually offers one:** CourtListener (federal
  bankruptcy, v1.1), Trellis (courts, v1.1, paid). Interview feedback asked for API
  ingestion; don't force it where bulk files are the better path
- Fictitious names (DBAs), federal tax liens, DBPR contractor licenses
- Name normalization beyond `name_key` (strip LLC/INC, expand abbreviations)
- PROD environment (when the web app reads data)
- Installing `snow` scripted loads / scheduling

---

## Open Questions

- Does a federal lien `COD` (certificate of discharge) clear the lien, or release specific property only?
- Exact per-record Sunbiz URL for a federal lien (for report citations)
- Duval bulk feed: layout, update frequency, terms of use (asked Nov 5)

- **Events file recon** (`doc/cor/events/yyyymmddce.txt`): needed to catch dissolutions
  between quarterly snapshots. Before launch.

- What does the date at positions 473–480 mean? (Some values are future dates —
  likely an effective date, not the filing date)
- ~~Does the quarterly snapshot include inactive companies?~~ **Yes:** 9.17M inactive vs
  3.82M active (2026-10-22)
- How does each report line link to the official record? (Sunbiz detail URLs need a
  GUID that isn't in the bulk file)
- Snowflake trial ends ~Nov 15 — upgrade decision
- The website shows statuses beyond A/I (`NAME HS`, `CROSS RF`, `INACT`, `InActive`).
  What do they mean, and where do they live in the bulk files?
- City casing is inconsistent (`Boynton Beach` vs `PALM BEACH GARDENS`) — normalize
  before matching on address
