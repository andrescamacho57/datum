# Leg D2: a summary first, and the details below

Branch `leg/d2-report-summary` (stacked on `leg/d1-contractor-search`) · pull request [#26](https://github.com/andrescamacho57/datum/pull/26) · run on Nov 25, 2026 · risk tier **High** · status: **built and reviewed, with every check passing. The Deep review ended in its second round with no finding, and it raised no Important finding in either round. Nothing is merged.**

This is the second and last leg of Phase D. On Nov 24 the report overwhelmed Andres: it opened with a table of record fields, and a contractor needs the answer to their question first. The same day, the first company on his shortlist was inactive, and the only sign of it was the last line of its reasons. This leg changes how the report and the shortlist are laid out. It changes no search rule and no fact.

**The short version**

- **A report now opens with a summary of four sentences.** For the company of checked case 1, built from the real data, it reads: "Active with the state as of Oct 7, 2026. Florida corporation (for profit), on record since 1998. No flags found in the sources checked." Then comes the sentence every report carries, word for word: "Datum shows a record only when it can confirm that the record belongs to this company. A record filed under a similar name or at a different address is not shown."
- **The summary cannot disagree with the records under it.** Its first two sentences are built from the very values the record table is built from. The tests read the summary and the table off the finished page and fail when the status, the year, the count of flags or the date differ.
- **The details sit under a heading,** "The records behind this summary": the company record table and the two lists of sources. The flags the summary counts come between the summary and that heading. No fact, caveat or citation changed.
- **The shortlist marks an inactive company beside its name** with "Inactive with the state", on the web page and in the terminal. The same words left its list of reasons on the shortlist, so the shortlist says it once. A report keeps them where it had them.
- The five reports of leg C3 were rebuilt from the real Postgres data, each with its summary (check 2).
- Five screenshots at 390 pixels wide show the shortlist, three reports and the address page of leg D1 (check 3).
- The offline tests pass with Postgres stopped: **530**, of which 18 are new in this leg.
- The leg made **no** live extraction call and used **no** Snowflake.
- The Deep review ran two rounds. Round 1 found 5 small problems and no Important one, and round 2 found nothing.

**What is left for Andres**

1. **Read the new sentences** in section 1. They are the first words a contractor reads on a report, and wording is your call.
2. **Rule on question Q53,** which holds three choices I made in the summary's wording where the brief gave an example and not a rule.
3. **Look at the pages.** The five screenshots are under `data/screens/` on your Mac, in files whose names begin with `d2_`. Section 7 says how to open the real app.
4. Answer the three questions in section 6, because this is a High-tier change.

Merge pull request 25, leg D1, before this one. This branch sits on top of it.

---

## 1. What I built

### The picture

```
 A REPORT, BEFORE                              A REPORT, NOW

 title, and the day it was built               title, and the day it was built
 (a caution, for a Possible match)             (a caution, for a Possible match)
 the summary line, one sentence                THE SUMMARY                                        new
 the sentence every report carries               status as of the published date                  new
 the company record table                        entity type, and the year on record              new
 the flags                                       the summary line: how many flags
 sources checked                                 the sentence every report carries
 not checked                                   the flags
 how the company was identified                THE RECORDS BEHIND THIS SUMMARY                    new heading
 the disclaimer                                  the company record table
                                                 sources checked
                                                 not checked
                                               how the company was identified
                                               the disclaimer

 A SHORTLIST CARD, BEFORE                      A SHORTLIST CARD, NOW

 INVENTED ROOFING CORP                         INVENTED ROOFING CORP · Inactive with the state    new
 Strong · Document number · TAMPA, FL          Strong · Document number · TAMPA, FL
 - name matches (...)                          - name matches (...)
 - principal city on record begins ...         - principal city on record begins ...
 - INACTIVE with the state                       (the third reason is gone from the SHORTLIST: it is said beside the name)
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| `Report.headline` in `src/datum/models.py` | Two new `Fact`s on every report: the status sentence and the entity-type sentence. A `Fact` is a statement that cannot exist without its source address and fetch time | Working rule S9, and rule W1: everything a page states about a company is a `Fact` |
| The headline's making, in `ReportBuilder.build()` in `src/datum/report_builder.py` | The builder works out the status, the entity type and the date on record once. It builds the record table's rows and the two headline sentences from those same values | So the summary and the table cannot say different things. The brief asks for exactly this |
| `summary_status_text()`, `summary_record_text()` and `long_day_text()` in `src/datum/wording.py` | The functions that word the two sentences, and the one that writes a date as "Oct 7, 2026" | Every fixed sentence lives in `wording.py`. A gap in the record gets its own sentence and is never filled in |
| `src/datum/web/templates/report.html` and `render_markdown()` | The page, and the report the terminal writes, laid out in the new order | The brief asks for the summary above the record table in both |
| `Candidate.mark` in `src/datum/models.py`, set in `candidate_for_page()` | "Inactive with the state", as a `Fact`, on the page model of an inactive company | Working rule S10 |
| `evidence()` in `src/datum/search.py` | The reasons behind a match level. It gained one switch, `status_marked`. A shortlist passes it, and then an inactive company's status is left out of its reasons. Every other caller gets all the reasons, as before | Rule S10: "the same words leave its evidence list, so it is said once". The brief also says a report keeps every fact it shows today, and a report's line about how its company was identified is built from the same reasons |
| `src/datum/web/templates/_candidate.html` and `show_shortlist()` in `src/datum/report.py` | The shortlist card on the page, and the shortlist line in the terminal, each with the mark beside the name | The terminal and the web app are built from the same page model, so they cannot drift apart |

### The sentences this leg added or changed

These are the entries of `src/datum/wording.py` that are new or different. A piece in curly braces is filled in when the sentence is used.

| Name in `wording.py` | The text | When it is shown |
|---|---|---|
| `SUMMARY_STATUS` | {status} with the state as of {day}. | The status is Active or Inactive. The day is the date the state published the record |
| `SUMMARY_NO_STATUS` | No status with the state is on record as of {day}. | The state has no status for the company. No company is in that case today |
| `SUMMARY_TYPE_SINCE` | {entity_type}, on record since {year}. | The usual case |
| `SUMMARY_TYPE_DATE_AHEAD` | {entity_type}, with a date on record in {year}, which is in the future. | The date on record has not come yet. 35 companies are in that case |
| `SUMMARY_TYPE_NO_DATE` | {entity_type}, with no date on record. | 1,964 companies have no date on record |
| `SUMMARY_NO_TYPE` | Entity type not on record | Stands where the entity type would, when the state gave none |
| `HEADING_RECORDS` | The records behind this summary | The heading over the record table and the two lists of sources |
| `INACTIVE_MARK` | Inactive with the state | Beside the name of an inactive company on a shortlist |
| `EVIDENCE_INACTIVE` (unchanged, shown in fewer places) | INACTIVE with the state | No longer on a shortlist, where the mark replaces it. Still in the line of a report that says how its company was identified, and in the terminal's question about a Possible match |

The counts of 35 and 1,964 companies are leg C3's, from question Q37 in `docs/open_questions.md`. I did not count them again.

Every other sentence on a report is unchanged, including the summary line ("No flags found in the sources checked." or "2 flags found in 3 sources checked.") and the sentence every report carries.

### Files

| File | New or changed |
|---|---|
| `src/datum/wording.py`, `tests/test_wording.py` | Changed. 13 tests, 1 of them new |
| `src/datum/models.py`, `tests/test_models.py` | Changed: `Report.headline` and `Candidate.mark`. 26 tests, 1 of them new |
| `src/datum/report_builder.py`, `tests/test_report_builder.py` | Changed. 39 tests, 8 of them new |
| `src/datum/web/templates/report.html`, `src/datum/web/templates/_candidate.html`, `tests/test_web.py` | Changed. 101 tests, 6 of them new |
| `src/datum/search.py`, `tests/test_search.py` | Changed: `evidence()` only. 105 tests, 1 of them rewritten |
| `src/datum/report.py`, `tests/test_report_cli.py` | Changed: one line of `show_shortlist()`. 31 tests, 2 of them new |
| `docs/open_questions.md` | Changed: Q53 added |

No Snowflake object, no dbt model and no Postgres table was touched. No search rule changed: the same companies come back in the same order with the same match levels.

---

## 2. Checks

### Check 1: the tests

```
brew services stop postgresql@17      → Successfully stopped `postgresql@17`
pg_isready                            → /tmp:5432 - no response
pytest                                → 530 passed
ruff check src tests                  → All checks passed!
brew services start postgresql@17     → Successfully started `postgresql@17`
pg_isready                            → /tmp:5432 - accepting connections
```

✅ With the database server stopped, all 530 tests pass. 512 existed at the end of leg D1 and 18 are new.

**The tests the brief asks for**

| What the brief asks | The test | The input that makes it fail |
|---|---|---|
| The five reports of leg C3 are rendered, and the test fails if the summary's status, year or count differs from the facts below it | `test_the_summary_at_the_top_agrees_with_the_facts_below_it`, in `test_report_builder.py`, run for the five fixture companies | It reads the summary and the table off the finished report. A summary whose status is not the table's, whose year is not the year in the "Date on record" row, or whose count is not the number of flag cards |
| The same, on the page a contractor sees | `test_the_report_page_opens_with_a_summary_that_agrees_with_the_records_under_it`, in `test_web.py`, run for the same five | The same three, read off the page |
| It fails if the summary's date differs from the record's `published_on` | `test_the_summarys_date_is_the_records_own_published_date_and_not_the_snapshots` | A company first seen in a daily file, published on Nov 5. The summary must say "as of Nov 5, 2026" |
| It fails if rule W4's sentence does not come right after the summary line | Both of the first two tests | The sentence moved anywhere else on the report, or left out |
| The banned-words test covers the summary | The two tests above, and the older `test_no_report_holds_a_word_that_reassures_or_judges` and `test_no_report_page_holds_a_word_that_reassures_or_judges`, which read the whole report | Any of rule W4's eight words anywhere on a report, the summary included |

**The other new tests**

| The test | The input that makes it fail |
|---|---|
| `test_the_summary_says_a_gap_in_the_record_and_never_fills_it_in` | A company with no status, no entity type or no date on record, or a date still to come. It fails if a gap is printed as "None", if a missing status is called inactive, or if a future date is called "on record since" |
| `test_a_possible_match_still_says_so_before_the_summary` | A report picked at the level Possible. The caution must come before the summary |
| `test_the_summary_sentences_say_the_status_as_of_a_date_and_never_fill_a_gap`, in `test_wording.py` | Each of the summary's sentences, typed out, and all twelve month names |
| `test_the_two_sentences_at_the_top_of_a_report_are_facts_and_there_are_exactly_two`, in `test_models.py` | A headline handed over as bare text, or with one sentence, or with none |
| `test_an_inactive_company_is_marked_beside_its_name_on_the_shortlist_and_the_words_are_said_once`, in `test_web.py` | A shortlist with one inactive company and four active ones. It fails if the mark is missing, if it is on an active company's card, if the words appear twice, or if a company with no status is marked |
| `test_the_terminal_marks_an_inactive_company_beside_its_name_and_says_it_once`, in `test_report_cli.py` | The same, in the terminal |
| `test_evidence_ends_with_the_status_of_an_active_company_and_never_guesses_one`, in `test_search.py` | An inactive company whose status is among the reasons a shortlist asks for, or missing from the reasons anybody else asks for |
| `test_the_terminals_question_about_a_possible_match_still_gives_an_inactive_companys_status`, in `test_report_cli.py` | An inactive company picked at the level Possible. The question, and the saved report's line, must still give its status |

✅ I made twelve deliberate breaks of the code, one at a time, and each failed at least one test. The last four were made after the review, on the final code.

```
the summary's status is not the record's:                          4 failed
the summary's year is the year the report was built:              10 failed
the summary's date is the day the report was built:               13 failed
the W4 sentence moved below the table:                            11 failed
the summary's count typed into the template:                      11 failed
the mark removed from the shortlist card:                          1 failed
a company with no status marked as inactive:                       1 failed
the mark removed from the terminal's shortlist:                    1 failed
the builder asks the machine's clock for today:                    1 failed
the summary printed a second time lower down the page:             5 failed
an inactive company's status left out of every list of reasons:    3 failed
the shortlist says an inactive company's status twice:             3 failed
```

### Check 2: the five reports of leg C3, rebuilt from the real data

A scratch script built each report with the real Postgres backend and saved it under `data/reports/`, which git ignores. The companies are named by document number only, as in leg C3.

```
kind                            document number   flags   the summary's first three sentences
a federal lien flag             207670            2       Active with the state as of Oct 7, 2026. Florida corporation (for profit), on record since 1957. 2 flags found in 3 sources checked.
an inactive license             361997            1       Active with the state as of Oct 7, 2026. Florida corporation (for profit), on record since 1970. 1 flag found in 3 sources checked.
an inactive company             000001            1       Inactive with the state as of Oct 7, 2026. Florida corporation (for profit), on record since 1870. 1 flag found in 3 sources checked.
a new company                   A26000000239      1       Active with the state as of Oct 7, 2026. Florida limited partnership, on record since 2026. 1 flag found in 3 sources checked.
no flags, found by the search   P98000033661      0       Active with the state as of Oct 7, 2026. Florida corporation (for profit), on record since 1998. No flags found in the sources checked.
```

| Kind | Document number | File under `data/reports/` | What the check showed |
|---|---|---|---|
| A company with a federal lien flag | `207670` | `207670_20261125.md` | ✅ The summary counts 2 flags, and two lien cards follow it |
| A company with an inactive license | `361997` | `361997_20261125.md` | ✅ The company is active with the state, and the summary says so. Its flag is the license |
| An inactive company | `000001` | `000001_20261125.md` | ✅ "Inactive with the state as of Oct 7, 2026." and 1 flag, with no "No flags found" line |
| A new company | `A26000000239` | `A26000000239_20261125.md` | ✅ "on record since 2026", and the flag "New company" |
| A company with no flags | `P98000033661` | `P98000033661_20261125.md` | ✅ The exact no-flags line. It was found through the real search, from the saved extraction of checked case 1, so it carries an identification line |

- ✅ In all five, the sentence every report carries comes right after the summary, the summary stands above the heading "The records behind this summary", and no banned word is anywhere in the report. The script checked each.
- ✅ No call to the Claude API was made. The fifth company's name and city came from the saved extraction.
- 🟡 The second company shows why the summary's first sentence is about the COMPANY's status only. The company is active, and a license it holds is inactive. A reader could take "Active with the state" as covering the license. The flag card right under the summary says "inactive" for the license.
- 🟡 "on record since 1870" is the year of the date the state has on record for that company. I did not check it against anything else.

### Check 3: the screenshots at 390 pixels

✅ Google Chrome is installed, and five screenshots are under `data/screens/`, which git ignores. They show the invented fixture companies, so they hold no real company.

| File | The page |
|---|---|
| `d2_1_shortlist_with_an_inactive_company.png` | A shortlist of five. The first company is inactive, and its name is followed by "· Inactive with the state" |
| `d2_2_report_with_flags.png` | A report with two federal liens |
| `d2_3_report_inactive_company.png` | The report of an inactive company |
| `d2_4_report_no_flags.png` | A report with no flag |
| `d2_5_address_results.png` | The address page of leg D1, with two active companies and a count of two inactive ones |

- ✅ I looked at the first, the third and the fifth. In each, every line wraps inside the 390 pixels, the two-column table fits, and nothing is cut off at the right edge. The summary is the first thing under the title and the date, in bold, and the sentence every report carries is under it.
- 🟡 I did not look at the second and the fourth. They are the same template as the third, with more and fewer flags.
- The first attempt at the screenshots cut the wrong part of each picture, and it showed the page's right half only. The tool that cuts a picture reads an offset of 0 as "from the centre". The pictures in the table are the second attempt.
- 🟡 A screenshot is not a phone. Section 7 says how to open the app on yours.
- The fifth picture is the one leg D1's report said was missing.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | The summary writes its date as "Oct 7, 2026" | The brief's example does. A contractor reads it more easily than 2026-10-07 | 🟡 The rest of the report writes dates as 2026-10-07, so one page has two forms. Question Q53 |
| 2 | The summary gives the entity type exactly as the record table does, such as "Florida limited liability company (LLC)" | The brief says the summary is built from facts the report already shows. Its example leaves out "(LLC)" | Three more characters than the example. Question Q53 |
| 3 | The summary says "on record since 2022" and leaves the note "may be an effective date" to the table | The brief's example does. The table under the heading still carries the note, word for word | 🟡 The summary states the year more firmly than the record supports. Question Q53 |
| 4 | A date on record that is still to come is not called "on record since" | 35 companies have such a date, one in the year 2120. "On record since 2120" would be false | One more sentence that almost nobody will see |
| 5 | A company with no status, no entity type or no date on record gets a sentence that says so | `CLAUDE.md` rule 3: a gap is never filled with an inference | Three more sentences that almost nobody will see |
| 6 | The flags come between the summary and the heading "The records behind this summary" | The summary's third sentence counts the flags, so they are what a reader looks for next. The brief puts "the company record table and the source lists" under the heading, and does not say where the flags go | The record table is further down the page than it was |
| 7 | The summary line and the sentence every report carries are one bold paragraph and one plain one | The summary line is the answer to "is anything on the record". The sentence after it says how far the check reaches, and bold would make it read like a warning about this company | None |
| 8 | The mark is a `Fact`, like everything else a shortlist states about a company | Rule W1 | None |
| 9 | A company with no status on record is not marked | No status is not "inactive". Its reasons still end "status not on record" | None. Every company has a status today |
| 10 | An inactive company's status left the reasons on the shortlist only. A report's line about how its company was identified, and the terminal's question about a Possible match, keep it | Rule S10 is about the shortlist. The brief also says to keep every other fact a report shows today, in the same words. My first version took the status out of all three, and the review found it | The function that gives the reasons has one more switch |

---

## 4. What I couldn't verify, and open questions for Andres

### What I couldn't verify

1. 🟡 **Whether a contractor reads "Active with the state" as a verdict.** The brief gives the wording, and rule W4 says a report never reassures. The sentence states the status on a date and nothing else. Only a contractor reading it can say how it lands.
2. 🟡 **That "on record since YEAR" is supported by the record** (decision 3). The table says the date "may be an effective date".
3. 🟡 **The two forms of a date on one page** (decision 1).
4. 🟡 **The pages on a real phone.** I looked at three of the five screenshots.
5. 🟡 **The counts of 35 and 1,964 companies** behind two of the new sentences. They are leg C3's.
6. 🟡 **That the mark beside a name is noticed.** It is in the heading of the card, in smaller type than the name. Andres did not see the old line. Whether he sees this one is for him to say.

### Questions added to `docs/open_questions.md`

| # | The question, in short |
|---|---|
| Q53 | Three wording choices in the summary where the brief gave an example and not a rule: the form of the date, the entity type's label, and "on record since" without the note about an effective date |

### The review

- **Tier:** High. The leg changes the wording on a report, which `REVIEW.md` names as High, and the brief names both legs of Phase D as High.
- **Depth:** Deep. In round 1, three `reviewer` subagents ran in parallel, each with one of the hunts the brief sets for Phase D, and a fourth then checked every finding against the code. A security review ran alongside, because `src/` changed.
- **Rounds:** two. The second found nothing, so the review ended there.
- **Findings over the rounds:** 0 Important and 5 Nit, all in round 1. Four Nits are fixed, and one is closed with a reason because it is the brief's own wording and a decision that is Andres's (question Q53).
- **What was not reviewed:** commit `0d44dd0`, which corrects one comment in a test. The commits after it add this report and the pull request's row to `docs/review_log.csv`. Reviewers are told to skip leg reports, so this report's own text was checked only where the Human review section repeats it.

**Round 1** (three reviewers, then a verifier, on the leg's first two commits, and the security review).

The three reviewers posted 5 findings, and the verifier confirmed all 5: **0 Important and 5 Nit.** `REVIEW.md` allows three Nits in a review. The three reviewers worked apart, so together they posted five, and all five are answered.

| Finding | Tag | Answer |
|---|---|---|
| The status of an inactive company had left more than the shortlist. The same list of reasons feeds the line of a report that says how its company was identified, and the terminal's question about a Possible match. The brief says to keep every other fact a report shows, in the same words | Nit. Nothing false was shown, because the report still said Inactive in its summary, its flag and its table | Fixed. The reasons are complete again for every caller, and only a shortlist asks for them without that status (decision 10). Two tests hold it |
| The summary says "on record since" a year without the note that the date may be an effective date, which goes with that date everywhere else | Nit, and the brief's own wording | Closed with a reason: it follows the example in rule S9 word for word, and wording is Andres's. It is the third part of question Q53 |
| Nothing tested that "a date in the future" is measured from the day the report is built. The only future date in a test was the year 2120, which is in the future by any clock | Nit | Fixed. A date one day after the fixture's build day now checks it |
| Nothing counted the summary, so a second copy of it lower down the page would have passed both summary tests | Nit | Fixed. Both tests now count it |
| One assertion compared the test's own input with itself | Nit | Fixed. It is replaced by a check that a report cannot be built without its two sentences |

- ✅ The reviewer that hunted ranking and matching found nothing. It confirmed that no caller reads the length or the last item of the reasons to decide a level, an order or a tie, and that the evaluation scores nothing differently.
- ✅ The reviewer of wording checked each new sentence against every case the code can show it in, and found each true: no status, an entity type with no label, no date, a date still to come, and a company from a daily file. It did not read the bold status line as a verdict.
- ✅ The security review reported no vulnerability. It put markup and template code into the entity type and into a company's name, and all of it came out escaped on the report page and the shortlist. It left one side note: the bold summary line of the report the terminal writes escapes nothing, so an entity type holding a line break or two asterisks would break the Markdown. No such value can arrive today, because the code is at most 15 characters cut from one line of the state's file, and nothing shows that Markdown as a web page. I changed nothing.

**Round 2** (one reviewer on the two commits that followed round 1, doing all three hunts on that diff, and reading the Human review section).

**0 findings.**

- ✅ The reviewer followed every caller of the function that gives the reasons. The report's line and the terminal's question get all the reasons. Every shortlist entry, on the page and in the terminal, on the list or under it, is built in one place that both sets the mark and leaves the status out of the reasons. So an inactive company's status is on a shortlist exactly once, never missing and never doubled.
- ✅ It named, for each new or changed assertion, an input that makes it fail.
- ✅ It checked the Human review section against the whole leg's diff, found all six unproven items of this report in it, and found no company, person or address named.
- It listed the numbers in the section that come from running the tests, the database or the app, which a diff cannot confirm, and did not call them findings.
- It noted that a comment in one test called a date "already in the past" that is today's date. The comment is corrected in commit `0d44dd0`, which changes no code and no assertion.

No Important finding was raised in either round, so no third round was needed.

---

## 5. Cost

| Item | Rate | Units | Cost |
|---|---|---|---|
| Snowflake | About $2 a credit | 0 credits | $0 |
| Claude API, the extraction step | 🟡 About $0.0004 a call (the plan's figure) | 0 calls in this leg | $0 |
| Postgres and Chrome on the Mac | Free | | $0 |

Phase D as a whole made **27** of its 30 live extraction calls, all in leg D1, and used no Snowflake. No hosted account, hosted database or paid service was created.

---

## 6. Three questions Andres should be able to answer

1. The summary says "Active with the state as of Oct 7, 2026" and not "This company is active". What does "as of" protect against, and where does that date come from?
2. The summary and the record table could have been written by two pieces of code. How does this leg make sure they cannot disagree, and what does the test read to check it?
3. Before this leg an inactive company's last reason on the shortlist was "INACTIVE with the state". Where is that said now, why only once, and what happens for a company with no status on record?

**Answers, to check yourself.** (1) The data is a snapshot. A company's status can change after the state published the file, and the report lists "changes to a company's status after the snapshot date" as not checked. "As of" ties the statement to the day it was true on the record. The date is `published_on`, the day the state published the file the company's row came from, which is later than the quarterly snapshot for a company first seen in a daily file. (2) `ReportBuilder.build()` works out the status, the entity type and the date on record once, and builds both the table's rows and the two headline sentences from those same values. The test does not look at the code: it renders the report and the page, reads the summary and the table rows off the finished text, and compares them. That is called testing the output and not the implementation, and it keeps working if the code is later rearranged. (3) Beside the company's name, as "Inactive with the state", on the web page and in the terminal. Rule S10 says the same words leave the shortlist's list of reasons, so the shortlist says the status once and where it is seen first. The report of that company still gives the status in the line that says how it was identified, because a report keeps every fact it had. A company with no status on record is not marked, because no status is not "inactive", and its reasons end "status not on record".

---

## 7. What only Andres can do: look at it

**Why.** The summary's wording and the mark on the shortlist are the first things a contractor reads. A screenshot shows the layout. Only you can say whether the words answer the question you had on Nov 24.

1. In the VS Code (Visual Studio Code) terminal, run these three commands, one after another. Postgres has to be running: `brew services start postgresql@17` starts it.

```
cd ~/datum
source .venv/bin/activate
PYTHONPATH=src uvicorn datum.web.app:app --host 127.0.0.1
```

| Piece | What it does |
|---|---|
| `cd ~/datum` | Moves the terminal into the project folder |
| `source .venv/bin/activate` | Switches this terminal to the project's own Python and packages |
| `PYTHONPATH=src` | A setting for this one command: it tells Python that the `datum` package is in the folder `src` |
| `uvicorn datum.web.app:app` | Starts Uvicorn, the program that serves the app, and tells it which app: the thing called `app` in `src/datum/web/app.py` |
| `--host 127.0.0.1` | Listen only for this Mac itself |

2. Open `http://127.0.0.1:8000` in Chrome. Type anything as the name and your access code as the password. The code is the `APP_ACCESS_CODE` line you added to the secrets file after leg C4.
3. Type `8586 palm pwwy` and press Search. You should see one company, V PIZZA LAKE BUENA VISTA LLC, and a line that says 3 inactive companies also match and are not listed.
4. Click the company's name.

**Done when** the report opens with a bold line that begins "Active with the state as of Oct 7, 2026." and you can find the heading "The records behind this summary" further down. To stop the app, press Control and C in the terminal.

🟡 Each search in step 3 is one call to the Claude API, about $0.0004 by the plan's figure.
