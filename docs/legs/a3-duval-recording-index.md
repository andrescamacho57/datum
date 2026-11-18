# Leg A3: Duval County recorded documents, raw to staging

Branch `leg/a3-duval-recording-index` · run 2026-11-12 (UTC) · status: **done with exceptions. 2,703 of 2,716 files loaded and every loaded file matches its EOF count. 13 files failed verification and were not loaded (section 2). Four things need your decision (section 4)**

## 1. What I built

The Duval County Clerk publishes, for every day, four pipe-delimited text files indexing the documents recorded in the county: the documents, the parties named on them, links from a document to an earlier one (a release pointing at its lien), and a lookup of document types. I worked out how to connect, downloaded everything dated 2025-01-01 onward, checked each file against the row count the Clerk writes on its last line, and loaded what passed.

- **`docs/access/duval-recording-index.md`**: protocol, file kinds, layouts, counts, the 13 mismatches and their cause.
- **`src/datum/duval.py`**: opens one SFTP connection, downloads files one at a time with a half-second pause to `data/raw/duval/`, then verifies every file's row count against its `EOF|<count>` trailer. A file that fails is reported and moved to `data/raw/duval/rejected/`, so the upload can't pick it up. The login comes from the secrets file through `load_dotenv()` and is never printed.
- **`tests/test_duval.py`** with fixtures in `tests/fixtures/duval/` (cut from real files, people's names redacted) and **`pytest.ini`** (same file as leg A2 adds).
- **`snowflake/15_duval_recording_index_raw.sql`**: a pipe-delimited file format, four stages and four raw tables in `datum.raw` (`duval_documents`, `duval_parties`, `duval_links`, `duval_doc_types`), one text column per field plus `source_file` and `loaded_at`.
- **`stg_duval__documents`, `stg_duval__parties`, `stg_duval__links`, `stg_duval__doc_types`**: drop the trailer rows, trim, type the dates and numbers, and take `file_date` from the file name.
- **Tests** in `_duval__models.yml`: `not_null` on instrument numbers and the recording date; `relationships` from parties and links to documents at `warn` severity.

Script number: 15, because legs A1 and A2 use 13 and 14.

## 2. Checks

**Protocol.** SFTP, found on the second of two allowed attempts. FTPS was not tried.

| Attempt | Result |
|---|---|
| SFTP, `paramiko` 5.1 | Failed in key exchange: `Incompatible ssh peer (no acceptable host key)`. The server offers only an old key type (ssh-dss) |
| SFTP, `paramiko` 3.5.1 | Connected and logged in |

**Download** (`python src/datum/duval.py download`)

```
downloaded 2716 files, skipped 0 already on disk
```

679 files of each kind, 2025-01-01 through 2026-11-11, 213 MB, 38 minutes over one connection.

**Verification before loading** (`python src/datum/duval.py verify`, first run)

```
FAIL  d2025090201id.16: 462 rows in the file, but the trailer says EOF|460
FAIL  d2025090301id.16: 1370 rows in the file, but the trailer says EOF|1369
FAIL  d2026010901id.16: 1174 rows in the file, but the trailer says EOF|1172
FAIL  d2026011501id.16: 523 rows in the file, but the trailer says EOF|520
FAIL  d2026021901id.16: 2494 rows in the file, but the trailer says EOF|2492
FAIL  l2026021901id.16: 2564 rows in the file, but the trailer says EOF|2563
FAIL  d2026022501id.16: 2669 rows in the file, but the trailer says EOF|2668
FAIL  d2026031401id.16: 254 rows in the file, but the trailer says EOF|253
FAIL  d2026040801id.16: 3208 rows in the file, but the trailer says EOF|3206
FAIL  d2026061101id.16: 1344 rows in the file, but the trailer says EOF|1343
FAIL  d2026072801id.16: 1372 rows in the file, but the trailer says EOF|1371
FAIL  d2026081201id.16: 1668 rows in the file, but the trailer says EOF|1665
FAIL  d2026101601id.16: 1868 rows in the file, but the trailer says EOF|1867
OK    documents: 667 files, 753259 rows, every file matches its EOF count
OK    parties: 679 files, 2050173 rows, every file matches its EOF count
OK    links: 678 files, 788122 rows, every file matches its EOF count
OK    doc_types: 679 files, 57715 rows, every file matches its EOF count
13 file(s) failed verification now; 0 more already in rejected/
```

**The 13 mismatches, explained.** In the 12 documents files, a legal description contains a line break, so one record is spread over two or three lines. Counting lines that begin `DDA|` gives exactly the EOF count in all 12: the Clerk's counts are right and no record is missing. The links file has one blank line. I did not repair them, because the brief says a mismatch fails the file. Not loaded: 18,386 document records (2.4% of 771,645) and 2,563 link rows.

**For every loaded file: rows loaded = its EOF count** (`snow sql -c datum -f snowflake/15_duval_recording_index_raw.sql`, CHECK)

```
+---------------------------------------------------------------------------------------------------------+
| RAW_TABLE | FILES_LOADED | DATA_ROWS | SUM_OF_EOF_COUNTS | FILES_MISMATCHED | FILES_WITHOUT_ONE_TRAILER |
|-----------+--------------+-----------+-------------------+------------------+---------------------------|
| doc_types | 679          | 57715     | 57715             | 0                | 0                         |
| documents | 667          | 753259    | 753259            | 0                | 0                         |
| links     | 678          | 788122    | 788122            | 0                | 0                         |
| parties   | 679          | 2050173   | 2050173           | 0                | 0                         |
+---------------------------------------------------------------------------------------------------------+
```

2,703 files, 3,649,269 data rows, 0 mismatches among loaded files. The Snowflake numbers equal the Python numbers above.

**dbt** (`cd pipeline && dbt build --select stg_duval__documents stg_duval__parties stg_duval__links stg_duval__doc_types`)

```
 Succeeded model DEV_staging.stg_duval__parties (view)
 Succeeded model DEV_staging.stg_duval__links (view)
 Succeeded model DEV_staging.stg_duval__documents (view)
 Succeeded model DEV_staging.stg_duval__doc_types (view)
    Passed test  not_null_stg_duval__links_instrument_number
    Passed test  not_null_stg_duval__parties_instrument_number
    Passed test  not_null_stg_duval__documents_doc_type_code
    Passed test  accepted_values_stg_duval__parties_party_role__FRM__TO
    Warned test  relationships_stg_duval__parties_instrument_number__instrument_number__ref_stg_duval__documents_
    Passed test  not_null_stg_duval__documents_recorded_date
    Passed test  not_null_stg_duval__documents_instrument_number
    Passed test  not_null_stg_duval__doc_types_doc_type_code
    Passed test  not_null_stg_duval__documents_file_date
    Warned test  relationships_stg_duval__links_instrument_number__instrument_number__ref_stg_duval__documents_
Finished 'build' with 2 warnings for target 'dev' [5.2s]
Summary: 14 total | 12 success | 2 warn
```

The two warnings are party and link rows whose document is not loaded:

```
| T       | ROW_COUNT | ORPHAN_ROWS | ORPHAN_INSTRUMENTS | ORPHANS_ON_REJECTED_DAYS |
| parties | 2050173   | 45173       | 16419              | 45173                    |
| links   | 788122    | 14464       | 14181              | 14464                    |
```

Every orphan is from one of the 12 days whose documents file was rejected. Outside those days there are none, so re-indexing did not produce a single orphan in this period.

**Document counts by type family** (distinct documents; the family is the Clerk's own lookup)

| Group | Documents | Codes in the group |
|---|---|---|
| Liens (family LN) | 50,332 | `LN` 47,358 · `WRT` warrant 2,687 · `WRTNF` 275 · `JVRL` juvenile restitution lien 12 |
| Judgments (families JUD, CCJ) | 131,594 | `JDG` 72,828 · `JDGS` judgment/sentence 41,654 · `CCCJUDG` 11,305 · `JDGR` restitution 2,833 · `DVJ` domestic violence 2,166 · `FJPD` 438 · `DVJMV` 365 · `RPOFJ` 5 |
| Releases (families REL, PR) | 23,978 | `RELEASE` 21,418 · `PTL REL` partial 2,435 · `CAN` 80 · `WDL` 45 |
| Satisfactions (family SAT) | 48,477 | `SAT` 48,290 · `SATNF` 187 |
| Notices of commencement (family NOC) | 63,752 | `N/C` |
| Lis pendens (family LP) | 5,495 | `LP` |

**Share of party names that look like businesses** (counts only, rough patterns, 2,050,173 party rows)

| Name contains | Rows | Share |
|---|---|---|
| A legal-entity word (LLC, INC, CORP, CO, COMPANY, LTD, LP, LLP, PLLC, PA, PC and similar) | 525,989 | 25.7% |
| No such word, but an organisation word (BANK, ASSOCIATION, MORTGAGE, TRUST, CITY OF, COUNTY…) | 329,610 | 16.1% |
| Neither: mostly individuals | 1,194,573 | 58.3% |

So roughly 4 in 10 party rows look like a business or organisation and 6 in 10 like an individual. Short words such as `CO` and `PA` can match inside a person's name, so this is an estimate of size, not a classifier.

**Offline checks**: `pytest` → `12 passed in 0.11s`. `ruff check src tests` → `All checks passed!`. `dbt parse` offline → success.

## 3. Decisions I made and why

| Decision | Why | Tradeoff |
|---|---|---|
| The 13 mismatched files are quarantined, not repaired | The brief: "A mismatch fails that file loudly." The cause is understood and a repair is simple, but joining lines means editing the Clerk's file, and that is your call | 12 days of documents (2.4%) are missing, and their parties and links show as orphans |
| Failing files are moved to `rejected/` | The upload is `PUT d*.16`; moving is the simplest way to make sure a bad file can't be included. The download skips a file already in `rejected/` at the same size | A repaired or re-issued file has to be moved back by hand |
| The EOF trailer row is loaded into raw | It lets Snowflake compare each file's rows with the Clerk's own count, and raw stays the file as sent | One non-data row per file; staging filters it |
| `paramiko` pinned below version 4 | The Clerk's server only offers an ssh-dss host key, which newer versions refuse | An old library version, and a weak key type on the server's side |
| The server's key is trusted on first contact, then pinned in `data/duval_known_hosts` | There was no known key to compare with. After the first contact a changed key is refused | The first contact itself was not verified. Fingerprint is in the access doc for you to confirm |
| Latin-1 encoding and no column-count check in the file format | Any byte loads; rows really do differ in length (trailing pipes, the trailer, short lookup rows) | The loader won't catch a shifted row; the Python check and staging tests do |
| All parties are kept in staging | The brief asks for a business share over all party names and allows individuals in staging. Decision d21 says "staging keeps only parties that match a company"; the brief is newer, so I followed it | See open question 4 |
| The doc-type lookup is loaded for every day | Same pattern as the other three kinds, and it shows the lookup never changed | 57,715 rows for 85 codes; take the latest `file_date` when one row per code is wanted |
| Built in a git worktree at `data/wt-a3` | The main folder held uncommitted edits to `docs/decisions.json` (not mine) that blocked switching branches. I left them alone | The data was downloaded into the worktree and moved to `data/raw/duval/` afterwards |

## 4. What I couldn't verify, and open questions for Andres

**Flagged, not resolved:**

1. **Terms of use.** The Clerk has not yet answered whether terms of use apply to this data. Nothing from Duval is shown to anyone outside this repo until you say so. The data is in Snowflake raw and staging, and redacted fixtures are in git.
2. **Criminal and personal records are in the families the brief names.** The Clerk's judgment family includes judgment/sentence (41,654), restitution, domestic violence and public defender judgments; the lien family includes warrants and juvenile restitution liens. The index also holds marriage licenses (with phone numbers in the description), death certificates and military discharges. All of it is in raw and staging, as the brief allows. Phase B needs an explicit list of codes to exclude; choosing it is yours.
3. **May the 12 documents files be repaired?** Joining the broken lines in a copy would recover 18,386 documents and remove every orphan.
4. **d21 versus the brief** on whether individuals' party rows belong in staging. I followed the brief.

**Other open questions:**

5. Is the server's ssh-dss fingerprint (in the access doc) the Clerk's? Worth one email to their IT contact.
6. `paramiko` is now 3.5.1 in the venv, and the repo has no requirements file to record it. Add one?
7. 10,674 links give only the earlier document's book and page, with no instrument number. Phase B's "is this lien released" has to follow book and page too.
8. `FRM` and `TO`: which side is the debtor on a lien, a judgment, a release? Not assumed anywhere in this leg.
9. There is no per-record URL for a citation, only the instrument number.
10. Three files start with a byte-order mark, one party name contains a pipe (cut short), and 206 documents use a type code missing from the lookup. Noted in the access doc; none is handled specially.
11. The oldest record date is 1775-01-01, presumably a placeholder.

## 5. Credits used

**About 0.088 credits** on `datum_wh` (roughly $0.18).

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH'))"
| 2026-11-11 21:55:20-08:00 | 2026-11-11 22:55:20-08:00 | 0.177138055  |   legs A1 and A2
| 2026-11-11 22:55:20-08:00 | 2026-11-11 23:55:20-08:00 | 0.041979167  |   after A2's last query (idle before suspend, or other use; I ran nothing then)
| 2026-11-12 04:55:20-08:00 | 2026-11-12 05:55:20-08:00 | 0.088472222  |   leg A3
```

Phase A total across the three rows: about 0.31 credits. Measured at this leg's last query; the idle minutes before auto-suspend may add a little.

## 6. Three questions you should be able to answer

1. Twelve documents files have more lines than their trailer says, yet no record is missing. What is in those files that makes "count the lines" the wrong way to count records, and what would Snowflake have done with those lines if the files had been loaded?
2. Why is the `EOF` trailer row loaded into the raw tables instead of being stripped before upload, and where does it get removed?
3. The `relationships` tests are `warn`, and they found 45,173 party rows without a document. What did the brief expect to cause orphans, and what actually caused every one of them?
