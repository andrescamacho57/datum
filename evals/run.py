"""evals/run.py: score the search against the hand-checked test set, on Postgres or on Snowflake (Phase C, leg C2; draft cases added in Phase D, leg D1).

An evaluation ("eval") is a fixed set of questions with known answers, run again after
every change, so that "is the search better?" is a number and not an impression.

    python -m evals.run --backend postgres      # the search the web app uses
    python -m evals.run --backend snowflake     # the same rules, with Snowflake doing the retrieve step
    python -m evals.run --backend postgres --latency 200   # also time the search on 200 random company names
    python -m evals.run --backend postgres --latency 200 --retrieve word    # time the second approach leg C2 tried
    python -m evals.run --backend postgres --latency 200 --retrieve plain   # time the first approach leg C2 tried (slow)
    python -m evals.run --backend postgres --compare 200   # do the second approach and the app's search give the same five companies?
    python -m evals.run --backend postgres --before        # also score the search as it was before Phase D, and say which cases moved
    python -m evals.run --backend postgres --address-latency 200   # also time the search by address on 200 random principal addresses

Run from ~/datum with the project's virtual environment active.

What it reads: the two committed seeds, pipeline/seeds/test_set.csv (the cases and their
answers) and pipeline/seeds/extracted_inputs.csv (the fields the extraction step pulled out
of each case, saved by src/datum/extract.py). It never calls the Claude API (working rule
W10): the extraction is read from the saved file, so a run costs nothing in API tokens and
gives the same result every time.

Checked cases and draft cases (Phase D working rule S1). A CHECKED case is a row of
test_set.csv: Andres has confirmed its expected answer, and its verified_on column says when.
A DRAFT case is one an agent wrote from the register and nobody has checked yet. The drafts
live in two files that git ignores, evals/draft_cases.csv and evals/draft_extracted.csv, and
they stay on the Mac until Andres checks them. Both kinds are scored, in SEPARATE tables:
    - the checked cases get a line per case and a summary by case group;
    - the draft cases get the summary by case group ONLY. No line per case is ever printed
      for them, because a leg report pastes this output and the repo is public.
When the draft files are absent, as they are on GitHub, one sentence says so and only the
checked cases are scored. Every pass or fail decision is taken from the checked cases alone.

The evaluation follows the app. Each case goes down the path the web app would send its
note: datum.search.search_kind() reads the extracted fields and answers "name" (the name
search), "address" (the search by address, when the note names no business and its street
begins with a house number) or "ask" (no company is shown). An address search answers with
the active companies at the address in document-number order, so its first five are scored
the way the name search's best five are.

--before scores every case twice: with the search as it is, and with the search as it was
before Phase D (search version 1's order: similarity first, and the city only to break an
exact tie, and no search by address: a note that named no business was always asked for
more). It then says, case by case for the checked cases and by count for the drafts,
whether the expected company moved up, moved down or stayed. A checked case that moved down
is the one thing that makes the command fail (exit code 1). That is working rule S3's test:
a case is worse when its company leaves the top five, drops in rank, or when a note that
should be asked about gets a company.

What it measures, per case group and in total. The first two are defined exactly as in
snowflake/11_score_search_v1.sql:
    top-1         the first answer is the expected company. For a case whose right answer
                  is "ask for more" (NEEDS_MORE_INFO), top-1 means the search did ask.
    recall at 5   the expected company is among the first five answers.
    wrong_match   the search ANSWERED with a company, and it is not the expected one. This
                  is the costly error: a confident wrong company. Asking for more is never
                  a wrong match, even when a company was expected. Script 11 does not
                  define wrong_match, so this definition is this module's (CLAUDE.md rule 3
                  says to track it; docs/PROJECT_CONTEXT.md calls it "a wrong confident match").

The Snowflake backend costs credits: each case is one scan of 13 million names, and the
warehouse stays awake for one to three minutes in all (about 0.05 credits a run). Run it
as rarely as the work needs.

.gitignore names four local files in evals/. This module reads two of them, the Phase D
drafts evals/draft_cases.csv and evals/draft_extracted.csv, and prints only counts from
them. It never reads the other two, evals/link_sample_20.csv and
evals/draft_test_cases_40.csv, which are the leg B3 hand-check drafts. No company drawn for
the latency run or the comparison is ever printed either: only timings, counts and a
fingerprint of the draw are (a short code for the whole list of names, see fingerprint()).
"""

import argparse                             # reads --backend, --latency, --retrieve and --compare from the command line
import csv                                  # reads the two seed files
import hashlib                              # MD5, for the fingerprint of a draw
import math                                # ceil(), for the percentile
import sys                                  # the import path, and the exit code
import time                                 # times each search
from collections.abc import Callable        # the type of "a function that gives a candidate its sort key"
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from pathlib import Path                    # file paths that work on any operating system

REPO_ROOT = Path(__file__).resolve().parents[1]            # this file is evals/run.py → go up 1 folder to the repo root
sys.path.insert(0, str(REPO_ROOT / "src"))                 # so `import datum.search` works when this is run as python -m evals.run

from datum.search import (  # noqa: E402  (the path line above has to come first)
    COMPANY_COLUMNS, CANDIDATE_POOL, SHORTLIST_SIZE, AddressBackend, Candidate, Company, PostgresBackend, SearchBackend, address_search, by_words_then_city,
    company_from_row, search, search_kind, search_pool,
)

TEST_SET = REPO_ROOT / "pipeline" / "seeds" / "test_set.csv"
EXTRACTED = REPO_ROOT / "pipeline" / "seeds" / "extracted_inputs.csv"
DRAFT_CASES = REPO_ROOT / "evals" / "draft_cases.csv"       # git ignores both draft files (working rule S1)
DRAFT_EXTRACTED = REPO_ROOT / "evals" / "draft_extracted.csv"
ASK = "NEEDS_MORE_INFO"                     # the expected answer of a case that names no business
LATENCY_SEED = 42                           # the seed of the random draw. Getting the same companies twice also needs draw_company_names' setting


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class Case:
    """One test case: what was typed, what the extraction step made of it, and the right answer."""

    case_id: int
    case_group: str
    expected_document_number: str           # a document number, or NEEDS_MORE_INFO
    business_name: str                      # from extracted_inputs.csv
    city: str
    street: str                             # the street the extraction step returned. Empty for most cases
    is_specific: bool                       # False = the note names no business, so the search must ask and not answer


@dataclass(frozen=True)
class CaseResult:
    """How the search did on one case."""

    case: Case
    answered: tuple[str, ...]               # the document numbers returned, best first. Empty when the search asked for more
    top1_correct: bool
    in_top5: bool
    wrong_match: bool
    place: int | None = None                # where the expected company stands among ALL the candidates the search ranked: 1 is first.
                                            # None when it is not among them, when the search asked for more, or when no company is expected
    candidates: int = 0                     # how many candidates the search ranked for this case
    searched: str = "name"                  # which path the case took: "name", "address" or "ask" (datum.search.search_kind)


def read_case_files(cases_file: Path, extracted: Path, checked: bool) -> list[Case]:
    """The cases of one file, each joined to its saved extraction by case_id.

    `checked` says which kind of file this is, and each kind refuses a row of the other
    (working rule S1). A checked case has a date in verified_on, the day Andres confirmed its
    answer. A draft has none. So a draft pasted into the test set by mistake stops the run,
    and it cannot be scored as if somebody had checked it.
    """
    with extracted.open(newline="") as handle:
        fields = {row["case_id"]: row for row in csv.DictReader(handle)}
    cases = []
    with cases_file.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if bool(row["verified_on"].strip()) != checked:        # the message gives the case id and the file, never the case's text
                kind = "has no verified_on date, so it is a draft and not a checked case" if checked else "has a verified_on date, so it is not a draft"
                raise ValueError(f"case {row['case_id']} in {cases_file.name} {kind}")
            extraction = fields[row["case_id"]]                    # a case with no extraction is an error, not a skip
            cases.append(Case(
                case_id=int(row["case_id"]), case_group=row["case_group"],
                expected_document_number=row["expected_document_number"],
                business_name=extraction["business_name"], city=extraction["city"], street=extraction["street"],
                is_specific=extraction["is_specific"] == "True",   # extract.py writes Python's True or False as text
            ))
    return cases


def read_cases(test_set: Path = TEST_SET, extracted: Path = EXTRACTED) -> list[Case]:
    """The CHECKED cases: the committed test set, each case joined to its saved extraction."""
    return read_case_files(test_set, extracted, checked=True)


def read_draft_cases(cases_file: Path = DRAFT_CASES, extracted: Path = DRAFT_EXTRACTED) -> list[Case] | None:
    """The DRAFT cases, or None when the two local files are not both there (as on GitHub, where git never had them)."""
    if not cases_file.exists() or not extracted.exists():
        return None
    return read_case_files(cases_file, extracted, checked=False)


def score_case(case: Case, answered: list[str], place: int | None = None, candidates: int = 0, searched: str | None = None) -> CaseResult:
    """Score one case from the document numbers the search returned (none when it asked for more).

    `searched` is the path the case took. Left out, it is worked out from the case the way
    the evaluation did before there was a search by address: a specific case was searched
    by name, and any other was asked about.
    """
    searched = searched or ("name" if case.is_specific else "ask")
    if case.expected_document_number == ASK:                       # the right behavior is to ask: no search runs and no company is shown
        correct = searched == "ask"
        return CaseResult(case, tuple(answered), top1_correct=correct, in_top5=correct, wrong_match=bool(answered), candidates=candidates, searched=searched)
    return CaseResult(
        case, tuple(answered),
        top1_correct=answered[:1] == [case.expected_document_number],
        in_top5=case.expected_document_number in answered[:5],
        wrong_match=bool(answered) and answered[0] != case.expected_document_number,
        place=place, candidates=candidates, searched=searched,
    )


def version_1_order(candidate: Candidate) -> tuple:
    """The sort key rank() used until leg D1: the highest similarity first, then a company in the city given, then the document number.

    It is kept here, and not in the app's module, for one use: --before sorts the same pool
    this way, so that the old order and the new one can be shown side by side at any time.
    """
    return (-candidate.similarity, not candidate.city_match, candidate.company.document_number)


def run_cases(cases: list[Case], backend: SearchBackend, order: Callable[[Candidate], tuple] = by_words_then_city,
              address_backend: AddressBackend | None = None) -> list[CaseResult]:
    """Send every case down the path the app would send its note, and score it.

    search_kind() picks the path from the extracted fields, exactly as the web app does:
      "name"     the name search. It ranks a whole pool of candidates and answers with the
                 best five. The five are what is scored. The expected company's place in the
                 whole pool is kept as well, because "it is 6th" and "the search never saw
                 it" are different faults with different fixes.
      "address"  the search by address. It answers with the active companies at the address
                 in document-number order, and the first five of those are scored.
      "ask"      no search runs and no company is shown.
    `order` is the app's own order unless --before asks for version 1's. With no
    address_backend there is no search by address, and a note that names no business is
    asked about, as every such note was before Phase D.
    """
    results = []
    for case in cases:
        kind = search_kind(case.business_name, case.street, case.is_specific)
        if kind == "address" and address_backend is None:
            kind = "ask"
        if kind == "ask":
            results.append(score_case(case, [], searched="ask"))
            continue
        if kind == "address":
            numbers = [company.document_number for company in address_search(address_backend, case.street, case.city).active]
        else:
            numbers = [c.company.document_number for c in search_pool(backend, case.business_name, case.city, order=order)]
        place = numbers.index(case.expected_document_number) + 1 if case.expected_document_number in numbers else None
        results.append(score_case(case, numbers[:SHORTLIST_SIZE], place, len(numbers), searched=kind))   # the first five are exactly what the app shows first
    return results


def summarize(results: list[CaseResult]) -> list[tuple[str, int, int, int, int]]:
    """(group, cases, top-1 correct, in the top 5, wrong matches) for each case group, then for all cases."""
    groups = sorted({r.case.case_group for r in results})
    rows = []
    for group in groups + ["ALL"]:
        chosen = [r for r in results if group == "ALL" or r.case.case_group == group]
        rows.append((group, len(chosen), sum(r.top1_correct for r in chosen), sum(r.in_top5 for r in chosen), sum(r.wrong_match for r in chosen)))
    return rows


def standing(result: CaseResult) -> float:
    """How well a case did, as one number where LOWER is better, so that two runs of the same case can be compared.

    For a case that expects a company it is the company's place among the candidates: 1 is
    first. A company that is not among them, or a search that asked for more, stands at
    infinity, which is worse than any place. For a case whose right answer is to ask, 0
    means the search asked and 1 means it answered with a company.
    """
    if result.case.expected_document_number == ASK:
        return 1.0 if result.answered else 0.0
    return float(result.place) if result.place else math.inf


def moved(before: CaseResult, after: CaseResult) -> str:
    """ "up", "down" or "stayed": how one case's standing changed between two runs."""
    was, now = standing(before), standing(after)
    return "up" if now < was else "down" if now > was else "stayed"


def made_worse(before: list[CaseResult], after: list[CaseResult]) -> list[int]:
    """The ids of the cases a change made worse (working rule S3). The two lists hold the same cases in the same order.

    Rule S3 names three ways a case gets worse: its company leaves the top five, its company
    drops in rank, or a note that should be asked about gets a company. All three are a
    standing that went up, so "moved down" covers them: a company that leaves the top five
    has dropped, and so has one that falls out of the candidates altogether.
    """
    return [a.case.case_id for b, a in zip(before, after, strict=True) if moved(b, a) == "down"]


def movement(before: list[CaseResult], after: list[CaseResult]) -> list[tuple[str, int, int, int, int]]:
    """(group, cases, moved up, moved down, stayed) for each case group, then for all cases. Counts only."""
    pairs = list(zip(before, after, strict=True))
    rows = []
    for group in sorted({a.case.case_group for _, a in pairs}) + ["ALL"]:
        moves = [moved(b, a) for b, a in pairs if group == "ALL" or a.case.case_group == group]
        rows.append((group, len(moves), moves.count("up"), moves.count("down"), moves.count("stayed")))
    return rows


def percentile(values: list[float], share: float) -> float:
    """The value that `share` of the values are at or below (nearest-rank method). share is 0.5 for p50, 0.95 for p95."""
    ordered = sorted(values)
    return ordered[max(math.ceil(share * len(ordered)) - 1, 0)]


class SnowflakeBackend:
    """The retrieve step done by Snowflake: it scores ALL companies by Jaro-Winkler, as search version 1 did.

    It scans every company, which is what makes it slow and billable, and also what makes it
    the reference: nothing is left out of the pool by an index.

    The pool is every company whose score is one of the FIVE HIGHEST DISTINCT scores. The
    best five companies of snowflake/11_score_search_v1.sql can only come from those score
    levels, whatever the city tie-break does inside a level, so the pool always holds them.
    datum.search.rank() then applies version 1's full order in Python. A fixed count would
    not be safe: the score is a whole number, so hundreds of companies can share one score,
    and a cut at 200 could drop a company in the right city (the review of leg C2 found this).
    """

    MOST_ROWS = 5000                        # a ceiling on the pool, far above any tie seen, so one odd name can't pull back a million rows. Reaching it is an error, not a quiet cut

    NEAREST_SQL = f"""
        SELECT {', '.join(COMPANY_COLUMNS)}
        FROM datum.dev_marts.company_search
        QUALIFY DENSE_RANK() OVER (ORDER BY JAROWINKLER_SIMILARITY(%(key)s, name_key) DESC) <= 5
        ORDER BY JAROWINKLER_SIMILARITY(%(key)s, name_key) DESC, document_number
        LIMIT %(limit)s
    """
    # %(key)s and %(limit)s are placeholders the driver fills in safely. DENSE_RANK numbers the
    # distinct scores 1, 2, 3 ... from the highest down, with no gaps, and gives equal scores the
    # same number. QUALIFY filters on that number, the way WHERE filters on a column.

    def __init__(self, conn):
        self.conn = conn                    # an open Snowflake connection

    def nearest(self, search_key: str, limit: int) -> list[Company]:
        from datetime import timezone       # imported here: only this backend needs it
        cursor = self.conn.cursor()
        cursor.execute(self.NEAREST_SQL, {"key": search_key, "limit": max(limit, self.MOST_ROWS)})
        at = COMPANY_COLUMNS.index("fetched_at")                   # found by name, so a reordered column list can't shift it
        rows = cursor.fetchall()
        if len(rows) >= self.MOST_ROWS:                            # the ceiling cut the pool, by document number and not by city
            raise RuntimeError(
                f"the Snowflake pool for {search_key!r} hit its ceiling of {self.MOST_ROWS} rows, so it may be missing a company "
                "that search version 1 would rank in its best five. Raise MOST_ROWS and run again."
            )
        companies = []
        for row in rows:
            values = list(row)
            values[at] = values[at].replace(tzinfo=timezone.utc)   # the mart's fetched_at has no zone and holds UTC (its staging model says so)
            companies.append(company_from_row(values))
        return companies


class WideTableBackend(PostgresBackend):
    """The SECOND retrieve step leg C2 tried, kept only so that it can be timed and compared again.

    It asks the same question as the app's search (word similarity at a threshold of 0.75,
    with the legal suffix left out of the lookup) and reads the answer from company_search
    itself, through that table's own trigram index. The app's search, PostgresBackend, reads
    the narrow table company_search_names. Both tables hold the same names, so the two must
    return the same companies, and --compare checks that they do. Run it with --retrieve word.
    """

    NEAREST_SQL = (
        f"select {', '.join(COMPANY_COLUMNS)} from company_search "
        "where %(key)s <%% name_key "
        "order by name_key <-> %(key)s, document_number "
        "limit %(limit)s"
    )


class PlainSimilarityBackend(PostgresBackend):
    """The FIRST retrieve step leg C2 tried, kept only so that its timing can be measured again.

    It compares the two whole texts with plain trigram similarity (the operator %) at the
    extension's default threshold of 0.3, which is the query the plan of Oct 30 wrote down.
    At that threshold the index cannot skip the long lists of common trigrams, and a search
    takes several seconds. The app does not use this class. Run it with --retrieve plain.
    """

    NEAREST_SQL = (
        f"select {', '.join(COMPANY_COLUMNS)} from company_search "
        "where name_key %% %(key)s "
        "order by name_key <-> %(key)s, document_number "
        "limit %(limit)s"
    )

    def nearest(self, search_key: str, limit: int) -> list[Company]:
        rows = self.conn.execute(self.NEAREST_SQL, {"key": search_key, "limit": limit}).fetchall()   # the whole key, suffix included, as first written
        return [company_from_row(row) for row in rows]


def place_text(result: CaseResult) -> str:
    """Where the expected company stands among the candidates the search ranked, in words a table can hold."""
    if result.searched == "ask":
        return "asked"
    if not result.candidates:
        return "no candidates"
    if result.case.expected_document_number == ASK:
        return "none expected"
    return f"{result.place} of {result.candidates}" if result.place else f"not among {result.candidates}"


def print_summary(results: list[CaseResult]) -> None:
    """The summary table: one line per case group, then one for all of them."""
    print(f"{'group':<24}{'cases':>6}{'top-1':>7}{'recall@5':>10}{'wrong_match':>13}")
    for group, cases, top1, top5, wrong in summarize(results):
        print(f"{group:<24}{cases:>6}{top1:>7}{top5:>10}{wrong:>13}")


def print_results(results: list[CaseResult], backend_name: str) -> None:
    """The CHECKED cases: a line per case, and the summary table."""
    print(f"\nbackend: {backend_name}")
    print("\nchecked cases (pipeline/seeds/test_set.csv)")
    print(f"{'case':>4}  {'group':<22}{'expected':<16}{'answer':<16}{'top-1':<7}{'top-5':<7}{'wrong_match':<13}{'place of the expected company'}")
    for r in results:
        answer = r.answered[0] if r.answered else ASK
        print(f"{r.case.case_id:>4}  {r.case.case_group:<22}{r.case.expected_document_number:<16}{answer:<16}"
              f"{'yes' if r.top1_correct else 'no':<7}{'yes' if r.in_top5 else 'no':<7}{'YES' if r.wrong_match else 'no':<13}{place_text(r)}")
    print()
    print_summary(results)


NO_DRAFTS = "draft cases: the two local draft files are not here, so only the checked cases were scored."


def print_draft_results(results: list[CaseResult] | None) -> None:
    """The DRAFT cases: the summary table by case group and nothing else, or one sentence when there are no draft files.

    No line per case is printed, on purpose. A draft is unchecked, it may hold an address
    that is somebody's home, and this output is pasted into a public leg report.
    """
    if results is None:
        print("\n" + NO_DRAFTS)
        return
    print("\ndraft cases (evals/draft_cases.csv: not checked by Andres, and so counted in no pass or fail decision)")
    print_summary(results)


def time_address_searches(backend: AddressBackend, inputs: list[tuple[str, str]]) -> tuple[list[float], int]:
    """(seconds taken by each search by address, how many of them answered "too many to list")."""
    seconds, too_many = [], 0
    for street, city in inputs:
        started = time.perf_counter()
        found = address_search(backend, street, city)
        seconds.append(time.perf_counter() - started)
        too_many += found.too_many
    return seconds, too_many


def time_searches(backend: SearchBackend, inputs: list[tuple[str, str]]) -> list[float]:
    """Seconds taken by each search, both steps included."""
    seconds = []
    for business_name, city in inputs:
        started = time.perf_counter()                              # a clock for measuring durations
        search(backend, business_name, city)
        seconds.append(time.perf_counter() - started)
    return seconds


@dataclass(frozen=True)
class Comparison:
    """What two backends returned for one input, by its position in the list of inputs. No name is kept."""

    position: int                           # 1 for the first input, and so on
    first_count: int                        # how many companies the first backend's search returned (five at most)
    second_count: int                       # the same for the second backend
    difference: str | None                  # None when both returned the same companies, in the same order, with the same evidence, from the same pool


def compare_backends(first: SearchBackend, second: SearchBackend, inputs: list[tuple[str, str]]) -> list[Comparison]:
    """Search every input on both backends and say, for each, whether the two answers are the same.

    The five companies returned are compared first, because they are what the evaluation
    scores. Then the whole reranked pool behind them is compared too (up to 200 companies),
    because shortlist() reads the pool below the fifth place to count same-name companies
    that are not shown (working rule W7). Two answers are the same only when both agree.
    """
    comparisons = []
    for position, (business_name, city) in enumerate(inputs, start=1):
        pool_one = search_pool(first, business_name, city)
        pool_two = search_pool(second, business_name, city)
        one, two = pool_one[:SHORTLIST_SIZE], pool_two[:SHORTLIST_SIZE]   # exactly what search() returns
        numbers_one = [c.company.document_number for c in one]
        numbers_two = [c.company.document_number for c in two]
        if numbers_one != numbers_two:
            difference = "the same companies in a different order" if sorted(numbers_one) == sorted(numbers_two) else "different companies"
        elif one != two:
            difference = "the same companies in the same order, with different details"   # a field of a company, or its score
        elif pool_one != pool_two:
            difference = "the same companies returned, and a different pool behind them"   # a company below the fifth place differs
        else:
            difference = None
        comparisons.append(Comparison(position, len(one), len(two), difference))
    return comparisons


def print_comparison(comparisons: list[Comparison], test_inputs: int) -> None:
    """How many inputs differ, which ones by position, and how many companies the searches returned."""
    differing = [c for c in comparisons if c.difference]
    print(f"\ncompared {len(comparisons)} searches ({test_inputs} test inputs, then {len(comparisons) - test_inputs} random company names): "
          "the second approach (company_search) against the app's search (company_search_names)")
    print(f"  the same companies in the same order, in the five returned and in the whole pool: {len(comparisons) - len(differing)} of {len(comparisons)}")
    print(f"  differing: {len(differing)}")
    for c in differing:                                            # a position, never a name: the random names are not printed
        print(f"    input {c.position}: {c.difference} ({c.first_count} companies against {c.second_count})")
    full = sum(1 for c in comparisons if c.first_count == SHORTLIST_SIZE)
    none = sum(1 for c in comparisons if c.first_count == 0)
    print(f"  the second approach returned {SHORTLIST_SIZE} companies for {full} searches, "
          f"1 to {SHORTLIST_SIZE - 1} for {len(comparisons) - full - none}, and none for {none}")


def print_movement(rows: list[tuple[str, int, int, int, int]]) -> None:
    print(f"{'group':<24}{'cases':>6}{'moved up':>10}{'moved down':>12}{'stayed':>8}")
    for group, cases, up, down, stayed in rows:
        print(f"{group:<24}{cases:>6}{up:>10}{down:>12}{stayed:>8}")


def print_before_and_after(checked_before: list[CaseResult], checked_after: list[CaseResult],
                           drafts_before: list[CaseResult] | None, drafts_after: list[CaseResult] | None) -> int:
    """Both runs side by side, and the exit code: 1 when a CHECKED case was made worse, otherwise 0.

    The checked cases get a line each. The draft cases get counts by case group and nothing
    else. The exit code is worked out from the checked cases alone: the drafts are printed
    after it is decided and are not an input to made_worse(), so no draft can change it
    (working rule S1).
    """
    worse = made_worse(checked_before, checked_after)
    print("\nbefore Phase D and now, checked cases (the place of the expected company among the candidates)")
    print(f"{'case':>4}  {'group':<22}{'before':<18}{'now':<18}{'moved'}")
    for b, a in zip(checked_before, checked_after, strict=True):
        print(f"{a.case.case_id:>4}  {a.case.case_group:<22}{place_text(b):<18}{place_text(a):<18}{moved(b, a)}")
    print()
    print_movement(movement(checked_before, checked_after))
    print("checked cases made worse: " + (", ".join(str(case_id) for case_id in worse) if worse else "none"))
    if drafts_before is not None and drafts_after is not None:
        print("\nbefore Phase D and now, draft cases (counts only: not checked by Andres, and so counted in no pass or fail decision)")
        print_movement(movement(drafts_before, drafts_after))
    return 1 if worse else 0


DRAW_SQL = "select entity_name, '' from company_search tablesample bernoulli (0.01) repeatable (%s) limit %s"
# tablesample bernoulli (0.01) picks a random 0.01% of the rows, about 1,300 companies, and
# repeatable (42) makes it pick the same rows every time. limit then keeps the first 200 that
# the scan MEETS, and that is the catch: see draw_company_names below.


DRAW_ADDRESS_SQL = ("select principal_address_1, '' from company_search tablesample bernoulli (0.01) repeatable (%s) "
                    "where principal_address_1 ~ '^[0-9]' limit %s")
# The same draw as DRAW_SQL, for the search by address: the principal address of sampled
# companies, keeping only an address that begins with a digit, because no other can be found
# by address. A drawn address may be somebody's home. It is searched and never printed.


def draw_company_names(conn, count: int, sql: str = DRAW_SQL) -> list[tuple[str, str]]:
    """`count` company names drawn at random, each with an empty city. They are searched and never printed.

    The draw gives the same names on every run for as long as company_search is not loaded
    again from different files. fingerprint() below gives a short code for a draw, and every
    run prints it, so two runs can be seen to have searched the same names.

    A fixed seed is not enough to get the same names twice. Postgres lets a scan of a large
    table start wherever the last scan of that table stopped (the setting is called
    synchronize_seqscans, and it is on by default), so the first 200 sampled rows a scan
    meets depend on what ran before it. Until Nov 24, 2026 this draw gave different names on
    every call after the first one following a restart of Postgres. Leg C2's report shows it:
    three calls in a row gave three different sets. With the setting off for this session the
    scan always starts at the first page of the table. What the setting cannot fix is the
    table itself: a load from a new export puts other rows on those pages, and the draw
    changes with them.
    """
    conn.execute("select set_config('synchronize_seqscans', 'off', false)")   # this session only. It must come BEFORE the draw
    return [tuple(row) for row in conn.execute(sql, (LATENCY_SEED, count)).fetchall()]


def fingerprint(drawn: list[tuple[str, str]]) -> str:
    """A short code for a draw: the MD5 hash of the drawn names, in order, joined by "|".

    It changes when any name changes or when the order does. Two runs that print the same
    fingerprint searched the same names. For a draw of 200 names the code cannot be turned
    back into names. For a draw of one or two it could be, by hashing every company name in
    the state's public file and looking for a match, so it hides nothing then. MD5 is used
    as a checksum here and not for security, which is what usedforsecurity=False says.
    """
    return hashlib.md5("|".join(name for name, _ in drawn).encode("utf-8"), usedforsecurity=False).hexdigest()


RETRIEVERS = {                              # --retrieve: which retrieve step to run on Postgres
    "narrow": (PostgresBackend, "narrow table, word similarity"),            # the search the app uses (the third approach)
    "word": (WideTableBackend, "company_search, word similarity"),           # the second approach
    "plain": (PlainSimilarityBackend, "company_search, plain similarity"),   # the first approach
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the search against the hand-checked test set.")
    parser.add_argument("--backend", choices=("postgres", "snowflake"), required=True, help="which database does the retrieve step")
    parser.add_argument("--latency", type=int, default=0, metavar="N", help="also time the search on the test inputs plus N random company names (postgres only)")
    parser.add_argument("--retrieve", choices=tuple(RETRIEVERS), default="narrow", help="postgres only: narrow = the narrow table, the search the app uses; word = the second approach and plain = the first, both for timing only")
    parser.add_argument("--compare", type=int, default=0, metavar="N", help="postgres only: run the second approach and the app's search on the test inputs plus N random company names, and count the searches whose five companies differ")
    parser.add_argument("--address-latency", type=int, default=0, metavar="N", help="postgres only: also time the search by address on N principal addresses drawn at random")
    parser.add_argument("--before", action="store_true", help="postgres only: also score the search as it was before Phase D, say which cases moved, and fail when a checked case was made worse")
    args = parser.parse_args(argv)
    exit_code = 0
    cases = read_cases()
    drafts = read_draft_cases()             # None when the two local files are not there

    if args.backend == "postgres":
        import os                           # reads the optional DATUM_PG_DSN environment variable
        import psycopg                      # the Postgres driver, imported only when it is used
        with psycopg.connect(os.environ.get("DATUM_PG_DSN", "dbname=datum_dev")) as conn:
            backend_class, label = RETRIEVERS[args.retrieve]
            backend = backend_class(conn)
            checked_now = run_cases(cases, backend, address_backend=backend)
            drafts_now = run_cases(drafts, backend, address_backend=backend) if drafts is not None else None
            print_results(checked_now, f"postgres ({label})")
            print_draft_results(drafts_now)
            if args.before:                 # before Phase D: version 1's order, and no address_backend, so no search by address
                exit_code = print_before_and_after(
                    run_cases(cases, backend, order=version_1_order), checked_now,
                    run_cases(drafts, backend, order=version_1_order) if drafts is not None else None, drafts_now,
                )
            test_inputs = [(c.business_name, c.city) for c in cases if c.is_specific]

            def with_random_names(count: int) -> list[tuple[str, str]]:
                """The test inputs, then `count` company names drawn at random (see draw_company_names for when two draws are the same)."""
                return test_inputs + draw_company_names(conn, count)

            if args.compare:
                inputs = with_random_names(args.compare)
                print_comparison(compare_backends(WideTableBackend(conn), PostgresBackend(conn), inputs), len(test_inputs))
                print(f"  fingerprint of the random names: {fingerprint(inputs[len(test_inputs):])}")
            if args.latency:
                inputs = with_random_names(args.latency)
                random_names = inputs[len(test_inputs):]
                seconds = time_searches(backend, inputs)
                print(f"\nlatency over {len(inputs)} searches ({len(inputs) - len(random_names)} test inputs + {len(random_names)} random company names, pool of {CANDIDATE_POOL}):")
                print(f"  p50 {percentile(seconds, 0.50) * 1000:.0f} ms   p95 {percentile(seconds, 0.95) * 1000:.0f} ms   slowest {max(seconds) * 1000:.0f} ms")
                over = sum(1 for value in seconds if value > 1.0)
                print(f"  searches over 1 second: {over} of {len(seconds)}")
                print(f"  fingerprint of the random names: {fingerprint(random_names)}")
            if args.address_latency:
                addresses = draw_company_names(conn, args.address_latency, DRAW_ADDRESS_SQL)
                seconds, too_many = time_address_searches(backend, addresses)
                print(f"\nlatency of the search by address over {len(addresses)} principal addresses drawn at random:")
                print(f"  p50 {percentile(seconds, 0.50) * 1000:.0f} ms   p95 {percentile(seconds, 0.95) * 1000:.0f} ms   slowest {max(seconds) * 1000:.0f} ms")
                print(f"  searches over 1 second: {sum(1 for value in seconds if value > 1.0)} of {len(seconds)}")
                print(f"  searches answered with \"too many to list\": {too_many} of {len(seconds)}")
                print(f"  fingerprint of the random addresses: {fingerprint(addresses)}")
    else:
        import snowflake.connector          # Snowflake's Python driver, imported only when it is used
        conn = snowflake.connector.connect(connection_name="datum")    # the driver reads the connection's settings itself
        try:
            print_results(run_cases(cases, SnowflakeBackend(conn)), "snowflake")   # no address_backend: Snowflake has no address table, so an address-only note is scored as asked
        finally:
            conn.close()                    # always release the session, even after an error
    return exit_code


if __name__ == "__main__":                  # true only when this file is run directly
    sys.exit(main())                        # run main and pass its result to the shell
