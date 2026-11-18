"""test_sunbiz_flr.py: offline tests for src/datum/sunbiz_flr.py.

Every test reads a small file under tests/fixtures/sunbiz_flr/ that was cut from the
state's real daily federal lien files (origin and capture date: the README there). No
test opens a connection: the download test talks to a stand-in that serves the fixtures.

Run from ~/datum:  pytest
"""

import shutil                               # copies fixture files into a temporary folder
from datetime import date                   # calendar dates
from pathlib import Path                    # file paths
from types import SimpleNamespace           # a quick object with named fields, for the stand-in's folder listing

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.manifest import read_manifest
from datum.sunbiz_flr import (
    KINDS, SNAPSHOT_DATE, FlrDailyFile, FlrInspectionError, backfill_manifest, download_missing,
    inspect_all, inspect_file, local_files, missing_business_days,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sunbiz_flr"   # tests/fixtures/sunbiz_flr/


def test_file_name_gives_kind_and_date():
    # The eight digits are the publish date; the letter after "flr" says which of the four kinds.
    daily = FlrDailyFile.from_name("20261104flrf.txt")
    assert (daily.kind.name, daily.kind.line_length, daily.file_date) == ("filings", 82, date(2026, 11, 4))
    assert FlrDailyFile.from_name("20261104flrd.txt").kind.name == "debtors"
    assert FlrDailyFile.from_name("20261104flre.txt").kind.name == "events"
    assert FlrDailyFile.from_name("20261104flrs.txt").kind.name == "secured"


def test_source_url_points_at_the_exact_file():
    # CLAUDE.md rule 3: the URL names the specific file, not the server's front door.
    assert FlrDailyFile.from_name("20261104flre.txt").source_url == "sftp://sftp.floridados.gov/doc/flr/events/20261104flre.txt"


def test_other_names_in_the_folders_are_ignored():
    # The folders also hold year sub-folders, and the quarterly snapshot uses other names.
    assert FlrDailyFile.from_name("2020") is None
    assert FlrDailyFile.from_name("FLRF.TXT") is None
    assert FlrDailyFile.from_name("20261104c.txt") is None                # a corporate daily file, not a lien file
    assert FlrDailyFile.from_name("20261304flrf.txt") is None             # month 13 is not a date


@pytest.mark.parametrize(                   # run the same test once per (file, length, expected rows)
    "name, line_length, expected_rows",
    [("20261104flrf.txt", 82, 42), ("20261104flre.txt", 135, 29), ("20261104flrd.txt", 206, 10)],
)
def test_real_files_have_every_line_the_documented_length(name, line_length, expected_rows):
    assert inspect_file(FIXTURES / name, line_length).rows == expected_rows


def test_short_line_is_rejected_and_names_the_line():
    # Line 3 lost its last 5 characters, so every field after the cut would be read from the wrong place.
    with pytest.raises(FlrInspectionError, match="line 3 is 77 characters, expected 82"):
        inspect_file(FIXTURES / "20261105flrf.txt", 82)


def test_file_cut_off_mid_line_is_rejected():
    with pytest.raises(FlrInspectionError, match="cut off"):
        inspect_file(FIXTURES / "20261106flrf.txt", 82)


def test_quarterly_line_endings_do_not_count_toward_the_length(tmp_path):
    # The quarterly files end lines with CRLF; the carriage return is not part of the 82 characters.
    crlf = tmp_path / "20261104flrf.txt"
    crlf.write_bytes((FIXTURES / "20261104flrf.txt").read_bytes().replace(b"\n", b"\r\n"))
    assert inspect_file(crlf, 82).rows == 42


def test_local_files_keeps_only_dailies_on_or_after_the_snapshot(tmp_path):
    for name in ("20261002flrf.txt", "20261003flrf.txt", "20261104flre.txt", "FLRF.TXT", "notes.txt"):
        (tmp_path / name).write_bytes(b"")
    assert [path.name for path, _ in local_files(tmp_path)] == ["20261003flrf.txt", "20261104flre.txt"]
    assert SNAPSHOT_DATE == date(2026, 10, 3)


def test_missing_business_days_skips_weekends():
    # 2026-11-02 is a Monday. Files exist for Monday and Wednesday; the range runs to the next Monday.
    present = {date(2026, 11, 2), date(2026, 11, 4)}
    assert missing_business_days(present, date(2026, 11, 2), date(2026, 11, 9)) == [
        date(2026, 11, 3), date(2026, 11, 5), date(2026, 11, 6), date(2026, 11, 9),   # Tue, Thu, Fri, Mon; never Sat 7 or Sun 8
    ]


def test_inspect_all_prints_the_table_and_quarantines_bad_files(tmp_path, capsys):
    for fixture in FIXTURES.glob("*.txt"):                                # copy, because quarantine MOVES files
        shutil.copy(fixture, tmp_path / fixture.name)
    assert inspect_all(tmp_path, quarantine=True, today=date(2026, 11, 7)) == 2   # the two corrupted fixtures
    printed = capsys.readouterr().out
    assert "FAIL  20261105flrf.txt: line 3 is 77 characters, expected 82" in printed
    assert "2026-11-04          42       10       29        -" in printed  # rows per kind; the dash = no secured file that day
    assert "OK    3 files on 1 days" in printed
    assert "2026-11-05, 2026-11-06" in printed and "2026-11-04," not in printed   # quiet business days are listed; the day with files isn't
    assert sorted(p.name for p in (tmp_path / "rejected").iterdir()) == ["20261105flrf.txt", "20261106flrf.txt"]


class StandInServer:
    """Plays the state's SFTP server for download_missing(): lists and serves the fixture files."""

    def __init__(self) -> None:
        self.fetched: list[str] = []                                      # every path the code asked for, in order

    def listdir_attr(self, remote_dir: str) -> list[SimpleNamespace]:
        letter = next(kind.letter for kind in KINDS if kind.remote_dir == remote_dir)   # which kind this folder holds
        entries = [SimpleNamespace(filename="2020", st_size=0)]           # a year sub-folder, which must be ignored
        for fixture in sorted(FIXTURES.glob(f"20261104flr{letter}.txt")):
            entries.append(SimpleNamespace(filename=fixture.name, st_size=fixture.stat().st_size))
        return entries

    def get(self, remote_path: str, local_path: str) -> None:
        self.fetched.append(remote_path)
        shutil.copy(FIXTURES / Path(remote_path).name, local_path)


def test_download_fetches_each_missing_file_once_and_writes_a_manifest_row(tmp_path, monkeypatch):
    monkeypatch.setattr("datum.sunbiz_flr.PAUSE_SECONDS", 0)              # no need to wait between files in a test
    server, manifest = StandInServer(), tmp_path / "fetch_manifest.csv"
    assert download_missing(server, tmp_path, manifest) == (3, 0)         # filings, debtors, events; no secured fixture
    assert server.fetched == ["doc/flr/debtors/20261104flrd.txt", "doc/flr/events/20261104flre.txt", "doc/flr/filings/20261104flrf.txt"]
    records = read_manifest(manifest)
    assert [(r.source, r.file_name, r.is_approximate) for r in records] == [
        ("sunbiz_flr", "20261104flrd.txt", False), ("sunbiz_flr", "20261104flre.txt", False), ("sunbiz_flr", "20261104flrf.txt", False),
    ]
    assert records[1].source_url == "sftp://sftp.floridados.gov/doc/flr/events/20261104flre.txt"
    assert download_missing(server, tmp_path, manifest) == (0, 3)         # a second run asks for nothing
    assert len(read_manifest(manifest)) == 3                              # and adds no rows


def test_backfill_covers_dailies_and_the_unzipped_snapshot(tmp_path):
    shutil.copy(FIXTURES / "20261104flrf.txt", tmp_path / "20261104flrf.txt")   # a daily file already on disk
    (tmp_path / "FLRF.TXT").write_bytes(b"snapshot")                      # the unzipped snapshot ...
    (tmp_path / "flrf.zip").write_bytes(b"zip")                           # ... and the zip it came in
    manifest = tmp_path / "fetch_manifest.csv"
    assert backfill_manifest(tmp_path, manifest) == 2
    by_name = {r.file_name: r for r in read_manifest(manifest)}
    assert by_name["FLRF.TXT"].source_url == "sftp://sftp.floridados.gov/doc/quarterly/flr/flrf.zip"   # the snapshot's address is the zip
    assert all(r.is_approximate for r in by_name.values())
    assert backfill_manifest(tmp_path, manifest) == 0                     # nothing new the second time
