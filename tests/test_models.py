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
from datum.models import AddressCandidate, Candidate, Extracted, Fact, Flag, Identification, Report, read_extracted

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
    good = Identification(business_name="Ferguson Air Conditioning", city="Boynton Beach", level="Strong", evidence=("principal city on record begins with the city you gave",))
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
        headline=(a_fact(text="Inactive with the state as of Oct 7, 2026."), a_fact(text="Florida corporation (for profit), on record since 2010.")),
        company=((wording.LABEL_STATUS, a_fact()),), company_source=a_fact(), flags=tuple(flags),
        sources_checked=(a_fact(text="source one"), a_fact(text="source two")), sources_not_checked=("Court cases",),
        identification=a_fact(text=wording.IDENTIFIED_BY_NUMBER), caution="",
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
                          evidence=(a_fact(text="principal city on record begins with the city you gave"), a_fact(text="ACTIVE")))
    assert candidate.name.source_url == SUNBIZ and candidate.place is None and candidate.source is candidate.name
    with pytest.raises(ValidationError, match="name"):
        Candidate(document_number="T26000000001", name="INVENTED ROOFING CORP", place=None, level="Likely", evidence=())   # a bare text is not a fact
    with pytest.raises(ValidationError, match="evidence"):
        # Rule W1 names a company's status. "ACTIVE" as a bare text would be a statement with no source and no fetch time.
        Candidate(document_number="T26000000001", name=a_fact(text="INVENTED ROOFING CORP"), place=None, level="Likely", evidence=("ACTIVE",))


def test_the_extraction_steps_reply_is_checked_and_trimmed_before_anything_uses_it():
    # The reply comes from a model, so it is checked like any outside input. Each fault must raise HERE, where the caller catches it.
    good = {"business_name": "  Acme Roofing ", "city": None, "street": "   ", "is_specific": True}
    assert read_extracted(good) == Extracted(business_name="Acme Roofing", city="", street="", is_specific=True)   # trimmed. A city of nothing, or of spaces, is no city
    for missing in good:
        with pytest.raises(KeyError):
            read_extracted({name: value for name, value in good.items() if name != missing})
    for field, wrong in (("business_name", None), ("business_name", 7), ("city", 7), ("street", ["Bay St"]), ("is_specific", "true"), ("is_specific", None), ("is_specific", 1)):
        with pytest.raises((ValidationError, AttributeError, TypeError)):
            read_extracted({**good, field: wrong})                        # a wrong kind of value never becomes a search
    assert "note" not in Extracted.model_fields                           # and the checked reply has no place for the note either


def test_a_company_is_identified_by_its_name_or_by_its_address_and_never_by_a_mix_of_the_two():
    # Phase D, leg D1. A company found by its address has no match level, and the type refuses to give it one (working rule S4).
    by_address = Identification(found_by="address", street="8586 palm pwwy", city="Orlando", tied_others=2)
    assert (by_address.level, by_address.business_name, by_address.evidence) == (None, "", ())
    for mixed in ({"level": "Strong"}, {"business_name": "V Pizza"}, {"evidence": ("ACTIVE",)}, {"street": ""}):
        with pytest.raises(ValidationError):
            Identification(**{"found_by": "address", "street": "8586 palm pwwy", **mixed})
    with pytest.raises(ValidationError):
        Identification(found_by="name", business_name="V Pizza")          # a company found by its name needs its match level
    with pytest.raises(ValidationError):
        Identification(level="Strong", evidence=())                       # and the business name: the default kind is "name"
    with pytest.raises(ValidationError):
        Identification(found_by="phone", business_name="V Pizza", level="Strong")   # only the two kinds exist
    assert "note" not in Identification.model_fields                      # rule W6 still holds: there is nowhere to put the typed note


def test_a_company_on_an_address_list_states_its_name_and_its_address_as_facts():
    candidate = AddressCandidate(document_number="T26000000001", name=a_fact(text="INVENTED PIZZA LLC"), address=a_fact(text="8586 PALM PKWY, ORLANDO, FL 32836"))
    assert candidate.source.source_url.startswith("https://") and "level" not in AddressCandidate.model_fields
    with pytest.raises(ValidationError):
        AddressCandidate(document_number="T26000000001", name=a_fact(text="INVENTED PIZZA LLC"), address="8586 PALM PKWY")   # a bare text is not a fact


def test_the_two_sentences_at_the_top_of_a_report_are_facts_and_there_are_exactly_two():
    # Phase D, leg D2 (working rule S9). The summary states the company's status and its entity type, so both carry their source (rule W1).
    report = a_report()
    assert [fact.source_url for fact in report.headline] == ["https://search.sunbiz.org/Inquiry/CorporationSearch/ByDocumentNumber"] * 2
    for wrong in (("Inactive with the state as of Oct 7, 2026.", "Florida corporation (for profit), on record since 2010."),   # bare texts are not facts
                  (a_fact(text="only one"),), ()):
        with pytest.raises(ValidationError):
            Report(**{**a_report().model_dump(), "headline": wrong})
