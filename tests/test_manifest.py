"""test_manifest.py: offline tests for src/datum/manifest.py, the fetch manifest (ruling R23).

The files "fetched" here are fixtures already in the repo, and the manifest is written to
a temporary folder. Nothing touches the network or data/.

Run from ~/datum:  pytest
"""

import os                                   # sets a file's modification time
from datetime import datetime, timedelta, timezone   # timestamps, time differences and the UTC zone
from pathlib import Path                    # file paths

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.manifest import COLUMNS, FetchRecord, backfill, read_manifest, record_fetch, sha256_of

FIXTURE = Path(__file__).parent / "fixtures" / "duval" / "m2025010301d.16"   # any real file will do: the Clerk's lookup, unchanged
URL = "sftp://ftp.duvalclerk.com/Recording%20Indexes/m2025010301d.16"        # where that file really comes from
UTC_NOON = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)             # a fixed moment, so tests don't depend on the clock


def test_record_fetch_writes_header_then_one_row_per_file(tmp_path):
    manifest = tmp_path / "fetch_manifest.csv"
    record_fetch("duval", FIXTURE, URL, fetched_at_utc=UTC_NOON, manifest_path=manifest)
    record_fetch("duval", FIXTURE, URL, fetched_at_utc=UTC_NOON, manifest_path=manifest)   # fetched again: a second row, nothing rewritten
    lines = manifest.read_text().splitlines()
    assert lines[0] == ",".join(COLUMNS)                                  # the header, once
    assert len(lines) == 3                                                # header + 2 rows
    assert lines[1] == (
        "duval,m2025010301d.16,sftp://ftp.duvalclerk.com/Recording%20Indexes/m2025010301d.16,"
        f"2026-11-18T12:00:00Z,{FIXTURE.stat().st_size},{sha256_of(FIXTURE)},false"
    )


def test_manifest_round_trips_through_the_file(tmp_path):
    manifest = tmp_path / "fetch_manifest.csv"
    written = record_fetch("duval", FIXTURE, URL, fetched_at_utc=UTC_NOON, manifest_path=manifest)
    assert read_manifest(manifest) == [written]                           # what was read back equals what was written
    assert read_manifest(tmp_path / "absent.csv") == []                   # no manifest yet is an empty manifest


def test_fetch_time_defaults_to_now_in_utc(tmp_path):
    record = record_fetch("duval", FIXTURE, URL, manifest_path=tmp_path / "m.csv")
    assert record.fetched_at_utc.utcoffset() == timedelta(0)              # UTC
    assert abs(datetime.now(timezone.utc) - record.fetched_at_utc) < timedelta(seconds=5)
    assert record.is_approximate is False                                 # a measured time


def test_record_without_a_full_source_url_cannot_be_built():
    # CLAUDE.md rule 3: a fact type constructible without a source URL is a bug in the type.
    with pytest.raises(ValueError, match="source_url must be a full address"):
        FetchRecord("duval", "x.16", "", UTC_NOON, 1, "0" * 64)
    with pytest.raises(ValueError, match="source_url must be a full address"):
        FetchRecord("duval", "x.16", "Recording Indexes/x.16", UTC_NOON, 1, "0" * 64)


def test_record_without_a_utc_fetch_time_cannot_be_built():
    # ... and the same for the fetch timestamp: no time zone, or a zone that isn't UTC, is refused.
    with pytest.raises(ValueError, match="time-zone-aware UTC"):
        FetchRecord("duval", "x.16", URL, datetime(2026, 11, 18, 12, 0, 0), 1, "0" * 64)
    eastern = timezone(timedelta(hours=-5))
    with pytest.raises(ValueError, match="time-zone-aware UTC"):
        FetchRecord("duval", "x.16", URL, datetime(2026, 11, 18, 7, 0, 0, tzinfo=eastern), 1, "0" * 64)


def test_unknown_source_is_refused():
    with pytest.raises(ValueError, match="unknown source"):
        FetchRecord("duvall", "x.16", URL, UTC_NOON, 1, "0" * 64)


def test_backfill_uses_the_modification_time_and_marks_it_approximate(tmp_path):
    on_disk = tmp_path / "m2025010301d.16"
    on_disk.write_bytes(FIXTURE.read_bytes())
    os.utime(on_disk, (UTC_NOON.timestamp(), UTC_NOON.timestamp()))       # pretend the file was downloaded at UTC noon
    manifest = tmp_path / "fetch_manifest.csv"
    assert backfill("duval", [(on_disk, URL, None)], manifest) == 1
    (record,) = read_manifest(manifest)                                   # exactly one row
    assert record.fetched_at_utc == UTC_NOON
    assert record.is_approximate is True
    assert record.sha256 == sha256_of(FIXTURE)


def test_backfill_never_adds_a_second_row_for_a_recorded_file(tmp_path):
    manifest = tmp_path / "fetch_manifest.csv"
    record_fetch("duval", FIXTURE, URL, fetched_at_utc=UTC_NOON, manifest_path=manifest)   # a measured row exists
    assert backfill("duval", [(FIXTURE, URL, None)], manifest) == 0       # so the backfill leaves it alone
    assert backfill("sunbiz_flr", [(FIXTURE, URL, None), (FIXTURE, URL, None)], manifest) == 1   # another source, listed twice: added once
    assert len(read_manifest(manifest)) == 2


def test_backfill_can_take_the_time_from_another_file(tmp_path):
    # A file unpacked from a zip keeps the time the source wrote it; the zip's own time is when we downloaded.
    unpacked = tmp_path / "FLRF.TXT"
    unpacked.write_bytes(b"x")
    os.utime(unpacked, (UTC_NOON.timestamp() - 86400 * 30, UTC_NOON.timestamp() - 86400 * 30))   # written by the source a month earlier
    archive = tmp_path / "flrf.zip"
    archive.write_bytes(b"zip")
    os.utime(archive, (UTC_NOON.timestamp(), UTC_NOON.timestamp()))       # downloaded at UTC noon
    manifest = tmp_path / "fetch_manifest.csv"
    backfill("sunbiz_flr", [(unpacked, "sftp://sftp.floridados.gov/doc/quarterly/flr/flrf.zip", archive)], manifest)
    assert read_manifest(manifest)[0].fetched_at_utc == UTC_NOON
