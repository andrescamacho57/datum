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

Run from ~/datum with the project's virtual environment active:
    python src/datum/duval.py probe       # connect, list the folder, print counts only
    python src/datum/duval.py download    # fetch what's missing, then verify everything
    python src/datum/duval.py verify      # verify the files on disk (no network)

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
    """Command line: probe | download | verify."""
    command = argv[1] if len(argv) > 1 else ""                     # the word after the script name
    if command not in ("probe", "download", "verify"):
        print("usage: python src/datum/duval.py probe|download|verify")
        return 2                                                   # 2 = "you called me wrong", by Unix convention
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
