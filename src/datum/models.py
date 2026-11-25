"""models.py: the shapes a report is made of, and the rule that no fact exists without its source (Phase C, leg C3).

    Fact            one thing the app states about a company, with where it was read and when
    Flag            a fact that belongs on the "flags" part of a report, with its date, status and caveat
    Candidate       one company on a shortlist, as a page shows it
    Identification  how a company was picked: the extracted fields, the match level, the evidence
    Report          everything one report page shows

These are Pydantic models. Pydantic is a library that checks a value when an object is
built: a field of the wrong type, a missing field or a field nobody declared raises an
error at that moment, and so a wrong object never exists to be shown. Every model here is
FROZEN, which means its fields cannot be changed after it is built.

The rule this module enforces is CLAUDE.md rule 3 and working rule W1: everything the app
states about a company is a Fact, and a Fact cannot be built without a full source address
and a time-zone-aware fetch time in UTC (Coordinated Universal Time). It is a rule of the
TYPE and not a habit of the code that uses it: there is no way to write a Fact without both.

Rule W6 is enforced the same way. Identification has no field for the note a contractor
typed, and it refuses any field it does not declare, so the note has nowhere to travel.
"""

from datetime import date, datetime         # a fact's fetch time, and the dates on a report
from typing import Literal                  # Literal["a", "b"] = the value must be one of these exact texts
from urllib.parse import urlsplit           # cuts an address into scheme, host and path, to check that it is a full one

from pydantic import BaseModel, ConfigDict, field_validator, model_validator   # the base class, its settings, and hooks that check one field or the whole object

from datum import wording                   # the summary line is built from the flags, with the words of wording.py

Level = Literal["Strong", "Likely", "Possible"]                # the three match levels of search.match_level()


class Frozen(BaseModel):
    """The settings every model here shares."""

    model_config = ConfigDict(
        frozen=True,                        # no field can be assigned after the object is built
        extra="forbid",                     # a field that is not declared is an error, not something quietly dropped
        strict=True,                        # no guessing: the text "2026-11-24" is not accepted where a date is required
    )


class Fact(Frozen):
    """One statement about a company, with the official page to check it on and the time Datum fetched it."""

    text: str                               # what the record says, as the page shows it
    source_url: str                         # the official page the record can be checked on
    citation: str                           # which record on that page: the document, filing or license number to look up
    fetched_at: datetime                    # when Datum fetched the file the record came from, in UTC
    fetched_at_is_approximate: bool         # True when that time is an estimate, and the page then says "about"

    @field_validator("source_url")
    @classmethod
    def a_full_address(cls, value: str) -> str:
        parts = urlsplit(value)             # "https://host/path" → scheme "https", netloc "host"
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("a fact needs a full source address, starting with http:// or https://")
        return value

    @field_validator("fetched_at")
    @classmethod
    def a_utc_time(cls, value: datetime) -> datetime:
        offset = value.utcoffset()          # None when the time has no time zone
        if offset is None:
            raise ValueError("a fact's fetch time needs a time zone: a time without one could be any of 24 hours")
        if offset.total_seconds() != 0:
            raise ValueError("a fact's fetch time must be in UTC: convert it where it is read, not where it is shown")
        return value

    @property
    def fetched_text(self) -> str:
        """"fetched 2026-11-18", or "fetched about 2026-10-22" when the time is an estimate (rule W1)."""
        return wording.fetched_text(self.fetched_at, self.fetched_at_is_approximate)


class Flag(Frozen):
    """A fact shown under "Flags": something on the public record that a contractor would want to see before a job."""

    kind: Literal["company_record", "linked_record"]           # from the company's own record, or from a record linked to it
    flag_type: str                          # the code: inactive_with_state, new_company, or the mart's flag_type
    title: str                              # the card's heading
    fact: Fact                              # what the record says, with its source and fetch time
    fact_date: date | None                  # the date on the record, when it has one
    status: str | None                      # the mart's status for a linked record (open, closed, inactive)
    status_note: str | None                 # the mart's note on that status, such as a release date
    caveat: str                             # what this line cannot tell the reader


class Candidate(Frozen):
    """One company on the shortlist, as a page shows it. Everything it says about the company is a Fact, so it carries its source."""

    document_number: str
    name: Fact                              # the legal name as filed
    place: Fact | None                      # "BOYNTON BEACH, FL". None when the state has no principal city for the company
    level: Level
    mark: Fact | None = None                # "Inactive with the state", shown beside the name of an inactive company (rule S10). None for any other company
    evidence: tuple[Fact, ...]              # the reasons behind the level, from search.evidence()
    # The reasons are Facts too. "ACTIVE" and "principal city on record is TAMPA, ..." are
    # statements about the company, and "name is similar (93/100)" is worked out from its name,
    # so each carries the company record's source address and fetch time (rule W1, and CLAUDE.md
    # rule 3: a derived value carries its inputs' provenance).

    @property
    def source(self) -> Fact:
        """The fact whose citation, address and fetch time stand for the whole line. Every fact here has the same ones."""
        return self.name


class AddressCandidate(Frozen):
    """One company on the list an address search shows. It has no match level: working rule S4 keeps the three levels for the name search."""

    document_number: str
    name: Fact                              # the legal name as filed
    address: Fact                           # the principal address as the state has it, so the reader can compare it with what was typed

    @property
    def source(self) -> Fact:
        """The fact whose citation, address and fetch time stand for the whole line. Both facts here have the same ones."""
        return self.name


class Identification(Frozen):
    """How a company was picked, from the EXTRACTED fields. There is no field for the typed note (rule W6).

    A company is found by its NAME (a business name, a match level and the evidence behind
    it) or by its ADDRESS (a street, and no level and no business name: the note named none).
    The object refuses a mix of the two, so a report can never print a match level for a
    company that was found by its address.
    """

    found_by: Literal["name", "address"] = "name"
    business_name: str = ""                 # what the extraction step read as the business's name. Empty when found by address
    city: str = ""
    street: str = ""
    level: Level | None = None              # the match level of the name search. None when found by address
    evidence: tuple[str, ...] = ()
    tied_others: int = 0                    # how many OTHER companies matched equally well (rule W7)

    @field_validator("tied_others")
    @classmethod
    def not_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("tied_others counts companies, so it cannot be below 0")
        return value

    @model_validator(mode="after")
    def one_kind_or_the_other(self) -> "Identification":
        if self.found_by == "name" and (not self.business_name or self.level is None):
            raise ValueError("a company found by its name needs the business name and a match level")
        if self.found_by == "address" and (not self.street or self.business_name or self.level is not None or self.evidence):
            raise ValueError("a company found by its address needs the street, and takes no business name, no match level and no evidence")
        return self


class Extracted(Frozen):
    """What the extraction step read from a note, checked: three texts and a yes-or-no. The note itself is not here."""

    business_name: str
    city: str
    street: str
    is_specific: bool                       # False = the note names no business, so the search must ask and not answer


def read_extracted(reply: dict) -> Extracted:
    """Check the extraction step's reply and trim it. Any fault in the reply raises an error here, where the caller expects one.

    The reply comes from a model, so it is checked like any outside input: a missing field,
    a number where a text belongs, or a text where True or False belongs is an error. A city
    or a street the reply leaves empty (or sends as nothing at all) is an empty text. Spaces
    around a value are removed, so a city of three spaces is no city.
    """
    return Extracted(
        business_name=reply["business_name"].strip(),
        city=(reply["city"] or "").strip(),
        street=(reply["street"] or "").strip(),
        is_specific=reply["is_specific"],
    )


class Report(Frozen):
    """Everything one report page shows. Both the terminal and the web app lay out this object and add no sentence of their own."""

    document_number: str
    built_on: date                          # the day the report was built
    name: str                               # the legal name, for the title
    headline: tuple[Fact, Fact]             # the summary's first two sentences (rule S9): the status as of the published date, and the entity
                                            # type with the year on record. Each is a Fact, built from the same values as the rows below
    company: tuple[tuple[str, Fact], ...]   # the company's own record: (label, fact) rows in display order
    company_source: Fact                    # the line that cites the company record as a whole
    flags: tuple[Flag, ...]                 # the company-record flags first, then the linked records, newest first
    sources_checked: tuple[Fact, ...]       # one line per source whose flags may be shown (rule W5)
    sources_not_checked: tuple[str, ...]    # what Datum did not look at, so that nobody reads silence as "nothing found"
    identification: Fact                    # the line that says how this company was picked (rules W6 and W7). It restates
                                            # the company's status and city as evidence, so it is a Fact with the company record's source
    caution: str                            # wording.POSSIBLE_CAUTION when the company was picked at the level Possible. Otherwise empty

    @field_validator("sources_checked")
    @classmethod
    def at_least_one_source(cls, value: tuple[Fact, ...]) -> tuple[Fact, ...]:
        if not value:                       # a report whose summary speaks of "the sources checked" must have checked one
            raise ValueError("a report needs at least one source checked: with none, it has nothing to say")
        return value

    # The next three are not fields. They are worked out from the fields above each time they
    # are read, so no code path can store a summary that disagrees with the flags (rule W2).

    @property
    def summary(self) -> str:
        """The summary line. It counts exactly the flags this report shows."""
        return wording.summary_line(len(self.flags), len(self.sources_checked))

    @property
    def confirmed_only(self) -> str:
        """The sentence every report carries, flags or no flags (rule W4)."""
        return wording.CONFIRMED_ONLY

    @property
    def disclaimer(self) -> str:
        return wording.DISCLAIMER
