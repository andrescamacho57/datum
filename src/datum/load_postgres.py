"""load_postgres.py: copy the exported marts into the Postgres database the web app reads (Phase C, leg C2).

Where this sits (decision d18: lookups read Postgres, builds run in Snowflake):

    Snowflake marts ── snowflake/23_export_marts.sql ──▶ data/export/*.csv.gz ── this module ──▶ Postgres

What it does, in order:
    1. inspect   read export_counts (how many rows Snowflake says it exported for each table)
                 and check line one of every file against the columns this module expects.
                 Nothing is loaded from a file whose header is wrong.
    2. load      create each table again under a temporary name (company_search_new ...) and
                 copy the files into it. The tables the app is reading are not touched.
    3. verify    count the rows of each new table. Every count must equal Snowflake's. One
                 mismatch stops the run here, before anything the app reads has changed.
    4. index     build the indexes on the new tables, including the trigram index the search uses.
    5. swap      in ONE transaction: drop each old table and give the new one its name. A
                 transaction is all-or-nothing, so the app sees the old tables until the
                 moment it sees all the new ones. A load that fails halfway never leaves the
                 app reading half a table.

Hidden records never get here (working rule W9): the export keeps only rows whose is_shown
is true, and the two flag tables below also carry CHECK (is_shown), so Postgres itself
refuses a hidden row.

The local database needs no password, so nothing about the connection is a secret. The
default is the database datum_dev on this machine. To point at another database, set the
environment variable DATUM_PG_DSN (a DSN, "data source name", is the text that says which
database to connect to, for example "dbname=datum_dev").

Run from ~/datum with the project's virtual environment active, after script 23 and the download:
    python src/datum/load_postgres.py
"""

import csv                                  # reads a CSV header line and the small counts file
import gzip                                 # the exported files are gzip-compressed
import os                                   # reads the optional DATUM_PG_DSN environment variable
import sys                                  # the exit code
import time                                 # times the index build
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from pathlib import Path                    # file paths that work on any operating system

# --- Settings -------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/load_postgres.py → go up 2 folders to the repo root
EXPORT_DIR = REPO_ROOT / "data" / "export"                 # where `snow stage copy` put the files; data/ is gitignored
DEFAULT_DSN = "dbname=datum_dev"                           # the local database: no host, no user, no password
COUNTS_TABLE = "export_counts"                             # the small file of row counts that travels with the export
NEW = "_new"                                               # the temporary ending a table carries until the swap
BLOCK_BYTES = 1024 * 1024                                  # send 1 MB of a file to Postgres at a time
INDEX_MEMORY = "1GB"                                       # memory Postgres may use while building an index, for this session only


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class Table:
    """One exported table: its columns, in file order, and what Postgres should enforce on it."""

    name: str                               # the table's name, the same in Snowflake's mart and in Postgres
    columns: tuple[tuple[str, str], ...]    # (column name, Postgres type and constraint), in the order the export writes them
    primary_key: str | None = None          # the column that is unique per row, when there is one
    indexes: tuple[tuple[str, str], ...] = ()   # (index name ending, what comes after ON <table>) for each extra index
    check: str | None = None                # a condition every row must meet, enforced by Postgres


FLAG_COLUMNS = (                            # the columns company_flags and company_possible_matches share
    ("document_number", "text not null"),
    ("flag_type", "text not null"),
    ("fact_date", "date"),
    ("status", "text not null"),
    ("status_note", "text"),
    ("source", "text not null"),
    ("source_record_id", "text not null"),
    ("source_url", "text not null"),        # CLAUDE.md rule 3: no fact without a source address ...
    ("citation", "text not null"),
    ("source_file", "text"),
    ("fetched_at", "timestamptz not null"),   # ... and none without a fetch time. timestamptz = a moment in time, stored in UTC
    ("caveat", "text not null"),
    ("is_shown", "boolean not null"),
    ("fetched_at_is_approximate", "boolean not null"),
)

TABLES = (
    Table(
        name="company_search",
        columns=(
            ("document_number", "text not null"),
            ("entity_name", "text not null"),
            ("name_key", "text not null"),
            ("status_code", "text"),
            ("filing_type", "text"),
            ("file_date", "date"),
            ("principal_address_1", "text"),
            ("principal_city", "text"),
            ("principal_state", "text"),
            ("principal_zip", "text"),
            ("published_on", "date not null"),
            ("source_url", "text not null"),
            ("fetched_at", "timestamptz not null"),
            ("fetched_at_is_approximate", "boolean not null"),
        ),
        primary_key="document_number",
        indexes=(("name_key_trgm", "using gin (name_key gin_trgm_ops)"),),
        # A GIN trigram index: for every three-letter piece of every name, the list of rows that
        # contain it. The search asks "which names share many pieces with this one?" and Postgres
        # answers from the index, not by reading 13 million names.
    ),
    Table(
        name="company_flags",
        columns=FLAG_COLUMNS,
        indexes=(("document_number", "(document_number)"),),   # a report asks for one company's flags
        check="is_shown",                   # rule W9: Postgres refuses a hidden flag, whatever the export sends
    ),
    Table(
        name="company_possible_matches",
        columns=FLAG_COLUMNS + (("link_reason", "text not null"),),
        indexes=(("document_number", "(document_number)"),),
        check="is_shown",                   # rule W9 again: every possible match is hidden today, so this table is empty
    ),
    Table(
        name="source_coverage",
        columns=(
            ("source", "text not null"),
            ("label", "text not null"),
            ("is_shown", "boolean not null"),   # TRUE = "checked" on a report. A source row is not a record, so FALSE rows belong here
            ("data_through", "date not null"),
            ("data_through_note", "text not null"),
            ("source_url", "text not null"),
            ("fetched_at", "timestamptz not null"),
            ("fetched_at_is_approximate", "boolean not null"),
            ("list_order", "integer not null"),
        ),
        primary_key="source",
    ),
)


class ExportError(ValueError):
    """The export on disk is not what this module expects. Nothing has been swapped in when it is raised."""


def export_files(table: str, export_dir: Path = EXPORT_DIR) -> list[Path]:
    """The exported files of one table, in name order. A table that exported no rows has no files."""
    folder = export_dir / table
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path.name.endswith(".csv.gz"))


def read_expected_counts(export_dir: Path = EXPORT_DIR) -> dict[str, int]:
    """How many rows Snowflake exported for each table, from the export_counts file."""
    files = export_files(COUNTS_TABLE, export_dir)
    if len(files) != 1:                                            # none = the download is missing; two = two exports mixed together
        raise ExportError(f"expected exactly one {COUNTS_TABLE} file under {export_dir}, found {len(files)}")
    with gzip.open(files[0], "rt", encoding="utf-8", newline="") as handle:   # rt = read as text
        counts = {row["TABLE_NAME"]: int(row["ROW_COUNT"]) for row in csv.DictReader(handle)}
    missing = [table.name for table in TABLES if table.name not in counts]
    if missing:                                                    # a table with no count can't be verified, so it can't be loaded
        raise ExportError(f"{files[0].name} has no count for: {', '.join(missing)}")
    return counts


def check_header(path: Path, table: Table) -> None:
    """Refuse a file whose first line is not exactly this table's columns, in order."""
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle), [])                      # the first line, split into its cells
    expected = [name for name, _ in table.columns]
    if [cell.lower() for cell in header] != expected:              # Snowflake writes column names in capitals
        raise ExportError(f"{path.name}: the header is {header}, expected {expected}")


def create_statement(table: Table) -> str:
    """CREATE TABLE for the temporary copy of a table, with its primary key and its CHECK."""
    lines = [f"{name} {definition}" for name, definition in table.columns]
    if table.primary_key:
        lines.append(f"constraint {table.name}{NEW}_pkey primary key ({table.primary_key})")
    if table.check:
        lines.append(f"constraint {table.name}{NEW}_check check ({table.check})")
    return f"create table {table.name}{NEW} (\n    " + ",\n    ".join(lines) + "\n)"


def index_statements(table: Table) -> list[str]:
    """CREATE INDEX for each extra index of a table, on its temporary copy."""
    return [f"create index {table.name}{NEW}_{ending} on {table.name}{NEW} {definition}" for ending, definition in table.indexes]


def swap_statements(table: Table) -> list[str]:
    """The statements that put a loaded copy in place of the live table. They run inside one transaction."""
    statements = [
        f"drop table if exists {table.name}",                      # the old table goes, and its indexes and constraints with it
        f"alter table {table.name}{NEW} rename to {table.name}",   # the new one takes its name
    ]
    if table.primary_key:
        statements.append(f"alter table {table.name} rename constraint {table.name}{NEW}_pkey to {table.name}_pkey")
    if table.check:
        statements.append(f"alter table {table.name} rename constraint {table.name}{NEW}_check to {table.name}_check")
    for ending, _ in table.indexes:
        statements.append(f"alter index {table.name}{NEW}_{ending} rename to {table.name}_{ending}")
    return statements


def copy_file(conn, path: Path, table: Table) -> None:
    """Send one exported file into the temporary copy of its table."""
    columns = ", ".join(name for name, _ in table.columns)
    statement = f"copy {table.name}{NEW} ({columns}) from stdin with (format csv, header true)"
    # format csv: quoted fields, a quote inside a field written twice, an empty unquoted field = NULL.
    # That is exactly how script 23 writes the files. header true: skip line one.
    with gzip.open(path, "rb") as handle, conn.cursor() as cursor, cursor.copy(statement) as copy:
        for block in iter(lambda: handle.read(BLOCK_BYTES), b""):  # until read() returns nothing
            copy.write(block)


def load(conn, export_dir: Path = EXPORT_DIR) -> dict:
    """Load every table from the export and swap them in. Returns the counts and timings.

    conn is an open psycopg connection in autocommit mode. Autocommit means each statement
    is saved as soon as it finishes, which is right for steps 2 to 4: they only touch the
    temporary tables. Step 5 opens an explicit transaction for the swap.
    """
    expected = read_expected_counts(export_dir)                    # step 1: inspect before loading
    files = {table.name: export_files(table.name, export_dir) for table in TABLES}
    for table in TABLES:
        if expected[table.name] > 0 and not files[table.name]:     # Snowflake exported rows and no file arrived
            raise ExportError(f"{table.name}: Snowflake exported {expected[table.name]} rows and no file is on disk")
        for path in files[table.name]:
            check_header(path, table)

    loaded = {}
    conn.execute("set time zone 'UTC'")                            # times are shown in UTC for this session; the files already say Z
    conn.execute(f"set maintenance_work_mem = '{INDEX_MEMORY}'")   # this session only: a faster index build
    for table in TABLES:                                           # step 2: load into temporary tables
        conn.execute(f"drop table if exists {table.name}{NEW}")    # left over from a run that stopped early
        conn.execute(create_statement(table))
        for path in files[table.name]:
            copy_file(conn, path, table)
        loaded[table.name] = conn.execute(f"select count(*) from {table.name}{NEW}").fetchone()[0]

    wrong = {name: (loaded[name], expected[name]) for name in loaded if loaded[name] != expected[name]}
    if wrong:                                                      # step 3: verify, and stop before the swap
        for table in TABLES:
            conn.execute(f"drop table if exists {table.name}{NEW}")    # leave nothing half-loaded behind
        details = "; ".join(f"{name}: loaded {got}, Snowflake exported {want}" for name, (got, want) in wrong.items())
        raise ExportError(f"row counts differ, nothing was swapped in. {details}")

    index_seconds = {}
    for table in TABLES:                                           # step 4: indexes, on the temporary tables
        for statement in index_statements(table):
            started = time.perf_counter()                          # a clock for measuring durations
            conn.execute(statement)
            index_seconds[statement.split()[2].replace(NEW, "")] = time.perf_counter() - started   # word 3 of the statement is the index name
        conn.execute(f"analyze {table.name}{NEW}")                 # refresh the statistics the query planner uses

    with conn.transaction():                                       # step 5: the swap, all or nothing
        for table in TABLES:
            for statement in swap_statements(table):
                conn.execute(statement)
    return {"expected": expected, "loaded": loaded, "index_seconds": index_seconds}


def sizes(conn) -> list[tuple[str, str, str]]:
    """(relation, kind, size) for every table and index this module made, biggest first."""
    names = [table.name for table in TABLES]
    rows = conn.execute(
        """
        select c.relname,
               case c.relkind when 'r' then 'table' else 'index' end,
               pg_size_pretty(pg_relation_size(c.oid)),
               pg_relation_size(c.oid)
        from pg_class c
        left join pg_index i on i.indexrelid = c.oid
        left join pg_class t on t.oid = i.indrelid
        where c.relkind in ('r', 'i')
          and coalesce(t.relname, c.relname) = any(%s)
        order by 4 desc
        """,
        (names,),
    ).fetchall()
    # pg_class is Postgres's own catalogue of tables and indexes. pg_relation_size is the bytes
    # one of them takes on disk, and pg_size_pretty writes that number as "1234 MB".
    return [(name, kind, pretty) for name, kind, pretty, _ in rows]


def main() -> int:
    """Command line: load the export and print the counts, the index build times and the sizes."""
    import psycopg                                                 # imported here so the tests, which never open a database, don't need the driver loaded
    with psycopg.connect(os.environ.get("DATUM_PG_DSN", DEFAULT_DSN), autocommit=True) as conn:
        try:
            result = load(conn)
        except ExportError as error:
            print(f"NOT LOADED: {error}")
            return 1
        print(f"{'table':<26}{'Snowflake exported':>20}{'Postgres loaded':>18}")
        for table in TABLES:
            print(f"{table.name:<26}{result['expected'][table.name]:>20,}{result['loaded'][table.name]:>18,}")
        for index, seconds in result["index_seconds"].items():
            print(f"index {index}: built in {seconds:.1f} seconds")
        for name, kind, pretty in sizes(conn):
            print(f"{kind:<6}{name:<44}{pretty:>10}")
        total = conn.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
        print(f"database total: {total}")
    return 0


if __name__ == "__main__":                  # true only when this file is run directly
    sys.exit(main())                        # run main and pass its result to the shell
