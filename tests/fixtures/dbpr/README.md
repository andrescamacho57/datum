# DBPR fixtures

Cut from real DBPR files so the tests run offline (CLAUDE.md rule 4).

| Fixture | Origin | Captured (UTC) | What it is |
|---|---|---|---|
| `construction_license_20.csv` | `https://www2.myfloridalicense.com/sto/file_download/extracts//CONSTRUCTIONLICENSE_1.csv` | 2026-11-12T06:49Z | 20 real rows, no header: 12 business (`QB`) rows and 8 contractor rows |
| `construction_license_bad_columns.csv` | same rows | 2026-11-12 | Corrupted on purpose: row 5 has 19 fields instead of 22 |
| `construction_license_truncated.csv` | same rows | 2026-11-12 | Corrupted on purpose: cut off mid-row, no final line break |
| `construction_license_with_header.csv` | same rows | 2026-11-18 | Corrupted on purpose (ruling R25): a header row placed above the 20 real rows. The state's file has never had one; the header's wording is the state's own field names from its "File Layout Information" list (`docs/access/dbpr.md`), so this is what the file would look like if the state started sending one |
| `contractor_disc_lic_19.csv` | `https://www2.myfloridalicense.com/pro/cilb/reports/contractor_disc_lic_2526.csv` | 2026-11-12T06:49Z | The real header row and the first 19 data rows |
| `contractor_disc_lic_bad_header.csv` | same rows | 2026-11-12 | Corrupted on purpose: header column 2 renamed |

**Redaction.** No file in git may hold a person's name. On every row about an individual, the name is replaced with `REDACTED, PERSON` and the street address with `REDACTED`. Everything else (codes, license numbers, dates, city, ZIP, quoting, CRLF line endings, column count) is as the state sent it. Business names are unchanged.
