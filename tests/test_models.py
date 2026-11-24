"""test_models.py: offline tests for src/datum/models.py, the shapes a report is made of.

The tests that matter most are the three that try to build a Fact the wrong way. CLAUDE.md
rule 3 says a fact type that can be built without a source address and a UTC fetch time is
a bug in the type, and so each way of breaking it has a test that fails if the type lets it through.

Run from ~/datum:  pytest
"""

from datetime import date, datetime, timedelta, timezone   # fetch times with and without a time zone

import pytest                               # the test runner; pytest.raises checks that an error IS raised
from pydantic import ValidationError        # the error Pydantic raises when a value breaks a model's rules

from datum import wording
from datum.models import Candidate, Fact, Flag, Identification, Report

FETCHED = datetime(2026, 10, 22, 19, 31, 31, tzinfo=timezone.utc)
SUNBIZ = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber"


def a_fact(**changes):
    """A good Fact, with any field replaced. Passing a field as ... leaves it out altogether."""
    fields = {"text": "Active", "source_url": SUNBIZ, "citation": "document number T26000000001", "fetched_at": FETCHED, "fetched_at_is_approximate": False}
    fields.update(changes)
    return Fact(**{name: value for name, value in fields.items() if value is not ...})


def test_a_fact_with_a_source_address_and_a_utc_fetch_time_is_built():
    fact = a_fact()
    assert (fact.source_url, fact.fetched_at) == (SUNBIZ, FETCHED)


@pytest.mark.parametrize("source_url", [..., None, "", "search.sunbiz.org/Inquiry", "/Inquiry/CorporationSearch", "ftp://ftp.example.org/file", "https://"],
                         ids=["left out", "None", "empty", "no scheme", "a path only", "not a web address", "no host"])
def test_a_fact_with_no_full_source_address_cannot_be_built(source_url):
    with pytest.raises(ValidationError, match="source_url"):
        a_fact(source_url=source_url)


@pytest.mark.parametrize("fetched_at", [..., None, datetime(2026, 10, 22, 19, 31, 31), "2026-10-22T19:31:31Z", date(2026, 10, 22)],
                         ids=["left out", "None", "no time zone", "text", "a date"])
def test_a_fact_whose_fetch_time_has_no_time_zone_cannot_be_built(fetched_at):
    with pytest.raises(ValidationError, match="fetched_at"):
        a_fact(fetched_at=fetched_at)


def test_a_fact_whose_fetch_time_is_not_utc_cannot_be_built():
    eastern = FETCHED.astimezone(timezone(timedelta(hours=-5)))           # the same moment, written as 14:31 -05:00
    with pytest.raises(ValidationError, match="must be in UTC"):
        a_fact(fetched_at=eastern)                                        # it is not converted for the caller: the caller has to hand over UTC


def test_a_fact_must_say_whether_its_fetch_time_is_an_estimate():
    with pytest.raises(ValidationError, match="fetched_at_is_approximate"):
        a_fact(fetched_at_is_approximate=...)
    assert a_fact(fetched_at_is_approximate=False).fetched_text == "fetched 2026-10-22"
    assert a_fact(fetched_at_is_approximate=True).fetched_text == "fetched about 2026-10-22"   # rule W1: an estimate says "about"


def test_a_fact_cannot_be_changed_after_it_is_built_and_takes_no_extra_field():
    fact = a_fact()
    with pytest.raises(ValidationError, match="frozen"):
        fact.source_url = "https://example.org/other"
    with pytest.raises(ValidationError, match="Extra inputs"):
        a_fact(note="anything")


def test_an_identification_has_nowhere_to_put_the_typed_note():
    # Rule W6: the note is used for one extraction call and then dropped. The type that travels to the report has no field for it.
    good = Identification(business_name="Ferguson Air Conditioning", city="Boynton Beach", level="Strong", evidence=("city matches",))
    assert "note" not in Identification.model_fields and good.street == ""
    for field in ("note", "raw_note", "owner", "owner_name"):
        with pytest.raises(ValidationError, match="Extra inputs"):
            Identification(business_name="Ferguson Air Conditioning", level="Strong", evidence=(), **{field: "ask for the owner, J. Doe"})
    with pytest.raises(ValidationError, match="tied_others"):
        Identification(business_name="x", level="Strong", evidence=(), tied_others=-1)
    with pytest.raises(ValidationError, match="level"):
        Identification(business_name="x", level="Certain", evidence=())  # only the three levels exist


def a_flag():
    return Flag(kind="company_record", flag_type="inactive_with_state", title=wording.FLAG_INACTIVE_TITLE, fact=a_fact(text=wording.FLAG_INACTIVE_TEXT),
                fact_date=None, status=None, status_note=None, caveat=wording.FLAG_INACTIVE_CAVEAT)


def a_report(flags=()):
    return Report(
        document_number="T26000000001", built_on=date(2026, 11, 24), name="INVENTED ROOFING CORP",
        company=((wording.LABEL_STATUS, a_fact()),), company_source=a_fact(), flags=tuple(flags),
        sources_checked=(a_fact(text="source one"), a_fact(text="source two")), sources_not_checked=("Court cases",),
        identification=a_fact(text=wording.IDENTIFIED_BY_NUMBER),
    )


def test_the_summary_line_is_worked_out_from_the_flags_and_cannot_be_stored():
    # Rule W2: a report that shows a flag never says "No flags found". The summary is not a field, so nothing can set it wrong.
    assert a_report().summary == "No flags found in the sources checked."
    assert a_report([a_flag()]).summary == "1 flag found in 2 sources checked."
    assert a_report([a_flag(), a_flag()]).summary == "2 flags found in 2 sources checked."
    assert "summary" not in Report.model_fields
    with pytest.raises(ValidationError, match="Extra inputs"):
        Report(**{**a_report([a_flag()]).model_dump(), "summary": wording.NO_FLAGS})


def test_a_report_with_no_source_checked_cannot_be_built():
    with pytest.raises(ValidationError, match="at least one source checked"):
        Report(**{**a_report().model_dump(), "sources_checked": ()})


def test_every_report_carries_the_same_two_sentences():
    for report in (a_report(), a_report([a_flag()])):
        assert report.confirmed_only == wording.CONFIRMED_ONLY and report.disclaimer == wording.DISCLAIMER


def test_a_report_cannot_take_its_identification_line_as_bare_text():
    with pytest.raises(ValidationError, match="identification"):
        Report(**{**a_report().model_dump(), "identification": "match level Strong (ACTIVE)"})   # the line restates the company's status, so it is a Fact


def test_a_candidate_states_its_name_its_place_and_its_evidence_as_facts():
    candidate = Candidate(document_number="T26000000001", name=a_fact(text="INVENTED ROOFING CORP"), place=None, level="Likely",
                          evidence=(a_fact(text="city matches"), a_fact(text="ACTIVE")))
    assert candidate.name.source_url == SUNBIZ and candidate.place is None and candidate.source is candidate.name
    with pytest.raises(ValidationError, match="name"):
        Candidate(document_number="T26000000001", name="INVENTED ROOFING CORP", place=None, level="Likely", evidence=())   # a bare text is not a fact
    with pytest.raises(ValidationError, match="evidence"):
        # Rule W1 names a company's status. "ACTIVE" as a bare text would be a statement with no source and no fetch time.
        Candidate(document_number="T26000000001", name=a_fact(text="INVENTED ROOFING CORP"), place=None, level="Likely", evidence=("ACTIVE",))
