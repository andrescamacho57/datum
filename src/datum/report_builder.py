"""report_builder.py: build the report for one company from the tables the app reads (Phase C, leg C3).

    document number ──▶ ReportBuilder.build() ──▶ Report ──▶ render_markdown()   (the terminal, and files under data/reports/)
                              │                          └─▶ the web templates  (leg C4)
                              ▼
                        ReportBackend   company_search, company_flags, source_coverage

The builder reads through an interface, ReportBackend. The app passes in
PostgresReportBackend, and the tests pass in FakeReportBackend, so the tests need no database
(CLAUDE.md rule 4).

What the builder may and may not say:
  - Every sentence comes from wording.py, or is a mart column copied as it is. For a LINKED
    record (a federal lien, a license) the builder holds no wording of its own: the citation,
    the status, the status note and the caveat are the mart's columns, written by dbt and
    reviewed with the rule that made them.
  - The two flags that come from the company's own record ("Inactive with the state" and
    "New company") follow the flags table of docs/mvp_plan_nov8.md, section 4.
  - A row that is hidden (is_shown false) or that is a possible match (it carries a
    link_reason) is dropped here, whatever the backend hands over. Postgres holds neither
    today (working rule W9), and this is the second lock on the same door.
  - Everything stated about the company is a Fact, with its source address and fetch time
    (working rule W1).
"""

import re                                   # the shape of a document number
from collections.abc import Callable        # the type of "a function that returns today's date"
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from datetime import date, datetime, timezone   # dates on the record, fetch times, and the UTC zone
from typing import Protocol                 # a Protocol describes an interface: "anything with these methods"

from datum import wording                   # every fixed sentence and label
from datum.models import Candidate, Fact, Flag, Identification, Report
from datum.search import COMPANY_COLUMNS, Company, company_from_row
from datum.search import Candidate as SearchCandidate           # the search's own candidate: a company with its scores

DOCUMENT_NUMBER = re.compile(r"[A-Z0-9]{5,12}")
# The state's document numbers are 6 or 12 letters and digits (two odd rows are 5 and 11 long).
# Anything else is not a document number, and it is refused before any query is made.


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class FlagRow:
    """One row of company_flags (or, if a backend ever hands one over, of company_possible_matches)."""

    document_number: str
    flag_type: str
    fact_date: date | None
    status: str
    status_note: str | None
    source: str
    source_record_id: str
    source_url: str
    citation: str
    fetched_at: datetime
    caveat: str
    is_shown: bool
    fetched_at_is_approximate: bool
    link_reason: str | None = None          # set only on a possible match. A flag has none


@dataclass(frozen=True)
class SourceRow:
    """One row of source_coverage: a source, whether its flags may be shown, and how fresh its data is."""

    source: str
    label: str
    is_shown: bool
    data_through: date
    data_through_note: str
    source_url: str
    fetched_at: datetime
    fetched_at_is_approximate: bool
    list_order: int


FLAG_COLUMNS = (                            # the columns of company_flags that FlagRow holds, in the order its fields are declared
    "document_number", "flag_type", "fact_date", "status", "status_note", "source", "source_record_id",
    "source_url", "citation", "fetched_at", "caveat", "is_shown", "fetched_at_is_approximate",
)
SOURCE_COLUMNS = (                          # the columns of source_coverage, in the order SourceRow's fields are declared
    "source", "label", "is_shown", "data_through", "data_through_note", "source_url",
    "fetched_at", "fetched_at_is_approximate", "list_order",
)


class CompanyNotFound(LookupError):
    """No company has this document number. The web app answers it with a plain 404 page."""


class ReportBackend(Protocol):
    """Anything that can hand over a company, its flag rows and the list of sources."""

    def company(self, document_number: str) -> Company | None:
        """The company with this document number, or None."""
        ...

    def flags(self, document_number: str) -> list[FlagRow]:
        """The flag rows of this company. Order does not matter: the builder sorts them."""
        ...

    def sources(self) -> list[SourceRow]:
        """Every row of source_coverage."""
        ...


def looks_like_a_document_number(text: str) -> bool:
    """True when the text has the shape of a document number. It says nothing about whether such a company exists."""
    return bool(DOCUMENT_NUMBER.fullmatch(text))


def one_year_before(day: date) -> date:
    """The same day twelve months earlier. Feb 29 goes to Feb 28, because the year before has no Feb 29."""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:                      # only Feb 29 raises this
        return day.replace(year=day.year - 1, day=28)


def in_utc(value: datetime) -> datetime:
    """The same moment written in UTC. A time with NO zone is returned as it is, and Fact then refuses it."""
    return value.astimezone(timezone.utc) if value.tzinfo is not None else value


def candidate_for_page(candidate: SearchCandidate, level: str, reasons: list[str]) -> Candidate:
    """A search result as a page shows it: the name and the place become Facts, with the company's source and fetch time."""
    company = candidate.company

    def fact(text: str) -> Fact:
        return Fact(
            text=text, source_url=company.source_url,
            citation=wording.COMPANY_CITATION.format(document_number=company.document_number),
            fetched_at=in_utc(company.fetched_at), fetched_at_is_approximate=company.fetched_at_is_approximate,
        )

    place = ", ".join(part for part in (company.principal_city, company.principal_state) if part)
    return Candidate(
        document_number=company.document_number, name=fact(company.entity_name),
        place=fact(place) if company.principal_city else None,   # no city on record: no place is shown, and none is made up
        level=level, evidence=tuple(reasons),
    )


class ReportBuilder:
    """Builds a Report for one document number. It reads through a ReportBackend and takes its words from wording.py."""

    def __init__(self, backend: ReportBackend, today: Callable[[], date] = date.today):
        self.backend = backend
        self.today = today                  # passed in so that a test can fix the date. "New company" depends on it

    def build(self, document_number: str, identification: Identification | None = None) -> Report:
        """The report for one company. `identification` says how it was picked. None means it was opened by its number."""
        if not looks_like_a_document_number(document_number):
            raise CompanyNotFound(document_number)
        company = self.backend.company(document_number)
        if company is None:
            raise CompanyNotFound(document_number)
        built_on = self.today()

        def fact(text: str) -> Fact:        # a statement about the company, carrying the company record's source and fetch time
            return Fact(
                text=text, source_url=company.source_url,
                citation=wording.COMPANY_CITATION.format(document_number=company.document_number),
                fetched_at=in_utc(company.fetched_at), fetched_at_is_approximate=company.fetched_at_is_approximate,
            )

        status = {"A": wording.STATUS_ACTIVE, "I": wording.STATUS_INACTIVE}.get(company.status_code, wording.NOT_ON_RECORD)
        entity_type = wording.FILING_TYPES.get(company.filing_type, company.filing_type) or wording.NOT_ON_RECORD
        on_record = wording.DATE_ON_RECORD.format(day=wording.day_text(company.file_date)) if company.file_date else wording.NOT_ON_RECORD
        street_and_city = ", ".join(part for part in (company.principal_address_1, company.principal_city) if part)
        state_and_zip = " ".join(part for part in (company.principal_state, company.principal_zip) if part)
        address = ", ".join(part for part in (street_and_city, state_and_zip) if part) or wording.NOT_ON_RECORD
        rows = (
            (wording.LABEL_LEGAL_NAME, fact(company.entity_name)),
            (wording.LABEL_DOCUMENT_NUMBER, fact(company.document_number)),
            (wording.LABEL_STATUS, fact(status)),
            (wording.LABEL_ENTITY_TYPE, fact(entity_type)),
            (wording.LABEL_DATE_ON_RECORD, fact(on_record)),
            (wording.LABEL_ADDRESS, fact(address)),
        )
        company_source = fact(
            wording.COMPANY_CITATION.format(document_number=company.document_number)
            + ", " + wording.COMPANY_PUBLISHED.format(day=wording.day_text(company.published_on))
        )

        flags = self.company_record_flags(company, built_on, fact) + self.linked_flags(self.backend.flags(company.document_number))

        sources = sorted(self.backend.sources(), key=lambda row: row.list_order)
        checked = tuple(
            Fact(
                text=f"{row.label}: {wording.DATA_THROUGH.format(day=wording.day_text(row.data_through))}. {row.data_through_note}",
                source_url=row.source_url, citation=row.label,
                fetched_at=in_utc(row.fetched_at), fetched_at_is_approximate=row.fetched_at_is_approximate,
            )
            for row in sources if row.is_shown   # rule W5: a source is "checked" only when its flags may be shown
        )
        not_checked = tuple(row.label for row in sources if not row.is_shown) + wording.NOT_CHECKED_ALWAYS

        if identification is None:
            identified = wording.IDENTIFIED_BY_NUMBER
        else:
            identified = wording.identified_text(
                identification.business_name, identification.city, identification.street,
                identification.level, identification.evidence, identification.tied_others,
            )
        return Report(
            document_number=company.document_number, built_on=built_on, name=company.entity_name,
            company=rows, company_source=company_source, flags=flags,
            sources_checked=checked, sources_not_checked=not_checked, identification=identified,
        )

    @staticmethod
    def company_record_flags(company: Company, built_on: date, fact: Callable[[str], Fact]) -> tuple[Flag, ...]:
        """The two flags that need no link, by the rules of the plan's flags table (section 4)."""
        flags = []
        if company.status_code == "I":      # the rule: status_code = 'I'
            flags.append(Flag(
                kind="company_record", flag_type="inactive_with_state", title=wording.FLAG_INACTIVE_TITLE,
                fact=fact(wording.FLAG_INACTIVE_TEXT), fact_date=None, status=None, status_note=None,
                caveat=wording.FLAG_INACTIVE_CAVEAT,
            ))
        on_record = company.file_date
        if on_record is not None and one_year_before(built_on) <= on_record <= built_on:   # the rule: date on record within 12 months
            # A date in the future is not "within 12 months". It is shown in the company's own
            # record, with its "may be an effective date" note, and it raises no flag.
            flags.append(Flag(
                kind="company_record", flag_type="new_company", title=wording.FLAG_NEW_TITLE,
                fact=fact(wording.FLAG_NEW_TEXT.format(day=wording.day_text(on_record))), fact_date=on_record,
                status=None, status_note=None, caveat=wording.FLAG_NEW_CAVEAT,
            ))
        return tuple(flags)

    @staticmethod
    def linked_flags(rows: list[FlagRow]) -> tuple[Flag, ...]:
        """One Flag per shown flag row, newest first. Every word on it is a mart column."""
        shown = [row for row in rows if row.is_shown is True and row.link_reason is None]
        # is_shown must be exactly True, and a row with a link_reason is a possible match (rule W3):
        # neither a hidden record nor a possible match is shown or counted, whatever the backend returned.
        shown.sort(key=lambda row: row.source_record_id)                    # a fixed order among records of the same date
        shown.sort(key=lambda row: row.fact_date or date.min, reverse=True)   # newest first. Python's sort keeps the order above for equal dates
        return tuple(
            Flag(
                kind="linked_record", flag_type=row.flag_type, title=row.citation,
                fact=Fact(
                    text=row.citation, source_url=row.source_url, citation=row.citation,
                    fetched_at=in_utc(row.fetched_at), fetched_at_is_approximate=row.fetched_at_is_approximate,
                ),
                fact_date=row.fact_date, status=row.status, status_note=row.status_note, caveat=row.caveat,
            )
            for row in shown
        )


def render_markdown(report: Report) -> str:
    """The report as Markdown text, for the terminal and for the files under data/reports/.

    This function only lays out. Every word it writes is a field of the report, a mart
    column carried by the report, or a label from wording.py.
    """
    def cited(fact: Fact) -> str:           # "[citation](address) · fetched 2026-11-18"
        return f"[{fact.citation}]({fact.source_url}) · {fact.fetched_text}"

    lines = [
        f"# {wording.REPORT_TITLE.format(name=report.name)}", "",
        wording.BUILT_ON.format(day=wording.day_text(report.built_on)), "",
        f"**{report.summary}**", "",
        report.confirmed_only, "",
        "| | |", "|---|---|",
    ]
    lines += [f"| {label} | {fact.text.replace('|', chr(92) + '|')} |" for label, fact in report.company]   # a "|" in a name would end the table cell, so it is written as \|
    lines += [f"| {wording.LABEL_COMPANY_SOURCE} | {cited(report.company_source)} |", ""]
    if report.flags:
        lines += [f"## {wording.HEADING_FLAGS}", ""]
        for flag in report.flags:
            lines.append(f"### {flag.title}")
            lines.append("")
            if flag.kind == "company_record":
                lines.append(f"- {flag.fact.text}")
            if flag.kind == "linked_record" and flag.fact_date:
                lines.append(f"- {wording.LABEL_FLAG_DATE}: {wording.day_text(flag.fact_date)}")
            if flag.status:
                lines.append(f"- {wording.LABEL_FLAG_STATUS}: {flag.status}" + (f". {flag.status_note}" if flag.status_note else ""))
            lines.append(f"- {flag.caveat}")
            lines.append(f"- {wording.LABEL_SOURCE}: {cited(flag.fact)}")
            lines.append("")
    lines += [f"## {wording.HEADING_CHECKED}", ""]
    lines += [f"- {fact.text} {wording.LABEL_SOURCE}: {cited(fact)}" for fact in report.sources_checked]
    lines += ["", f"## {wording.HEADING_NOT_CHECKED}", ""]
    lines += [f"- {item}" for item in report.sources_not_checked]
    lines += ["", f"**{wording.LABEL_IDENTIFIED}:** {report.identification}", "", f"*{report.disclaimer}*", ""]
    return "\n".join(lines)


class PostgresReportBackend:
    """Reads the three tables from Postgres. Every value a person supplies travels as a parameter, never as SQL text."""

    COMPANY_SQL = f"select {', '.join(COMPANY_COLUMNS)} from company_search where document_number = %(document_number)s"
    FLAGS_SQL = f"select {', '.join(FLAG_COLUMNS)} from company_flags where document_number = %(document_number)s and is_shown"
    SOURCES_SQL = f"select {', '.join(SOURCE_COLUMNS)} from source_coverage order by list_order"
    # %(document_number)s is a PLACEHOLDER: the driver sends the value apart from the SQL. The
    # f-strings above only paste in the column lists, which are constants of this code.
    # "and is_shown" repeats what the table already promises with its CHECK (rule W9).

    def __init__(self, conn):
        self.conn = conn                    # an open psycopg connection
        conn.execute("select set_config('TimeZone', %s, false)", ("UTC",))   # this session only: fetch times come back in UTC

    def company(self, document_number: str) -> Company | None:
        row = self.conn.execute(self.COMPANY_SQL, {"document_number": document_number}).fetchone()
        return company_from_row(row) if row else None

    def flags(self, document_number: str) -> list[FlagRow]:
        rows = self.conn.execute(self.FLAGS_SQL, {"document_number": document_number}).fetchall()
        return [FlagRow(*row) for row in rows]

    def sources(self) -> list[SourceRow]:
        return [SourceRow(*row) for row in self.conn.execute(self.SOURCES_SQL).fetchall()]


class FakeReportBackend:
    """For the tests: companies, flag rows and source rows held in memory. No database, no network.

    It hands over EVERY flag row it holds for a company, hidden rows and possible matches
    included. A real backend never has those, and that is the point: the tests give the
    builder the worst case and check that it still shows and counts only what it may.
    """

    def __init__(self, companies: list[Company], flags: list[FlagRow], sources: list[SourceRow]):
        self.companies = {company.document_number: company for company in companies}
        self.flag_rows = list(flags)
        self.source_rows = list(sources)

    def company(self, document_number: str) -> Company | None:
        return self.companies.get(document_number)

    def flags(self, document_number: str) -> list[FlagRow]:
        return [row for row in self.flag_rows if row.document_number == document_number]

    def sources(self) -> list[SourceRow]:
        return list(self.source_rows)
