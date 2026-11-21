"""test_load_postgres.py: offline tests for src/datum/load_postgres.py, the loader that copies the export into Postgres.

No database is opened. The loader is handed a stand-in for the connection (FakeConnection
below) that writes down every statement it is given, in order, and counts the rows it is
sent. So the tests can prove the ORDER of the steps: every table is loaded and counted
before anything is swapped, and a wrong count stops the run before the swap.

What these tests cannot prove is that Postgres accepts the statements. That is proven by
the real load, whose counts are in the leg report (docs/legs/c2-postgres-search.md).

Every file is made in pytest's temporary folder from invented rows. Run from ~/datum:  pytest
"""

import csv                                  # writes the small export files and reads back what the loader sent
import gzip                                 # the export is gzip-compressed
import io                                   # turns bytes into a text stream for the csv module

import pytest                               # the test runner; pytest.raises checks that an error IS raised

from datum.load_postgres import (
    TABLES, ExportError, check_header, create_statement, export_files, load, read_expected_counts, swap_statements,
)

BY_NAME = {table.name: table for table in TABLES}


def write_export(export_dir, table_name, rows, header=None, file_name=None):
    """Write one gzip CSV file for a table, with its header line, the way script 23 does."""
    table = BY_NAME.get(table_name)
    header = header or [name.upper() for name, _ in table.columns]        # Snowflake writes column names in capitals
    folder = export_dir / table_name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (file_name or f"{table_name}_0_0_0.csv.gz")
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:   # wt = write as text
        writer = csv.writer(handle, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def a_row(table_name, number):
    """One invented row with the right number of cells. The loader never looks inside a cell."""
    return [f"{table_name}-{number}"] + ["x"] * (len(BY_NAME[table_name].columns) - 1)


def write_counts(export_dir, counts):
    write_export(export_dir, "export_counts", list(counts.items()), header=["TABLE_NAME", "ROW_COUNT"], file_name="export_counts.csv.gz")


def a_full_export(export_dir, counts=None):
    """A small, consistent export: 3 companies, 2 flags, no possible matches (so no file), 5 sources."""
    write_export(export_dir, "company_search", [a_row("company_search", n) for n in range(3)])
    write_export(export_dir, "company_flags", [a_row("company_flags", n) for n in range(2)])
    write_export(export_dir, "source_coverage", [a_row("source_coverage", n) for n in range(5)])
    write_counts(export_dir, counts or {"company_search": 3, "company_flags": 2, "company_possible_matches": 0, "source_coverage": 5})


class FakeConnection:
    """Stands in for a psycopg connection: it records every statement and counts the rows copied into each table."""

    def __init__(self):
        self.log = []                       # every statement, in the order it arrived, plus BEGIN and COMMIT markers
        self.rows = {}                      # table name → rows copied into it

    def execute(self, statement, params=None):
        self.log.append(" ".join(statement.split()))                      # one line per statement, extra spaces removed
        words = statement.split()
        if words[:2] == ["create", "table"]:
            self.rows[words[2]] = 0                                       # a new, empty table
        if statement.startswith("select count(*) from "):
            return FakeResult(self.rows[words[-1]])
        return FakeResult(None)

    def cursor(self):
        return FakeCursor(self)

    def transaction(self):
        return FakeTransaction(self)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return (self.value,)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def copy(self, statement):
        self.conn.log.append(" ".join(statement.split()))
        return FakeCopy(self.conn, statement.split()[1])                  # word 2 of "copy <table> (...)" is the table


class FakeCopy:
    def __init__(self, conn, table):
        self.conn, self.table, self.data = conn, table, b""

    def __enter__(self):
        return self

    def write(self, block):
        self.data += block

    def __exit__(self, *exc):
        lines = list(csv.reader(io.StringIO(self.data.decode("utf-8"))))
        self.conn.rows[self.table] += len(lines) - 1                      # every line but the header is a row
        return False


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.log.append("BEGIN")

    def __exit__(self, exc_type, *rest):
        self.conn.log.append("COMMIT" if exc_type is None else "ROLLBACK")
        return False


def test_a_file_with_the_expected_header_is_accepted_whatever_its_case(tmp_path):
    path = write_export(tmp_path, "source_coverage", [a_row("source_coverage", 1)])
    check_header(path, BY_NAME["source_coverage"])                        # raises nothing


def test_a_file_with_a_missing_or_reordered_column_is_refused(tmp_path):
    columns = [name.upper() for name, _ in BY_NAME["company_flags"].columns]
    missing = write_export(tmp_path, "company_flags", [], header=columns[:-1], file_name="missing.csv.gz")
    swapped = write_export(tmp_path, "company_flags", [], header=[columns[1], columns[0]] + columns[2:], file_name="swapped.csv.gz")
    for path in (missing, swapped):
        with pytest.raises(ExportError, match="the header is"):
            check_header(path, BY_NAME["company_flags"])


def test_the_counts_file_must_be_there_once_and_cover_every_table(tmp_path):
    with pytest.raises(ExportError, match="exactly one export_counts file"):
        read_expected_counts(tmp_path)                                    # no download at all
    write_counts(tmp_path, {"company_search": 3})
    with pytest.raises(ExportError, match="no count for: company_flags, company_possible_matches, source_coverage"):
        read_expected_counts(tmp_path)
    write_export(tmp_path, "export_counts", [], header=["TABLE_NAME", "ROW_COUNT"], file_name="second.csv.gz")
    with pytest.raises(ExportError, match="found 2"):
        read_expected_counts(tmp_path)                                    # two exports mixed in one folder


def test_only_exported_files_are_picked_up_and_in_name_order(tmp_path):
    for name in ("company_flags_0_2_0.csv.gz", "company_flags_0_0_0.csv.gz", "notes.txt"):
        write_export(tmp_path, "company_flags", [], file_name=name)
    assert [p.name for p in export_files("company_flags", tmp_path)] == ["company_flags_0_0_0.csv.gz", "company_flags_0_2_0.csv.gz"]
    assert export_files("company_possible_matches", tmp_path) == []       # no folder: the table exported no rows


def test_every_table_is_loaded_and_counted_before_anything_is_swapped(tmp_path):
    a_full_export(tmp_path)
    conn = FakeConnection()
    result = load(conn, tmp_path)
    assert result["loaded"] == {"company_search": 3, "company_flags": 2, "company_possible_matches": 0, "source_coverage": 5}
    begin, commit = conn.log.index("BEGIN"), conn.log.index("COMMIT")
    before, inside, after = conn.log[:begin], conn.log[begin + 1:commit], conn.log[commit + 1:]
    assert after == []                                                    # the swap is the last thing that happens
    for table in TABLES:                                                  # before the transaction: only the temporary tables are touched
        assert f"select count(*) from {table.name}_new" in before
        assert all(statement in inside for statement in swap_statements(table))
    assert not [s for s in before if " rename " in s or s.startswith("drop table if exists") and not s.endswith("_new")]
    assert [s for s in inside if s.startswith("create index")] == []      # the slow index build is finished before the swap starts
    assert any(s.startswith("create index company_search_new_name_key_trgm") for s in before)


def test_a_wrong_count_stops_the_run_before_the_swap(tmp_path):
    a_full_export(tmp_path, counts={"company_search": 3, "company_flags": 9, "company_possible_matches": 0, "source_coverage": 5})
    conn = FakeConnection()
    with pytest.raises(ExportError, match="company_flags: loaded 2, Snowflake exported 9"):
        load(conn, tmp_path)
    assert "BEGIN" not in conn.log                                        # no transaction was opened
    assert not [s for s in conn.log if " rename " in s]                   # and no table was given a live name
    assert conn.log[-4:] == [f"drop table if exists {table.name}_new" for table in TABLES]   # the half-loaded copies are removed


def test_rows_exported_with_no_file_on_disk_stop_the_run_before_anything_is_created(tmp_path):
    a_full_export(tmp_path, counts={"company_search": 3, "company_flags": 2, "company_possible_matches": 7, "source_coverage": 5})
    conn = FakeConnection()
    with pytest.raises(ExportError, match="company_possible_matches: Snowflake exported 7 rows and no file is on disk"):
        load(conn, tmp_path)
    assert conn.log == []                                                 # the files were inspected before the database was touched


def test_a_bad_header_stops_the_run_before_anything_is_created(tmp_path):
    a_full_export(tmp_path)
    write_export(tmp_path, "company_flags", [], header=["DOCUMENT_NUMBER"], file_name="company_flags_0_1_0.csv.gz")
    conn = FakeConnection()
    with pytest.raises(ExportError, match="company_flags_0_1_0.csv.gz: the header is"):
        load(conn, tmp_path)
    assert conn.log == []


def test_postgres_itself_refuses_a_hidden_flag_or_possible_match():
    # Working rule W9: hidden records never leave Snowflake. The export filters them out, and these two tables check again.
    for name in ("company_flags", "company_possible_matches"):
        assert f"constraint {name}_new_check check (is_shown)" in create_statement(BY_NAME[name])
    assert "check (" not in create_statement(BY_NAME["source_coverage"])  # a source row is not a record: its FALSE rows are the "not checked" list
    assert "constraint company_search_new_pkey primary key (document_number)" in create_statement(BY_NAME["company_search"])


def test_every_fact_column_is_required():
    # CLAUDE.md rule 3: a table that could hold a fact with no source address or no fetch time is a bug in the table.
    for table in TABLES:
        definitions = dict(table.columns)
        assert definitions["source_url"] == "text not null"
        assert definitions["fetched_at"] == "timestamptz not null"
        assert definitions["fetched_at_is_approximate"] == "boolean not null"
