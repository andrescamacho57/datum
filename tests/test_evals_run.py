"""test_evals_run.py: offline tests for evals/run.py, the script that scores the search against the test set.

What is under test is the SCORING: how a list of answers becomes top-1, recall at 5 and
wrong_match. The search itself runs against FakeBackend with invented companies, so no
database is opened and nothing is billed. The two seed files the script reads are the
committed ones in pipeline/seeds/.

Run from ~/datum:  pytest
"""

from datetime import date, datetime, timezone   # an invented company's dates and its UTC fetch time

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.search import COMPANY_COLUMNS, Company, FakeBackend, name_key
from evals.run import ASK, Case, SnowflakeBackend, percentile, read_cases, run_cases, score_case, summarize


def company(document_number, entity_name):
    """An invented company. The document numbers use a prefix (T) the state does not."""
    return Company(
        document_number=document_number, entity_name=entity_name, name_key=name_key(entity_name),
        status_code="A", filing_type="FLAL", file_date=date(2020, 1, 15),
        principal_address_1="1 INVENTED WAY", principal_city="JACKSONVILLE", principal_state="FL", principal_zip="32256",
        published_on=date(2026, 10, 7), source_url="https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber",
        fetched_at=datetime(2026, 10, 22, 19, 31, 31, tzinfo=timezone.utc), fetched_at_is_approximate=True,
    )


def a_case(expected, is_specific=True, name="Acme Roofing", group="g", case_id=1):
    return Case(case_id=case_id, case_group=group, expected_document_number=expected, business_name=name, city="", is_specific=is_specific)


def test_the_committed_test_set_is_read_and_joined_to_its_extractions():
    cases = read_cases()
    assert [c.case_id for c in cases] == list(range(1, 11))               # ten hand-checked cases
    by_id = {c.case_id: c for c in cases}
    assert (by_id[1].business_name, by_id[1].city, by_id[1].is_specific) == ("Ferguson Air Conditioning", "Boynton Beach", True)
    assert by_id[10].expected_document_number == ASK and by_id[10].is_specific is False   # "the pool guy": the right answer is to ask
    assert by_id[7].is_specific is False                                  # the extraction step judged this one not specific


def test_the_right_company_first_is_top1_and_not_a_wrong_match():
    result = score_case(a_case("T1"), ["T1", "T2", "T3"])
    assert (result.top1_correct, result.in_top5, result.wrong_match) == (True, True, False)


def test_the_right_company_second_is_in_the_top_five_and_IS_a_wrong_match():
    # The first answer is what a contractor would act on. It names another company, so it is the costly error.
    result = score_case(a_case("T1"), ["T2", "T1"])
    assert (result.top1_correct, result.in_top5, result.wrong_match) == (False, True, True)


def test_the_right_company_sixth_is_outside_the_top_five():
    result = score_case(a_case("T1"), ["T2", "T3", "T4", "T5", "T6", "T1"])
    assert (result.top1_correct, result.in_top5, result.wrong_match) == (False, False, True)


def test_asking_for_more_is_never_a_wrong_match_even_when_a_company_was_expected():
    result = score_case(a_case("T1", is_specific=False), [])
    assert (result.top1_correct, result.in_top5, result.wrong_match) == (False, False, False)   # a miss, and the cheap kind


def test_a_case_whose_right_answer_is_to_ask_is_correct_only_when_the_search_asked():
    asked = score_case(a_case(ASK, is_specific=False), [])
    assert (asked.top1_correct, asked.in_top5, asked.wrong_match) == (True, True, False)
    answered = score_case(a_case(ASK, is_specific=True), ["T9"])
    assert (answered.top1_correct, answered.in_top5, answered.wrong_match) == (False, False, True)   # it named a company for "the pool guy"


def test_a_specific_case_with_no_candidates_is_a_miss_and_not_a_wrong_match():
    result = score_case(a_case("T1"), [])
    assert (result.top1_correct, result.in_top5, result.wrong_match) == (False, False, False)


def test_a_case_that_names_no_business_is_never_searched():
    backend = FakeBackend([company("T1", "ACME ROOFING LLC")])
    results = run_cases([a_case(ASK, is_specific=False, case_id=1), a_case("T1", case_id=2)], backend)
    assert len(backend.calls) == 1                                        # only the specific case reached the backend
    assert results[0].answered == () and results[1].answered == ("T1",)


def test_the_summary_counts_each_group_and_then_everything():
    results = [
        score_case(a_case("T1", group="a", case_id=1), ["T1"]),
        score_case(a_case("T1", group="a", case_id=2), ["T2", "T1"]),
        score_case(a_case(ASK, is_specific=False, group="b", case_id=3), []),
    ]
    assert summarize(results) == [("a", 2, 1, 2, 1), ("b", 1, 1, 1, 0), ("ALL", 3, 2, 3, 1)]


def test_percentile_is_the_value_that_share_of_the_values_are_at_or_below():
    values = [float(n) for n in range(1, 101)]                            # 1.0 to 100.0
    assert percentile(values, 0.50) == 50.0
    assert percentile(values, 0.95) == 95.0
    assert percentile([3.0, 1.0, 2.0], 0.95) == 3.0                       # a small list: the largest value
    assert percentile([7.0], 0.50) == 7.0


def test_the_snowflake_backend_marks_the_marts_fetch_time_as_utc_and_changes_nothing_else():
    # Snowflake's column has no time zone and holds UTC. The backend has to add the zone, and to the right column.
    expected = company("T1", "ACME ROOFING LLC")
    row = [getattr(expected, column) for column in COMPANY_COLUMNS]
    row[COMPANY_COLUMNS.index("fetched_at")] = expected.fetched_at.replace(tzinfo=None)   # as Snowflake hands it over: no zone

    class OneRowCursor:
        """Stands in for a Snowflake cursor: it keeps what it was asked and answers with one row."""

        def execute(self, sql, params):
            self.sql, self.params = sql, params

        def fetchall(self):
            return [tuple(row)]

    class OneRowConnection:
        def __init__(self):
            self.the_cursor = OneRowCursor()

        def cursor(self):
            return self.the_cursor

    conn = OneRowConnection()
    assert SnowflakeBackend(conn).nearest("ACME ROOFING", 200) == [expected]
    assert conn.the_cursor.params == {"key": "ACME ROOFING", "limit": 5000}   # the typed name travels as a value, and the ceiling is the pool
    assert "DENSE_RANK()" in conn.the_cursor.sql and "<= 5" in conn.the_cursor.sql   # the pool is the five highest score levels, not a fixed count


def test_the_snowflake_backend_refuses_a_pool_that_hit_its_ceiling(monkeypatch):
    # A pool cut at the ceiling is cut by document number, so it could be missing a company in the right city. That must be loud.
    monkeypatch.setattr(SnowflakeBackend, "MOST_ROWS", 3)
    expected = company("T1", "ACME ROOFING LLC")
    row = [getattr(expected, column) for column in COMPANY_COLUMNS]
    row[COMPANY_COLUMNS.index("fetched_at")] = expected.fetched_at.replace(tzinfo=None)

    class Cursor:
        def __init__(self, count):
            self.count = count

        def execute(self, sql, params):
            pass

        def fetchall(self):
            return [tuple(row)] * self.count

    class Connection:
        def __init__(self, count):
            self.count = count

        def cursor(self):
            return Cursor(self.count)

    assert len(SnowflakeBackend(Connection(2)).nearest("ACME ROOFING", 200)) == 2   # under the ceiling: fine
    with pytest.raises(RuntimeError, match="hit its ceiling of 3 rows"):
        SnowflakeBackend(Connection(3)).nearest("ACME ROOFING", 200)
