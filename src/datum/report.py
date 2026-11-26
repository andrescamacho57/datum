"""report.py: the terminal command, from a contractor's note to a one-page report (rewritten in Phase C, leg C3).

    note ─▶ extract fields (Claude) ─▶ search_kind() ─┬▶ a business is named:     the shortlist of the name search ─┐
                                                     ├▶ no business, and a street with a house number:              ├▶ the user picks ─▶ ReportBuilder ─▶ a Markdown file
                                                     │                            the companies at that address ────┘
                                                     └▶ neither: ask for a business name or an address, and show no company

Since leg D4 (Phase D rule S18) the terminal makes the same choice as the web app, with the
same function, search_kind(), and an address search here uses the same search and prints
the same sentences as the web page. One note gets the same answer in both places.

Run from ~/datum with the virtual environment active, and Postgres running:
    python src/datum/report.py
and type the note when it asks ("ferguson ac boynton beach"). The note is NOT given after the
command: the shell keeps every command line in its history file, and the note is never kept.
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
    Two more doors are shut. The note is read at a prompt and never from the command line,
    and when the extraction step fails its error is not printed, because an error message
    can quote what it was given.
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
from datum.models import Candidate, Identification, read_extracted   # noqa: E402
from datum.report_builder import ReportBackend, ReportBuilder, address_candidate_for_page, address_counts, candidate_for_page, render_markdown   # noqa: E402
from datum.search import AddressMatches, SearchBackend, Shortlist, address_search, evidence, search_kind, search_pool, shortlist   # noqa: E402

REPORTS_DIR = REPO_ROOT / "data" / "reports"               # under data/, which git ignores
GIVE_UP = {"", "idk", "i dont know", "i don't know", "dont know", "don't know", "na", "n/a", "no", "none"}
# answers that mean "I have nothing more to add" (Enter alone counts too)
MAX_ROUNDS = 3                                              # never ask more than 3 times


def others_at_the_same_level(short: Shortlist, picked: int) -> int:
    """How many OTHER companies matched as well as the one picked (rule W7).

    At the top level the shortlist's own count is used. For the level Strong that count
    covers every candidate the search brought back, on the list or not. For Likely and
    Possible, at the top level or below it, the count is over the companies shown, and the
    sentence wording.tied_text() makes then says "on the shortlist".
    """
    level = short.levels[picked]
    same = short.tied_at_top if level == short.top_level else short.levels.count(level)
    return same - 1


def source_line(candidate: Candidate) -> str:
    """Where a shortlist line can be checked, and when it was fetched: the citation, the address and "fetched (about) <date>"."""
    source = candidate.source
    return f"{wording.LABEL_SOURCE}: {source.citation} ({source.source_url}) · {source.fetched_text}"


def show_shortlist(short: Shortlist, say: Callable[[str], None]) -> None:
    """Print the shortlist, and say so when the top answers tie or when a same-name company did not fit on it.

    Each company is turned into a page Candidate first, whose name, place and reasons are
    Facts, and each line is followed by its source and fetch date (rule W1). The terminal
    states nothing about a company that it cannot cite.
    """
    def show(candidate: Candidate, lead: str) -> None:   # one company: its level and name, its place and reasons, its source
        say(f"{lead}[{candidate.level}] {candidate.name.text}  ({candidate.document_number})" + (f"  ·  {candidate.mark.text}" if candidate.mark else ""))   # rule S10: an inactive company says so beside its name
        say("   " + "  ·  ".join(part for part in (candidate.place.text if candidate.place else "",
                                                   "; ".join(reason.text for reason in candidate.evidence)) if part))
        say("   " + source_line(candidate))

    say("")
    if short.tied_at_top > 1:               # more than one company at the top level: said first, and it says which level and how many
        say(wording.tie_text(short.tied_at_top, short.top_level) + "\n")
    for number, (level, found) in enumerate(zip(short.levels, short.candidates), start=1):
        show(candidate_for_page(found, level, short.city_given), f"{number}. ")
    if short.lower_level_above_higher:      # rule S12: the list is in rank order, so a lower level can stand above a higher one, and then the list says so once
        say(wording.search_order_text(True))
    if short.not_shown:                     # Strong candidates that are counted in the tie and did not fit on the list
        say(wording.not_shown_text(short.tied_not_shown))
        for found in short.not_shown:       # each one is shown with its reasons and its source, so the count is never a statement with nothing behind it
            show(candidate_for_page(found, "Strong", short.city_given), "   ")   # only a Strong candidate is ever in not_shown


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
        try:
            extracted = read_extracted(extract(note))   # the ONLY use of the note. From here on, the code works with the extracted fields
            business_name, city, street = extracted.business_name, extracted.city, extracted.street
            kind = search_kind(business_name, street, extracted.is_specific)   # "name", "address" or "ask": the very choice the web app makes (rule S18)
            # read_extracted is inside the try, so a reply with a field missing or of the wrong kind is handled here too.
            # search_kind() also treats a reply that calls the note specific and gives no name as naming no business.
        except Exception as error:          # any failure of the extraction step: the API is down, the key is missing, the reply is malformed
            say("\n" + wording.SEARCH_UNAVAILABLE)   # a fixed sentence, and no company is shown
            say(wording.EXTRACTION_ERROR_KIND.format(kind=type(error).__name__))
            # Only the error's class name is printed, so a wrong key does not look like a passing
            # fault. The error's message is NOT printed: its text could quote the note.
            return None
        if kind == "ask":                   # no business, and no street that begins with a house number: ask, and show no company (acceptance test A2)
            extra = ask_for_more(wording.ASK_FOR_A_BUSINESS_ON_A_PAGE)   # the web page's own question, so the two cannot drift apart
            if extra is None:
                break
            note += " " + extra
            continue
        if kind == "address":               # no business, and a street with a house number: the companies whose principal address that is (rule S18)
            path = by_address(street, city, search_backend, report_backend, ask, say, today, reports_dir)
            if path is not None:
                return path                 # done: a report was written
            extra = ask_for_more(wording.ASK_FOR_MORE)
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
                    return save_report(chosen.company.document_number, identification, report_backend, say, today, reports_dir)   # done: a report was written
        extra = ask_for_more(wording.ASK_FOR_MORE)
        if extra is None:
            break
        note += " " + extra

    say("\n" + wording.GIVING_UP)
    return None


def show_address_results(found: AddressMatches, street: str, city: str, say: Callable[[str], None]) -> int:
    """Print what an address search found, in the sentences the web page shows, and return how many companies can be picked.

    The same lines as the address page (src/datum/web/app.py, by_address), in the same order:
    what was read from the note, what was compared, how many active companies match, each
    of them with its principal address and its source, the counts of the companies that are
    not listed, the sentence of rule S16 when only inactive ones match, and rule S8's note.
    Only the ACTIVE companies are listed and can be picked (working rule S6). An address with
    too many companies, or with none, gets the page's own sentence and nothing to pick.
    """
    say("\n" + wording.READ_AS.format(fields=", ".join(
        part for part in (wording.FIELD_STREET.format(value=street), wording.FIELD_CITY.format(value=city) if city else "") if part)))
    if found.too_many:                      # an office tower, a mail drop or an agent's office: no list would help
        say(wording.ADDRESS_TOO_MANY)
        return 0
    if not (found.active or found.inactive or found.no_status):
        say(wording.address_not_found_text(city_given=bool(city)))
        return 0
    say(wording.address_compared_text(found.house_number, city_given=bool(city)))
    say(wording.count_text(len(found.active), wording.ADDRESS_ACTIVE_ONE, wording.ADDRESS_ACTIVE_MANY) or wording.ADDRESS_NO_ACTIVE)
    for number, company in enumerate(found.active, start=1):
        candidate = address_candidate_for_page(company)   # the name and the address are Facts with the company record's source (rule W1)
        say(f"{number}. {candidate.name.text}  ({candidate.document_number})")
        say(f"   {wording.LABEL_ADDRESS} {candidate.address.text}")
        say("   " + source_line(candidate))
    for fact in address_counts(found):      # each count cites the records it was made from, as on the page
        say(f"{fact.text} {wording.LABEL_SOURCE}: {fact.citation} ({fact.source_url}) · {fact.fetched_text}")
    only_inactive = wording.only_inactive_text(len(found.active), len(found.inactive))
    if only_inactive:                       # rule S16: no active company and at least one inactive one
        say(only_inactive)
    say(wording.PRINCIPAL_ADDRESS_NOTE)
    return len(found.active)


def by_address(street: str, city: str, search_backend: SearchBackend, report_backend: ReportBackend, ask: Callable[[str], str],
               say: Callable[[str], None], today: Callable[[], date], reports_dir: Path) -> Path | None:
    """The address search, from the extracted street and city: print the results, let the user pick an active company, and report on it.

    Returns the saved report's path, or None when nothing could be picked or the user typed 0.
    A company found by its address has no match level (rule S4), so there is no Possible
    question to answer before the report. The report says how the company was found and how
    many other active companies were listed with it, as on the web page.
    """
    found = address_search(search_backend, street, city)   # the search backend answers both searches: by name and by address
    listed = show_address_results(found, street, city, say)
    if not listed:
        return None
    choice = pick(listed, ask, say)
    if choice == 0:
        return None
    identification = Identification(found_by="address", street=street, city=city, tied_others=len(found.active) - 1)
    return save_report(found.active[choice - 1].document_number, identification, report_backend, say, today, reports_dir)


def save_report(document_number: str, identification: Identification, report_backend: ReportBackend,
                say: Callable[[str], None], today: Callable[[], date], reports_dir: Path) -> Path:
    """Build the report for one company, print it, save it as a Markdown file under reports_dir, and return where it was saved."""
    report = ReportBuilder(report_backend, today).build(document_number, identification)
    text = render_markdown(report)
    reports_dir.mkdir(parents=True, exist_ok=True)          # create data/reports/ if it doesn't exist
    path = reports_dir / f"{report.document_number}_{report.built_on:%Y%m%d}.md"
    path.write_text(text)                                   # save as a Markdown file
    say("\n" + text)
    say(wording.SAVED_TO.format(path=path))
    return path


def pick(count: int, ask: Callable[[str], str], say: Callable[[str], None]) -> int:
    """Ask for a number from 0 to count until the answer is valid. 0 means "add more details"."""
    while True:
        answer = ask("\n" + wording.PICK.format(count=count)).strip()
        if answer.isascii() and answer.isdigit() and 0 <= int(answer) <= count:   # plain digits only, so int() can't fail ("²" is a digit to isdigit() and not to int())
            return int(answer)
        say(wording.PICK_AGAIN.format(count=count))          # anything else: ask again instead of guessing


def read_note(arguments: list[str], ask: Callable[[str], str] = input, say: Callable[[str], None] = print) -> str:
    """Ask for the note at a prompt. Anything typed after the command is NOT used, and the user is told why."""
    if arguments:
        say(wording.NOTE_NOT_ON_COMMAND_LINE)
    return ask(wording.DESCRIBE_THE_CLIENT)


def main() -> None:
    """Command line: build the real extraction step and the two Postgres backends, then run the conversation."""
    import os                               # reads the optional DATUM_PG_DSN environment variable
    import anthropic                        # the Claude API client, imported only when the command is really run
    import psycopg                          # the Postgres driver, the same
    from datum.extract import extract_fields   # step 1, unchanged since October. Importing it loads the API key into the environment
    from datum.report_builder import PostgresReportBackend
    from datum.search import PostgresBackend

    note = read_note(sys.argv[1:])          # typed at the prompt, never taken from the command line
    claude = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY
    with psycopg.connect(os.environ.get("DATUM_PG_DSN", "dbname=datum_dev")) as conn:
        run(note, lambda text: extract_fields(claude, text), PostgresBackend(conn), PostgresReportBackend(conn))


if __name__ == "__main__":                  # true only when this file is run directly
    main()
