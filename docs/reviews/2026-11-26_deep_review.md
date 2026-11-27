# Deep review: open pull requests, November 26, 2026

## Summary

1. This run reviewed the three open pull requests, 30 and 29 (both High tier) and 20 (Low tier), with one fresh-context reviewer each, ran the offline test suite (575 passed), and made four checks of its own.
2. It found 3 Important findings, 2 in pull request 30 and 1 in pull request 29, confirmed each against the code, and all three were fixed the same night; pull request 20 has 3 Nits and cannot merge until its row in `docs/review_log.csv` is moved.
3. The single most important thing to look at tomorrow is question Q64 in `docs/open_questions.md` on `leg/d3-name-search`: leaving AND and THE out of the every-word test (Q63) can put a near name above the exact name when no city is given, and only Andres can decide whether to accept that.

## Scope and method

- The run started at 20:50 EST on November 26, 2026, with a hard 15-minute timebox, so it stops at 21:05 EST.
- `gh pr list --state open` returned three open pull requests, so this run reviewed pull requests and skipped the bug hunt on `main` that the brief reserves for a night with none open.

| Pull request | Title | Branch | Size | Risk tier | Why that tier |
|---|---|---|---|---|---|
| 30 | Leg D4: the address search, finished | `leg/d4-address-search` (head `4ecabb5e`) | +2,784 / -263, 20 files | **High** | It touches `src/datum/report.py`, which `REVIEW.md` names as High, and `src/datum/wording.py` plus two templates, which decide the wording on a report |
| 29 | Leg D3: the name search finds the company | `leg/d3-name-search` (head `a038b4f2`) | +1,357 / -169, 14 files | **High** | It touches `src/datum/report.py` and `src/datum/wording.py` |
| 20 | Study guide: Nov 20 to 26, the public files | `docs/study-guide-nov24` (head `c63347fa`) | +377 / -0, 4 files | **Low** | It touches only the root study guide files (`CONCEPTS.md`, `PROGRESS.md`, `UNIX_COMMANDS.md`) and `docs/review_log.csv` |

- Each pull request went to one `reviewer` subagent with a fresh context, briefed on `REVIEW.md`. `REVIEW.md` asks for three reviewers and a verifier on a High-tier pull request; the timebox allowed one reviewer per pull request, so this report is a second look, not a replacement for each pull request's own High-tier gate.
- Findings are ranked Important, then Nit, then Pre-existing. Each one gives a file and line, what is wrong, and a concrete failure scenario.

## Checks this review ran (20:52 to 20:54 EST)

| Check | Result | Command |
|---|---|---|
| Offline test suite on pull request 30's head (`4ecabb5e`, which contains all of pull request 29) | ✅ 575 passed in 4.21 seconds | `source .venv/bin/activate && pytest -q -p no:cacheprovider` (the `-p no:cacheprovider` flag stops pytest from writing its cache folder, so the run leaves no files behind) |
| GitHub CI, pull request 30 | ✅ `offline-checks` passed in 27 seconds | `gh pr checks 30` |
| GitHub CI, pull request 29 | ✅ `offline-checks` passed in 25 seconds | `gh pr checks 29` |
| GitHub CI, pull request 20 | ⚠️ No checks ran on the branch | `gh pr checks 20` |
| Can it merge? | Pull requests 30 and 29: `MERGEABLE`, `CLEAN`. Pull request 20: `CONFLICTING`, `DIRTY` | `gh pr view <n> --json mergeable,mergeStateStatus` |

Three facts about how these pull requests relate, each checked with git:

1. ✅ **Pull request 30 contains all of pull request 29.** Leg D4 was built on top of leg D3: D3's head commit `a038b4f2` is an ancestor of D4's head `4ecabb5e` (`git merge-base --is-ancestor a038b4f2 4ecabb5e`), so pull request 30 is D3's 13 commits plus 18 of D4's own. Merging 30 also merges everything in 29. The safe order is 29 first, then 30, each with a merge commit as pull request 28 was. A squash merge of 29 would leave 30 holding D3's original commits and could produce conflicts.
2. ✅ **Pull request 20 cannot merge as it stands.** Its branch starts 127 commits behind `origin/main` (merge base `94e55946`), and the one file both sides changed since then is `docs/review_log.csv`. 🟡 GitHub does not run `pull_request` workflows while a pull request has a merge conflict ([GitHub docs, "Events that trigger workflows"](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#pull_request)), which would explain the missing checks; this run did not open the workflow history to confirm it. Fixing it means rebasing or merging `main` into the branch and keeping both sides' rows in the review log.
3. ✅ **Your local `main` is stale.** Local `main` is `ccef8da` and `origin/main` is `143d82c`, three commits ahead (pull request 28's merge). A local `git diff main...<branch>` therefore shows extra changes that are already on GitHub. Run `git checkout main && git pull` before comparing against `main` tomorrow.

One disclosure: to let the reviewer read pull request 20, this run ran `git fetch origin docs/study-guide-nov24`, because the local copy of that branch pointed at an older commit (`336fedf`) than the pull request's head (`c63347f`). A fetch updates git's record of the remote branch and changes no file, branch or commit of yours.

## Pull request 30: Leg D4, the address search, finished (High tier)

Reviewer result: **2 findings: 2 Important.** The reviewer read D4's 18 commits (`git diff a038b4f2 4ecabb5e`). This run then checked both findings against the code; what it confirmed is marked ✅.

### Important

**1. `src/datum/wording.py:353`: the line printed on every address-found report still describes the old comparison.**

- The line: `"from {fields} · found by its principal address on record (the same house number, and a street name made only of words that were typed) "`
- What is wrong: leg D4 (rule S15) now leaves out of both the record and the note the seven office unit words with the number after them (`OFFICE_UNIT_WORDS` at `src/datum/search.py:94`: STE, SUITE, BLDG, FL, FLOOR, RM, ROOM) and all twelve directions (`DIRECTIONS` at `src/datum/search.py:90`). So a company can be listed while words in its stored street, such as NORTH or BLDG 9, were never typed. Round 1 of D4's review (commit `c42e235`) removed the same phrase, "made only of words you typed", from three other address sentences for exactly this reason, and left it in this one. This is the line the report a contractor keeps carries (`identified_by_address_text()`, `src/datum/wording.py:463` to `:468`). ✅ This run confirmed the constant's text, both word lists, and that the D4 diff removes the phrase elsewhere and not here.
- Failure scenario (the reviewer's, with invented values; 🟡 not executed by this run): a user types `100 example st bldg 2 apt 305`. A company's record reads `100 EXAMPLE ST BLDG 9 APT 305`, an apartment in a different building. The cut turns both into the same street, so the company is listed, the user picks it, and the report says its street name was made only of words that were typed, although `9` never was. The report presents another building's address as the same one, which is the "it accuses" failure in `REVIEW.md`: a match shown as stronger than its evidence.
- Three tests pin the sentence's text and none tests whether it is true: `tests/test_web.py:662`, `tests/test_report_builder.py:386`, and the new D4 test at `tests/test_report_cli.py:424`.
- The check that would catch it: build a report for an invented record whose street holds an untyped `STE 300` or `NORTH`, and assert that its identification line makes no "made only of words that were typed" claim; or a wording test that fails when any constant other than `ADDRESS_COMPARED` describes the comparison.
- Context: the phrase was already loose before D4, because since November 25 (commit `9003348`) the comparison skipped the kind of street and N, S, E or W. D4 widened the gap to unit numbers and the spelled-out directions, which is why it counts against this pull request rather than as pre-existing.

**2. The Human review section of pull request 30 says something the diff does not support.**

- The sentence: "after round 3 the comparison got one description, `ADDRESS_COMPARED`, which the results page and the "no match" page both show. Read those sentences line by line." The same claim is the code comment at `src/datum/wording.py:272`: "THIS IS THE ONE DESCRIPTION OF THE COMPARISON."
- What is wrong: `IDENTIFIED_BY_ADDRESS` (finding 1) is a second, shorter description of the comparison, and it sits on the report itself. `docs/review_process.md:36` makes a Human review sentence the diff does not support an Important finding.
- Failure scenario: Andres reads the two pages line by line, as the section tells him to, signs off, and never reads the report's line, which is the one that is wrong.
- The check that would catch it: the same wording test as finding 1.

### Nit and Pre-existing

None reported.

### What the reviewer checked and found clean

- Each new test it checked can fail on a named input. For example, `test_the_loaders_pattern_and_the_python_rule_cut_every_street_the_same_way` fails if the Postgres pattern and `without_office_units()` disagree on any of its 71,048 streets.
- The Python cut and the Postgres pattern agree on the edge cases it traced: `STE STE 5`, FLOOR against FL, STEVENS after STE, a unit word at the end, and an empty street.
- No personal data: the street repeated in the new lines of `tests/test_report_cli.py` (about lines 336 to 355) is a business's address that was already committed on `main` in `docs/prompts/florida_master.md` and `pipeline/seeds/extracted_inputs.csv`, and it is not one of the draft cases.
- It also ran the tests: 575 passed, the same as this run.
- Not checkable from the diff, and not contradicted by it: "30 of them new" (the diff adds 16 test functions and removes 1, and parametrized cases make up the rest), the 27 deliberate breaks, the agreement counts, the timings, the live check, and "no hand-checked case got worse".

## Pull request 29: Leg D3, the name search finds the company (High tier)

Reviewer result: **1 finding: 1 Important.** The reviewer read the whole pull request (`git diff origin/main...a038b4f2`) and ran the head commit's `search.py` on invented companies. This run read the four lines below at `a038b4f2` and confirmed the logic (✅); it did not rerun the reviewer's scenario.

### Important

**1. `src/datum/search.py:262` with `:318` and `:333`: a typed "and" or "The" can push the right company off first place.**

- The lines: `typed = (without_suffixes(search_key) or search_key).split()` (line 262); `return (not candidate.every_word, not city_agrees_for_order(candidate), -candidate.similarity, candidate.company.document_number)` (line 318); `RANK_ORDER = by_words_then_city` (line 333). The same test runs before the 200-name cut, at line 533 (rule S11).
- What is wrong: `name_key()` (line 192, `re.sub(r"[^A-Z0-9]+", " ", name.upper())`) turns "&" into a space, so a registered "A&B ROOFING LLC" never holds the typed word AND, and a registered name never holds a typed leading THE that it does not spell out. Since this pull request, "holds every typed word" outranks both the city and the similarity, so any company that happens to spell out the connector or the article goes above the right one, however close the right one's name is. ✅ Confirmed by reading the code at `a038b4f2`.
- Failure scenario (run by the reviewer on invented companies): typed "A and B Roofing", city Tampa. The new order puts "ALPHA AND BRAVO ROOFING A B HOLDINGS OF NORTH FLORIDA INC" (Ocala, similarity 73, Possible) first and "A&B ROOFING LLC" (Tampa, similarity 80, Likely) second; search version 1's order put the Tampa company first. The match levels stay honest and the order sentence shows, but the first card is the wrong company.
- How sure: the ranking is certain. Whether it leads to a false report depends on a contractor picking the first card and accepting a Possible match, so the Important tag, rather than Nit, is a judgment call that the reviewer flagged itself.
- The check that would catch it: a `tests/test_search.py` case asserting that `rank()` puts "A&B ROOFING LLC" in Tampa first for typed "A and B Roofing", city Tampa, against a longer name elsewhere that spells out every word, plus a twin for typed "The Acme Group" against "ACME GROUP LLC". 🟡 Both should fail today; no test in the repo types "&", "and" or "the" into a name search.
- Leg D4 does not fix it: the same test is unchanged on disk in pull request 30 (now near line 279), so the fix belongs in pull request 29 and flows into 30.

### Nit and Pre-existing

None reported.

### What the reviewer checked and found clean

- Rule 3: no fact type can be built without its source address and UTC fetch time (`Company.__post_init__` is unchanged), and no match level or outcome is turned into a true or false value.
- Legal suffixes (L.L.C., Inc., Incorporated, Corp, Co) and empty or blank cities behave as the tests say.
- Every new function and branch has a test that fails on the old behavior. One caveat: the rule S11 SQL is pinned as text only, so whether Postgres and Python agree rests on the leg's live measurement, as the test's own comment says.
- Every sentence of the Human review section that can be checked against the diff holds, including the count of 15 new tests. Its live-run numbers cannot be checked offline.
- No person's name, email, phone number or home address in code, tests or templates. The draft case in `docs/legs/d3-name-search.md:509` is already on `main` in `docs/prompts/florida_master.md:408` (see this run's draft-case check below).

## Pull request 20: Study guide, Nov 20 to 26 (Low tier)

Reviewer result: **3 findings: 0 Important, 3 Nit.**

**Nit 1. `docs/review_log.csv:18`: the pull request's own row conflicts with `main` and describes an older version of the pull request.** Since the merge base, `main` inserted row 16 and appended rows 21 to 28 right where row 20 goes, which is the conflict GitHub reports. The row also says 278 lines added where the pull request now adds 377, "Nov 20 to 24" where the title says Nov 20 to 26, and round-1 counts that do not cover the 99 lines added by the last five commits. Failure scenario: the log, which the Datum Roadmap dashboard's Reviews tab reads, records 278 reviewed lines for a 377-line merge, so the review-coverage measure overstates what a review round saw. The check: compare `git diff --shortstat origin/main...c63347fa` with the row's `lines_added`. The fix: place row 20 between rows 19 and 21, which also keeps it clear of rows 29 and 30.

**Nit 2. `UNIX_COMMANDS.md:180-181`: "`git worktree add --detach <folder> origin/main` makes a second working folder for the same repo, at the newest `main` from GitHub."** ✅ `origin/main` is only as fresh as the last `git fetch`, and `git worktree add` does not contact GitHub. Failure scenario: Andres runs only this line a day after his last fetch and reviews an old `main` believing it is current, which is the same stale-reference problem this run hit with pull request 20's branch. Suggested wording: "at `main` as of your last `git fetch`".

**Nit 3 (🟡 uncertain). `UNIX_COMMANDS.md:164`: `env -u ANTHROPIC_API_KEY claude rc`.** The reviewer found no `rc` command in `claude --help`, which lists Remote Control as the flag `--remote-control [name]` (and `/rc` inside a session). If that holds, `claude` takes "rc" as the first prompt, and the phone cannot reach the session. Suggested line: `env -u ANTHROPIC_API_KEY claude --remote-control`. Check it with `claude --help | grep -i remote` before changing it.

Clean: no secret, email, phone number or person's name in the 377 lines; the paths, rulings, question numbers and figures it checked match `main`; the other command explanations are correct for macOS with zsh.

## How the reviewers worked, for the record

The reviewers edited no repo file. Two went beyond their git-only tools, all read-only: pull request 30's reviewer ran the test suite; pull request 20's reviewer ran `claude --help`, `ls -ld ~/datum`, and `grep -c` on the two git-ignored draft files, which prints counts and no content. Pull request 29's reviewer left scratch copies of the head commit's modules and its probe scripts in this session's temporary scratchpad folder, outside the repo.

## Check by this run: draft search cases copied into committed files

Why this check: `.gitignore` keeps `evals/draft_cases.csv` and `evals/draft_extracted.csv` out of git because "an unchecked address may be someone's home" (working rule S1). A script compared every value of 10 or more characters in the three git-ignored draft files against the lines each pull request adds, and printed only positions, never the values. It matches exact text only, so an address copied with different spacing or abbreviations would slip past it.

Result: ✅ no draft **address** appears in any of the three pull requests. One draft case does: the brand-and-place search that question Q55 discusses, with its expected document number and expected company name.

- **Pre-existing, `docs/legs/d3-name-search.md:26`, `:472` to `:509`, `docs/open_questions.md:72` and `:76`, `docs/review_log.csv:27` (pull request 29, and so pull request 30).** What is wrong: these lines quote a git-ignored draft case word for word. The same three values were already on `origin/main` before either pull request, in `docs/prompts/florida_master.md`, `docs/legs/d1-contractor-search.md`, `docs/open_questions.md` and `tests/test_search.py`, so the brief itself quotes the draft and later legs copy it from there. Failure scenario: this case is a company's trade name and a place, not a home address, so it exposes nothing personal today; the risk is the habit. The next leg that quotes a draft the way these lines do could quote an address-search draft, which is exactly the case rule S1 exists for, and nothing would stop it. The check that would catch it: a test in `tests/test_evals_run.py` (which `.gitignore` says already checks these draft files; 🟡 not opened in this run) that fails when any draft value appears in a tracked file, or the same comparison this run made, run before each push.

## Check by this run: length of the Human review sections

- **Nit, the `## Human review` section of pull requests 29 and 30.** `docs/review_process.md:31-33` says the section is "usually 300 to 600 words" and that Andres "reads it in under 5 minutes". Measured from each pull request body (`gh pr view <n> --json body`, the text from `## Human review` to the next `##` heading): pull request 30's section is 1,391 words and pull request 29's is 1,474, more than twice the usual top. At a typical silent reading speed of about 240 words a minute that is 6 minutes each, before any time spent explaining it back. Failure scenario: the section is the one part a person is sure to read, and a long one is skimmed, so a decision buried in it is missed. Pull request 20's section is 144 words. The check that would catch it: a word count of the section in the last review round, against the range the process doc gives.

## Check by this run: what the file lists alone settle

- ✅ No pull request touches `pipeline/` or `snowflake/` (`git diff --name-only origin/main...4ecabb5e`, and pull request 29's files are a subset of pull request 30's). So `REVIEW.md` questions 3 (a name column past staging), 5 (Duval rows outside the allowlist) and 7 (a Snowflake statement that alters or drops an object) cannot be triggered by these changes.
- ✅ The extraction prompt lives in `src/datum/extract.py`, which neither pull request changes, so the brief's rule that legs D3 and D4 leave the prompt alone held.
- Not settled by the file list: question 2 (loaded row counts), because pull request 30 changes the loader `src/datum/load_postgres.py`. That is in the pull request 30 reviewer's diff.

## What this run did not get to

- **The full High-tier review.** `REVIEW.md` asks for three reviewers in parallel and then a verifier on pull requests 29 and 30. This run gave each pull request one reviewer, so a finding below is one agent's reading plus this run's spot check, not a verified result.
- **The security pass.** `REVIEW.md` says to run `/security-review` whenever `src/` changes, and both High-tier pull requests change `src/datum/`. It was not run in this review; it was run afterwards on the new `src/` lines of the fixes (see the last section).
- **The three questions check.** `docs/review_process.md` (rule added Nov 26) asks the last review round to answer the three questions from the Human review section alone. This run did not have the questions, so it did not do that check.
- **A second opinion on two tags.** Pull request 29's Important finding depends on a contractor accepting a Possible first card, and this run did not rerun either reviewer's executed scenario.
- **Leg D3's commits inside pull request 30.** The pull request 30 reviewer read only D4's 18 commits, because pull request 29's reviewer covered D3's 13. Anything that only goes wrong when D3 and D4 run together was in neither reviewer's brief.
- The run stopped at about 21:00 EST, inside the 15-minute timebox.

## What happened after the review (November 26, 2026, from 21:00 EST)

### Andres's decisions

- **Question Q63: keep leaving AND and THE out of the every-word test.** It also covers a registered name with no "&" at all, such as A B ROOFING, and a THE that a contractor types and the registered name lacks. It is recorded on `leg/d3-name-search` in `docs/open_questions.md` (commit `ae4fcdd`).
- **The approach does not need rethinking under `REVIEW.md`.** `REVIEW.md` says that Important findings remaining after round three mean "the approach needs rethinking". These findings came after round 3, from this separate review, and Andres ruled that both approaches stand: the D4 fix finishes round 3's own one-description approach, and the D3 fix narrows one word list.

### The commits

| Branch | Commit | What it does |
|---|---|---|
| `leg/d3-name-search` | `cc39913` | `typed_words()` in `src/datum/search.py` leaves AND and THE out of the every-word test, in `holds_every_word()` and in the words step 1's query reads. Its test's two pools put the wrong company first on the code before it |
| `leg/d3-name-search` | `ae4fcdd` | Question Q63, Andres's answer |
| `leg/d3-name-search` | `17e9a19`, `e972020` | Question Q64, the cost the review of the fix found, with a test that pins today's order for one example with THE and one with AND |
| `leg/d4-address-search` | `3f39e40` | The line a saved report prints for a company picked by its address now gives `ADDRESS_COMPARED`, the one description of the comparison, in place of its own shorter one |
| `leg/d4-address-search` | `e05c6d0` | The report names the house number the search compared (12 for "12-b"), and the builder refuses an address identification whose street holds none |
| `leg/d4-address-search` | `196776b` | The wording test is renamed to say what it checks: no string that `wording.py` names at its top level holds the phrase "made only of words". It does not catch the idea restated in other words, text inside a tuple or a function, or a template |
| `leg/d4-address-search` | `967b103`, `464a252`, `b5a5728` | Merges that bring each commit of leg D3 above into leg D4 |

The paperwork followed in `ed6bc46` (leg D3's report, section 7, and its row in the review log), `241da35` (its merge into leg D4) and `82cf85b` (leg D4's report, section 7, and its row). The Human review sections and descriptions of pull requests 29 and 30 were brought up to date on GitHub.

### The checks, run again, beside their targets

| Check | Target | Result |
|---|---|---|
| Leg D3, the evaluation (`python -m evals.run --backend postgres`) | The leg's own scores | ✅ The same: 10 of 13 checked cases first, 12 among the first five, 2 wrong matches |
| Leg D3, the gate of rule S17, with `cc39913` as a step after `a038b4f` | No checked case worse than on `main` at `051a928` or than at `a038b4f`, by rank or on the page | ✅ None worse, and no draft case moved against `a038b4f` |
| Leg D3, rule S11 in the query against `holds_every_word()`, over the speed check's 210 searches | 0 differences | ✅ 0 of 558,647 names |
| Leg D3, the speed of the name search (`--latency 200`), first run after a Postgres restart | p95 under 1 second | ✅ 608 ms (599 ms on a second restart; 599 ms before the fix) |
| Leg D4, the gate, with `4ecabb5` as the step before | No checked case worse than on `main` or than at `4ecabb5` | ✅ None worse, and no draft case moved |
| Leg D4, the speed of the address search (`--address-latency 200`), first run after a restart | p95 under 1 second | ✅ 246 ms (252 ms on a second restart; 256 ms before the fixes) |
| The tests, with the Postgres server stopped | All pass | ✅ 547 on leg D3 (545 before), 579 on leg D4 (575 before). `ruff` passes on both |

No live extraction call was made, and no Snowflake warehouse was used. One more count: the fix changes nothing the evaluation can see. No checked case types AND or THE, and the 12 searches of the speed check that do kept the same 200 candidates and the same page.

### The High-tier review of the fixes

The review this report lacked was done for the fixes, at the High tier, in three rounds.

- **Round 1.** Three reviewers ran in parallel, each hunting one thing: a wrong company first or a sentence that claims too much, a person's data or a secret, and a test that cannot fail. A fourth then checked every finding against the code. It confirmed five and dropped none, and none was Important:
  - **A call for Andres, now question Q64.** With AND and THE left out, a near name that lacks the typed word joins the exact name's group, and with no city the similarity decides. For "Lords of the Lawn", LORDS OF LAWN (Possible) now comes before LORDS OF THE LAWN L.L.C. (Strong). No sentence becomes false, and the page says the list is in search order. The fourth reviewer found that the order cannot change without a new matching rule, and the one narrow rule it found would need the gate. The recommendation recorded with Q64 is to keep today's order until a checked case shows the problem.
  - **Pre-existing.** Step 1's `WHERE` still compares the whole typed name, THE included. In Postgres, "THE ACME GROUP" against ACME GROUP LLC scores 0.733, under the threshold of 0.75, so a short name can miss the 200 candidates. It is recorded in Q64.
  - **Three Nits, all fixed** (`e05c6d0`, `196776b`): the report's house number had an untested branch and nothing checking where it came from, and the wording test's name, with the message of `3f39e40`, claimed more than the test checks.
  - **A security review** of the new `src/` lines on both branches found no vulnerability.
- **Round 2.** One reviewer read the new commits, both Human review sections and the three questions of each leg. It found three Important problems, each a sentence of a section that said more than the facts, and two Nits. All are fixed, and all six questions were answerable from the sections.
- **Round 3.** Round 3 had one reviewer on the corrections. In pull request 30's section it found one Important problem, a count of merges ("two merges") that round 3's own merge had made stale, and one Nit, a sentence that read as if the wording test covered the collections of strings in `wording.py`. Both are corrected, and as three rounds is the most `REVIEW.md` allows, no round read those two corrections.

### What is still open

- **Question Q64** is Andres's decision.
- The fixes of leg D4's third review round were read by one reviewer only, in this deep review.
- The draft-case quoting and the long Human review sections, found above, are recorded here and not changed.
