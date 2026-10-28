"""report.py: Datum's first end-to-end flow, from a contractor's note to a one-page report.

    note -> extract fields (Claude) -> shortlist of 5 (Snowflake) -> contractor picks -> report

Run from ~/datum with the virtual environment active:
    python src/datum/report.py "ferguson ac boynton beach"
Needs: ANTHROPIC_API_KEY in the environment, and the `datum` connection in
~/.snowflake/connections.toml (the same one the snow CLI uses).

Confidence is shown as a LEVEL with its evidence, not a percentage: a percentage would claim
"right N% of the time", and we can't back that up until the test set is much bigger.
"""

import sys                                  # read the note from the command line
from datetime import date                   # today's date for the report header
from pathlib import Path                    # file paths that work on any operating system
from urllib.parse import quote_plus         # make a company name safe to put in a web link

import anthropic                            # Claude API SDK (used by the extraction step)
import snowflake.connector                  # Snowflake's Python driver: runs SQL from Python

from extract import extract_fields          # reuse step 1 from extract.py (same folder)

REPO_ROOT = Path(__file__).resolve().parents[2]            # ~/datum
REPORTS_DIR = REPO_ROOT / "data" / "reports"               # under data/, which git ignores

SUFFIX_PATTERN = r"( (L L C|LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LP|LLP|LLLP|PA|PLLC))+$"
# trailing legal suffixes, removed from BOTH sides before the exact-name comparison

FILING_TYPES = {                            # plain-English labels for the codes we've seen (🟡 from samples)
    "FLAL": "Florida limited liability company (LLC)",
    "DOMP": "Florida corporation (for profit)",
    "DOMNP": "Florida nonprofit corporation",
    "DOMLP": "Florida limited partnership",
    "FORP": "Out-of-state corporation registered in Florida",
    "FORL": "Out-of-state LLC registered in Florida",
    "FORNP": "Out-of-state nonprofit registered in Florida",
}

# One query does the whole search. %(name)s and %(city)s are PLACEHOLDERS: the driver fills
# them in safely (never paste user text straight into SQL: that's how SQL injection happens).
# A literal % in SQL must be written %% because % marks a placeholder here.
SEARCH_SQL = """
WITH q AS (
    SELECT TRIM(REGEXP_REPLACE(UPPER(%(name)s), '[^A-Z0-9]+', ' ')) AS search_key,
           UPPER(TRIM(%(city)s))                                    AS city_key
)
SELECT e.document_number, e.entity_name, e.status_code, e.filing_type,
       e.principal_address_1, e.principal_city, e.principal_state, e.principal_zip,
       e.file_date, e.published_on,
       JAROWINKLER_SIMILARITY(q.search_key, e.name_key) AS similarity,
       IFF(q.city_key <> '' AND UPPER(e.principal_city) LIKE q.city_key || '%%', 1, 0) AS city_match,
       IFF(REGEXP_REPLACE(e.name_key, %(suffix)s, '') = REGEXP_REPLACE(q.search_key, %(suffix)s, ''),
           1, 0) AS exact_name
FROM datum.dev_marts.entity_lookup e
CROSS JOIN q
ORDER BY similarity DESC, city_match DESC, e.document_number
LIMIT 5
"""


def search(conn, fields: dict) -> list[dict]:
    """Return the top 5 candidate companies for the extracted fields."""
    cur = conn.cursor(snowflake.connector.DictCursor)       # rows come back as dicts: row["ENTITY_NAME"]
    cur.execute(SEARCH_SQL, {                               # run the query with the placeholders filled
        "name": fields["business_name"],
        "city": fields["city"] or "",                       # empty string when no city was given
        "suffix": SUFFIX_PATTERN,
    })
    return cur.fetchall()                                   # list of 5 dicts


def confidence(c: dict, city_given: bool) -> str:
    """Turn evidence into a level. Rules, not tuned numbers, so they're easy to explain."""
    if c["EXACT_NAME"] and (not city_given or c["CITY_MATCH"]):
        return "Strong"                                     # same name, and the city agrees (or none given)
    if c["EXACT_NAME"] or c["CITY_MATCH"]:
        return "Likely"                                     # one of the two signals
    return "Possible"                                       # only a similar-looking name


def evidence(c: dict, city_given: bool) -> list[str]:
    """The reasons behind the level, in words the contractor can check."""
    reasons = ["name matches exactly (ignoring LLC/INC)" if c["EXACT_NAME"]
               else f"name is similar ({c['SIMILARITY']}/100)"]
    if city_given:
        reasons.append("city matches" if c["CITY_MATCH"]
                       else f"registered in {c['PRINCIPAL_CITY']}, not the city you gave")
    reasons.append("ACTIVE" if c["STATUS_CODE"] == "A" else "INACTIVE with the state")
    return reasons


def show_shortlist(candidates: list[dict], city_given: bool) -> None:
    """Print the ranked shortlist, and say so honestly when the top answers tie."""
    order = {"Strong": 0, "Likely": 1, "Possible": 2}       # for sorting by level
    levels = [confidence(c, city_given) for c in candidates]
    ranked = sorted(zip(levels, candidates), key=lambda pair: order[pair[0]])  # stable: keeps similarity order within a level
    candidates[:] = [c for _, c in ranked]                  # re-order the caller's list in place to match what's shown
    print()
    for i, (level, c) in enumerate(ranked, start=1):
        print(f"{i}. [{level}] {c['ENTITY_NAME']}  ({c['DOCUMENT_NUMBER']})")
        print(f"   {c['PRINCIPAL_CITY']}, {c['PRINCIPAL_STATE']}  ·  " + "; ".join(evidence(c, city_given)))
    best = ranked[0][0]
    if sum(1 for level, _ in ranked if level == best) > 1:  # more than one candidate at the top level
        print("\nThese look about equally likely. Is it one of these? A street, city, or an owner's"
              " name would help me tell them apart.")


def write_report(c: dict, note: str, level: str, reasons: list[str]) -> Path:
    """Build the one-page report for the chosen company, print it, and save it.
    The report records HOW the company was identified (the note, the level, the evidence),
    so anyone reading it later can judge the match, not just the facts."""
    status = "Active" if c["STATUS_CODE"] == "A" else "Inactive"
    link = ("https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults"
            f"?inquiryType=EntityName&searchTerm={quote_plus(c['ENTITY_NAME'])}")
    # Sunbiz's name search is a plain web link (GET). Detail pages need an ID that isn't in the
    # bulk file, so the link opens the name list; the document number confirms the right row.
    report = f"""# Datum company check: {c['ENTITY_NAME']}

Checked {date.today():%B %d, %Y} · Source: Florida Division of Corporations (Sunbiz), data published {c['PUBLISHED_ON']}

| | |
|---|---|
| Legal name | {c['ENTITY_NAME']} |
| Document number | {c['DOCUMENT_NUMBER']} |
| Status with the state | **{status}** |
| Entity type | {FILING_TYPES.get(c['FILING_TYPE'], c['FILING_TYPE'])} |
| Date on record | {c['FILE_DATE']} (may be an effective date; confirm on the official record) |
| Principal address | {c['PRINCIPAL_ADDRESS_1']}, {c['PRINCIPAL_CITY']}, {c['PRINCIPAL_STATE']} {c['PRINCIPAL_ZIP']} |
| Official record | [Look up on Sunbiz]({link}), then match document number {c['DOCUMENT_NUMBER']} |

**How this company was identified:** from the note "{note}" · match level **{level}** ({'; '.join(reasons)}) · chosen by the user from a shortlist.

**Not covered yet:** liens, court cases, contractor licenses, and status changes after {c['PUBLISHED_ON']}.

*Sourced public-record facts, not advice. Verify on the official record before relying on them.*
"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)          # create data/reports/ if it doesn't exist
    path = REPORTS_DIR / f"{c['DOCUMENT_NUMBER']}_{date.today():%Y%m%d}.md"
    path.write_text(report)                                 # save as a Markdown file
    print("\n" + report)
    return path


GIVE_UP = {"", "idk", "i dont know", "i don't know", "dont know", "don't know", "na", "n/a", "no", "none"}
# answers that mean "I have nothing more to add" (Enter alone counts too)
MAX_ROUNDS = 3                                              # never ask more than 3 times


def ask_for_more(prompt: str) -> str | None:
    """Ask the contractor for more detail. Return it, or None if they have nothing to add."""
    extra = input(prompt + " (press Enter if you don't know): ").strip()
    return None if extra.lower() in GIVE_UP else extra      # None = stop asking


def pick(n: int) -> int:
    """Ask for a number from 0 to n until the answer is valid. 0 means "add more details"."""
    while True:
        answer = input(f"\nPick 1-{n}, or 0 to add more details: ").strip()
        if answer.isdigit() and 0 <= int(answer) <= n:  # isdigit(): only digits, so int() can't fail
            return int(answer)
        print(f"Please type a number from 0 to {n}.")   # anything else: ask again instead of guessing


def main() -> None:
    note = " ".join(sys.argv[1:]) or input("Describe the client: ")   # note from the command line, or ask
    claude = anthropic.Anthropic()                          # reads ANTHROPIC_API_KEY
    conn = snowflake.connector.connect(connection_name="datum")      # reads ~/.snowflake/connections.toml

    for _ in range(MAX_ROUNDS):                             # at most 3 rounds of "tell me more"
        fields = extract_fields(claude, note)
        print(f"\nI read that as: {fields}")
        if not fields["is_specific"]:                       # vague note: ask instead of guessing
            extra = ask_for_more("That describes a business but doesn't name one. "
                                 "Add its name, street and city, or an owner's name")
            if extra is None:                               # nothing more to go on: stop, don't guess
                break
            note += " " + extra
            continue
        candidates = search(conn, fields)                   # 🟡 ~30-60 s: compares against 13M names
        city_given = bool(fields["city"])
        show_shortlist(candidates, city_given)
        choice = pick(len(candidates))
        if choice > 0:
            chosen = candidates[choice - 1]
            level = confidence(chosen, city_given)
            reasons = evidence(chosen, city_given)
            confirmed = level != "Possible" or input(
                f"\nThat's only a POSSIBLE match: {'; '.join(reasons)}. Nothing else confirms it's "
                "the company you mean. Make the report anyway? (y/N): ").strip().lower() == "y"
            # (y/N) convention: capital N = the default if you just press Enter
            if confirmed:
                saved = write_report(chosen, note, level, reasons)
                print(f"Saved to {saved}")
                conn.close()
                return                                      # done: a report was written
        extra = ask_for_more("Add a street, city, or an owner's name")
        if extra is None:
            break
        note += " " + extra

    print("\nI can't identify this business reliably from what I have, so I won't guess."
          " Run it again when you have its name, a street and city, or an owner's name.")
    conn.close()                                            # release the Snowflake session


if __name__ == "__main__":
    main()
