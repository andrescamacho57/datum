# Duval recording index fixtures

Cut from real files in the Duval County Clerk's bulk recording index so the tests run offline (CLAUDE.md rule 4). The layout, the line endings and the damage are the Clerk's. On every row about a person, the values that could lead back to that person are invented (see "What is invented, and why" below).

Origin: SFTP `ftp.duvalclerk.com`, folder `/Recording Indexes`, the four files dated 2025-01-03. Captured 2026-11-12T13:10Z.

| Fixture | What it is |
|---|---|
| `d2025010301id.16` | 11 document rows (satisfactions, releases, notices of commencement), trailer rewritten to `EOF|11`. 3 rows are about businesses only and are real; 8 carry invented values |
| `p2025010301id.16` | The 32 party rows for those 11 documents, trailer rewritten to `EOF|32` |
| `l2025010301id.16` | The 13 link rows for those 11 documents, trailer rewritten to `EOF|13` |
| `m2025010301d.16` | The real document-type lookup file, whole and unchanged |
| `d2025010401id.16` | Corrupted on purpose: the same 11 rows with a trailer that says `EOF|12` |
| `d2025010501id.16` | Corrupted on purpose: the same 11 rows with no trailer (a cut-off download) |

**Broken files, for the repair (ruling R15).** In `rejected/`, mirroring `data/raw/duval/rejected/`. Cut on 2026-11-18 from two of the 13 files that failed verification (downloaded 2026-11-12). They hold document and link rows only, so no party names. Because there is no parties file to say which of these documents belong to a business, every row is treated as a person's and carries invented values.

| Fixture | What it is |
|---|---|
| `rejected/d2026011501id.16` | Cut from lines 102–118 of the real file: 14 mortgage records from 2004. Two are split by a line break inside the legal description, and one of those also has a blank line, so the file has 17 lines above a trailer rewritten to `EOF|14` |
| `rejected/l2026021901id.16` | Cut from lines 2207–2214 of the real file: 7 link rows and the one blank line, trailer rewritten to `EOF|7` |
| `rejected/d2026011601id.16` | Corrupted on purpose: the same 14 records with a trailer that says `EOF|15`. No repair can make it match, so it must stay out |

**Redaction.** No file in git may hold a person's name. Every party name that is not plainly a company is replaced with `REDACTED PERSON`.

**What is invented, and why.** On Nov 19, 2026 Andres decided that hiding the name alone does not hide the person, because anyone can type a real instrument number, a book and page, a case number or a parcel number into the Clerk's public search and read the name there. So every document that has at least one `REDACTED PERSON` party, and every document in `rejected/`, now carries invented values in the Clerk's own shapes:

| Value | Invented range | Example |
|---|---|---|
| Instrument number | The year, then a running number of 900001 or more. The largest real running number in the files on disk is below 900000 | `2024900001` |
| Book | 90001 to 99999. The largest real book on disk is 22125 | `90001` |
| Page | Any number, because a page means nothing without its real book | `101` |
| Linked instrument, linked book and linked page | The same ranges. The one linked instrument in the Clerk's older shape (book digits followed by page digits) keeps that shape | `2018900001`, `90006101` |
| Legal description (the free-text field that holds the lot and block, a parcel number or a case number) | A lot and block in a place whose name contains the word `INVENTED` | `L1 B1 INVENTED ACRES` |

Three things follow from that decision:

- A row about a person holds no case number and no parcel number at all. The Clerk writes them as `Case# ...` and `PIN ...` inside the legal description, and the test `tests/test_fixture_privacy.py` fails if either appears on a person's row, so the invented text leaves them out. A case number stub survives on one business row (`2024283010`), which is enough to show the shape.
- One instrument has one invented number everywhere. `2024900001` is the same document in the `d`, `p` and `l` files, and the link row `-OR 90012/101` in `rejected/l2026021901id.16` still points at the mortgage two rows above it.
- The family-court judgment that was in the first cut (a `JDG` row whose case number held `-DR-`) is gone, with its 2 party rows and its 1 link row. No invented number makes a family-court record a good fixture.

The three documents whose parties are all businesses (`2024282998`, `2024283010`, `2024283155`) keep every real value, and so do the documents they link to. Dates, recording times, amounts, type codes, company names, the pipe layout, the NUL byte in one legal description, the broken lines and the CRLF line endings are as the Clerk sent them.

**Not for display.** The Clerk has not yet said whether terms of use apply to this data. Nothing from Duval is shown outside this repo until Andres says so.
