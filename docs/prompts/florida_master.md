# Florida master brief (for Fable 5.2 in Claude Code)

Kickoff line Andres types: `Read docs/prompts/florida_master.md. Run Phase A only.`
Later: `Read docs/prompts/florida_master.md. Run Phase B.` then `Run Phase C.` then `Run Phase D.`, and on Nov 26 `Run legs D3 and D4.` Never start a phase or leg you weren't told to run.
Phase A finished Nov 12, 2026 (three legs, reports in `docs/legs/`).
Phase B finished Nov 19, 2026 (four legs). Leg C0 followed the same day and added rulings R29 and R30.
Phase C finished Nov 24, 2026 (legs C1 to C4: the marts the app reads, the Postgres copy and the search, the report, and the web app).
Legs D1 and D2 finished Nov 25, 2026 (the search by address and the report's summary). Legs D3 and D4 were added on Nov 26, because the name search still did not find the company Andres meant.

## 1. What you're building and for whom

Datum checks a small trade contractor's commercial client before a job: is it a real, active Florida company, and what's on the public record against it? You are building the Florida data pipeline and app. Andres Camacho owns the repo. He is learning data engineering through this project, so he reviews every leg and must be able to explain what you built. Write for that reader.

## 2. Read these first

- `CLAUDE.md` (rules and the commands that prove work)
- `docs/mvp_plan_nov8.md` (spec A1–A12, decisions d15–d21, architecture, flags table). Its dates are targets, not deadlines. Never cut scope to hit a date.
- `docs/access/sunbiz_flr.md` (federal lien layouts and verified counts)
- `snowflake/01`–`12` and `pipeline/models/` (the style to match)
- `docs/phase_b_rulings.md` (decided Nov 18; binding from Phase B on) and `docs/open_questions.md`
- `docs/legs/` (your own Phase A reports)

## 3. Rules for every leg

**Git**
- One branch per leg, named `leg/a1-federal-liens` and so on. One pull request per leg with `gh pr create`. Never commit to `main`, never merge, never force-push.
- One concern per commit, with its test.

**Code style**
- Snowflake SQL goes in `snowflake/` as the next numbered script (Phases A and B used 13–20, so the next free number is 21). Run it with `snow sql -c datum -f snowflake/NN_name.sql`.
- Comment every line. End each SQL script with `-- Syntax`, `-- Concept` and `-- Design decision` sections, like scripts 01–12. dbt models get the same header-and-inline style as `stg_sunbiz__cor.sql`.
- Raw = one `line` (or one column per field for delimited files) plus `source_file` and `loaded_at`. Staging names and types the fields. Never change or drop existing tables, models or seeds; only add.

**Writing** (added Nov 19, 2026; applies to everything Andres reads: leg reports, pull request text, review replies, your final message, commit messages and code comments)
- Write the way a patient colleague would explain it out loud, sitting next to him. He reads these to learn, so each sentence has to make sense on its own, even to someone who was not there when the work happened.
- Use complete sentences with a subject and a verb. Keep the connecting words that make them flow: "and so", "because", "which means", "the same day".
- Don't write clipped fragments, or a label followed by a colon. Not: "Re-planned Nov 2: hand-collected first. No retriever until counsel reviews the gate." Instead: "On Nov 2 the plan changed. The records would be collected by hand first, and so there would be no automated retriever until a lawyer had reviewed the disclaimer page."
- Say what each number counts and what each thing is. Spell out every acronym, and explain a technical term in a few words the first time it appears.
- Lead with the answer and don't pad. Fuller means each sentence carries its own context, not that there are more sentences.
- When there are several dated events, steps or open items, put each on its own line (bullets, a table or a timeline), never in one paragraph. Give a short summary first, then what is left, then the history.
- Mark a claim you could not check: ✅ verified, 🟡 unsourced, 🔴 assumed.
- Existing text: don't rewrite a file only to change its style. When you change a file for a real reason, bring the comments you touch up to this style. Never rewrite commit history or the text of a merged pull request.

**Safety**
- Never read, print or edit `.env`, `~/.dbt/profiles.yml`, `~/.snowflake/` or `*.p8`. Python reads secrets with `load_dotenv()`; nothing else touches them.
- `data/` is gitignored. Raw data never goes to git.
- Businesses only. Records about individuals may sit in raw and staging, and go no further: no intermediate model, mart, report or sample file may contain a person's name. Keep criminal judgments out of everything past staging.
- Inspect before loading: count lines, check record lengths or delimiters, and compare to the source's own totals before any `COPY`.

**Cost**
- Use only warehouse `datum_wh` (X-Small). Don't resize it, create another, or change the resource monitor.
- After each leg, record credits used (query `snowflake.account_usage.warehouse_metering_history` or `information_schema`) in the leg report.
- No new paid services or accounts.

**When to stop**
- A check still fails after two fix attempts: stop that leg, write the report with what failed, and move to the next independent leg.
- You need a credential, a login, a purchase or a product decision: stop and ask in the leg report.
- Anything about a source's terms of use, or the FCRA (Fair Credit Reporting Act): stop and flag it. Don't decide it.

**Review before the pull request** (see `REVIEW.md` and `docs/review_process.md`)
- When the leg's checks pass, set its risk tier from the table in `REVIEW.md`. The highest tier of any file it touches wins.
- Review the leg's diff in a fresh context with the `reviewer` subagent, which runs on Opus so the reviewer is a different model from the author:
  - Low: one pass.
  - Medium: one pass, plus `/security-review` when `src/` changed.
  - High: three `reviewer` subagents in parallel, each told to hunt one thing (a wrong link or wrong status; a person's data past staging; a test that cannot fail). Then a fourth checks every finding against the code and drops any it cannot confirm with a file and line.
- Fix every `Important` finding, or answer it with a one-line reason. Review again, looking only at the new diff. Three rounds at most; if `Important` findings remain after the third, stop the leg and say so in the report.
- Open the pull request with a `## Human review` section first (see below), then `.github/pull_request_template.md` filled in, then the leg report below it.
- The last review round also checks the `## Human review` section against the diff. The reviewer reads only the diff, so paste the full text of the section into its prompt. At High tier, give the section to the fourth agent, the one that checks the findings, and not to the three reviewers that each hunt one thing. A sentence in the section that the diff does not support, or a risk it leaves out that the leg report marks 🔴 or 🟡, is an `Important` finding. A sentence about the tier, the merge order or an open question is checked against `REVIEW.md`, `docs/open_questions.md` or the list of open pull requests, and not against the diff. The reviewer cannot see GitHub, so paste the output of `gh pr list --json number,title,headRefName,baseRefName` into its prompt together with the section.
- Add one row for the pull request to `docs/review_log.csv`.
- Never ask a question or wait for approval during review.

**Human review section**: the pull request body starts with `## Human review`. Andres reads it before anything else, in under 5 minutes, and it has to tell him everything he needs without opening the leg report: enough to explain the change back, answer the three questions and make his decisions. It does not replace reading the diff on a High-tier change. There it tells him what the change does and where in the diff to read line by line. The leg report below it keeps its full detail, because later agents read that. Nothing in the leg report is shortened to make room.
- Write it the way a colleague would explain the change out loud to someone who was not there. Use full sentences with a subject and a verb. Do not write a bold label followed by clipped fragments, such as "**Your decisions.** Dropping the old index, and a host for 5.5 GB." Write "The decisions that are yours", and then a numbered list in which each decision is a full sentence or a question, followed by the facts he needs to decide it.
- It is as long as the essentials need, which is usually 300 to 600 words, and at most 800 except in the one case below. Count the words outside code blocks, so the diagram does not count. The limit is on what goes in, not on how it is said: leave a detail out before you shorten a sentence into a fragment. The items under "What is not proven" are never the detail that is left out: shorten "What was built" and "If you open the code" first. If every item still cannot fit, go over the limit and say so in one sentence at the end of the section.
- It has these parts, in this order, each under a short bold heading on its own line:
    1. An opening with no heading: what the leg does and why, the risk tier and what that tier asks of him, and which pull requests to merge first.
    2. "What was built": a small diagram of the pieces and how data moves between them, as a `mermaid` code block, which GitHub draws as a picture. Under it, the two or three ideas the change rests on, each explained in plain words. A pull request that only changes documents has no diagram.
    3. "What is proven": the results, each with its number, what the number counts, and the check that produced it, described in plain words.
    4. "What is not proven": every 🔴 and 🟡 item from section 4 of the leg report, and any commit that no review round covered. The items that bear on his decisions come first and get a full sentence or two each. The rest may share one sentence that names each of them. None is left out.
    5. "The decisions that are yours": the numbered list described above. Each item says what he is deciding, what happens today, and what the other choice would change. Name an open question by its number only after saying what it asks.
    6. "If you open the code": at most three places that carry the judgment.
- Every part appears. When a part is empty, write one sentence that says so, for example "Nothing was assumed."
- It stands alone. Do not point at "check 3", "section 4" or "Q36" as if he had read them: say what the check showed or what the question asks, and then give the reference.
- Each technical term is explained in a few words the first time, and every number says what it counts.
- It states no fact about the change that is not in the leg report or the diff. Three things may come from elsewhere: what the tier asks of him (from `REVIEW.md`), the merge order (from the open pull requests), and what an open question asks (from `docs/open_questions.md`).
- It explains the ideas he needs for the three questions, and it does not quote the questions or their answers. The questions stay a check of his understanding.
- Each of the three questions must be answerable from this section alone (added Nov 26, 2026). On Nov 25 Andres could answer only one of pull request 24's three questions from its section, because review rounds 2 and 3 changed the change after the section was written, and he had to read the brief for the rest. So the last review round also gets the three questions, and the reviewer that is given the Human review section (at High tier, the fourth agent, the one that checks the findings) answers each one using only the section. A question that needs the leg report, the diff or another file to answer is an `Important` finding, and the fix is to add the missing idea to the section, never to make the question easier. The reviewer's answers are never written to the leg report, the pull request or `docs/review_log.csv`: a finding names the question and the idea that is missing, and not the answer.
- The pull request is public. Never name a person, and never give a street address or a secret. Name a company only when it is one of the repo's own test cases, and otherwise give a count and describe the case.
- For a pull request with no leg report, read "the leg report" in these rules as the diff and the filled-in template, and "What is not proven" lists what the author could not check. At High tier, add a `## Three questions` section at the end of the pull request body, with the questions and not their answers.
- The template's "What this changes" and "What a person should look at" must agree with this section. Each may be one sentence that points to it.
- Write it once the code is final and before the last review round, which checks it. If a fix in that round changes the code, bring the section up to date and include it in the next round.

**Leg report**: for every leg, write `docs/legs/<leg-name>.md` and put the same text in the pull request body:
1. What I built (files, tables, models), in plain English a new engineer could repeat out loud
2. Checks: each check, the command, and its pasted output
3. Decisions I made and why, with the tradeoff
4. What I couldn't verify, and open questions for Andres
   (include the review: tier, depth, rounds, and each finding with how it was answered)
5. Credits used
6. Three questions Andres should be able to answer after reviewing

## 4. Phase A: three sources, raw to staging

The three legs are independent. Run them one after another, each on its own branch from `main`.

### A1. Federal tax liens (Sunbiz)

Files are already in `data/raw/sunbiz/flr/`: quarterly `FLRF.TXT`, `FLRD.TXT`, `FLRE.TXT`, `FLRS.TXT` (upper case; globs are case-sensitive) and the `20261104` dailies.

Build:
- `snowflake/13_federal_liens_raw.sql`: 4 stages and 4 raw tables in `datum.raw` (`sunbiz_flr_filings`, `_debtors`, `_events`, `_secured`), reusing the `fixed_width` file format and `METADATA$FILENAME`. Each table holds quarterly and daily rows. `PUT` the 8 files with `snow sql -c datum -q "PUT ..."`.
- dbt sources plus `stg_sunbiz__flr_filings`, `_debtors`, `_events`, `_secured`, cut by the positions in `docs/access/sunbiz_flr.md`. Dates with `TRY_TO_DATE(x, 'MMDDYYYY')`. Add `source_kind` and `published_on` the way `stg_sunbiz__cor` does (quarterly snapshot date 2026-10-03).
- `stg_sunbiz__flr_debtors` keeps only `name_format = 'C'` (corporate).

Done when:
| Table | Quarterly rows | Daily 20261104 rows | Line length |
|---|---|---|---|
| filings | 20,444 | 42 | 82 |
| debtors | 22,173 | 46 | 206 |
| events | 97,256 | 29 | 135 |
| secured | 20,448 | 42 | 206 |
- dbt tests pass: `not_null` and `unique` on the filing document number per source file; `accepted_values` A/L/T on status; a `warn`-severity test that assessment and expiration years fall in 1990–2040 (28 known bad rows).
- Every `COR` event in the daily file joins to a filing in the snapshot (29 of 29).

### A2. DBPR (Department of Business and Professional Regulation) contractor licenses

Recon first, then build. Known starting points (verify them; don't trust them):
- Construction licensee extract: `https://www2.myfloridalicense.com/sto/file_download/extracts//CONSTRUCTIONLICENSE_1.csv`
- Discipline reports: `contractor_disc_lic_[fiscal year].csv` under `/pro/cilb/reports/`
- The licensee file is reported to exclude delinquent and involuntarily inactive licenses. Confirm and document.

Build:
- `docs/access/dbpr.md`: where the files are, the layout, update cadence, what's excluded, and what the site's terms and robots rules say about automated download. If they forbid it, stop and report.
- `src/datum/dbpr.py`: a small `DbprFile` class that downloads a file to `data/raw/dbpr/`, then validates it before anything is loaded (expected header, column count on every row, row count). One request per file, no retries in a loop.
- Next numbered Snowflake script: a CSV file format, stage, raw tables, `COPY`.
- `stg_dbpr__licenses` and `stg_dbpr__discipline`, with tests.

Done when:
- Rows in each raw table = data lines in the file (file lines minus header). Paste both numbers.
- License number is `not_null`; duplicates are either zero or explained in the report.
- The report states how many licenses are business-held versus individual-held, and which column tells them apart.

### A3. Duval County recorded documents

What's known (from four sample files Andres pulled by hand):
- Site `https://ftp.duvalclerk.com`, folder `Recording Indexes`. One set of files per day since 2019-07-31, published about 3 AM the next day.
- Pipe-delimited text, CRLF line endings, each file ends with a trailer `EOF|<row count>`. A 7-byte file is `EOF|0` (nothing recorded).
- `dYYYYMMDD01id.16` documents: `DDA|16|instrument|type code|type name|legal description|OR|book|page||pages|record date MM/DD/YYYY|time|amount|`
- `pYYYYMMDD01id.16` parties: `DPA|16|instrument|seq|FRM or TO|name|`
- `lYYYYMMDD01id.16` links: `instrument|book|page|OR|type|linked instrument|book|page|OR|linked type` (`NONE` when no link). A `RELEASE` linked to an `LN` means that lien was released.
- `mYYYYMMDD01d.16` document-type lookup: `code|family|`
- Daily files can contain old instrument numbers (re-indexing). Don't assume a file's date equals the recording date.

Access: Andres has put `DUVAL_FTP_USER` and `DUVAL_FTP_PASSWORD` in `.env`. Your download script reads them with `load_dotenv()` and never prints them. Work out the transfer protocol (try SFTP, then FTPS) with at most two attempts each. If neither works, stop and report; don't probe further. Use one connection, sequential downloads, and a short pause between files.

Scope: files dated 2025-01-01 onward.

Build:
- `docs/access/duval-recording-index.md`: protocol, file kinds, layouts, counts.
- `src/datum/duval.py`: download to `data/raw/duval/`, then verify every file's row count against its `EOF` trailer before loading. A mismatch fails that file loudly.
- Next numbered Snowflake script: pipe-delimited file format, 4 stages, 4 raw tables.
- `stg_duval__documents`, `stg_duval__parties`, `stg_duval__links`, `stg_duval__doc_types`, with tests (`not_null` instrument; relationships from parties and links to documents, `warn` severity because of re-indexed rows).

Done when:
- For every loaded file: rows loaded = its `EOF` count. Report the totals and any mismatches.
- The report lists document counts by type family for liens, judgments, releases, satisfactions, notices of commencement and lis pendens.
- The report says what share of party names look like businesses (LLC, INC, CORP and similar) versus individuals. This is a count only; write no names in the report.

Flag in the report, don't resolve: the Clerk has not yet answered whether terms of use apply to this data. Nothing from Duval is shown to anyone outside this repo until Andres says so.

## 5. Phase B: close the gaps, link to companies, then flags (only when told)

Read `docs/phase_b_rulings.md` before anything else. Its rulings R1–R26 are decided, and each bullet below names the ones it implements. Don't reopen them and don't ask about them. If the data contradicts a ruling, follow the ruling, and report the contradiction with counts in the leg report.

Run unattended. Never stop to ask a question or wait for approval. When something is unclear, take the most cautious reading (the one that shows less on a report), write the assumption in the leg report, and keep going. The stop conditions in section 3 still apply.

Four legs, in order. Each leg depends on the one before it, so stack the branches: `leg/b0-close-gaps` from `main`, `leg/b1-links` from `leg/b0-close-gaps`, and so on. One pull request per leg, each targeting `main`. Andres merges them in order.

Paths: the repo is at `~/Work Streams/datum`, and `~/datum` is a symbolic link to it. Use `~/datum` in commands so no path contains a space.

### B0. Close the Phase A gaps

- **Duval repair (R15).** For the 13 files in `data/raw/duval/rejected/`: write a repaired copy to `data/raw/duval/repaired/` with the same file name. Join a line that doesn't start with the record prefix to the line above it with one space; drop blank lines. The repaired row count must equal the `EOF` trailer, or the file stays out. Extend `duval.py` and its tests (a fixture with a broken record). `PUT` and `COPY` the repaired files with the next numbered script. Add a "Repaired files" section to `docs/access/duval-recording-index.md`.
- **Federal lien dailies (R8).** Download every daily `flrf`, `flrd`, `flre` and `flrs` file published since 2026-10-03 from the state's SFTP (secure file transfer protocol) server, using the public login the state publishes (see `docs/access/sunbiz.md`). Put the download in a small `src/datum/sunbiz_flr.py` with tests. Inspect line lengths before loading, then `PUT` and `COPY` into the existing four tables. One connection, sequential, a short pause between files.
- **Fetch manifest (R23).** Each downloader (`dbpr.py`, `duval.py`, `sunbiz_flr.py`) writes one manifest row per file. Load it into `datum.raw.fetch_manifest`, with a staging view. Backfill files already on disk from their modification time with `is_approximate = true`.
- **`requirements.txt` (R24)** with exact versions from the working environment.
- **DBPR header check (R25)** in `validate()`, with a fixture that must be rejected.

Done when:
- Every Duval file dated 2025-01-01 onward is loaded and equals its `EOF` count (2,716 files as of 2026-11-11; report the number). The two `relationships` tests report 0 orphans, or the remainder is counted and explained.
- Lien dailies: a table of file date by rows loaded for each of the four kinds, every line the documented length, and missing business days listed. Every daily `COR` event joins to a filing in the snapshot or in an earlier daily; report found and missing.
- `fetch_manifest` has one row per loaded file across the three sources. Paste the count per source next to the count of distinct `source_file` values in raw.
- `pytest` and `ruff check src tests` pass.

### B1. Link models (R1–R4, R11, R13, R14, R17, R19)

Add `+schema: intermediate` in `dbt_project.yml`. Models in `pipeline/models/intermediate/`:
- `int_company_match_keys`: one row per company from `entity_lookup` with `match_key` (the `name_key` minus a trailing legal suffix), ZIP5, status, filing date, and `match_key_company_count` across all statuses.
- `int_federal_lien_links`: corporate debtors → companies.
- `int_dbpr_license_links`: licenses → companies through `dba_name`; `QB` rows through their own name.
- `int_dbpr_discipline_links`: discipline → license → company. The words-to-code map is a seed (R14).
- `int_duval_party_links`: TO-side parties on allowlisted documents (R16) → companies. Unique-name branch only (R3).

Every link model has the same columns: the source record's identifier, `document_number`, `link_status` (CONFIRMED, AMBIGUOUS, NO_MATCH), `matched_on` (`name_zip` or `unique_name`), and the source's date. No raw source name (R4).

Tests: `accepted_values` on `link_status`; `relationships` to `entity_lookup` for every non-NO_MATCH row; a singular test that fails if any column named like a name exists in an intermediate model other than `int_company_match_keys`; a singular test for R2 (no CONFIRMED link dated before the company's filing date).

Done when: the report has a table of CONFIRMED, AMBIGUOUS and NO_MATCH counts per source, with the share CONFIRMED by `name_zip` versus `unique_name`. Counts only, no names.

### B2. Open or closed, then the flags mart (R5–R7, R9, R12, R16, R18, R20–R22)

- `int_federal_liens_status`: one row per lien, open or closed per R6, with the date of any `COD`.
- `int_duval_document_status`: one row per allowlisted lien, warrant or judgment, open or closed per R18.
- `company_flags` (mart, table): one row per flag on a CONFIRMED link. Columns: `document_number`, `flag_type`, `fact_date`, `status`, `status_note`, `source`, `source_record_id`, `source_url`, `fetched_at`, `caveat`, `is_shown`. `is_shown` is false for Duval flags unless `show_duval` is true, and false for discipline unless `show_dbpr_discipline` is true; both variables default to false in `dbt_project.yml`.
- Flag types and wording follow the flags table in `docs/mvp_plan_nov8.md` section 4. Facts, never conclusions.

Tests: `not_null` on `source_url`, `fetched_at` and `source_record_id`; `accepted_values` on `flag_type` and `source`; a singular test that every Duval flag's type code is in the allowlist and no flagged judgment has "FLORIDA STATE OF" on the FRM side; a singular test that every flag traces to a CONFIRMED link.

Done when: the report shows flags by type and by `is_shown`, open versus closed liens per source, and how many companies carry at least one flag.

### B3. Samples for Andres's hand checks

- `evals/link_sample_20.csv`: 20 random CONFIRMED links, 8 federal lien, 6 DBPR license and 6 Duval. Columns: company name as registered, `document_number`, source, source record identifier, `matched_on`, the two dates, and the official search page to check it on. Businesses only. Done when Andres finds 0 wrong; you only produce the file.
- `evals/draft_test_cases_40.csv`: 40 draft lookup cases built from real lien debtor and license business names (entity-word names only), each with the expected `document_number`. Don't add them to `pipeline/seeds/test_set.csv`.

Cost: record credits per leg as in Phase A. If Phase B as a whole passes 3 credits, stop after the current leg and say so in the report.

## 6. Phase C: the app that reads the marts (only when told)

Phase B finished on Nov 19, 2026, and leg C0 then tightened the linking rule with rulings R29 and R30. Phase C builds what a contractor will use: a copy of the finished tables in Postgres, a search over them, a report made only of cited facts, and a small web app. At the end of the phase the app runs on Andres's Mac. Putting it on the internet is not part of this phase.

Run unattended. Never stop to ask a question or wait for approval. When something is unclear, take the most cautious reading, which in this phase is the one that shows less to a contractor and claims less, write the assumption in the leg report, and keep going. The stop conditions in section 3 still apply.

### Before the first leg

Do these three things first, and stop if any of them fails.

1. **Pull request 13 must be merged.** Run `git fetch origin` and check that `docs/phase_b_rulings.md` on `origin/main` holds ruling R30. If it does not, stop and say that Phase C waits for pull request 13, because the marts would otherwise be built on the old linking rule.
2. **Read the newer material.** Read `docs/legs/c0-link-rules.md`, questions Q26 to Q28 in `docs/open_questions.md`, and sections 1, 3 and 4 and Days 5 to 7 of `docs/mvp_plan_nov8.md`. That plan was written on Oct 30, before Phases A and B existed. Where it disagrees with this section, this section wins. For example, the plan calls the flags table `mart_company_flags`, and the table that exists is `company_flags`.
3. **Check the credit room.** The resource monitor caps `datum_wh` at 10 credits a month (`snowflake/01_cost_guardrails.sql`). Read the credits used so far this month from `warehouse_metering_history` and put the number in the first leg report. If fewer than 2 credits are left in the month, stop before building anything, because a warehouse that the monitor suspends in the middle of a build leaves half-built tables.

### Working rules for Phase C

Andres approves these rules by merging this brief, and he can overrule any of them with a ruling. Until he does, build exactly this. Each rule is the cautious choice for a question that the rulings R1 to R30 do not answer.

| # | Rule | Why |
|---|---|---|
| W1 | Everything the app states about a company is a `Fact`, and a `Fact` cannot be built without a source address and a time-zone-aware fetch time in UTC (Coordinated Universal Time). This includes the company's own status, date on record and address, not only the flags. When the fetch time is an estimate (the manifest's `is_approximate`), the fact carries that mark and the page says "about". | CLAUDE.md rule 3 says the type itself must refuse a fact with no source. The bug hunt of Nov 19 found that the flags mart could not tell a measured fetch time from an estimated one. |
| W2 | The summary line counts two kinds of flag and nothing else: the two flags that come from the company's own record ("Inactive with the state" and "New company"), and the flags from a linked record that sit on a CONFIRMED link and have `is_shown` true. A possible match and a hidden flag are never counted. A report that shows any flag never carries the line "No flags found in the sources checked." | Decision d19: a linked flag attaches only on a CONFIRMED link. The two company-record flags need no link, and leaving them out of the count would put "No flags found" beside an inactive company. |
| W3 | Possible matches are built, and every one starts hidden. A possible match is a record on an AMBIGUOUS link that would be a shown flag if the link were CONFIRMED. Decision d19 says such a record shows as "possible match: verify" and is never counted. Since d19, the linking rule has gained reason codes (`zip_differs`, `before_company_filed`, `no_entity_word` and the rest), and nobody has decided which reasons are safe to show. So a seed lists every reason with `is_shown` false, and Andres turns a reason on with a ruling. | Showing a record that predates the company, or one filed under a name with no legal-entity word (which may be a person's name), could accuse the wrong company or surface a person's record. That is a matching and privacy call, and those are Andres's. |
| W4 | A report never reassures. The words "clean", "safe", "risky", "trustworthy", "reliable", "credit", "score" and "recommend" never appear on a page. When there is no flag, the line is exactly "No flags found in the sources checked." Every report, with or without flags, also carries this sentence: "Datum shows a record only when it can confirm that the record belongs to this company. A record filed under a similar name or at a different address is not shown." | "No flags found" next to hidden possible matches would read as an all-clear. The sentence says what the report cannot see, in the same words on every report, so it never hints at anything about one company. |
| W5 | A source counts as "checked" only when its flags may be shown. Today that is three sources: the Sunbiz company record, federal tax liens and DBPR (Department of Business and Professional Regulation) licenses. Each is listed with the date its data runs through. Everything else is listed as "not checked": Duval County recorded documents, DBPR discipline, court cases, UCC (Uniform Commercial Code) filings, other counties, fictitious names, and changes to a company's status after the snapshot date. | Listing a hidden source as checked would tell a contractor that Datum looked there and found nothing. |
| W6 | The app asks for a business name, a street or a city, and it never asks for an owner's name. The note a contractor types is used for one extraction call and then dropped. It is never stored, never written to a log and never shown back. The report says how the company was identified by showing the extracted business fields (name, city, street), the match level and the evidence. | The search has no owner data, so an owner's name cannot help it, and asking for one brings a person's name into a tool that is about businesses only. The bug hunt found that `report.py` wrote the raw note, owner's name included, into the saved report. This narrows acceptance test A2, which says "name, street or owner". |
| W7 | A tie is said out loud. When more than one company shares the top match level, the shortlist says so, and the report for whichever company is picked says how many other companies matched equally well. | The bug hunt found that `report.py` wrote "Strong" for a company that had tied with another one. CLAUDE.md rule 3 says never to collapse an unclear result into a confident one. |
| W8 | The app is private and fails closed. Every page except `/healthz` needs the access code. The app refuses to start when `APP_ACCESS_CODE` is not set. Search engines are told not to index it in three places: a `noindex` meta tag, an `X-Robots-Tag` header and `/robots.txt`. During this phase the server listens on `127.0.0.1` only, which means only the Mac itself can reach it. | Acceptance test A9. Failing closed means a forgotten setting locks the app, where failing open would publish it. |
| W9 | Hidden records never leave Snowflake. The export to Postgres carries only rows with `is_shown` true. | The app cannot show, leak or miscount a row it does not have. |
| W10 | No test and no evaluation calls the Claude API (application programming interface, the paid service the extraction step calls). The extraction step sits behind an interface, tests use a fake, and the evaluation reads the `extracted_inputs` seed. The whole phase may make at most 10 live extraction calls, for the two live checks in leg C4. | CLAUDE.md rule 4, and cost: about $0.0004 a call 🟡 (the plan's figure), so at most about half a cent. |

The app is built in this phase and shown to nobody. Whether it is ready for a contractor is Andres's call, and it depends on gates outside this phase: the 90% bar on the hand-checked test set, the link hand checks and a lawyer's review.

### Rules for every Phase C leg

- **Branches.** There are four legs, in order, and each depends on the one before it. Stack the branches as Phase B did: `leg/c1-serving-marts` from `main`, `leg/c2-postgres-search` from `leg/c1-serving-marts`, and so on. Open one pull request per leg, each targeting `main`. Andres merges them in order.
- **Additions only, with three exceptions.** Section 3 says never to change an existing table, model or seed. Leg C1 may add one column to `company_flags`, add one row to the seed `search_page_sources`, and add the source `sunbiz_cor` wherever the fetch manifest lists its allowed sources. Nothing else about those may change. Leg C3 may rewrite `src/datum/report.py`.
- **Snowflake scripts.** The next free number is 21. Leave scripts 01 to 20 as they are, and put new statements in a new numbered script.
- **Packages.** The app needs FastAPI, Uvicorn (the program that serves a FastAPI app), Jinja2 (the template library), psycopg version 3 (the Postgres driver), python-multipart (reads a submitted form) and whatever FastAPI's test client needs. Install the current stable version of each, run `pytest`, and pin the exact versions in `requirements.txt` with a comment per package, as ruling R24 asks. Add no other package without giving the reason in the leg report. Write the Jaro-Winkler name comparison in plain Python, because Postgres has no such function and CLAUDE.md rule 1 puts scoring in plain code.
- **Fixtures.** A fixture row may be cut from a real mart row about a company. Replace every license, filing, complaint and instrument number in it with an invented number of the same shape, because those numbers lead to a person's record and the repo is public (Andres's decision of Nov 19). Record each fixture's origin and capture date, and extend `tests/test_fixture_privacy.py` to cover the new files.
- **dbt unit tests cost credits.** They run inside Snowflake, and leg C0 spent 0.64 credits mostly by running them about fifty times in a row. Run the whole unit-test selection once per change, not one test at a time.
- **Review.** Set each leg's tier from `REVIEW.md`. Legs C1, C3 and C4 are High, because they touch the marts or decide the wording on a report. For a High leg in this phase, give the three reviewers these hunts in place of the ones in section 3: (1) a sentence on a page or report that the data does not support, that draws a conclusion, or that reassures; (2) a person's data, the raw note or a hidden record reaching a page, a log, Postgres or git, and any way to open a page without the access code; (3) a test that cannot fail. Leg C2 is Medium, and it gets `/security-review` because `src/` changes.

### C1. The marts the app reads

- **A fetch time for company filings.** The fetch manifest covers three sources and leaves out the Sunbiz corporate files (`SOURCES` in `src/datum/manifest.py`), so no company's status, date or address has a fetch time today. Add the source `sunbiz_cor`. Backfill the quarterly and daily corporate files that are still on disk under `data/raw/` from their modification time, with `is_approximate = true`, exactly as ruling R23 did for the other sources, and load the new rows with a new numbered script. If the files are no longer on disk, do not estimate the time from anything else. Leave this bullet undone, say so first in the leg report, and finish the rest of the leg.
- **`company_search`** (mart, table). One row per company, holding what the search and the report header need: `document_number`, `entity_name`, `name_key`, `status_code`, `filing_type`, `file_date`, the four principal address columns, `published_on`, `source_url`, `fetched_at` and `fetched_at_is_approximate`. The source address follows ruling R9 (cite the search page and the number): it is Sunbiz's search-by-document-number page, `https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber` ✅ (`docs/access/sunbiz.md`). Add that page to `search_page_sources` as the source `sunbiz_cor`. Do not fetch the page to test it, because the site blocks automated access.
- **`company_flags` gains one column,** `fetched_at_is_approximate`. Prove that nothing else moved: the row count and a checksum over every existing column must be the same before and after.
- **`company_possible_matches`** (mart, table), for rule W3. It has the columns of `company_flags` plus `link_reason`. Only the sources whose flags are shown today can produce a row (federal tax liens and inactive DBPR licenses), and the flag rules are the same ones `company_flags` uses, including the liens that ruling R7 leaves out. Keep those rules in one place that both marts read. If that means moving them out of `company_flags.sql`, do the move in its own commit and prove with the same checksum that `company_flags` did not change. Add the seed `possible_match_reasons` (one row per reason code, `is_shown` false on every row) and the test `assert_possible_matches_stay_hidden`, which fails when any row has `is_shown` true. It compares to the literal `false`, as ruling R28 requires, so that showing a reason takes two reviewed edits. A near-namesake is counted and not listed (question Q27), and that stays as it is.
- **`source_coverage`** (mart, table). One row per source: the source, a plain-English label, whether its flags are shown, the date its data runs through, its newest fetch time and whether that time is an estimate. The report's "checked" and "not checked" lists come from this table (rule W5).
- **The app as a dbt exposure.** An exposure is dbt's way of recording that something outside the warehouse reads a model. Declare the web app as one that reads the four marts.
- **Size question Q28, and change nothing.** Count the companies whose match key was shortened by reading spaced single letters as a longer suffix, and count the CONFIRMED links that point at one of them. Print counts only. Add both counts to Q28's row in `docs/open_questions.md`.
- **New open questions.** Add a row to `docs/open_questions.md` asking which possible-match reasons may be shown (rule W3), and one for anything else this leg could not decide.

Tests: `not_null` on `source_url` and `fetched_at` in every new mart, `unique` on `company_search.document_number`, `relationships` from the two flag marts to `company_search`, and `accepted_values` on `link_reason`.

Done when the leg report holds:
- the build output for the four marts and everything they depend on, with every test passing;
- the before-and-after row count and checksum for `company_flags`;
- a count of possible matches by source and reason, with 0 shown;
- the rows of `source_coverage`;
- how many companies have a measured fetch time, an estimated one, or none;
- the two Q28 counts;
- the credits this leg used.

### C2. The Postgres copy and the search

- **Postgres on the Mac.** Check `psql --version`. If Postgres is missing, install it with Homebrew (`brew install postgresql@17`, then `brew services start postgresql@17`), which is free and local. If the install is blocked or fails, stop this leg and give Andres the exact commands in the report. Create the database `datum_dev` and turn on `pg_trgm`, the extension that compares names by their three-letter pieces. The local database needs no password, so nothing about it is a secret.
- **Export (the next numbered script, named `NN_export_marts.sql`).** Create one new internal stage in `datum.dev_marts`, and copy the four marts into it as compressed CSV (comma-separated values) files, keeping only rows with `is_shown` true in the two flag marts (rule W9). Download the files to `data/export/` with `snow stage copy`.
- **Load.** Write a small loader in `src/datum/` that copies the files into Postgres. Load into new tables and swap them in with one transaction, so that a load that fails halfway never leaves the app reading half a table. Every table's row count in Postgres must equal its count in Snowflake.
- **Index.** Build a trigram index on `company_search.name_key`. Record how long it took to build, and the size of each table and index with `pg_size_pretty`. Those sizes will pick the host later, and that choice is Andres's.
- **`src/datum/search.py`.** One `SearchBackend` interface (a Python `Protocol`) with two implementations: `PostgresBackend` for the app and `FakeBackend` for tests. Postgres returns the nearest candidates by trigram, and then the same rules as search version 1 rank them: Jaro-Winkler similarity, then a city match, then the document number as a fixed tie-break. Test the plain-Python Jaro-Winkler against a fixture of name pairs with the scores Snowflake's `JAROWINKLER_SIMILARITY` gives them, captured with one query. Write the match level and the evidence as functions in this module, following the rules `report.py` uses today. Do not edit `report.py` in this leg, because that file is High tier and this leg is Medium. Leg C3 makes `report.py` use these functions, so that they exist in one place.
- **`evals/run.py`.** `python -m evals.run --backend postgres` and `--backend snowflake` print top-1 accuracy, recall at 5 and `wrong_match` by case group for the cases in `pipeline/seeds/test_set.csv`, using the definitions in `snowflake/11_score_search_v1.sql`. Never commit or print a row of the two local files in `evals/` that `.gitignore` names.
- **`docs/adr/0001-serving-layer.md`.** An ADR (architecture decision record) is a one-page note on a decision. Write the one for decision d18: why lookups read Postgres and builds run in Snowflake, with the cost line.

Done when the leg report holds:
- row counts in Snowflake and in Postgres, side by side, for every table;
- the evaluation on both backends. Postgres must be at least as good as Snowflake on top-1 and on recall at 5, with no more `wrong_match`. List any case that differs by its case number;
- p50 and p95 search time over the evaluation inputs plus 200 company names drawn at random. The p50 is the time that half of the searches beat, and the p95 is the time that 95 of every 100 searches beat. The target is a p95 under 1 second 🔴 (the plan's target, never measured). If two different approaches both miss it, record the numbers and stop the leg. Do not loosen the target;
- table and index sizes, and the index build time;
- `pytest` and `ruff check src tests` passing with Postgres stopped, which proves the offline suite does not need a database;
- the credits this leg used.

### C3. The Fact type and the report

- **`src/datum/models.py`.** Pydantic models that cannot be changed after they are built: `Fact` (rule W1), `Flag`, `Candidate` and `Report`. Building a `Fact` with no source address, with a fetch time that has no time zone, or with one that is not UTC raises an error, and a test proves each of the three.
- **`src/datum/report_builder.py`.** `ReportBuilder.build()` takes a document number and how the company was identified, reads through a `ReportBackend` interface (Postgres for the app, a fake for tests), and returns a `Report`. It holds no wording of its own for a linked record: a flag's fact, status note, caveat and citation come from the mart's columns as they are.
- **The two flags from the company's own record.** "Inactive with the state" and "New company" use the rule, the wording and the caveat from the flags table in `docs/mvp_plan_nov8.md` section 4, word for word.
- **The rest of the page.** A summary line (rule W2), the flags newest first, the "checked" and "not checked" lists (rule W5), the two sentences of rule W4, the identification line (rules W6 and W7), and the disclaimer that `report.py` prints today, word for word. Keep every piece of fixed wording in one module, so that a reviewer reads one file to see every sentence a contractor can be shown.
- **`report.py` becomes a thin command-line wrapper** over the builder, so that the terminal and the web app cannot drift apart. It stops asking for an owner's name.
- **Tests that fail on the old behavior.** One test proves that a typed note never reaches a report (rule W6). One proves that a tie is stated (rule W7). One renders reports from fixtures and fails on any word in rule W4's list, and on a no-flag report that lacks the exact line and the sentence. One proves the summary count ignores possible matches and hidden flags, and one renders an inactive company with no linked flag and fails unless the count is 1 and the no-flags line is absent.

Done when the leg report holds:
- the test output, with the name of each new test and the input that makes it fail;
- five reports built from the real Postgres data and saved under `data/reports/`, which git ignores: one company with a federal lien flag, one with an inactive license, one inactive company, one new company and one with no flags. Name them in the leg report by document number only;
- every fixed sentence a contractor can be shown, in one table, for Andres to read.

### C4. The web app

- **`src/datum/web/`.** A FastAPI app with server-rendered Jinja templates and Pico CSS (decision d20). Keep one copy of the Pico CSS file in the repo, with its version and license noted, so that a contractor's phone never calls a third party. Use no JavaScript framework.
- **Routes.** `GET /` shows the search box. `POST /search` takes the note, extracts the fields and shows the shortlist, or asks for a business name, a street or a city when the note names no business, and in that case shows no company at all (acceptance test A2). `GET /company/{document_number}` shows the report. `GET /healthz` answers "ok" and nothing else. The search uses POST so that the note never lands in an address, a browser history or an access log.
- **Injection.** The extractor, the search backend and the report backend are passed in (dependency injection), so every test runs with fakes and no network.
- **Access and privacy (rule W8).** The access code comes from `APP_ACCESS_CODE` and is asked for with HTTP Basic, the browser's built-in sign-in box. It is compared with `secrets.compare_digest`. A test proves the app will not start without the code, that every route but `/healthz` answers 401 without it, and that the three no-index signals are present. Another test captures the logs during a search and fails if the note appears in them.
- **Safe rendering.** Template auto-escaping stays on, and a test renders a company name that contains markup. A document number that does not look like one, or that matches no company, gets a plain 404.
- **When extraction fails,** the page says the search is unavailable and shows no company.
- **Phone width.** Every page has a viewport tag and no fixed width wider than 390 pixels. If Google Chrome is installed, save a headless screenshot of each page at 390 pixels wide under `data/screens/`. If it is not, mark the check 🟡 and leave it to Andres.

Done when the leg report holds:
- `pytest` and `ruff check src tests` passing;
- the app started with `uvicorn datum.web.app:app --host 127.0.0.1` and the two live checks, with timings. For this one command, set a throwaway `APP_ACCESS_CODE` in the shell on the same line as the command. Never write it to a file, a log or the leg report, and never touch the secrets file. The two checks are: `ferguson ac boynton beach` must put FERGUSON AIR CONDITIONING & REFRIGERATION, INC. first (acceptance test A1), and `the pool guy off race track rd` must show no company (A2). These are the only live extraction calls in the phase (rule W10);
- the screenshots, or the 🟡 mark;
- a short list for Andres of what only he can do: add the `APP_ACCESS_CODE` line to the secrets file himself, open the app on his phone, and decide on hosting.

### Cost

- **Snowflake.** Leg C1 should use about 0.3 to 0.6 credits 🟡. That is less than leg C0's 0.64, because most of C0's credits went on running unit tests about fifty times and this phase runs them once per change. The export should use about 0.05 credits 🟡 (the plan's estimate). Each evaluation run on the Snowflake backend in leg C2 wakes the warehouse for one to three minutes, which is up to about 0.05 credits a run 🟡, so run it as few times as the leg needs and record its credits in the C2 report. A credit costs about $2 ✅ (leg C0's report). Record the credits per leg. If Phase C as a whole passes 3 credits, stop after the current leg and say so in the report.
- **Claude API.** At most 10 extraction calls, which is about half a cent.
- **Everything else is free.** Postgres runs on the Mac. Creating a hosted account, a hosted database or anything with a bill is a stop condition under section 3: stop and ask in the leg report.


## 7. Phase D: search the way contractors search (only when told)

On Nov 24, 2026 Andres tried the web app on a restaurant he knows, and it failed him in two ways. The data was not the problem: the company he meant is in the register, active, at the address he knew.

- **"v pizza orlando" ranked the right company 13th.** V PIZZA LAKE BUENA VISTA LLC (document number L22000086098, active, principal address 8586 PALM PKWY, ORLANDO 32836) lost to an inactive V PIZZA WP LLC in Winter Park and to eleven other V Pizza companies in other cities. The cause is in `rank()` in `src/datum/search.py`: candidates are sorted by Jaro-Winkler similarity first, which favours a short name when the typed name is short, and the city only breaks an exact tie.
- **"8586 palm pwwy" found nothing.** The extraction step returns a street, and neither the app nor the evaluation ever reads it. The app then answers that the note names no business. Four companies have that principal address, and V Pizza Lake Buena Vista is the only active one.
- **The report overwhelmed him.** It opens with a table of record fields, and a contractor needs the answer to their question first.

The 10 cases in `pipeline/seeds/test_set.csv` are all names, so they could not catch any of this. Phase D fixes the test set first and the search second, and then puts a plain summary at the top of the report. It had two legs at first, and both are High tier: D1 changes the matching rules and the wording on the search pages, and D2 changes the wording on a report. Legs D3 and D4, also High tier, were added on Nov 26 and are described after D2.

Run unattended. Never stop to ask a question or wait for approval. When something is unclear, take the most cautious reading, which in this phase is the one that shows a contractor less and claims less, write the assumption in the leg report, and keep going. The stop conditions in section 3 still apply.

The Phase C working rules W1 to W9 still apply. Of rule W10, the first sentence still holds: no test and no evaluation calls the Claude API. Its limit of 10 live calls was Phase C's, and this phase has its own limit, under "Rules for every Phase D leg". Rule W6 also still holds, with one change: leg D1 may change the page wording W6 describes, so that the pages match the address search.

### Before the first leg

Stop if any of these fails.

1. **Pull requests 21 and 22 must be merged.** Run `git fetch origin` and check that `src/datum/wording.py`, `src/datum/report_builder.py` and `src/datum/web/app.py` exist on `origin/main`. If they do not, stop and say that Phase D waits for them, because both legs change those files.
2. **Postgres must hold the data.** Check that Postgres is running and that `company_search` in `datum_dev` has 12,988,435 rows. If Postgres is stopped, start it with `brew services start postgresql@17`. If the table is missing or its count differs, stop and say so.
3. **The exported files must still be on the Mac.** Leg D1 reloads Postgres from `data/export/`. Check that the files for all four tables are there. If they are not, stop: getting them again needs Snowflake, and this phase does not use it.

Before the first change, read `docs/legs/c2-postgres-search.md`, `docs/legs/c3-fact-report.md`, `docs/legs/c4-web-app.md`, and questions Q34, Q35, Q41 and Q42 in `docs/open_questions.md`.

### Working rules for Phase D

Andres approves these rules by merging this brief, and he can overrule any of them with a ruling. Until he does, build exactly this.

| # | Rule | Why |
|---|---|---|
| S1 | A test case enters `pipeline/seeds/test_set.csv` only when Andres has checked it. A case you draft goes into `evals/draft_cases.csv`, with an empty `verified_on`. That file and `evals/draft_extracted.csv` are added to `.gitignore` beside the leg B3 drafts, and they stay on the Mac until Andres checks them. The evaluation scores the checked and the draft cases and reports them in separate tables. Every pass or fail gate in this phase uses the checked cases only. Never change the search to make a draft case pass. | A case whose expected answer is wrong would teach the search the wrong thing, and Andres owns the hand checks (the build split of Nov 11). An unchecked address may be someone's home, and the repo is public. |
| S2 | Rank in this order: (1) whether every word of the typed business name appears among the words of the company's name, ignoring legal suffixes; (2) whether the company's principal city agrees with the city the extraction step returned; (3) Jaro-Winkler similarity; (4) the document number, as a fixed tie-break. Status never moves a company up or down. The shortlist marks an inactive company instead (rule S10). The extraction returns no ZIP code, so the ranking compares none. | A long legal name such as V PIZZA LAKE BUENA VISTA LLC holds every word of "V Pizza", and a contractor names the business and the town. Ranking active companies first would hide a dissolved client behind an active namesake (ruling R1's reasoning), and that is a wrong match that reassures. |
| S3 | If S2 makes any checked case worse (it leaves the top five, it drops in rank, or a NEEDS_MORE_INFO case gets a company), try one variant: swap (1) and (2). If the variant also makes a checked case worse, keep the old ranking and record both results. Then finish the rest of the leg (the address search, the speed check and the tests), and put this result first in the leg report. Do not invent a third ordering. Leg D2 then branches from D1 as usual. | The same discipline as leg C2: two approaches, then let Andres decide. Trying order after order on a handful of cases is fitting the test set. |
| S4 | The match level (Strong, Likely, Possible) keeps its current rules in `search.py`. Phase D changes the order of the candidates and not what each level means. | A level is a claim to the contractor about how sure Datum is. Changing it is a separate decision. |
| S5 | When the note names no business (the extraction's `is_specific` is false or its `business_name` is empty, the rule in `src/datum/web/app.py`) and its extracted street begins with a house number, the app and the evaluation run the address search in place of asking for more. A note that names a business runs the name search, even when its street has a house number. The house number must match exactly. For the street, remove the street types (PKWY, PARKWAY, ST, STREET, AVE, AVENUE, RD, ROAD, BLVD, DR, DRIVE, LN, CT, WAY, CIR, HWY and the like) and the directions (N, S, E, W) from both sides. A company matches when every remaining word of its stored street is among the remaining typed words, so the typed "PALM PWWY" matches the stored "PALM PKWY". When the extraction returns a city, the company's principal city must also agree with it, by the same comparison the name search uses (`city_matches` in `src/datum/search.py`), and the shortlist shows each company's city beside it. Only the principal address is searched. | That is how a contractor knows a job: the address. The street type and the direction are where the typing errors and abbreviations are. |
| S6 | An address search lists only the active companies at the address, in document-number order. When inactive companies are also registered there, the shortlist says how many in one sentence and does not list them. Add a new open question asking Andres whether inactive companies at an address should be listed, and whether an address that may be a home should be searchable at all. | A name search starts from one company. An address search starts from a place, which may be a home, and could list every business ever registered there. That is a privacy call, and privacy calls are Andres's. Listing less is the cautious reading. |
| S7 | A note with a street but no house number still asks for more ("the pool guy off race track rd" stays NEEDS_MORE_INFO). | Acceptance test A2. A street alone matches thousands of companies. |
| S8 | Under the results of an address search, the shortlist says once: "A company's principal address is the address it gave the state, which is not always where it does business." | The principal address can be an accountant's office or a registered agent's. Datum states what the record says and nothing more (CLAUDE.md rule 2). |
| S9 | The summary at the top of a report is built from facts the report already shows, in this order: the company's status with the state as of the date its record was published (the report's "data published" date, `published_on`), its entity type, the year of its date on record, the summary line of rule W2, and then rule W4's sentence, word for word, on every report. Example: "Active with the state as of Oct 7, 2026. Florida limited liability company, on record since 2022. No flags found in the sources checked. Datum shows a record only when it can confirm that the record belongs to this company. A record filed under a similar name or at a different address is not shown." The words in rule W4's list stay banned. | A contractor reads the first lines and stops. Those lines must answer "is it real, and is anything on the record" without a verdict, and they must say how far the check reaches. "Active" is the status on that date, because rule W5 lists later changes as not checked, and a company first seen in a daily file has a later date than the quarterly snapshot. |
| S10 | The shortlist marks an inactive company with "Inactive with the state" beside its name, and the same words leave its evidence list, so it is said once. | The only sign that the company Andres got first was inactive was the last line of its evidence list. |

### Rules for every Phase D leg

- **Branches.** `leg/d1-contractor-search` from `main`, then `leg/d2-report-summary` from `leg/d1-contractor-search`. One pull request per leg, each targeting `main`. Andres merges them in order.
- **Extraction.** Change the street line of the extraction prompt in `src/datum/extract.py`, as prompt v3, to: "street: the house number and the street exactly as typed (for example "8586 palm pwwy"), without correcting the spelling, else empty." Code reads the house number from the start of `street`; the note itself is never parsed (rule W6). Never extract cases 1 to 10 again, and never change their rows in `pipeline/seeds/extracted_inputs.csv`: they stay as prompt v2 made them, and the leg report says so. `extract.py` today re-extracts the whole test set and overwrites its output, so give it an option that extracts only the case ids it is given and appends their rows, and use the same option to write `evals/draft_extracted.csv`.
- **Live calls.** At most 30 live extraction calls in the phase: about 3 for the checked cases, 16 for the draft cases and 4 for the checks on the real app, which leaves a few spare. That is about 1.2 cents at most 🟡 (the plan's figure of $0.0004 a call). No test calls the API.
- **No Snowflake.** Everything in this phase reads Postgres on the Mac. Running anything in Snowflake is a stop condition: stop and say why it seemed necessary.
- **Public repo.** A checked case may name a company, because the existing cases do. It never names a person, and its notes say nothing about a company beyond what the register says. The leg report and the pull request give the draft cases' count by kind and how each kind was chosen, and never the cases themselves.
- **Review.** Both legs are High. Give the three reviewers these hunts: (1) a ranking or matching change that makes a checked case worse, or that is tuned to a draft case; (2) a sentence on a page that the record does not support, that draws a conclusion, that reassures, or that reveals something about a person, including the new summary and the address results; (3) a test that cannot fail.

### D1. Search the way contractors search

- **The checked cases.** Add these three rows to `pipeline/seeds/test_set.csv`, as case group `contractor_search`, with `verified_on` 2026-11-24. Andres confirmed the restaurant and its address on Nov 24, and the document number is from the Oct 7 snapshot.

  | input_text | expected_document_number | expected_entity_name | case_type |
  | --- | --- | --- | --- |
  | v pizza orlando | L22000086098 | V PIZZA LAKE BUENA VISTA LLC | trade name + city |
  | v pizza lake buena vista | L22000086098 | V PIZZA LAKE BUENA VISTA LLC | trade name + area name |
  | 8586 palm pwwy | L22000086098 | V PIZZA LAKE BUENA VISTA LLC | address only, with a typo |

- **Draft cases for Andres to check.** Draft 16 from the data in Postgres into the git-ignored `evals/draft_cases.csv` (rule S1), with the same columns as the test set and an empty `verified_on`. Make the first one `v pizza durbin`, expecting V PIZZA DURBIN, LLC (L25000541856). Then draft five of a brand with several companies named "BRAND LOCATION LLC", typed as the brand and a city; five of an address alone, using only addresses where at least one active company's name holds a legal-entity word (LLC, INC, CORP and the like) and no company there has a name that could be a person's; and five of a name with a street. When unsure whether a name could be a person's, skip it. Prefer active companies in Northeast and Central Florida, because Andres can check those. For each case, write in `notes` the query you used to pick it.
- **Ranking (rules S2 to S4).** Change `rank()` in `src/datum/search.py`. Show the before and after rank of the expected company on every checked case. For the draft cases, give only how many moved up, moved down or stayed, by kind.
- **Address search (rules S5 to S8).** Add a narrow address table to the Postgres load. It holds the document number, the house number and the street words, built from `principal_address_1`, with an index on the house number. The loader checks that it holds the same document numbers as `company_search` before the swap, as it does for the narrow name table. In the web app, a note runs the address search under the condition of rule S5. Update the page wording that asks for "a street or a city" so it matches what the search now does, and answer question Q42 in `docs/open_questions.md` with what was built.
- **The evaluation follows the app.** In `evals/run.py`, give `Case` the extracted `street`, and send each case down the same path the app uses, by the condition of rule S5. Score the checked cases from `pipeline/seeds/test_set.csv` and the draft cases from the git-ignored files, in separate tables. For the draft cases, `evals/run.py` prints only the summary table by case group and never a line per case, because the leg report pastes this output. When the draft files are absent, as on GitHub, it prints one sentence saying so and scores the checked cases only, and no test reads them. Update the line in its docstring about the git-ignored files in `evals/` so it names all four and says which two it reads.
- **Speed.** Measure the name search as leg C2 did, with the same 200 randomly drawn names plus every specific checked case, and time the address search on 200 addresses drawn at random. The target is a p95 under 1 second for each search. If either one misses it with two different approaches, record the numbers and stop the leg. Do not loosen the target, and do not drop the address search to meet it.
- **Tests.** One test per rule S2, S5, S6 and S8 that fails on the old behavior. One test proves that the match levels of rule S4 come out as before on the existing fixtures, and one proves that a note with a street but no house number still asks for more (rule S7). One test, on a fixture, proves that a draft case can never change a gate, because the gates read `test_set.csv` only. One test proves that an address search with one active and two inactive companies lists only the active one and says that two inactive ones are there. Update `tests/test_evals_run.py`, which counts the test cases.

Done when the leg report holds:
- the evaluation before and after, on the checked cases and the draft cases in separate tables, by case group: top-1, recall at 5 and `wrong_match`;
- the before-and-after rank of the expected company for every checked case, and for the draft cases by count only;
- the three V Pizza searches and `v pizza durbin` run on the real app, with the top five each returned;
- the speed numbers for both searches;
- how many draft cases of each kind were written, and how each kind was chosen;
- `pytest` and `ruff check src tests` passing with Postgres stopped;
- the number of live extraction calls made.

### D2. A summary first, and the details below

- **The summary (rule S9).** Put it at the top of the report page and of the report the command line writes, above the record table. Its sentences live in `src/datum/wording.py` with the rest.
- **The shortlist mark (rule S10).** Add it beside the name in the shortlist template, with its words in `src/datum/wording.py`, and remove the matching line from the evidence list.
- **The details below.** Keep every other fact the report shows today, in the same words, and put the company record table and the source lists under a heading such as "The records behind this summary". Change no fact, caveat or citation.
- **Tests.** The summary is built from the same facts as the page and cannot disagree with them: a test renders the five reports of leg C3 and fails if the summary's status, year or count differs from the facts below it, if the summary's date differs from the record's `published_on`, or if rule W4's sentence does not come right after the summary line. The banned-words test covers the summary.

Done when the leg report holds:
- the five reports of leg C3 rebuilt, with their summaries, named by document number only;
- a screenshot of the report page and the shortlist at 390 pixels wide, or the 🟡 mark;
- every new or changed sentence in one table, for Andres to read.

### Rulings of Nov 26, 2026, for legs D3 and D4

On Nov 26, 2026 Andres merged pull requests 25 and 26 and decided the nine questions they raised (Q45 to Q53), taking the recommendation on each. The rules below are binding for legs D3 and D4, and `docs/open_questions.md` records each question as answered. Rules S1, S2 (as amended by rule S14) and S4 to S10 still apply, with rule S5's list of ignored words amended by rule S15. So status still never moves a company up or down, also in the new first step of rule S11. The open question that rule S6 asks for is Q45, already answered, so do not add it again. For these two legs, rule S13 replaces the choice that rule S3 made, and rule S17 replaces rule S3's test of what counts as worse.

| # | Rule | Why | Question |
|---|---|---|---|
| S11 | The first step of the name search brings back first the names that hold every typed word, and then the nearest names, as it does today. Build it as one more term in the `ORDER BY` of `NEAREST_SQL` in `src/datum/search.py`, placed before the trigram distance. "Every typed word" means the words of the typed business name with the legal suffixes left out, the same words that `holds_every_word()` compares for rule S2. The rule lives in the query, so its test pins the query's text, as the existing tests in `tests/test_search.py` do, and the measured numbers on the real data prove what it does. The in-memory backend the tests use does not need to copy it. | The step keeps the 200 names nearest to the typed name as a whole, and a long legal name is far from a short trade name. For `v pizza orlando`, 10,062 names passed the step and the right company stood 2,861st among them, so no ranking of the 200 could put it first. Leg D1 measured this option in a scratch script: alone it brought the company to 17th, no checked case got worse, and it was not slower. | Q46 |
| S12 | The shortlist page shows its five companies in rank order, each with its match level beside it, as today. `shortlist()` stops re-sorting them by level. The tie count of rule W7 and `top_level` work as today: Strong is counted over the whole pool, and otherwise the best level among the five is used, never the first card's level. When a company of a lower level is shown above one of a higher level, the page shows once, under the list, the sentence "The list is in search order. The level beside each company says how much of the record agrees with what you typed.", kept in `src/datum/wording.py`. Top-1 in the evaluation then means the first company on the page, which is now also the first by rank. | The page sorted the five by match level, so the first company by rank could be second on the page, and the evaluation scored one order while a contractor saw another. That gap is what moved checked case 9 (`cinemark durbin park`) to second on the page under rule S2. | Q51 |
| S13 | Switch rule S2 on: `RANK_ORDER` becomes `by_words_then_city`. This holds only if, with rules S11 and S12 built, it passes the gate of rule S17. | With rule S11, rule S2 put the right company first for `v pizza orlando`. Its only cost on the checked cases was case 9 on the page, and rule S12 removes the cause. | Q52 |
| S14 | In step (2) of rule S2, the city also agrees when every word of the city the extraction returned is among the words of the company's name. This changes the order only. The match level keeps its rules (rule S4). The evidence list gets one new line when this applies, saying that the place the contractor gave is part of the company's name, and its words live in `src/datum/wording.py`. | The extraction moves a place out of the business name even when the place is part of the registered name. `v pizza lake buena vista` came back as the business "V Pizza" and the city "Lake Buena Vista", and the company's principal city is Orlando, so it could never agree. The model also read that same note two different ways on two calls, and the installed SDK rejects a temperature setting for this model, so the search has to reach the same company whichever way the place is read. | Q50 |
| S15 | When the address search compares streets, an office unit word and the one word right after it (its number or letter) are left out, on the stored side and on the typed side, and every other word stays. The office unit words are STE, SUITE, BLDG, FL, FLOOR, RM and ROOM. So a stored `100 OCEAN DR BLDG 2 APT 305` keeps APT 305, and a note must still hold APT 305 to match it. APT, UNIT and LOT, and the number after a `#` sign, are still compared, as today, until the lawyer answers question Q54. The simplifying step (`name_key()`, and `regexp_replace` in the loader's `ADDRESSES_FILL_SQL`) already turns `#` into a space, so `#200` is compared as the word 200, and nothing needs to change for it. NORTH, SOUTH, EAST, WEST, NE, NW, SE and SW also count as directions, beside N, S, E and W. | A contractor types a building's address and not its suite. 1,095,222 principal addresses hold a unit word of some kind, and today each one is found only when the note has the same unit. APT, UNIT, LOT and `#` often mark an apartment or a mobile-home lot, which is a home 🟡 (not counted; UNIT is also common on warehouse addresses), and leaving them out would let one typed address list the companies of every apartment or lot there. That is the exposure rule S6 and question Q45 hold back, so those four stay compared. A record that says SOUTH or SE matches only a note that says the same. | Q47 |
| S16 | When an address search finds no active company and at least one inactive one, the page today says "No active company matches." (`ADDRESS_NO_ACTIVE`) and gives the count of inactive companies as a cited Fact (`ADDRESS_INACTIVE_ONE` or `ADDRESS_INACTIVE_MANY`), and it lists none of them. Keep all of that, and the sentence saying what was compared and rule S8's note. Add one sentence after the count, kept in `src/datum/wording.py`, that asks for the business's name so the name search can look for it. Do not say the count a second time, and list none of the companies. | Andres asked for this in chat on Nov 25, when he approved pull request 24: if the company at an address is inactive, the contractor should still be led to it, without listing the other companies there, which may be at homes. Today the page stops at the count and gives no next step. With the name added, the name search finds the company and marks it inactive (rule S10). | Q45 |
| S17 | The gate for every change in legs D3 and D4. A checked case is worse when its expected company drops by rank, drops on the page, or leaves the first five, or when a NEEDS_MORE_INFO case gets a company. A step is kept only when no checked case is worse than on `main` at commit `051a928` (the state on Nov 26) AND none is worse than after the step before it. In leg D3, build rules S11 and S12 together and measure, then switch on rule S13 and measure, then add rule S14 and measure. When a step fails the gate, leave it off, keep the steps before it, build no later step (rule S14 is built only when rule S13 is kept), and put the result first in the leg report. Do not invent another order or a variant. To measure, use one scratch script, as leg D1's check 9 did, and do not commit it. It runs the search as it is at `051a928` (that query and that order) and the search after each step, against the same Postgres in the same run, and prints, for each checked case, its expected company's place by rank and on the page, and for the draft cases only the counts of moved up, moved down and stayed, by kind. `python -m evals.run --backend postgres` alone prints the place by rank only, so it is not enough for the gate. Paste the script's output, and say in the leg report what the script does. If a step makes the help text of `--before` or `--try-order`, or the docstring of `WideTableBackend` (which says the two backends return the same companies), in `evals/run.py` untrue, correct it in the same commit. | This is the same discipline as rule S3. Trying variant after variant on 13 cases would be fitting the test set. Comparing with both main and the step before means a step cannot undo an earlier step's gain and still pass. | none |
| S18 | The terminal command `src/datum/report.py` takes the same path as the web app. It makes the same choice between the name search, the address search and a question (`search_kind()`), and it uses the same address search and the same sentences. | One note should get the same answer in the terminal and on the page. Today an address-only note gets the address search on the page and a question in the terminal. | Q49 |

Three things stay as built, because each is the reading that shows less or wording that was already reviewed, and nothing found since argues for changing it. They are the limit of 50 companies at one address (Q48), listing only the active companies at an address and counting the inactive ones (rule S6, Q45), and the three wording choices in the report's summary (Q53). Whether an address that may be a home should be searchable at all is a new question for the lawyer before launch, Q54 in `docs/open_questions.md`, under "Needs a lawyer before launch".

### Before legs D3 and D4

Stop if any of these fails.

1. **Pull requests 25 and 26 must be merged.** Run `git fetch origin` and check that `origin/main` contains commit `051a928` and that `src/datum/search.py` on `origin/main` defines `RANK_ORDER` and `address_search`.
2. **Postgres must hold the data.** Check that Postgres is running, that `company_search` in `datum_dev` has 12,988,435 rows, and that `company_search_addresses` exists and is not empty. If Postgres is stopped, start it with `brew services start postgresql@17`.
3. **The exported files must still be on the Mac,** in `data/export/`, because leg D4 rebuilds the address table. If they are not there, stop: getting them again needs Snowflake.
4. **Count the checked cases.** `pipeline/seeds/test_set.csv` holds 13 cases on `main`. If it holds more when the leg starts, Andres checked some drafts and added them himself. Score them as checked cases, include them in the gate of rule S17, and say how many there were. The evaluation needs each case's saved extraction in `pipeline/seeds/extracted_inputs.csv`. For a promoted case that has no row there, find its row in the git-ignored `evals/draft_extracted.csv` by matching `input_text`, copy it into `extracted_inputs.csv` with only its case id changed to the case's id in the test set, in a commit of its own, and make no live call for it. If a promoted case has no saved row anywhere, this check has failed: stop. Never move a draft into the test set yourself (rule S1).

Before the first change, read `docs/legs/d1-contractor-search.md` (check 9 above all), `docs/legs/d2-report-summary.md`, and questions Q45 to Q53 in `docs/open_questions.md`.

### Rules for legs D3 and D4

- **Branches.** `leg/d3-name-search` from `main`, then `leg/d4-address-search` from `leg/d3-name-search`. One pull request per leg, each targeting `main`. Andres merges them in order. If leg D3 stops before its pull request opens, leg D4 does not depend on it: branch D4 from `main` instead, run it, and say so in both reports.
- **Live calls.** At most 10 live extraction calls across both legs. For these two legs this replaces the phase limit of 30 under "Rules for every Phase D leg", of which legs D1 and D2 used 27. Do not change the extraction prompt, because the evaluation scores extractions saved with prompt v3. Leg D3 uses five on the real app: the three V Pizza notes, `v pizza durbin`, and `v pizza lake buena vista` a second time, to show that rule S14 reaches the same company whichever way the place is read. Leg D4 uses up to three, on address notes on the real app. That is about 0.4 cents 🟡 (the plan's figure of $0.0004 a call). Never re-extract the checked or draft cases into the saved extraction files, because the evaluation scores the extractions saved there; the real-app runs above are the only live calls on those notes, and their results are reported, not saved. The second run of `v pizza lake buena vista` may read the note the same way as the first, and then it shows nothing new; the fixture test of rule S14 covers both readings, and the two live runs are only reported. No test calls the API.
- **No Snowflake,** as for legs D1 and D2. Running anything in Snowflake is a stop condition.
- **Public repo.** The rules of D1 and D2 hold: a case may name a company and never a person, and the draft cases appear only as counts by kind. An address appears in a commit, a test or a pull request only when it is already in `pipeline/seeds/test_set.csv`. Every other street in a test is invented.
- **Review.** Both legs are High. Give the three reviewers the Phase D hunts, unchanged. The rule added on Nov 26 under "Human review section" applies to both pull requests: the last round checks that each of the three questions can be answered from the Human review section alone.

### D3. The name search finds the company

- **Build in the order of rule S17.** First rules S11 and S12, then rule S13, then rule S14, measuring after each step against `main` at `051a928`. Show one table like check 9 of leg D1, with each checked case's place by rank and on the page after each step, and the draft cases by count only (moved up, moved down, stayed, by kind).
- **The query.** Two tests in `tests/test_search.py` read the text of `PostgresBackend.NEAREST_SQL`, so change them with the query. Explain the new `ORDER BY` term in the comments, line by line. `WideTableBackend.NEAREST_SQL` in `evals/run.py` is leg C2's comparison baseline and stays as it is, so `python -m evals.run --compare` will now show the two backends returning different candidates, by design. Say so in the leg report.
- **Rank order on the page (rule S12).** A company with a lower match level can now be shown above one with a higher level. On the 200 randomly drawn names of the speed check, count how many pages show that, and give the count only.
- **Speed.** Measure the name search as leg D1 did, with the same 200 randomly drawn names plus every specific checked case. The target is still a p95 under 1 second. If it misses with two different approaches, record the numbers and stop the leg. Do not loosen the target.
- **If `v pizza orlando` is still not first on the page** after every step that rule S17 keeps, say why with numbers. Do not add a rule to make it pass.
- **Tests.** One test for each of rules S11, S12, S13 and S14 that rule S17 keeps, failing on the old behavior. A rule left off gets no test, and the leg report says why. The test of rule S14 covers both ways the extraction read `v pizza lake buena vista`: the place as the city, and the place left in the business name. One test proves that the match levels of rule S4 come out as before under the new order. One test, on five companies whose levels come out Possible, Likely, Likely, Possible, Possible in rank order, proves that the tie count still reads the best level (Likely, two tied) and that the sentence of rule S12 appears. One test proves that the evidence line of rule S14 appears only when the typed city's words are in the company's name, and that the company's level is the same with and without it.

Done when the leg report holds:
- the evaluation on `main` at `051a928` and after the leg, on the checked and the draft cases in separate tables, by case group: top-1, recall at 5 and `wrong_match`;
- the table of each step described above, and which steps were kept;
- the five searches on the real app, with the top five each returned, and for both runs of `v pizza lake buena vista` the business name and city the extraction returned;
- the speed numbers and the count for rule S12;
- `pytest` and `ruff check src tests` passing with Postgres stopped;
- the number of live extraction calls made.

### D4. The address search, finished

- **Units and directions (rule S15).** Change `street_parts()`, `street_matches()`, `AT_HOUSE_NUMBER_SQL` and the loader step that builds `company_search_addresses`, then rebuild that table. The loader's check that it holds the same document numbers as `company_search` still runs before the swap. Give the database's size before and after.
- **The SQL and the Python rule must agree.** Rule S15 changes both the Python cut and the loader's cut of an address. Run leg D1's check 7 A again (the loader and Python cut a sample of addresses the same way) and check 8 again (the query and `street_matches()` keep the same rows, on 200 addresses drawn at random), and report how many differed. Both answers must be 0. Change the pinned query test with the query.
- **The crowded addresses again.** Rule S15 merges the suites of a building into one address, so more addresses pass the limit of 50. Count again, before and after: out of 200 random addresses, how many get the "too many" answer, and how many addresses in all hold more than 50 companies.
- **Only inactive companies (rule S16).** Add the sentence to `src/datum/wording.py`, and use it when the address search has no active match and at least one inactive one.
- **The page must say what is compared.** Rule S15 changes the comparison, so change the sentences that describe it in `src/datum/wording.py`: `ADDRESS_COMPARED` must say that office units and all twelve directions are not compared, and `ADDRESS_NOT_FOUND` and `ADDRESS_NOT_FOUND_IN_CITY` must stop advising the contractor to add a suite, and may advise adding an apartment, unit or lot number, because those are still compared.
- **The terminal (rule S18).** Change `src/datum/report.py` so an address-only note takes the same path as on the web page. The terminal's questions, `ASK_FOR_A_BUSINESS` and `ASK_FOR_MORE`, and its closing sentence `GIVING_UP`, all in `src/datum/wording.py`, still offer a street or a city. Make them ask for what the search now uses, as leg D1 did for the web pages, and remove any of them that nothing uses any more.
- **Speed.** Time the address search on 200 addresses drawn at random. The target is a p95 under 1 second, with the same stop rule as leg D3.
- **Tests.** One test for each of rules S15, S16 and S18 that fails on the old behavior. For rule S15, a stored address with STE matches a note without it, a note with SUITE matches a stored address without it, a stored APT still needs the note's APT, a stored `BLDG 2 APT 305` does not match a note without APT 305, and a stored SOUTH matches a typed S. For rule S18, the terminal and the web app give the same kind of answer and the same companies for one note, on a fixture.

Done when the leg report holds:
- the address case of the evaluation, before and after;
- checks 7 A and 8 run again, the counts of crowded addresses before and after, and the database's size before and after;
- the restaurant's address and one address with a STE or SUITE run on the real app, with the second chosen by leg D1's rule for draft addresses (at least one active company there whose name holds a legal-entity word, and no company there whose name could be a person's; skip it when unsure) and described by count and kind only;
- the speed numbers;
- `pytest` and `ruff check src tests` passing with Postgres stopped;
- the number of live extraction calls made.

### Cost

- **Claude API.** Legs D1 and D2 made 27 of their 30 live extraction calls. Legs D3 and D4 may make at most 10 more, about 0.4 cents 🟡.
- **Snowflake.** None.
- **Everything else is free.** Postgres runs on the Mac.
