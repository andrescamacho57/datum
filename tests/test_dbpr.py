"""test_dbpr.py: offline tests for src/datum/dbpr.py.

Every test reads a small file under tests/fixtures/dbpr/ that was cut from a real DBPR
download (origin and capture date: tests/fixtures/dbpr/README.md). No test touches the
network: the download test fetches a fixture through a file:// address instead.

Run from ~/datum:  pytest
"""

from dataclasses import replace             # makes a copy of a frozen dataclass with some fields changed
from pathlib import Path                    # file paths

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.dbpr import DISCIPLINE_FILES, DISCIPLINE_HEADER, LICENSE_FILE, DbprFile, DbprValidationError

FIXTURES = Path(__file__).parent / "fixtures" / "dbpr"     # tests/fixtures/dbpr/


def license_spec(file_name: str) -> DbprFile:
    """The real license-file spec, pointed at a fixture and with the row minimum lowered to fit 20 rows."""
    return replace(LICENSE_FILE, file_name=file_name, min_rows=20)


def discipline_spec(file_name: str) -> DbprFile:
    """The real discipline-file spec, pointed at a fixture and with the row minimum lowered to fit 19 rows."""
    return replace(DISCIPLINE_FILES[0], file_name=file_name, min_rows=19)


def test_license_fixture_passes_and_counts_every_line_as_data():
    # The license file has no header row, so 20 lines = 20 data rows.
    report = license_spec("construction_license_20.csv").validate(FIXTURES)
    assert report.file_lines == 20
    assert report.data_rows == 20


def test_discipline_fixture_passes_and_does_not_count_the_header():
    # The discipline file has a header row, so 20 lines = 19 data rows.
    report = discipline_spec("contractor_disc_lic_19.csv").validate(FIXTURES)
    assert report.file_lines == 20
    assert report.data_rows == 19


def test_row_with_wrong_column_count_is_rejected_and_names_the_row():
    # Row 5 of this fixture has 19 fields, not 22. The error must say which row.
    with pytest.raises(DbprValidationError, match="row 5 has 19 columns, expected 22"):
        license_spec("construction_license_bad_columns.csv").validate(FIXTURES)


def test_file_cut_off_mid_row_is_rejected():
    # A download that stopped early ends without a line break.
    with pytest.raises(DbprValidationError, match="cut off"):
        license_spec("construction_license_truncated.csv").validate(FIXTURES)


def test_changed_header_is_rejected():
    # If the state renames or moves a column, loading by position would put data in the wrong column.
    with pytest.raises(DbprValidationError, match="header changed"):
        discipline_spec("contractor_disc_lic_bad_header.csv").validate(FIXTURES)


def test_too_few_rows_is_rejected():
    # The real spec expects at least 200,000 rows; a 20-row file must fail it.
    with pytest.raises(DbprValidationError, match="20 data rows, expected at least 200000"):
        replace(LICENSE_FILE, file_name="construction_license_20.csv").validate(FIXTURES)


def test_missing_file_is_rejected(tmp_path):
    # tmp_path is an empty temporary folder pytest creates for this one test.
    with pytest.raises(DbprValidationError, match="file not found"):
        LICENSE_FILE.validate(tmp_path)


def test_empty_file_is_rejected(tmp_path):
    (tmp_path / LICENSE_FILE.file_name).write_bytes(b"")           # a zero-byte file with the right name
    with pytest.raises(DbprValidationError, match="file is empty"):
        LICENSE_FILE.validate(tmp_path)


def test_download_saves_the_bytes_unchanged_and_leaves_no_partial_file(tmp_path):
    # file:// makes urllib read a local file through the same code path as https://, so no network and no mock.
    source = FIXTURES / "construction_license_20.csv"
    spec = replace(license_spec("construction_license_20.csv"), url=source.as_uri())
    saved = spec.download(tmp_path)
    assert saved.read_bytes() == source.read_bytes()               # raw stays raw: byte for byte
    assert [p.name for p in tmp_path.iterdir()] == ["construction_license_20.csv"]   # the .part file was renamed away


def test_specs_match_what_the_state_publishes():
    # Guards the settings themselves: six files, the right shapes, addresses on the state's site.
    assert LICENSE_FILE.expected_columns == 22 and LICENSE_FILE.expected_header is None
    assert len(DISCIPLINE_FILES) == 5
    assert all(f.expected_columns == len(DISCIPLINE_HEADER) == 17 for f in DISCIPLINE_FILES)
    assert all(f.url.startswith("https://www2.myfloridalicense.com/") for f in (LICENSE_FILE, *DISCIPLINE_FILES))
