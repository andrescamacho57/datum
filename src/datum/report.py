"""report.py: the terminal command, from a contractor's note to a one-page report (rewritten in Phase C, leg C3).

    note ─▶ extract fields (Claude) ─▶ shortlist (Postgres) ─▶ the user picks ─▶ ReportBuilder ─▶ a Markdown file

Run from ~/datum with the virtual environment active, and Postgres running:
    python src/datum/report.py "ferguson ac boynton beach"
Needs: ANTHROPIC_API_KEY in the environment (the extraction step is one call to the Claude
API), and the local Postgres database datum_dev that src/datum/load_postgres.py fills.

This file is a THIN WRAPPER. It asks, it prints and it saves, and that is all:
  - the search is datum.search (the same functions the web app uses),
  - the report is built by datum.report_builder.ReportBuilder (the same builder the web app uses),
  - every sentence it prints is in datum.wording.
So the terminal and the web app cannot drift apart: there is one place where a report is
built and one place where its words are written.

Three things the version before leg C3 did, and this one does not:
  - It read Snowflake for every search. This one reads Postgres (decision d18).
  - It wrote the typed note into the saved report, and asked for an owner's name. The note
    is now used for the extraction call and nothing else: it is not printed back, not saved
    and not passed to the report (working rule W6). Nothing here asks for an owner's name.
  - It wrote "Strong" for a company that had tied with another. A tie is now said on the
    shortlist and on the report (working rule W7).
"""

import sys                                  # the note from the command line, and the import path
from collections.abc import Callable        # the type of the functions passed in: extract, ask, say, today
from datetime import date                   # today's date, for the report and its file name
from pathlib import Path                    # file paths that work on any operating system

REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/report.py → go up 2 folders to the repo root
sys.path.insert(0, str(REPO_ROOT / "src"))                 # so `import datum.search` works when this file is run as a script

from datum import wording                                   # noqa: E402  (the path line above has to come first)
from datum.models import Identification                     # noqa: E402
from datum.report_builder import ReportBackend, ReportBuilder, render_markdown   # noqa: E402
from datum.search import SearchBackend, Shortlist, evidence, search_pool, shortlist   # noqa: E402

REPORTS_DIR = REPO_ROOT / "data" / "reports"               # under data/, which git ignores
GIVE_UP = {"", "idk", "i dont know", "i don't know", "dont know", "don't know", "na", "n/a", "no", "none"}
# answers that mean "I have nothing more to add" (Enter alone counts too)
MAX_ROUNDS = 3                                              # never ask more than 3 times


def others_at_the_same_level(short: Shortlist, picked: int) -> int:
    """How many OTHER companies matched as well as the one picked (rule W7).

    At the top level the shortlist's own count is used, because for a same-name match it
    also covers companies that did not fit on the list. Below the top level the count is
    over the companies shown.
    """
    level = short.levels[picked]
    same = short.tied_at_top if level == short.top_level else short.levels.count(level)
    return same - 1


def show_shortlist(short: Shortlist, say: Callable[[str], None]) -> None:
    """Print the shortlist, and say so when the top answers tie or when a same-name company did not fit on it."""
    say("")
    for number, (level, candidate) in enumerate(zip(short.levels, short.candidates), start=1):
        company = candidate.company
        place = ", ".join(part for part in (company.principal_city, company.principal_state) if part)
        say(f"{number}. [{level}] {company.entity_name}  ({company.document_number})")
        say("   " + "  ·  ".join(part for part in (place, "; ".join(evidence(candidate, short.city_given))) if part))
    if short.tied_at_top > 1:               # more than one company at the top level
        say("\n" + wording.SHORTLIST_TIE)
    if short.not_shown:                     # same-name companies that are counted in the tie and did not fit on the list
        say(wording.not_shown_text(short.tied_not_shown))
        for candidate in short.not_shown:   # each one is named, so the count above is never a statement with nothing behind it
            say(f"   {candidate.company.entity_name}  ({candidate.company.document_number})")


def run(note: str, extract: Callable[[str], dict], search_backend: SearchBackend, report_backend: ReportBackend,
        ask: Callable[[str], str] = input, say: Callable[[str], None] = print,
        today: Callable[[], date] = date.today, reports_dir: Path = REPORTS_DIR) -> Path | None:
    """The whole conversation. Returns the saved report's path, or None when no company could be identified.

    Everything it depends on is passed in: the extraction step, the two backends, how to ask
    and how to print. The tests pass in fakes, so they need no API key, no database and no
    keyboard. That pattern is called dependency injection.
    """
    def ask_for_more(prompt: str) -> str | None:
        extra = ask(prompt + wording.PRESS_ENTER).strip()
        return None if extra.lower() in GIVE_UP else extra                 # None = stop asking

    for _ in range(MAX_ROUNDS):             # at most 3 rounds of "tell me more"
        fields = extract(note)              # the ONLY use of the note. From here on, the code works with the extracted fields
        business_name, city, street = fields["business_name"], fields["city"] or "", fields["street"] or ""
        if not fields["is_specific"]:       # a vague note: ask, and show no company (acceptance test A2)
            extra = ask_for_more(wording.ASK_FOR_A_BUSINESS)
            if extra is None:
                break
            note += " " + extra
            continue
        say("\n" + wording.READ_AS.format(fields=", ".join(
            part for part in (wording.FIELD_BUSINESS_NAME.format(value=business_name),
                              wording.FIELD_CITY.format(value=city) if city else "",
                              wording.FIELD_STREET.format(value=street) if street else "") if part)))
        short = shortlist(search_pool(search_backend, business_name, city), city_given=bool(city))
        if short.candidates:
            show_shortlist(short, say)
            choice = pick(len(short.candidates), ask, say)
            if choice > 0:
                chosen, level = short.candidates[choice - 1], short.levels[choice - 1]
                reasons = evidence(chosen, short.city_given)
                confirmed = level != "Possible" or ask("\n" + wording.POSSIBLE_ONLY.format(evidence="; ".join(reasons))).strip().lower() == "y"
                # (y/N) convention: capital N = the default if you just press Enter
                if confirmed:
                    identification = Identification(
                        business_name=business_name, city=city, street=street, level=level, evidence=tuple(reasons),
                        tied_others=others_at_the_same_level(short, choice - 1),
                    )
                    report = ReportBuilder(report_backend, today).build(chosen.company.document_number, identification)
                    text = render_markdown(report)
                    reports_dir.mkdir(parents=True, exist_ok=True)          # create data/reports/ if it doesn't exist
                    path = reports_dir / f"{report.document_number}_{report.built_on:%Y%m%d}.md"
                    path.write_text(text)   # save as a Markdown file
                    say("\n" + text)
                    say(wording.SAVED_TO.format(path=path))
                    return path             # done: a report was written
        extra = ask_for_more(wording.ASK_FOR_MORE)
        if extra is None:
            break
        note += " " + extra

    say("\n" + wording.GIVING_UP)
    return None


def pick(count: int, ask: Callable[[str], str], say: Callable[[str], None]) -> int:
    """Ask for a number from 0 to count until the answer is valid. 0 means "add more details"."""
    while True:
        answer = ask("\n" + wording.PICK.format(count=count)).strip()
        if answer.isdigit() and 0 <= int(answer) <= count:   # isdigit(): only digits, so int() can't fail
            return int(answer)
        say(wording.PICK_AGAIN.format(count=count))          # anything else: ask again instead of guessing


def main() -> None:
    """Command line: build the real extraction step and the two Postgres backends, then run the conversation."""
    import os                               # reads the optional DATUM_PG_DSN environment variable
    import anthropic                        # the Claude API client, imported only when the command is really run
    import psycopg                          # the Postgres driver, the same
    from datum.extract import extract_fields   # step 1, unchanged since October. Importing it loads the API key into the environment
    from datum.report_builder import PostgresReportBackend
    from datum.search import PostgresBackend

    note = " ".join(sys.argv[1:]) or input(wording.DESCRIBE_THE_CLIENT)   # the note from the command line, or ask
    claude = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY
    with psycopg.connect(os.environ.get("DATUM_PG_DSN", "dbname=datum_dev")) as conn:
        run(note, lambda text: extract_fields(claude, text), PostgresBackend(conn), PostgresReportBackend(conn))


if __name__ == "__main__":                  # true only when this file is run directly
    main()
