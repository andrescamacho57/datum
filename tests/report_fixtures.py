"""report_fixtures.py: reads tests/fixtures/report/ into the objects the report builder works with.

It is a helper and holds no test. The tests of the report builder, of the terminal command
and of the web app all import it, so the three build their reports from the same rows.
The folder's README says where each row came from and which values are invented.
"""

import csv                                  # reads the three fixture files
from datetime import date, datetime         # turns the dates and fetch times in the files into Python values
from pathlib import Path                    # file paths

from datum.report_builder import FakeReportBackend, FlagRow, ReportBuilder, SourceRow
from datum.search import Company

FOLDER = Path(__file__).parent / "fixtures" / "report"
BUILT_ON = date(2026, 11, 24)               # the day every fixture report is "built", so that "New company" gives the same answer on any day

LIEN_COMPANY = "T26000000001"               # one open federal lien and one closed one
LICENSE_COMPANY = "T26000000002"            # an inactive license, and an open lien with a certificate of discharge
INACTIVE_COMPANY = "T26000000003"           # inactive with the state, and no linked record
NEW_COMPANY = "T26000000004"                # on record since 2026-06-15, which is within 12 months of BUILT_ON
NO_FLAG_COMPANY = "T26000000005"            # active, on record since 2015, no linked record
GAPS_COMPANY = "T26000000006"               # no date, no address, and an entity-type code with no label


def rows_of(name: str) -> list[dict]:
    with (FOLDER / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def a_day(text: str) -> date | None:
    return date.fromisoformat(text) if text else None


def load_companies() -> list[Company]:
    return [
        Company(
            document_number=row["document_number"], entity_name=row["entity_name"], name_key=row["name_key"],
            status_code=row["status_code"] or None, filing_type=row["filing_type"] or None, file_date=a_day(row["file_date"]),
            principal_address_1=row["principal_address_1"] or None, principal_city=row["principal_city"] or None,
            principal_state=row["principal_state"] or None, principal_zip=row["principal_zip"] or None,
            published_on=a_day(row["published_on"]), source_url=row["source_url"],
            fetched_at=datetime.fromisoformat(row["fetched_at"]), fetched_at_is_approximate=row["fetched_at_is_approximate"] == "True",
        )
        for row in rows_of("company_search.csv")
    ]


def load_flags() -> list[FlagRow]:
    return [
        FlagRow(
            document_number=row["document_number"], flag_type=row["flag_type"], fact_date=a_day(row["fact_date"]),
            status=row["status"], status_note=row["status_note"] or None, source=row["source"],
            source_record_id=row["source_record_id"], source_url=row["source_url"], citation=row["citation"],
            fetched_at=datetime.fromisoformat(row["fetched_at"]), caveat=row["caveat"],
            is_shown=row["is_shown"] == "True", fetched_at_is_approximate=row["fetched_at_is_approximate"] == "True",
        )
        for row in rows_of("company_flags.csv")
    ]


def load_sources() -> list[SourceRow]:
    return [
        SourceRow(
            source=row["source"], label=row["label"], is_shown=row["is_shown"] == "True", data_through=a_day(row["data_through"]),
            data_through_note=row["data_through_note"], source_url=row["source_url"], fetched_at=datetime.fromisoformat(row["fetched_at"]),
            fetched_at_is_approximate=row["fetched_at_is_approximate"] == "True", list_order=int(row["list_order"]),
        )
        for row in rows_of("source_coverage.csv")
    ]


def backend(extra_flags: list[FlagRow] | None = None) -> FakeReportBackend:
    """The fixture rows behind a fake backend. extra_flags lets a test add rows a real backend would never hold."""
    return FakeReportBackend(load_companies(), load_flags() + list(extra_flags or []), load_sources())


def builder(extra_flags: list[FlagRow] | None = None) -> ReportBuilder:
    return ReportBuilder(backend(extra_flags), today=lambda: BUILT_ON)
