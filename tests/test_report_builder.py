"""test_report_builder.py: offline tests for src/datum/report_builder.py, which builds the report a contractor reads.

Every report here is built from the rows in tests/fixtures/report/ through FakeReportBackend,
so no database is opened. The flag rows carry the mart's own wording with invented numbers,
and the six companies are invented (the folder's README has the details).

Several of these tests exist because of a fault the old report.py had (the bug hunt of
Nov 19, 2026). Each says which input makes it fail.

Run from ~/datum:  pytest
"""

import re                                   # the search for the words rule W4 bans
from dataclasses import replace             # a copy of a frozen dataclass with one field changed
from datetime import date, datetime, timedelta, timezone   # dates for the "New company" rule and fetch times

import pytest                               # the test runner; pytest.raises checks that an error IS raised

import report_fixtures as fx                # tests/report_fixtures.py: the fixture rows as objects
from datum import report as terminal        # src/datum/report.py, the terminal command
from datum import report_builder as builder_module
from datum import wording
from datum.models import Identification
from datum.report_builder import (
    CompanyNotFound, FakeReportBackend, NoSourceChecked, PostgresReportBackend, ReportBuilder, address_candidate_for_page, address_text, candidate_for_page,
    count_fact, looks_like_a_document_number, one_year_before, render_markdown,
)
from datum.search import Candidate as SearchCandidate

W4_WORDS = ("clean", "safe", "risky", "trustworthy", "reliable", "credit", "score", "recommend")   # typed out, NOT read from wording.py: the test must not take its list from the module it checks
BANNED = re.compile(r"\b(" + "|".join(W4_WORDS) + ")", re.IGNORECASE)   # each banned word at the START of a word, so "scores" is caught too
W4_SENTENCE = ("Datum shows a record only when it can confirm that the record belongs to this company. "
               "A record filed under a similar name or at a different address is not shown.")
ALL_COMPANIES = (fx.LIEN_COMPANY, fx.LICENSE_COMPANY, fx.INACTIVE_COMPANY, fx.NEW_COMPANY, fx.NO_FLAG_COMPANY, fx.GAPS_COMPANY)
PICKED = Identification(business_name="Invented Air Conditioning", city="Boynton Beach", level="Strong",
                        evidence=("name matches (ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space)", "principal city on record begins with the city you gave", "ACTIVE"))


def build(document_number, identification=None, extra_flags=None):
    return fx.builder(extra_flags).build(document_number, identification)


def test_a_company_with_two_liens_shows_both_newest_first_in_the_marts_own_words():
    report = build(fx.LIEN_COMPANY)
    rows = {row.source_record_id: row for row in fx.load_flags() if row.document_number == fx.LIEN_COMPANY}
    assert [flag.fact_date for flag in report.flags] == [date(2026, 11, 16), date(2016, 11, 29)]   # newest first
    for flag in report.flags:
        row = next(r for r in rows.values() if r.citation == flag.title)
        # Every word on a linked record is a mart column, copied as it is. The builder adds none of its own.
        assert (flag.kind, flag.fact.text, flag.fact.citation, flag.status, flag.status_note, flag.caveat) == \
               ("linked_record", row.citation, row.citation, row.status, row.status_note, row.caveat)
        assert (flag.fact.source_url, flag.fact.fetched_at, flag.fact.fetched_at_is_approximate) == (row.source_url, row.fetched_at, row.fetched_at_is_approximate)
    assert report.summary == "2 flags found in 3 sources checked."
    text = render_markdown(report)
    assert "Status: closed. Certificate of release filed 2026-11-16." in text and "Status: open" in text
    # Each flag's OWN source line, found by a filing number that appears nowhere else on the page. A measured fetch time: no "about".
    assert "- Source: [Florida Department of State federal lien filing 26FLR9900001](https://dos.fl.gov/sunbiz/search/) · fetched 2026-11-18" in text
    assert "- Source: [Florida Department of State federal lien filing 19FLR9900002](https://dos.fl.gov/sunbiz/search/) · fetched about 2026-11-18" in text   # this row's fetch time is an estimate
    assert "- Date on the record: 2026-11-16" in text and "- Date on the record: 2016-11-29" in text
    assert text.count("- Open or closed is read from the state's federal lien files published through 2026-11-16.") == 2   # the caveat, once per lien


def test_an_inactive_company_with_no_linked_record_counts_one_flag_and_never_says_no_flags_found():
    # The old rule W2 left the two company-record flags out of the count. That would put "No flags found" beside an inactive company.
    report = build(fx.INACTIVE_COMPANY)
    assert [(flag.kind, flag.title, flag.fact.text, flag.caveat) for flag in report.flags] == [
        ("company_record", "Inactive with the state", "Inactive with the Florida Division of Corporations",
         "Data as of the snapshot date; changes since then aren't covered until the events file is loaded"),   # the plan's flags table, word for word
    ]
    assert report.summary == "1 flag found in 3 sources checked."
    text = render_markdown(report)
    assert wording.NO_FLAGS not in text and "| Status with the state | Inactive |" in text
    assert "### Inactive with the state\n\n- Inactive with the Florida Division of Corporations\n- Data as of the snapshot date;" in text   # the card: title, fact, caveat
    assert "- Source: [Florida Division of Corporations (Sunbiz) record, document number T26000000003](https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber) · fetched about 2026-10-22" in text
    assert "fetched about 2026-10-22" in text                             # the company record's fetch time is an estimate, and the page says so (rule W1)


def test_a_company_on_record_within_twelve_months_is_flagged_as_new_and_one_outside_them_is_not():
    report = build(fx.NEW_COMPANY)
    assert [(flag.title, flag.fact.text, flag.caveat, flag.fact_date) for flag in report.flags] == [
        ("New company", "On record since 2026-06-15", "May be an effective date", date(2026, 6, 15)),   # the plan's flags table, word for word
    ]
    assert "### New company\n\n- On record since 2026-06-15\n- May be an effective date\n- Source: [" in render_markdown(report)   # the card as a contractor reads it
    company = next(c for c in fx.load_companies() if c.document_number == fx.NEW_COMPANY)
    for on_record, flagged in (
        (date(2025, 11, 24), True),                                       # exactly twelve months before the report: still within them
        (date(2025, 11, 23), False),                                      # one day more than twelve months
        (fx.BUILT_ON, True),                                              # filed the day the report is built
        (fx.BUILT_ON + timedelta(days=1), False),                         # a date in the future is not "within 12 months"
        (None, False),                                                    # no date on record: nothing is assumed
    ):
        backend = FakeReportBackend([replace(company, file_date=on_record)], [], fx.load_sources())
        flags = ReportBuilder(backend, today=lambda: fx.BUILT_ON).build(fx.NEW_COMPANY, None).flags
        assert [flag.flag_type for flag in flags] == (["new_company"] if flagged else []), on_record
    assert one_year_before(date(2024, 2, 29)) == date(2023, 2, 28)        # the year before a leap day has no Feb 29


def test_a_company_with_no_flag_says_exactly_the_no_flags_line():
    report = build(fx.NO_FLAG_COMPANY)
    assert report.flags == () and report.summary == "No flags found in the sources checked."
    text = render_markdown(report)
    assert ("**Active with the state as of Oct 7, 2026. Florida limited liability company (LLC), on record since 2015. "
            "No flags found in the sources checked.**") in text and f"## {wording.HEADING_FLAGS}" not in text


def test_the_count_ignores_a_hidden_flag_and_a_possible_match_even_when_the_backend_hands_them_over():
    # Postgres holds neither today (rule W9). This is the worst case: a backend that returns them anyway.
    shown = next(row for row in fx.load_flags() if row.document_number == fx.LIEN_COMPANY)
    hidden = replace(shown, document_number=fx.NO_FLAG_COMPANY, is_shown=False, source_record_id="26FLR9900091",
                     citation="Florida Department of State federal lien filing 26FLR9900091")
    possible = replace(shown, document_number=fx.NO_FLAG_COMPANY, is_shown=True, link_reason="zip_differs", source_record_id="26FLR9900092",
                       citation="Florida Department of State federal lien filing 26FLR9900092")
    not_a_boolean = replace(shown, document_number=fx.NO_FLAG_COMPANY, is_shown="f", source_record_id="26FLR9900093",
                            citation="Florida Department of State federal lien filing 26FLR9900093")   # a text where True was expected is not "shown"
    report = build(fx.NO_FLAG_COMPANY, extra_flags=[hidden, possible, not_a_boolean])
    assert report.flags == () and report.summary == wording.NO_FLAGS
    text = render_markdown(report)
    for number in ("26FLR9900091", "26FLR9900092", "26FLR9900093"):
        assert number not in text
    counted = build(fx.LIEN_COMPANY, extra_flags=[replace(hidden, document_number=fx.LIEN_COMPANY), replace(possible, document_number=fx.LIEN_COMPANY)])
    assert counted.summary == "2 flags found in 3 sources checked."       # still the two shown liens, and nothing else


def test_company_record_flags_come_first_and_linked_records_follow_newest_first():
    lien = next(row for row in fx.load_flags() if row.document_number == fx.LIEN_COMPANY)
    extra = [replace(lien, document_number=fx.INACTIVE_COMPANY), replace(lien, document_number=fx.INACTIVE_COMPANY, fact_date=None, source_record_id="26FLR9900095")]
    report = build(fx.INACTIVE_COMPANY, extra_flags=extra)
    assert [(flag.kind, flag.fact_date) for flag in report.flags] == [("company_record", None), ("linked_record", date(2026, 11, 16)), ("linked_record", None)]
    assert report.summary == "3 flags found in 3 sources checked."        # the summary counts both kinds (rule W2)
    same_day = [replace(lien, document_number=fx.NO_FLAG_COMPANY, source_record_id=number, citation=f"filing {number}") for number in ("26FLR9900097", "26FLR9900096")]
    titles = [flag.title for flag in build(fx.NO_FLAG_COMPANY, extra_flags=same_day).flags]
    assert titles == ["filing 26FLR9900096", "filing 26FLR9900097"]       # two records of one date come in a fixed order, by record number


def test_the_license_company_shows_the_license_line_and_the_lien_with_its_discharge_note():
    text = render_markdown(build(fx.LICENSE_COMPANY))
    assert "### Florida DBPR license CGC9900004" in text
    assert "Status: inactive. License CGC9900004: inactive, expires 2022-08-31." in text
    assert "this line is about the license, not the person" in text      # the mart's caveat, whole
    assert "Status: open. Certificate of discharge recorded on 2022-09-21." in text


def test_a_tie_is_said_on_the_report_of_whichever_company_was_picked():
    # The old report.py wrote "Strong" for a company that had tied with another one (rule W7).
    assert "2 other companies matched equally well." in build(fx.LIEN_COMPANY, PICKED.model_copy(update={"tied_others": 2})).identification.text
    assert build(fx.LIEN_COMPANY, PICKED.model_copy(update={"tied_others": 1})).identification.text.endswith("1 other company matched equally well.")
    assert "matched equally well" not in build(fx.LIEN_COMPANY, PICKED).identification.text   # no tie: nothing is said about one


def test_a_company_picked_at_the_level_possible_says_so_at_the_top_of_its_report():
    caution = "This is only a POSSIBLE match: the name is similar, and nothing else confirms it is the company you mean."
    possible = build(fx.LIEN_COMPANY, PICKED.model_copy(update={"level": "Possible"}))
    text = render_markdown(possible)
    assert possible.caution == caution and text.count(f"**{caution}**") == 1 and text.index(caution) < text.index("flags found")   # before the summary line
    for identification in (PICKED, PICKED.model_copy(update={"level": "Likely"}), None):
        report = build(fx.LIEN_COMPANY, identification)
        assert report.caution == "" and "POSSIBLE" not in render_markdown(report)   # only the level Possible carries it, and "opened by its number" claims no level


def test_the_identification_line_shows_the_extracted_fields_and_no_note():
    # The old report.py wrote the raw note, owner's name included, into the saved report (rule W6).
    identification = build(fx.LIEN_COMPANY, PICKED).identification
    assert identification.citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000001"   # it restates the status, so it cites the record
    line = identification.text
    assert line == ('from the business name "Invented Air Conditioning", the city "Boynton Beach" · match level Strong '
                    "(name matches (ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space); principal city on record begins with the city you gave; ACTIVE) "
                    "· chosen by the user from a shortlist.")
    with_street = PICKED.model_copy(update={"city": "", "street": "Race Track Rd"})
    assert 'the business name "Invented Air Conditioning", the street "Race Track Rd"' in build(fx.LIEN_COMPANY, with_street).identification.text
    opened = render_markdown(build(fx.LIEN_COMPANY))
    assert "**How this company was identified:** opened by its document number, so no match level applies." in opened and "match level Strong" not in opened


@pytest.mark.parametrize("document_number", ALL_COMPANIES)
def test_no_report_holds_a_word_that_reassures_or_judges(document_number):
    # Rule W4. It fails on: clean, safe, risky, trustworthy, reliable, credit, score, recommend, and words that start with one of them.
    for identification in (None, PICKED, PICKED.model_copy(update={"level": "Possible", "tied_others": 3})):
        report = build(document_number, identification)
        text = render_markdown(report)
        assert BANNED.findall(text) == []
        assert text.count(W4_SENTENCE) == 1                               # on every report, with or without flags, in these exact words
        assert "*Sourced public-record facts, not advice. Verify on the official record before relying on them.*" in text
        assert (wording.NO_FLAGS in text) == (len(report.flags) == 0)     # the line is there exactly when no flag is shown


def test_the_check_for_banned_words_can_fail_and_the_fixed_wording_passes_it():
    assert BANNED.findall("No flags found, so this company looks clean. Credit scores are recommended.") == ["clean", "Credit", "score", "recommend"]
    assert BANNED.findall("A safe, reliable and trustworthy choice, not a risky one.") == ["safe", "reliable", "trustworthy", "risky"]   # the other four
    assert wording.BANNED_WORDS == W4_WORDS
    constants = [value for name, value in vars(wording).items() if name.isupper() and name != "BANNED_WORDS"]   # a constant's name is in capitals
    fixed = [value for value in constants if isinstance(value, str)]
    fixed += [item for value in constants if isinstance(value, (tuple, dict)) for item in (value.values() if isinstance(value, dict) else value)]
    assert len(fixed) > 40 and all(BANNED.findall(text) == [] for text in fixed)   # every constant of wording.py but the list of banned words itself


def test_the_sources_lists_say_what_was_checked_through_which_date_and_what_was_not():
    report = build(fx.NO_FLAG_COMPANY)
    assert [fact.citation for fact in report.sources_checked] == [
        "Florida Division of Corporations company record (Sunbiz)",
        "Federal tax liens filed with the Florida Department of State",
        "Florida DBPR construction contractor licenses",
    ]                                                                     # only the three sources whose flags may be shown (rule W5)
    assert report.sources_checked[1].text.startswith("Federal tax liens filed with the Florida Department of State: data through 2026-11-16. ")
    assert report.sources_not_checked == (
        "Florida DBPR discipline records against construction license holders",
        "Duval County recorded liens, tax warrants and judgments",
    ) + wording.NOT_CHECKED_ALWAYS                                        # a hidden source is listed as NOT checked, never as checked
    assert "Court cases" in report.sources_not_checked and "UCC (Uniform Commercial Code) filings" in report.sources_not_checked
    text = render_markdown(report)
    assert text.index("## Sources checked") < text.index("## Not checked") < text.index("How this company was identified")
    for fact in report.sources_checked:                                   # every checked source is ON the page, with its date, its address and its fetch date
        assert f"- {fact.text} Source: [{fact.citation}]({fact.source_url}) · {fact.fetched_text}" in text
    assert "- Federal tax liens filed with the Florida Department of State: data through 2026-11-16." in text
    for item in report.sources_not_checked:                               # and so is everything that was NOT checked
        assert f"\n- {item}\n" in text
    assert "\n- Court cases\n" in text and "\n- Duval County recorded liens, tax warrants and judgments\n" in text
    # R: the order is the table's list_order whatever order a backend returns the rows in.
    backwards = FakeReportBackend(fx.load_companies(), [], list(reversed(fx.load_sources())))
    assert ReportBuilder(backwards, today=lambda: fx.BUILT_ON).build(fx.NO_FLAG_COMPANY, None).sources_checked == report.sources_checked


def test_a_report_is_refused_when_no_source_may_be_shown():
    # "No flags found in the sources checked." under an empty list of sources would be an all-clear about nothing.
    hidden_everything = [replace(row, is_shown=False) for row in fx.load_sources()]
    for sources in (hidden_everything, []):
        for document_number in (fx.NO_FLAG_COMPANY, fx.INACTIVE_COMPANY):  # with a flag or without one
            with pytest.raises(NoSourceChecked):
                ReportBuilder(FakeReportBackend(fx.load_companies(), [], sources), today=lambda: fx.BUILT_ON).build(document_number, None)
    with pytest.raises(ValueError, match="at least one source checked"):
        wording.summary_line(0, 0)
    with pytest.raises(ValueError, match="at least one source checked"):
        wording.summary_line(2, 0)


def test_the_identification_has_no_default_so_no_caller_can_drop_it_by_accident():
    with pytest.raises(TypeError, match="identification"):
        fx.builder().build(fx.NO_FLAG_COMPANY)                            # a caller must say None in so many words
    by_number = fx.builder().build(fx.NO_FLAG_COMPANY, None).identification.text
    assert by_number == "opened by its document number, so no match level applies." and "search" not in by_number   # it claims nothing about a search


def test_everything_stated_about_the_company_is_a_fact_with_the_company_records_source():
    report = build(fx.LIEN_COMPANY)
    assert [label for label, _ in report.company] == ["Legal name", "Document number", "Status with the state", "Entity type", "Date on record", "Principal address"]
    for _, fact in report.company + (("", report.company_source),):
        assert fact.source_url == "https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber"
        assert fact.citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000001"
        assert fact.fetched_at == datetime(2026, 10, 22, 19, 31, 31, tzinfo=timezone.utc) and fact.fetched_at_is_approximate is True
    values = {label: fact.text for label, fact in report.company}
    assert values["Entity type"] == "Florida limited liability company (LLC)"
    assert values["Date on record"] == "2019-05-06 (may be an effective date; confirm on the official record)"
    assert values["Principal address"] == "1 INVENTED WAY, BOYNTON BEACH, FL 33426"
    assert "data published 2026-10-07" in report.company_source.text
    # ...and the page shows it. Until leg C4 the row showed the citation alone, and the date the state published the file was on no page.
    assert ("| Official record | [Florida Division of Corporations (Sunbiz) record, document number T26000000001, data published 2026-10-07]"
            "(https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber) · fetched about 2026-10-22 |") in render_markdown(report)


def test_a_gap_in_the_states_record_is_said_and_never_filled_in():
    values = {label: fact.text for label, fact in build(fx.GAPS_COMPANY).company}
    assert (values["Date on record"], values["Principal address"]) == ("Not on record", "Not on record")
    assert values["Entity type"] == "TRUST"                               # a code with no label is shown as the state writes it
    text = render_markdown(build(fx.GAPS_COMPANY))
    assert "None" not in text
    no_status = replace(next(c for c in fx.load_companies() if c.document_number == fx.GAPS_COMPANY), status_code=None, filing_type=None)
    report = ReportBuilder(FakeReportBackend([no_status], [], fx.load_sources()), today=lambda: fx.BUILT_ON).build(fx.GAPS_COMPANY, None)
    values = {label: fact.text for label, fact in report.company}
    assert (values["Status with the state"], values["Entity type"]) == ("Not on record", "Not on record")
    assert report.flags == ()                                             # no status on record is not "inactive"


def test_a_fetch_time_in_another_zone_is_converted_and_one_with_no_zone_is_refused():
    company = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)
    lien = next(row for row in fx.load_flags() if row.document_number == fx.LIEN_COMPANY)
    eastern = replace(lien, document_number=fx.NO_FLAG_COMPANY, fetched_at=lien.fetched_at.astimezone(timezone(timedelta(hours=-5))))
    report = ReportBuilder(FakeReportBackend([company], [eastern], fx.load_sources()), today=lambda: fx.BUILT_ON).build(fx.NO_FLAG_COMPANY, None)
    assert report.flags[0].fact.fetched_at == lien.fetched_at and report.flags[0].fact.fetched_at.utcoffset() == timedelta(0)
    naive = replace(eastern, fetched_at=lien.fetched_at.replace(tzinfo=None))
    with pytest.raises(ValueError, match="needs a time zone"):
        ReportBuilder(FakeReportBackend([company], [naive], fx.load_sources()), today=lambda: fx.BUILT_ON).build(fx.NO_FLAG_COMPANY, None)


def test_a_number_that_names_no_company_or_is_not_a_number_at_all_is_not_found():
    class NeverAsked:
        def company(self, document_number):
            raise AssertionError("the backend was asked about something that is not a document number")

    for text in ("", "T2600000000X!", "../../etc", "t26000000001", "T260000000012345", "T26 000000001", "' or 1=1 --"):
        assert not looks_like_a_document_number(text)
        with pytest.raises(CompanyNotFound):
            ReportBuilder(NeverAsked()).build(text, None)                       # refused before any query is made
    assert looks_like_a_document_number("T26000000001") and looks_like_a_document_number("688030")
    with pytest.raises(CompanyNotFound):
        build("T26000000099")                                             # the right shape, and no such company


def test_the_functions_that_lay_out_a_report_or_talk_in_the_terminal_hold_no_sentence_of_their_own():
    # Every sentence must come from wording.py or from a mart column. A text of two or more words written inside these
    # functions would be wording nobody reviewed. Codes such as "company_record" and marks such as "|---|---|" are fine.
    def texts(code):
        for constant in code.co_consts:
            if isinstance(constant, str):
                yield constant
            elif hasattr(constant, "co_consts"):                          # a function or a comprehension nested inside
                yield from texts(constant)

    a_sentence = re.compile(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}")                # two words with a space between
    functions = (render_markdown, ReportBuilder.build, ReportBuilder.company_record_flags, ReportBuilder.linked_flags, candidate_for_page,
                 address_candidate_for_page, address_text, count_fact,
                 terminal.run, terminal.show_shortlist, terminal.source_line, terminal.pick, terminal.read_note, terminal.others_at_the_same_level)
    for function in functions:
        written = [text for text in texts(function.__code__) if text != function.__doc__ and a_sentence.search(text)]
        assert written == [], (function.__name__, written)
    # A sentence kept in a module-level name and printed from there would slip past the check above, so those are read too.
    for module in (builder_module, terminal):
        kept = [name for name, value in vars(module).items() if isinstance(value, str) and not name.startswith("__") and a_sentence.search(value)]
        assert kept == [], (module.__name__, kept)
    # main() is not in the list: it holds the connection text "dbname=datum_dev" and prints nothing itself.


def test_a_search_result_becomes_a_page_candidate_whose_name_and_place_are_facts():
    companies = {c.document_number: c for c in fx.load_companies()}
    found = SearchCandidate(company=companies[fx.LIEN_COMPANY], similarity=100, city_match=True, exact_name=True, every_word=True)
    candidate = candidate_for_page(found, "Strong", city_given=True)
    assert (candidate.name.text, candidate.place.text, candidate.level) == ("INVENTED AIR CONDITIONING, LLC", "BOYNTON BEACH, FL", "Strong")
    assert [reason.text for reason in candidate.evidence] == ["name matches (ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space)", "principal city on record begins with the city you gave", "ACTIVE"]
    for fact in (candidate.name, candidate.place) + candidate.evidence:   # rule W1: the status and the city are stated with their source, like the name
        assert fact.source_url == companies[fx.LIEN_COMPANY].source_url and fact.fetched_at_is_approximate is True
        assert fact.citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000001"
    assert candidate.mark is None                                         # an active company carries no mark (rule S10)
    marked = candidate_for_page(SearchCandidate(company=companies[fx.INACTIVE_COMPANY], similarity=100, city_match=False, exact_name=True, every_word=True), "Likely", city_given=True)
    assert marked.mark.text == "Inactive with the state" and marked.mark.source_url == companies[fx.INACTIVE_COMPANY].source_url   # the mark is a Fact with the company record's source
    assert marked.mark.citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000003"
    assert [reason.text for reason in marked.evidence][-1].startswith("principal city on record is TAMPA")   # and the status is not said again among the reasons
    no_city = candidate_for_page(SearchCandidate(company=companies[fx.GAPS_COMPANY], similarity=90, city_match=False, exact_name=False, every_word=False), "Possible", city_given=True)
    assert no_city.place is None                                          # no city on record: no place is shown
    assert [reason.text for reason in no_city.evidence] == ["name is similar (90/100)", "no principal city on record for this company", "ACTIVE"]


def test_a_name_with_a_table_mark_in_it_does_not_break_the_table():
    company = replace(next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY), entity_name="INVENTED A|B LLC")
    text = render_markdown(ReportBuilder(FakeReportBackend([company], [], fx.load_sources()), today=lambda: fx.BUILT_ON).build(fx.NO_FLAG_COMPANY, None))
    assert "| Legal name | INVENTED A\\|B LLC |" in text


class RecordingConnection:
    """Stands in for a psycopg connection: it keeps what it was asked and answers from the fixture rows."""

    def __init__(self, rows):
        self.rows, self.asked = rows, []

    def execute(self, sql, params=None):
        self.asked.append((sql, params))
        return self

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


def test_the_postgres_backend_sends_the_document_number_as_a_value_and_asks_for_shown_flags_only():
    for sql in (PostgresReportBackend.COMPANY_SQL, PostgresReportBackend.FLAGS_SQL):
        assert sql.count("%(document_number)s") == 1 and "'" not in sql and "{" not in sql
    assert PostgresReportBackend.FLAGS_SQL.endswith("from company_flags where document_number = %(document_number)s and is_shown")
    assert "company_possible_matches" not in PostgresReportBackend.COMPANY_SQL + PostgresReportBackend.FLAGS_SQL + PostgresReportBackend.SOURCES_SQL
    lien = next(row for row in fx.load_flags() if row.document_number == fx.LIEN_COMPANY)
    as_a_row = tuple(getattr(lien, name) for name in ("document_number", "flag_type", "fact_date", "status", "status_note", "source", "source_record_id",
                                                      "source_url", "citation", "fetched_at", "caveat", "is_shown", "fetched_at_is_approximate"))
    conn = RecordingConnection([as_a_row])
    backend = PostgresReportBackend(conn)
    assert conn.asked[0] == ("select set_config('TimeZone', %s, false)", ("UTC",))   # this session only: fetch times come back in UTC
    assert backend.flags("T1'; drop table company_flags; --") == [lien]   # the columns map onto FlagRow's fields in order
    assert conn.asked[-1][1] == {"document_number": "T1'; drop table company_flags; --"} and "drop table" not in conn.asked[-1][0]
    assert PostgresReportBackend(RecordingConnection([])).company("T26000000001") is None


def test_a_company_found_by_its_address_says_so_on_its_report_and_claims_no_match_level():
    # Phase D, leg D1. The identification line is built from the extracted street and city, and it carries the company record's source.
    how = Identification(found_by="address", street="1 invented wy", city="Boynton Beach", tied_others=1)
    report = fx.builder().build(fx.LIEN_COMPANY, how)
    assert report.identification.text == (
        'from the street "1 invented wy", the city "Boynton Beach" · found by its principal address on record (the same house number, and a street name '
        "made only of words that were typed) · chosen by the user from the active companies listed. 1 other active company was listed with it.")
    assert report.identification.citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000001"
    assert report.caution == "" and "match level" not in render_markdown(report)   # no level was claimed, so there is nothing to caution about


def test_a_company_on_an_address_list_shows_its_address_as_the_state_has_it():
    companies = {c.document_number: c for c in fx.load_companies()}
    shown = address_candidate_for_page(companies[fx.NO_FLAG_COMPANY])
    assert (shown.name.text, shown.address.text) == ("INVENTED ELECTRIC LLC", "5 INVENTED WAY, MIAMI, FL 33130")
    assert shown.address.source_url == companies[fx.NO_FLAG_COMPANY].source_url and shown.address.fetched_at_is_approximate is True   # rule W1: the address is a Fact
    assert shown.address.citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000005"
    assert address_text(companies[fx.GAPS_COMPANY]) == ""                 # no address on record: nothing is made up, and the report says "Not on record"


def test_a_count_of_companies_cites_the_records_it_was_made_from_and_is_as_fresh_as_its_oldest_input():
    # CLAUDE.md rule 3: a derived value carries its inputs' provenance. "2 inactive companies ..." is derived from two company records.
    base = next(c for c in fx.load_companies() if c.document_number == fx.INACTIVE_COMPANY)
    older = replace(base, fetched_at=base.fetched_at - timedelta(days=30), fetched_at_is_approximate=False)
    counted = count_fact("2 inactive companies also match and are not listed.", (base, older))
    assert counted.text.startswith("2 inactive companies") and counted.citation == "Florida Division of Corporations (Sunbiz) company records"
    assert counted.source_url == base.source_url and counted.fetched_at == older.fetched_at   # the OLDEST fetch time of the two
    assert counted.fetched_at_is_approximate is True                      # one of the two times is an estimate, so the count's is
    assert count_fact("x", (older,)).fetched_at_is_approximate is False and count_fact("", ()) is None   # no companies: no sentence and no fact


# --- The summary at the top (Phase D, leg D2; working rule S9) ------------------------------------------

MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")   # typed out, not read from wording.py
SUMMARY = re.compile(r"\*\*((Active|Inactive) with the state as of ([A-Z][a-z]{2}) (\d{1,2}), (\d{4})\. (.+?), on record since (\d{4})\. (No flags found in the sources checked\.|(\d+) flags? found in \d+ sources? checked\.))\*\*")
FIVE_REPORTS = (fx.LIEN_COMPANY, fx.LICENSE_COMPANY, fx.INACTIVE_COMPANY, fx.NEW_COMPANY, fx.NO_FLAG_COMPANY)   # the five kinds of report leg C3 built


def table_row(text, label):
    """The value of one row of the company record table in a rendered report."""
    return re.search(rf"^\| {re.escape(label)} \| (.+) \|$", text, flags=re.M).group(1)


@pytest.mark.parametrize("document_number", FIVE_REPORTS)
def test_the_summary_at_the_top_agrees_with_the_facts_below_it(document_number):
    # The summary is built from the same values as the rows under it. This test reads both off the RENDERED report and compares
    # them, so it fails if the two ever come from different places: the status, the year, the count of flags and the date.
    company = next(c for c in fx.load_companies() if c.document_number == document_number)
    text = render_markdown(build(document_number))
    summary = SUMMARY.search(text)
    assert summary, text[:300]
    whole, status, month, day_of_month, year_published, entity_type, year_on_record, count_line, count = summary.groups()
    assert status == table_row(text, "Status with the state")             # the status in the summary is the status in the table
    assert entity_type == table_row(text, "Entity type")
    assert year_on_record == table_row(text, "Date on record")[:4] == str(company.file_date.year)
    cards = text[:text.index("## The records behind this summary")].count("\n### ")   # one heading per flag card, all above the records
    assert cards == len(build(document_number).flags)                     # the cards on the page are the report's flags
    assert count_line == "No flags found in the sources checked." if cards == 0 else count == str(cards)   # and the summary counts exactly those cards
    assert (int(year_published), MONTH_NAMES.index(month) + 1, int(day_of_month)) == (company.published_on.year, company.published_on.month, company.published_on.day)
    assert f"data published {company.published_on:%Y-%m-%d}" in table_row(text, "Official record")   # the same date, as the table writes it
    assert text.count(whole) == 1 and text.count("with the state as of") == 1   # the summary is in the report once, not a second time lower down
    after = text[summary.end():].lstrip("\n")
    assert after.startswith(W4_SENTENCE + "\n")                           # rule W4's sentence comes right after the summary line
    assert text.index(whole) < text.index("## The records behind this summary") < text.index("| Legal name |") < text.index("### Sources checked") < text.index("### Not checked")
    assert BANNED.findall(text) == [] and text.count(W4_SENTENCE) == 1


def test_the_summarys_date_is_the_records_own_published_date_and_not_the_snapshots():
    # A company first seen in a daily file has a later published date than the quarterly snapshot. The summary must give ITS date.
    daily = replace(next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY), published_on=date(2026, 11, 5), status_code="I")
    report = ReportBuilder(FakeReportBackend([daily], [], fx.load_sources()), today=lambda: fx.BUILT_ON).build(fx.NO_FLAG_COMPANY, None)
    assert report.headline[0].text == "Inactive with the state as of Nov 5, 2026."
    assert "data published 2026-11-05" in report.company_source.text and report.headline[0].source_url == daily.source_url   # the summary's fact cites the company record
    assert report.headline[0].citation == "Florida Division of Corporations (Sunbiz) record, document number T26000000005"


def test_the_summary_says_a_gap_in_the_record_and_never_fills_it_in():
    gaps = render_markdown(build(fx.GAPS_COMPANY))                         # no date on record, and an entity-type code with no label
    assert "**Active with the state as of Oct 7, 2026. TRUST, with no date on record. No flags found in the sources checked.**" in gaps
    base = next(c for c in fx.load_companies() if c.document_number == fx.NO_FLAG_COMPANY)

    def summary_of(company):
        return " ".join(fact.text for fact in ReportBuilder(FakeReportBackend([company], [], fx.load_sources()), today=lambda: fx.BUILT_ON).build(company.document_number, None).headline)

    assert summary_of(replace(base, status_code=None)) == "No status with the state is on record as of Oct 7, 2026. Florida limited liability company (LLC), on record since 2015."
    assert summary_of(replace(base, filing_type=None)) == "Active with the state as of Oct 7, 2026. Entity type not on record, on record since 2015."
    assert summary_of(replace(base, file_date=date(2120, 1, 1))).endswith("with a date on record in 2120, which is in the future.")   # not "on record since 2120"
    # "The future" is measured from the day the report is BUILT, which the builder is told, and not from the machine's clock. The day
    # after fx.BUILT_ON is Nov 25, 2026, which for the machine is today or earlier, so this fails if the builder asks the clock.
    assert summary_of(replace(base, file_date=fx.BUILT_ON + timedelta(days=1))).endswith("with a date on record in 2026, which is in the future.")
    assert summary_of(replace(base, file_date=fx.BUILT_ON)).endswith("on record since 2026.")   # the day itself is not the future
    assert "None" not in gaps and "None" not in summary_of(replace(base, status_code=None, filing_type=None, file_date=None))


def test_a_possible_match_still_says_so_before_the_summary():
    picked = Identification(business_name="Invented Electric", level="Possible", evidence=("name is similar (90/100)", "ACTIVE"))
    text = render_markdown(build(fx.NO_FLAG_COMPANY, picked))
    assert text.index(wording.POSSIBLE_CAUTION) < text.index("Active with the state as of")   # the caution is the first thing read, then the summary
