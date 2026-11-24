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
    CANDIDATE_POOL, COMPANY_COLUMNS, Company, FakeBackend, PostgresBackend, company_from_row, evidence, jaro_winkler_similarity, match_level, name_key, rank,
    search, search_pool, shortlist,
)

PAIRS = Path(__file__).parent / "fixtures" / "search" / "jarowinkler_pairs.csv"
FETCHED = datetime(2026, 10, 22, 19, 31, 31, tzinfo=timezone.utc)


def company(document_number, entity_name, city="JACKSONVILLE", status="A"):
    """An invented company with the fields the search reads. The document numbers use a prefix (T) the state does not."""
    return Company(
        document_number=document_number, entity_name=entity_name, name_key=name_key(entity_name),
        status_code=status, filing_type="FLAL", file_date=date(2020, 1, 15),
        principal_address_1="1 INVENTED WAY", principal_city=city, principal_state="FL", principal_zip="32256",
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
    ranked = rank(pool, "acme roofing", city="jacksonville")
    assert [c.company.document_number for c in ranked] == [
        "T00000000002",                                                   # same similarity as 1 and 3, and in the given city
        "T00000000001", "T00000000003",                                   # then the document number decides
        "T00000000004",                                                   # a lower similarity loses to all three, although its city matches
        "T00000000005",
    ]
    assert [c.similarity for c in ranked] == [95, 95, 95, 88, 56]
    assert [c.city_match for c in ranked] == [True, False, False, True, True]


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
    exact_in_city, exact_elsewhere, similar_in_city, similar_elsewhere = rank([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000002", "ACME ROOFING INC", city="TAMPA"),
        company("T00000000003", "ACME ROOFING AND SIDING INC", city="JACKSONVILLE"),
        company("T00000000004", "ACME ROOFERS OF TAMPA INC", city="TAMPA"),
    ], "acme roofing", city="jacksonville")
    assert (exact_in_city.exact_name, exact_elsewhere.exact_name, similar_in_city.exact_name, similar_elsewhere.exact_name) == (True, True, False, False)
    assert match_level(exact_in_city, city_given=True) == "Strong"        # the same name and the city agrees
    assert match_level(exact_elsewhere, city_given=True) == "Likely"      # the same name, another city
    assert match_level(similar_in_city, city_given=True) == "Likely"      # a similar name, the right city
    assert match_level(similar_elsewhere, city_given=True) == "Possible"  # only a similar name
    assert match_level(exact_elsewhere, city_given=False) == "Strong"     # no city was given, so there is no city to disagree


def test_evidence_says_what_the_level_rests_on():
    exact, similar = rank([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),
        company("T00000000002", "ACME ROOFING AND SIDING INC", city="TAMPA"),
    ], "acme roofing", city="jacksonville")
    assert evidence(exact, city_given=True) == ["name matches exactly (ignoring LLC/INC)", "city matches", "ACTIVE"]
    assert evidence(similar, city_given=True) == ["name is similar (88/100)", "registered in TAMPA, not the city you gave", "ACTIVE"]
    assert evidence(similar, city_given=False) == ["name is similar (88/100)", "ACTIVE"]   # no city given: the city is not mentioned


def test_evidence_ends_with_the_status_and_never_guesses_one():
    # The status is what tells an active company from an inactive namesake on a shortlist, so it is always the last reason.
    active, inactive, unknown = (
        rank([company("T00000000001", "ACME ROOFING LLC", status=status)], "acme roofing")[0] for status in ("A", "I", None)
    )
    assert evidence(active, city_given=False)[-1] == "ACTIVE"
    assert evidence(inactive, city_given=False)[-1] == "INACTIVE with the state"
    assert evidence(unknown, city_given=False)[-1] == "status not on record"   # a missing status is not "inactive" (CLAUDE.md rule 3)


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
    # The first review round of leg C2 found this case. Five near-misses outrank a second exact-name company by
    # similarity, so it is not among the five shown, and a count over those five alone would report no tie.
    backend = FakeBackend([
        company("T00000000001", "ACME ROOFING LLC", city="JACKSONVILLE"),           # exact name, similarity 95: fifth by rank
        company("T00000000002", "ACME ROOFING CORPORATION", city="JACKSONVILLE"),   # exact name, similarity 90: sixth by rank
        company("T00000000003", "ACME ROOFINGS", city="TAMPA"),                     # 98
        company("T00000000004", "ACME ROOFING 1", city="TAMPA"),                    # 97
        company("T00000000005", "ACME ROOFING 2", city="TAMPA"),                    # 97
        company("T00000000006", "ACME ROOFING FL", city="TAMPA"),                   # 96
    ])
    listed = shortlist(search_pool(backend, "Acme Roofing", city="Jacksonville"), city_given=True)
    assert (listed.top_level, listed.tied_at_top, listed.tied_not_shown) == ("Strong", 2, 1)   # two share the name and city, and one is not listed
    assert listed.levels == ("Strong", "Possible", "Possible", "Possible", "Possible")


def test_the_shortlist_shows_exactly_the_five_the_evaluation_scores():
    # The second review round found that levelling the whole pool let weak names in the right city push out the
    # best-ranked company. City is a tie-break and never a filter, so nobody is brought in from further down the pool.
    backend = FakeBackend(
        [company("T00000000001", "ACME ROOFINGS", city="TAMPA")]                                    # 98: the best by rank, in another city
        + [company(f"T0000000001{n}", f"ACME ROOFING {n}", city="TAMPA") for n in range(4)]        # 97 each
        + [company(f"T0000000002{n}", f"ACME ROOFERS OF JAX {n}", city="JACKSONVILLE") for n in range(6)]   # weaker names, right city: Likely
    )
    scored = search(backend, "Acme Roofing", city="Jacksonville")
    listed = shortlist(search_pool(backend, "Acme Roofing", city="Jacksonville"), city_given=True)
    assert {c.company.document_number for c in listed.candidates} == {c.company.document_number for c in scored}
    assert "T00000000001" in {c.company.document_number for c in listed.candidates}   # the best-ranked company is on the list
    assert listed.top_level == "Possible" and listed.tied_not_shown == 0


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


def test_the_shortlist_shows_the_best_level_first_and_keeps_rank_order_inside_a_level():
    ranked = rank([
        company("T00000000001", "ACME ROOFING AND SIDING INC", city="JACKSONVILLE"),   # similarity 88, right city: Likely
        company("T00000000002", "ACME ROOFINGS", city="TAMPA"),                        # similarity 98, wrong city: Possible
        company("T00000000003", "ACME ROOFING LLC", city="TAMPA"),                     # similarity 95, exact name, wrong city: Likely
    ], "acme roofing", city="jacksonville")
    assert [c.company.document_number for c in ranked] == ["T00000000002", "T00000000003", "T00000000001"]   # rank order: by similarity
    listed = shortlist(ranked, city_given=True)
    assert [c.company.document_number for c in listed.candidates] == ["T00000000003", "T00000000001", "T00000000002"]
    assert listed.levels == ("Likely", "Likely", "Possible")


def test_an_empty_shortlist_has_no_tie():
    empty = shortlist([], city_given=False)
    assert (empty.candidates, empty.top_level, empty.tied_at_top, empty.not_shown) == ((), None, 0, ())


def test_the_postgres_query_sends_what_was_typed_as_a_value_never_as_sql():
    # Nothing typed by a contractor may be pasted into the SQL text. The query holds two placeholders and no other gap.
    sql = PostgresBackend.NEAREST_SQL
    assert sql.count("%(key)s") == 2 and sql.count("%(limit)s") == 1
    assert "{" not in sql and "'" not in sql


def test_the_postgres_query_finds_names_in_the_narrow_table_and_reads_every_company_from_company_search():
    # The narrow table has no source address and no fetch time, so nothing a Company holds may be read from it.
    sql = PostgresBackend.NEAREST_SQL
    subquery = sql[sql.index("(select"):sql.index(") as nearest")]
    assert subquery.startswith("(select document_number from company_search_names where %(key)s <%% name_key ")   # only the number leaves the narrow table
    assert subquery.endswith("limit %(limit)s")                           # the pool is cut BEFORE the join, so at most `limit` full rows are fetched
    assert sql.endswith(") as nearest join company_search as c using (document_number)")
    selected = sql[len("select "):sql.index(" from (")].split(", ")
    assert selected == ["c." + column for column in COMPANY_COLUMNS]      # every field, source_url and fetched_at included, comes from company_search


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
    assert params == {"key": "ACME'; DROP TABLE company_search; --", "limit": 200}
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
