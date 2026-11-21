"""test_sunbiz_cor.py: offline tests for src/datum/sunbiz_cor.py, the fetch-manifest rows for the state's corporate files.

Every file here is made inside pytest's temporary folder, from invented bytes. The real
corporate files are 1.9 GB each and hold every company in Florida, so none is a fixture.
What is under test is which files get a row, where each row's time comes from, and what
happens when a file is missing. None of that depends on what a file holds.

Run from ~/datum:  pytest
"""

import hashlib                              # the checksum the module is expected to arrive at
import os                                   # sets a file's modification time
import zipfile                              # builds the small stand-in for cordata.zip
from datetime import datetime, timezone     # timestamps and the UTC zone

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.manifest import read_manifest
from datum.sunbiz_cor import backfill_manifest, daily_files, snapshot_records

DOWNLOADED = datetime(2026, 10, 22, 19, 31, 0, tzinfo=timezone.utc)      # when the stand-in zip "was downloaded"
STATE_WROTE = (2026, 10, 7, 9, 24, 0)                                    # the time the state stamped on the files inside it
DAILY_DOWNLOADED = datetime(2026, 10, 12, 19, 33, 0, tzinfo=timezone.utc)


def make_snapshot(raw_dir, members):
    """Write quarterly/cordata.zip under raw_dir holding the given {member name: bytes}, dated DOWNLOADED."""
    archive = raw_dir / "quarterly" / "cordata.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, content in members.items():
            bundle.writestr(zipfile.ZipInfo(name, date_time=STATE_WROTE), content)   # each member carries the STATE's time
    os.utime(archive, (DOWNLOADED.timestamp(), DOWNLOADED.timestamp()))
    return archive


def make_daily(raw_dir, name="20261009c.txt", content=b"one daily line\n"):
    path = raw_dir / name
    path.write_bytes(content)
    os.utime(path, (DAILY_DOWNLOADED.timestamp(), DAILY_DOWNLOADED.timestamp()))
    return path


def test_snapshot_rows_take_their_time_from_the_zip_not_from_the_files_inside(tmp_path):
    archive = make_snapshot(tmp_path, {"cordata0.txt": b"zero", "cordata1.txt": b"one-one"})
    first, second = snapshot_records(archive)
    assert (first.file_name, second.file_name) == ("cordata0.txt", "cordata1.txt")
    assert first.fetched_at_utc == DOWNLOADED                             # the zip's time; the member's own time is 2026-10-07
    assert first.is_approximate is True and second.is_approximate is True
    assert first.source_url == "sftp://sftp.floridados.gov/doc/quarterly/cor/cordata.zip"
    assert (second.size_bytes, second.sha256) == (7, hashlib.sha256(b"one-one").hexdigest())   # of the UNPACKED member


def test_a_member_larger_than_one_block_is_read_whole(tmp_path, monkeypatch):
    monkeypatch.setattr("datum.sunbiz_cor.BLOCK_BYTES", 4)                # 4 bytes a block, so 10 bytes take three reads
    archive = make_snapshot(tmp_path, {"cordata0.txt": b"0123456789"})
    (record,) = snapshot_records(archive)
    assert (record.size_bytes, record.sha256) == (10, hashlib.sha256(b"0123456789").hexdigest())


def test_a_zip_that_cannot_be_read_whole_raises_and_names_the_member(tmp_path):
    archive = make_snapshot(tmp_path, {"cordata0.txt": b"zero" * 1000})
    damaged = archive.read_bytes()
    archive.write_bytes(damaged[:2000] + b"XXXX" + damaged[2004:])        # four bytes of the member's data are overwritten
    with pytest.raises(ValueError, match="could not read cordata0.txt whole"):
        snapshot_records(archive)


def test_other_members_of_the_zip_get_no_row(tmp_path):
    archive = make_snapshot(tmp_path, {"cordata0.txt": b"a", "readme.txt": b"b", "cordata10.txt": b"c", "xcordata1.txt": b"d"})
    assert [r.file_name for r in snapshot_records(archive)] == ["cordata0.txt"]


def test_daily_files_are_picked_by_name(tmp_path):
    for name in ("20261009c.txt", "20261008c.txt", "20261009ce.txt", "20261009f.txt", "notes.txt"):   # ce = corporate events, f = fictitious names
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "20261010c.txt").mkdir()                                  # a folder with a file's name is not a file
    assert [p.name for p in daily_files(tmp_path)] == ["20261008c.txt", "20261009c.txt"]
    assert daily_files(tmp_path / "absent") == []


def test_backfill_adds_one_row_per_file_on_disk_and_nothing_the_second_time(tmp_path):
    make_daily(tmp_path)
    make_snapshot(tmp_path, {"cordata0.txt": b"zero", "cordata1.txt": b"one"})
    manifest = tmp_path / "fetch_manifest.csv"
    assert backfill_manifest(tmp_path, manifest) == 3
    by_name = {r.file_name: r for r in read_manifest(manifest)}
    assert set(by_name) == {"20261009c.txt", "cordata0.txt", "cordata1.txt"}
    assert {r.source for r in by_name.values()} == {"sunbiz_cor"}
    assert all(r.is_approximate for r in by_name.values())                # none of these times was measured
    assert by_name["20261009c.txt"].fetched_at_utc == DAILY_DOWNLOADED    # a daily file's own time
    assert by_name["20261009c.txt"].source_url == "sftp://sftp.floridados.gov/doc/cor/20261009c.txt"
    assert by_name["cordata1.txt"].fetched_at_utc == DOWNLOADED
    assert backfill_manifest(tmp_path, manifest) == 0
    assert len(read_manifest(manifest)) == 3


def test_a_file_that_is_not_on_disk_gets_no_row(tmp_path):
    manifest = tmp_path / "fetch_manifest.csv"
    assert backfill_manifest(tmp_path, manifest) == 0                     # no daily file and no zip: nothing is estimated
    assert read_manifest(manifest) == []
    make_daily(tmp_path)
    assert backfill_manifest(tmp_path, manifest) == 1                     # the daily file alone, and still no snapshot rows
    assert [r.file_name for r in read_manifest(manifest)] == ["20261009c.txt"]


def test_backfill_adds_only_the_members_that_have_no_row_yet(tmp_path):
    archive = make_snapshot(tmp_path, {"cordata0.txt": b"zero"})
    manifest = tmp_path / "fetch_manifest.csv"
    assert backfill_manifest(tmp_path, manifest) == 1
    archive.unlink()
    archive.parent.rmdir()
    make_snapshot(tmp_path, {"cordata0.txt": b"zero", "cordata1.txt": b"one"})   # the same snapshot, with one more file in it
    assert backfill_manifest(tmp_path, manifest) == 1
    assert [r.file_name for r in read_manifest(manifest)] == ["cordata0.txt", "cordata1.txt"]
