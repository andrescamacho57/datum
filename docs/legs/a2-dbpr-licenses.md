# Leg A2: DBPR contractor licenses and discipline, raw to staging

Branch `leg/a2-dbpr-licenses` · run 2026-11-12 (UTC) · status: **done, all done-when checks pass. Three things need your decision (section 4)**

DBPR = Florida Department of Business and Professional Regulation.

## 1. What I built

DBPR publishes one CSV of current construction licensees and one CSV per fiscal year of discipline cases against licensed contractors. I checked the site's terms first, then built the path from download to staging.

- **`docs/access/dbpr.md`**: where the files are, both layouts, how often they change, what the state leaves out, and what the terms and robots.txt say. Nothing forbids automated download; the terms are silent on it.
- **`src/datum/dbpr.py`**: a small `DbprFile` class. `download()` makes one HTTPS request and saves the file to `data/raw/dbpr/`. `validate()` runs before anything is loaded and checks the header (when the file has one), the column count on every row, a minimum row count, and that the last line is complete. `python src/datum/dbpr.py download` does both for all six files.
- **`tests/test_dbpr.py`** with fixtures in `tests/fixtures/dbpr/` (cut from the real files, people's names redacted) and **`pytest.ini`** so `pytest` can import `datum`.
- **`snowflake/14_dbpr_raw.sql`**: two CSV file formats (with and without a header row), two stages, and two raw tables in `datum.raw`: `dbpr_licenses` (22 fields) and `dbpr_discipline` (17 fields), one text column per field plus `source_file` and `loaded_at`.
- **`stg_dbpr__licenses`** and **`stg_dbpr__discipline`**: trim, blanks to NULL, text to dates. Licenses get a `record_kind` label from the occupation code. Discipline's combined "date - action" column is split in two.
- **Tests**: `_dbpr__models.yml` (12 column tests) and `pipeline/tests/assert_dbpr_license_key_unique.sql`.

Script number: 14, because leg A1's branch uses 13.

## 2. Checks

**Validation before loading** (`python src/datum/dbpr.py validate`)

```
OK    CONSTRUCTIONLICENSE_1.csv: 263337 lines, 263337 data rows
OK    contractor_disc_lic_2122.csv: 1110 lines, 1109 data rows
OK    contractor_disc_lic_2223.csv: 1535 lines, 1534 data rows
OK    contractor_disc_lic_2324.csv: 1879 lines, 1878 data rows
OK    contractor_disc_lic_2425.csv: 1542 lines, 1541 data rows
OK    contractor_disc_lic_2526.csv: 396 lines, 395 data rows
```

`wc -l data/raw/dbpr/*.csv` gives the same line counts. The license file has no header, so lines = data rows. Each discipline file has one header line.

**Rows in each raw table = data lines in the file** (`snow sql -c datum -f snowflake/14_dbpr_raw.sql`, CHECK)

```
+------------------------------------------------------------+
| RAW_TABLE  | SOURCE_FILE                     | ROWS_LOADED |
|------------+---------------------------------+-------------|
| licenses   | CONSTRUCTIONLICENSE_1.csv.gz    | 263337      |
| discipline | contractor_disc_lic_2122.csv.gz | 1109        |
| discipline | contractor_disc_lic_2223.csv.gz | 1534        |
| discipline | contractor_disc_lic_2324.csv.gz | 1878        |
| discipline | contractor_disc_lic_2425.csv.gz | 1541        |
| discipline | contractor_disc_lic_2526.csv.gz | 395         |
+------------------------------------------------------------+
```

| Table | Data lines in files | Rows loaded |
|---|---|---|
| `dbpr_licenses` | 263,337 | 263,337 |
| `dbpr_discipline` | 6,457 (1,109 + 1,534 + 1,878 + 1,541 + 395) | 6,457 |

**dbt** (`cd pipeline && dbt build --select stg_dbpr__licenses stg_dbpr__discipline`)

```
 Succeeded model DEV_staging.stg_dbpr__discipline (view)
 Succeeded model DEV_staging.stg_dbpr__licenses (view)
    Passed test  not_null_stg_dbpr__licenses_license_number
    Passed test  assert_dbpr_license_key_unique
    Passed test  not_null_stg_dbpr__licenses_occupation_code
    Passed test  accepted_values_stg_dbpr__licenses_occupation_code__CAC__CBC__...__CRS1
    Passed test  not_null_stg_dbpr__licenses_record_kind
    Passed test  not_null_stg_dbpr__licenses_licensee_name
    Passed test  accepted_values_stg_dbpr__licenses_primary_status__C__P__S
    Passed test  accepted_values_stg_dbpr__licenses_secondary_status__A__I
    Passed test  not_null_stg_dbpr__discipline_license_number
    Passed test  not_null_stg_dbpr__discipline_complaint_number
    Passed test  not_null_stg_dbpr__discipline_entered_date
    Passed test  not_null_stg_dbpr__discipline_discipline_date
    Passed test  not_null_stg_dbpr__discipline_fiscal_year_code
Finished 'build' successfully for target 'dev' [4.8s]
Summary: 15 total | 15 success
```

(Lines reordered by model for reading; the long test name is shortened.)

**License number `not_null`, and duplicates**

The `not_null` test passes with one stated exception: it skips `QB` rows. The state's file gives all 128,904 `QB` (business) rows a blank license number. Outside `QB`, 0 of 134,433 are blank.

```
| TOTAL  | NULL_LICENSE_NUMBER | NULL_OUTSIDE_QB |
| 263337 | 128904              | 0               |

| K                                    | DUP_KEYS |
| license_number alone                 | 13001    |
| occupation_code + license_number     | 0        |
| alternate_license_number             | 78       |
| QB whole-row duplicates (extra rows) | 7        |
```

Explained: DBPR numbers each occupation separately, so the same digits recur under different codes (13,001 numbers). The real key, occupation code + license number, has zero duplicates and is tested. The 78 are course codes that collide when printed (`CRS1` + `1130` and `CRS1` + `11130`). The 7 are exact repeated `QB` rows in the state's file.

**Business-held versus individual-held.** The column is `occupation_code` (staging adds `record_kind` from it).

```
| RECORD_KIND        | N      | WITH_LICENSE_NUMBER | WITH_DBA_NAME | ACTIVE | INACTIVE | STATUS_BLANK |
| business           | 128904 | 0                   | 13005         | 9751   | 0        | 119153       |
| contractor_license | 111400 | 111400              | 98948         | 98730  | 12667    | 3            |
| financial_officer  | 19580  | 19580               | 17251         | 3      | 0        | 19577        |
| education          | 3453   | 3453                | 1             | 0      | 0        | 3453         |
```

- **128,904 business records** (`QB`, "Construction Business Information").
- **111,400 individual-held contractor licenses** (25 codes such as `CGC`, `CBC`). 98,948 of them name a company in `dba_name`.
- 19,580 financially responsible officers (individuals) and 3,453 education providers and courses, which are not contractor licenses.

**Discipline**: 6,457 rows, 3,160 complaints, all five files. Every respondent is an individual (0 names not shaped `LAST, FIRST`).

**Offline checks**: `pytest` → `10 passed in 0.04s`. `ruff check src tests` → `All checks passed!`.

## 3. Decisions I made and why

| Decision | Why | Tradeoff |
|---|---|---|
| `not_null` on license number skips `QB` rows | The file has no number for them. Failing the build on the state's design would teach nothing; hiding the rows would lose every business record | The done-when line is met with an exception, stated here and in the test's comment |
| Fixtures are real rows with people's names and street addresses replaced by `REDACTED` | CLAUDE.md wants real responses as fixtures; the brief forbids a person's name in any sample file. Redacting keeps the real structure (quotes, CRLF, column count, codes) | The fixtures are not byte-for-byte the state's rows. `tests/fixtures/dbpr/README.md` says so |
| Two file formats differing in `SKIP_HEADER` | The license file has no header, the discipline files do | One more object than the brief's "a CSV file format" |
| Raw has 22 license columns, including the state's "Blank" field and an undocumented empty last field | Raw is the file as sent. Staging drops the three always-empty columns | Three useless columns in raw |
| HTTPS certificates are checked with `truststore` (the system's trusted list) | This Python build ships without a certificate list, so the first attempt failed verification. `truststore` was already in the venv. Verification stays on | One import a reader has to look up |
| Module is `src/datum/dbpr.py` | The brief says so (the plan's Appendix B says `ingest/dbpr.py`) | Differs from the plan |
| All five discipline years loaded, into one table | The brief's pattern is `[fiscal year]`, and five small files cost little | None found |
| Unlicensed-activity and recovery-fund discipline files not downloaded | Not in the brief | They exist and are listed in the access doc |
| `record_kind` is computed in staging | It is a fixed code-to-label map from the state's code page, guarded by an `accepted_values` test | A new state code fails the build until someone maps it |

Requests made to the state's server: four page fetches for the terms, robots.txt and code list; one round of six download attempts that failed certificate verification before any data moved; then one successful request per file.

## 4. What I couldn't verify, and open questions for Andres

**Stop-and-flag items (your decision, not mine):**

1. **Terms of use are silent.** DBPR's ReadMe says the files are provided "to the public through free download" under Chapter 119. It neither allows nor forbids automated download, redistribution or commercial use, and robots.txt does not block the download folders. I downloaded because nothing forbids it. Whether silence is enough to show this data in a product is yours and counsel's call.
2. **Discipline is about people.** All 6,457 discipline rows name an individual licensee; no business name is in those files. A company's report could only show discipline by going person → license → `dba_name` → company. The brief keeps people's names out of everything past staging, and I'm flagging this, not designing around it. It is license discipline, not credit, but it is still a record about an individual.
3. **`QB` rows are not all companies.** Several hundred `QB` names look like a person (a rough pattern count: 822). Phase B can't treat `QB` as automatically safe.

**Other open questions:**

4. A `QB` business record has no license number, no expiration date and mostly no status. What would the report say about such a business?
5. The discipline files give the license kind in words and the number unpadded; the license file uses a code and 7 digits. Joining them needs a words-to-code map. Build it in Phase B?
6. There is no FY 26/27 discipline file, and the latest discipline date is 2026-07-17. The discipline data may be four months behind.
7. Raw has `loaded_at` but not the moment the file was fetched (they were five minutes apart today). Rule 3 wants a fetch timestamp on every fact. Is `loaded_at` acceptable, or should the fetch time be recorded?
8. The validator does not detect a header row appearing in the license file one day (it would load as one bad data row). Worth adding?

## 5. Credits used

**About 0.110 credits** on `datum_wh` (roughly $0.22), measured as the difference between two readings:

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH'))"
after A1 (22:46 Pacific):  0.063368056
after A2 (22:56 Pacific):  0.173557777
```

The difference includes the idle minutes after A1's last query, before the warehouse suspended, so A2's own share is somewhat less.

## 6. Three questions you should be able to answer

1. Why does `validate()` run before `PUT` and `COPY`, when Snowflake's `ERROR_ON_COLUMN_COUNT_MISMATCH` would also catch a row with the wrong number of fields?
2. `license_number` has 13,001 duplicated values, yet the uniqueness test passes. What is the key, and why isn't the number alone enough?
3. The two file formats in script 14 differ by one line. Which line, and what would the discipline table contain if the license format were used for it by mistake?
