"""test_search.py: offline tests for src/datum/search.py, the search the web app uses.

Nothing here opens a database. The retrieve step is played by FakeBackend, which holds a few
invented companies in memory, and the rerank step, the match level, the evidence and the tie
count run for real. The Jaro-Winkler function is checked against scores captured from Snowflake
(tests/fixtures/search/jarowinkler_pairs.csv, with its origin in the README next to it).

Every company below is invented. Run from ~/datum:  pytest
"""

import csv                                  # reads the fixture of name pairs
from dataclasses import replace             # a copy of a frozen dataclass with one field changed
from datetime import date, datetime, timedelta, timezone   # a company's dates and its UTC fetch time
from pathlib import Path                    # file paths

import pytest                               # the test runner; parametrize runs one test body over several cases

from datum.search import (
    ADDRESS_FETCH, CANDIDATE_POOL, COMPANY_COLUMNS, DIRECTIONS, IGNORED_STREET_WORDS, MOST_AT_AN_ADDRESS, STREET_TYPES, SUFFIX_PATTERN, Company, FakeBackend, PostgresBackend,
    RANK_ORDER, address_search, by_city_then_words, by_similarity_then_city, by_words_then_city, company_from_row, evidence, holds_every_word, jaro_winkler_similarity, match_level, name_key, rank, search,
    search_kind, search_pool, shortlist, street_matches, street_parts,
)

PAIRS = Path(__file__).parent / "fixtures" / "search" / "jarowinkler_pairs.csv"
FETCHED = datetime(2026, 10, 22, 19, 31, 31, tzinfo=timezone.utc)


def company(document_number, entity_name, city="JACKSONVILLE", status="A", address="1 INVENTED WAY"):
    """An invented company with the fields the search reads. The document numbers use a prefix (T) the state does not."""
    return Company(
        document_number=document_number, entity_name=entity_name, name_key=name_key(entity_name),
        status_code=status, filing_type="FLAL", file_date=date(2020, 1, 15),
        principal_address_1=address, principal_city=city, principal_state="FL", principal_zip="32256",
        published_on=date(2026, 10, 7), source_url="https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber",
        fetched_at=FETCHED, fetched_at_is_approximate=True,
    )


def read_pairs():
    with PAIRS.open(newline="") as handle:
        return [(row["left"], row["right"], int(row["snowflake_score"])) for row in csv.DictReader(handle)]


def test_the_fixture_has_every_pair():
    assert len(read_pairs()) == 61                                        # a fixture that lost rows would make the next test weaker without failing it


@pytest.mark.parametrize("left,right,snowflake_score", read_pairs())
def test_jaro_winkler_gives_the_score_snowflake_gives(left, right, snowflake_score):
    assert jaro_winkler_similarity(left, right) == snowflake_score


def test_jaro_winkler_details_each_have_a_pair_that_needs_them():
    # Each line fails if one detail of the function is changed. The expected numbers are Snowflake's, from the fixture.
    assert jaro_winkler_similarity("ABCDEF", "ABCXXX") == 66              # cut down, not rounded: the exact value is 66.67
    assert jaro_winkler_similarity("ABCDEF", "AXXXXX") == 44              # no bonus below 0.7: with the bonus it would be 50
    assert jaro_winkler_similarity("ABCDEF", "ABCDEX") == jaro_winkler_similarity("ABCDEX", "ABCDEF") == 93   # the bonus counts 4 letters, not 5
    assert jaro_winkler_similarity("acme roofing", "ACME ROOFING") == 100   # case does not count
    assert jaro_winkler_similarity("", "") == 0                           # two empty texts are not "the same name"
    assert jaro_winkler_similarity("A", "AB") == 85                       # exactly 0.85: floating-point arithmetic would give 84


def test_name_key_simplifies_a_name_the_way_the_mart_does():
    assert name_key("Acme, L.L.C.") == "ACME L L C"
    assert name_key("  ferguson   a/c & refrigeration ") == "FERGUSON A C REFRIGERATION"
    assert name_key("...") == ""


def test_rank_orders_by_similarity_then_city_then_document_number():
    pool = [
        company("T00000000003", "ACME ROOFING LLC", city="ORLANDO"),
        company("T00000000002", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000001", "ACME ROOFING LLC", city="ORLANDO"),
        company("T00000000004", "ACME ROOFING AND SIDING INC", city="JACKSONVILLE"),
        company("T00000000005", "ZEBRA PAINTING INC", city="JACKSONVILLE"),
    ]
    ranked = rank(pool, "acme roofing", city="jacksonville", order=by_similarity_then_city)   # search version 1's order, the app's until leg D3
    assert [c.company.document_number for c in ranked] == [
        "T00000000002",                                                   # same similarity as 1 and 3, and in the given city
        "T00000000001", "T00000000003",                                   # then the document number decides
        "T00000000004",                                                   # a lower similarity loses to all three, although its city matches
        "T00000000005",
    ]
    assert [c.similarity for c in ranked] == [95, 95, 95, 88, 56]
    assert [c.city_match for c in ranked] == [True, False, False, True, True]


def test_rank_orders_by_every_word_then_city_then_similarity_then_document_number():
    # Working rule S2, which leg D1 built and leg D3 switched on (Phase D rule S13). rank() is called with NO order here, so this
    # is the order the app uses, and the test fails if RANK_ORDER goes back to search version 1's. Each company below is placed by a
    # different part of the rule. Version 1's order (similarity first, the city only to break an exact tie) puts T3 and T4 above
    # T2, and T6 above all of them.
    pool = [
        company("T00000000004", "ACME ROOFING LLC", city="ORLANDO"),               # every word, another city, similarity 95
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),          # every word, the city given, similarity 95
        company("T00000000003", "ACME ROOFING LLC", city="ORLANDO"),               # the same as T4: the document number decides
        company("T00000000002", "ACME ROOFING AND SIDING OF DUVAL INC", city="JACKSONVILLE"),   # every word, the city given, a long name: similarity 86
        company("T00000000006", "ACME ROOFINGS", city="ORLANDO"),                  # ROOFINGS is not the word ROOFING. Similarity 98, the highest here
        company("T00000000005", "ACME ROOFERS INC", city="JACKSONVILLE"),          # not every word, but the city given
    ]
    ranked = rank(pool, "acme roofing", city="jacksonville")
    assert ranked == rank(pool, "acme roofing", city="jacksonville", order=by_words_then_city)   # the app's order IS rule S2
    assert [c.company.document_number for c in ranked] == [
        "T00000000001",                                                   # 1 and 2: every word and the city. The higher similarity comes first
        "T00000000002",                                                   # the long name in the right city now beats the short names in Orlando
        "T00000000003", "T00000000004",                                   # every word, another city: equal in everything, so the document number decides
        "T00000000005",                                                   # not every word: the city given comes before ...
    ]
    assert rank(pool, "acme roofing", city="jacksonville", limit=None)[-1].company.document_number == "T00000000006"   # ... the highest similarity of all, which is last
    assert [c.every_word for c in ranked] == [True, True, True, True, False]
    assert [c.city_match for c in ranked] == [True, True, False, False, True]
    assert [c.similarity for c in ranked] == [95, 86, 95, 95, 92]
    assert [c.company.document_number for c in rank(pool, "acme roofing", city="jacksonville", order=by_similarity_then_city)][:2] == ["T00000000006", "T00000000001"]   # version 1's order, for contrast: the near-miss ROOFINGS first
    # The one variant rule S3 allows: the city before the words. T5, in the city without every word, moves above T3 and T4.
    swapped = rank(pool, "acme roofing", city="jacksonville", order=by_city_then_words)
    assert [c.company.document_number for c in swapped] == ["T00000000001", "T00000000002", "T00000000005", "T00000000003", "T00000000004"]


def test_a_long_legal_name_that_holds_the_typed_trade_name_ranks_above_a_shorter_namesake_elsewhere():
    # The shape of the failure Andres found on Nov 24, with invented companies: a short trade name and a city.
    pool = [
        company("T00000000001", "Q PIZZA WP LLC", city="WINTER PARK", status="I"),             # a short name: similarity first would put it on top
        company("T00000000002", "Q PIZZA DURBIN, LLC", city="SAINT JOHNS"),
        company("T00000000003", "Q PIZZA LAKE BUENA VISTA LLC", city="ORLANDO"),               # the one in the city given, with the longest name
    ]
    ranked = rank(pool, "Q Pizza", city="Orlando")                         # no order passed: the app's own, which since leg D3 is rule S2 (rule S13)
    assert [c.company.document_number for c in ranked] == ["T00000000003", "T00000000001", "T00000000002"]
    assert ranked[0].similarity < ranked[1].similarity and ranked[0].similarity < ranked[2].similarity   # it is first with the LOWEST similarity of the three
    # Status never moves a company. With no city given, the inactive company keeps the place its name gives it, which is first.
    assert [c.company.document_number for c in rank(pool, "Q Pizza")] == ["T00000000001", "T00000000002", "T00000000003"]
    assert [c.company.document_number for c in rank(pool, "Q Pizza", city="Orlando", order=by_similarity_then_city)][0] == "T00000000001"   # version 1's order: the short name first, as on Nov 24
    active_twin = [company("T00000000001", "Q PIZZA WP LLC", status="I"), company("T00000000002", "Q PIZZA WP LLC", status="A")]
    assert [c.company.document_number for c in rank(active_twin, "Q Pizza")] == ["T00000000001", "T00000000002"]   # the inactive one is not pushed below its active twin


def test_every_word_compares_whole_words_and_leaves_legal_suffixes_out_of_both_names():
    assert holds_every_word("V PIZZA", "V PIZZA LAKE BUENA VISTA LLC") is True
    assert holds_every_word("V PIZZA", "VA PIZZA LLC") is False            # V is not the word VA
    assert holds_every_word("ACME ROOFING", "ACME ROOFINGS") is False     # nor is ROOFING the word ROOFINGS
    assert holds_every_word("PIZZA V", "V PIZZA DURBIN LLC") is True      # the order of the words does not count
    assert holds_every_word("ACME ROOFING INC", "ACME ROOFING LLC") is True   # INC and LLC are legal suffixes: neither is a word of the name
    assert holds_every_word("ACME CO ROOFING", "ACME ROOFING LLC") is False   # CO in the MIDDLE of what was typed is a word like any other
    assert holds_every_word("LLC", "ACME ROOFING LLC") is False and holds_every_word("LLC", "LLC") is True   # a name that is only a suffix keeps its word
    assert holds_every_word("", "ACME ROOFING LLC") is False              # nothing typed holds nothing
    one = rank([company("T00000000001", "ACME ROOFING LLC")], "acme roofing")[0]
    assert by_words_then_city(one) == (False, True, -95, "T00000000001") and by_city_then_words(one) == (True, False, -95, "T00000000001")   # the two sort keys themselves
    assert by_similarity_then_city(one) == (-95, True, "T00000000001")     # search version 1's key, kept for the evaluation
    assert RANK_ORDER is by_words_then_city                               # Phase D rule S13: the app's order is rule S2


def test_city_is_a_tie_break_and_never_a_filter():
    pool = [company("T00000000001", "ACME ROOFING LLC", city="TAMPA")]
    (only,) = rank(pool, "acme roofing", city="jacksonville")             # the company in another city is still returned
    assert only.city_match is False
    assert rank(pool, "acme roofing")[0].city_match is False              # no city given: nothing can match it


def test_city_matches_on_the_start_of_the_registered_city():
    pool = [company("T00000000001", "HUGHES FINANCIAL PARTNERS INC", city="Ponte Vedra Beach")]
    assert rank(pool, "hughes financial", city="ponte vedra")[0].city_match is True
    assert rank(pool, "hughes financial", city="vedra")[0].city_match is False
    assert rank([company("T00000000002", "X LLC", city=None)], "x", city="tampa")[0].city_match is False   # a company with no city on record


def test_rank_keeps_the_best_five():
    pool = [company(f"T0000000000{n}", "ACME ROOFING LLC") for n in range(9)]
    assert len(rank(pool, "acme roofing")) == 5
    assert len(rank(pool, "acme roofing", limit=3)) == 3


def test_exact_name_ignores_trailing_legal_suffixes_on_both_sides():
    pool = [
        company("T00000000001", "SADLER HOLDINGS, INC."),
        company("T00000000002", "SADLER HOLDINGS GROUP, INC."),
        company("T00000000003", "SADLER HOLDINGS CO., L.L.C."),
    ]
    by_number = {c.company.document_number: c for c in rank(pool, "Sadler Holdings Inc")}
    assert by_number["T00000000001"].exact_name is True
    assert by_number["T00000000002"].exact_name is False                  # GROUP is part of the name, not a legal suffix
    assert by_number["T00000000003"].exact_name is True                   # CO and L L C are both removed
    # What wording.NAME_IGNORING tells a contractor has to be what happens here, both ways.
    spaced = {c.company.document_number: c for c in rank([company("T00000000004", "A.B.C. ROOFING, LLC"), company("T00000000005", "ABC ROOFING LLC")], "a b c roofing")}
    assert spaced["T00000000004"].exact_name is True                      # capitals ignored, and each full stop read as a space
    assert spaced["T00000000005"].exact_name is False                     # A B C is not ABC: a space is kept, it is not ignored


def test_a_city_is_compared_by_its_spelling_and_the_reason_says_so():
    # "St. Augustine" against ST AUGUSTINE: the full stop makes the comparison fail. The reason may not then say the company is in another city.
    found = rank([company("T00000000001", "ACME ROOFING LLC", city="ST AUGUSTINE")], "Acme Roofing", "St. Augustine")[0]
    assert found.city_match is False
    reasons = evidence(found, city_given=True)
    assert reasons[1] == "principal city on record is ST AUGUSTINE, and that spelling does not begin with the city you gave"
    assert not [reason for reason in reasons if "not the city you gave" in reason]


def test_search_asks_the_backend_for_a_pool_and_reranks_it():
    backend = FakeBackend([company("T00000000002", "ZEBRA PAINTING INC"), company("T00000000001", "ACME ROOFING LLC")])
    found = search(backend, "Acme Roofing")
    assert backend.calls == [("ACME ROOFING", CANDIDATE_POOL)]            # the simplified name, and the pool size
    assert [c.company.document_number for c in found] == ["T00000000001", "T00000000002"]   # the backend's order does not survive the rerank


def test_a_name_with_nothing_to_search_for_returns_nothing_and_asks_nobody():
    backend = FakeBackend([company("T00000000001", "ACME ROOFING LLC")])
    assert search(backend, " ... ") == []
    assert backend.calls == []                                            # an empty key would match the whole table


def test_match_level_follows_the_three_rules():
    # Working rule S4: a level never depends on the order of the candidates. These are the four companies and the five expected
    # levels this test has had since leg C2. They are looked up by document number, so the test holds under any order, and the
    # last lines run it under rule S2 and its variant too.
    by_number = {c.company.document_number: c for c in rank([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000002", "ACME ROOFING INC", city="TAMPA"),
        company("T00000000003", "ACME ROOFING AND SIDING INC", city="JACKSONVILLE"),
        company("T00000000004", "ACME ROOFERS OF TAMPA INC", city="TAMPA"),
    ], "acme roofing", city="jacksonville")}
    exact_in_city, exact_elsewhere, similar_in_city, similar_elsewhere = (by_number[f"T0000000000{n}"] for n in (1, 2, 3, 4))
    assert (exact_in_city.exact_name, exact_elsewhere.exact_name, similar_in_city.exact_name, similar_elsewhere.exact_name) == (True, True, False, False)
    assert match_level(exact_in_city, city_given=True) == "Strong"        # the same name and the city agrees
    assert match_level(exact_elsewhere, city_given=True) == "Likely"      # the same name, another city
    assert match_level(similar_in_city, city_given=True) == "Likely"      # a similar name, the right city
    assert match_level(similar_elsewhere, city_given=True) == "Possible"  # only a similar name
    assert match_level(exact_elsewhere, city_given=False) == "Strong"     # no city was given, so there is no city to disagree
    # Holding every typed word is a reason for a company's PLACE and never for its level. This company holds both words, is in
    # another city and has a longer name, and it is still only Possible.
    longer = rank([company("T00000000005", "ACME ROOFING AND SIDING INC", city="TAMPA")], "acme roofing", city="jacksonville")[0]
    assert longer.every_word is True and match_level(longer, city_given=True) == "Possible"
    for order in (by_words_then_city, by_city_then_words):
        again = {c.company.document_number: match_level(c, city_given=True) for c in rank([
            company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"), company("T00000000002", "ACME ROOFING INC", city="TAMPA"),
            company("T00000000003", "ACME ROOFING AND SIDING INC", city="JACKSONVILLE"), company("T00000000004", "ACME ROOFERS OF TAMPA INC", city="TAMPA"),
        ], "acme roofing", city="jacksonville", order=order)}
        assert again == {"T00000000001": "Strong", "T00000000002": "Likely", "T00000000003": "Likely", "T00000000004": "Possible"}


def test_evidence_says_what_the_level_rests_on():
    exact, similar = rank([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000002", "ACME ROOFING AND SIDING INC", city="TAMPA"),
    ], "acme roofing", city="jacksonville")
    assert evidence(exact, city_given=True) == ["name matches (ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space)", "principal city on record begins with the city you gave", "ACTIVE"]
    assert evidence(similar, city_given=True) == ["name is similar (88/100)", "principal city on record is TAMPA, and that spelling does not begin with the city you gave", "ACTIVE"]
    assert evidence(similar, city_given=False) == ["name is similar (88/100)", "ACTIVE"]   # no city given: the city is not mentioned


def test_evidence_ends_with_the_status_of_an_active_company_and_never_guesses_one():
    active, inactive, unknown = (
        rank([company("T00000000001", "ACME ROOFING LLC", status=status)], "acme roofing")[0] for status in ("A", "I", None)
    )
    assert evidence(active, city_given=False)[-1] == "ACTIVE"
    assert evidence(inactive, city_given=False)[-1] == "INACTIVE with the state"   # as it has been since October: a report's line and the terminal's question keep it
    assert evidence(unknown, city_given=False)[-1] == "status not on record"   # a missing status is not "inactive" (CLAUDE.md rule 3)
    # Working rule S10 (leg D2): a SHORTLIST marks an inactive company beside its name, and so asks for the reasons without that status.
    reasons = evidence(inactive, city_given=False, status_marked=True)
    assert len(reasons) == 1 and reasons[0].startswith("name matches (") and not [reason for reason in reasons if "nactive" in reason or "NACTIVE" in reason]
    assert len(evidence(inactive, city_given=True, status_marked=True)) == 2   # the name and the city, and no status
    assert evidence(active, city_given=False, status_marked=True)[-1] == "ACTIVE"   # only an INACTIVE company's status is left out: nothing marks the others
    assert evidence(unknown, city_given=False, status_marked=True)[-1] == "status not on record"


def test_evidence_does_not_print_a_missing_city():
    (no_city,) = rank([company("T00000000001", "ACME ROOFING LLC", city=None)], "acme roofing", city="tampa")
    assert evidence(no_city, city_given=True)[1] == "no principal city on record for this company"


def test_a_tie_at_the_top_level_is_counted():
    # Working rule W7: when more than one company shares the top level, the shortlist has to say so.
    ranked = rank([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000002", "ACME ROOFING INC", city="TAMPA"),
        company("T00000000003", "ACME ROOFING AND SIDING INC", city="TAMPA"),
    ], "acme roofing")
    listed = shortlist(ranked, city_given=False)
    assert listed.levels == ("Strong", "Strong", "Possible")
    assert listed.tied_at_top == 2                                        # two companies are equally good answers


def test_an_exact_name_company_that_misses_the_list_is_still_counted_in_the_tie():
    # The first review round of leg C2 found this case. Five other companies outrank a second exact-name company, so it is not
    # among the five shown, and a count over those five alone would report no tie. All seven hold both typed words and are in the
    # city given, so rule S2 orders them by similarity, as search version 1 did.
    backend = FakeBackend([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),           # exact name, similarity 95: fifth by rank
        company("T00000000002", "ACME ROOFING CORPORATION", city="JACKSONVILLE"),   # exact name, similarity 90: sixth by rank
        company("T00000000003", "ACME ROOFING 3", city="JACKSONVILLE"),             # 97
        company("T00000000004", "ACME ROOFING 1", city="JACKSONVILLE"),             # 97
        company("T00000000005", "ACME ROOFING 2", city="JACKSONVILLE"),             # 97
        company("T00000000006", "ACME ROOFING FL", city="JACKSONVILLE"),            # 96
    ])
    listed = shortlist(search_pool(backend, "Acme Roofing", city="Jacksonville"), city_given=True)
    assert (listed.top_level, listed.tied_at_top, listed.tied_not_shown) == ("Strong", 2, 1)   # two share the name and city, and one is not listed
    assert listed.levels == ("Likely", "Likely", "Likely", "Likely", "Strong")   # rank order (rule S12): the exact name is fifth, and it is shown fifth
    assert listed.candidates[-1].company.document_number == "T00000000001" and listed.lower_level_above_higher is True
    assert [c.company.document_number for c in listed.not_shown] == ["T00000000002"]


def test_the_shortlist_shows_exactly_the_five_the_evaluation_scores():
    # The second review round of leg C2 found that levelling the whole pool let weak names in the right city push out better-ranked
    # companies. Nobody is brought in from further down the pool: the list is the first five by rank, in that order (rule S12).
    backend = FakeBackend(
        [company(f"T0000000001{n}", f"ACME ROOFING {n}", city="TAMPA") for n in range(4)]          # both typed words, another city: Possible
        + [company(f"T0000000002{n}", f"ACME ROOFERS OF JAX {n}", city="JACKSONVILLE") for n in range(6)]   # weaker names, right city: Likely
    )
    scored = search(backend, "Acme Roofing", city="Jacksonville")
    listed = shortlist(search_pool(backend, "Acme Roofing", city="Jacksonville"), city_given=True)
    assert [c.company.document_number for c in listed.candidates] == [c.company.document_number for c in scored]   # the same five, in the same order
    assert listed.levels == ("Possible", "Possible", "Possible", "Possible", "Likely")   # one Likely company fits. The other five do not push anybody out
    assert (listed.top_level, listed.tied_at_top, listed.tied_not_shown) == ("Likely", 1, 0)


def test_a_tie_below_strong_is_counted_among_the_candidates_shown_only():
    # With no exact-name match, a count over the whole pool would be the size of the pool, which says nothing about the companies.
    pool = rank([company(f"T00000000{n:03d}", f"ACME ROOFERS {n}") for n in range(40)], "acme roofing", limit=None)
    listed = shortlist(pool, city_given=False)
    assert (listed.top_level, listed.tied_at_top, listed.tied_not_shown) == ("Possible", 5, 0)


def test_a_tie_wider_than_the_shortlist_is_counted_in_full():
    pool = rank([company(f"T0000000000{n}", "ACME ROOFING LLC") for n in range(8)], "acme roofing", limit=None)
    listed = shortlist(pool, city_given=False)
    assert len(listed.candidates) == 5
    assert (listed.tied_at_top, listed.tied_not_shown) == (8, 3)          # five are shown, all eight are counted, three are not listed


def test_an_exact_name_company_outside_the_list_makes_the_top_level_strong_even_when_none_is_shown():
    backend = FakeBackend(
        [company(f"T0000000001{n}", f"ACME ROOFING {n}", city="TAMPA") for n in range(5)]          # 97 each: the five shown
        + [company("T00000000001", "ACME ROOFING CORPORATION", city="TAMPA")]                      # exact name, 90: sixth
    )
    listed = shortlist(search_pool(backend, "Acme Roofing"), city_given=False)
    assert listed.levels == ("Possible",) * 5
    assert (listed.top_level, listed.tied_at_top, listed.tied_not_shown) == ("Strong", 1, 1)
    (unlisted,) = listed.not_shown                                        # the company itself is carried, not only a count of it
    assert unlisted.company.document_number == "T00000000001"
    assert unlisted.company.source_url.startswith("https://") and unlisted.company.fetched_at == FETCHED   # so a page can name it AND cite it


def test_every_company_counted_in_a_tie_can_be_reached_from_the_shortlist():
    # The third review round found that the count covered companies the shortlist did not hold: a number with no source behind it.
    pool = rank([company(f"T0000000000{n}", "ACME ROOFING LLC") for n in range(8)], "acme roofing", limit=None)
    listed = shortlist(pool, city_given=False)
    strong_shown = [c for c, level in zip(listed.candidates, listed.levels) if level == listed.top_level]
    reachable = {c.company.document_number for c in strong_shown} | {c.company.document_number for c in listed.not_shown}
    assert len(reachable) == listed.tied_at_top == 8
    assert [c.company.document_number for c in listed.not_shown] == ["T00000000005", "T00000000006", "T00000000007"]   # in rank order


def test_one_candidate_at_the_top_level_is_not_a_tie():
    ranked = rank([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000002", "ACME ROOFING INC", city="TAMPA"),
    ], "acme roofing", city="jacksonville")
    listed = shortlist(ranked, city_given=True)
    assert listed.levels == ("Strong", "Likely")
    assert listed.tied_at_top == 1


def test_a_tie_among_possible_matches_is_still_a_tie():
    ranked = rank([company("T00000000001", "ACME ROOFERS INC"), company("T00000000002", "ACME ROOFS INC")], "acme roofing")
    assert shortlist(ranked, city_given=False).tied_at_top == 2           # the best level present is Possible, and two share it


def test_the_shortlist_shows_its_companies_in_rank_order_each_with_its_level():
    # Phase D rule S12 (leg D3). Until then the five were re-sorted with the best level first, so this list read T3, T1, T2 and the
    # company at the top of a page was not always the first by rank. This test fails on that order.
    ranked = rank([
        company("T00000000001", "ACME ROOFING AND SIDING INC", city="JACKSONVILLE"),   # similarity 88, right city: Likely
        company("T00000000002", "ACME ROOFINGS", city="TAMPA"),                        # similarity 98, wrong city: Possible
        company("T00000000003", "ACME ROOFING LLC", city="TAMPA"),                     # similarity 95, exact name, wrong city: Likely
    ], "acme roofing", city="jacksonville", order=by_similarity_then_city)
    assert [c.company.document_number for c in ranked] == ["T00000000002", "T00000000003", "T00000000001"]   # rank order: by similarity
    listed = shortlist(ranked, city_given=True)
    assert [c.company.document_number for c in listed.candidates] == ["T00000000002", "T00000000003", "T00000000001"]   # the same order on the list
    assert listed.levels == ("Possible", "Likely", "Likely")              # each company keeps its own level beside it
    assert (listed.top_level, listed.tied_at_top) == ("Likely", 2)        # the BEST level on the list, and not the first card's
    assert listed.lower_level_above_higher is True                        # a Possible stands above a Likely, so a page says the list is in search order
    in_level_order = shortlist(ranked[1:], city_given=True)               # Likely, Likely: nothing stands above a better level
    assert in_level_order.levels == ("Likely", "Likely") and in_level_order.lower_level_above_higher is False


FIVE_OUT_OF_LEVEL_ORDER = [
    company("T00000000001", "ACME ROOFING AND SIDING INC", city="TAMPA"),          # holds every typed word, another city, similarity 88: Possible
    company("T00000000002", "ACME ROOFERS INC", city="JACKSONVILLE"),              # a near-miss name in the city given, 92: Likely
    company("T00000000003", "ACME ROOFER INC", city="JACKSONVILLE"),               # the same, 93: Likely
    company("T00000000004", "ACME ROOFINGS", city="TAMPA"),                        # a near-miss name elsewhere, 98: Possible
    company("T00000000005", "ACME ROOFERS OF TAMPA INC", city="TAMPA"),            # a near-miss name elsewhere, 82: Possible
]
# Five invented companies whose levels come out Possible, Likely, Likely, Possible, Possible in rank order, typed as "acme roofing" in
# Jacksonville. They do so under BOTH orders, with a different company on top: by similarity T4 (98) leads, and under rule S2 T1
# leads, because it is the only one that holds both typed words.


@pytest.mark.parametrize("order,first", [(by_similarity_then_city, "T00000000004"), (by_words_then_city, "T00000000001")])
def test_a_tie_reads_the_best_level_on_the_list_when_a_lower_level_is_shown_first(order, first):
    # Rule S12 keeps rule W7's count: with no Strong company anywhere, the tie is counted at the best level AMONG THE FIVE. The first
    # card here is Possible. A count that read the first card's level would say "3 companies ... at the level Possible".
    pool = rank(FIVE_OUT_OF_LEVEL_ORDER, "acme roofing", city="jacksonville", limit=None, order=order)
    listed = shortlist(pool, city_given=True)
    assert listed.candidates[0].company.document_number == first
    assert listed.levels == ("Possible", "Likely", "Likely", "Possible", "Possible")
    assert (listed.top_level, listed.tied_at_top, listed.tied_not_shown) == ("Likely", 2, 0)
    assert listed.lower_level_above_higher is True


def test_an_empty_shortlist_has_no_tie():
    empty = shortlist([], city_given=False)
    assert (empty.candidates, empty.top_level, empty.tied_at_top, empty.not_shown) == ((), None, 0, ())


def test_the_postgres_query_sends_what_was_typed_as_a_value_never_as_sql():
    # Nothing typed by a contractor may be pasted into the SQL text. The query holds four placeholders and no other gap. Its only
    # quotes are the two fixed pairs of rule S11's term: one holds nothing and one holds a single space.
    sql = PostgresBackend.NEAREST_SQL
    assert [sql.count(f"%({name})s") for name in ("key", "suffixes", "words", "limit")] == [2, 1, 1, 1]
    assert sql.count("%(") == 5 and "{" not in sql                        # no placeholder besides those five uses, and no gap left by an f-string
    assert sql.count("'") == 4 and "%(suffixes)s, '')" in sql and "' ') @>" in sql


def test_the_postgres_query_finds_names_in_the_narrow_table_and_reads_every_company_from_company_search():
    # The narrow table has no source address and no fetch time, so nothing a Company holds may be read from it.
    sql = PostgresBackend.NEAREST_SQL
    subquery = sql[sql.index("(select"):sql.index(") as nearest")]
    assert subquery.startswith("(select document_number from company_search_names where %(key)s <%% name_key ")   # only the number leaves the narrow table
    assert subquery.endswith("limit %(limit)s")                           # the pool is cut BEFORE the join, so at most `limit` full rows are fetched
    assert sql.endswith(") as nearest join company_search as c using (document_number)")
    selected = sql[len("select "):sql.index(" from (")].split(", ")
    assert selected == ["c." + column for column in COMPANY_COLUMNS]      # every field, source_url and fetched_at included, comes from company_search


def test_the_first_step_keeps_the_names_that_hold_every_typed_word_before_the_nearest_names():
    # Phase D rule S11 (leg D3). The rule lives in the query, and no offline test can RUN a query, so its text is pinned word for
    # word, as the address query's is. Before leg D3 the ORDER BY began with the trigram distance, and this test fails on that text.
    # What the term DOES is measured on the real data in the leg report: it brought checked case 11's company from "not among 200" to 17th.
    sql = PostgresBackend.NEAREST_SQL
    assert sql == (
        "select " + ", ".join("c." + column for column in COMPANY_COLUMNS) + " "
        "from (select document_number from company_search_names "
        "where %(key)s <%% name_key "
        "order by not (string_to_array(regexp_replace(name_key, %(suffixes)s, ''), ' ') @> %(words)s::text[]), "
        "name_key <-> %(key)s, document_number "
        "limit %(limit)s) as nearest "
        "join company_search as c using (document_number)"
    )
    order_by = sql[sql.index("order by ") + len("order by "):sql.index(" limit %(limit)s")]
    assert order_by.index("@> %(words)s") < order_by.index("<-> %(key)s") < order_by.index("document_number")   # every word, THEN the nearest, then a fixed order
    # The two values the term reads are the ones holds_every_word() compares: the typed words with the legal endings left out, and
    # the one list of legal endings. A name that is nothing but a legal ending keeps its word, as it does in holds_every_word().
    conn = RecordingConnection()
    backend = PostgresBackend(conn)
    backend.nearest("V PIZZA LLC", 200)
    assert conn.asked[-1][1] == {"key": "V PIZZA", "limit": 200, "words": ["V", "PIZZA"], "suffixes": SUFFIX_PATTERN.pattern}
    backend.nearest("LLC", 200)
    assert conn.asked[-1][1]["words"] == ["LLC"]
    assert holds_every_word("V PIZZA LLC", "V PIZZA LAKE BUENA VISTA LLC") and not holds_every_word("V PIZZA LLC", "PIZZA VILLA INC")   # the Python rule the term copies


class RecordingConnection:
    """Stands in for a psycopg connection: it keeps everything it was asked and answers a search with one invented row."""

    def __init__(self):
        self.asked = []                                                   # every (sql, params), in order

    def execute(self, sql, params=None):
        self.asked.append((sql, params))
        return self

    def fetchall(self):
        c = company("T00000000001", "ACME ROOFING LLC")
        return [(c.document_number, c.entity_name, c.name_key, c.status_code, c.filing_type, c.file_date, c.principal_address_1,
                 c.principal_city, c.principal_state, c.principal_zip, c.published_on, c.source_url, c.fetched_at, c.fetched_at_is_approximate)]


def test_the_postgres_backend_passes_the_key_and_limit_as_parameters():
    conn = RecordingConnection()
    rows = PostgresBackend(conn).nearest("ACME'; DROP TABLE company_search; --", 200)
    sql, params = conn.asked[-1]
    assert params["key"] == "ACME'; DROP TABLE company_search; --" and params["limit"] == 200
    assert params["words"] == ["ACME';", "DROP", "TABLE", "company_search;", "--"]   # the typed words travel as a value too, whatever they hold
    assert "DROP TABLE" not in sql
    assert rows == [company("T00000000001", "ACME ROOFING LLC")]          # the columns map onto Company's fields in order


def test_the_postgres_backend_leaves_the_legal_suffix_out_of_the_index_lookup():
    conn = RecordingConnection()
    backend = PostgresBackend(conn)
    backend.nearest("ACME ROOFING CO LLC", 200)
    assert conn.asked[-1][1]["key"] == "ACME ROOFING"                     # LLC and CO are in millions of names and tell nothing apart
    backend.nearest("LLC", 200)
    assert conn.asked[-1][1]["key"] == "LLC"                              # a name that is only a suffix is sent as typed, never as an empty key


def test_the_postgres_backend_sets_its_three_settings_for_its_own_connection_only():
    conn = RecordingConnection()
    PostgresBackend(conn)
    assert [params for _, params in conn.asked] == [("0.75",), ("64MB",), ("UTC",)]
    assert all("set_config" in sql and "false" in sql for sql, _ in conn.asked)   # false = this session, not the whole server


def test_a_company_cannot_be_built_without_a_source_address_and_a_utc_fetch_time():
    # CLAUDE.md rule 3: a fact type that can be built without both is a bug in the type. One test per way to break it.
    good = company("T00000000001", "ACME ROOFING LLC")
    with pytest.raises(ValueError, match="full source address"):
        replace(good, source_url="")
    with pytest.raises(ValueError, match="full source address"):
        replace(good, source_url=None)
    with pytest.raises(ValueError, match="time-zone-aware UTC"):
        replace(good, fetched_at=datetime(2026, 10, 22, 19, 31, 31))                       # no time zone
    with pytest.raises(ValueError, match="time-zone-aware UTC"):
        replace(good, fetched_at=datetime(2026, 10, 22, 14, 31, 31, tzinfo=timezone(timedelta(hours=-5))))   # a zone that is not UTC
    with pytest.raises(ValueError, match="time-zone-aware UTC"):
        replace(good, fetched_at=None)


def test_a_fetch_time_that_arrives_in_local_time_is_converted_to_utc():
    # Postgres hands a moment back in the connection's zone. On the Mac that is Eastern time unless the connection asks for UTC.
    c = company("T00000000001", "ACME ROOFING LLC")
    eastern = FETCHED.astimezone(timezone(timedelta(hours=-5)))            # the same moment, written as 14:31 -05:00
    row = (c.document_number, c.entity_name, c.name_key, c.status_code, c.filing_type, c.file_date, c.principal_address_1,
           c.principal_city, c.principal_state, c.principal_zip, c.published_on, c.source_url, eastern, c.fetched_at_is_approximate)
    built = company_from_row(row)
    assert built.fetched_at == FETCHED and built.fetched_at.utcoffset() == timedelta(0)
    naive = row[:12] + (datetime(2026, 10, 22, 19, 31, 31),) + row[13:]
    with pytest.raises(ValueError, match="time-zone-aware UTC"):
        company_from_row(naive)                                           # a time with no zone is never guessed to be UTC


# --- The search by address (Phase D, leg D1; working rules S5 to S8) ---------------------------------

def test_a_street_is_cut_into_a_house_number_and_the_words_that_are_compared():
    assert street_parts("8586 palm pwwy") == ("8586", ("PALM", "PWWY"))   # the mistyped street type stays a word. Nothing has to match it
    assert street_parts("8586 Palm Pkwy.") == ("8586", ("PALM",))         # PKWY is a street type: left out
    assert street_parts("77 N. Quartz Rd") == ("77", ("QUARTZ",))   # a direction and a street type: both left out
    assert street_parts("12 US-1 N") == ("12", ("US", "1"))               # punctuation becomes a space, as it does in a name
    assert street_parts("123A Main Street, Suite 4") == ("123A", ("MAIN", "SUITE", "4"))   # a number with a letter is the whole house number. A suite is not ignored
    assert street_parts("115 SE 1st St") == ("115", ("SE", "1ST"))        # SE is not one of the four directions the rule lists
    for no_number in ("Race Track Rd", "race track rd 12", "PO Box 12", "One Main St", "", "   "):
        assert street_parts(no_number) == (None, ()), no_number           # a street that does not BEGIN with a digit has no house number here
    for numbered_street in ("4th st south", "1st ave", "2ND STREET N", "3rd Ave", "101st street", "22nd"):
        assert street_parts(numbered_street) == (None, ()), numbered_street   # 4TH is the street's name, not a house on it (rule S7). Round 1 of the review found this
    assert street_parts("12 4th st south") == ("12", ("4TH", "SOUTH"))           # the same street WITH a house number
    assert street_parts("4 th st") == ("4", ("TH",)) and street_parts("1 st") == ("1", ())   # a number standing alone is a house number, whatever follows it
    assert {"PKWY", "PARKWAY", "ST", "STREET", "AVE", "AVENUE", "RD", "ROAD", "BLVD", "DR", "DRIVE", "LN", "CT", "WAY", "CIR", "HWY"} <= STREET_TYPES   # the sixteen the brief names
    assert DIRECTIONS == {"N", "S", "E", "W"} and IGNORED_STREET_WORDS == STREET_TYPES | DIRECTIONS


def test_a_stored_street_matches_when_all_its_words_were_typed_whatever_the_street_type():
    typed = street_parts("8586 palm pwwy")[1]
    assert street_matches("PALM PKWY", typed) and street_matches("PALM PARKWAY", typed) and street_matches("N PALM AVE", typed)   # the type and the direction are ignored
    assert not street_matches("PALM BEACH PKWY", typed)                   # BEACH is a word of the stored street that was not typed
    assert not street_matches("PALMETTO PKWY", typed)                     # whole words are compared
    assert not street_matches("PALM PKWY STE 200", typed)                 # a suite on the record that was not typed is a miss: a suite is not a street type
    assert street_matches("PALM PKWY STE 200", street_parts("8586 palm pkwy ste 200")[1])
    assert not street_matches("", typed) and not street_matches("N ST", typed) and not street_matches("PKWY", typed)   # nothing left to compare matches nothing
    assert not street_matches("PALM PKWY", ())                            # and nothing typed matches nothing
    assert not street_matches("ZEBRA GLASS MEMORIAL HWY", street_parts("12 w zebra glass hwy")[1])   # one word of the stored street left out: a miss


def test_a_note_gets_the_name_search_the_address_search_or_a_question():
    # Working rules S5 and S7. Before leg D1 every note that named no business was asked for more, whatever its street.
    assert search_kind("", "8586 palm pwwy", False) == "address"          # no business, and the street begins with a house number
    assert search_kind("<UNKNOWN>", "8586 palm pwwy", False) == "address"   # what the extraction step puts in the name when there is none does not count
    assert search_kind("", "8586 palm pwwy", True) == "address"           # "specific", and no name at all: it names no business
    assert search_kind("   ", "8586 palm pwwy", True) == "address"
    assert search_kind("Pool", "Race Track Rd", False) == "ask"           # rule S7: a street with no house number still asks ("the pool guy off race track rd")
    assert search_kind("", "", False) == "ask" and search_kind("Pool", "", False) == "ask"
    assert search_kind("", "4th st south", False) == "ask" and search_kind("", "1st ave", False) == "ask"   # a numbered street is a street with no house number
    assert search_kind("", "12 parkway", False) == "ask" and search_kind("", "12", False) == "ask"   # a house number with no street name: nothing could be compared
    assert search_kind("Q Pizza", "12 made up ave", True) == "name"   # a note that names a business gets the name search, house number or not
    assert search_kind("V Pizza", "", True) == "name"


def at(document_number, name, address, city="ORLANDO", status="A"):
    return company(document_number, name, city=city, status=status, address=address)


AT_ONE_ADDRESS = [
    at("T00000000004", "QUARTZ TILE INC.", "8586 PALM PARKWAY", status="I"),
    at("T00000000002", "INVENTED HOLDINGS OF ORLANDO LLC", "8586 Palm Pkwy.", status="I"),
    at("T00000000001", "Q PIZZA LAKE BUENA VISTA LLC", "8586 PALM PKWY"),
    at("T00000000003", "ZEBRA GLASS OF TAMPA LLC", "8586 PALM RIVER RD", city="TAMPA"),   # the same number, another street
    at("T00000000005", "CORAL ELECTRIC LLC", "8587 PALM PKWY"),                           # the same street, the house next door
    at("T00000000006", "DUNE ROOFING LLC", "8586 PALM AVE", city="MIAMI"),                # the same number and street name in another city
]


def test_an_address_search_lists_the_active_companies_and_only_counts_the_inactive_ones():
    # Working rules S5 and S6, on the shape of Andres's case: one active company and two inactive ones at "8586 palm pwwy" in Orlando.
    backend = FakeBackend(AT_ONE_ADDRESS)
    found = address_search(backend, "8586 palm pwwy", "Orlando")
    assert [c.document_number for c in found.active] == ["T00000000001"]  # the one active company whose principal address this is
    assert [c.document_number for c in found.inactive] == ["T00000000002", "T00000000004"]   # carried, in document-number order, so that a page can count them
    assert (found.house_number, found.street_words, found.no_status, found.too_many) == ("8586", ("PALM", "PWWY"), (), False)
    assert backend.address_calls == [("8586", ("PALM", "PWWY"), ADDRESS_FETCH)] and backend.calls == []   # one lookup by house number, and no name search
    # With no city given, the company with the same number and street name in Miami matches too. Document-number order, whatever the city.
    assert [c.document_number for c in address_search(backend, "8586 palm pwwy").active] == ["T00000000001", "T00000000006"]
    assert address_search(backend, "8586 palm pwwy", "Tampa").active == ()   # a city that no match is in: the Tampa company is on another street
    assert [c.document_number for c in address_search(backend, "8587 palm parkway").active] == ["T00000000005"]   # the house number must be the same
    assert address_search(backend, "858 palm pkwy").active == () and address_search(backend, "8586 pkwy").active == ()   # a shorter number, and no street name


def test_an_address_search_is_in_document_number_order_and_status_never_reorders_it():
    backend = FakeBackend([at(f"T0000000000{n}", f"INVENTED CO {n} LLC", "12 MADE UP RD", status="I" if n in (8, 2) else "A") for n in (5, 8, 3, 9, 2, 1)])
    assert [c.document_number for c, _ in backend.at_house_number("12", ("MADE", "UP"), 1000)][:3] == ["T00000000005", "T00000000008", "T00000000003"]   # the backend hands them over UNSORTED
    found = address_search(backend, "12 made up road")
    assert [c.document_number for c in found.active] == ["T00000000001", "T00000000003", "T00000000005", "T00000000009"]   # address_search puts them in order
    assert [c.document_number for c in found.inactive] == ["T00000000002", "T00000000008"]
    unknown = FakeBackend([at("T00000000001", "INVENTED CO LLC", "12 MADE UP RD", status=None), at("T00000000002", "OTHER CO LLC", "12 MADE UP RD", status="X")])
    found = address_search(unknown, "12 made up rd")
    assert (found.active, found.inactive) == ((), ()) and [c.document_number for c in found.no_status] == ["T00000000001", "T00000000002"]   # no status is not "inactive"


def test_an_address_with_more_companies_than_a_page_may_list_lists_none():
    crowded = FakeBackend([at(f"T{n:011d}", f"INVENTED CO {n} LLC", "7 MAIL DROP WAY STE 300") for n in range(MOST_AT_AN_ADDRESS + 1)])
    found = address_search(crowded, "7 mail drop way ste 300")
    assert found.too_many is True and (found.active, found.inactive, found.no_status) == ((), (), ())
    exactly = FakeBackend(crowded.companies[:MOST_AT_AN_ADDRESS])
    assert address_search(exactly, "7 mail drop way ste 300").too_many is False and len(address_search(exactly, "7 mail drop way ste 300").active) == MOST_AT_AN_ADDRESS
    # When the database hands over as many rows as it was asked for, there may be more that were never looked at. No count can be trusted then.
    full = FakeBackend([at(f"T{n:011d}", f"INVENTED CO {n} LLC", "7 OTHER ST" if n else "7 MAIL DROP WAY") for n in range(ADDRESS_FETCH)])
    assert address_search(full, "7 mail drop way").too_many is True       # one real match, and a full hand-over: the answer is still "too many"
    assert address_search(FakeBackend(full.companies[:ADDRESS_FETCH - 1]), "7 mail drop way").too_many is False


def test_a_street_with_no_house_number_or_no_name_looks_nothing_up():
    numbered = at("T00000000009", "INVENTED CO ON FOURTH LLC", "4TH ST SOUTH")   # an address with no house number, on a numbered street
    backend = FakeBackend(AT_ONE_ADDRESS + [numbered])
    for street in ("palm pkwy", "8586", "8586 pkwy n", "", "4th st south", "4TH ST SOUTH"):
        found = address_search(backend, street)
        assert (found.active, found.inactive, found.too_many) == ((), (), False), street
    assert backend.address_calls == []                                    # the database was not asked at all


def test_the_address_query_sends_what_was_typed_as_values_and_reads_every_company_from_company_search():
    sql = PostgresBackend.AT_HOUSE_NUMBER_SQL
    assert [sql.count(f"%({name})s") for name in ("house_number", "allowed", "ignored", "limit")] == [1, 1, 1, 1] and "{" not in sql
    subquery = sql[sql.index("(select"):sql.index(") as found")]
    assert subquery.startswith("(select document_number, street_words from company_search_addresses where house_number = %(house_number)s ")
    assert subquery.endswith("order by document_number limit %(limit)s")  # the list is cut BEFORE the join, so at most `limit` full rows are fetched
    assert ") as found join company_search as c using (document_number)" in sql
    # The street rule inside the query, word for word. No offline test can RUN it, so its text is pinned: stored words are contained in
    # (<@) the allowed words, and are NOT all ignored words. Leg D1's report compares it with street_matches() on real rows.
    assert sql == (
        "select " + ", ".join("c." + column for column in COMPANY_COLUMNS) + ", found.street_words "
        "from (select document_number, street_words from company_search_addresses "
        "where house_number = %(house_number)s "
        "and string_to_array(street_words, ' ') <@ %(allowed)s::text[] "
        "and not (string_to_array(street_words, ' ') <@ %(ignored)s::text[]) "
        "order by document_number limit %(limit)s) as found "
        "join company_search as c using (document_number) "
        "order by c.document_number"
    )
    selected = sql[len("select "):sql.index(" from (")].split(", ")
    assert selected == ["c." + column for column in COMPANY_COLUMNS] + ["found.street_words"]   # every company field comes from company_search

    class AddressConnection(RecordingConnection):
        def fetchall(self):
            return [row + ("PALM PKWY",) for row in super().fetchall()]

    conn = AddressConnection()
    rows = PostgresBackend(conn).at_house_number("8586'; drop table company_search; --", ("PALM", "PWWY"), 1000)
    asked, params = conn.asked[-1]
    assert "drop table" not in asked and params["house_number"] == "8586'; drop table company_search; --" and params["limit"] == 1000
    assert params["ignored"] == sorted(IGNORED_STREET_WORDS) and params["allowed"] == ["PALM", "PWWY"] + sorted(IGNORED_STREET_WORDS)
    assert rows == [(company("T00000000001", "ACME ROOFING LLC"), "PALM PKWY")]   # the company, and its stored street for street_matches()
