"""test_duval.py: offline tests for src/datum/duval.py.

Every test reads a small file under tests/fixtures/duval/ that was cut from a real Duval
recording index file (origin and capture date: tests/fixtures/duval/README.md). No test
opens a connection: only the name parsing and the EOF check are tested here.

Run from ~/datum:  pytest
"""

import shutil                               # copies fixture files into a temporary folder
from datetime import date                   # calendar dates, to compare with a parsed file date
from pathlib import Path                    # file paths

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.duval import START_DATE, DuvalFile, DuvalVerificationError, local_files, verify_all, verify_file

FIXTURES = Path(__file__).parent / "fixtures" / "duval"    # tests/fixtures/duval/


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
    [("d2025010301id.16", 12), ("p2025010301id.16", 34), ("l2025010301id.16", 14), ("m2025010301d.16", 85)],
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
    # 12 rows in the file, but the trailer says 13: a row went missing somewhere.
    with pytest.raises(DuvalVerificationError, match=r"12 rows in the file, but the trailer says EOF\|13"):
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
    assert "OK    documents: 1 files, 12 rows" in printed                  # the good files were still checked
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
