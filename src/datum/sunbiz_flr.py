"""sunbiz_flr.py: download and inspect the state's DAILY federal tax lien files (ruling R8).

The Florida Division of Corporations publishes federal tax liens as four fixed-width
files: filings (the liens), debtors (who owes), events (releases and other actions) and
secured parties (who is owed). A full snapshot comes out every quarter; small daily files
carry what changed since. Layouts: docs/access/sunbiz_flr.md.

Why the dailies matter: a lien in the 2026-10-03 snapshot may have been released since.
Without every daily file after the snapshot, "is this lien still open?" can't be answered.

What this module does, in order:
    1. download: ONE connection to the state's public file server, the four daily folders
       listed once each, then every file dated on or after the snapshot fetched one after
       another with a short pause, into data/raw/sunbiz/flr/ (gitignored). A file already
       on disk at the same size is skipped. Each fetched file gets a fetch-manifest row.
    2. inspect: every line of a fixed-width file must be exactly the documented length
       (82, 206, 135 or 206 characters). A file with any other line fails loudly and is
       moved to data/raw/sunbiz/flr/rejected/, out of reach of the upload.

Run from ~/datum with the project's virtual environment active:
    python src/datum/sunbiz_flr.py probe      # connect, list the four folders, print counts only
    python src/datum/sunbiz_flr.py download   # fetch what's missing, then inspect everything
    python src/datum/sunbiz_flr.py inspect    # inspect the files on disk and print the summary (no network)

The login is NOT a secret: the state publishes one shared public account on its data
download pages (docs/access/sunbiz.md), for exactly this use.

Needs paramiko 3.x, the same pin as duval.py (requirements.txt).
"""

import re                                   # regular expressions, to take a file name apart
import sys                                  # command-line arguments and the exit code
import time                                 # the short pause between downloads
from dataclasses import dataclass           # writes __init__ and friends for a class of plain fields
from datetime import date, datetime, timedelta   # calendar dates and day arithmetic
from pathlib import Path                    # file paths that work on any operating system

import paramiko                             # SFTP (file transfer over SSH) client library

try:                                        # imported as datum.sunbiz_flr (pytest puts src/ on the import path)
    from datum.manifest import MANIFEST_PATH, backfill, record_fetch
except ModuleNotFoundError:                 # run as a script: Python puts src/datum/ on the path, so the sibling module is plain `manifest`
    from manifest import MANIFEST_PATH, backfill, record_fetch

# --- Settings -------------------------------------------------------------------------
SOURCE = "sunbiz_flr"                                      # this source's name in the fetch manifest
REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/sunbiz_flr.py → go up 2 folders to the repo root
RAW_DIR = REPO_ROOT / "data" / "raw" / "sunbiz" / "flr"    # where downloads land; data/ is gitignored
REJECTED = "rejected"                                      # sub-folder of RAW_DIR for files that failed inspection
KNOWN_HOSTS = REPO_ROOT / "data" / "sunbiz_known_hosts"    # the server's identity key, saved on first contact (see connect)
HOST = "sftp.floridados.gov"                               # the Division of Corporations' public file server
PORT = 22                                                  # the standard SFTP port
PUBLIC_USER = "Public"                                     # the shared public account the state publishes on its data-download pages
PUBLIC_PASSWORD = "PubAccess1845!"                         # published next to it, for anyone to use: not a secret (docs/access/sunbiz.md)
SNAPSHOT_DATE = date(2026, 10, 3)                          # the quarterly snapshot we loaded; dailies dated on or after it are in scope
PAUSE_SECONDS = 0.5                                        # wait between files: sequential and unhurried
TIMEOUT_SECONDS = 60                                       # give up on a stalled connection instead of hanging


@dataclass(frozen=True)                     # frozen = fields can't change after creation
class FlrKind:
    """One of the four file kinds: where its dailies live and how long each line must be."""

    name: str                               # filings, debtors, events or secured
    letter: str                             # the last letter of the file name: f, d, e or s
    remote_dir: str                         # the folder of daily files on the state's server
    line_length: int                        # characters per line, from the state's layout (docs/access/sunbiz_flr.md)
    quarterly_file: str                     # the snapshot file's name once unzipped, e.g. FLRF.TXT
    quarterly_zip: str                      # the zip it came in, e.g. flrf.zip


KINDS = (                                   # order: filings first, because the other three point at them
    FlrKind("filings", "f", "doc/flr/filings", 82, "FLRF.TXT", "flrf.zip"),
    FlrKind("debtors", "d", "doc/flr/debtors", 206, "FLRD.TXT", "flrd.zip"),
    FlrKind("events", "e", "doc/flr/events", 135, "FLRE.TXT", "flre.zip"),
    FlrKind("secured", "s", "doc/flr/secured", 206, "FLRS.TXT", "flrs.zip"),
)
KIND_BY_LETTER = {kind.letter: kind for kind in KINDS}     # f → the filings kind, and so on
QUARTERLY_DIR = "doc/quarterly/flr"                        # where the snapshot zips live on the server

# Daily file names look like 20261104flrf.txt: the date as YYYYMMDD, "flr", a kind letter, ".txt".
FILE_NAME = re.compile(r"^(\d{8})flr([fdes])\.txt$")       # group 1 = the date digits, group 2 = the kind letter


class FlrInspectionError(Exception):
    """Raised when a line of a file is not the documented length. The file must not be loaded."""


@dataclass(frozen=True)
class FlrDailyFile:
    """One daily file, described by its name alone."""

    name: str                               # e.g. 20261104flrf.txt
    kind: FlrKind                           # which of the four kinds
    file_date: date                         # the date in the name: the day the state published the file

    @classmethod                            # a method called on the class itself: FlrDailyFile.from_name("...")
    def from_name(cls, name: str) -> "FlrDailyFile | None":
        """Build a FlrDailyFile from a file name, or return None when the name isn't a daily lien file."""
        match = FILE_NAME.match(name)                              # try the pattern on the whole name
        if match is None:                                          # a year folder, a readme, the quarterly FLRF.TXT ...
            return None
        try:
            file_date = datetime.strptime(match.group(1), "%Y%m%d").date()   # "20261104" → date(2026, 11, 4)
        except ValueError:                                         # eight digits that aren't a real date
            return None
        return cls(name=name, kind=KIND_BY_LETTER[match.group(2)], file_date=file_date)

    @property                               # read like a field: daily_file.source_url
    def source_url(self) -> str:
        """The exact address of this file on the state's server, for the fetch manifest."""
        return f"sftp://{HOST}/{self.kind.remote_dir}/{self.name}"


@dataclass(frozen=True)
class InspectReport:
    """What inspect_file() found in a file that passed."""

    name: str                               # which file was checked
    rows: int                               # lines in the file, every one the documented length


def inspect_file(path: Path, line_length: int) -> InspectReport:
    """Check that every line of a fixed-width file is exactly line_length characters. Raises on the first that isn't."""
    data = path.read_bytes()                                       # the whole file (a daily file is a few KB)
    if data and not data.endswith(b"\n"):                          # every complete line ends with a line break
        raise FlrInspectionError(f"{path.name}: last line has no line break, the download looks cut off")
    lines = data.split(b"\n")                                      # daily files end lines with LF
    if lines and lines[-1] == b"":                                 # the empty piece after the final line break
        lines.pop()
    for line_number, line in enumerate(lines, start=1):            # line_number starts at 1, like a text editor
        length = len(line.rstrip(b"\r"))                           # the quarterly files use CRLF: don't count the CR
        if length != line_length:                                  # a shifted or cut line would put every field in the wrong place
            raise FlrInspectionError(f"{path.name}: line {line_number} is {length} characters, expected {line_length}")
    return InspectReport(path.name, len(lines))


def local_files(raw_dir: Path = RAW_DIR) -> list[tuple[Path, FlrDailyFile]]:
    """Every daily lien file on disk that is in scope, oldest first."""
    found = []                                                     # (path, description) pairs
    for path in raw_dir.glob("*.txt"):                             # lower-case .txt: the quarterly FLRF.TXT doesn't match
        daily_file = FlrDailyFile.from_name(path.name)             # None for names that don't fit
        if daily_file is not None and daily_file.file_date >= SNAPSHOT_DATE:
            found.append((path, daily_file))
    return sorted(found, key=lambda pair: (pair[1].file_date, pair[1].name))   # by date, then name


def missing_business_days(present: set[date], first: date, last: date) -> list[date]:
    """Mondays to Fridays from first to last (inclusive) that are not in present.

    The state only publishes a daily file when something happened that day, so a missing
    day is not an error. The list is printed so a reader can tell a quiet day or a public
    holiday from a gap.
    """
    missing = []
    day = first
    while day <= last:
        if day.weekday() < 5 and day not in present:               # weekday(): Monday = 0 ... Friday = 4, Saturday = 5, Sunday = 6
            missing.append(day)
        day += timedelta(days=1)                                   # the next calendar day
    return missing


def connect() -> paramiko.SSHClient:
    """Open ONE SSH connection to the state's server with the published public login. The caller closes it."""
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
        HOST, port=PORT, username=PUBLIC_USER, password=PUBLIC_PASSWORD,   # the state's published public account
        timeout=TIMEOUT_SECONDS, banner_timeout=TIMEOUT_SECONDS, auth_timeout=TIMEOUT_SECONDS,   # never hang
        look_for_keys=False, allow_agent=False,                    # use the password only; don't offer this machine's SSH keys
    )
    return client


def list_remote(sftp: paramiko.SFTPClient) -> list[tuple[FlrDailyFile, int]]:
    """List each of the four daily folders once and keep the in-scope files, with their sizes in bytes."""
    in_scope = []                                                  # (description, size) pairs
    for kind in KINDS:                                             # four folders, four listing requests
        for entry in sftp.listdir_attr(kind.remote_dir):           # one request returns every name and size in the folder
            daily_file = FlrDailyFile.from_name(entry.filename)    # None for year folders and anything else
            if daily_file is not None and daily_file.kind is kind and daily_file.file_date >= SNAPSHOT_DATE:
                in_scope.append((daily_file, entry.st_size or 0))
    return sorted(in_scope, key=lambda pair: (pair[0].file_date, pair[0].name))   # oldest first


def download_missing(sftp: paramiko.SFTPClient, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> tuple[int, int]:
    """Fetch every in-scope file not already on disk at the same size. Returns (downloaded, skipped)."""
    raw_dir.mkdir(parents=True, exist_ok=True)                     # create data/raw/sunbiz/flr/ if needed
    downloaded = skipped = 0                                       # two counters
    for daily_file, size in list_remote(sftp):                     # oldest first
        target = raw_dir / daily_file.name                         # where the file goes
        rejected = raw_dir / REJECTED / daily_file.name            # where the file sits if it failed inspection before
        if any(copy.exists() and copy.stat().st_size == size for copy in (target, rejected)):   # already have it, same size: don't ask again
            skipped += 1
            continue
        partial = target.with_name(target.name + ".part")          # download under a temporary name
        sftp.get(f"{daily_file.kind.remote_dir}/{daily_file.name}", str(partial))   # one file, over the one open connection
        partial.replace(target)                                    # rename only when the whole file arrived
        record_fetch(SOURCE, target, daily_file.source_url, manifest_path=manifest_path)   # one manifest row: address, UTC time now, size, checksum
        downloaded += 1
        time.sleep(PAUSE_SECONDS)                                  # a short pause before the next file
    return downloaded, skipped


def inspect_all(raw_dir: Path = RAW_DIR, quarantine: bool = False, today: date | None = None) -> int:
    """Inspect every in-scope daily file on disk and print the summary. Returns the failure count.

    Prints: each failure, a table of file date by rows for the four kinds, and the business
    days with no file. With quarantine=True a failing file is moved to raw_dir/rejected/.
    """
    rows_by_date: dict[date, dict[str, int]] = {}                  # file date → {kind name: rows}
    failures = 0
    for path, daily_file in local_files(raw_dir):
        try:
            report = inspect_file(path, daily_file.kind.line_length)   # raises when a line is the wrong length
        except FlrInspectionError as error:
            failures += 1
            print(f"FAIL  {error}")                                # loud: one line per bad file
            if quarantine:                                         # keep it away from the files that will be loaded
                (raw_dir / REJECTED).mkdir(exist_ok=True)          # create rejected/ on first use
                path.replace(raw_dir / REJECTED / path.name)       # move, don't delete: the evidence stays on disk
            continue
        rows_by_date.setdefault(daily_file.file_date, {})[daily_file.kind.name] = report.rows   # remember rows for the table

    print("file date    " + "".join(f"{kind.name:>9}" for kind in KINDS))   # table header: one column per kind
    totals = {kind.name: 0 for kind in KINDS}                      # running total per kind
    for file_date in sorted(rows_by_date):
        cells = []
        for kind in KINDS:
            rows = rows_by_date[file_date].get(kind.name)          # None when that kind has no file for the day
            cells.append(f"{'-' if rows is None else rows:>9}")    # a dash shows "no file", which differs from "0 rows"
            totals[kind.name] += rows or 0
        print(f"{file_date.isoformat()}   " + "".join(cells))
    print("total        " + "".join(f"{totals[kind.name]:>9}" for kind in KINDS))
    files = sum(len(kinds) for kinds in rows_by_date.values())
    print(f"OK    {files} files on {len(rows_by_date)} days, every line the documented length "
          + ", ".join(f"{kind.name} {kind.line_length}" for kind in KINDS))

    last = today or date.today()                                   # tests pass a fixed "today"
    missing = missing_business_days(set(rows_by_date), SNAPSHOT_DATE, last - timedelta(days=1))   # today's file isn't published until tomorrow
    print(f"business days with no file, {SNAPSHOT_DATE} to {last - timedelta(days=1)}: "
          + (", ".join(day.isoformat() for day in missing) or "none"))
    print(f"{failures} file(s) failed inspection")
    return failures


def backfill_manifest(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> int:
    """Add approximate fetch-manifest rows for lien files that were on disk before the manifest existed."""
    files: list[tuple[Path, str, Path | None]] = []                # (path, source URL, file to take the time from)
    for kind in KINDS:                                             # the quarterly snapshot: four files unpacked from four zips
        unpacked = raw_dir / kind.quarterly_file                   # e.g. FLRF.TXT, whose own time is when the STATE wrote it
        archive = raw_dir / kind.quarterly_zip                     # e.g. flrf.zip, whose time is when we downloaded it
        if unpacked.exists():
            files.append((unpacked, f"sftp://{HOST}/{QUARTERLY_DIR}/{kind.quarterly_zip}", archive if archive.exists() else None))
    for path, daily_file in local_files(raw_dir):                  # daily files: their own modification time is the download time
        files.append((path, daily_file.source_url, None))
    return backfill(SOURCE, files, manifest_path)


def main(argv: list[str]) -> int:
    """Command line: probe | download | inspect."""
    command = argv[1] if len(argv) > 1 else ""                     # the word after the script name
    if command not in ("probe", "download", "inspect"):
        print("usage: python src/datum/sunbiz_flr.py probe|download|inspect")
        return 2                                                   # 2 = "you called me wrong", by Unix convention
    if command in ("probe", "download"):                           # these two need the network
        client = connect()                                         # the ONE connection
        try:
            sftp = client.open_sftp()                              # start the file-transfer channel on it
            if command == "probe":                                 # look, don't fetch
                listing = list_remote(sftp)
                print(f"connected over SFTP; {len(listing)} in-scope daily files, {sum(size for _, size in listing)} bytes")
                if listing:
                    print(f"first {listing[0][0].name}, last {listing[-1][0].name}")
                return 0
            downloaded, skipped = download_missing(sftp)
            print(f"downloaded {downloaded} files, skipped {skipped} already on disk")
        finally:
            client.close()                                         # always hang up, even after an error
    return 1 if inspect_all(quarantine=True) else 0                # non-zero exit code when any file failed


if __name__ == "__main__":                  # true only when this file is run directly
    sys.exit(main(sys.argv))                # run main and pass its result to the shell
