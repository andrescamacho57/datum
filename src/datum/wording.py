"""wording.py: every fixed sentence, label and heading a contractor can be shown (Phase C, leg C3).

Why one module: a reviewer who wants to know what Datum can say to a contractor reads this
file and nothing else. The report builder, the terminal command and the web app all take
their words from here. A test reads the code of the functions that lay out a report or
talk in the terminal, and it fails when one of them holds a sentence of its own.

What is NOT here, on purpose: the wording of a linked record. A federal lien or a license
is described by the mart's own columns (citation, status, status_note, caveat), exactly as
dbt wrote them, so that the text a contractor reads was reviewed with the rule that made it.

Three rules shape these words (docs/prompts/florida_master.md, section 6):
    W2  the summary line counts flags, and a report that shows a flag never says "No flags found"
    W4  a report never reassures. The words in BANNED_WORDS never appear on a page
    W6  the app never asks for an owner's name, and never shows the typed note back
"""

from datetime import date, datetime         # the types of the dates these sentences print

# --- Rule W4: words that never appear on a page ---------------------------------------
BANNED_WORDS = ("clean", "safe", "risky", "trustworthy", "reliable", "credit", "score", "recommend")
# Each one would turn a list of records into a judgment about the business. The tests look
# for them as the START of a word, so "scores" and "recommended" are caught too.

# --- The lines every report carries ---------------------------------------------------
NO_FLAGS = "No flags found in the sources checked."            # the exact line of acceptance test A8. Never "clean"
CONFIRMED_ONLY = (
    "Datum shows a record only when it can confirm that the record belongs to this company. "
    "A record filed under a similar name or at a different address is not shown."
)
# Rule W4: on EVERY report, with or without flags, in the same words. It says what the report
# cannot see, and because it never changes it hints at nothing about one company.
DISCLAIMER = "Sourced public-record facts, not advice. Verify on the official record before relying on them."
# Word for word the disclaimer report.py has printed since October.

REPORT_TITLE = "Datum company check: {name}"
BUILT_ON = "Report built {day}"

# --- The company's own record ---------------------------------------------------------
LABEL_LEGAL_NAME = "Legal name"
LABEL_DOCUMENT_NUMBER = "Document number"
LABEL_STATUS = "Status with the state"
LABEL_ENTITY_TYPE = "Entity type"
LABEL_DATE_ON_RECORD = "Date on record"
LABEL_ADDRESS = "Principal address"
LABEL_COMPANY_SOURCE = "Official record"

STATUS_ACTIVE = "Active"
STATUS_INACTIVE = "Inactive"
NOT_ON_RECORD = "Not on record"                                # a gap in the state's data is said plainly and never filled in
DATE_ON_RECORD = "{day} (may be an effective date; confirm on the official record)"   # report.py's wording, unchanged
COMPANY_CITATION = "Florida Division of Corporations (Sunbiz) record, document number {document_number}"
COMPANY_PUBLISHED = "data published {day}"

FILING_TYPES = {                            # plain-English labels for the state's codes, as report.py has had them (🟡 from samples)
    "FLAL": "Florida limited liability company (LLC)",
    "DOMP": "Florida corporation (for profit)",
    "DOMNP": "Florida nonprofit corporation",
    "DOMLP": "Florida limited partnership",
    "FORP": "Out-of-state corporation registered in Florida",
    "FORL": "Out-of-state LLC registered in Florida",
    "FORNP": "Out-of-state nonprofit registered in Florida",
}
# A code that is not in this list is shown as the state writes it. Nothing is guessed.

# --- The two flags that come from the company's own record ------------------------------
# The rule, the wording and the caveat are the flags table of docs/mvp_plan_nov8.md, section 4, word for word.
FLAG_INACTIVE_TITLE = "Inactive with the state"
FLAG_INACTIVE_TEXT = "Inactive with the Florida Division of Corporations"
FLAG_INACTIVE_CAVEAT = "Data as of the snapshot date; changes since then aren't covered until the events file is loaded"
FLAG_NEW_TITLE = "New company"
FLAG_NEW_TEXT = "On record since {day}"
FLAG_NEW_CAVEAT = "May be an effective date"
NEW_COMPANY_MONTHS = 12                     # "Date on record within 12 months", from the same table

# --- A flag card ------------------------------------------------------------------------
HEADING_FLAGS = "Flags"
LABEL_FLAG_DATE = "Date on the record"
LABEL_FLAG_STATUS = "Status"
LABEL_SOURCE = "Source"
FETCHED = "fetched {day}"
FETCHED_ABOUT = "fetched about {day}"       # rule W1: an estimated fetch time is shown with "about"

# --- Sources (rule W5) ------------------------------------------------------------------
HEADING_CHECKED = "Sources checked"
HEADING_NOT_CHECKED = "Not checked"
DATA_THROUGH = "data through {day}"
NOT_CHECKED_ALWAYS = (                      # what no table lists, because Datum has never loaded it
    "Court cases",
    "UCC (Uniform Commercial Code) filings",
    "Recorded documents in other counties",
    "Fictitious names (the names a business trades under)",
    "Changes to a company's status after the snapshot date",
)

# --- How the company was identified (rules W6 and W7) -------------------------------------
LABEL_IDENTIFIED = "How this company was identified"
IDENTIFIED_BY_SEARCH = "from {fields} · match level {level} ({evidence}) · chosen by the user from a shortlist."
IDENTIFIED_BY_NUMBER = "opened by its document number, so no match level applies."
# It does not say "no search was made". The builder cannot know that: it only knows that it
# was handed no identification.
FIELD_BUSINESS_NAME = 'the business name "{value}"'
FIELD_CITY = 'the city "{value}"'
FIELD_STREET = 'the street "{value}"'
TIED_ONE = "1 other company matched equally well."
TIED_MANY = "{count} other companies matched equally well."
TIED_ON_LIST_ONE = "1 other company on the shortlist matched equally well."
TIED_ON_LIST_MANY = "{count} other companies on the shortlist matched equally well."
# Two wordings, because the count behind them differs. At the level Strong (the same name, and
# the city agrees when one was given) every candidate the search brought back is counted. At
# the levels Likely and Possible only the companies on the shortlist are counted, and so the
# sentence says "on the shortlist". A sentence must not claim more than its count covers.

# --- The search and the shortlist (the terminal command now, the web app in leg C4) -------
EVIDENCE_EXACT_NAME = "name matches exactly (ignoring LLC/INC)"
EVIDENCE_SIMILAR_NAME = "name is similar ({similarity}/100)"
EVIDENCE_CITY_MATCHES = "city matches"
EVIDENCE_OTHER_CITY = "registered in {city}, not the city you gave"
EVIDENCE_NO_CITY = "no principal city on record for this company"   # the principal address is the only one the table holds
EVIDENCE_ACTIVE = "ACTIVE"
EVIDENCE_INACTIVE = "INACTIVE with the state"
EVIDENCE_NO_STATUS = "status not on record"
# The eight lines above are the reasons search.evidence() gives for a match level. They were
# written in search.py in leg C2 and moved here unchanged, so that this file holds them all.
SHORTLIST_TIE = "These look about equally likely. Is it one of these? A street or a city would help tell them apart."
# report.py's line, without "or an owner's name": rule W6, the app never asks for one.
SHORTLIST_NOT_SHOWN_ONE = "1 more company has this name (ignoring LLC/INC) and is not on this list."
SHORTLIST_NOT_SHOWN_MANY = "{count} more companies have this name (ignoring LLC/INC) and are not on this list."
SHORTLIST_NOT_SHOWN_IN_CITY_ONE = "1 more company has this name (ignoring LLC/INC) in the city you gave and is not on this list."
SHORTLIST_NOT_SHOWN_IN_CITY_MANY = "{count} more companies have this name (ignoring LLC/INC) in the city you gave and are not on this list."
# Two wordings here too. When a city was given, the companies counted are the ones with this
# name IN that city: a company with the same name in another city is not counted, and so the
# sentence names the city. "This name (ignoring LLC/INC)" is the comparison search.py makes.
ASK_FOR_A_BUSINESS = "That describes a business but doesn't name one. Add its name, a street or a city"
ASK_FOR_MORE = "Add a street or a city"
POSSIBLE_ONLY = (
    "That's only a POSSIBLE match: {evidence}. Nothing else confirms it's the company you mean. "
    "Make the report anyway? (y/N): "
)
GIVING_UP = (
    "I can't identify this business from what I have, so I won't guess. "
    "Run it again when you have its name, a street or a city."
)
READ_AS = "I read that as: {fields}"       # the terminal shows the EXTRACTED fields, never the note itself
PICK = "Pick 1-{count}, or 0 to add more details: "
PICK_AGAIN = "Please type a number from 0 to {count}."
PRESS_ENTER = " (press Enter if you don't know): "
SAVED_TO = "Saved to {path}"
DESCRIBE_THE_CLIENT = "Describe the client: "
NOTE_NOT_ON_COMMAND_LINE = (
    "Type the note here, not after the command. What is typed after a command is kept in the shell's history, "
    "and a note is not kept anywhere."
)
SEARCH_UNAVAILABLE = "The search is unavailable right now, so no company is shown. Try again in a few minutes."


def day_text(value: date | datetime) -> str:
    """A date the way every page writes it: 2026-11-24. A fetch time is shown as its UTC date."""
    return value.strftime("%Y-%m-%d")


def summary_line(flag_count: int, sources_checked: int) -> str:
    """The summary line (rule W2). With no flag it is exactly NO_FLAGS, and with a flag it never is."""
    if sources_checked < 1:                 # "No flags found in the sources checked" with nothing checked would be an all-clear about nothing
        raise ValueError("a summary line needs at least one source checked")
    if flag_count == 0:
        return NO_FLAGS
    flags = "1 flag found" if flag_count == 1 else f"{flag_count} flags found"
    sources = "1 source checked" if sources_checked == 1 else f"{sources_checked} sources checked"
    return f"{flags} in {sources}."


def fetched_text(fetched_at: datetime, is_approximate: bool) -> str:
    """"fetched 2026-11-18", or "fetched about 2026-10-22" when the time is an estimate (rule W1)."""
    return (FETCHED_ABOUT if is_approximate else FETCHED).format(day=day_text(fetched_at))


def tied_text(others: int, level: str) -> str:
    """How many other companies matched equally well (rule W7). Empty when there is no tie.

    The level decides the wording, because it decides what was counted: at Strong the whole
    pool of candidates, and at Likely or Possible the companies on the shortlist.
    """
    if others <= 0:
        return ""
    if level == "Strong":
        return TIED_ONE if others == 1 else TIED_MANY.format(count=others)
    return TIED_ON_LIST_ONE if others == 1 else TIED_ON_LIST_MANY.format(count=others)


def not_shown_text(count: int, city_given: bool) -> str:
    """The shortlist's line for same-name companies it counts and does not list. Empty when there are none."""
    if count <= 0:
        return ""
    if city_given:
        return SHORTLIST_NOT_SHOWN_IN_CITY_ONE if count == 1 else SHORTLIST_NOT_SHOWN_IN_CITY_MANY.format(count=count)
    return SHORTLIST_NOT_SHOWN_ONE if count == 1 else SHORTLIST_NOT_SHOWN_MANY.format(count=count)


def identified_text(business_name: str, city: str, street: str, level: str, evidence: tuple[str, ...], tied_others: int) -> str:
    """The identification line, built from the EXTRACTED fields only. The typed note is not an input (rule W6)."""
    fields = [FIELD_BUSINESS_NAME.format(value=business_name)]
    if city:
        fields.append(FIELD_CITY.format(value=city))
    if street:
        fields.append(FIELD_STREET.format(value=street))
    line = IDENTIFIED_BY_SEARCH.format(fields=", ".join(fields), level=level, evidence="; ".join(evidence))
    tied = tied_text(tied_others, level)
    return f"{line} {tied}" if tied else line
