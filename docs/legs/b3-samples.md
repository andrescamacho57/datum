# Leg B3: samples for Andres's hand checks

Branch `leg/b3-samples` (stacked on `leg/b2-flags`) · run 2026-11-18 (UTC) · status: **both files produced and on your machine. They are NOT in git: read section 3 first, it is the one decision in this leg that goes against the letter of the brief**

## 1. What I built

Two files for you to check by hand, and the two scripts that make them. I only produce the files; the checking is yours.

| File on your machine | What it is | Made by |
|---|---|---|
| `evals/link_sample_20.csv` | 20 CONFIRMED links: 8 federal lien, 6 DBPR license, 6 Duval. One row = "this record belongs to this company" | `snowflake/19_sample_confirmed_links.sql` |
| `evals/draft_test_cases_40.csv` | 40 draft lookup cases: a business name as the IRS or a license holder wrote it, and the company it should find | `snowflake/20_draft_lookup_cases.sql` |

**`link_sample_20.csv` columns**

| Column | What it holds |
|---|---|
| `company_name_as_registered` | The company's legal name on Sunbiz |
| `document_number` | Its Sunbiz document number |
| `source` | `federal_lien`, `dbpr_license` or `duval` |
| `source_record_id` | Lien filing number, license number as printed, or Clerk's instrument number |
| `matched_on` | `name_zip` or `unique_name` |
| `source_record_date` | Lien filed, license period began, or document recorded |
| `company_filing_date` | The company's own filing date on Sunbiz |
| `official_search_page` | Where to look the record up |
| `company_search_page` | Where to look the company up by document number |
| `verdict`, `verified_on`, `notes` | Empty, for you |

**`draft_test_cases_40.csv`** has the same eight columns as `pipeline/seeds/test_set.csv` (`case_id`, `case_group`, `input_text`, `expected_document_number`, `expected_entity_name`, `case_type`, `verified_on`, `notes`), so a checked row needs no reshaping. It is not pasted in as it is, though: fill in `verified_on`, replace the DRAFT sentence in `notes`, and give the row a new `case_id` (review round 1, section 7). Case ids run 101 to 140. Nothing was added to `test_set.csv`.

**How to check a link** (about two minutes a row):
1. Open the file: in the VS Code file explorer, click `evals`, then `link_sample_20.csv`.
2. Open the row's `official_search_page` in your browser and look up its `source_record_id`.
3. Open the row's `company_search_page`, type the `document_number`, and compare the name and address with the record from step 2.
4. Type `right`, `wrong` or `unsure` in `verdict`, today's date in `verified_on`, and anything odd in `notes`.

**Done when:** all 20 rows have a verdict and none says `wrong`. One `wrong` means the linking rule changes before any flag is shown.

## 2. Checks

**The two files were made with:**

```
cd ~/datum
mkdir -p evals
snow sql -c datum -f snowflake/19_sample_confirmed_links.sql --format csv > evals/link_sample_20.csv
snow sql -c datum -f snowflake/20_draft_lookup_cases.sql --format csv > evals/draft_test_cases_40.csv
```

`mkdir -p evals` makes the `evals` folder when it is missing and does nothing when it is there (`-p` is what stops it complaining). It was added in review round 1: no file under `evals/` is in git, so a fresh copy of the repo has no such folder, and `>` cannot write into a folder that does not exist.

**Shape of both files** (a throwaway Python check that reads them and prints counts only)

```
link sample: rows 20 columns ['company_name_as_registered', 'document_number', 'source', 'source_record_id', 'matched_on', 'source_record_date', 'company_filing_date', 'official_search_page', 'company_search_page', 'verdict', 'verified_on', 'notes']
  by source {'dbpr_license': 6, 'duval': 6, 'federal_lien': 8} | matched_on {'name_zip': 14, 'unique_name': 6}
  distinct companies 20 | blank cells in data columns 0
  R2 holds (record date >= company filing date): True
draft cases: rows 40 columns ['case_id', 'case_group', 'input_text', 'expected_document_number', 'expected_entity_name', 'case_type', 'verified_on', 'notes']
  case ids 101 .. 140 | distinct companies 40
  by origin and type {('lien', 'legal suffix written differently'): 10, ('lien', 'punctuation or spacing differs'): 10, ('license', 'legal suffix written differently'): 10, ('license', 'punctuation or spacing differs'): 10}
  status in notes {'A': 22, 'I': 18}
  every input has an entity word: True
  inputs equal to the registered name: 0
```

| Check | Result |
|---|---|
| 20 links: 8 federal lien, 6 DBPR license, 6 Duval | ✅ |
| Every link is CONFIRMED (the scripts read only `link_status = 'CONFIRMED'`) | ✅ |
| 20 different companies; no empty data cell | ✅ |
| 40 cases, 40 different companies, each with an expected document number | ✅ |
| Businesses only: every input name carries a legal-entity word | ✅ |
| Nothing added to `pipeline/seeds/test_set.csv` | ✅ (`git status` shows no change to it) |
| The two files are ignored by git | ✅ `git check-ignore -v evals/link_sample_20.csv evals/draft_test_cases_40.csv` prints both, from `.gitignore` lines 15 and 16 |

**Offline checks:** `pytest` → `60 passed`. `ruff check src tests` → `All checks passed!`. This leg adds no Python and no dbt model.

## 3. Decisions I made and why

**The two files are on your disk and not in the pull request.** The brief says to produce `evals/link_sample_20.csv` and `evals/draft_test_cases_40.csv`. I produced both, at those paths, and added both to `.gitignore`. Three reasons:

1. **The repo is public** (`gh repo view` says `PUBLIC`). A committed file is published to anyone.
2. **The links are unverified.** Each row of the sample puts a real company's name next to a tax lien, a license or a recorded lien or judgment. The whole point of the file is that nobody has checked those links yet. Decision d19 calls a lien on the wrong company the most expensive error Datum can make; publishing 20 unchecked ones is that error in miniature.
3. **Six rows are Duval.** Ruling R20 and the Phase A report say nothing from Duval is shown outside this repo until you say so, and the Clerk has not answered on terms of use. The brief tells me to flag anything about a source's terms, not to decide it. Not publishing is the choice that leaves the decision with you.

The draft test cases get the same treatment for a milder version of reason 2: their expected answers are unchecked, and half of the names come from tax lien debtor lists. Since review round 1 the `notes` column no longer says which half, but the case ids still do (101 to 120).

Nothing is lost by this: the scripts are in the pull request, the draw is fixed, and anyone with warehouse access gets the identical files by running the two commands above. Whether anything from `evals/` ever goes into git is your call, and section 4, item 1 says exactly what may and what may not.

| Other decisions | Why | Tradeoff |
|---|---|---|
| The sample is drawn in a fixed pseudo-random order (sorted by a checksum that includes the text `sample-2026-11-18`) | The file can be regenerated exactly, and a second checker sees the same 20 links. Script 08's `ORDER BY RANDOM()` gives a different sample every run | To draw fresh links, change that text in the script |
| DBPR sample rows are contractor licenses only, no `QB` records | A `QB` record has no number anyone can type into DBPR's search, so it can't be checked by hand | The 72,039 CONFIRMED `QB` links are not sampled. They need another way to be checked |
| Two extra columns for where to look (`company_search_page`) and three empty ones for your verdict | You need both pages to compare, and a place to write the answer | 12 columns, not the 9 listed |
| Each script is one statement with no `USE ROLE` / `USE WAREHOUSE` lines | Every statement prints a result, and those would land inside the CSV file. The `datum` connection already defaults to `SYSADMIN` and `datum_wh` | Breaks the pattern of scripts 01–18, and the header says why |
| Draft cases: 10 per origin whose legal suffix is written differently, 10 per origin that differ only in punctuation; none identical to the registered name | An identical name tests nothing. Splitting evenly keeps the harder kind from being crowded out | All 40 are near-exact names. No typos, abbreviations or vague notes |
| One case per company | 40 cases should exercise 40 lookups | A company with two interesting spellings appears once |
| Script 19 reads each source's search page from the seed table `datum.dev_reference.search_page_sources` (changed in review round 1, section 7) | A Snowflake script can't read dbt variables, but it can read the table dbt loads from `pipeline/seeds/search_page_sources.csv`. The script holds no address of its own for the three sources, so it cannot disagree with the rulings | The seed must be loaded before the script runs. A source with no seed row would leave the file short of 20 rows, which the row count shows. `company_search_page` (Sunbiz's search by document number) is still written in the script: it is where the company is looked up, and it is not one of the seed's three rows |

## 4. What I couldn't verify, and open questions for Andres

1. **Do you want anything from `evals/` in git?** My recommendation: no, keep both files local. Checked cases reach git when you paste them into `pipeline/seeds/test_set.csv`, and the result of the link check reaches git as counts in a report.
   - **Never run `git add evals/`.** A folder name stages every file in it, and `link_sample_20.csv` holds 6 Duval rows.
   - **The Duval rows stay out of git** (ruling R20: nothing from Duval is shown until the Clerk answers on terms of use, and this repo is public). So `evals/link_sample_20.csv` stays ignored. Leave its line in `.gitignore`.
   - **If you do want one file published, it is this one and only this one:** `evals/draft_test_cases_40.csv`, after your check. It has no Duval rows. Delete only its own line (`evals/draft_test_cases_40.csv`) from the bottom of `.gitignore`, then run `git add .gitignore evals/draft_test_cases_40.csv` and commit. Before that, renumber the case ids, because ids 101 to 120 mark the names that came from tax lien debtor lists.
2. **I verified none of the 20 links.** That is the hand check, and it is yours. What to look for, from leg B1: about 1% of CONFIRMED links join names whose legal form differs (`INC` against `LLC`). If one of those turns up wrong, the fix is a small addition to ruling R1.
3. **The federal lien search address in the sample is the state's search hub**, not the lien search form itself (leg B2, section 4, item 1). You will need one extra click to reach "search by document number".
4. **The 40 draft cases are the easy kind.** The plan asks for at least 5 `NEEDS_MORE_INFO` cases, 5 inactive companies and 5 near-twins. Inactive is covered (18 of 40). The other two kinds can't come from CONFIRMED links: they come from the AMBIGUOUS and NO_MATCH records, where a person has to find the right answer first.
5. **20 links is a small sample.** Zero wrong in 20 says the true error rate is probably under about 14% (the 95% bound; the quick version is the "rule of three", 3 ÷ 20 = 15%), not that it is zero. The plan's gate is 30 or more; ten more rows are one edit to script 19.

## 5. Credits used

**About 0.093 credits** on `datum_wh` (roughly $0.19).

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"
after B2 (23:44 Pacific, Nov 17):  0.445662778
after B3 (23:50 Pacific, Nov 17):  0.538446111
```

**Phase B as a whole: about 0.54 credits (roughly $1.08), against a cap of 3.** B0 0.159 · B1 0.116 · B2 0.170 · B3 0.093.

## 6. Three questions you should be able to answer

1. All of B1's and B2's tests pass. Why is a hand check of 20 links still needed, and what can it find that no dbt test can?
2. The sample is sorted by a checksum instead of `ORDER BY RANDOM()`. What do you gain, and how would you draw a different 20?
3. `git status` is clean, yet two new files sit in `evals/`. Which file makes git ignore them, and why were they kept out of a public repository?

## 7. Review round 1 (2026-11-19)

Pull request 7 got a Standard review under `REVIEW.md` (one reviewer, fresh context): **4 findings, 1 Important and 3 Nit.** All four are fixed, one commit each. Both files were then regenerated on your machine with the fixed scripts. They are still not in git.

```
review (4 findings) ──▶ one commit per finding ──▶ run both scripts twice ──▶ count ──▶ this section ──▶ push ──▶ reply on the pull request
```

### What changed, finding by finding

| Finding | What was wrong | What changed | The check that catches it | Commit |
|---|---|---|---|---|
| **Important.** Script 19 sent the DBPR hand check to a replaced address | The script had its own copy of the three official search addresses. Its DBPR copy was the one ruling R27 replaced, so 6 of the 20 rows pointed at a page the rulings no longer name | `official_search_page` is read from the seed table `datum.dev_reference.search_page_sources` (a seed is a small CSV file, here `pipeline/seeds/search_page_sources.csv`, that dbt loads as a table). The script maps its own labels to the seed's: `federal_lien` → `sunbiz_flr`, `dbpr_license` → `dbpr`, `duval` → `duval`. No address for those three is typed in the script. The false comment on the old line 67 is gone, and the row in section 3 says what the script does now | Every `official_search_page` in the file is a row of the seed: 0 outside it (6 before). `git grep -n wl11 -- snowflake pipeline` prints nothing | `6ffde63` |
| **Nit 1.** The fixed order could tie | A tie is two rows with the same sort value: the database may return them in either order, so "fixed" was not guaranteed. Script 19 kept a link as two rows when two debtors on one lien were confirmed in two different ways. Script 20 tied when a company was spelled the same way on a lien and on a license | Script 19: one row per (`source`, `source_record_id`, `document_number`), taking `MIN(matched_on)`. Script 20: `drawn_from` is now part of the checksum that picks one spelling per company | Counted with each script's own steps on the real data. Script 19: links counted more than once 1 → 0. Script 20: companies with a tied sort value 30 → 0. Each script run twice gives byte-identical files | `e42e808` |
| **Nit 2.** Two sentences led to publishing what must stay private | Section 4 item 1 said `git add evals/`, which stages both files, 6 Duval rows included. Script 20's `notes` column said "Spelling from a federal lien debtor name" beside a real company, and its header said a checked row could be pasted into the public `test_set.csv` as it is | Section 4 item 1 now says never to add the folder, that the Duval rows stay out of git (ruling R20), and names the one file that may be added. The `notes` column is neutral: `DRAFT, not verified. Company status on Sunbiz: A.` The header says what to do before pasting a row | 0 of 40 notes mention a lien, a license, the IRS or DBPR (40 before). All 40 match the neutral sentence exactly | `3efff05` |
| **Nit 3.** The run commands failed on a fresh copy of the repo | Nothing under `evals/` is in git, so a fresh clone has no `evals` folder, and `>` cannot write into a folder that does not exist | `mkdir -p evals` comes before the run command in both script headers and in section 2 | In an empty folder the redirect fails without it ("no such file or directory") and works with it | `b09f56f` |

### What the fixes did to the two files

| File | Before and after |
|---|---|
| `evals/link_sample_20.csv` | The same 20 links in the same order. The only cells that changed are the 6 DBPR search pages. The one link that used to be counted twice was not among the 20 drawn |
| `evals/draft_test_cases_40.csv` | The same 40 cases (same input text, same expected company). Only the `notes` text changed. The new checksum picked a different spelling for 48 of the 99 companies that have more than one, and none of those 48 is among the 40 drawn |

**Both files were overwritten.** Before running, I counted the cells you fill in: 0 rows of either file had a `verdict` or a `verified_on`, so no hand-check work was lost.

### Check outputs (counts only, no rows)

Both scripts were run the way their headers say, then a second time into a scratch folder outside the repo:

```
cd ~/datum
mkdir -p evals
snow sql -c datum -f snowflake/19_sample_confirmed_links.sql --format csv > evals/link_sample_20.csv      exit 0
snow sql -c datum -f snowflake/20_draft_lookup_cases.sql --format csv > evals/draft_test_cases_40.csv     exit 0

link_sample_20.csv: run 1 and run 2 identical        (cmp; SHA-256 of both starts fd7937e3be44acb8)
draft_test_cases_40.csv: run 1 and run 2 identical   (cmp; SHA-256 of both starts 8cfe17ae31dd5f2c)
```

Shape of both files (a throwaway Python script that prints counts and never a row):

```
link sample: data rows 20 | columns 12
  by source {'dbpr_license': 6, 'duval': 6, 'federal_lien': 8} | matched_on {'name_zip': 14, 'unique_name': 6}
  official_search_page values that are not a row of the seed: 0 (old file: 6 )
  rows whose page is not the seed row for their own source: 0
  distinct official_search_page values: 3 | rows containing 'wl11': 0
  links counted more than once in the file: 0 | distinct companies 20
  blank cells in data columns: 0 | R2 holds (record date >= company filing date): True
  same 20 links, same order as the Nov 18 file: True | cells that differ, by column: {'official_search_page': 6}
draft cases: data rows 40 | columns 8 | same columns as test_set.csv: True
  case ids 101 .. 140 | distinct companies 40
  by id half and type {('ids 101-120', 'legal suffix written differently'): 10, ('ids 101-120', 'punctuation or spacing differs'): 10, ('ids 121-140', 'legal suffix written differently'): 10, ('ids 121-140', 'punctuation or spacing differs'): 10}
  notes that are not the neutral sentence: 0 | notes mentioning lien, license, IRS or DBPR: 0 (old file: 40 )
  status in notes {'A': 22, 'I': 18} | verified_on filled: 0
  every input has an entity word: True | inputs equal to the registered name: 0
  cases also in the Nov 18 draft (same input and company): 40 of 40 | same companies: 40
```

The seed table in Snowflake holds the same three rows as `pipeline/seeds/search_page_sources.csv` (`sunbiz_flr` R9, `dbpr` R27, `duval` R21), read with `snow sql -c datum -q "SELECT source, ruling, search_page_url, looked_up_by FROM datum.dev_reference.search_page_sources ORDER BY source"`.

Ties, counted by running each script's own steps with a counting `SELECT` in place of the last one:

```
script 19, step 2 (one_per_link)                     before the fix    after the fix
  rows                                                72699             72698
  distinct (source, source_record_id, document_number) 72698            72698
  links counted above 1                               1                 0
  highest count for any one link                                        1
  sort values shared by two rows in step 3                              0
  links with two record dates (so MIN(source_date) changes nothing)  0

script 20, step 4 (one_per_company)                  before the fix    after the fix
  companies                                           15859             15859
  companies with a tied sort value                    30                0
  sort values shared by two rows in step 5                              0
```

Offline checks:

```
$ git grep -n wl11 -- snowflake pipeline
(no output, exit status 1: nothing matched)
$ ruff check src tests
All checks passed!
$ pytest -q
60 passed in 0.20s
```

The old address still appears once in git, in `docs/legs/b2-flags.md`, where that report records what ruling R27 replaced. That is history, not something a script reads.

### Three things I did not change, for you to know

1. **`company_search_page` is still typed in script 19** (`https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber`). The finding and the seed cover the three pages where a *record* is looked up. This fourth address is where the *company* is looked up, and the seed has no row for it. A seed row needs a ruling, so adding one is your call.
2. **The case ids in the draft file still show where a name came from.** Script 20 numbers the lien spellings 101 to 120 and the license spellings 121 to 140, and the script is public. A neutral note next to id 105 would still tell a reader of the script that the name came from a tax lien list. The review did not ask for this, so I did not change the numbering. I wrote it into the script's header and into section 4 item 1 instead: give a row a new `case_id` when it moves into `test_set.csv`. My recommendation is to leave the script as it is and renumber on the way in, since `test_set.csv` numbers its own cases anyway (it stops at 10 today).
3. **Round 2 of the review is still owed.** `REVIEW.md` says the next round reads only the new diff. Nothing was merged.

### Credits used in review round 1

**About 0.06 credits** on `datum_wh` (X-Small), roughly $0.12 at the $2 per credit this report uses in section 5. This covers five script runs (two each for the proof, one scratch run after the first fix), the seed read and five counting queries.

```
snow sql -c datum -q "SELECT COUNT(*) AS hours, SUM(credits_used) AS credits FROM TABLE(datum.information_schema.warehouse_metering_history('2026-11-19 00:00:00 -08:00'::timestamp_ltz, CURRENT_TIMESTAMP(), 'DATUM_WH'))"
before the round's runs (00:25 Pacific, Nov 19):  0.023993056
after the last query     (00:30 Pacific, Nov 19):  0.083229167
difference:                                       0.059236111
```

The first reading is not zero because the meter counts from midnight Pacific and earlier work had already used some of that hour. One small query of this round (the seed read) ran before the first reading. The second reading was taken while the warehouse was still running, so the meter can add a little for the last minute before it suspends.
