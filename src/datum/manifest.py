"""manifest.py: the fetch manifest, one row for every file Datum downloads (ruling R23).

Why it exists: CLAUDE.md rule 3 says every fact carries a source URL and a UTC fetch
timestamp. The raw tables know when Snowflake LOADED a file (loaded_at), which is not when
we FETCHED it from the source. The manifest records the fetch itself: which file, from
which exact address, at what moment, how big it was and its checksum.

How it is used:
    1. Each downloader (dbpr.py, duval.py, sunbiz_flr.py) calls record_fetch() right after
       a file lands on disk. One file = one row appended to data/raw/fetch_manifest.csv.
    2. Files that were downloaded before the manifest existed are backfilled from their
       modification time, marked is_approximate = true. That includes the state's corporate
       files, which were pulled by hand and have no downloader (sunbiz_cor.py):
           python src/datum/manifest.py backfill
    3. snowflake/18_fetch_manifest.sql loads the CSV into datum.raw.fetch_manifest, and the
       staging view stg_datum__fetch_manifest gives every raw source_file its fetch time.

The manifest is append-only: a file fetched twice gets two rows, and nothing is ever
rewritten. No secrets are involved: a source URL names a server and a path, never a login.
"""

import csv                                  # reads and writes the comma-delimited manifest file
import hashlib                              # SHA-256 checksums
import sys                                  # command-line arguments and the exit code
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from datetime import datetime, timezone     # timestamps, and the UTC time zone
from pathlib import Path                    # file paths that work on any operating system

# --- Settings -------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/manifest.py → go up 2 folders to the repo root
MANIFEST_PATH = REPO_ROOT / "data" / "raw" / "fetch_manifest.csv"   # one manifest for every source; data/ is gitignored
COLUMNS = ("source", "file_name", "source_url", "fetched_at_utc", "size_bytes", "sha256", "is_approximate")   # the CSV header, in order
SOURCES = ("dbpr", "duval", "sunbiz_flr", "sunbiz_cor")    # the only values allowed in the source column. sunbiz_cor (the company register) joined in leg C1
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"                         # ISO 8601 in UTC, e.g. 2026-11-18T07:15:02Z (Z = "zero offset" = UTC)


@dataclass(frozen=True)                     # frozen = fields can't change after creation: a fetch is a fact
class FetchRecord:
    """One fetched file. It cannot be built without a source URL and a UTC fetch time (CLAUDE.md rule 3)."""

    source: str                             # which source the file belongs to: one of SOURCES
    file_name: str                          # the file's name on disk, e.g. d2026110501id.16
    source_url: str                         # the exact address the file came from
    fetched_at_utc: datetime                # when the download finished, in UTC
    size_bytes: int                         # the file's size as fetched
    sha256: str                             # checksum of the bytes as fetched: proves later that the file hasn't changed
    is_approximate: bool = False            # True when fetched_at_utc is the file's modification time, not a measured fetch time

    def __post_init__(self) -> None:        # runs right after __init__: refuse a record that breaks rule 3
        if self.source not in SOURCES:                             # a typo here would split one source into two
            raise ValueError(f"unknown source {self.source!r}; expected one of {SOURCES}")
        if not self.file_name:                                     # a row that names no file is useless
            raise ValueError("a fetch record needs a file name")
        if "://" not in self.source_url:                           # must be a full address: scheme://host/path
            raise ValueError(f"{self.file_name}: source_url must be a full address, got {self.source_url!r}")
        offset = self.fetched_at_utc.utcoffset()                   # None when the datetime carries no time zone
        if offset is None or offset.total_seconds() != 0:          # a time without a zone is ambiguous; a non-UTC one breaks the column's promise
            raise ValueError(f"{self.file_name}: fetched_at_utc must be a time-zone-aware UTC datetime")

    def as_row(self) -> list[str]:
        """The record as the text cells of one CSV row, in COLUMNS order."""
        return [
            self.source, self.file_name, self.source_url,
            self.fetched_at_utc.strftime(TIME_FORMAT),             # datetime → 2026-11-18T07:15:02Z
            str(self.size_bytes), self.sha256,
            "true" if self.is_approximate else "false",            # lower case, the way Snowflake reads a BOOLEAN from text
        ]


def sha256_of(path: Path) -> str:
    """The SHA-256 checksum of a file, as 64 hexadecimal characters."""
    digest = hashlib.sha256()                                      # an empty running checksum
    with path.open("rb") as handle:                                # rb = read bytes, not text
        for block in iter(lambda: handle.read(1024 * 1024), b""):  # 1 MB at a time, until read() returns nothing
            digest.update(block)                                   # fold this block into the checksum
    return digest.hexdigest()


def read_manifest(manifest_path: Path = MANIFEST_PATH) -> list[FetchRecord]:
    """Every row of the manifest, oldest first. An absent manifest is an empty one."""
    if not manifest_path.exists():                                 # nothing fetched yet
        return []
    with manifest_path.open(newline="", encoding="utf-8") as handle:   # newline="" lets the csv module handle line endings
        return [
            FetchRecord(
                source=row["source"], file_name=row["file_name"], source_url=row["source_url"],
                fetched_at_utc=datetime.strptime(row["fetched_at_utc"], TIME_FORMAT).replace(tzinfo=timezone.utc),   # text → UTC datetime
                size_bytes=int(row["size_bytes"]), sha256=row["sha256"],
                is_approximate=row["is_approximate"] == "true",
            )
            for row in csv.DictReader(handle)                      # DictReader gives each row as {column name: value}
        ]


def append_record(record: FetchRecord, manifest_path: Path = MANIFEST_PATH) -> None:
    """Add one row to the end of the manifest, writing the header first if the file is new."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)        # create data/raw/ if needed
    is_new = not manifest_path.exists()                            # decide before opening: opening creates the file
    with manifest_path.open("a", newline="", encoding="utf-8") as handle:   # "a" = append: earlier rows are never rewritten
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(COLUMNS)                               # the header row, once
        writer.writerow(record.as_row())


def record_fetch(
    source: str, path: Path, source_url: str,
    fetched_at_utc: datetime | None = None, is_approximate: bool = False, manifest_path: Path = MANIFEST_PATH,
) -> FetchRecord:
    """Describe a file that was just fetched and append it to the manifest. Returns the record.

    Call it right after the download: with no fetched_at_utc given, the fetch time is "now".
    """
    record = FetchRecord(
        source=source, file_name=path.name, source_url=source_url,
        fetched_at_utc=fetched_at_utc or datetime.now(timezone.utc),   # now, in UTC, unless the caller measured it
        size_bytes=path.stat().st_size, sha256=sha256_of(path), is_approximate=is_approximate,
    )
    append_record(record, manifest_path)
    return record


def backfill(
    source: str, files: list[tuple[Path, str, Path | None]], manifest_path: Path = MANIFEST_PATH,
) -> int:
    """Add approximate rows for files fetched before the manifest existed. Returns how many rows were added.

    files is a list of (path on disk, source URL, time_from). The fetch time is taken from a
    modification time: the file's own, or time_from's when it isn't None (a file unpacked
    from a zip keeps the time the SOURCE wrote it, so the zip's own modification time is the
    better stand-in for when we downloaded it). A file that already has a row is skipped, so
    running the backfill twice adds nothing the second time.
    """
    recorded = {r.file_name for r in read_manifest(manifest_path) if r.source == source}   # read the manifest once, not once per file
    added = 0
    for path, source_url, time_from in files:
        if path.name in recorded:                                  # already has a row, measured or approximate
            continue
        modified = (time_from or path).stat().st_mtime             # seconds since 1970-01-01 UTC, so no local time zone is involved
        record_fetch(
            source, path, source_url,
            fetched_at_utc=datetime.fromtimestamp(modified, tz=timezone.utc).replace(microsecond=0),   # whole seconds: it's approximate anyway
            is_approximate=True, manifest_path=manifest_path,
        )
        recorded.add(path.name)                                    # so a name listed twice is still added once
        added += 1
    return added


def main(argv: list[str]) -> int:
    """Command line: `backfill` adds approximate rows for files already on disk, for every source."""
    if len(argv) != 2 or argv[1] != "backfill":
        print("usage: python src/datum/manifest.py backfill")
        return 2                                                   # 2 = "you called me wrong", by Unix convention
    import dbpr                                                    # imported here, not at the top: the downloaders import this module,
    import duval                                                   # so importing them at the top would be a circle
    import sunbiz_cor                                              # the company register: it has no downloader, only files pulled by hand
    import sunbiz_flr
    for module in (dbpr, duval, sunbiz_flr, sunbiz_cor):           # each module knows its own files and addresses
        added = module.backfill_manifest()                         # returns how many rows it added
        print(f"{module.SOURCE}: added {added} approximate row(s)")
    print(f"manifest now has {len(read_manifest())} row(s): {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":                  # true only when this file is run directly
    sys.exit(main(sys.argv))                # run main and pass its result to the shell
