"""test_wording.py: offline tests for src/datum/wording.py, the one module that holds every fixed sentence.

Most of wording.py is constants, and a constant is checked by reading it. What is tested
here is the handful of functions that put a sentence together, because each has a case
that is easy to get wrong: one flag or several, a tie or none, an estimated fetch time.

Run from ~/datum:  pytest
"""

from datetime import date, datetime, timezone   # the dates these sentences print

from datum import wording


def test_the_summary_line_counts_flags_and_is_the_exact_no_flags_line_when_there_are_none():
    assert wording.summary_line(0, 3) == "No flags found in the sources checked."     # acceptance test A8, to the letter
    assert wording.summary_line(1, 3) == "1 flag found in 3 sources checked."
    assert wording.summary_line(2, 1) == "2 flags found in 1 source checked."
    assert all(wording.summary_line(count, 3) != wording.NO_FLAGS for count in range(1, 30))   # rule W2: never beside a flag


def test_an_estimated_fetch_time_says_about_and_a_measured_one_does_not():
    at = datetime(2026, 11, 18, 7, 10, 57, tzinfo=timezone.utc)
    assert wording.fetched_text(at, False) == "fetched 2026-11-18"
    assert wording.fetched_text(at, True) == "fetched about 2026-11-18"   # rule W1
    assert wording.day_text(date(2026, 3, 4)) == "2026-03-04"


def test_a_tie_is_worded_for_one_other_company_for_several_and_not_at_all_for_none():
    assert (wording.tied_text(0, "Strong"), wording.tied_text(-1, "Likely")) == ("", "")
    assert wording.tied_text(1, "Strong") == "1 other company matched equally well."
    assert wording.tied_text(4, "Strong") == "4 other companies matched equally well."


def test_a_sentence_about_a_count_says_what_the_count_covers():
    # Below the level Strong only the companies on the shortlist are counted, so the sentence may not read as if all were.
    assert wording.tied_text(1, "Likely") == "1 other company on the shortlist matched equally well."
    assert wording.tied_text(3, "Possible") == "3 other companies on the shortlist matched equally well."
    # The line under the shortlist names the level it counts, which is exactly what is in Shortlist.not_shown.
    assert wording.not_shown_text(0) == ""
    assert wording.not_shown_text(1) == "1 more company matches at the level Strong and is not on this list."
    assert wording.not_shown_text(3) == "3 more companies match at the level Strong and are not on this list."
    ignoring = "ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space"
    assert wording.EVIDENCE_EXACT_NAME == f"name matches ({ignoring})" and wording.EVIDENCE_CITY_MATCHES == "principal city on record begins with the city you gave"
    every = [value for name, value in vars(wording).items() if name.isupper() and isinstance(value, str)]
    # Phrases that claimed more than the comparison behind them does. None may come back.
    for phrase in ("exactly this name", "matches exactly", "ignoring LLC/INC", "in the city you gave", "city matches", "punctuation", "spacing"):
        assert not [text for text in every if phrase in text], phrase


def test_the_line_above_a_tied_shortlist_names_the_level_and_the_count_and_promises_nothing():
    assert (wording.tie_text(1, "Strong"), wording.tie_text(0, "Strong"), wording.tie_text(3, None)) == ("", "", "")   # one company at the top is no tie
    assert wording.tie_text(2, "Strong") == "2 companies match at the level Strong. Check which one you mean before you open a report."
    assert wording.tie_text(3, "Likely") == "3 companies on this list match at the level Likely. Check which one you mean before you open a report."
    assert wording.tie_text(5, "Possible") == "5 companies on this list match at the level Possible. Check which one you mean before you open a report."
    every = " | ".join(value for name, value in vars(wording).items() if name.isupper() and isinstance(value, str))
    for phrase in ("equally likely", "would help tell them apart", "Try again in a few minutes"):
        assert phrase not in every, phrase                                # three things the app could not stand behind


def test_the_line_under_a_list_that_is_out_of_level_order_is_rule_s12s_sentence_word_for_word():
    # Phase D rule S12 gives the sentence, so it is typed out here and not read from wording.py.
    sentence = "The list is in search order. The level beside each company says how much of the record agrees with what you typed."
    assert wording.search_order_text(True) == wording.SHORTLIST_SEARCH_ORDER == sentence
    assert wording.search_order_text(False) == ""                         # levels that already go from best to worst need no sentence


def test_the_reason_about_a_place_in_a_name_says_what_was_compared_and_claims_no_location():
    # Phase D rule S14. The comparison is "every word of the city is a word of the name", so that is what the reason says.
    # A name that holds a place does not put the company there, so the line says where the WORDS are and nothing about the company's location.
    assert wording.EVIDENCE_CITY_IN_NAME == "every word of the city you gave is in the company's name"


def test_the_identification_line_is_built_from_extracted_fields_and_leaves_out_an_empty_one():
    line = wording.identified_text("Acme Roofing", "", "", "Likely", ("name is similar (93/100)", "ACTIVE"), 0)
    assert line == 'from the business name "Acme Roofing" · match level Likely (name is similar (93/100); ACTIVE) · chosen by the user from a shortlist.'
    full = wording.identified_text("Acme Roofing", "Tampa", "Bay St", "Strong", ("ACTIVE",), 2)
    assert 'the business name "Acme Roofing", the city "Tampa", the street "Bay St"' in full and full.endswith(" 2 other companies matched equally well.")
    likely = wording.identified_text("Acme Roofing", "Tampa", "", "Likely", ("ACTIVE",), 2)
    assert likely.endswith(" 2 other companies on the shortlist matched equally well.")


def test_the_not_checked_list_names_what_the_brief_says_datum_never_looked_at():
    listed = " | ".join(wording.NOT_CHECKED_ALWAYS).lower()
    for subject in ("court cases", "ucc", "other counties", "fictitious names", "after the snapshot date"):
        assert subject in listed                                          # rule W5. The two hidden sources come from the table source_coverage


def test_the_sentence_every_report_carries_and_the_banned_words_are_held_here_as_literal_text():
    # A test that compares a sentence with the constant it came from passes when the constant is emptied. These are typed out.
    assert wording.CONFIRMED_ONLY == ("Datum shows a record only when it can confirm that the record belongs to this company. "
                                      "A record filed under a similar name or at a different address is not shown.")   # rule W4, word for word
    assert wording.BANNED_WORDS == ("clean", "safe", "risky", "trustworthy", "reliable", "credit", "score", "recommend")   # rule W4's eight words
    assert wording.SEARCH_UNAVAILABLE == "The search is unavailable right now, so no company is shown."
    assert wording.REPORT_UNAVAILABLE == "The report is unavailable right now."
    assert wording.POSSIBLE_CAUTION == "This is only a POSSIBLE match: the name is similar, and nothing else confirms it is the company you mean."
    assert wording.IDENTIFIED_BY_NUMBER == "opened by its document number, so no match level applies."
    assert wording.NOTE_NOT_ON_COMMAND_LINE == ("What you typed after the command was not used. A shell usually keeps each command line in its history file, "
                                                "so that text may be stored there now. Type the note below instead.")
    assert "not kept" not in wording.NOTE_NOT_ON_COMMAND_LINE             # it is shown exactly when the text MAY have been kept, so it must not say otherwise


def test_the_two_company_record_flags_use_the_plans_wording_word_for_word():
    # docs/mvp_plan_nov8.md, section 4, the first two rows of the flags table.
    assert wording.FLAG_INACTIVE_TEXT == "Inactive with the Florida Division of Corporations"
    assert wording.FLAG_INACTIVE_CAVEAT == "Data as of the snapshot date; changes since then aren't covered until the events file is loaded"
    assert wording.FLAG_NEW_TEXT.format(day="2026-03-14") == "On record since 2026-03-14" and wording.FLAG_NEW_CAVEAT == "May be an effective date"
    assert wording.DISCLAIMER == "Sourced public-record facts, not advice. Verify on the official record before relying on them."


def test_the_sentences_of_an_address_search_are_held_here_as_literal_text():
    # Phase D, leg D1. Rule S8's sentence is typed out word for word, and so is every sentence that counts companies.
    assert wording.PRINCIPAL_ADDRESS_NOTE == "A company's principal address is the address it gave the state, which is not always where it does business."
    assert wording.count_text(0, wording.ADDRESS_INACTIVE_ONE, wording.ADDRESS_INACTIVE_MANY) == ""   # no sentence about no companies
    assert wording.count_text(1, wording.ADDRESS_INACTIVE_ONE, wording.ADDRESS_INACTIVE_MANY) == "1 inactive company also matches and is not listed."
    assert wording.count_text(2, wording.ADDRESS_INACTIVE_ONE, wording.ADDRESS_INACTIVE_MANY) == "2 inactive companies also match and are not listed."
    assert wording.count_text(1, wording.ADDRESS_ACTIVE_ONE, wording.ADDRESS_ACTIVE_MANY) == "1 active company matches."
    assert wording.count_text(3, wording.ADDRESS_NO_STATUS_ONE, wording.ADDRESS_NO_STATUS_MANY) == "3 companies with no status on record also match and are not listed."
    assert "inactive" not in wording.ADDRESS_NO_STATUS_ONE + wording.ADDRESS_NO_STATUS_MANY   # no status on record is never called inactive
    assert wording.ADDRESS_TOO_MANY == "That house number and street name are on the records of too many companies to list them. Add the business's name."
    assert wording.address_not_found_text(city_given=False) == wording.ADDRESS_NOT_FOUND and "city" not in wording.ADDRESS_NOT_FOUND
    assert wording.address_not_found_text(city_given=True).startswith("No company matches: none has a principal address on record with that house number, "
                                                                      "a street name made only of words you typed, and a principal city that begins with the city you gave.")
    assert wording.address_compared_text("8586", city_given=False).endswith("so it has to be typed too. You gave no city, so a match can be in any city.")
    assert wording.address_compared_text("8586", city_given=True).endswith("so it has to be typed too. Its principal city on record also begins with the city you gave.")


def test_the_sentence_about_what_an_address_search_compares_names_exactly_the_words_the_search_leaves_out():
    # Phase D rule S15 (leg D4). The sentence is typed out, and then checked against the search's own lists, so that it cannot
    # name a direction or a unit word the search does not leave out, or leave one out that it does. Until leg D4 it named four
    # directions and no unit, and the two sentences for "no match" advised adding a suite, which is no longer compared.
    import re
    from datum.search import DIRECTIONS, HOME_UNIT_WORDS, OFFICE_UNIT_WORDS
    assert wording.ADDRESS_COMPARED == (
        "A company matches when its principal address on record has the house number {house_number} and a street name made only of words you typed. "
        "Three things are not compared: the kind of street, such as ST or PKWY; a direction (N, S, E, W, NORTH, SOUTH, EAST, WEST, NE, NW, SE or SW); "
        "and an office unit (STE, SUITE, BLDG, FL, FLOOR, RM or ROOM) with the number or letter after it. "
        "An apartment, unit or lot number on the record is compared, so it has to be typed too."
    )
    named = re.findall(r"\(([^)]*)\)", wording.ADDRESS_COMPARED)          # the two lists in brackets
    assert set(re.findall(r"[A-Z]+", named[0])) == set(DIRECTIONS) and len(DIRECTIONS) == 12
    assert tuple(re.findall(r"[A-Z]+", named[1])) == OFFICE_UNIT_WORDS
    assert HOME_UNIT_WORDS == ("APT", "UNIT", "LOT")                      # the three the last sentence says are still compared
    for sentence in (wording.ADDRESS_NOT_FOUND, wording.ADDRESS_NOT_FOUND_IN_CITY):
        assert sentence.endswith("and add the apartment, unit or lot number if the address has one.") and "suite" not in sentence.lower()


def test_the_sentence_for_an_address_with_only_inactive_companies_asks_for_the_name_and_says_no_number():
    # Phase D rule S16. Typed out here, so that a change to the words is a change to this test too.
    assert wording.ADDRESS_ONLY_INACTIVE == "Type the business's name to look for it with the name search, which lists inactive companies too."
    assert wording.only_inactive_text(0, 1) == wording.only_inactive_text(0, 7) == wording.ADDRESS_ONLY_INACTIVE   # no active company, and at least one inactive one
    assert wording.only_inactive_text(1, 2) == wording.only_inactive_text(0, 0) == wording.only_inactive_text(3, 0) == ""   # an active one, or no inactive one: nothing


def test_the_identification_line_of_an_address_search_names_the_street_and_no_match_level():
    line = wording.identified_by_address_text("8586 palm pwwy", "", 0)
    assert line == ('from the street "8586 palm pwwy" · found by its principal address on record (the same house number, and a street name made only of '
                    "words that were typed) · chosen by the user from the active companies listed.")
    assert "level" not in line                                            # rule S4 keeps the three levels for the name search
    with_city = wording.identified_by_address_text("8586 palm pwwy", "Orlando", 1)
    assert 'from the street "8586 palm pwwy", the city "Orlando" ·' in with_city and with_city.endswith(" 1 other active company was listed with it.")
    assert wording.identified_by_address_text("12 made up rd", "", 4).endswith(" 4 other active companies were listed with it.")


def test_the_pages_ask_for_what_the_two_searches_use_and_no_longer_for_a_street_beside_a_name():
    # Question Q42: until leg D1 the pages asked for "a street or a city", and the search used no street.
    asked = "the business's name and its city, or a street address that begins with its house number."
    assert wording.SEARCH_HINT == "A business name and its city, or a street address that begins with its house number."
    assert wording.NOTE_EMPTY == "Nothing was typed. Type " + asked and wording.NOTE_TOO_LONG == "That is too long to search for. Type " + asked
    assert wording.ASK_FOR_A_BUSINESS_ON_A_PAGE == "That describes a business but doesn't name one. Add its name, or its street address beginning with the house number."
    for page_sentence in (wording.SEARCH_HINT, wording.NOTE_EMPTY, wording.NOTE_TOO_LONG, wording.ASK_FOR_A_BUSINESS_ON_A_PAGE):
        assert "a street or a city" not in page_sentence
    # Since leg D4 the terminal has the search by address too (rule S18). It asks the page's own question, its old version is gone,
    # and its two other sentences ask for what the searches use.
    assert not hasattr(wording, "ASK_FOR_A_BUSINESS")
    assert wording.ASK_FOR_MORE == "Add the business's full name or its city"
    assert wording.GIVING_UP == ("I can't identify this business from what I have, so I won't guess. "
                                 "Run it again when you have its name and its city, or its street address beginning with the house number.")
    every = [value for name, value in vars(wording).items() if name.isupper() and isinstance(value, str)]
    assert not [text for text in every if "a street or a city" in text]   # no sentence anywhere still offers "a street or a city"


def test_the_summary_sentences_say_the_status_as_of_a_date_and_never_fill_a_gap():
    # Phase D, leg D2 (working rule S9). The example in the brief: "Active with the state as of Oct 7, 2026. Florida limited
    # liability company, on record since 2022."
    assert wording.long_day_text(date(2026, 10, 7)) == "Oct 7, 2026" and wording.long_day_text(date(2027, 1, 31)) == "Jan 31, 2027"
    assert [wording.long_day_text(date(2026, month, 1))[:3] for month in range(1, 13)] == ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    assert wording.summary_status_text("Active", date(2026, 10, 7)) == "Active with the state as of Oct 7, 2026."
    assert wording.summary_status_text("Inactive", date(2026, 11, 5)) == "Inactive with the state as of Nov 5, 2026."
    assert wording.summary_status_text(None, date(2026, 10, 7)) == "No status with the state is on record as of Oct 7, 2026."   # a missing status is not "Inactive"
    today = date(2026, 11, 25)
    llc = "Florida limited liability company (LLC)"
    assert wording.summary_record_text(llc, date(2022, 3, 14), today) == "Florida limited liability company (LLC), on record since 2022."
    assert wording.summary_record_text(llc, today, today) == "Florida limited liability company (LLC), on record since 2026."   # today is not the future
    assert wording.summary_record_text(llc, date(2120, 1, 1), today) == "Florida limited liability company (LLC), with a date on record in 2120, which is in the future."
    assert wording.summary_record_text(llc, None, today) == "Florida limited liability company (LLC), with no date on record."
    assert wording.summary_record_text(None, date(2022, 3, 14), today) == "Entity type not on record, on record since 2022."
    assert wording.summary_record_text("TRUST", None, today) == "TRUST, with no date on record."   # a code with no label is shown as the state writes it
    assert wording.HEADING_RECORDS == "The records behind this summary"
