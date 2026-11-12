# Sunbiz federal tax liens (FLR)

**What it is:** federal liens (almost all IRS tax liens) filed with the Florida Department of State against the personal property of Florida businesses. Fla. Stat. §713.901 sends liens on corporations and partnerships here; liens on real estate and on individuals go to the county clerk instead.

**Access:** public SFTP, `sftp.floridados.gov`, user `Public`, password published by the state on the [Quarterly Data page](https://dos.fl.gov/sunbiz/other-services/data-downloads/quarterly-data). Bulk download is the state's intended channel, so no terms-of-use issue for downloading. Definitions: "Federal Tax Lien File Definitions" (linked from the [Daily Data page](https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/)); raw copy in `docs/access/sunbiz_flr_definitions.txt`. The server also has `doc/quarterly/flr/FLRreadme.txt` (2013), not pulled yet.

| File | Quarterly (full) | Daily |
|---|---|---|
| Filings | `doc/quarterly/flr/flrf.zip` → `FLRF.TXT` | `doc/flr/filings/yyyymmddflrf.txt` |
| Debtors | `doc/quarterly/flr/flrd.zip` → `FLRD.TXT` | `doc/flr/debtors/yyyymmddflrd.txt` |
| Events | `doc/quarterly/flr/flre.zip` → `FLRE.TXT` | `doc/flr/events/yyyymmddflre.txt` |
| Secured parties | `doc/quarterly/flr/flrs.zip` → `FLRS.TXT` | `doc/flr/secured/yyyymmddflrs.txt` |

Daily files exist only on days with activity (not every business day). Older dailies are in year folders (`2011` … `2020`, `Prior to 2011`).

## Record layouts (positions are 1-based, as Snowflake's `SUBSTR(line, start, length)` uses them)

### Filings: 82 characters, one row per lien

| # | Field | Start | Len | Notes |
|---|---|---|---|---|
| 1 | doc_number | 1 | 12 | Lien document number, e.g. `26FLR0004110`. Primary key |
| 2 | filing_date | 13 | 8 | MMDDYYYY |
| 3 | pages | 21 | 5 | |
| 4 | total_pages | 26 | 5 | |
| 5 | filing_status | 31 | 1 | A active, L lapsed, T terminated |
| 6 | filing_type | 32 | 1 | F = federal lien (U = UCC lien, not in this feed) |
| 7 | assessment_date | 33 | 8 | MMDDYYYY, the IRS assessment date |
| 8 | cancellation_date | 41 | 8 | `00000000` when not cancelled |
| 9 | expiration_date | 49 | 8 | MMDDYYYY, about 10 years + 30 days after assessment |
| 10 | transmitting_utility | 57 | 1 | Y/N |
| 11 | event_count | 58 | 5 | |
| 12 | total_debtor_count | 63 | 5 | |
| 13 | total_secured_count | 68 | 5 | |
| 14 | current_debtor_count | 73 | 5 | |
| 15 | current_secured_count | 78 | 5 | |

### Debtors: 206 characters (secured parties use the identical layout)

| # | Field | Start | Len | Notes |
|---|---|---|---|---|
| 1 | filing_type | 1 | 1 | `F` |
| 2 | doc_number | 2 | 12 | Joins to filings.doc_number |
| 3 | name | 14 | 55 | Debtor (or secured party) name |
| 4 | name_format | 69 | 1 | C corporate, P personal |
| 5 | address_1 | 70 | 44 | |
| 6 | address_2 | 114 | 44 | |
| 7 | city | 158 | 28 | |
| 8 | state | 186 | 2 | |
| 9 | zip | 188 | 9 | ZIP+4 without a dash; first 5 = ZIP5 |
| 10 | country | 197 | 2 | |
| 11 | seq | 199 | 5 | Debtor sequence within the filing |
| 12 | relation_to_filing | 204 | 1 | C current |
| 13 | original_party | 205 | 1 | |
| 14 | filing_status | 206 | 1 | A / L / T |

### Events: 135 characters, one row per action on a lien

| # | Field | Start | Len | Notes |
|---|---|---|---|---|
| 1 | key | 1 | 1 | Internal |
| 2 | event_doc_number | 2 | 12 | The event's own document number |
| 3 | filing_doc_number | 14 | 12 | The lien it acts on → filings.doc_number |
| 4 | action_count | 26 | 1 | |
| 5 | event_seq | 27 | 1 | |
| 6 | pages | 28 | 1 | |
| 7 | event_filing_date | 29 | 8 | MMDDYYYY |
| 8 | create_date | 37 | 8 | MMDDYYYY |
| 9–10 | internal keys | 45 | 2 | |
| 11 | action_event_number | 47 | 12 | |
| 12 | action_seq | 59 | 1 | |
| 13 | action_code | 60 | 3 | `COR` release, `COD` discharge, `AGI` amendment, `RNC`/`RNL` refiling… |
| 14 | action_text | 63 | 70 | e.g. `CERTIFICATE OF RELEASE` |
| 15–17 | name seq / type | 133 | 3 | Name type D debtor, S secured party |

## Verified by manual pull (Nov 5, 2026)

Quarterly snapshot dated **2026-10-03** (`unzip -l`); daily files pulled for **2026-11-04**.

| File | Bytes | Lines | Bytes ÷ lines |
|---|---|---|---|
| FLRF.TXT | 1,717,296 | 20,444 | 84 = 82 + CRLF ✅ |
| FLRD.TXT | 4,611,984 | 22,173 | 208 = 206 + CRLF ✅ |
| FLRE.TXT | 13,324,072 | 97,256 | 137 = 135 + CRLF ✅ |
| FLRS.TXT | 4,253,184 | 20,448 | 208 = 206 + CRLF ✅ |
| 20261104 dailies | | 42 / 46 / 29 / 42 | 82 / 206 / 135 / 206 + LF ✅ |

Quarterly files end lines with `\r\n` (CRLF), daily files with `\n` (LF), same as the corporate files. Every line in every file is exactly the documented length.

**Findings**
1. **The quarterly filings file holds only active liens:** all 20,444 rows have status `A`. Released and lapsed liens are dropped from the snapshot, so "is there an active federal lien?" is answered by presence in the latest snapshot. No window function needed for MVP.
2. **Releases arrive through the daily events file.** All 29 events on Nov 4 were `COR` (certificate of release), and all 29 point at liens in the Oct 3 active snapshot. So between snapshots: active = snapshot + daily new filings − daily releases/discharges. The quarterly events file is mostly history (95,310 releases, only 2 on still-active liens).
3. **Debtors are businesses:** 22,171 of 22,173 have name_format `C`; the 2 `P` rows are junk names. 22,068 are in Florida. LLCs do land here: about 6,400 debtor names contain LLC (open question closed ✅).
4. **No Sunbiz document number, no FEIN, no dollar amount** in any of the four files. Linking a lien to a company must use **name + address (ZIP5)**, which is exactly decision d19's CONFIRMED rule. The report can't show an amount.
5. Secured party is `IRS JACKSONVILLE` on 20,385 of 20,448 rows; the rest are pension plans and the Alcohol and Tobacco Tax and Trade Bureau.
6. 18,837 liens have 1 debtor, 1,595 have 2; one outlier has 111.
7. **Data quality:** 28 active liens (from 2008–2012 filings) have impossible expiration years (2510, 9211…) and a few assessment years look mistyped (8200, 9201). Dates still parse as MMDDYYYY, so staging should test for a sane year range (`warn`, not `error`).
8. Filing years in the active snapshot: mostly 2017–2026, a long tail back to 2007 (refiled liens).

## Verified after loading (Nov 12, 2026, leg A1)

Loaded by `snowflake/13_federal_liens_raw.sql`; all eight per-file row counts and line lengths match the table above.

9. **The status on a debtor or secured-party row is not reliable.** All 20,486 filings rows (snapshot + daily) say `A`, but 5 debtor rows and 4 secured-party rows on those same liens say `T`, `L` or `C`. Read a lien's status from the filings file only.
10. **Undocumented status `C`:** one debtor row and one secured-party row in the snapshot hold `C` at position 206. The layout lists only A / L / T. Meaning unknown; not guessed. The staging test on that column is `warn`.
11. **One active lien has a cancellation date** (the other 20,485 hold `00000000`). What a cancellation date on an active lien means is open.
12. Staging keeps 22,171 of 22,173 snapshot debtors (2 personal-format rows stay in raw) and all 46 daily debtors.

## Implications for the build
- Raw: one table per file kind (decision d9), loaded with the existing `fixed_width` format.
- Staging: cut by the positions above; parse dates with `TRY_TO_DATE(x, 'MMDDYYYY')`; keep only debtors with name_format `C` (Datum is businesses only).
- Intermediate: debtor → company link on normalized name + ZIP5 (CONFIRMED / AMBIGUOUS / NO_MATCH); apply daily releases (`COR`, `COD`) on top of the snapshot.
- Report flag text: "Active federal tax lien, filed MM/DD/YYYY, secured party IRS" with no amount, linked to the Sunbiz lien record.

## Open questions
- What is in `FLRreadme.txt` (2013)?
- Does a `COD` (certificate of discharge) fully clear a lien, or only release specific property? Treat as "discharge filed" text, not as cleared, until confirmed.
- Exact per-record Sunbiz URL for a lien, for the citation link.
