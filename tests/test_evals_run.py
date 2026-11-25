"""test_evals_run.py: offline tests for evals/run.py, the script that scores the search against the test set.

What is under test is the SCORING: how a list of answers becomes top-1, recall at 5 and
wrong_match. The search itself runs against FakeBackend with invented companies, so no
database is opened and nothing is billed. The two seed files the script reads are the
committed ones in pipeline/seeds/.

Run from ~/datum:  pytest
"""

import subprocess                           # runs git as a separate program, to ask what it ignores
from dataclasses import replace             # a copy of a frozen dataclass with one field changed
from datetime import date, datetime, timezone   # an invented company's dates and its UTC fetch time
from pathlib import Path                    # the repo's root folder

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.search import COMPANY_COLUMNS, Company, FakeBackend, name_key
from datum.search import PostgresBackend
from evals.run import (
    ASK, DRAW_SQL, LATENCY_SEED, NO_DRAFTS, RETRIEVERS, Case, SnowflakeBackend, WideTableBackend, compare_backends, draw_company_names, fingerprint,
    percentile, place_text, print_comparison, print_draft_results, print_results, read_cases, read_draft_cases, run_cases, score_case, summarize,
)


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
    return Case(case_id=case_id, case_group=group, expected_document_number=expected, business_name=name, city="", street="", is_specific=is_specific)


def test_the_committed_test_set_is_read_and_joined_to_its_extractions():
    cases = read_cases()
    assert [c.case_id for c in cases] == list(range(1, 14))               # thirteen hand-checked cases: ten from October, and three added in leg D1
    by_id = {c.case_id: c for c in cases}
    assert [c.case_group for c in cases[10:]] == ["contractor_search"] * 3 and {c.expected_document_number for c in cases[10:]} == {"L22000086098"}
    assert (by_id[11].business_name, by_id[11].city, by_id[11].is_specific) == ("V Pizza", "Orlando", True)
    assert by_id[13].is_specific is False                                 # "8586 palm pwwy" names no business: the extraction step said so
    assert by_id[13].street == "8586 palm pwwy" and by_id[10].street == "Race Track Rd" and by_id[1].street == ""   # the street is read as the extraction step returned it
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


def test_two_backends_that_hold_the_same_companies_give_the_same_five():
    companies = [company(f"T{n}", f"ACME ROOFING {n}") for n in range(1, 8)]
    same = compare_backends(FakeBackend(companies), FakeBackend(list(reversed(companies))), [("Acme Roofing", ""), ("Acme Roofing 3", "")])
    assert [(c.position, c.first_count, c.second_count, c.difference) for c in same] == [(1, 5, 5, None), (2, 5, 5, None)]   # the pool's order does not matter: the rerank decides


def test_a_comparison_names_each_way_two_answers_can_differ():
    companies = [company("T1", "ACME ROOFING LLC"), company("T2", "ACME ROOFING INC"), company("T3", "ACME ROOFS LLC")]
    first = FakeBackend(companies)
    missing_one = FakeBackend(companies[:2])                              # T3 is not in this backend's table
    moved = FakeBackend([replace(companies[0], principal_city="TAMPA")] + companies[1:])   # T1 sits in another city here
    restated = FakeBackend([replace(companies[0], status_code="I")] + companies[1:])   # the same companies, one with another status

    def difference(other, city=""):
        return compare_backends(first, other, [("Acme Roofing Inc", city)])[0]

    assert (difference(missing_one).difference, difference(missing_one).second_count) == ("different companies", 2)
    # T1 and T2 score the same against "Acme Roofing". Both are in Jacksonville in the first backend, so the document number
    # puts T1 first. In the other backend T1 is in Tampa, and so the city tie-break puts T2 first.
    by_city = compare_backends(first, moved, [("Acme Roofing", "Jacksonville")])[0]
    assert by_city.difference == "the same companies in a different order"
    assert difference(restated).difference == "the same companies in the same order, with different details"
    assert difference(first).difference is None


def test_a_comparison_sees_a_difference_below_the_five_companies_returned():
    # shortlist() reads the pool below the fifth place to count same-name companies that are not shown, so the pool has to agree too.
    companies = [company(f"T{n}", f"ACME ROOFING {n}") for n in range(1, 8)]
    all_seven, without_the_last = FakeBackend(companies), FakeBackend(companies[:6])   # T7 ranks seventh, below the five returned
    result = compare_backends(all_seven, without_the_last, [("Acme Roofing 1", "")])[0]
    assert (result.first_count, result.second_count) == (5, 5)            # the five returned are the same five
    assert result.difference == "the same companies returned, and a different pool behind them"


def test_the_comparison_prints_positions_and_counts_and_never_a_name(capsys):
    companies = [company("T1", "ACME ROOFING LLC"), company("T2", "BEST POOLS INC")]
    inputs = [("Acme Roofing", ""), ("Zebra Glass", ""), ("Best Pools", "")]
    print_comparison(compare_backends(FakeBackend(companies), FakeBackend(companies[:1]), inputs), test_inputs=1)   # capsys catches what is printed
    printed = capsys.readouterr().out
    assert "in the five returned and in the whole pool: 0 of 3" in printed and "differing: 3" in printed
    assert "input 2: different companies (2 companies against 1)" in printed
    for text in ("ACME", "Acme", "Zebra", "BEST", "Best", "T1", "T2"):    # no typed name, no company name and no document number
        assert text not in printed


def test_the_second_approach_reads_company_search_itself_and_the_default_is_the_apps_search():
    sql = WideTableBackend.NEAREST_SQL
    assert " from company_search where %(key)s <%% name_key " in sql and "company_search_names" not in sql
    assert sql.count("%(key)s") == 2 and sql.count("%(limit)s") == 1 and "'" not in sql   # what was typed still travels as a value
    assert RETRIEVERS["narrow"][0] is PostgresBackend and RETRIEVERS["word"][0] is WideTableBackend
    assert list(RETRIEVERS)[0] == "narrow"                                # the first key is the one --retrieve defaults to


def test_the_random_draw_switches_synchronized_scans_off_before_it_draws():
    # With that setting on, a scan of a large table starts where the last one stopped, and the "same" draw returns other names.
    class DrawConnection:
        """Stands in for a psycopg connection: it keeps what it was asked, in order, and answers the draw with two rows."""

        def __init__(self):
            self.asked = []

        def execute(self, sql, params=None):
            self.asked.append((sql, params))
            return self

        def fetchall(self):
            return [("ACME ROOFING LLC", ""), ("BEST POOLS INC", "")]

    conn = DrawConnection()
    assert draw_company_names(conn, 200) == [("ACME ROOFING LLC", ""), ("BEST POOLS INC", "")]   # (name, no city), as the search takes them
    statements = [sql for sql, _ in conn.asked]
    assert statements == ["select set_config('synchronize_seqscans', 'off', false)", DRAW_SQL]   # the setting first, then the draw, and nothing between
    assert conn.asked[1][1] == (LATENCY_SEED, 200)                         # the seed and the count travel as values
    assert "repeatable (%s) limit %s" in DRAW_SQL and "order by" not in DRAW_SQL   # no sort: the scan order IS the draw, which is why the setting matters


def test_a_fingerprint_changes_with_any_name_or_with_the_order():
    drawn = [("ACME ROOFING LLC", ""), ("BEST POOLS INC", "")]
    code = fingerprint(drawn)
    assert code == "8e70d4cdb9e0fb05e2a14af8851c9427"                     # the MD5 of "ACME ROOFING LLC|BEST POOLS INC", from the Mac's own md5 command
    assert fingerprint(list(reversed(drawn))) != code                     # the same names in another order are another draw
    assert fingerprint([("ACME ROOFING LLC", ""), ("BEST POOLS INC.", "")]) != code   # one character changed
    assert fingerprint([("ACME ROOFING LLC", "TAMPA"), ("BEST POOLS INC", "")]) == code   # the city is not part of a draw: it is always empty


@pytest.mark.parametrize("path", ["evals/draft_cases.csv", "evals/draft_extracted.csv"])
def test_the_draft_case_files_are_ignored_by_git(path):
    # Working rule S1: a drafted case stays on the Mac until Andres has checked it, because the repo is public and an unchecked
    # address may be someone's home. `git check-ignore` compares the path, as text, with the ignore rules. No file is created or read.
    repo_root = Path(__file__).parent.parent
    result = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", path], cwd=repo_root, check=False)
    assert result.returncode == 0, f"{path} is not ignored, so `git add .` would publish it"   # 0 = ignored, 1 = not ignored


def test_the_expected_companys_place_among_all_the_candidates_is_kept():
    # "It is sixth" and "the search never saw it" are different faults. The five answers alone cannot tell them apart.
    companies = [company(f"T{n}", f"ACME ROOFING {n}") for n in range(1, 7)] + [company("T7", "ACME ROOFING AND SIDING OF JACKSONVILLE")]
    backend = FakeBackend(companies)
    sixth, absent, asked, none_expected = run_cases([
        a_case("T7", case_id=1), a_case("T9", case_id=2), a_case("T7", is_specific=False, case_id=3), a_case(ASK, case_id=4),
    ], backend)
    assert (sixth.place, sixth.candidates, sixth.in_top5, len(sixth.answered)) == (7, 7, False, 5)   # ranked, and below the five returned
    assert (absent.place, absent.candidates) == (None, 7)                 # T9 is not among the candidates at all
    assert [place_text(r) for r in (sixth, absent, asked, none_expected)] == ["7 of 7", "not among 7", "asked", "none expected"]
    assert place_text(run_cases([a_case("T1")], FakeBackend([]))[0]) == "no candidates"


def write_case_files(folder, rows, name="cases.csv"):
    """A file of cases and the file of their extractions, in a temporary folder. Every case is invented."""
    cases, extracted = folder / name, folder / ("extracted_" + name)
    with cases.open("w", newline="") as handle:
        handle.write("case_id,case_group,input_text,expected_document_number,expected_entity_name,case_type,verified_on,notes\n")
        for case_id, group, typed, expected, verified_on in rows:
            handle.write(f"{case_id},{group},{typed},{expected},,,{verified_on},\n")
    with extracted.open("w", newline="") as handle:
        handle.write("case_id,input_text,business_name,city,street,is_specific,model\n")
        for case_id, _, typed, _, _ in rows:
            handle.write(f"{case_id},{typed},{typed.title()},,,True,a-model\n")
    return cases, extracted


def test_a_draft_cannot_sit_in_the_test_set_and_a_checked_case_cannot_sit_among_the_drafts(tmp_path):
    # Working rule S1: a case enters the test set only when Andres has checked it, and the date in verified_on is the sign that he did.
    checked = [("1", "g", "acme roofing", "T1", "2026-11-24")]
    draft = [("101", "g", "zebra glass", "T2", "")]
    assert [c.case_id for c in read_cases(*write_case_files(tmp_path, checked))] == [1]
    assert [c.case_id for c in read_draft_cases(*write_case_files(tmp_path, draft, "drafts.csv"))] == [101]
    with pytest.raises(ValueError, match="case 101 in mixed.csv has no verified_on date, so it is a draft and not a checked case"):
        read_cases(*write_case_files(tmp_path, checked + draft, "mixed.csv"))
    with pytest.raises(ValueError, match="case 1 in mixed_drafts.csv has a verified_on date, so it is not a draft"):
        read_draft_cases(*write_case_files(tmp_path, draft + checked, "mixed_drafts.csv"))


def test_with_no_draft_files_one_sentence_says_so(tmp_path, capsys):
    # On GitHub the two draft files do not exist, because git ignores them. The run must still score the checked cases.
    cases, extracted = write_case_files(tmp_path, [("101", "g", "zebra glass", "T2", "")], "drafts.csv")
    assert read_draft_cases(tmp_path / "no_such_file.csv", extracted) is None and read_draft_cases(cases, tmp_path / "no_such_file.csv") is None
    print_draft_results(None)
    assert capsys.readouterr().out.strip() == NO_DRAFTS == "draft cases: the two local draft files are not here, so only the checked cases were scored."


def test_the_draft_cases_are_printed_as_a_summary_by_group_and_never_a_line_per_case(tmp_path, capsys):
    # A leg report pastes this output into a public pull request. A draft may hold an address that is somebody's home.
    drafts = read_draft_cases(*write_case_files(tmp_path, [
        ("101", "address_only", "77 zebra glass way", "T2", ""), ("102", "address_only", "88 quartz lane", "T9", ""),
        ("103", "brand_and_city", "acme roofing", "T1", ""),
    ], "drafts.csv"))
    backend = FakeBackend([company("T1", "ACME ROOFING LLC"), company("T2", "77 ZEBRA GLASS WAY LLC")])
    results = run_cases(drafts, backend)
    print_draft_results(results)
    printed = capsys.readouterr().out
    lines = [line.split() for line in printed.splitlines() if line and line.split()[0] in ("address_only", "brand_and_city", "ALL")]
    assert lines == [["address_only", "2", "1", "1", "1"], ["brand_and_city", "1", "1", "1", "0"], ["ALL", "3", "2", "2", "1"]]   # counts, by group
    for text in ("zebra", "Zebra", "ZEBRA", "quartz", "Quartz", "77", "88", "T1", "T2", "T9", "101", "102", "103", "ACME", "Acme"):
        assert text not in printed, text                                  # no typed text, no company, no document number and no case id
    print_results(results, "a backend")                                   # the CHECKED table does print a line per case, so the check above can fail
    assert "T2" in capsys.readouterr().out
