# DBPR fixtures

Cut from real files published by DBPR (Florida's Department of Business and Professional Regulation) so the tests run offline (CLAUDE.md rule 4). On every row about a person, the license number, the complaint number and the business name are invented, and some ordinary values are still real (see "What is invented, and why" and "What is still real on a person's row" below).

| Fixture | Origin | Captured (UTC) | What it is |
|---|---|---|---|
| `construction_license_20.csv` | `https://www2.myfloridalicense.com/sto/file_download/extracts//CONSTRUCTIONLICENSE_1.csv` | 2026-11-12T06:49Z | 20 rows, no header: 12 business (`QB`) rows, which are real, and 8 contractor rows, which carry invented license numbers and invented business names |
| `construction_license_bad_columns.csv` | same rows | 2026-11-12 | Corrupted on purpose: row 5 has 19 fields instead of 22 |
| `construction_license_truncated.csv` | same rows | 2026-11-12 | Corrupted on purpose: cut off mid-row, no final line break |
| `construction_license_with_header.csv` | same rows | 2026-11-18 | Corrupted on purpose (ruling R25): a header row placed above the 20 real rows. The state's file has never had one; the header's wording is the state's own field names from its "File Layout Information" list (`docs/access/dbpr.md`), so this is what the file would look like if the state started sending one |
| `contractor_disc_lic_19.csv` | `https://www2.myfloridalicense.com/pro/cilb/reports/contractor_disc_lic_2526.csv` | 2026-11-12T06:49Z | The real header row and the first 19 data rows. All 19 are about people, so all 19 carry invented license and complaint numbers |
| `contractor_disc_lic_bad_header.csv` | same rows | 2026-11-12 | Corrupted on purpose: header column 2 renamed |

**Redaction.** No file in git may hold a person's name. On every row about an individual, the name is replaced with `REDACTED, PERSON` and the street address with `REDACTED`.

**What is invented, and why.** On Nov 19, 2026 Andres decided that hiding the name alone does not hide the person, because anyone can type a real license number, complaint number or business name into DBPR's public search and read the name there. So every row that holds `REDACTED, PERSON` now carries invented values in the state's own shapes:

| Value | Where | Invented range | Example |
|---|---|---|---|
| License number | Column 13 of the license file, column 2 of the discipline file | 9900001 to 9999999. No license number in the files on disk falls in that range | `9900001` |
| Alternate license number | Column 21 of the license file | The occupation code followed by the invented license number | `CBC9900001` |
| Doing-business-as name (the business a licensed person trades as) | Column 4 of the license file | A name that contains the word `INVENTED` and keeps the legal ending (`INC`, `LLC`) of the real one. One of the real names held a person's first and last name | `INVENTED HOMES INC` |
| Complaint number | Column 11 of the discipline file | The year, then a running number of 900001 or more. The largest real running number on disk is 92099 | `2025900001` |

One real number always becomes the same invented number. In the discipline file three people have more than one row (4, 3 and 10 rows), and each person's rows still share one license number. Each copy of a fixture (the good one and the ones corrupted on purpose) holds the same rows. The test `tests/test_fixture_privacy.py` fails if a person's row holds a number outside these ranges or a business name without the word `INVENTED`.

The 12 business (`QB`) rows have no license number in the state's file and are unchanged. The codes, the quoting, the CRLF line endings and the column count are as the state sent them.

**What is still real on a person's row.** The license type, the city, the state, the ZIP code, the county, every date, and in the discipline file the disposition and the discipline description are as the state sent them. None of them finds a person on its own. Together they might: a nine-digit ZIP code narrows to a street block, and DBPR publishes its final orders by date. 🔴 That is an assumption, and it has not been tried. Whether to invent these values too is an open decision for Andres, raised in the pull request that made this change. `tests/test_fixture_privacy.py` does not check them.
