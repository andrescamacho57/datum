"""duval.py: download and verify the Duval County Clerk's daily recording index files.

The Clerk publishes, for every day since 2019-07-31, a set of pipe-delimited text files
describing the documents recorded that day (deeds, liens, judgments, releases...).
File kinds, layouts and counts: docs/access/duval-recording-index.md.

What this module does, in order:
    1. download: ONE connection to the Clerk's secure FTP server, files fetched one after
       another with a short pause, saved under data/raw/duval/ (gitignored). Only files
       dated 2025-01-01 or later. A file already on disk at the same size is skipped.
    2. verify: every file ends with a trailer line `EOF|<row count>`. Count the rows above
       the trailer and compare. A mismatch fails that file loudly, and the file is moved to
       data/raw/duval/rejected/ so that an upload of data/raw/duval/*.16 can't include it.
    3. repair (ruling R15): a rejected file is usually broken by a line break inside a legal
       description, which spreads one record over two or three lines. The repair writes a
       mended COPY to data/raw/duval/repaired/ under the same file name: a line that does not
       start a record is joined to the line above with one space, and blank lines are dropped.
       The copy is kept only if its row count now equals the EOF trailer. The file as the
       Clerk sent it stays in rejected/, untouched.

Run from ~/datum with the project's virtual environment active:
    python src/datum/duval.py probe       # connect, list the folder, print counts only
    python src/datum/duval.py download    # fetch what's missing, then verify everything
    python src/datum/duval.py verify      # verify the files on disk (no network)
    python src/datum/duval.py repair      # mend the files in rejected/ into repaired/ (no network)

Needs DUVAL_FTP_USER and DUVAL_FTP_PASSWORD in .env. They are read into memory and
never printed, logged or written anywhere.

Needs paramiko 3.x (`pip install "paramiko>=3.5,<4"`). The Clerk's server identifies itself
with an old kind of key (ssh-dss) that paramiko 4 and later no longer accept.
"""

import os                                   # reads environment variables (where load_dotenv puts the secrets)
import re                                   # regular expressions, to take a file name apart
import sys                                  # command-line arguments and the exit code
import time                                 # the short pause between downloads
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from datetime import date, datetime         # calendar dates, to compare a file's date with the start date
from pathlib import Path                    # file paths that work on any operating system

import paramiko                             # SFTP (file transfer over SSH) client library
from dotenv import load_dotenv              # reads NAME=value lines from .env into the environment

load_dotenv()                               # look for .env from this file's folder upward (finds ~/datum/.env) and load it

# --- Settings -------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/duval.py → go up 2 folders to the repo root
RAW_DIR = REPO_ROOT / "data" / "raw" / "duval"             # where downloads land; data/ is gitignored
REJECTED = "rejected"                                      # sub-folder of RAW_DIR for files that failed verification
REPAIRED = "repaired"                                      # sub-folder of RAW_DIR for mended copies of rejected files (ruling R15)
KNOWN_HOSTS = REPO_ROOT / "data" / "duval_known_hosts"     # the server's identity key, saved on first contact (see connect)
HOST = "ftp.duvalclerk.com"                                # the Clerk's file server
PORT = 22                                                  # the standard SFTP port
REMOTE_DIR = "/Recording Indexes"                          # the folder holding the daily files (the server needs the leading slash)
START_DATE = date(2025, 1, 1)                              # scope: files dated on or after this day
PAUSE_SECONDS = 0.5                                        # wait between files: sequential and unhurried
TIMEOUT_SECONDS = 60                                       # give up on a stalled connection instead of hanging

# File names look like d2026110501id.16: a kind letter, the date as YYYYMMDD, "01", "id" or "d", ".16".
FILE_NAME = re.compile(r"^([dplm])(\d{8})01(?:id|d)\.16$")  # group 1 = kind letter, group 2 = the date digits
KINDS = {"d": "documents", "p": "parties", "l": "links", "m": "doc_types"}   # kind letter → what the file holds
# Every data line of a documents or parties file starts with a fixed marker. A line without it is
# the tail of the record above, cut off by a line break inside a text field. Links and doc-type
# files have no marker, so in those only blank lines can be repaired.
RECORD_PREFIX = {"documents": b"DDA|", "parties": b"DPA|"}  # kind → the bytes that start every record


class DuvalVerificationError(Exception):
    """Raised when a file's row count disagrees with its EOF trailer. The file must not be loaded."""


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class DuvalFile:
    """One daily index file, described by its name alone."""

    name: str                               # e.g. d2026110501id.16
    kind: str                               # documents, parties, links or doc_types
    file_date: date                         # the date in the name: the day the Clerk produced the file, NOT the recording date

    @classmethod                            # a method called on the class itself: DuvalFile.from_name("...")
    def from_name(cls, name: str) -> "DuvalFile | None":
        """Build a DuvalFile from a file name, or return None when the name isn't one of the four kinds."""
        match = FILE_NAME.match(name)                              # try the pattern on the whole name
        if match is None:                                          # some other file in the folder
            return None
        try:
            file_date = datetime.strptime(match.group(2), "%Y%m%d").date()   # "20261105" → date(2026, 11, 5)
        except ValueError:                                         # eight digits that aren't a real date
            return None
        return cls(name=name, kind=KINDS[match.group(1)], file_date=file_date)


@dataclass(frozen=True)
class VerifyReport:
    """What verify_file() found in a file that passed."""

    name: str                               # which file was checked
    rows: int                               # data rows counted above the trailer
    eof_count: int                          # the number the Clerk wrote in the trailer (equal to rows, or we raised)


def verify_file(path: Path) -> VerifyReport:
    """Count a file's data rows and compare with its `EOF|<count>` trailer. Raises on any mismatch."""
    lines = path.read_bytes().split(b"\r\n")                       # the files use CRLF line endings; split on them
    if lines and lines[-1] == b"":                                 # the file ends with CRLF, so the last piece is empty
        lines.pop()                                                # drop it
    if not lines or not lines[-1].startswith(b"EOF|"):             # no trailer: the download was cut off, or this isn't an index file
        raise DuvalVerificationError(f"{path.name}: no EOF trailer on the last line")
    try:
        eof_count = int(lines[-1][4:])                             # the digits after "EOF|"
    except ValueError:                                             # "EOF|" followed by something that isn't a number
        raise DuvalVerificationError(f"{path.name}: EOF trailer has no row count") from None
    rows = len(lines) - 1                                          # every line above the trailer is one data row
    if rows != eof_count:                                          # the Clerk says N rows, we see a different number
        raise DuvalVerificationError(f"{path.name}: {rows} rows in the file, but the trailer says EOF|{eof_count}")
    return VerifyReport(path.name, rows, eof_count)


@dataclass(frozen=True)
class RepairReport:
    """What repair_file() did to a file whose mended copy passed verification."""

    name: str                               # which file was repaired
    rows: int                               # data rows in the repaired copy (equal to the EOF trailer, or we raised)
    lines_joined: int                       # continuation lines glued back onto the record above
    blank_lines_dropped: int                # empty lines removed


def repair_lines(lines: list[bytes], prefix: bytes | None) -> tuple[list[bytes], int, int]:
    """Mend the data lines of one file. Returns (mended lines, lines joined, blank lines dropped).

    prefix is the marker every record starts with (b"DDA|"), or None when the kind has no marker.
    """
    mended: list[bytes] = []                                       # the records, rebuilt
    joined = dropped = 0                                           # two counters for the report
    for line in lines:
        if line.strip() == b"":                                    # an empty line holds no data: drop it
            dropped += 1
            continue
        starts_record = prefix is None or line.startswith(prefix)  # without a marker, every non-blank line is a record
        if starts_record or not mended:                            # the first line has nothing above it to join to (it may also carry a byte-order mark)
            mended.append(line)
        else:                                                      # the tail of the record above
            mended[-1] = mended[-1] + b" " + line                  # one space where the line break was (ruling R15)
            joined += 1
    return mended, joined, dropped


def repair_file(path: Path, repaired_dir: Path) -> RepairReport:
    """Write a mended copy of one rejected file into repaired_dir. Raises if the copy still fails its EOF check.

    The original is only read, never changed. A copy that fails is deleted, so repaired/ only
    ever holds files that are safe to load.
    """
    duval_file = DuvalFile.from_name(path.name)                    # the name tells us the kind
    if duval_file is None:                                         # not one of the four index files
        raise DuvalVerificationError(f"{path.name}: not a Duval index file name")
    lines = path.read_bytes().split(b"\r\n")                       # same split as verify_file: CRLF line endings
    if lines and lines[-1] == b"":                                 # the empty piece after the final CRLF
        lines.pop()
    if not lines or not lines[-1].startswith(b"EOF|"):             # no trailer means a cut-off download: nothing to repair against
        raise DuvalVerificationError(f"{path.name}: no EOF trailer on the last line, cannot repair")
    trailer = lines[-1]                                            # keep the Clerk's count exactly as sent
    mended, joined, dropped = repair_lines(lines[:-1], RECORD_PREFIX.get(duval_file.kind))   # mend everything above the trailer
    repaired_dir.mkdir(parents=True, exist_ok=True)                # create repaired/ on first use
    target = repaired_dir / path.name                              # same file name, so staging still reads the date from it
    partial = target.with_name(target.name + ".part")              # write under a temporary name first
    partial.write_bytes(b"\r\n".join([*mended, trailer]) + b"\r\n")   # same shape as the Clerk's files: CRLF after every line
    try:
        report = verify_file(partial)                              # the mended rows must now equal the trailer
    except DuvalVerificationError as error:
        partial.unlink()                                           # a copy that still fails must not sit where the upload looks
        raise DuvalVerificationError(str(error).replace(partial.name, path.name) + " (after repair)") from None
    partial.replace(target)                                        # only a verified copy gets the real name
    return RepairReport(path.name, report.rows, joined, dropped)


def repair_all(raw_dir: Path = RAW_DIR) -> int:
    """Repair every file in raw_dir/rejected/ into raw_dir/repaired/. Prints one line per file. Returns the failure count."""
    failures = 0
    for path in sorted((raw_dir / REJECTED).glob("*.16")):         # every quarantined file, by name
        try:
            report = repair_file(path, raw_dir / REPAIRED)         # raises if the copy still disagrees with its trailer
        except DuvalVerificationError as error:
            failures += 1
            print(f"FAIL  {error}")                                # loud: this file stays out of the load
            continue
        print(f"OK    {report.name}: {report.rows} rows = EOF count; "
              f"joined {report.lines_joined} line(s), dropped {report.blank_lines_dropped} blank line(s)")
    print(f"{failures} file(s) could not be repaired and stay out")
    return failures


def local_files(raw_dir: Path = RAW_DIR) -> list[tuple[Path, DuvalFile]]:
    """Every index file on disk that is in scope, oldest first."""
    found = []                                                     # (path, description) pairs
    for path in sorted(raw_dir.glob("*.16")):                      # sorted by name
        duval_file = DuvalFile.from_name(path.name)                # None for names that don't fit
        if duval_file is not None and duval_file.file_date >= START_DATE:
            found.append((path, duval_file))
    return sorted(found, key=lambda pair: (pair[1].file_date, pair[1].name))   # by date, then name


def connect() -> paramiko.SSHClient:
    """Open ONE SSH connection to the Clerk's server. The caller closes it."""
    user = os.environ["DUVAL_FTP_USER"]                            # KeyError here means .env has no such line
    password = os.environ["DUVAL_FTP_PASSWORD"]                    # held in memory only
    client = paramiko.SSHClient()                                  # an SSH session object, not yet connected
    if KNOWN_HOSTS.exists() and KNOWN_HOSTS.stat().st_size > 0:    # we have met this server before (the file holds its key)
        client.load_host_keys(str(KNOWN_HOSTS))                    # load the identity key we saved then
        client.set_missing_host_key_policy(paramiko.RejectPolicy())    # a different key now = refuse to connect
    else:                                                          # first contact: trust the key once and remember it
        KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)      # make sure data/ exists
        KNOWN_HOSTS.touch()                                        # an empty file for paramiko to save into
        client.load_host_keys(str(KNOWN_HOSTS))                    # tells paramiko WHERE to save the new key
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())   # accept and save the key on this first connection
    client.connect(
        HOST, port=PORT, username=user, password=password,         # who we are
        timeout=TIMEOUT_SECONDS, banner_timeout=TIMEOUT_SECONDS, auth_timeout=TIMEOUT_SECONDS,   # never hang
        look_for_keys=False, allow_agent=False,                    # use the password only; don't offer this machine's SSH keys
    )
    return client


def list_remote(sftp: paramiko.SFTPClient) -> list[tuple[DuvalFile, int]]:
    """List the remote folder once and keep the in-scope index files, with their sizes in bytes."""
    in_scope = []                                                  # (description, size) pairs
    for entry in sftp.listdir_attr(REMOTE_DIR):                    # one request returns every name and size
        duval_file = DuvalFile.from_name(entry.filename)           # None for anything that isn't an index file
        if duval_file is not None and duval_file.file_date >= START_DATE:
            in_scope.append((duval_file, entry.st_size or 0))
    return sorted(in_scope, key=lambda pair: (pair[0].file_date, pair[0].name))   # oldest first


def download_missing(sftp: paramiko.SFTPClient, raw_dir: Path = RAW_DIR) -> tuple[int, int]:
    """Fetch every in-scope file not already on disk at the same size. Returns (downloaded, skipped)."""
    raw_dir.mkdir(parents=True, exist_ok=True)                     # create data/raw/duval/ if needed
    downloaded = skipped = 0                                       # two counters
    for duval_file, size in list_remote(sftp):                     # oldest first
        target = raw_dir / duval_file.name                         # where the file goes
        rejected = raw_dir / REJECTED / duval_file.name            # where the file sits if it failed verification before
        if any(copy.exists() and copy.stat().st_size == size for copy in (target, rejected)):   # already have it, same size: don't ask again
            skipped += 1
            continue
        partial = target.with_name(target.name + ".part")          # download under a temporary name
        sftp.get(f"{REMOTE_DIR}/{duval_file.name}", str(partial))  # one file, over the one open connection
        partial.replace(target)                                    # rename only when the whole file arrived
        downloaded += 1
        time.sleep(PAUSE_SECONDS)                                  # a short pause before the next file
    return downloaded, skipped


def verify_all(raw_dir: Path = RAW_DIR, quarantine: bool = False) -> int:
    """Verify every in-scope file on disk. Prints totals per kind and each failure. Returns the failure count.

    With quarantine=True a failing file is moved to raw_dir/rejected/, out of reach of the upload.
    """
    totals: dict[str, list[int]] = {kind: [0, 0] for kind in KINDS.values()}   # kind → [files, rows]
    failures = 0
    for path, duval_file in local_files(raw_dir):
        try:
            report = verify_file(path)                             # raises on a mismatch
        except DuvalVerificationError as error:
            failures += 1
            print(f"FAIL  {error}")                                # loud: one line per bad file
            if quarantine:                                         # keep it away from the files that will be loaded
                (raw_dir / REJECTED).mkdir(exist_ok=True)          # create rejected/ on first use
                path.replace(raw_dir / REJECTED / path.name)       # move, don't delete: the evidence stays on disk
            continue
        totals[duval_file.kind][0] += 1                            # one more good file of this kind
        totals[duval_file.kind][1] += report.rows                  # its rows
    for kind, (files, rows) in totals.items():
        print(f"OK    {kind}: {files} files, {rows} rows, every file matches its EOF count")
    already = len(list((raw_dir / REJECTED).glob("*.16"))) - (failures if quarantine else 0)   # rejected on an earlier run
    print(f"{failures} file(s) failed verification now; {max(already, 0)} more already in {REJECTED}/")
    return failures


def main(argv: list[str]) -> int:
    """Command line: probe | download | verify | repair."""
    command = argv[1] if len(argv) > 1 else ""                     # the word after the script name
    if command not in ("probe", "download", "verify", "repair"):
        print("usage: python src/datum/duval.py probe|download|verify|repair")
        return 2                                                   # 2 = "you called me wrong", by Unix convention
    if command == "repair":                                        # no network: mend what verification rejected
        return 1 if repair_all() else 0                            # non-zero exit code when any file could not be repaired
    if command in ("probe", "download"):                           # these two need the network
        client = connect()                                         # the ONE connection
        try:
            sftp = client.open_sftp()                              # start the file-transfer channel on it
            if command == "probe":                                 # look, don't fetch
                listing = list_remote(sftp)
                print(f"connected over SFTP; {len(listing)} in-scope files, {sum(size for _, size in listing)} bytes")
                if listing:
                    print(f"first {listing[0][0].name}, last {listing[-1][0].name}")
                return 0
            downloaded, skipped = download_missing(sftp)
            print(f"downloaded {downloaded} files, skipped {skipped} already on disk")
        finally:
            client.close()                                         # always hang up, even after an error
    return 1 if verify_all(quarantine=True) else 0                 # non-zero exit code when any file failed


if __name__ == "__main__":                  # true only when this file is run directly
    sys.exit(main(sys.argv))                # run main and pass its result to the shell
