# Florida master brief (for Fable 5.2 in Claude Code)

Kickoff line Andres types: `Read docs/prompts/florida_master.md. Run Phase A only.`
Later: `Read docs/prompts/florida_master.md. Run Phase B.` then `Run Phase C.` Never start a phase you weren't told to run.
Phase A finished Nov 12, 2026 (three legs, reports in `docs/legs/`).
Phase B finished Nov 19, 2026 (four legs). Leg C0 followed the same day and added rulings R29 and R30.

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
- The last review round also checks the `## Human review` section against the diff. The reviewer reads only the diff, so paste the full text of the section into its prompt. At High tier, give the section to the fourth agent, the one that checks the findings, and not to the three reviewers that each hunt one thing. A sentence in the section that the diff does not support, or a risk it leaves out that the leg report marks 🔴 or 🟡, is an `Important` finding. A sentence about the tier, the merge order or an open question is checked against `REVIEW.md`, `docs/open_questions.md` or the list of open pull requests, and not against the diff. The reviewer cannot see GitHub, so paste the output of `gh pr list` into its prompt together with the section.
- Add one row for the pull request to `docs/review_log.csv`.
- Never ask a question or wait for approval during review.

**Human review section**: the pull request body starts with `## Human review`. Andres reads it before anything else, in under 5 minutes, and it has to tell him everything he needs without opening the leg report: enough to explain the change back, answer the three questions and make his decisions. It does not replace reading the diff on a High-tier change. There it tells him what the change does and where in the diff to read line by line. The leg report below it keeps its full detail, because later agents read that. Nothing in the leg report is shortened to make room.
- Write it the way a colleague would explain the change out loud to someone who was not there. Use full sentences with a subject and a verb. Do not write a bold label followed by clipped fragments, such as "**Your decisions.** Dropping the old index, and a host for 5.5 GB." Write "The decisions that are yours", and then a numbered list in which each decision is a full sentence or a question, followed by the facts he needs to decide it.
- It is as long as the essentials need, which is usually 300 to 600 words, and never more than 800. Count the words outside code blocks, so the diagram does not count. The limit is on what goes in, not on how it is said: leave a detail out before you shorten a sentence into a fragment. The items under "What is not proven" are never the detail that is left out: shorten "What was built" and "If you open the code" first. If every item still cannot fit, go over the limit and say so in one sentence at the end of the section.
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
