"""dbpr.py: download and validate the DBPR construction license files.

DBPR = Florida Department of Business and Professional Regulation. It publishes free CSV
files of construction licensees and of discipline cases against licensed contractors.
Where the files live, their layouts and the site's terms: docs/access/dbpr.md.

What this module does, in order:
    1. download: one HTTPS request per file, saved under data/raw/dbpr/ (gitignored). Every
       downloaded file gets one row in the fetch manifest (manifest.py, ruling R23).
    2. validate: BEFORE anything is loaded into Snowflake, check the file is the shape we
       expect: the right number of columns on every row, enough rows, and a complete
       last line. A file that fails is reported loudly and must not be loaded.

Run from ~/datum with the project's virtual environment active:
    python src/datum/dbpr.py download     # fetch every file in FILES, then validate each
    python src/datum/dbpr.py validate     # validate the files already on disk (no network)

No secrets are needed: the files are public and need no login.
"""

import csv                                  # reads quote/comma delimited text the way the state writes it
import ssl                                  # builds the settings for a verified HTTPS connection
import sys                                  # command-line arguments and the exit code
import time                                 # a short pause between downloads, to be polite to the server
import urllib.request                       # Python's built-in HTTP client: no extra package to install
from dataclasses import dataclass           # a decorator that writes __init__ and friends for a class of plain fields
from pathlib import Path                    # file paths that work on any operating system

import truststore                           # verifies HTTPS certificates against the operating system's trusted list (already in the venv)

try:                                        # imported as datum.dbpr (pytest puts src/ on the import path)
    from datum.manifest import MANIFEST_PATH, backfill, record_fetch
except ModuleNotFoundError:                 # run as a script: Python puts src/datum/ on the path, so the sibling module is plain `manifest`
    from manifest import MANIFEST_PATH, backfill, record_fetch

# --- Settings -------------------------------------------------------------------------
SOURCE = "dbpr"                                            # this source's name in the fetch manifest
REPO_ROOT = Path(__file__).resolve().parents[2]            # this file is src/datum/dbpr.py → go up 2 folders to ~/datum
RAW_DIR = REPO_ROOT / "data" / "raw" / "dbpr"              # where downloads land; data/ is gitignored
USER_AGENT = "datum-dbpr/0.1 (Andrescamacho57@gmail.com)"  # tells the state who is downloading and how to reach us
TIMEOUT_SECONDS = 120                                      # give up on a stalled download instead of hanging forever
PAUSE_SECONDS = 2                                          # wait between files: sequential and unhurried
ENCODING = "latin-1"                                       # one byte = one character, so no byte can fail to decode

LICENSE_BASE = "https://www2.myfloridalicense.com/sto/file_download/extracts/"   # licensee extracts folder
DISCIPLINE_BASE = "https://www2.myfloridalicense.com/pro/cilb/reports/"          # CILB (Construction Industry Licensing Board) reports folder


class DbprValidationError(Exception):
    """Raised when a downloaded file is not the shape we expect. The file must not be loaded."""


@dataclass(frozen=True)                     # frozen = fields can't be changed after creation: a spec is a fact, not a variable
class ValidationReport:
    """What validate() found in a file that passed."""

    file_name: str                          # which file was checked
    file_lines: int                         # physical lines in the file (what `wc -l` prints)
    data_rows: int                          # rows of data = file lines minus the header line, if the file has one


@dataclass(frozen=True)
class DbprFile:
    """One DBPR download file: where it comes from and what a healthy copy looks like."""

    file_name: str                          # the name on the state's server and on our disk
    url: str                                # the exact address of the file
    expected_columns: int                   # every row must have exactly this many fields
    expected_header: tuple[str, ...] | None = None   # the header row we expect, or None when the file has no header row
    min_rows: int = 1                       # fewer data rows than this means a truncated or empty download

    def path(self, raw_dir: Path = RAW_DIR) -> Path:
        """Where this file lives on disk."""
        return raw_dir / self.file_name     # e.g. data/raw/dbpr/CONSTRUCTIONLICENSE_1.csv

    def download(self, raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> Path:
        """Fetch the file with ONE request, save it and add its fetch-manifest row. No retry: a failure is reported, not hidden."""
        raw_dir.mkdir(parents=True, exist_ok=True)                 # create data/raw/dbpr/ if it isn't there yet
        target = self.path(raw_dir)                                # the final file name
        partial = target.with_name(target.name + ".part")          # download under a temporary name first
        request = urllib.request.Request(self.url, headers={"User-Agent": USER_AGENT})   # the request, with our identity attached
        tls = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)      # verify the server's certificate with the system's trusted list (this Python ships without its own)
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=tls) as response:   # open the connection (raises on HTTP errors like 404)
            partial.write_bytes(response.read())                   # write the bytes exactly as received: raw stays raw
        partial.replace(target)                                    # rename only after the whole file arrived, so a half file never has the real name
        record_fetch(SOURCE, target, self.url, manifest_path=manifest_path)   # one manifest row: address, UTC time now, size, checksum
        return target                                              # hand back the path for the next step

    def validate(self, raw_dir: Path = RAW_DIR) -> ValidationReport:
        """Check the file's shape. Returns a report if healthy, raises DbprValidationError if not."""
        target = self.path(raw_dir)                                # the file to check
        if not target.exists():                                    # nothing was downloaded
            raise DbprValidationError(f"{self.file_name}: file not found at {target}")
        raw_bytes = target.read_bytes()                            # the whole file in memory (the biggest is a few tens of MB)
        if not raw_bytes:                                          # zero bytes
            raise DbprValidationError(f"{self.file_name}: file is empty")
        if not raw_bytes.endswith(b"\n"):                          # every complete line ends with a line break
            raise DbprValidationError(f"{self.file_name}: last line has no line break, the download looks cut off")

        file_lines = raw_bytes.count(b"\n")                        # physical lines, the same number `wc -l` prints
        text = raw_bytes.decode(ENCODING)                          # bytes → text; latin-1 never fails
        reader = csv.reader(text.splitlines(keepends=True))        # parse quote/comma rows; keepends lets a quoted field span lines
        data_rows = 0                                              # count of data rows seen so far
        for row_number, row in enumerate(reader, start=1):         # row_number starts at 1, like a text editor
            if row_number == 1 and self.expected_header is not None:   # the first row of a file that should have a header
                found = tuple(cell.strip() for cell in row)        # trim padding so "Name " equals "Name"
                if found != self.expected_header:                  # the state changed, added or dropped a column
                    raise DbprValidationError(f"{self.file_name}: header changed.\n  expected {self.expected_header}\n  found    {found}")
                continue                                           # the header isn't data: don't count it
            if len(row) != self.expected_columns:                  # a row with too few or too many fields
                raise DbprValidationError(f"{self.file_name}: row {row_number} has {len(row)} columns, expected {self.expected_columns}")
            data_rows += 1                                         # a healthy data row

        if data_rows < self.min_rows:                              # far fewer rows than the file should have
            raise DbprValidationError(f"{self.file_name}: {data_rows} data rows, expected at least {self.min_rows}")
        return ValidationReport(self.file_name, file_lines, data_rows)   # the numbers the load is checked against


# --- The files we load ----------------------------------------------------------------
# Layouts verified on the real files on 2026-11-12 (docs/access/dbpr.md).

DISCIPLINE_HEADER = (                       # the header row of every discipline file, exactly as the state writes it
    "License Type", "License Nbr", "Respondent Name", "Address Line 1", "Address Line 2", "Address Line 3",
    "City", "State", "ZIP Code", "County", "Complaint Nbr", "Classification", "Entered Date", "Disposition",
    "Disposition Date", "Discipline Date - Description", "Violation Code",
)
DISCIPLINE_FISCAL_YEARS = ("2122", "2223", "2324", "2425", "2526")   # "2526" = fiscal year July 2025 – June 2026; the five years the state posts

LICENSE_FILE = DbprFile(
    file_name="CONSTRUCTIONLICENSE_1.csv",                          # construction licensees, about 263,000 rows
    url=LICENSE_BASE + "/CONSTRUCTIONLICENSE_1.csv",                # the double slash is in the state's own link
    expected_columns=22,                                            # 21 documented fields + 1 empty field from a trailing comma
    expected_header=None,                                           # this file has NO header row: line 1 is data
    min_rows=200_000,                                               # 263,337 on 2026-11-12; far fewer means a cut-off download
)
DISCIPLINE_FILES = tuple(                                           # one spec per fiscal year, built from the list above
    DbprFile(
        file_name=f"contractor_disc_lic_{fiscal_year}.csv",         # e.g. contractor_disc_lic_2526.csv
        url=DISCIPLINE_BASE + f"contractor_disc_lic_{fiscal_year}.csv",
        expected_columns=17,                                        # the 17 header names above
        expected_header=DISCIPLINE_HEADER,                          # these files DO start with a header row
        min_rows=100,                                               # the smallest (the current, partial year) had 395 on 2026-11-12
    )
    for fiscal_year in DISCIPLINE_FISCAL_YEARS
)
FILES: tuple[DbprFile, ...] = (LICENSE_FILE, *DISCIPLINE_FILES)     # everything `download` and `validate` work through, in order


def backfill_manifest(raw_dir: Path = RAW_DIR, manifest_path: Path = MANIFEST_PATH) -> int:
    """Add approximate fetch-manifest rows for DBPR files that were on disk before the manifest existed."""
    files = [(f.path(raw_dir), f.url, None) for f in FILES if f.path(raw_dir).exists()]   # (path, source URL, None = the file's own modification time)
    return backfill(SOURCE, files, manifest_path)


def main(argv: list[str]) -> int:
    """Command line: `download` fetches then validates; `validate` only checks what's on disk."""
    command = argv[1] if len(argv) > 1 else ""                     # the word after the script name
    if command not in ("download", "validate"):                    # anything else: show how to use it
        print("usage: python src/datum/dbpr.py download|validate")
        return 2                                                   # 2 = "you called me wrong", by Unix convention
    failures = 0                                                   # how many files failed
    for index, dbpr_file in enumerate(FILES):                      # one file at a time, in order
        try:
            if command == "download":
                if index > 0:                                      # no pause before the first file
                    time.sleep(PAUSE_SECONDS)
                dbpr_file.download()                               # one request for this file
            report = dbpr_file.validate()                          # shape check, always
            print(f"OK    {report.file_name}: {report.file_lines} lines, {report.data_rows} data rows")
        except (DbprValidationError, OSError) as error:            # OSError covers network and disk failures
            failures += 1
            print(f"FAIL  {dbpr_file.file_name}: {error}")         # loud, and we carry on to the next file
    return 1 if failures else 0                                    # a non-zero exit code tells the shell something failed


if __name__ == "__main__":                  # true only when this file is run directly, not when it's imported
    sys.exit(main(sys.argv))                # run main and pass its result to the shell as the exit code
