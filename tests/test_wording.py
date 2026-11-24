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
    # With a city given, a same-name company in another city is not counted, so the sentence names the city.
    assert (wording.not_shown_text(0, False), wording.not_shown_text(0, True)) == ("", "")
    assert wording.not_shown_text(1, False) == "1 more company has this name (ignoring LLC/INC) and is not on this list."
    assert wording.not_shown_text(3, False) == "3 more companies have this name (ignoring LLC/INC) and are not on this list."
    assert wording.not_shown_text(1, True) == "1 more company has this name (ignoring LLC/INC) in the city you gave and is not on this list."
    assert wording.not_shown_text(2, True) == "2 more companies have this name (ignoring LLC/INC) in the city you gave and are not on this list."
    every = [value for name, value in vars(wording).items() if name.isupper() and isinstance(value, str)]
    assert not [text for text in every if "exactly this name" in text]    # "exactly" claimed more than the comparison does: it ignores the legal suffix


def test_the_identification_line_is_built_from_extracted_fields_and_leaves_out_an_empty_one():
    line = wording.identified_text("Acme Roofing", "", "", "Likely", ("name is similar (93/100)", "ACTIVE"), 0)
    assert line == 'from the business name "Acme Roofing" · match level Likely (name is similar (93/100); ACTIVE) · chosen by the user from a shortlist.'
    full = wording.identified_text("Acme Roofing", "Tampa", "Bay St", "Strong", ("city matches",), 2)
    assert 'the business name "Acme Roofing", the city "Tampa", the street "Bay St"' in full and full.endswith(" 2 other companies matched equally well.")
    likely = wording.identified_text("Acme Roofing", "Tampa", "", "Likely", ("city matches",), 2)
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
    assert wording.SHORTLIST_TIE == "These look about equally likely. Is it one of these? A street or a city would help tell them apart."
    assert wording.SEARCH_UNAVAILABLE == "The search is unavailable right now, so no company is shown. Try again in a few minutes."
    assert wording.IDENTIFIED_BY_NUMBER == "opened by its document number, so no match level applies."


def test_the_two_company_record_flags_use_the_plans_wording_word_for_word():
    # docs/mvp_plan_nov8.md, section 4, the first two rows of the flags table.
    assert wording.FLAG_INACTIVE_TEXT == "Inactive with the Florida Division of Corporations"
    assert wording.FLAG_INACTIVE_CAVEAT == "Data as of the snapshot date; changes since then aren't covered until the events file is loaded"
    assert wording.FLAG_NEW_TEXT.format(day="2026-03-14") == "On record since 2026-03-14" and wording.FLAG_NEW_CAVEAT == "May be an effective date"
    assert wording.DISCLAIMER == "Sourced public-record facts, not advice. Verify on the official record before relying on them."
