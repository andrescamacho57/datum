# Leg C3: the Fact type and the report

Branch `leg/c3-fact-report` (stacked on `leg/c2-postgres-search`) · pull request [#21](https://github.com/andrescamacho57/datum/pull/21) · run on Nov 24, 2026 · risk tier **High** · status: **done. Every check passes, and the Deep review ended after three rounds with no Important finding left open. The answers to the last round's three Nits were not reviewed.**

This is the third of the four legs of Phase C. Leg C2 made the search. This leg makes the thing the search leads to: the report a contractor reads about one company. It builds no web page. Leg C4 puts this report on a page.

**The short version**

- **A fact cannot exist without its source.** `Fact` is a new type, and building one with no source address, with a fetch time that has no time zone, or with a fetch time that is not in UTC (Coordinated Universal Time) raises an error. A test proves each of the three. Everything a report states about a company is a `Fact`.
- **One builder makes the report.** `ReportBuilder.build()` takes a document number, reads three Postgres tables, and returns a `Report`. The terminal command `report.py` is now a thin wrapper over it, and the web app of leg C4 will use the same builder, so the two cannot say different things.
- **Every fixed sentence is in one file,** `src/datum/wording.py`. Section 2 lists all 70 of its entries in one table for you to read. A linked record (a lien or a license) is described only by the mart's own columns.
- **Three faults of the old `report.py` are gone,** each with a test that fails on the old behavior:
  - It wrote the typed note, owner's name included, into the saved report. The note now reaches the extraction step and nothing else.
  - It asked for an owner's name. Nothing does now.
  - It wrote "Strong" for a company that had tied with another. A tie is now said on the shortlist and on the report.
- **The review found two more ways the note could get out, and both are closed.** An error message in the extraction step quoted the whole note, and the documented way to run the command put the note in the shell's history file.
- **Five reports were built from the real data** in Postgres and saved under `data/reports/`, which git ignores: a company with federal liens, one with an inactive license, an inactive company, a new company and one with no flags.
- The offline tests pass: **368**, of which 101 are new. 30 of the 101 were added to answer the review.
- This leg used **no Snowflake credits** and made **no call to the Claude API**.

**What is left for Andres**

1. **Read the table of fixed sentences** (check 3). These are the words a contractor will see, and wording is your call.
2. **Rule on six questions this leg could not decide.** Each has a row in `docs/open_questions.md`.
   - Q36: does a federal lien that is closed count in the summary line? I count it.
   - Q37: "New company" within 12 months of which day? I use the day the report is built.
   - Q38: what does a report say about a possible match, once you switch a reason on?
   - Q39: five entity-type codes have no plain-English label.
   - Q40: can the extraction step put a person's name into the fields a report shows? It came out of the review.
   - Q41: should the search treat "St. Augustine" and "ST AUGUSTINE" as one city? It came out of the review too.
3. Read section 3, which holds the calls I made where the brief did not say.
4. Answer the three questions in section 6, because this is a High-tier change.

---

## 1. What I built

### The picture

```
                              wording.py   every fixed sentence, label and heading
                                   │ (read by everything below)
 company_search ┐                  ▼
 company_flags  ├─▶ ReportBackend ─▶ ReportBuilder.build(document number, how it was identified)
 source_coverage┘   (Postgres, or a fake in tests)        │
                                                          ▼
                                                       Report        made of Fact and Flag objects (models.py)
                                                          │
                                          ┌───────────────┴───────────────┐
                                          ▼                               ▼
                               render_markdown()                   the web templates
                               report.py, the terminal command     (leg C4)
                               and files under data/reports/
```

### Each piece in plain English

| Piece | What it is | Why it exists |
|---|---|---|
| `src/datum/wording.py` | One module that holds every sentence, label and heading a contractor can be shown, and the list of words that never appear on a page | The brief asks that a reviewer read one file to see every sentence. Working rule W4 bans eight words, and W6 bans asking for an owner's name |
| `src/datum/models.py` | Five Pydantic models: `Fact`, `Flag`, `Candidate`, `Identification` and `Report`. Pydantic is a library that checks a value when an object is built, and raises an error when it breaks the model's rules. Every model here is frozen, which means its fields cannot be changed afterwards | `CLAUDE.md` rule 3 and working rule W1: a fact type that can be built without a source address and a UTC fetch time is a bug in the type |
| `src/datum/report_builder.py` | `ReportBuilder`, which builds a `Report` for one document number. It reads through `ReportBackend`, an interface with two implementations: `PostgresReportBackend` for the app and `FakeReportBackend` for the tests. It also holds `render_markdown()`, which lays a report out as text | One place where a report is built, for the terminal and the web app alike |
| `src/datum/report.py` | The terminal command, rewritten as a thin wrapper: it asks, prints and saves, and it leaves the search to `search.py` and the report to the builder | The brief asks for it, so that the terminal and the web app cannot drift apart |
| `tests/fixtures/report/` | Three small files that stand in for the three Postgres tables: the five real source rows, four real flag rows with invented numbers, and six invented companies | `CLAUDE.md` rule 4: the tests run with no database |
| `tests/report_fixtures.py` | A helper that reads those files into objects. It holds no test | Three test files, and leg C4's tests, build reports from the same rows |

### What a report holds, top to bottom

| Part | Where its words come from | The rule |
|---|---|---|
| The title and the day it was built | `wording.py` and the company's legal name | |
| The summary line | `wording.summary_line()`. "No flags found in the sources checked." when there is no flag, and "2 flags found in 3 sources checked." when there are two | W2. It is worked out from the flags each time it is read, and it is not a stored field, so nothing can store the wrong one |
| One sentence that says what the report cannot see | `wording.CONFIRMED_ONLY`, the same words on every report | W4 |
| The company's own record: legal name, document number, status, entity type, date on record, principal address | The state's values, each as a `Fact` that carries the company record's source address and fetch time | W1 |
| The flags | First the two flags that come from the company's own record, then the linked records, newest first | W2, and the plan's flags table |
| Sources checked, and not checked | The table `source_coverage`, plus five fixed lines for what Datum never loaded | W5 |
| How the company was identified | The extracted business name, city and street, the match level, the evidence, and how many other companies matched equally well | W6 and W7 |
| The disclaimer | `wording.DISCLAIMER`, word for word what `report.py` printed before | |

### The two kinds of flag

```
 from the company's own record                    from a linked record
 (needs no link)                                  (only on a CONFIRMED link, only when is_shown is true)

 "Inactive with the state"   status_code = 'I'    a federal tax lien        title  = the mart's citation
 "New company"               date on record       an inactive DBPR license  status = the mart's status and status_note
                             within 12 months                               caveat = the mart's caveat
 wording: the plan's flags table, word for word   wording: none of the builder's own
```

DBPR is the Department of Business and Professional Regulation, which licenses contractors.

### Files

| File | New or changed |
|---|---|
| `src/datum/wording.py`, `tests/test_wording.py` | New. 8 tests |
| `src/datum/models.py`, `tests/test_models.py` | New. 22 tests |
| `src/datum/report_builder.py`, `tests/test_report_builder.py`, `tests/report_fixtures.py` | New. 27 tests |
| `src/datum/report.py`, `tests/test_report_cli.py` | Rewritten, which the brief allows for this leg. 28 tests |
| `tests/fixtures/report/` (three files and a README) | New |
| `tests/test_fixture_privacy.py` | Changed: it now checks the report fixtures. 15 new tests |
| `src/datum/search.py`, `tests/test_search.py` | Changed: the eight reasons that `evidence()` gives moved to `wording.py`. Three of them were then reworded in the review, and `tests/test_search.py` gained one test. No rule of the search changed |
| `requirements.txt` | Changed: three comments. No package was added or upgraded |
| `docs/open_questions.md` | Changed: Q36 to Q41 added, and a note on Q34 |
| `src/datum/extract.py` | Changed in the review: one error message no longer quotes the note. Nothing else in the file changed |

No Snowflake object, no dbt model and no Postgres table was touched.

---

## 2. Checks

### Check 1: the tests, with the input that makes each new one fail

```
pytest
368 passed in 0.77s

ruff check src tests
All checks passed!
```

267 tests existed before this leg, and 101 are new. Some of the 101 are one test run over several inputs, so the tables below list 66 test names. The last table holds the 18 that the review added.

**The five tests the brief asks for by name**

| What the brief asks | The test | The input that makes it fail |
|---|---|---|
| A typed note never reaches a report (W6) | `test_the_typed_note_is_never_printed_back_and_never_saved` in `test_report_cli.py` | A note that holds an owner's name and a phone number. The test fails if either appears in the saved file or in anything the command printed or asked |
| | `test_an_identification_has_nowhere_to_put_the_typed_note` in `test_models.py` | `Identification(note=...)`. The test fails if the type accepts a field called `note`, `raw_note`, `owner` or `owner_name` |
| A tie is stated (W7) | `test_a_tie_is_said_on_the_report_of_whichever_company_was_picked` in `test_report_builder.py` | An identification with 2 other companies tied. The test fails if the report does not say "2 other companies matched equally well." |
| | `test_two_companies_with_the_same_name_are_called_a_tie_on_the_shortlist_and_on_the_report` in `test_report_cli.py` | Two invented companies with the same name in the same city. The test fails if the shortlist or the saved report is silent about the tie |
| No rendered report holds a banned word, and a no-flag report has the exact line and the sentence (W4) | `test_no_report_holds_a_word_that_reassures_or_judges`, run for each of the six fixture companies | Any of the eight words, or a word that starts with one, anywhere in a rendered report. It also fails if a report lacks the fixed sentence or the disclaimer, or if the no-flags line is present beside a flag or absent without one |
| | `test_the_check_for_banned_words_can_fail_and_the_fixed_wording_passes_it` | The sentence "this company looks clean. Credit scores are recommended." must be caught, and no entry of `wording.py` may be |
| The summary count ignores possible matches and hidden flags | `test_the_count_ignores_a_hidden_flag_and_a_possible_match_even_when_the_backend_hands_them_over` | A backend that returns a hidden row, a possible match and a row whose `is_shown` is the text "f". The test fails if any of the three is counted or printed |
| An inactive company with no linked flag counts 1 and has no "No flags found" line | `test_an_inactive_company_with_no_linked_record_counts_one_flag_and_never_says_no_flags_found` | The invented inactive company. The test fails if the count is not 1 or if the no-flags line is on the report |

**The three ways to break a Fact** (`tests/test_models.py`)

| The test | The input that makes it fail |
|---|---|
| `test_a_fact_with_no_full_source_address_cannot_be_built` | A source address that is left out, `None`, empty, has no `https://`, is a path only, is an `ftp://` address, or has no host. Seven inputs, and the type must refuse each |
| `test_a_fact_whose_fetch_time_has_no_time_zone_cannot_be_built` | A fetch time that is left out, `None`, a time with no zone, a text, or a bare date. Five inputs |
| `test_a_fact_whose_fetch_time_is_not_utc_cannot_be_built` | The right moment written in Eastern time. The type must refuse it and not convert it |

**The other new tests**

| File | The test | The input that makes it fail |
|---|---|---|
| `test_models.py` | `test_a_fact_with_a_source_address_and_a_utc_fetch_time_is_built` | A good fact that the type refuses |
| | `test_a_fact_must_say_whether_its_fetch_time_is_an_estimate` | A fact with no `fetched_at_is_approximate`, or an estimated time shown without the word "about" |
| | `test_a_fact_cannot_be_changed_after_it_is_built_and_takes_no_extra_field` | Assigning to a field of a built fact, or passing a field the type does not declare |
| | `test_the_summary_line_is_worked_out_from_the_flags_and_cannot_be_stored` | A `Report` built with `summary="No flags found..."` beside a flag. The type must refuse the field |
| | `test_every_report_carries_the_same_two_sentences` | A report whose fixed sentence or disclaimer differs from `wording.py` |
| | `test_a_candidate_states_its_name_its_place_and_its_evidence_as_facts` | A candidate whose name is a bare text, or whose evidence holds "ACTIVE" as a bare text and not as a `Fact` |
| `test_wording.py` | `test_the_summary_line_counts_flags_and_is_the_exact_no_flags_line_when_there_are_none` | A count of 1 worded as "1 flags", or the no-flags line returned for any count from 1 to 29 |
| | `test_an_estimated_fetch_time_says_about_and_a_measured_one_does_not` | An estimate without "about", or a measured time with it |
| | `test_a_tie_is_worded_for_one_other_company_for_several_and_not_at_all_for_none` | "1 other companies", or any sentence for a count of 0 |
| | `test_the_identification_line_is_built_from_extracted_fields_and_leaves_out_an_empty_one` | An empty city printed as `the city ""` |
| | `test_the_not_checked_list_names_what_the_brief_says_datum_never_looked_at` | A list that leaves out court cases, UCC filings, other counties, fictitious names or later status changes |
| | `test_the_two_company_record_flags_use_the_plans_wording_word_for_word` | Any change to the wording or caveat of the two flags, or to the disclaimer |
| `test_report_builder.py` | `test_a_company_with_two_liens_shows_both_newest_first_in_the_marts_own_words` | A flag whose title, status, status note or caveat is not exactly the mart's column, the older lien listed first, or a flag's own source line or date line missing from the page |
| | `test_a_company_on_record_within_twelve_months_is_flagged_as_new_and_one_outside_them_is_not` | A date exactly 12 months back that is not flagged, a date one day older that is, a future date that is, or a missing date that is |
| | `test_a_company_with_no_flag_says_exactly_the_no_flags_line` | Any other wording of that line, or a "Flags" heading with nothing under it |
| | `test_company_record_flags_come_first_and_linked_records_follow_newest_first` | A linked record placed above the company's own flag, or a count that leaves one kind out |
| | `test_the_license_company_shows_the_license_line_and_the_lien_with_its_discharge_note` | A caveat that is cut short, or a status note that is dropped |
| | `test_the_identification_line_shows_the_extracted_fields_and_no_note` | A line that differs from the expected one by a character |
| | `test_the_sources_lists_say_what_was_checked_through_which_date_and_what_was_not` | A hidden source listed as checked, or a checked source with no "data through" date |
| | `test_everything_stated_about_the_company_is_a_fact_with_the_company_records_source` | A company line whose source address, citation or fetch time is not the company record's |
| | `test_a_gap_in_the_states_record_is_said_and_never_filled_in` | The word "None" on a report, or a company with no status called inactive |
| | `test_a_fetch_time_in_another_zone_is_converted_and_one_with_no_zone_is_refused` | A fetch time with no zone that the builder lets through |
| | `test_a_number_that_names_no_company_or_is_not_a_number_at_all_is_not_found` | A text such as `' or 1=1 --` that reaches the backend. The test's backend fails if it is asked at all |
| | `test_the_functions_that_lay_out_a_report_or_talk_in_the_terminal_hold_no_sentence_of_their_own` | A text of two or more words written inside `render_markdown`, the builder's functions or the terminal command's functions, or kept in a module-level name, where it would be wording nobody reviewed |
| | `test_a_search_result_becomes_a_page_candidate_whose_name_and_place_are_facts` | A place made up for a company that has no city on record |
| | `test_a_name_with_a_table_mark_in_it_does_not_break_the_table` | A company name that holds the character that ends a table cell |
| | `test_the_postgres_backend_sends_the_document_number_as_a_value_and_asks_for_shown_flags_only` | A query with a quote or a brace in it, a query that reads `company_possible_matches`, or a flags query without `and is_shown` |
| `test_report_cli.py` | `test_the_note_reaches_the_extraction_step_and_nothing_else` | A second call to the extraction step, or a changed note |
| | `test_a_vague_note_asks_for_a_name_a_street_or_a_city_and_shows_no_company` | A prompt that differs by a word, any company printed, or any file written |
| | `test_nothing_the_command_can_say_asks_for_an_owner` | The word "owner" in any entry of `wording.py` or in the code of `report.py` |
| | `test_a_same_name_company_that_did_not_fit_on_the_list_is_named_and_counted` | Seven companies with one name. The test fails if the two that are off the list are not named, or if the report does not count 6 others |
| | `test_a_possible_match_needs_a_yes_before_a_report_is_made` | A report written after the user answered "n" |
| | `test_a_wrong_pick_is_asked_again_and_zero_asks_for_more` | An out-of-range answer taken as a pick |
| | `test_the_command_gives_up_after_three_rounds_and_never_guesses` | A fourth round of questions |
| | `test_others_at_the_same_level_counts_below_the_top_level_among_the_companies_shown` | A count that includes the picked company itself |
| `test_fixture_privacy.py` | 14 new cases of `test_the_check_fails_on_a_row_that_still_leads_to_a_person` | Each case is a report fixture that breaks one rule: a document number of a real shape on a company or on a flag row, a company name, simplified name or street address left real, a filing or license number left real, a second number inside a citation, a status note or a caveat, a source address that points at one record, a source or a file the test has no rule for |
| | `test_a_report_fixture_with_invented_companies_and_invented_numbers_passes` | A date such as 2026-11-18 mistaken for a record number |

**The 18 tests the review added.** The review ran changes against the suite and found ones that no test noticed. Each test below fails on one of them.

| File | The test | The input that makes it fail |
|---|---|---|
| `test_wording.py` | `test_a_sentence_about_a_count_says_what_the_count_covers` | A tie at the level Likely worded as if every company were counted, or any of seven phrases that claimed more than the code compares ("exactly this name", "city matches", "ignoring LLC/INC" and four more) anywhere in `wording.py` |
| | `test_the_sentence_every_report_carries_and_the_banned_words_are_held_here_as_literal_text` | The fixed sentence of rule W4 emptied or reworded, or a word dropped from the banned list. Both are typed out in the test |
| `test_models.py` | `test_a_report_with_no_source_checked_cannot_be_built` | A `Report` with an empty list of checked sources |
| | `test_a_report_cannot_take_its_identification_line_as_bare_text` | An identification line handed over as text and not as a `Fact` |
| `test_report_builder.py` | `test_a_report_is_refused_when_no_source_may_be_shown` | A table of sources in which every row is hidden, or which is empty. The builder must refuse, with a flag or without one |
| | `test_the_identification_has_no_default_so_no_caller_can_drop_it_by_accident` | A call to `build()` that leaves the identification out |
| `test_report_cli.py` | `test_with_a_city_given_the_counts_say_which_companies_they_cover` | Seven same-name companies in the city given, then the same seven in another city. It fails if the line under the shortlist or the tie sentence reads as if it counted more than it does |
| | `test_a_failed_extraction_says_two_fixed_sentences_and_never_the_errors_own_words`, run for five kinds of error | An extraction step that raises an error quoting the whole note. It fails if any word of the note or of the error's message is printed, or if only one kind of error is caught |
| | `test_a_reply_with_any_one_field_missing_is_a_failed_extraction_too`, run once for each of the four fields | A reply from the extraction step with one field left out. A reply with no `is_specific` must not be searched as if the note had named a business |
| | `test_no_error_raised_by_the_extraction_step_is_built_from_the_note` | A `raise` in `extract.py` that uses the note in any way: in an f-string, joined with `+`, passed to `format()`, under another parameter name, or copied to another name first. The test parses the code and does not import it |
| | `test_main_hands_the_command_line_to_read_note_and_uses_it_nowhere_else` | A `main()` that joins the command line into the note, even on the same line as a call to `read_note`, or after `from sys import argv` |
| `test_search.py` | `test_a_city_is_compared_by_its_spelling_and_the_reason_says_so` | The city "St. Augustine" against a company in ST AUGUSTINE. It fails if the reason says "not the city you gave" |
| | `test_a_company_in_a_city_that_only_begins_with_the_one_given_is_not_said_to_be_in_that_city` | Seven companies in JACKSONVILLE BEACH when the city given is Jacksonville. It fails if any line says "city matches" or "in the city you gave" |
| | `test_the_note_is_read_at_a_prompt_and_never_from_the_command_line` | A note typed after the command that is used, or shown back |
| | `test_a_vague_note_shows_no_company_until_a_second_extraction_names_one` | A vague note followed by an answer. It fails if anything is printed about a company before the second extraction |
| | `test_pressing_enter_at_the_possible_match_question_means_no` | Enter, a space, "yes please", "N" or "no" taken as a yes |
| | `test_a_pick_one_past_the_end_of_the_list_is_asked_again` | The answer 6 when five companies are listed, and the answer "²", which one Python function calls a digit and another cannot read as a number |
| | `test_nothing_the_terminal_prints_in_a_whole_conversation_holds_a_banned_word` | Any of the eight words in anything the terminal prints during a conversation with two shortlists and a report |

✅ I checked two of these by hand as well: the list of words inside the layout functions was empty only after I moved the terminal's prompts into `wording.py`, and the privacy test failed on the real fixture until the pattern for a record number was right.

### Check 2: five reports from the real data

The brief asks for five reports built from the real Postgres data, named here by document number only. A small script built them with `PostgresReportBackend` and `render_markdown`, and saved each under `data/reports/`, which git ignores.

```
kind                             document number   flags                                            summary
a federal lien flag              207670            federal_tax_lien, federal_tax_lien               2 flags found in 3 sources checked.
an inactive license              361997            dbpr_license_inactive                            1 flag found in 3 sources checked.
an inactive company              000001            inactive_with_state                              1 flag found in 3 sources checked.
a new company                    A26000000239      new_company                                      1 flag found in 3 sources checked.
no flags, found by the search    P98000033661      (none)                                           No flags found in the sources checked.
```

| Kind | Document number | File under `data/reports/` | What the check showed |
|---|---|---|---|
| A company with a federal lien flag | `207670` | `207670_20261124.md` | ✅ Two liens, newest first, each with the mart's citation, status and caveat |
| A company with an inactive license | `361997` | `361997_20261124.md` | ✅ One license line with the mart's status note |
| An inactive company | `000001` | `000001_20261124.md` | ✅ One flag, and no "No flags found" line |
| A new company | `A26000000239` | `A26000000239_20261124.md` | ✅ "On record since" with its date |
| A company with no flags | `P98000033661` | `P98000033661_20261124.md` | ✅ The exact no-flags line. This one was found through the real search, so it carries an identification line |

- ✅ No report of the five holds a banned word. The script ran the same check the tests use.
- ✅ Every company line says "fetched about", because every company's fetch time is an estimate (question Q31).
- The fifth company is case 1 of the committed test set. Its name and city came from the saved extraction in `pipeline/seeds/extracted_inputs.csv`, and the real search on Postgres put it first, at the level "Likely". No call to the Claude API was made.
- 🟡 That fifth report says "chosen by the user from a shortlist". The script took the first company on the list. Nobody chose.
- ✅ The five reports were built again after each round of review fixes, and they gave the same table each time.
- 🟡 The terminal command was not run from end to end with a real note, because that takes a call to the Claude API and working rule W10 keeps the phase's live calls for the two checks of leg C4. Its conversation is tested with stand-ins, and its two Postgres backends ran for real in this check.

### Check 3: every fixed sentence a contractor can be shown

This is all of `src/datum/wording.py`: 70 entries. A piece in curly braces, such as `{day}`, is filled in when the sentence is used. A linked record's own words are not here, because they are the mart's columns (`citation`, `status`, `status_note` and `caveat`), which were reviewed in legs B2 and C1.

**On every report**

| Name in `wording.py` | The text |
|---|---|
| `NO_FLAGS` | No flags found in the sources checked. |
| `CONFIRMED_ONLY` | Datum shows a record only when it can confirm that the record belongs to this company. A record filed under a similar name or at a different address is not shown. |
| `DISCLAIMER` | Sourced public-record facts, not advice. Verify on the official record before relying on them. |
| `REPORT_TITLE` | Datum company check: {name} |
| `BUILT_ON` | Report built {day} |

**The company's own record**

| Name in `wording.py` | The text |
|---|---|
| `LABEL_LEGAL_NAME` | Legal name |
| `LABEL_DOCUMENT_NUMBER` | Document number |
| `LABEL_STATUS` | Status with the state |
| `LABEL_ENTITY_TYPE` | Entity type |
| `LABEL_DATE_ON_RECORD` | Date on record |
| `LABEL_ADDRESS` | Principal address |
| `LABEL_COMPANY_SOURCE` | Official record |
| `STATUS_ACTIVE` | Active |
| `STATUS_INACTIVE` | Inactive |
| `NOT_ON_RECORD` | Not on record |
| `DATE_ON_RECORD` | {day} (may be an effective date; confirm on the official record) |
| `COMPANY_CITATION` | Florida Division of Corporations (Sunbiz) record, document number {document_number} |
| `COMPANY_PUBLISHED` | data published {day} |
| `FILING_TYPES` | `FLAL`: Florida limited liability company (LLC)<br>`DOMP`: Florida corporation (for profit)<br>`DOMNP`: Florida nonprofit corporation<br>`DOMLP`: Florida limited partnership<br>`FORP`: Out-of-state corporation registered in Florida<br>`FORL`: Out-of-state LLC registered in Florida<br>`FORNP`: Out-of-state nonprofit registered in Florida |

**The two flags from the company's own record**

| Name in `wording.py` | The text |
|---|---|
| `FLAG_INACTIVE_TITLE` | Inactive with the state |
| `FLAG_INACTIVE_TEXT` | Inactive with the Florida Division of Corporations |
| `FLAG_INACTIVE_CAVEAT` | Data as of the snapshot date; changes since then aren't covered until the events file is loaded |
| `FLAG_NEW_TITLE` | New company |
| `FLAG_NEW_TEXT` | On record since {day} |
| `FLAG_NEW_CAVEAT` | May be an effective date |

**A flag card**

| Name in `wording.py` | The text |
|---|---|
| `HEADING_FLAGS` | Flags |
| `LABEL_FLAG_DATE` | Date on the record |
| `LABEL_FLAG_STATUS` | Status |
| `LABEL_SOURCE` | Source |
| `FETCHED` | fetched {day} |
| `FETCHED_ABOUT` | fetched about {day} |

**The sources lists**

| Name in `wording.py` | The text |
|---|---|
| `HEADING_CHECKED` | Sources checked |
| `HEADING_NOT_CHECKED` | Not checked |
| `DATA_THROUGH` | data through {day} |
| `NOT_CHECKED_ALWAYS` | Court cases<br>UCC (Uniform Commercial Code) filings<br>Recorded documents in other counties<br>Fictitious names (the names a business trades under)<br>Changes to a company's status after the snapshot date |

**How the company was identified**

| Name in `wording.py` | The text |
|---|---|
| `LABEL_IDENTIFIED` | How this company was identified |
| `IDENTIFIED_BY_SEARCH` | from {fields} · match level {level} ({evidence}) · chosen by the user from a shortlist. |
| `IDENTIFIED_BY_NUMBER` | opened by its document number, so no match level applies. |
| `FIELD_BUSINESS_NAME` | the business name "{value}" |
| `FIELD_CITY` | the city "{value}" |
| `FIELD_STREET` | the street "{value}" |
| `TIED_ONE` | 1 other company matched equally well. |
| `TIED_MANY` | {count} other companies matched equally well. |
| `TIED_ON_LIST_ONE` | 1 other company on the shortlist matched equally well. |
| `TIED_ON_LIST_MANY` | {count} other companies on the shortlist matched equally well. |

**The reasons for a match level**

| Name in `wording.py` | The text |
|---|---|
| `NAME_IGNORING` | ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space |
| `EVIDENCE_EXACT_NAME` | name matches (ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space) |
| `EVIDENCE_SIMILAR_NAME` | name is similar ({similarity}/100) |
| `EVIDENCE_CITY_MATCHES` | principal city on record begins with the city you gave |
| `EVIDENCE_OTHER_CITY` | principal city on record is {city}, and that spelling does not begin with the city you gave |
| `EVIDENCE_NO_CITY` | no principal city on record for this company |
| `EVIDENCE_ACTIVE` | ACTIVE |
| `EVIDENCE_INACTIVE` | INACTIVE with the state |
| `EVIDENCE_NO_STATUS` | status not on record |

**The shortlist and the terminal's questions**

| Name in `wording.py` | The text |
|---|---|
| `SHORTLIST_TIE` | These look about equally likely. Is it one of these? A street or a city would help tell them apart. |
| `SHORTLIST_NOT_SHOWN_ONE` | 1 more company matches at the level Strong and is not on this list. |
| `SHORTLIST_NOT_SHOWN_MANY` | {count} more companies match at the level Strong and are not on this list. |
| `ASK_FOR_A_BUSINESS` | That describes a business but doesn't name one. Add its name, a street or a city |
| `ASK_FOR_MORE` | Add a street or a city |
| `POSSIBLE_ONLY` | That's only a POSSIBLE match: {evidence}. Nothing else confirms it's the company you mean. Make the report anyway? (y/N):  |
| `GIVING_UP` | I can't identify this business from what I have, so I won't guess. Run it again when you have its name, a street or a city. |
| `READ_AS` | I read that as: {fields} |
| `PICK` | Pick 1-{count}, or 0 to add more details:  |
| `PICK_AGAIN` | Please type a number from 0 to {count}. |
| `PRESS_ENTER` |  (press Enter if you don't know):  |
| `SAVED_TO` | Saved to {path} |
| `DESCRIBE_THE_CLIENT` | Describe the client:  |
| `NOTE_NOT_ON_COMMAND_LINE` | What you typed after the command was not used. A shell usually keeps each command line in its history file, so that text may be stored there now. Type the note below instead. |
| `SEARCH_UNAVAILABLE` | The search is unavailable right now, so no company is shown. Try again in a few minutes. |
| `EXTRACTION_ERROR_KIND` | The extraction step stopped with this kind of error: {kind}. |

The eight words that never appear on a page (working rule W4) are `clean`, `safe`, `risky`, `trustworthy`, `reliable`, `credit`, `score` and `recommend`. The tests look for each at the start of a word, so "scores" and "recommended" are caught too.

### Check 4: the report fixtures lead to nobody

```
pytest tests/test_fixture_privacy.py -q
45 passed in 0.08s
```

✅ The test now reads `tests/fixtures/report/` on every run. Every document number there starts with `T`, and no company in the state's file has one that does (counted in Postgres on Nov 24: 0 of 12,988,435). Every filing and license number is in an invented range, and the test fails if a sentence holds any other number.

---

## 3. Decisions I made and why

| # | Decision | Why | The tradeoff |
|---|---|---|---|
| 1 | The six fixture companies are invented, and only the flag rows are cut from real mart rows | The brief allows a fixture cut from a real company row. A small company's principal address is often somebody's home, and the repo is public. The builder's tests need the shape of a company and not any particular one | The fixtures do not prove the builder against a real company's oddities. Check 2 does that, on five real companies |
| 2 | A linked record's card has no title of its own. Its heading is the mart's `citation`, and its date sits under the neutral label "Date on the record" | The brief says the builder holds no wording of its own for a linked record. A label such as "Filed on" would be right for a lien and wrong for a license, whose date is its effective date | The card does not say what kind of date it is. The citation names the record, and the source link shows the rest |
| 3 | "New company" is measured from the day the report is built, the boundary day counts, and a date in the future raises no flag | The plan's table says only "Date on record within 12 months". A date in the future is not within the last 12 months, and 35 companies have one | 🔴 This is my reading. The same company can be "new" in one report and not in the next. Question Q37 |
| 4 | A closed federal lien counts in the summary line | Working rule W2 counts every flag on a CONFIRMED link that may be shown, and a closed lien is one. The card says "Status: closed" with the release date | 🔴 "2 flags found" beside two released liens may read as more than the record says today. Question Q36 |
| 5 | The company's own flags come first, and the linked records follow, newest first | The brief says "the flags newest first". "Inactive with the state" has no date, and it is the first thing a contractor should see | A linked record from last week sits below a "New company" line from last spring |
| 6 | The builder does not read possible matches at all | Every possible match is hidden today (W3) and Postgres holds none (W9). No wording exists for one on a page. A builder that never reads them cannot show, leak or count one | When you switch a reason on, the builder needs new code and new wording first. Question Q38 |
| 7 | The summary line, the fixed sentence and the disclaimer are worked out from the report and are not stored fields | A stored summary could disagree with the flags. One that is computed cannot | None |
| 8 | A report opened by its document number, with no search, says so | Leg C4's page for one company is reached by its number. Saying "match level Strong" there would be a claim with nothing behind it | The line is new wording. It is in the table of check 3 |
| 9 | The shortlist shows the Strong companies that did not fit on it, each with its reasons, its source and its fetch date | Leg C2 made the shortlist carry them, so that a count is never a statement with nothing behind it. A count the reader cannot check is not much better | They are named and cannot be picked. Whether they belong on the list is question Q34, and it stays yours |
| 10 | The eight reasons for a match level moved from `search.py` to `wording.py` | The brief asks for one module that holds every fixed sentence. Leaving eight of them in the search module would break that | `search.py` now imports `wording.py`. The words did not change, and the search tests pass unchanged |
| 11 | The models are strict: the text "2026-11-24" is not accepted where a date is required | A model that quietly converts what it is given could accept a fetch time written as text and guess its zone | Code that builds a model has to hand over real dates and times, and a test backend has to as well |
| 12 | An entity-type code with no label is shown as the state writes it | Seven labels exist, from samples taken in October. Five codes have none, and a guessed label would be wording nobody approved | 22,848 companies show a code such as `FORLP`. Question Q39 |
| 13 | The company's source link is the state's search-by-document-number page | Ruling R9: cite the search page and the number. The old `report.py` linked to a search by name, which lists every similar company | The contractor types the document number into the state's page. The site blocks a direct link to one company |
| 14 | A fetch time is shown as its date in UTC | A report is read in Florida and the data's times are stored in UTC. A date is enough for "how fresh is this" | A file fetched at 9 PM Eastern shows the next day's date |
| 15 | At the levels Likely and Possible, "matched equally well" counts the companies on the shortlist, and the sentence says "on the shortlist" | Leg C2 counts those two levels over the five companies shown. The review found that my first wording read as if every company were counted, and so each count now has a wording of its own | Two more sentences in `wording.py`. 🟡 At the level Strong the count covers the pool of up to 200 candidates, and a same-name company outside that pool would not be counted (item 9 of section 4) |
| 17 | The note is read at a prompt, and text typed after the command is not used | The shell keeps every command line in its history file, and working rule W6 says the note is never stored. The review found that the documented way to run the command put the note there | Running the command takes one more keystroke. A note that was already typed after the command is in the history anyway, and the command says why it did not use it |
| 18 | A failed extraction prints two fixed sentences, the second with the error's class name, and never the error's own message | An error message can quote what it was given, and the old one in `extract.py` quoted the whole note | The terminal says what kind of error it was and not what the error said. The full cause has to be found by running the extraction step on its own |
| 19 | The builder refuses to build a report when no source may be shown | "No flags found in the sources checked." above an empty list of sources would be an all-clear about nothing | If every source were ever hidden, the app would show no report at all, and that would be the right thing to see |
| 21 | A sentence about a match says exactly what the code compares, even where that makes it long | Two review rounds found sentences that claimed more than the comparison behind them. "City matches" was wrong for a company in JACKSONVILLE BEACH when the city given was Jacksonville, because the comparison is "begins with". "Ignoring LLC/INC" left out a dozen other endings. Each phrase is now the comparison in words | The reason for a name match is 30 words long. It is exact and it is clumsy, and shortening it without making it false is a wording call for you |
| 22 | The line under the shortlist names the level it counts and nothing else | "N more companies match at the level Strong and are not on this list" is true by construction, because the level Strong is what is counted. Each of those companies is then shown with its own reasons | The line does not explain what Strong means. The reasons under each company do |
| 20 | `build()` has no default for how the company was identified | With a default, a caller that forgot the argument would print "opened by its document number" for a company that was found by a search | Every caller has to pass the argument, and `None` has to be written out |
| 16 | A document number is checked for its shape before any query | Leg C4 needs "a document number that does not look like one gets a plain 404". Putting the check in the builder means no caller can forget it | Two odd real numbers are 5 and 11 characters long, so the shape allows 5 to 12. 🟡 One company's document number is a single character, and its report cannot be opened |

---

## 4. What I couldn't verify, and open questions for Andres

### What I couldn't verify

1. 🔴 **That a closed lien should count as a flag** (decision 4, question Q36).
2. 🔴 **Which day "within 12 months" is measured from** (decision 3, question Q37). On Nov 24 the rule flags 621,783 companies as new.
3. 🟡 **The terminal command from end to end.** `main()` in `report.py` was not run with a real note, because that needs a call to the Claude API (check 2).
4. 🟡 **The seven entity-type labels.** They came from samples in October and were never checked against the state's own list. Five codes have no label (question Q39).
5. 🟡 **What a report should say about a possible match** (decision 6, question Q38). Nothing is shown today, so nothing depends on it yet.
6. 🟡 **Odd dates in the state's file.** 1,964 companies have no date on record, 35 have one in the future, and the oldest is in the year 1609. A report shows the date as the state has it, with the note that it may be an effective date.
7. 🟡 **How the report reads on a phone.** This leg makes text. Leg C4 makes the page.
8. 🟡 **Whether the extraction step can return a person's name as the business name** (question Q40). The report shows the extracted fields, and the prompt does not tell the model to leave a person's name out. Testing it needs a call to the Claude API.
9. 🟡 **A same-name company outside the pool of 200.** The counts at the level Strong cover the pool: up to 200 companies whose names are nearest the typed one. A company with the same name and a long legal ending can fall outside the pool when 200 or more shorter names are nearer, and both counts would then be too low. ✅ For the 8 test inputs it does not happen: I counted the same-name companies in the whole table (0 or 1 for each input) and the pool held every one. The largest pool of the 8 held 28 companies. 🟡 I did not measure it for common names.
11. 🟡 **How the search compares a city** (question Q41). "St. Augustine" does not match a company in ST AUGUSTINE, because the comparison is one of spelling. The reason on the page now says that. The comparison is unchanged.
10. 🟡 **The dates on the three federal lien rows of the fixture are real.** The numbers are invented. A reviewer asked whether a filing date beside a release date could lead back to the filing, and the verifier dropped the point because the fixture rule covers numbers. A federal lien in this mart is filed against a business. It is your call whether fixture dates should be invented too.

### Questions added to `docs/open_questions.md`

| # | The question, in short |
|---|---|
| Q36 | Does a closed federal lien count in the summary line? |
| Q37 | "New company" within 12 months of which day, and what about a date in the future? |
| Q38 | What does a report say about a possible match, once a reason is switched on? |
| Q39 | Five entity-type codes have no label |
| Q40 | Can the extraction step put a person's name into the fields a report shows? |
| Q41 | Should the search treat "St. Augustine", "ST AUGUSTINE" and "Saint Augustine" as one city? |
| Q34 (note added) | The shortlist now names the same-name companies that are not on it. Whether they belong on it is still open |

### The review

- **Tier:** High. The leg rewrites `src/datum/report.py` and decides the wording on a report.
- **Depth:** Deep. In round 1, three `reviewer` subagents ran in parallel, each hunting one thing, and a fourth then checked every finding against the code. The three hunts are the ones the brief sets for a High leg of Phase C: a sentence the data does not support, that draws a conclusion or that reassures; a person's data, the typed note or a hidden record reaching a page, a log, Postgres or git; and a test that cannot fail.
- **Rounds:** 3, the most the rules allow.
- **Findings in all:** 10 Important, 11 Nit and 3 Pre-existing, after duplicates were merged and 2 findings were dropped by the verifier. The security review found nothing.
- **How it ended:** ✅ round 3 found no Important finding, and so the review is complete inside the three rounds. Its three Nits and its one Pre-existing finding were then fixed in two commits that **were not reviewed**: one rewords a single sentence and adds two tests, and the other changes tests only.

**Round 1** (three reviewers, then a verifier, on the first seven commits).

The three reviewers posted 19 findings. The verifier confirmed 17 and dropped 2. Counting two pairs of duplicates once each, that is **7 Important, 6 Nit and 2 Pre-existing**. Every confirmed finding was fixed, the Nits and the Pre-existing ones included.

| Finding | Tag | Answer |
|---|---|---|
| Two sentences claimed more than the count behind them. "1 more company has exactly this name" counted only same-name companies in the city given, and "exactly" hid that the legal suffix is ignored. "N other companies matched equally well" counted only the shortlist at the levels Likely and Possible | Important (found in two places, counted once) | Fixed. Each sentence has a second wording for the narrower count: "in the city you gave", and "on the shortlist". The counting did not change |
| The shortlist stated a company's status and city as bare text. Rule W1 says everything stated about a company is a `Fact`, and it names the status. The terminal printed each company with no source and no fetch date | Important | Fixed. A candidate's evidence is now a tuple of `Fact` objects, a report's identification line is a `Fact`, and the terminal prints the source and fetch date under every company it names |
| The sentence every report must carry, and the list of banned words, were compared in tests with the constants they came from. Emptying the sentence, or dropping "safe" from the list, failed no test | Important (two findings of one kind, counted once) | Fixed. Both are typed out in the tests |
| Five lines of the report's layout could each be deleted with no test failing: a flag's own source line, the checked sources, the unchecked ones, a company-record flag's text, and a linked flag's date | Important | Fixed. Each is read on the rendered page |
| A vague note followed by an answer was never tested. Without one line of code, a shortlist built from the vague note would have been shown, which breaks acceptance test A2 | Important | Fixed with a test that fails if anything about a company is printed before the second extraction |
| No test pressed Enter at the question about a Possible match. Code in which Enter meant yes passed every test | Important | Fixed with a test of five answers that must all mean no |
| The privacy check of the report fixtures did not prove that it reads the caveat column, or that it refuses a flag row with a real-shaped document number | Important | Fixed with a failing case for each |
| `build()` defaulted to "opened by its document number. No search was made", so a caller that dropped the argument would state something false | Nit | Fixed. The argument has no default, and the sentence no longer says that no search was made |
| With no source that may be shown, a report would say "No flags found in the sources checked." above an empty list | Nit | Fixed. The builder, the `Report` type and the summary line each refuse it |
| The privacy check skipped the source address and the simplified name, and the fixture's README said the test checks everything it promises | Nit | Fixed. Both columns are checked, with a failing case each, and the README lists what is checked and what is not |
| The check that the layout functions hold no sentence of their own did not cover the terminal command, or a sentence kept in a module-level name | Nit (the verifier lowered it from Important) | Fixed. It covers both, and a whole terminal conversation is searched for banned words |
| Two sort orders had no test | Nit | Fixed |
| A pick one past the end of the list crashed, and no test tried it | Nit | Fixed with a test. The code was already right |
| The extraction step's error message quoted the whole note, and nothing caught the error, so a failed extraction printed the note | Pre-existing | Fixed. The message no longer holds the note, and the terminal answers any failure with one fixed sentence |
| The documented way to run the command put the note after it, where the shell's history file keeps it | Pre-existing | Fixed. The note is read at a prompt only |

The two findings the verifier dropped, and what I did with them anyway:

| Dropped finding | Why it was dropped | What I did |
|---|---|---|
| The extraction prompt does not tell the model to leave out a person's name, so one could become the "business name" a report shows | It is a guess about what the model does, with no line of this diff to prove it, and rule W6 says the extracted fields are what a report shows | Logged as question Q40, because the risk is real and the decision is yours |
| The three federal lien rows of the fixture keep their real dates | The fixture rule covers numbers, and reviewers are told to skip fixture rows | Left as it is, and listed under "What I couldn't verify" |

The reviewer that hunted tests ran more than 100 changes against the suite, one at a time, and reported which ones no test noticed. ✅ After the fixes I repeated seven of the ones that had survived, and each now fails a test:

```
CONFIRMED_ONLY cut in half:                  1 failed
safe dropped from the banned list:           1 failed
flag source line deleted:                    1 failed
not-checked items deleted:                   1 failed
continue after a vague note removed:         1 failed
Enter means yes:                             1 failed
a sentence added to show_shortlist:          1 failed
```

**Round 2** (one reviewer on the seven fix commits, doing all three hunts on that diff, and reading the Human review section).

**3 Important and 2 Nit.** All three Important findings were in sentences I had written to answer round 1.

| Finding | Tag | Answer |
|---|---|---|
| The new sentence "N more companies have this name in the city you gave" was false for a company in JACKSONVILLE BEACH when the city given was Jacksonville. The city comparison is "begins with", and the sentence said more | Important | Fixed. The line under the shortlist now names only the level it counts, "N more companies match at the level Strong and are not on this list", and each such company is shown with its own reasons. The reason "city matches", which had the same fault since October, now reads "principal city on record begins with the city you gave" |
| "(ignoring LLC/INC)" understated the name comparison, which also removes CORP, CO, LTD and other endings. The round 1 test pinned the inaccurate sentence | Important | Fixed. One phrase, `NAME_IGNORING`, now states the comparison exactly, and every sentence that needs it uses it |
| The warning shown when a note was typed after the command said a note "is not kept anywhere". It is shown only in the case where the shell may already have kept that text | Important | Fixed. It now says the text was not used and may be stored in the shell's history file |
| The test of a failed extraction raised only `ValueError`, so code that caught only that kind passed. A wrong API key would also have looked like a passing fault | Nit | Fixed. Five kinds of error are tested, a reply with a missing field is handled, and the error's class name is printed |
| Two tests read source code as text and checked one spelling each | Nit | Fixed. Both now parse the code, so the note joined with `+`, or the command line joined into the note, is seen |

The reviewer found nothing in the Human review section: every sentence matched the code and this report, and all ten items of "What I couldn't verify" were represented.

A security review ran alongside round 2, because `src/` changed. It read the leg's source files in full and reported no vulnerability it was at least 80% sure of. It checked that the document number reaches SQL only as a bound value and is refused by its shape before any query, that no typed text reaches a file name, that the note's only destination is the extraction step, and that a hidden record or a possible match has four separate locks in front of it. One of its side notes was a real fault of another kind, and it is fixed: a character such as "²" at the pick prompt stopped the command with an error.

✅ After the fixes of round 2, I repeated four changes that had survived, and each now fails a test:

```
only ValueError is caught:                       1 failed
the note joined from the command line:           1 failed
the note joined into the error with +:           1 failed
"city matches" comes back:                       1 failed
```

Before round 3 I read each new sentence against the code once more and changed two things that the reviewer had not flagged. "Ignoring punctuation and spacing" was not what the comparison does: `A.B.C` becomes `A B C`, which is not `ABC`. The phrase now says that anything that is not a letter A to Z or a digit is read as a space. And the line under the shortlist stopped restating the name and the city at all.

**Round 3** (one reviewer on the round 2 fix commit, doing all three hunts on that diff, and reading the Human review section).

**0 Important, 3 Nit and 1 Pre-existing.** The reviewer checked each new sentence against the code it describes and found each one true. It found nothing about a person, the note or a hidden record reaching the terminal, and it found the Human review section supported, with all ten items of "What I couldn't verify" represented.

| Finding | Tag | Answer |
|---|---|---|
| The reason for a city that failed the comparison read "registered in ST AUGUSTINE, not the city you gave", also when the city given was "St. Augustine". The comparison is one of spelling, and the sentence said the company was somewhere else. The sentence is from October | Pre-existing | Fixed, in a commit that was not reviewed. It now reads "principal city on record is ST AUGUSTINE, and that spelling does not begin with the city you gave". The comparison itself is question Q41 |
| The test of a reply with a missing field removed three fields at once, so the first one hid the others. A reply with no `is_specific` could have been searched as if the note had named a business | Nit | Fixed, in a commit of tests that was not reviewed. Each of the four fields is removed on its own |
| The two tests that parse source code could be got past by renaming the parameter, by copying the note to another name, or by `from sys import argv` | Nit | Fixed in the same commit. The test follows the parameter by position and through assignments, and it sees an imported `argv` |
| The counts at the level Strong cover the pool of up to 200 nearest names, and a same-name company with a long legal ending can fall outside it. The report's wording of this ("a name shared by more than 200 companies") was narrower than the real case | Nit (the reviewer marked it uncertain, and did not query the database) | Answered with a measurement and a corrected sentence, and not with a code change. For the 8 test inputs the pool held every same-name company in the table. Item 9 of "What I couldn't verify" now describes the real case |

The reviewer tried about thirty changes to the code of this round, and most failed a test. Of those that survived, the ones that mattered are the ones the last two commits close: a reply with no `is_specific`, a note that was renamed or copied before it was quoted, an imported `argv`, and a name comparison that ignored spaces.

---

## 5. Credits used

**None.** This leg made no call to Snowflake. It read the Postgres copy on the Mac, which is free, and the tests read fixture files. ✅ No `snow` command and no dbt command was run.

It also made no call to the Claude API. Phase C may make at most 10 live extraction calls (working rule W10), and all 10 are still unused.

Phase C has used about 0.63 of its cap of 3 credits: 0.47 in leg C1, 0.15 in leg C2 and nothing here.

---

## 6. Three questions Andres should be able to answer

1. `Fact` refuses to be built without a source address and a UTC fetch time. Why is that better than a rule that says "always pass a source", and what are the three inputs it refuses?
2. An inactive company has no lien and no license record. What does its summary line say, and what did the first draft of working rule W2 get wrong about that case?
3. The builder drops a flag row whose `is_shown` is false, and Postgres already refuses such a row. Why check twice, and what does the builder do with a possible match?

**Answers, to check yourself.** (1) A rule in a document depends on every future author remembering it, and a type that raises an error does not. A `Fact` with no full source address, with a fetch time that has no time zone, or with a fetch time in a zone other than UTC cannot be built at all, so a page can never be handed one. (2) It says "1 flag found in 3 sources checked.", because "Inactive with the state" is a flag from the company's own record and needs no link. The first draft counted only flags from linked records, which would have put "No flags found in the sources checked." beside an inactive company. (3) The export keeps hidden rows in Snowflake, Postgres refuses them with a CHECK, and the builder drops them again, so three separate mistakes would have to line up before a hidden record reached a page. The builder does not read possible matches at all, and it drops one even if a backend hands it over, because no reason for a possible match has been approved for showing.
