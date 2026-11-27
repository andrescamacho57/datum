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

from datum.search import COMPANY_COLUMNS, Company, FakeBackend, by_city_then_words, by_words_then_city, name_key
from datum.search import PostgresBackend
from evals.run import (
    ASK, DRAW_ADDRESS_SQL, DRAW_SQL, LATENCY_SEED, NO_DRAFTS, ORDERS, RETRIEVERS, Case, SnowflakeBackend, WideTableBackend, compare_backends, draw_company_names,
    evaluate, fingerprint, made_worse, moved, movement, percentile, place_text, print_before_and_after, print_comparison, print_draft_results, print_results,
    page_text, read_cases, read_draft_cases, run_cases, score_case, summarize, time_address_searches,
)


def company(document_number, entity_name, address="1 INVENTED WAY", status="A"):
    """An invented company. The document numbers use a prefix (T) the state does not."""
    return Company(
        document_number=document_number, entity_name=entity_name, name_key=name_key(entity_name),
        status_code=status, filing_type="FLAL", file_date=date(2020, 1, 15),
        principal_address_1=address, principal_city="JACKSONVILLE", principal_state="FL", principal_zip="32256",
        published_on=date(2026, 10, 7), source_url="https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber",
        fetched_at=datetime(2026, 10, 22, 19, 31, 31, tzinfo=timezone.utc), fetched_at_is_approximate=True,
    )


def a_case(expected, is_specific=True, name="Acme Roofing", group="g", case_id=1, street=""):
    return Case(case_id=case_id, case_group=group, expected_document_number=expected, business_name=name, city="", street=street, is_specific=is_specific)


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


def test_a_case_is_worse_when_its_company_drops_leaves_the_candidates_or_an_ask_case_gets_a_company():
    # Working rule S3's three tests, and the two things that are NOT worse: staying put and moving up.
    def result(expected, answered, place=None, is_specific=True):
        return score_case(a_case(expected, is_specific=is_specific), answered, place, candidates=10)

    first, second, sixth = result("T1", ["T1"], 1), result("T1", ["T2", "T1"], 2), result("T1", ["T2", "T3", "T4", "T5", "T6"], 6)
    gone, asked_for_more = result("T1", ["T2"], None), result("T1", [], None, is_specific=False)
    ask_kept, ask_broken = result(ASK, [], is_specific=False), result(ASK, ["T9"])
    assert [moved(first, second), moved(second, sixth), moved(sixth, gone), moved(first, asked_for_more)] == ["down"] * 4   # a drop, out of the top five, out of the candidates, no answer at all
    assert moved(ask_kept, ask_broken) == "down"                          # a note that should be asked about got a company
    assert [moved(second, first), moved(gone, sixth), moved(ask_broken, ask_kept)] == ["up"] * 3
    assert [moved(first, first), moved(gone, gone), moved(gone, asked_for_more), moved(ask_kept, ask_kept)] == ["stayed"] * 4
    before = [score_case(a_case("T1", case_id=n), ["T1"], 1) for n in (1, 2, 3)]
    after = [before[0], score_case(a_case("T1", case_id=2), ["T2", "T1"], 2), before[2]]
    assert made_worse(before, after) == [2] and made_worse(before, before) == []
    with pytest.raises(ValueError):
        made_worse(before, after[:2])                                     # two runs of different length are not the same cases


def test_another_order_is_scored_on_the_same_pool_and_can_disagree_with_the_apps():
    # The same candidates, sorted two ways. Under the app's order the near-miss ROOFINGS comes first, and under rule S2 it comes last.
    backend = FakeBackend([company("T1", "ACME ROOFINGS"), company("T2", "ACME ROOFING AND SIDING INC")])
    (app,), (tried,) = run_cases([a_case("T2")], backend), run_cases([a_case("T2")], backend, order=by_words_then_city)
    assert (app.place, tried.place, app.page_place, tried.page_place, moved(app, tried)) == (2, 1, 2, 1, "up")
    assert movement([app], [tried]) == [("g", 1, 1, 0, 0), ("ALL", 1, 1, 0, 0)]
    assert ORDERS == {"s2": by_words_then_city, "s2-city-first": by_city_then_words}   # the two orders --try-order can name: rule S2 and its one variant


def test_a_company_that_keeps_its_rank_and_drops_on_the_page_counts_as_worse():
    # The shape of what leg D1 found on checked case 9, with invented companies. Typed: "Acme". The expected company, T1, is first by
    # rank under both orders. Under the app's order the five shown are T1 and four near-misses, all rated Possible, so T1 tops the page.
    # Rule S2 lifts T6, whose name is exactly the typed one, into the five. The page shows the five by level, so T6 (Strong) goes on top.
    backend = FakeBackend([company("T1", "ACME X LLC")] + [company(f"T{n}", f"ACME{letter} INC") for n, letter in zip((2, 3, 4, 5), "SABC")]
                          + [company("T6", "ACME CORPORATION")])
    (app,), (tried,) = run_cases([a_case("T1", name="Acme")], backend), run_cases([a_case("T1", name="Acme")], backend, order=by_words_then_city)
    assert (app.place, app.page_place, app.top1_correct) == (1, 1, True)
    assert (tried.place, tried.page_place, tried.top1_correct) == (1, 2, True)        # the rank and top-1 say nothing changed ...
    assert moved(app, tried) == "down" and made_worse([app], [tried]) == [1]          # ... and the comparison still calls it worse
    assert (page_text(app), page_text(tried)) == ("1", "2")
    asked = run_cases([a_case("T1", is_specific=False)], backend)[0]
    not_shown = run_cases([a_case("T9", name="Acme")], backend)[0]
    assert (page_text(asked), page_text(not_shown), page_text(run_cases([a_case(ASK, name="Acme")], backend)[0])) == ("asked", "not shown", "none expected")
def test_a_draft_case_can_never_change_the_pass_or_fail_decision(tmp_path, capsys):
    # Working rule S1: every gate reads the checked cases only. The fixture is a checked case that stays first, and two drafts
    # that the change makes as bad as a case can get. The decision must be the same with those drafts, with none, and with good ones.
    checked = read_cases(*write_case_files(tmp_path, [("1", "g", "acme roofing", "T1", "2026-11-24")]))
    drafts = read_draft_cases(*write_case_files(tmp_path, [("101", "address_only", "77 zebra glass way", "T2", ""), ("102", "address_only", "88 quartz lane", "T3", "")], "drafts.csv"))
    steady = [score_case(checked[0], ["T1"], 1, 3)]
    drafts_good = [score_case(case, [case.expected_document_number], 1, 3) for case in drafts]
    drafts_bad = [score_case(case, ["T9"], None, 3) for case in drafts]
    assert print_before_and_after(steady, steady, drafts_good, drafts_bad) == 0      # both drafts fell out of the candidates, and the decision is still "pass"
    printed = capsys.readouterr().out
    assert "checked cases made worse: none" in printed and ["address_only", "2", "0", "2", "0"] in [line.split() for line in printed.splitlines()]
    for text in ("zebra", "quartz", "77", "88", "T2", "T3", "101", "102"):   # the drafts appear as counts by group and nothing else
        assert text not in printed, text
    assert print_before_and_after(steady, steady, None, None) == 0 and print_before_and_after(steady, steady, drafts_bad, drafts_good) == 0
    dropped = [score_case(checked[0], ["T9", "T1"], 2, 3)]
    assert print_before_and_after(steady, dropped, drafts_bad, drafts_good) == 1     # a CHECKED case dropped: fail, however well the drafts did
    assert "checked cases made worse: 1" in capsys.readouterr().out


def test_each_case_goes_down_the_path_the_app_would_send_its_note():
    # The evaluation follows the app (working rule S5). Before leg D1 a case that named no business was never searched, whatever its street.
    backend = FakeBackend([
        company("T2", "ZEBRA GLASS LLC", address="77 QUARTZ PKWY"), company("T1", "ACME ROOFING LLC", address="77 Quartz Parkway"),
        company("T3", "BEST POOLS INC", address="77 QUARTZ PKWY", status="I"), company("T4", "CORAL ELECTRIC LLC", address="78 QUARTZ PKWY"),
    ])
    by_address = a_case("T1", is_specific=False, name="<UNKNOWN>", street="77 quartz pwwy", case_id=1)
    no_number = a_case(ASK, is_specific=False, name="Pool", street="Race Track Rd", case_id=2)
    named = a_case("T1", is_specific=True, name="Acme Roofing", street="77 quartz pwwy", case_id=3)
    found, asked, by_name = run_cases([by_address, no_number, named], backend, address_backend=backend)
    assert (found.searched, found.answered, found.place, found.candidates) == ("address", ("T1", "T2"), 1, 2)   # the two ACTIVE companies there, by document number
    assert (found.top1_correct, found.in_top5, found.wrong_match, place_text(found)) == (True, True, False, "1 of 2")
    assert (asked.searched, asked.answered, asked.top1_correct, place_text(asked)) == ("ask", (), True, "asked")   # rule S7: no house number, so it asks
    assert by_name.searched == "name" and by_name.answered[0] == "T1" and by_name.candidates == 4   # a named business gets the name search, house number or not
    assert backend.address_calls == [("77", ("QUARTZ", "PWWY"), 1000)] and len(backend.calls) == 1
    # With no address backend there is no search by address: that is the search as it was before Phase D, and the Snowflake backend's case.
    (before,) = run_cases([by_address], backend)
    assert (before.searched, before.answered, place_text(before)) == ("ask", (), "asked") and moved(before, found) == "up"
    nobody_there = run_cases([a_case("T1", is_specific=False, name="", street="5 nowhere ln")], backend, address_backend=backend)[0]
    assert (nobody_there.searched, nobody_there.answered, place_text(nobody_there), nobody_there.wrong_match) == ("address", (), "no candidates", False)


def test_a_note_that_should_be_asked_about_and_gets_a_company_from_the_address_search_is_a_wrong_match():
    # Working rule S3's third test. The extraction calls this note not specific, and its street has a house number, so the address search answers.
    backend = FakeBackend([company("T1", "ACME ROOFING LLC", address="12 RACE TRACK RD")])
    before, now = (run_cases([a_case(ASK, is_specific=False, name="Pool", street="12 race track rd")], backend, address_backend=chosen)[0] for chosen in (None, backend))
    assert (before.top1_correct, before.wrong_match) == (True, False) and (now.top1_correct, now.in_top5, now.wrong_match) == (False, False, True)
    assert moved(before, now) == "down" and made_worse([before], [now]) == [1]


def test_the_address_timing_draws_addresses_that_begin_with_a_digit_and_counts_the_too_many_answers():
    assert "principal_address_1 ~ '^[0-9]'" in DRAW_ADDRESS_SQL and "repeatable (%s)" in DRAW_ADDRESS_SQL and "order by" not in DRAW_ADDRESS_SQL

    class DrawConnection:
        def __init__(self):
            self.asked = []

        def execute(self, sql, params=None):
            self.asked.append((sql, params))
            return self

        def fetchall(self):
            return [("12 MADE UP RD", ""), ("7 MAIL DROP WAY", "")]

    conn = DrawConnection()
    assert draw_company_names(conn, 200, DRAW_ADDRESS_SQL) == [("12 MADE UP RD", ""), ("7 MAIL DROP WAY", "")]
    assert [sql for sql, _ in conn.asked] == ["select set_config('synchronize_seqscans', 'off', false)", DRAW_ADDRESS_SQL]   # the same setting as the draw of names
    crowded = FakeBackend([company("T0", "INVENTED CO LLC", address="12 MADE UP RD")] + [company(f"T{n}", f"INVENTED CO {n} LLC", address="7 MAIL DROP WAY") for n in range(1, 52)])
    seconds, too_many = time_address_searches(crowded, [("12 MADE UP RD", ""), ("7 MAIL DROP WAY", "")])
    assert len(seconds) == 2 and all(value >= 0 for value in seconds) and too_many == 1   # 51 companies at the second address: too many to list


def test_the_whole_evaluation_fails_only_when_a_checked_case_is_made_worse(tmp_path, capsys):
    # Round 1 of leg D1's review: the helpers were tested, and the wiring that feeds them was not. evaluate() is that wiring. The two
    # companies are ranked in opposite orders by the app (ROOFINGS first, on similarity) and by rule S2 (the name that holds every word first).
    backend = FakeBackend([company("T1", "ACME ROOFINGS"), company("T2", "ACME ROOFING AND SIDING INC"), company("T3", "ZEBRA GLASS LLC", address="77 QUARTZ PKWY")])

    def cases(rows, name):
        return (read_cases if rows[0][4] else read_draft_cases)(*write_case_files(tmp_path, rows, name))

    def lines():
        return [line.split() for line in capsys.readouterr().out.splitlines()]

    better = cases([("1", "g", "acme roofing", "T2", "2026-11-24")], "better.csv")          # T2 is second for the app and first under rule S2
    worse = cases([("2", "g", "acme roofing", "T1", "2026-11-24")], "worse.csv")            # T1 is first for the app and second under rule S2
    draft_worse = cases([("101", "brand_and_city", "acme roofing", "T1", "")], "draft_worse.csv")
    assert evaluate(better, None, backend, "fake", address_backend=backend, try_order="s2") == 0
    assert ["1", "g", "2", "of", "3", "1", "of", "3", "2", "->", "1", "up"] in lines()         # by rank and on the page: second, then first
    assert evaluate(worse, None, backend, "fake", address_backend=backend, try_order="s2") == 1    # a checked case moved down: the command fails
    printed = lines()
    assert ["checked", "cases", "made", "worse:", "2"] in printed and ["2", "g", "1", "of", "3", "2", "of", "3", "1", "->", "2", "down"] in printed
    assert evaluate(worse, None, backend, "fake", address_backend=backend) == 0                # with no comparison asked for, nothing can fail
    assert evaluate(worse, None, backend, "fake", address_backend=backend, before=True) == 0   # before Phase D the ORDER was the same, so this case did not move
    capsys.readouterr()
    assert evaluate(better, draft_worse, backend, "fake", address_backend=backend, try_order="s2") == 0   # the DRAFT moved down, and the decision does not change
    printed = lines()
    assert ["checked", "cases", "made", "worse:", "none"] in printed and ["brand_and_city", "1", "0", "1", "0"] in printed
    # "Before Phase D" has no search by address. An address-only case was asked about then and is answered now, so it moved up.
    by_address = [Case(case_id=3, case_group="g", expected_document_number="T3", business_name="", city="", street="77 quartz pwwy", is_specific=False)]
    assert evaluate(by_address, None, backend, "fake", address_backend=backend, before=True) == 0
    assert ["3", "g", "asked", "1", "of", "1", "asked", "->", "1", "up"] in lines()
    # And the reverse: a note that should be asked about, which the address search now answers, fails the --before comparison.
    should_ask = [Case(case_id=4, case_group="g", expected_document_number=ASK, business_name="Pool", city="", street="77 quartz pkwy", is_specific=False)]
    assert evaluate(should_ask, None, backend, "fake", address_backend=backend, before=True) == 1
    # The same note as a DRAFT decides nothing in this comparison either: the checked case moved up, and the command passes.
    capsys.readouterr()                                                   # forget what the call above printed: its own table also holds the row "g 1 0 1 0"
    assert evaluate(by_address, should_ask, backend, "fake", address_backend=backend, before=True) == 0
    printed = capsys.readouterr().out
    drafts_table = printed[printed.index("before Phase D, and now: draft cases"):]   # only what follows the drafts' own heading
    assert ["g", "1", "0", "1", "0"] in [line.split() for line in drafts_table.splitlines()]   # the draft is counted as moved down, in the drafts' own table
    assert ["checked", "cases", "made", "worse:", "none"] in [line.split() for line in printed.splitlines()]
