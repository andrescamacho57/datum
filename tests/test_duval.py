"""test_duval.py: offline tests for src/datum/duval.py.

Every test reads a small file under tests/fixtures/duval/ that was cut from a real Duval
recording index file (origin and capture date: tests/fixtures/duval/README.md). No test
opens a connection: only the name parsing and the EOF check are tested here.

Run from ~/datum:  pytest
"""

import shutil                               # copies fixture files into a temporary folder
from datetime import date                   # calendar dates, to compare with a parsed file date
from pathlib import Path                    # file paths
from types import SimpleNamespace           # a quick object with named fields, for the stand-in's folder listing

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.duval import (
    START_DATE, DuvalFile, DuvalVerificationError, backfill_manifest, download_missing, local_files,
    repair_all, repair_file, repair_lines, verify_all, verify_file,
)
from datum.manifest import read_manifest

FIXTURES = Path(__file__).parent / "fixtures" / "duval"    # tests/fixtures/duval/
REJECTED = FIXTURES / "rejected"                           # files broken the way the Clerk's 13 rejected files are


def test_file_name_gives_kind_and_date():
    # The first letter says what the file holds; the next eight digits are the file's date.
    assert DuvalFile.from_name("d2026110501id.16") == DuvalFile("d2026110501id.16", "documents", date(2026, 11, 5))
    assert DuvalFile.from_name("p2026110501id.16").kind == "parties"
    assert DuvalFile.from_name("l2026110501id.16").kind == "links"
    assert DuvalFile.from_name("m2026110501d.16").kind == "doc_types"     # the lookup file's name ends "d", not "id"


def test_other_names_in_the_folder_are_ignored():
    # The Clerk's folder also holds Thumbs.db and a few files ending .16c or .16d. None is an index file.
    assert DuvalFile.from_name("Thumbs.db") is None
    assert DuvalFile.from_name("m2019080101d.16c") is None
    assert DuvalFile.from_name("p2020010101id.16d") is None
    assert DuvalFile.from_name("d2025139901id.16") is None                # month 13 is not a date


@pytest.mark.parametrize(                   # run the same test once per (file, expected rows) pair
    "name, expected_rows",
    [("d2025010301id.16", 11), ("p2025010301id.16", 32), ("l2025010301id.16", 13), ("m2025010301d.16", 85)],
)
def test_row_count_matches_the_eof_trailer(name, expected_rows):
    report = verify_file(FIXTURES / name)
    assert report.rows == expected_rows
    assert report.eof_count == expected_rows


def test_file_with_nothing_recorded_passes_with_zero_rows(tmp_path):
    # On a day with nothing recorded the Clerk sends a 7-byte file: EOF|0 and a line break.
    empty_day = tmp_path / "d2025010101id.16"
    empty_day.write_bytes(b"EOF|0\r\n")
    assert verify_file(empty_day).rows == 0


def test_trailer_that_disagrees_with_the_rows_is_rejected():
    # 11 rows in the file, but the trailer says 12: a row went missing somewhere.
    with pytest.raises(DuvalVerificationError, match=r"11 rows in the file, but the trailer says EOF\|12"):
        verify_file(FIXTURES / "d2025010401id.16")


def test_file_without_a_trailer_is_rejected():
    # A download that stopped early never reaches the trailer line.
    with pytest.raises(DuvalVerificationError, match="no EOF trailer"):
        verify_file(FIXTURES / "d2025010501id.16")


def test_local_files_keeps_only_in_scope_index_files(tmp_path):
    # tmp_path is an empty temporary folder pytest creates for this one test.
    for name in ("d2024123101id.16", "d2025010101id.16", "m2025010101d.16", "Thumbs.db", "notes.16"):
        (tmp_path / name).write_bytes(b"EOF|0\r\n")
    names = [path.name for path, _ in local_files(tmp_path)]
    assert names == ["d2025010101id.16", "m2025010101d.16"]              # 2024 is before START_DATE; the others aren't index files
    assert START_DATE == date(2025, 1, 1)


def test_verify_all_counts_failures_and_keeps_going(capsys):
    # capsys captures what the code prints, so the test can read it.
    failures = verify_all(FIXTURES)
    printed = capsys.readouterr().out
    assert failures == 2                                                  # the two corrupted fixtures
    assert "FAIL  d2025010401id.16" in printed and "FAIL  d2025010501id.16" in printed
    assert "OK    documents: 1 files, 11 rows" in printed                  # the good files were still checked
    assert (FIXTURES / "d2025010401id.16").exists()                       # without quarantine, nothing is moved


def test_quarantine_moves_failing_files_out_of_the_upload_folder(tmp_path):
    # Copy the fixtures to a temporary folder, because quarantine MOVES files.
    for fixture in FIXTURES.glob("*.16"):
        shutil.copy(fixture, tmp_path / fixture.name)
    assert verify_all(tmp_path, quarantine=True) == 2
    assert sorted(p.name for p in (tmp_path / "rejected").iterdir()) == ["d2025010401id.16", "d2025010501id.16"]
    assert [p.name for p, _ in local_files(tmp_path)] == [                # what's left is exactly the good files
        "d2025010301id.16", "l2025010301id.16", "m2025010301d.16", "p2025010301id.16",
    ]
    assert verify_all(tmp_path, quarantine=True) == 0                     # a second run finds nothing left to fail


# --- Repair (ruling R15) ----------------------------------------------------------------


def test_broken_record_fails_verification_before_repair():
    # 14 records, but two are split by a line break and one of those also has a blank line: 17 lines.
    with pytest.raises(DuvalVerificationError, match=r"17 rows in the file, but the trailer says EOF\|14"):
        verify_file(REJECTED / "d2026011501id.16")


def test_repair_joins_continuation_lines_with_one_space(tmp_path):
    report = repair_file(REJECTED / "d2026011501id.16", tmp_path)
    assert (report.rows, report.lines_joined, report.blank_lines_dropped) == (14, 2, 1)
    repaired = (tmp_path / "d2026011501id.16").read_bytes().split(b"\r\n")
    # The record that was spread over three lines (text, blank, rest) is one line again, with one space at the join.
    # The instrument number, book, page and legal description are invented (see the fixture README); the break is where the Clerk's was.
    assert b"DDA|16|2004900004|MTG|MORTGAGE|L4 B1 INVENTED ACRES |OR|90010|119||6|11/03/2004|8210|35500.00|" in repaired
    assert b"DDA|16|2004900010|MTG|MORTGAGE|SEC 99 9 99 INVENTED |OR|90010|155||6|11/03/2004|8210|100000.00|" in repaired
    assert all(line.startswith(b"DDA|") for line in repaired[:-2])        # every data line starts a record again
    assert repaired[-2:] == [b"EOF|14", b""]                              # the Clerk's trailer is kept as sent
    assert verify_file(tmp_path / "d2026011501id.16").rows == 14          # and the copy now passes the same check as any file


def test_repair_drops_the_blank_line_in_a_links_file(tmp_path):
    # Links rows have no record marker, so the only repair is dropping the blank line.
    report = repair_file(REJECTED / "l2026021901id.16", tmp_path)
    assert (report.rows, report.lines_joined, report.blank_lines_dropped) == (7, 0, 1)


def test_repair_never_changes_the_file_as_sent(tmp_path):
    original = REJECTED / "d2026011501id.16"
    before = original.read_bytes()
    repair_file(original, tmp_path)
    assert original.read_bytes() == before                                # the evidence stays byte for byte


def test_repair_that_still_disagrees_with_the_trailer_leaves_no_copy(tmp_path):
    # Same 14 records, but the trailer claims 15: a record really is missing, and joining lines can't bring it back.
    with pytest.raises(DuvalVerificationError, match=r"d2026011601id\.16: 14 rows in the file, but the trailer says EOF\|15 \(after repair\)"):
        repair_file(REJECTED / "d2026011601id.16", tmp_path)
    assert list(tmp_path.iterdir()) == []                                 # nothing was left where the upload would look


def test_repair_keeps_a_first_line_that_starts_with_a_byte_order_mark():
    # Three of the Clerk's files start with a byte-order mark, so line 1 doesn't begin with DDA|. It must not be glued to nothing.
    lines = [b"\xef\xbb\xbfDDA|16|1|", b"DDA|16|2|LEGAL", b"|OR|", b"", b"DDA|16|3|"]
    mended, joined, dropped = repair_lines(lines, b"DDA|")
    assert mended == [b"\xef\xbb\xbfDDA|16|1|", b"DDA|16|2|LEGAL |OR|", b"DDA|16|3|"]
    assert (joined, dropped) == (1, 1)


def test_repair_all_repairs_what_it_can_and_reports_the_rest(tmp_path, capsys):
    shutil.copytree(REJECTED, tmp_path / "rejected")                      # repair_all reads <raw_dir>/rejected/
    assert repair_all(tmp_path) == 1                                      # the EOF|15 file can't be repaired
    printed = capsys.readouterr().out
    assert "OK    d2026011501id.16: 14 rows = EOF count; joined 2 line(s), dropped 1 blank line(s)" in printed
    assert "FAIL  d2026011601id.16" in printed
    assert sorted(p.name for p in (tmp_path / "repaired").iterdir()) == ["d2026011501id.16", "l2026021901id.16"]
    assert len(list((tmp_path / "rejected").iterdir())) == 3              # the originals are all still there


# --- Fetch manifest (ruling R23) --------------------------------------------------------


def test_source_url_names_the_exact_file_and_no_login():
    url = DuvalFile.from_name("d2026110501id.16").source_url
    assert url == "sftp://ftp.duvalclerk.com/Recording%20Indexes/d2026110501id.16"   # the space in the folder name is written %20
    assert "@" not in url                                                 # an address can carry a login before the host; this one must not


class StandInServer:
    """Plays the Clerk's SFTP server for download_missing(): lists and serves the good fixture files."""

    def listdir_attr(self, remote_dir: str) -> list[SimpleNamespace]:
        names = ("d2025010301id.16", "p2025010301id.16", "Thumbs.db")     # two index files and one file to ignore
        return [SimpleNamespace(filename=n, st_size=(FIXTURES / n).stat().st_size if n.endswith(".16") else 1) for n in names]

    def get(self, remote_path: str, local_path: str) -> None:
        shutil.copy(FIXTURES / Path(remote_path).name, local_path)


def test_download_writes_one_manifest_row_per_fetched_file(tmp_path, monkeypatch):
    monkeypatch.setattr("datum.duval.PAUSE_SECONDS", 0)                   # no need to wait between files in a test
    raw_dir, manifest = tmp_path / "raw", tmp_path / "fetch_manifest.csv"
    assert download_missing(StandInServer(), raw_dir, manifest) == (2, 0)
    records = read_manifest(manifest)
    assert [(r.source, r.file_name, r.is_approximate) for r in records] == [
        ("duval", "d2025010301id.16", False), ("duval", "p2025010301id.16", False),
    ]
    assert download_missing(StandInServer(), raw_dir, manifest) == (0, 2)  # already on disk at the same size: no request, no new row
    assert len(read_manifest(manifest)) == 2


def test_backfill_covers_verified_and_rejected_files_but_not_repaired_copies(tmp_path):
    shutil.copy(FIXTURES / "d2025010301id.16", tmp_path / "d2025010301id.16")       # a file that passed
    shutil.copytree(REJECTED, tmp_path / "rejected")                                # three files as sent, quarantined
    repair_all(tmp_path)                                                            # makes repaired/ copies of two of them
    manifest = tmp_path / "fetch_manifest.csv"
    assert backfill_manifest(tmp_path, manifest) == 4                               # 1 verified + 3 rejected; repaired copies were never fetched
    assert all(r.is_approximate for r in read_manifest(manifest))
    assert backfill_manifest(tmp_path, manifest) == 0                               # nothing new the second time
