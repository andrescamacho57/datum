"""sunbiz_cor.py: fetch-manifest rows for the state's CORPORATE files (Phase C, leg C1).

The corporate files are the company register itself: one quarterly snapshot, cordata.zip,
which unpacks into ten files (cordata0.txt to cordata9.txt), and small daily files named
for their date (20261009c.txt). They were pulled by hand in October 2026, before the fetch
manifest existed, and so no company's status, date or address had a fetch time. CLAUDE.md
rule 3 says every fact carries a source URL and a UTC fetch timestamp, and that includes
the company's own record.

What this module does: it adds one manifest row for each corporate file that is still on
disk, with the fetch time taken from a modification time and marked is_approximate = true,
exactly as ruling R23 did for the other sources. It downloads nothing.

Where each time comes from:
    a daily file      its own modification time, which is when it was downloaded
    a snapshot file   the modification time of cordata.zip. The ten files inside the zip
                      carry the time the STATE wrote them (2026-10-07), which is not when
                      we fetched them. The zip's own time is.

The ten snapshot files do not have to be unpacked. Snowflake loaded them and the unpacked
copies were deleted, but the zip that was fetched is still on disk, and a zip can be read
one member at a time (with the `unzip` program, which macOS and Linux both ship). The size and checksum of each row are those of the unpacked member,
because that is the file the raw table names in its source_file column.

If a file is not on disk, it gets no row. Nothing here estimates a time from anything else.

Run from ~/datum with the project's virtual environment active:
    python src/datum/manifest.py backfill
"""

import hashlib                              # SHA-256 checksums
import re                                   # regular expressions, to recognise a file name
import subprocess                           # runs the `unzip` program and reads what it writes
import zipfile                              # reads a zip's table of contents: member names and sizes
from datetime import datetime, timezone     # timestamps, and the UTC time zone
from pathlib import Path                    # file paths that work on any operating system

try:                                        # imported as datum.sunbiz_cor (pytest puts src/ on the import path)
    from datum.manifest import MANIFEST_PATH, FetchRecord, append_record, backfill, read_manifest
except ModuleNotFoundError:                 # run through manifest.py as a script: the sibling module is plain `manifest`
    from manifest import MANIFEST_PATH, FetchRecord, append_record, backfill, read_manifest

# --- Settings -------------------------------------------------------------------------
SOURCE = "sunbiz_cor"                                      # this source's name in the fetch manifest
REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/sunbiz_cor.py → go up 2 folders to the repo root
RAW_DIR = REPO_ROOT / "data" / "raw" / "sunbiz"            # the daily files sit here; data/ is gitignored
QUARTERLY_ZIP = Path("quarterly") / "cordata.zip"          # the snapshot, relative to RAW_DIR
HOST = "sftp.floridados.gov"                               # the Division of Corporations' public file server
DAILY_DIR = "doc/cor"                                      # the folder of daily corporate files on that server (docs/access/sunbiz.md)
QUARTERLY_DIR = "doc/quarterly/cor"                        # the folder that holds cordata.zip (docs/access/sunbiz.md)
DAILY_NAME = re.compile(r"\d{8}c\.txt")                    # 20261009c.txt: eight digits, the letter c, .txt
SNAPSHOT_MEMBER = re.compile(r"cordata\d\.txt")            # cordata0.txt to cordata9.txt
BLOCK_BYTES = 1024 * 1024                                  # read 1 MB at a time: a member is 1.9 GB, too big to hold in memory


def daily_files(raw_dir: Path = RAW_DIR) -> list[Path]:
    """The daily corporate files on disk, oldest first. Other files in the folder are ignored."""
    if not raw_dir.is_dir():                                       # nothing was ever downloaded here
        return []
    return sorted(path for path in raw_dir.iterdir() if path.is_file() and DAILY_NAME.fullmatch(path.name))


def daily_url(file_name: str) -> str:
    """The exact address a daily corporate file comes from."""
    return f"sftp://{HOST}/{DAILY_DIR}/{file_name}"


def snapshot_url() -> str:
    """The exact address the quarterly snapshot comes from. All ten files arrive inside this one zip."""
    return f"sftp://{HOST}/{QUARTERLY_DIR}/{QUARTERLY_ZIP.name}"


def snapshot_records(archive: Path) -> list[FetchRecord]:
    """One approximate fetch record for each snapshot file inside the zip, in name order.

    The fetch time of every record is the zip's own modification time. The size and the
    checksum are worked out by reading the member straight from the zip, block by block.

    The reading is done by the `unzip` program, not by Python's zipfile module. The state
    packs cordata.zip with a method called Deflate64, which zipfile can list and cannot
    unpack. `unzip -p` writes one member's unpacked bytes to its output, which this
    function reads as a stream, so nothing is written to disk.
    """
    fetched_at = datetime.fromtimestamp(archive.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)   # seconds since 1970 are already UTC
    with zipfile.ZipFile(archive) as bundle:                       # zipfile CAN read the table of contents: names and unpacked sizes
        expected_sizes = {info.filename: info.file_size for info in bundle.infolist() if SNAPSHOT_MEMBER.fullmatch(info.filename)}
    records = []
    for member in sorted(expected_sizes):
        digest = hashlib.sha256()                                  # an empty running checksum
        size = 0                                                   # bytes read so far
        # The command is a list, so no shell reads it, and the member name has already matched SNAPSHOT_MEMBER.
        with subprocess.Popen(["unzip", "-p", str(archive), member], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as unpacking:
            for block in iter(lambda: unpacking.stdout.read(BLOCK_BYTES), b""):   # until read() returns nothing
                digest.update(block)
                size += len(block)
        if unpacking.returncode != 0 or size != expected_sizes[member]:   # unzip failed, or stopped short of the size the zip promises
            raise ValueError(
                f"{archive.name}: could not read {member} whole "
                f"(unzip exit code {unpacking.returncode}, {size} of {expected_sizes[member]} bytes)"
            )
        records.append(FetchRecord(
            source=SOURCE, file_name=member, source_url=snapshot_url(),
            fetched_at_utc=fetched_at, size_bytes=size, sha256=digest.hexdigest(),
            is_approximate=True,                                   # a modification time, not a measured fetch
        ))
    return records


def backfill_manifest(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> int:
    """Add approximate fetch-manifest rows for the corporate files on disk. Returns how many rows were added.

    A file that already has a row is skipped, so running this twice adds nothing the second time.
    """
    added = backfill(SOURCE, [(path, daily_url(path.name), None) for path in daily_files(raw_dir)], manifest_path)
    archive = raw_dir / QUARTERLY_ZIP
    if not archive.exists():                                       # no snapshot on disk: no row, and no guess (see the module header)
        return added
    recorded = {r.file_name for r in read_manifest(manifest_path) if r.source == SOURCE}
    with zipfile.ZipFile(archive) as bundle:                       # look at the names first: reading 18 GB to add nothing would be a waste
        wanted = {info.filename for info in bundle.infolist() if SNAPSHOT_MEMBER.fullmatch(info.filename)}
    if wanted <= recorded:                                         # <= on sets means "is a subset of": every member already has a row
        return added
    for record in snapshot_records(archive):
        if record.file_name not in recorded:
            append_record(record, manifest_path)
            added += 1
    return added
