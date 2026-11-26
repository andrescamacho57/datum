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

# --- The summary at the top of a report (Phase D, leg D2; working rule S9) ----------------
# A contractor reads the first lines and stops. They answer "is it real, and is anything on the
# record" from facts the report shows further down, and they give no verdict. The order is the
# rule's: the status as of the day the state published the record, the entity type and the year
# of the date on record, the summary line (summary_line below), and then CONFIRMED_ONLY.
SUMMARY_STATUS = "{status} with the state as of {day}."
# "As of" the published date, and never "is active": a change after that date is not checked
# (rule W5 lists it), and a company first seen in a daily file has a later date than the snapshot.
SUMMARY_NO_STATUS = "No status with the state is on record as of {day}."
SUMMARY_TYPE_SINCE = "{entity_type}, on record since {year}."
SUMMARY_TYPE_DATE_AHEAD = "{entity_type}, with a date on record in {year}, which is in the future."
# 35 companies have a date on record that has not come yet. "On record since 2120" would be false.
SUMMARY_TYPE_NO_DATE = "{entity_type}, with no date on record."
SUMMARY_NO_TYPE = "Entity type not on record"                  # stands where the entity type would, when the state has none
HEADING_RECORDS = "The records behind this summary"            # the company record table and the two lists of sources sit under it
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

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
NAME_IGNORING = "ignoring capitals and legal endings such as LLC, INC or CORP, and reading anything that is not a letter A to Z or a digit as a space"
# Exactly what the name comparison in search.py does before it calls two names the same. It
# puts both in capitals, turns every run of characters that are not A to Z or 0 to 9 into one
# space (search.name_key), and removes the legal endings at the end (search.without_suffixes).
# The list of endings is longer than three (CO, LTD, LP, PA and others are on it), which is
# why the phrase says "such as". It does NOT say "ignoring punctuation": A.B.C becomes A B C,
# which is not ABC.
EVIDENCE_EXACT_NAME = f"name matches ({NAME_IGNORING})"
EVIDENCE_SIMILAR_NAME = "name is similar ({similarity}/100)"
EVIDENCE_CITY_MATCHES = "principal city on record begins with the city you gave"
# "Begins with", because that is the comparison (search.city_matches): PONTE VEDRA finds a
# company in PONTE VEDRA BEACH. It also means JACKSONVILLE finds one in JACKSONVILLE BEACH,
# which is another city, so the sentence may not say "city matches". The shortlist shows the
# company's city next to it. The city compared is the principal address's, the only one the table holds.
EVIDENCE_OTHER_CITY = "principal city on record is {city}, and that spelling does not begin with the city you gave"
# It used to end "not the city you gave". The comparison is one of spelling: ST AUGUSTINE does
# not begin with "St. Augustine", because of the full stop, and the old sentence then told a
# contractor the company was in another city. The sentence now says only what was compared.
# Whether the comparison itself should treat "St." and "ST" alike is question Q41.
EVIDENCE_NO_CITY = "no principal city on record for this company"   # the principal address is the only one the table holds
EVIDENCE_CITY_IN_NAME = "every word of the city you gave is in the company's name"
# Phase D rule S14 (leg D3). The extraction step reads a place out of a note as the city, also
# when the place is part of the registered name: "v pizza lake buena vista" came back as the
# business "V Pizza" and the city "Lake Buena Vista". Such a company is moved up the list, and
# this line says why. It says exactly what was compared (search.city_in_name: whole words, in
# any order, legal endings left out), and it is given BESIDE the line about the principal city,
# never in its place. It does not say the company is in that city, and it changes no match level.
EVIDENCE_ACTIVE = "ACTIVE"
EVIDENCE_INACTIVE = "INACTIVE with the state"
EVIDENCE_NO_STATUS = "status not on record"
# The nine lines above are the reasons search.evidence() gives. Eight are behind a match level:
# they were written in search.py in leg C2 and moved here unchanged, so that this file holds
# them all. EVIDENCE_CITY_IN_NAME is leg D3's, and it is behind a company's place on the list.
INACTIVE_MARK = "Inactive with the state"
# Working rule S10 (leg D2): the shortlist says this BESIDE an inactive company's name. Until
# then the only sign was the last of its reasons, EVIDENCE_INACTIVE above, which Andres did not
# see on Nov 24. On a SHORTLIST that reason is left out when the mark is shown, so the list
# says it once. Everywhere else the reason stays as it was: in the line of a report that says
# how its company was identified, and in the terminal's question about a Possible match.
# The mark is the status on the record and nothing more.
TIE_STRONG = "{count} companies match at the level Strong. Check which one you mean before you open a report."
TIE_ON_LIST = "{count} companies on this list match at the level {level}. Check which one you mean before you open a report."
# Shown ABOVE the shortlist when more than one company shares the top level (rule W7). Each
# says what it counts, as the tie sentences on a report do: at Strong every candidate the
# search brought back, at Likely and Possible the companies on the list. The sentence before
# it, from October, read "These look about equally likely ... A street or a city would help
# tell them apart": it stood under the whole list, so "these" took in companies that were not
# tied, and it asked for a city when one had been given and for a street the search never uses.
SHORTLIST_SEARCH_ORDER = "The list is in search order. The level beside each company says how much of the record agrees with what you typed."
# Phase D rule S12 (leg D3), word for word. A shortlist shows its companies in the order the
# search ranked them, and no longer best level first. The sentence is shown once, UNDER the
# list, and only when a company with a lower level stands above one with a higher level,
# because only then could the order be read as a mistake. It gives no reason to prefer one
# company: it says what the order is and what a level is.
POSSIBLE_CAUTION = "This is only a POSSIBLE match: the name is similar, and nothing else confirms it is the company you mean."
# On the shortlist under every company rated Possible, and at the top of a report whose company
# was picked at that level. The terminal has asked "Make the report anyway?" since October.
# A web page cannot ask before it opens, so it says this where the contractor will read it.
SHORTLIST_NOT_SHOWN_ONE = "1 more company matches at the level Strong and is not on this list."
SHORTLIST_NOT_SHOWN_MANY = "{count} more companies match at the level Strong and are not on this list."
# The sentence names the LEVEL, because that is exactly what is counted: the candidates rated
# Strong that did not fit on the list (search.shortlist). It does not restate what Strong means.
# Each of those companies is then shown with its own reasons, as the companies on the list are.
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
    "What you typed after the command was not used. A shell usually keeps each command line in its history file, "
    "so that text may be stored there now. Type the note below instead."
)
# It is shown only when something WAS typed after the command, so it must not say that the note
# is kept nowhere: that text may already be in the history file, and the user should know.
EXTRACTION_ERROR_KIND = "The extraction step stopped with this kind of error: {kind}."
# The kind is the error's class name, such as APIConnectionError. A class name cannot hold the
# note. The error's own message can, and so it is never printed.
SEARCH_UNAVAILABLE = "The search is unavailable right now, so no company is shown."
# It does not say "try again in a few minutes". A wrong API key does not pass in a few minutes.


# --- The web app (leg C4) -----------------------------------------------------------------
APP_NAME = "Datum"
SEARCH_HEADING = "Check a company"
SEARCH_LABEL = "Describe the client"
SEARCH_HINT = "A business name and its city, or a street address that begins with its house number."
# Rule W6: the app never asks for an owner's name. Until leg D1 this line asked for "a street or
# a city", and the search used no street (question Q42). It now says what the two searches use:
# the name search reads the name and the city, and the address search reads a street that
# begins with a house number, when the note names no business.
SEARCH_BUTTON = "Search"
SEARCH_AGAIN = "Search again"
SHORTLIST_HEADING = "Which company do you mean?"
NOTE_EMPTY = "Nothing was typed. Type the business's name and its city, or a street address that begins with its house number."
NOTE_TOO_LONG = "That is too long to search for. Type the business's name and its city, or a street address that begins with its house number."
ASK_FOR_A_BUSINESS_ON_A_PAGE = "That describes a business but doesn't name one. Add its name, or its street address beginning with the house number."
# Acceptance test A2. The terminal's question, ASK_FOR_A_BUSINESS above, still ends "a street or
# a city": the terminal has no search by address, so its words are left as they were.
NO_COMPANY_FOUND = "No company with a name close to that was found. Check the spelling of the business's name."
REPORT_UNAVAILABLE = "The report is unavailable right now."
REQUEST_NOT_READ = "That could not be read as a search. Type the business's name in the box."   # a form that was not sent by the search box

# --- The search by address (Phase D, leg D1; working rules S5 to S8) ------------------------
ADDRESS_HEADING = "Companies by principal address"
ADDRESS_COMPARED = (
    "A company matches when its principal address on record has the house number {house_number} "
    "and a street name made only of words you typed. The kind of street, such as ST or PKWY, and a direction, N, S, E or W, are not compared."
)
# Exactly the comparison of search.street_matches(). Every line below says "matches" and never
# "has this address", because the comparison is looser than that: 8586 PALM AVE matches
# "8586 palm pkwy", and so does a street made of fewer words than were typed. Round 1 of leg
# D1's review found that the first wording, "has this principal address", claimed more than was
# checked, above all for the companies that are counted and not shown. Each LISTED company is
# shown with its own address as the state has it, so the reader can compare.
ADDRESS_COMPARED_CITY = "Its principal city on record also begins with the city you gave."
ADDRESS_COMPARED_NO_CITY = "You gave no city, so a match can be in any city."
ADDRESS_ACTIVE_ONE = "1 active company matches."
ADDRESS_ACTIVE_MANY = "{count} active companies match. They are in document-number order, which says nothing about which one you mean."
ADDRESS_NO_ACTIVE = "No active company matches."
ADDRESS_INACTIVE_ONE = "1 inactive company also matches and is not listed."
ADDRESS_INACTIVE_MANY = "{count} inactive companies also match and are not listed."
# Rule S6: an address search lists only the active companies and says how many inactive ones
# there are, in one sentence. Whether they should be listed is Andres's call (question Q45).
ADDRESS_NO_STATUS_ONE = "1 company with no status on record also matches and is not listed."
ADDRESS_NO_STATUS_MANY = "{count} companies with no status on record also match and are not listed."
# A company with no status on record is not called inactive (CLAUDE.md rule 3). Every company has a status today.
PRINCIPAL_ADDRESS_NOTE = "A company's principal address is the address it gave the state, which is not always where it does business."
# Rule S8, word for word: once, under the results of every address search.
ADDRESS_NOT_FOUND = (
    "No company matches: none has a principal address on record with that house number and a street name made only of words you typed. "
    "Check the house number and the spelling of the street's name, and add the suite or unit if the address has one."
)
ADDRESS_NOT_FOUND_IN_CITY = (
    "No company matches: none has a principal address on record with that house number, a street name made only of words you typed, "
    "and a principal city that begins with the city you gave. "
    "Check the house number, the spelling of the street's name and the city, and add the suite or unit if the address has one."
)
# Each says what was compared, so that it does not read as "no company is at this address". A
# record that holds a suite only matches when the suite was typed too (question Q47). The
# second is shown when a city was read from the note: the city is then part of the comparison,
# and a company with that house number and street in ANOTHER city is not a match. Round 2 of
# leg D1's review found that one sentence for both cases denied such a company's record.
ADDRESS_TOO_MANY = "That house number and street name are on the records of too many companies to list them. Add the business's name."
# It gives no count. The search stops reading at a limit, before the city is compared, so it
# cannot say how many companies there are, and a sentence with a number would need a source.
COMPANY_RECORDS_CITATION = "Florida Division of Corporations (Sunbiz) company records"
# What a count of companies cites. One company cites its own record, with its document number.
IDENTIFIED_BY_ADDRESS = (
    "from {fields} · found by its principal address on record (the same house number, and a street name made only of words that were typed) "
    "· chosen by the user from the active companies listed."
)
ADDRESS_OTHERS_ONE = "1 other active company was listed with it."
ADDRESS_OTHERS_MANY = "{count} other active companies were listed with it."
# Rule W7 for an address: every company on the list matched equally, so the report of whichever
# one was picked says how many others were on it. No match level is given, because rule S4
# keeps the three levels for the name search.

NOT_FOUND_HEADING = "Not found"
NOT_FOUND = "Nothing was found at this address."
# One sentence for every 404, whether the address is unknown, the document number has the
# wrong shape or no company has it. It never repeats what was typed into the address.


def day_text(value: date | datetime) -> str:
    """A date the way every page writes it: 2026-11-24. A fetch time is shown as its UTC date."""
    return value.strftime("%Y-%m-%d")


def long_day_text(value: date) -> str:
    """A date the way the summary writes it: Oct 7, 2026. The month names are spelled here, so the text does not depend on the machine's language."""
    return f"{MONTHS[value.month - 1]} {value.day}, {value.year}"


def summary_status_text(status: str | None, published_on: date) -> str:
    """The summary's first sentence: the status with the state as of the day the record was published. `status` is None when the state has none."""
    day = long_day_text(published_on)
    return SUMMARY_STATUS.format(status=status, day=day) if status else SUMMARY_NO_STATUS.format(day=day)


def summary_record_text(entity_type: str | None, on_record: date | None, built_on: date) -> str:
    """The summary's second sentence: the entity type and the year of the date on record. A gap is said, and a date still to come is not called "since"."""
    entity_type = entity_type or SUMMARY_NO_TYPE
    if on_record is None:
        return SUMMARY_TYPE_NO_DATE.format(entity_type=entity_type)
    sentence = SUMMARY_TYPE_DATE_AHEAD if on_record > built_on else SUMMARY_TYPE_SINCE
    return sentence.format(entity_type=entity_type, year=on_record.year)


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


def tie_text(count: int, level: str | None) -> str:
    """The line above a shortlist whose top level is shared by `count` companies (rule W7). Empty when there is no tie."""
    if count <= 1 or level is None:
        return ""
    return TIE_STRONG.format(count=count) if level == "Strong" else TIE_ON_LIST.format(count=count, level=level)


def search_order_text(lower_level_above_higher: bool) -> str:
    """The line under a shortlist that says its order is the search's (rule S12). Empty when the levels already go from best to worst."""
    return SHORTLIST_SEARCH_ORDER if lower_level_above_higher else ""


def not_shown_text(count: int) -> str:
    """The shortlist's line for the Strong candidates it counts and does not list. Empty when there are none."""
    if count <= 0:
        return ""
    return SHORTLIST_NOT_SHOWN_ONE if count == 1 else SHORTLIST_NOT_SHOWN_MANY.format(count=count)


def count_text(count: int, one: str, many: str) -> str:
    """One of two sentences about a count of companies: `one` for 1, `many` with the number filled in for more. Empty for none."""
    if count <= 0:
        return ""
    return one if count == 1 else many.format(count=count)


def address_compared_text(house_number: str, city_given: bool) -> str:
    """The sentence that says what an address search compared, and a second one about the city: compared, or not given."""
    return f"{ADDRESS_COMPARED.format(house_number=house_number)} {ADDRESS_COMPARED_CITY if city_given else ADDRESS_COMPARED_NO_CITY}"


def address_not_found_text(city_given: bool) -> str:
    """The sentence for an address search that matched nobody. It names the city as one of the things compared only when one was given."""
    return ADDRESS_NOT_FOUND_IN_CITY if city_given else ADDRESS_NOT_FOUND


def identified_by_address_text(street: str, city: str, others_listed: int) -> str:
    """The identification line of a company picked from an address search, built from the EXTRACTED street and city only (rule W6)."""
    fields = [FIELD_STREET.format(value=street)]
    if city:
        fields.append(FIELD_CITY.format(value=city))
    line = IDENTIFIED_BY_ADDRESS.format(fields=", ".join(fields))
    others = count_text(others_listed, ADDRESS_OTHERS_ONE, ADDRESS_OTHERS_MANY)
    return f"{line} {others}" if others else line


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
