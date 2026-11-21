"""evals/run.py: score the search against the hand-checked test set, on Postgres or on Snowflake (Phase C, leg C2).

An evaluation ("eval") is a fixed set of questions with known answers, run again after
every change, so that "is the search better?" is a number and not an impression.

    python -m evals.run --backend postgres      # the search the web app uses
    python -m evals.run --backend snowflake     # the same rules, with Snowflake doing the retrieve step
    python -m evals.run --backend postgres --latency 200   # also time the search on 200 random company names
    python -m evals.run --backend postgres --latency 200 --retrieve plain   # time the first approach leg C2 tried (slow)

Run from ~/datum with the project's virtual environment active.

What it reads: the two committed seeds, pipeline/seeds/test_set.csv (the cases and their
answers) and pipeline/seeds/extracted_inputs.csv (the fields the extraction step pulled out
of each case, saved by src/datum/extract.py). It never calls the Claude API (working rule
W10): the extraction is read from the saved file, so a run costs nothing in API tokens and
gives the same result every time.

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

Nothing here reads the two local files in evals/ that .gitignore names, and no company
drawn for the latency run is ever printed: only the timings are.
"""

import argparse                             # reads --backend and --latency from the command line
import csv                                  # reads the two seed files
import math                                 # ceil(), for the percentile
import sys                                  # the import path, and the exit code
import time                                 # times each search
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from pathlib import Path                    # file paths that work on any operating system

REPO_ROOT = Path(__file__).resolve().parents[1]            # this file is evals/run.py → go up 1 folder to the repo root
sys.path.insert(0, str(REPO_ROOT / "src"))                 # so `import datum.search` works when this is run as python -m evals.run

from datum.search import COMPANY_COLUMNS, CANDIDATE_POOL, Company, PostgresBackend, SearchBackend, company_from_row, search   # noqa: E402  (the path line above has to come first)

TEST_SET = REPO_ROOT / "pipeline" / "seeds" / "test_set.csv"
EXTRACTED = REPO_ROOT / "pipeline" / "seeds" / "extracted_inputs.csv"
ASK = "NEEDS_MORE_INFO"                     # the expected answer of a case that names no business
LATENCY_SEED = 42                           # the same random companies on every run, so two runs can be compared


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class Case:
    """One test case: what was typed, what the extraction step made of it, and the right answer."""

    case_id: int
    case_group: str
    expected_document_number: str           # a document number, or NEEDS_MORE_INFO
    business_name: str                      # from extracted_inputs.csv
    city: str
    is_specific: bool                       # False = the note names no business, so the search must ask and not answer


@dataclass(frozen=True)
class CaseResult:
    """How the search did on one case."""

    case: Case
    answered: tuple[str, ...]               # the document numbers returned, best first. Empty when the search asked for more
    top1_correct: bool
    in_top5: bool
    wrong_match: bool


def read_cases(test_set: Path = TEST_SET, extracted: Path = EXTRACTED) -> list[Case]:
    """The cases of the test set, each joined to its saved extraction by case_id."""
    with extracted.open(newline="") as handle:
        fields = {row["case_id"]: row for row in csv.DictReader(handle)}
    cases = []
    with test_set.open(newline="") as handle:
        for row in csv.DictReader(handle):
            extraction = fields[row["case_id"]]                    # a case with no extraction is an error, not a skip
            cases.append(Case(
                case_id=int(row["case_id"]), case_group=row["case_group"],
                expected_document_number=row["expected_document_number"],
                business_name=extraction["business_name"], city=extraction["city"],
                is_specific=extraction["is_specific"] == "True",   # extract.py writes Python's True or False as text
            ))
    return cases


def score_case(case: Case, answered: list[str]) -> CaseResult:
    """Score one case from the document numbers the search returned (none when it asked for more)."""
    if case.expected_document_number == ASK:                       # the right behavior is to ask
        correct = not case.is_specific
        return CaseResult(case, tuple(answered), top1_correct=correct, in_top5=correct, wrong_match=bool(answered))
    return CaseResult(
        case, tuple(answered),
        top1_correct=answered[:1] == [case.expected_document_number],
        in_top5=case.expected_document_number in answered[:5],
        wrong_match=bool(answered) and answered[0] != case.expected_document_number,
    )


def run_cases(cases: list[Case], backend: SearchBackend) -> list[CaseResult]:
    """Search for every specific case and score all of them. A case that names no business is never searched."""
    results = []
    for case in cases:
        answered = [c.company.document_number for c in search(backend, case.business_name, case.city)] if case.is_specific else []
        results.append(score_case(case, answered))
    return results


def summarize(results: list[CaseResult]) -> list[tuple[str, int, int, int, int]]:
    """(group, cases, top-1 correct, in the top 5, wrong matches) for each case group, then for all cases."""
    groups = sorted({r.case.case_group for r in results})
    rows = []
    for group in groups + ["ALL"]:
        chosen = [r for r in results if group == "ALL" or r.case.case_group == group]
        rows.append((group, len(chosen), sum(r.top1_correct for r in chosen), sum(r.in_top5 for r in chosen), sum(r.wrong_match for r in chosen)))
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


def print_results(results: list[CaseResult], backend_name: str) -> None:
    """The per-case lines and the summary table."""
    print(f"\nbackend: {backend_name}")
    print(f"{'case':>4}  {'group':<22}{'expected':<16}{'answer':<16}{'top-1':<7}{'top-5':<7}{'wrong_match'}")
    for r in results:
        answer = r.answered[0] if r.answered else ASK
        print(f"{r.case.case_id:>4}  {r.case.case_group:<22}{r.case.expected_document_number:<16}{answer:<16}"
              f"{'yes' if r.top1_correct else 'no':<7}{'yes' if r.in_top5 else 'no':<7}{'YES' if r.wrong_match else 'no'}")
    print(f"\n{'group':<24}{'cases':>6}{'top-1':>7}{'recall@5':>10}{'wrong_match':>13}")
    for group, cases, top1, top5, wrong in summarize(results):
        print(f"{group:<24}{cases:>6}{top1:>7}{top5:>10}{wrong:>13}")


def time_searches(backend: SearchBackend, inputs: list[tuple[str, str]]) -> list[float]:
    """Seconds taken by each search, both steps included."""
    seconds = []
    for business_name, city in inputs:
        started = time.perf_counter()                              # a clock for measuring durations
        search(backend, business_name, city)
        seconds.append(time.perf_counter() - started)
    return seconds


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the search against the hand-checked test set.")
    parser.add_argument("--backend", choices=("postgres", "snowflake"), required=True, help="which database does the retrieve step")
    parser.add_argument("--latency", type=int, default=0, metavar="N", help="also time the search on the test inputs plus N random company names (postgres only)")
    parser.add_argument("--retrieve", choices=("word", "plain"), default="word", help="postgres only: word = word similarity, the search the app uses; plain = plain similarity, the first approach, for timing only")
    args = parser.parse_args(argv)
    cases = read_cases()

    if args.backend == "postgres":
        import os                           # reads the optional DATUM_PG_DSN environment variable
        import psycopg                      # the Postgres driver, imported only when it is used
        with psycopg.connect(os.environ.get("DATUM_PG_DSN", "dbname=datum_dev")) as conn:
            backend = PostgresBackend(conn) if args.retrieve == "word" else PlainSimilarityBackend(conn)
            print_results(run_cases(cases, backend), f"postgres ({args.retrieve} similarity)")
            if args.latency:
                random_names = conn.execute(
                    "select entity_name, '' from company_search tablesample bernoulli (0.01) repeatable (%s) limit %s",
                    (LATENCY_SEED, args.latency),
                ).fetchall()
                # tablesample bernoulli (0.01) reads a random 0.01% of the rows, and repeatable (42)
                # makes it the same sample every time. The names are searched and never printed.
                inputs = [(c.business_name, c.city) for c in cases if c.is_specific] + [tuple(row) for row in random_names]
                seconds = time_searches(backend, inputs)
                print(f"\nlatency over {len(inputs)} searches ({len(inputs) - len(random_names)} test inputs + {len(random_names)} random company names, pool of {CANDIDATE_POOL}):")
                print(f"  p50 {percentile(seconds, 0.50) * 1000:.0f} ms   p95 {percentile(seconds, 0.95) * 1000:.0f} ms   slowest {max(seconds) * 1000:.0f} ms")
                over = sum(1 for value in seconds if value > 1.0)
                print(f"  searches over 1 second: {over} of {len(seconds)}")
    else:
        import snowflake.connector          # Snowflake's Python driver, imported only when it is used
        conn = snowflake.connector.connect(connection_name="datum")    # the driver reads the connection's settings itself
        try:
            print_results(run_cases(cases, SnowflakeBackend(conn)), "snowflake")
        finally:
            conn.close()                    # always release the session, even after an error
    return 0


if __name__ == "__main__":                  # true only when this file is run directly
    sys.exit(main())                        # run main and pass its result to the shell
