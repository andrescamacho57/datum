"""search.py: find the company a contractor means, from an extracted business name and city (Phase C, leg C2; the order changed in Phase D, leg D1).

The search has two steps, and the split is the point of this module:

    1. RETRIEVE   ask the database for the companies whose names are nearest to the one typed.
                  This step is fast and rough. It reads an index over a narrow table of names,
                  and it brings back a pool of candidates (200 by default) out of 13 million
                  companies, each fetched in full from company_search by its document number.
    2. RERANK     put that small pool in order, in plain Python, by Phase D working rule S2:
                  first the companies whose name holds every word that was typed, then the
                  ones whose principal city agrees with the city given, then Jaro-Winkler
                  similarity, then the document number as a fixed tie-break. Keep the best five.
                  Until leg D1 the order was search version 1's
                  (snowflake/11_score_search_v1.sql): similarity first, and the city only to
                  break an exact tie. That order favoured a short name whenever the typed
                  name was short.

Step 2 can only order what step 1 brought back. A company that is not in the pool is never
ranked, whatever the order is. Leg D1's report shows a case where that decides the answer.

This pattern is called retrieve-then-rerank. A careful score over 13 million names takes
Snowflake about a minute. A careful score over 200 names takes Python a millisecond.

The database sits behind an interface, SearchBackend. The app passes in PostgresBackend,
and the tests pass in FakeBackend, so the tests run with no database and no network
(CLAUDE.md rule 4). The scoring is plain code (CLAUDE.md rule 1: anything a test can
assert is plain Python, never a model call).

Also here, because the report and the shortlist both need them: the match LEVEL (Strong,
Likely or Possible), the EVIDENCE behind it, and the count of candidates that TIE at the
top level (working rule W7: a tie is said out loud). They follow the rules src/datum/report.py
has used since October.

No names of people are involved: every name here is a registered business name.
"""

import re                                   # regular expressions, for the simplified name and the legal suffixes
from collections.abc import Callable        # the type of "a function that gives a candidate its sort key"
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from datetime import date, datetime, timezone   # the types of a company's dates and fetch time, and the UTC zone
from fractions import Fraction              # exact fractions, so a score never depends on rounding error
from typing import Protocol                 # a Protocol describes an interface: "anything with these methods"

from datum import wording                   # every sentence a contractor can be shown, the reasons for a match level included

# --- Settings -------------------------------------------------------------------------
CANDIDATE_POOL = 200                        # how many companies step 1 brings back for step 2 to score
SHORTLIST_SIZE = 5                          # how many the contractor is shown
PREFIX_WEIGHT = Fraction(1, 10)             # Winkler's bonus per shared leading letter
PREFIX_LETTERS = 4                          # the bonus counts at most this many leading letters
BONUS_FLOOR = Fraction(7, 10)               # the bonus applies only when the plain Jaro score is above this

SUFFIX_PATTERN = re.compile(r"( (L L C|LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LP|LLP|LLLP|PA|PLLC))+$")
# Trailing legal suffixes, removed from BOTH names before the exact-name comparison. This is the
# pattern report.py has used since October, unchanged. It is NOT the linking rule's suffix list
# (pipeline/macros/company_matching.sql): that one decides which company a lien belongs to, and
# this one only decides whether to call a typed name an exact match.

LEVELS = ("Strong", "Likely", "Possible")   # the three match levels, best first


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class Company:
    """One row of company_search: a company as the state has it, with where and when that was read."""

    document_number: str                    # the state's ID for the company
    entity_name: str                        # the legal name as filed
    name_key: str                           # the simplified name the search compares against
    status_code: str | None                 # A = active, I = inactive
    filing_type: str | None                 # the state's code for the kind of company
    file_date: date | None                  # the date on record with the state
    principal_address_1: str | None
    principal_city: str | None
    principal_state: str | None
    principal_zip: str | None
    published_on: date                      # the date the state published the file the row came from
    source_url: str                         # the official page to check the record on (CLAUDE.md rule 3)
    fetched_at: datetime                    # when Datum fetched that file, UTC (CLAUDE.md rule 3)
    fetched_at_is_approximate: bool         # True when that time is an estimate

    def __post_init__(self) -> None:        # runs right after __init__: refuse a company that breaks rule 3
        if "://" not in (self.source_url or ""):                   # must be a full address: scheme://host/path
            raise ValueError(f"{self.document_number}: a company needs a full source address, got {self.source_url!r}")
        offset = self.fetched_at.utcoffset() if isinstance(self.fetched_at, datetime) else None   # None when there is no time, or no time zone
        if offset is None or offset.total_seconds() != 0:          # a time with no zone is ambiguous, and one in another zone breaks the field's promise
            raise ValueError(f"{self.document_number}: fetched_at must be a time-zone-aware UTC datetime")


@dataclass(frozen=True)
class Candidate:
    """A company with the evidence that it is the one the contractor means."""

    company: Company
    similarity: int                         # Jaro-Winkler similarity of the two simplified names, 0 to 100
    city_match: bool                        # True when a city was given and the company's city starts with it
    exact_name: bool                        # True when the two names are equal once legal suffixes are removed
    every_word: bool                        # True when every word of the typed name is among the words of the company's name, legal suffixes aside


@dataclass(frozen=True)
class Shortlist:
    """What the contractor is shown: the candidates in display order, each with its level, and whether the top is a tie."""

    candidates: tuple[Candidate, ...]       # the ones shown: the best five by rank, put in order of level, best first
    levels: tuple[str, ...]                 # the level of each shown candidate, in the same order
    top_level: str | None                   # the best level found. None when there is no candidate at all
    tied_at_top: int                        # how many candidates share top_level. More than 1 is a tie (rule W7)
    not_shown: tuple[Candidate, ...]        # the candidates counted in tied_at_top that are NOT among the ones shown, in rank order
    city_given: bool                        # whether the contractor's note named a city

    # not_shown holds the companies themselves, not only how many there are. A count of
    # companies that the object does not carry would be a statement with no source behind
    # it (CLAUDE.md rule 3): a page could say "one more company has this exact name" and
    # could not name it or cite it. Only a Strong (exact-name) candidate can be here.

    @property
    def tied_not_shown(self) -> int:
        """How many of the tied candidates are not on the list shown."""
        return len(self.not_shown)


class SearchBackend(Protocol):
    """Anything that can bring back the companies whose names are nearest to a search key.

    A Protocol is an interface without inheritance: a class does not have to say it
    implements SearchBackend. It only has to have this method with this shape.
    """

    def nearest(self, search_key: str, limit: int) -> list[Company]:
        """Up to `limit` companies whose name_key is nearest to search_key. Order does not matter: the caller reranks."""
        ...


def name_key(name: str) -> str:
    """A simplified name: capitals, with every run of punctuation and spaces turned into one space.

    "Acme, L.L.C." becomes "ACME L L C". This is the same rule entity_lookup.sql uses for its
    name_key column, so a typed name and a registered name are simplified the same way.
    """
    return re.sub(r"[^A-Z0-9]+", " ", name.upper()).strip()


def jaro_winkler_similarity(left: str, right: str) -> int:
    """Jaro-Winkler similarity of two texts, as a whole number from 0 to 100.

    It returns what Snowflake's JAROWINKLER_SIMILARITY returns, which the test proves on
    name pairs captured from Snowflake (tests/fixtures/search/jarowinkler_pairs.csv). Three
    details were learned from that capture, and each has a pair in the fixture that needs it:
      - upper and lower case are the same letter
      - the result is cut down to a whole number, never rounded up (0.6667 is 66)
      - the bonus for a shared beginning is added only when the plain score is above 0.7
    Two empty texts score 0, as they do in Snowflake.

    How the plain (Jaro) score works: a letter of one text MATCHES a letter of the other when
    they are equal and no further apart than half the longer text's length, minus one. With m
    matches, and t of them out of order (counted in pairs), the score is the average of three
    fractions: m over each text's length, and (m - t) over m. Winkler's bonus then moves the
    score toward 1 for each of the first four letters the two texts share, because a typo is
    less likely at the start of a name than at its end.
    """
    left, right = left.upper(), right.upper()
    if not left or not right:
        return 0
    window = max(max(len(left), len(right)) // 2 - 1, 0)           # how far apart two equal letters may be and still match
    left_matched = [False] * len(left)
    right_matched = [False] * len(right)
    matches = 0
    for i, letter in enumerate(left):                              # for each letter on the left, the first free equal letter in its window
        for j in range(max(0, i - window), min(len(right), i + window + 1)):
            if not right_matched[j] and right[j] == letter:
                left_matched[i] = right_matched[j] = True
                matches += 1
                break
    if matches == 0:
        return 0
    left_letters = [letter for letter, used in zip(left, left_matched) if used]      # the matched letters, in each text's own order
    right_letters = [letter for letter, used in zip(right, right_matched) if used]
    transpositions = sum(a != b for a, b in zip(left_letters, right_letters)) // 2   # each swapped pair shows up twice
    jaro = (Fraction(matches, len(left)) + Fraction(matches, len(right)) + Fraction(matches - transpositions, matches)) / 3
    score = jaro
    if jaro > BONUS_FLOOR:
        prefix = 0
        for a, b in zip(left[:PREFIX_LETTERS], right[:PREFIX_LETTERS]):   # count the shared leading letters, 4 at most
            if a != b:
                break
            prefix += 1
        score = jaro + prefix * PREFIX_WEIGHT * (1 - jaro)
    return int(score * 100)                                        # int() cuts a fraction down to the whole number below it


def city_matches(given_city: str, company_city: str | None) -> bool:
    """True when a city was given and the company's city starts with it ("PONTE VEDRA" matches "PONTE VEDRA BEACH")."""
    wanted = given_city.strip().upper()
    return bool(wanted) and (company_city or "").upper().startswith(wanted)


def without_suffixes(key: str) -> str:
    """A simplified name with its trailing legal suffixes removed, for the exact-name comparison."""
    return SUFFIX_PATTERN.sub("", key)


def holds_every_word(search_key: str, company_key: str) -> bool:
    """True when every word of the typed name is among the words of the company's name, with trailing legal suffixes left out of both.

    "V PIZZA" is held by "V PIZZA LAKE BUENA VISTA LLC": both of its words are there. It is
    not held by "VA PIZZA LLC". Whole words are compared, so ROOFING is not held by ROOFINGS.
    A typed name that is nothing but a legal suffix, such as "LLC", keeps its words, as it
    does in the index lookup: there would otherwise be no word left to look for.
    """
    typed = (without_suffixes(search_key) or search_key).split()
    words = set((without_suffixes(company_key) or company_key).split())
    return bool(typed) and all(word in words for word in typed)


def by_words_then_city(candidate: Candidate) -> tuple:
    """Working rule S2, as a sort key. Python sorts tuples left to right, and False sorts before True.

      1. a company whose name holds every typed word comes first ("not every_word" is False for it);
      2. then a company whose principal city agrees with the city given;
      3. then the higher Jaro-Winkler similarity (the minus sign puts 95 before 88);
      4. then the document number, a fixed order, so a rerun can never flip two equal candidates.

    Status is not in the key, on purpose. An inactive company is neither moved up nor down:
    ranking active companies first would hide a dissolved client behind an active namesake.
    The extraction step returns no ZIP code, so none is compared.
    """
    return (not candidate.every_word, not candidate.city_match, -candidate.similarity, candidate.company.document_number)


def rank(companies: list[Company], business_name: str, city: str = "", limit: int | None = SHORTLIST_SIZE,
         order: Callable[[Candidate], tuple] = by_words_then_city) -> list[Candidate]:
    """Step 2: score a pool of companies against the typed name and keep the best `limit` (all of them when limit is None).

    The order is working rule S2's, by_words_then_city above. City is a rank and never a
    filter: a company in another city is still returned, lower down, because a company's
    registered city is its principal address, which can differ from the job site.
    `order` exists so that the evaluation can sort the same pool the way search version 1
    did and show the two side by side. The app never passes it.
    """
    search_key = name_key(business_name)
    candidates = [
        Candidate(
            company=company,
            similarity=jaro_winkler_similarity(search_key, company.name_key),
            city_match=city_matches(city, company.principal_city),
            exact_name=without_suffixes(company.name_key) == without_suffixes(search_key),
            every_word=holds_every_word(search_key, company.name_key),
        )
        for company in companies
    ]
    candidates.sort(key=order)
    return candidates[:limit]                                      # a slice up to None is the whole list


def search_pool(backend: SearchBackend, business_name: str, city: str = "", pool: int = CANDIDATE_POOL,
                order: Callable[[Candidate], tuple] = by_words_then_city) -> list[Candidate]:
    """Both steps, keeping the WHOLE reranked pool. The shortlist is built from this, so that it can see every tie."""
    search_key = name_key(business_name)
    if not search_key:                                             # nothing to search for: no candidates, and no guess
        return []
    return rank(backend.nearest(search_key, pool), business_name, city, limit=None, order=order)


def search(backend: SearchBackend, business_name: str, city: str = "", limit: int = SHORTLIST_SIZE, pool: int = CANDIDATE_POOL) -> list[Candidate]:
    """Both steps, keeping the best `limit` candidates in rank order. This is what the evaluation scores (search version 1's top five)."""
    return search_pool(backend, business_name, city, pool)[:limit]


def match_level(candidate: Candidate, city_given: bool) -> str:
    """Turn the evidence into a level. Rules, not tuned numbers, so they are easy to explain.

    Strong    the same name, and the city agrees (or no city was given)
    Likely    one of the two signals
    Possible  only a similar-looking name
    A level is shown with its evidence and never as a percentage: a percentage would claim
    "right N% of the time", and nothing measured backs that up.
    """
    if candidate.exact_name and (not city_given or candidate.city_match):
        return "Strong"
    if candidate.exact_name or candidate.city_match:
        return "Likely"
    return "Possible"


def evidence(candidate: Candidate, city_given: bool) -> list[str]:
    """The reasons behind the level, in words the contractor can check: the name, the city when one was given, and the status.

    These are the three reasons report.py has given since October. Two gaps in the data are
    said plainly and never filled in (CLAUDE.md rule 3): a company with no principal city on
    record is not "registered in None", and a company with no status on record is not called inactive.
    The words themselves live in wording.py, with every other sentence a contractor can be shown.
    """
    reasons = [wording.EVIDENCE_EXACT_NAME if candidate.exact_name
               else wording.EVIDENCE_SIMILAR_NAME.format(similarity=candidate.similarity)]
    if city_given:
        if candidate.city_match:
            reasons.append(wording.EVIDENCE_CITY_MATCHES)
        elif candidate.company.principal_city:
            reasons.append(wording.EVIDENCE_OTHER_CITY.format(city=candidate.company.principal_city))
        else:
            reasons.append(wording.EVIDENCE_NO_CITY)
    status = candidate.company.status_code
    reasons.append(wording.EVIDENCE_ACTIVE if status == "A" else wording.EVIDENCE_INACTIVE if status == "I" else wording.EVIDENCE_NO_STATUS)
    return reasons


def shortlist(pool: list[Candidate], city_given: bool, limit: int = SHORTLIST_SIZE) -> Shortlist:
    """Pick the candidates to show from a ranked pool, put them in display order, and count the tie at the top (working rule W7).

    `pool` is the whole reranked pool from search_pool(), in rank order.

    WHO IS SHOWN: the best `limit` by rank, which are exactly the candidates the evaluation
    scores, re-ordered by level with the best level first. Python's sort is stable, which
    means candidates with the same level keep their rank order. Nobody is brought in from
    further down the pool. Who is among the best five is decided by rank() alone, and the
    level only orders those five.

    HOW THE TIE IS COUNTED:
      - Strong means the SAME NAME (and the city agrees, or none was given). Those are
        counted over the WHOLE pool, because a company with the exact name can rank sixth,
        behind five longer names that hold the same words and score higher, and a count
        over the five shown would miss it. not_shown holds the ones that did not fit on the
        list, each with its own source address and fetch time, so a page can name them and
        cite them.
      - Likely and Possible are counted among the candidates shown only. Over the whole
        pool those counts would mostly measure how wide the retrieve step cast its net,
        and that says nothing about the companies.
    The two review rounds of leg C2 found one gap each in earlier versions of this function.
    """
    shown = sorted(((match_level(c, city_given), c) for c in pool[:limit]), key=lambda pair: LEVELS.index(pair[0]))
    levels = tuple(level for level, _ in shown)
    strong_further_down = tuple(c for c in pool[limit:] if match_level(c, city_given) == "Strong")   # same-name companies that did not fit on the list
    strong_shown = levels.count("Strong")
    if strong_shown or strong_further_down:
        top_level, tied = "Strong", strong_shown + len(strong_further_down)
    else:
        top_level = levels[0] if levels else None
        tied = levels.count(top_level) if levels else 0
    return Shortlist(
        candidates=tuple(c for _, c in shown), levels=levels,
        top_level=top_level, tied_at_top=tied, not_shown=strong_further_down, city_given=city_given,
    )


COMPANY_COLUMNS = (                         # the columns of company_search, in the order Company's fields are declared
    "document_number", "entity_name", "name_key", "status_code", "filing_type", "file_date",
    "principal_address_1", "principal_city", "principal_state", "principal_zip",
    "published_on", "source_url", "fetched_at", "fetched_at_is_approximate",
)


class PostgresBackend:
    """Step 1 against Postgres: the names that CONTAIN something close to the typed name, read from the trigram index.

    A trigram is a run of three characters. pg_trgm, a Postgres extension, cuts every name
    into its trigrams, and the loader builds an index that lists, for each trigram, the
    names that hold it.

    The names are searched in company_search_names, the NARROW table the loader builds: one
    row per company, holding its document number and its simplified name and nothing else.
    The index only says which rows MIGHT match, so Postgres has to open each of those rows to
    check it, and for a name made of common words that is thousands of rows. Opening them in
    a table of 0.85 GB whose rows are in name order reads far fewer pages than opening them
    in company_search, which is 3 GB with the rows in no useful order. The 200 companies
    that are kept are then read in full from company_search, by document number, so every
    Company still carries its source address and fetch time. The loader refuses to swap the
    tables in unless both hold the same companies. Leg C2's report has the timings of this
    approach and of the two before it.

    The comparison is WORD SIMILARITY, the operator <%. It asks whether the typed name is
    close to some stretch of the registered name, so "CINEMARK" is a full match inside
    "CINEMARK USA INC". Plain trigram similarity (the operator %) compares the two whole
    texts, which punishes a registered name for being longer than what was typed, and a
    contractor nearly always types less than the legal name.

    Why the threshold is high (0.75): the index can only skip its longest lists (the
    trigrams of common words such as ING or FLORIDA) when a match needs most of the typed
    trigrams. At the default threshold of plain similarity (0.3) Postgres reads every one
    of those lists and then fetches about 100,000 rows to check them, which took 7 to 10
    seconds a search on this data. The leg report of leg C2 has both measurements.

    The trailing legal suffix is left out of what is sent to the index. LLC and INC are in
    millions of names, so their trigrams cost the most and tell nothing apart. The rerank
    step still scores the full typed name.
    """

    WORD_SIMILARITY_THRESHOLD = 0.75        # how close a stretch of a registered name must be to the typed name
    WORK_MEMORY = "64MB"                    # room for this session to hold the list of matching rows exactly, not page by page

    NEAREST_SQL = (
        f"select {', '.join('c.' + column for column in COMPANY_COLUMNS)} "
        "from (select document_number from company_search_names "
        "where %(key)s <%% name_key "
        "order by name_key <-> %(key)s, document_number "
        "limit %(limit)s) as nearest "
        "join company_search as c using (document_number)"
    )
    # The part in brackets is a SUBQUERY: it runs first, against the narrow table, and gives back
    # the document numbers of the nearest names. The join then looks each of those numbers up in
    # company_search through its primary key, which is one quick lookup per company.
    # %(key)s and %(limit)s are PLACEHOLDERS: the driver sends the values apart from the SQL, so
    # nothing a contractor types can ever be read as SQL (that is how SQL injection is prevented).
    # The operator is <% ("is word-similar to"), and because % also marks a placeholder here, a
    # literal one is typed twice. <-> is the plain trigram DISTANCE between two texts (0 = the
    # same trigrams), so among the names that pass, the ones closest to the typed name as a
    # whole come first, and the document number settles a tie the same way on every run.

    def __init__(self, conn):
        self.conn = conn                    # an open psycopg connection
        conn.execute("select set_config('pg_trgm.word_similarity_threshold', %s, false)", (str(self.WORD_SIMILARITY_THRESHOLD),))
        conn.execute("select set_config('work_mem', %s, false)", (self.WORK_MEMORY,))
        conn.execute("select set_config('TimeZone', %s, false)", ("UTC",))
        # set_config(name, value, false) sets a setting for this connection only, and it takes the
        # value as a parameter. Nothing on the server is changed for anybody else.
        # TimeZone: Postgres stores fetched_at as a moment in time and hands it back in the
        # connection's zone, which by default is the Mac's own. Asking for UTC here, and
        # converting again in nearest(), means a Company never carries a local time.

    def nearest(self, search_key: str, limit: int) -> list[Company]:
        key = without_suffixes(search_key) or search_key           # "LLC" alone would leave nothing: then send it as typed
        rows = self.conn.execute(self.NEAREST_SQL, {"key": key, "limit": limit}).fetchall()
        return [company_from_row(row) for row in rows]


def company_from_row(row) -> Company:
    """One database row, in COMPANY_COLUMNS order, as a Company whose fetch time is in UTC.

    A fetch time that arrives with another zone is the same moment written differently, so
    it is converted. One that arrives with NO zone is ambiguous, and Company refuses it.
    """
    values = list(row)
    at = COMPANY_COLUMNS.index("fetched_at")                       # found by name, so a reordered column list can't shift it
    if isinstance(values[at], datetime) and values[at].tzinfo is not None:
        values[at] = values[at].astimezone(timezone.utc)
    return Company(*values)


class FakeBackend:
    """Step 1 for the tests: a fixed list of companies held in memory. No database, no network.

    It returns every company it holds, whatever the key, up to the limit. That is a fair
    stand-in, because step 1 only promises a pool that CONTAINS the right company, and the
    order and the scoring are step 2's job, which runs for real in the tests.
    """

    def __init__(self, companies: list[Company]):
        self.companies = list(companies)
        self.calls: list[tuple[str, int]] = []                     # every (search key, limit) asked for, so a test can check them

    def nearest(self, search_key: str, limit: int) -> list[Company]:
        self.calls.append((search_key, limit))
        return self.companies[:limit]
