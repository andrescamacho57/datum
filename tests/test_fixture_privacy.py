"""test_fixture_privacy.py: no fixture row about a person may hold a value that leads back to that person.

The fixtures under tests/fixtures/ are cut from real public records, and the repository is public.
Replacing a person's name with REDACTED is not enough (decision by Andres, Nov 19, 2026): a real
instrument number, book and page, case number, parcel number, license number or complaint number
can be typed into the source's own search, which then shows the name. So a row about a person must
carry invented numbers, in ranges no real record uses. The ranges are written down in
tests/fixtures/duval/README.md and tests/fixtures/dbpr/README.md, and repeated below on purpose:
a test that read its ranges from the files it checks could only agree with them.

The check fails closed, which means that when it cannot tell, it treats the row as a person's:
- A name must be either the redaction itself or plainly a business (its last word is LLC, INC, BANK
  and so on). Any other name is reported, so a name that was never redacted, or was replaced with
  some other placeholder, cannot slip through as "not a person".
- A Duval document counts as a business's only when a parties file lists it and every one of its
  parties is plainly a business. A document with no party rows at all is treated as a person's.
- A file or a row in a shape this test does not know is reported, not skipped.

What this test does not look at: dates, recording times, amounts, cities and ZIP codes stay real on
a person's row. No single one of them finds a person, but a patient reader could combine them.
Whether they should be invented too is an open decision (see the fixture READMEs).

A problem is reported as a file, a line number and the rule that was broken. The value itself is
never printed, because this test's output lands in public CI (continuous integration) logs.

Run from the repo root:  pytest tests/test_fixture_privacy.py
"""

import csv                                  # reads DBPR's quoted, comma-separated rows
import re                                   # regular expressions: patterns for "looks like an invented number"
from pathlib import Path                    # file paths

import pytest                               # the test runner; parametrize runs one test body over several cases

FIXTURES = Path(__file__).parent / "fixtures"              # tests/fixtures/

MARK = "REDACTED"                                          # the word every redacted name or address contains
REDACTED_NAMES = {"REDACTED PERSON", "REDACTED, PERSON"}   # the two spellings the fixtures use for a person's name
# A name is "plainly a business" when its last word is one of these. Short endings that also end
# people's names (CO, PA) are left out on purpose: a wrong "business" is the costly mistake here.
BUSINESS_ENDINGS = {"LLC", "INC", "CORP", "CORPORATION", "COMPANY", "LP", "LLP", "LTD", "PLLC", "NA", "BANK", "ASSOCIATION"}
# Words that join a person's name to a business name: "<person> DBA <business> LLC" ends like a business and names a person.
ALIAS_WORDS = {"DBA", "D/B/A", "AKA", "A/K/A", "FKA", "F/K/A"}
HEADER_NAMES = {"Licensee Name", "Respondent Name"}        # column 3 of a DBPR header row
ADDRESS_COLUMNS = {"construction_license": (5, 6, 7), "contractor_disc": (3, 4, 5)}   # the three street-address cells, counted from 0
BANNED_TEXT = ("Case#", "PIN ")                            # how the Clerk writes a court case number and a parcel number

# The invented ranges. Each one starts above the largest real value in the files on disk (counted Nov 19, 2026).
INVENTED_INSTRUMENT = re.compile(r"\d{4}9\d{5}")           # Duval: the year, then a running number of 900000 or more
INVENTED_BOOKS = range(90001, 100000)                      # Duval: the largest real book on disk is 22125
INVENTED_LICENSE = re.compile(r"99\d{5}")                  # DBPR: 9900000 to 9999999
INVENTED_ALTERNATE = re.compile(r"[A-Z]+99\d{5}")          # DBPR: the occupation code, then an invented license number
INVENTED_COMPLAINT = re.compile(r"\d{4}9\d{5}")            # DBPR: the year, then a running number of 900000 or more
INVENTED_WORD = "INVENTED"                                 # every invented legal description contains this word

DUVAL_KIND = re.compile(r"([dpl])\d{10}id\.16")            # d = documents, p = parties, l = links
DUVAL_LOOKUP = re.compile(r"m\d{10}d\.16")                 # the document-type lookup file, which has no rows about anyone
BYTE_ORDER_MARK = "\xef\xbb\xbf"                           # three bytes some of the Clerk's files start with, as latin-1 reads them
BOOK_AND_PAGE = re.compile(r"(\d+)/\d+")                   # a links row can end "-OR <book>/<page>"


def rows_of(path: Path) -> list[tuple[int, str]]:
    """Every line of a fixture with its line number. latin-1 maps each byte to one character, so no file can fail to decode."""
    text = path.read_bytes().decode("latin-1").removeprefix(BYTE_ORDER_MARK)
    return [(number, line.rstrip("\r")) for number, line in enumerate(text.split("\n"), start=1)]


def is_plainly_a_business(name: str) -> bool:
    words = [word.upper() for word in name.replace(".", " ").replace(",", " ").split()]
    return bool(words) and words[-1] in BUSINESS_ENDINGS and not ALIAS_WORDS.intersection(words)


def is_data_line(line: str) -> bool:
    return bool(line) and not line.startswith("EOF|")       # not a blank line and not the trailer


def is_invented_book(value: str) -> bool:
    return value.isdigit() and int(value) in INVENTED_BOOKS


def business_only_instruments(duval_dir: Path) -> set[str]:
    """Instrument numbers whose every party, in a parties file, is plainly a business. Only these may keep real values."""
    parties: dict[str, list[str]] = {}
    for path in sorted(duval_dir.rglob("p*.16")):
        for _, line in rows_of(path):
            fields = line.split("|")
            if fields[0] == "DPA" and len(fields) >= 7:
                parties.setdefault(fields[2], []).append("|".join(fields[5:-1]))    # one real name holds a pipe
    return {instrument for instrument, names in parties.items() if all(is_plainly_a_business(name) for name in names)}


def duval_problems(duval_dir: Path) -> list[str]:
    problems = []
    business_only = business_only_instruments(duval_dir)
    for path in sorted(duval_dir.rglob("*.16")):
        where = path.relative_to(duval_dir.parent)
        kind = DUVAL_KIND.fullmatch(path.name)
        if kind is None:
            if not DUVAL_LOOKUP.fullmatch(path.name):
                problems.append(f"{where}: a file name this test does not know, so it cannot check the rows. Teach it the layout")
            continue
        if kind.group(1) == "p":
            for number, line in rows_of(path):
                if not is_data_line(line):
                    continue
                fields = line.split("|")
                if fields[0] != "DPA" or len(fields) < 7:
                    problems.append(f"{where} line {number}: a party row in a shape this test does not know")
                    continue
                name = "|".join(fields[5:-1])
                if name not in REDACTED_NAMES and not is_plainly_a_business(name):
                    problems.append(f"{where} line {number}: a party name that is neither the redaction nor plainly a business")
                if fields[2] not in business_only and not INVENTED_INSTRUMENT.fullmatch(fields[2]):
                    problems.append(f"{where} line {number}: a party row of a person's document has an instrument number outside the invented range")
        elif kind.group(1) == "d":
            # A legal description can hold a line break, so one record can sit on two or three lines. Glue them back together first.
            records: list[tuple[int, str]] = []
            for number, line in rows_of(path):
                if line.startswith("DDA|"):
                    records.append((number, line))
                elif is_data_line(line) and records:
                    records[-1] = (records[-1][0], records[-1][1] + line)
                elif is_data_line(line):
                    problems.append(f"{where} line {number}: a line before the first document row, in a shape this test does not know")
            for number, record in records:
                fields = record.split("|")
                if len(fields) != 15:
                    problems.append(f"{where} line {number}: a document row in a shape this test does not know")
                    continue
                if fields[2] in business_only:
                    continue
                if not INVENTED_INSTRUMENT.fullmatch(fields[2]):
                    problems.append(f"{where} line {number}: a person's document has an instrument number outside the invented range")
                for banned in BANNED_TEXT:
                    if banned in record:
                        problems.append(f"{where} line {number}: a person's document holds '{banned.strip()}'")
                legal = fields[5].strip(" \x00")
                if legal and INVENTED_WORD not in legal:
                    problems.append(f"{where} line {number}: a person's document has a legal description without the word {INVENTED_WORD}")
                if not is_invented_book(fields[7]):
                    problems.append(f"{where} line {number}: a person's document has a book outside the invented range")
        else:
            for number, line in rows_of(path):
                if not is_data_line(line):
                    continue
                fields = line.split("|")
                if len(fields) != 10:
                    problems.append(f"{where} line {number}: a link row in a shape this test does not know")
                    continue
                if fields[0] in business_only:
                    continue
                if not INVENTED_INSTRUMENT.fullmatch(fields[0]):
                    problems.append(f"{where} line {number}: a link row of a person's document has an instrument number outside the invented range")
                if not is_invented_book(fields[1]):
                    problems.append(f"{where} line {number}: a link row of a person's document has a book outside the invented range")
                old_shape = fields[6] + fields[7]           # the Clerk's older instrument numbers are the book digits followed by the page digits
                if fields[5] and not INVENTED_INSTRUMENT.fullmatch(fields[5]) and fields[5] != old_shape:
                    problems.append(f"{where} line {number}: a link row of a person's document points at an instrument number outside the invented range")
                if fields[6] and not is_invented_book(fields[6]):
                    problems.append(f"{where} line {number}: a link row of a person's document points at a book outside the invented range")
                if any(not is_invented_book(book) for book in BOOK_AND_PAGE.findall(fields[9])):
                    problems.append(f"{where} line {number}: a link row of a person's document names a book and page outside the invented range")
    return problems


def dbpr_problems(dbpr_dir: Path) -> list[str]:
    problems = []
    for path in sorted(dbpr_dir.rglob("*.csv")):
        where = path.relative_to(dbpr_dir.parent)
        with path.open(newline="", encoding="latin-1") as handle:
            for number, row in enumerate(csv.reader(handle), start=1):
                name = row[2] if len(row) > 2 else ""
                if name in HEADER_NAMES or (name not in REDACTED_NAMES and is_plainly_a_business(name) and not any(MARK in cell for cell in row)):
                    continue                                # the header, or a row about a business
                if name not in REDACTED_NAMES and not is_plainly_a_business(name):
                    problems.append(f"{where} line {number}: a name that is neither the redaction nor plainly a business")
                # The READMEs promise that a person's street address is REDACTED. Hold them to it.
                for prefix, columns in ADDRESS_COLUMNS.items():
                    if path.name.startswith(prefix) and any(len(row) > c and row[c] not in ("", MARK) for c in columns):
                        problems.append(f"{where} line {number}: a person's row has a street address that is not {MARK}")
                if path.name.startswith("construction_license"):
                    if len(row) > 12 and row[12] and not INVENTED_LICENSE.fullmatch(row[12]):
                        problems.append(f"{where} line {number}: a person's row has a license number outside the invented range")
                    if len(row) > 20 and row[20] and not INVENTED_ALTERNATE.fullmatch(row[20]):
                        problems.append(f"{where} line {number}: a person's row has an alternate license number outside the invented range")
                    # Column 4 is the business the person does business as. DBPR's search finds the person by that name too.
                    if len(row) > 3 and row[3] and INVENTED_WORD not in row[3]:
                        problems.append(f"{where} line {number}: a person's row has a business name without the word {INVENTED_WORD}")
                elif path.name.startswith("contractor_disc"):
                    if not INVENTED_LICENSE.fullmatch(row[1]):
                        problems.append(f"{where} line {number}: a person's row has a license number outside the invented range")
                    if not INVENTED_COMPLAINT.fullmatch(row[10]):
                        problems.append(f"{where} line {number}: a person's row has a complaint number outside the invented range")
                else:
                    # A layout this test has never seen: it cannot know which columns identify a person, so it refuses to guess.
                    problems.append(f"{where} line {number}: a row about a person in a file layout this test does not know. Teach it the layout")
                    break
    return problems


def find_problems(root: Path) -> list[str]:
    """Every rule broken under root, which is laid out like tests/fixtures/. An empty list means the fixtures are clean."""
    problems = []
    # The plain rule, for every source: a line that holds a redaction may not also hold a case number or a parcel number.
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix != ".md"):
        for number, line in rows_of(path):
            for banned in BANNED_TEXT:
                if MARK in line and banned in line:
                    problems.append(f"{path.relative_to(root)} line {number}: a redacted row holds '{banned.strip()}'")
    problems += duval_problems(root / "duval")
    problems += dbpr_problems(root / "dbpr")
    return problems


def test_no_fixture_row_about_a_person_leads_back_to_that_person():
    problems = find_problems(FIXTURES)
    assert problems == [], "\n".join(problems)


# --- Proof that the check can fail --------------------------------------------------------
# Each case writes one or two tiny files that break exactly one rule, the way a fixture cut from a
# real file with only the name replaced would. The out-of-range numbers are made up too: their
# running number is 000000, which no source issues.

PERSON = "DPA|16|2024900001|1|TO|REDACTED PERSON|\r\n"                       # makes 2024900001 a person's document
LICENSE_ROW = '"06","CBC","REDACTED, PERSON","INVENTED BUILDERS INC","","REDACTED","","","TAMPA","FL","33675","39","{}","C","A","","","","","","{}",""\r\n'
DISCIPLINE_ROW = '"Certified Building Contractor","{}","REDACTED, PERSON","REDACTED","","","TAMPA","FL","33675","DADE","{}","Licensed Activity","","","","",""\r\n'

BROKEN = [
    ("a redacted party next to an out-of-range instrument number",
     {"duval/p2025010301id.16": "DPA|16|2024000000|1|TO|REDACTED PERSON|\r\n"}, "instrument number"),
    ("a case number on a person's document",
     {"duval/p2025010301id.16": PERSON, "duval/d2025010301id.16": "DDA|16|2024900001|SAT|SATISFACTION|Case# 16- L1 INVENTED ACRES|OR|90001|101||1|12/30/2024|1|0.00|\r\n"}, "'Case#'"),
    ("a parcel number on a person's document",
     {"duval/p2025010301id.16": PERSON, "duval/d2025010301id.16": "DDA|16|2024900001|N/C|NOTICE|PIN 000000-0000 L1 INVENTED ACRES|OR|90001|101||1|12/30/2024|1|0.00|\r\n"}, "'PIN'"),
    ("a redaction and a case number on the same line, in a source this test has no layout for",
     {"other_source/rows.txt": "REDACTED PERSON  Case# 16-0000-XX-000000\r\n"}, "'Case#'"),
    ("a document with no party rows and a legal description that was not invented",
     {"duval/rejected/d2026011501id.16": "DDA|16|2004900001|MTG|MORTGAGE|L1 B1 SOME REAL PLACE|OR|90010|101||6|11/03/2004|1|0.00|\r\n"}, "legal description"),
    ("a document with no party rows, split over two lines, with an out-of-range book on the second line",
     {"duval/rejected/d2026011501id.16": "DDA|16|2004900001|MTG|MORTGAGE|L1 INVENTED ACRES\r\n|OR|0|101||6|11/03/2004|1|0.00|\r\n"}, "book"),
    ("a document with no party rows and an out-of-range instrument number",
     {"duval/rejected/d2026011501id.16": "DDA|16|2004000000|MTG|MORTGAGE|L1 INVENTED ACRES|OR|90010|101||6|11/03/2004|1|0.00|\r\n"}, "document has an instrument number"),
    ("a party whose name was replaced with some other placeholder, next to real-shaped numbers",
     {"duval/p2025010301id.16": "DPA|16|2024000000|1|TO|NAME REMOVED|\r\n", "duval/d2025010301id.16": "DDA|16|2024000000|N/C|NOTICE|PIN 000000-0000 L1 SOME PLACE|OR|1|1||1|12/30/2024|1|0.00|\r\n"}, "neither the redaction nor plainly a business"),
    ("the same placeholder case, which must also stop the document from counting as a business's",
     {"duval/p2025010301id.16": "DPA|16|2024000000|1|TO|NAME REMOVED|\r\n", "duval/d2025010301id.16": "DDA|16|2024000000|N/C|NOTICE|PIN 000000-0000 L1 SOME PLACE|OR|1|1||1|12/30/2024|1|0.00|\r\n"}, "'PIN'"),
    ("a party written as a person doing business as a company, which ends like a business and is not one",
     {"duval/p2025010301id.16": "DPA|16|2024000000|1|TO|DOE JANE DBA DOE ROOFING LLC|\r\nDPA|16|2024000000|1|FRM|BOLT BANK NA|\r\n"}, "neither the redaction nor plainly a business"),
    ("the same doing-business-as case, which must also stop the document from counting as a business's",
     {"duval/p2025010301id.16": "DPA|16|2024000000|1|TO|DOE JANE DBA DOE ROOFING LLC|\r\nDPA|16|2024000000|1|FRM|BOLT BANK NA|\r\n",
      "duval/d2025010301id.16": "DDA|16|2024000000|SAT|SATISFACTION|Case# 16-|OR|1|1||1|12/30/2024|1|0.00|\r\n"}, "'Case#'"),
    ("a link row of a person's document with an out-of-range book of its own",
     {"duval/l2025010301id.16": "2024900001|1|101|OR|SAT|||||NONE\r\n"}, "link row of a person's document has a book"),
    ("a link from a person's document to an out-of-range earlier book",
     {"duval/l2025010301id.16": "2024900001|90001|101|OR|SAT|2018900001|1|101|OR|MTG\r\n"}, "points at a book"),
    ("a link from a person's document that names an out-of-range book and page as text",
     {"duval/l2025010301id.16": "2024900001|90001|101|OR|ASSIGN|||||-OR 1/101\r\n"}, "names a book and page"),
    ("a link row with one field too many, which the test must not skip",
     {"duval/l2025010301id.16": "2024000000|1|101|OR|SAT|||||NONE|\r\n"}, "link row in a shape this test does not know"),
    ("a Duval file under a name the test has no layout for",
     {"duval/x2025010301id.16": "2024000000|1|101\r\n"}, "file name this test does not know"),
    ("a link from a person's document to an out-of-range earlier instrument",
     {"duval/l2025010301id.16": "2024900001|90001|101|OR|SAT|2018000000|90003|101|OR|MTG\r\n"}, "points at an instrument number"),
    ("a person's license row with an out-of-range license number",
     {"dbpr/construction_license_20.csv": LICENSE_ROW.format("0000000", "CBC9900001")}, "license number"),
    ("a person's license row with an out-of-range alternate license number",
     {"dbpr/construction_license_20.csv": LICENSE_ROW.format("9900001", "CBC000000")}, "alternate license number"),
    ("a person's license row that still names the business the person trades as",
     {"dbpr/construction_license_20.csv": LICENSE_ROW.format("9900001", "CBC9900001").replace("INVENTED BUILDERS INC", "ACME BUILDERS INC")}, "business name"),
    ("a person's license row whose street address was left in",
     {"dbpr/construction_license_20.csv": LICENSE_ROW.format("9900001", "CBC9900001").replace('"","REDACTED","",""', '"","1 SOME STREET","",""')}, "street address"),
    ("a person's discipline row whose street address was left in",
     {"dbpr/contractor_disc_lic_19.csv": DISCIPLINE_ROW.format("9900011", "2025900001").replace('"REDACTED","",""', '"1 SOME STREET","",""')}, "street address"),
    ("a person's discipline row with an out-of-range complaint number",
     {"dbpr/contractor_disc_lic_19.csv": DISCIPLINE_ROW.format("9900011", "2025000000")}, "complaint number"),
    ("a person's discipline row with an out-of-range license number",
     {"dbpr/contractor_disc_lic_19.csv": DISCIPLINE_ROW.format("0000000", "2025900001")}, "license number"),
    ("a discipline row whose respondent was replaced with some other placeholder",
     {"dbpr/contractor_disc_lic_19.csv": DISCIPLINE_ROW.format("0000000", "2025000000").replace("REDACTED, PERSON", "NAME REMOVED")}, "neither the redaction nor plainly a business"),
    ("a redacted row in a DBPR file whose layout the test does not know",
     {"dbpr/some_new_extract.csv": '"REDACTED, PERSON","0000000"\r\n'}, "does not know"),
]


@pytest.mark.parametrize("files, expected", [case[1:] for case in BROKEN], ids=[case[0] for case in BROKEN])
def test_the_check_fails_on_a_row_that_still_leads_to_a_person(tmp_path, files, expected):
    # tmp_path is an empty temporary folder pytest creates for this one test.
    for name, content in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(content.encode("latin-1"))
    problems = find_problems(tmp_path)
    assert any(expected in problem for problem in problems), problems


def test_a_document_between_businesses_may_keep_its_real_values(tmp_path):
    # The check must not push anyone to invent values for business records, which are what Datum is about.
    (tmp_path / "duval").mkdir()
    (tmp_path / "duval" / "p2025010301id.16").write_bytes(b"DPA|16|2024000000|1|TO|ACME LLC|\r\nDPA|16|2024000000|1|FRM|BOLT BANK NA|\r\n")
    (tmp_path / "duval" / "d2025010301id.16").write_bytes(b"DDA|16|2024000000|RELEASE|RELEASE|Case# 16-|OR|1|1||1|12/31/2024|1|0.00|\r\n")
    (tmp_path / "duval" / "l2025010301id.16").write_bytes(b"2024000000|1|1|OR|RELEASE|2014000000|1|1|OR|MTG\r\n")
    assert find_problems(tmp_path) == []
