# DBPR construction licenses and discipline

**What it is:** the Florida Department of Business and Professional Regulation (DBPR) licenses contractors through its Construction Industry Licensing Board (CILB). It publishes free CSV files of current construction licensees and of discipline cases against licensed contractors.

**Investigated:** 2026-11-12, 06:47–06:52 UTC (leg A2). Every figure below was measured on the files downloaded at 2026-11-12T06:49Z.

**Verdict:** usable. Free, no login, published by the state for download under the public records law. The terms say nothing about automated download or commercial use, in either direction (see "Terms").

## Where the files are

Download page: <https://www2.myfloridalicense.com/construction-industry/public-records/>

| File | URL | Loaded? |
|---|---|---|
| Construction licensees | `https://www2.myfloridalicense.com/sto/file_download/extracts//CONSTRUCTIONLICENSE_1.csv` (the double slash is in the state's link) | Yes |
| Licensed contractor discipline, one file per fiscal year | `https://www2.myfloridalicense.com/pro/cilb/reports/contractor_disc_lic_<yyzz>.csv` for `2122`, `2223`, `2324`, `2425`, `2526` | Yes, all five |
| Unlicensed activity (ULA) discipline | `…/pro/cilb/reports/contractor_disc_ula_<yyzz>.csv` | No: not requested, not downloaded |
| Recovery fund discipline | `…/pro/cilb/reports/contractor_disc_rf_<yyzz>.csv` | No: not requested, not downloaded |
| Applicants, continuing education, pool examiners | `…/sto/file_download/extracts/constr_app.csv`, `cilb_certified.csv`, `cilb_registered.csv`, `swimpool_exam.csv` | No: out of scope |

The starting points in the brief were both correct. A fiscal year runs July to June: `2526` holds complaints entered from 2025-07-01.

## Terms, robots and rate limits

**ReadMe/Disclaimer** (<https://www2.myfloridalicense.com/public-records-read-medisclaimer/>, fetched 2026-11-12T06:47Z), quoted:

> "Under Chapter 119, Florida Statutes, the Department of Business and Professional Regulation (DBPR) is required to make available for inspection and copying any public record regardless of physical format, which is not otherwise exempted from public access by general law. To fulfill this obligation, the DBPR provides copies of electronic records to the public through free download."

> "Although data is refreshed weekly, system maintenance may delay the updating of files. To determine the timeliness of the data, please refer to the date posted. For up-to-the-minute license verification, please call our Customer Contact Center at 850.487.1395 or access the DBPR's license search feature at https://www.myfloridalicense.com/portalsearches/VerifyLicensee."

> "DBPR does not offer technical support during or after the download process."

- The page has **no clause on automated download, redistribution or commercial use**, allowing or forbidding. The site's general Disclaimer page (<https://www2.myfloridalicense.com/disclaimer/>) has no such clause either; it covers email addresses as public records.
- **robots.txt** (<https://www2.myfloridalicense.com/robots.txt>, fetched 2026-11-12T06:47Z) disallows only `/wp-admin/`, `/wp-includes/`, `/wp-content/`, `/xmlrpc.php` and `/author/*`. The download folders `/sto/` and `/pro/` are not disallowed. No `Crawl-delay`.
- **No published rate limit.** `src/datum/dbpr.py` makes one request per file, in sequence, with a 2-second pause and no retry, and sends a User-Agent with a contact address. A weekly refresh is six requests.

Nothing forbids the download, so the leg went ahead. Whether silence is enough for showing this data in a paid product is a question for Andres and counsel, not answered here.

## Update cadence

- Licensee file: "refreshed weekly" (ReadMe). The download page's "Date" column was blank on 2026-11-12, so the file's own date can't be read from the page.
- Discipline files: cadence not stated. The newest file is FY 25/26; **there is no FY 26/27 file** although that fiscal year began 2026-07-01, and the latest discipline date in any file is 2026-07-17. The discipline data may be about four months behind. Could not determine more.

## What is excluded

Quoted from the download page, under "Licensee Files":

> "Active, inactive and voluntarily inactive licensees. NULL & VOID, delinquent and involuntarily inactive records are not included in this download."

Confirmed in the data as far as it can be: the only secondary statuses present are `A` (active), `I` (inactive) and blank. So "not found in this file" does not mean "never licensed".

## Layout: licensee file

`CONSTRUCTIONLICENSE_1.csv`: 47,023,105 bytes, **263,337 lines, no header row**, every field in double quotes, comma-delimited, CRLF line endings, valid UTF-8 (43 rows have accented letters). Every row has **22 fields**: the 21 the state documents plus one empty field at the end.

| # | State's name | Raw column | Notes |
|---|---|---|---|
| 1 | Board Number | `board_number` | Always `06` (CILB) |
| 2 | Occupation Code | `occupation_code` | Kind of record. See the table below |
| 3 | Licensee Name | `licensee_name` | A person, `LAST, FIRST`, on license rows; a business on most `QB` rows |
| 4 | Doing Business as Name | `dba_name` | Usually the contractor's company. Filled on 98,948 of 111,400 contractor licenses |
| 5 | Class Code | `class_code` | Mostly blank |
| 6–8 | Address Line 1–3 | `address_line_1..3` | Mailing address |
| 9–11 | City, State, Zip | `city`, `state`, `zip` | ZIP is 5 digits, or ZIP+4 with a dash; 15 rows have 9 digits, 12 have a trailing space |
| 12 | County Code | `county_code` | DBPR's own number, not FIPS |
| 13 | License Number | `license_number` | Digits, zero-padded. **Blank on every `QB` row** |
| 14 | Primary Status | `primary_status` | `C` current 262,915 · `S` suspended 227 · `P` probation 195 |
| 15 | Secondary Status | `secondary_status` | `A` active, `I` inactive, or blank |
| 16 | Original Licensure Date | `original_licensure_date` | MM/DD/YYYY; blank on 859 rows |
| 17 | Effective Date | `effective_date` | MM/DD/YYYY; blank on 19 rows |
| 18 | Expiration Date | `expiration_date` | MM/DD/YYYY; blank on all `QB` rows |
| 19 | Blank | `blank_field` | Always empty |
| 20 | Renewal Period | `renewal_period` | Always empty |
| 21 | Alternate Lic# | `alternate_license_number` | As printed on a license, e.g. `CBC006231`. Blank on `QB` rows |
| 22 | (not documented) | `trailing_field` | Always empty |

### Which column tells business records from individual-held licenses: `occupation_code`

Code meanings are from DBPR's [Understanding DBPR Codes](https://www2.myfloridalicense.com/about-us/understanding-dbpr-codes/) page (fetched 2026-11-12T06:51Z).

| Kind (staging `record_kind`) | Codes | Rows | Who the name is |
|---|---|---|---|
| `business` | `QB` "Construction Business Information" | 128,904 | A business, with exceptions noted below |
| `contractor_license` | 25 codes: `CGC`, `CBC`, `CCC`, `CAC`, `CFC`, `CRC`, `CPC`, `SCC`, `CUC`, `CMC`, `CVC`, `CSC`, `PCC` (certified) and `RR`, `RF`, `RC`, `RP`, `RG`, `RB`, `RA`, `RX`, `RM`, `RU`, `RQ`, `RS` (registered) | 111,400 | An individual. Their company is in `dba_name` |
| `financial_officer` | `FRO` "Financial Responsible Officer" | 19,580 | An individual |
| `education` | `PVDR` course provider, `CRS1` CILB course | 3,453 | Not licenses |

So the file holds **128,904 business records and 111,400 individual-held contractor licenses** (98,730 active, 12,667 inactive, 3 blank).

Two cautions:
1. **A `QB` row has no license number, no expiration date and usually no status** (119,153 of 128,904 blank; 9,751 `A`). The file gives no way to tie a `QB` business to the contractor who qualifies it, other than name and address.
2. **Not every `QB` name is a company.** About 37,800 `QB` names contain a comma; nearly all are companies written like `NAME, INC`, but several hundred look like a person's name (a sole proprietor). A rough pattern count gives 822. Phase B must not treat `QB` as "safe to show".

### Duplicates

| Key | Duplicate keys | Explanation |
|---|---|---|
| `license_number` alone | 13,001 | DBPR numbers each occupation separately, so the same digits recur under different codes |
| `occupation_code` + `license_number` | **0** | This is the key (tested) |
| `alternate_license_number` | 78 | Course codes: `CRS1` + `1130` and `CRS1` + `11130` both print as `CRS11130` |
| Whole row, `QB` only | 7 extra rows | Exact repeats in the state's file |

## Layout: discipline files

`contractor_disc_lic_<yyzz>.csv`: **one header row**, 17 fields, every field quoted, CRLF, plain ASCII.

Header, verbatim: `License Type, License Nbr, Respondent Name, Address Line 1, Address Line 2, Address Line 3, City, State, ZIP Code, County, Complaint Nbr, Classification, Entered Date, Disposition, Disposition Date, Discipline Date - Description, Violation Code`

| File | File lines | Data rows | Complaints | Licenses |
|---|---|---|---|---|
| `…_2122.csv` | 1,110 | 1,109 | 620 | 246 |
| `…_2223.csv` | 1,535 | 1,534 | 744 | 339 |
| `…_2324.csv` | 1,879 | 1,878 | 846 | 396 |
| `…_2425.csv` | 1,542 | 1,541 | 760 | 315 |
| `…_2526.csv` | 396 | 395 | 190 | 124 |
| Total | 6,462 | 6,457 | 3,160 | |

- **One row per discipline line per complaint.** A complaint ending in a fine, costs and education is three rows. No exact duplicate rows.
- **Every respondent is an individual** (all 6,457 names are `LAST, FIRST`). There is no business name in these files.
- `License Nbr` is **not zero-padded** (`27000`) and the license kind is in **words** (`Certified Building Contractor`), while the licensee file pads to 7 digits (`0027000`) and uses a code (`CBC`). Joining the two needs a words-to-code map and padding. Not built in this leg.
- `Discipline Date - Description` is one field, `MM/DD/YYYY - text`. Staging splits it.
- `Address Line 1` is the literal `Private Address` on 57 rows.
- Dispositions seen: Final Order (most), Citation filed, Violation found - corrected, Dismissed, Mandate, Final Order of Local Discipline, a few others, and blank.

## Open questions

- Do the terms need to say more before this data appears in a product shown to contractors? (Silent today.)
- Discipline is against the individual license holder. Showing it on a company's report means going person → license → `dba_name` → company. Is that a link Datum wants to make, given "businesses only"?
- How does a `QB` business record tie to its qualifying contractor? Not in the file.
- Is the discipline data current, with no FY 26/27 file?
- The download page offers no file date, so "data as of" can only be our fetch time.
