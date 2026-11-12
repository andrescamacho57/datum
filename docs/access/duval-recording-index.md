# Duval County Clerk: bulk recording index

**What it is:** the Clerk's index of every document recorded in Duval County's Official Records (deeds, mortgages, liens, judgments, releases, notices of commencement and much else), published as daily text files on the Clerk's file server. Offered to Datum at no cost by the Clerk's office on 2026-11-04 (decision d21).

**Investigated:** 2026-11-12, 13:09–13:49 UTC (leg A3). Every figure below was measured on the files downloaded then.

**Terms of use: not yet answered.** Andres asked the Clerk on 2026-11-05 whether terms of use apply to this data. No answer is recorded. Until Andres says otherwise, **nothing from this source is shown to anyone outside this repo.** This document does not settle that question.

**Personal records.** This is not a business dataset. It indexes marriage licenses, death certificates, domestic violence judgments, criminal judgments and sentences, and military discharges alongside liens and deeds, and most party names are individuals. Under the project's rules these rows may sit in raw and staging and go no further.

## Access

| | |
|---|---|
| Host | `ftp.duvalclerk.com`, port 22 |
| Protocol | **SFTP** (file transfer over SSH). FTPS was not tried, because SFTP worked |
| Login | Account issued by the Clerk; `DUVAL_FTP_USER` and `DUVAL_FTP_PASSWORD` in the secrets file, read by `src/datum/duval.py` and never printed |
| Folder | `/Recording Indexes` (the leading slash is required; without it the server answers "No such file") |
| Server identity | The server offers only an **ssh-dss** host key, an old key type. Fingerprint (MD5) `89:6f:d1:f3:94:05:e1:09:77:d0:ae:ba:70:39:9d:4c`. Trusted on first contact and pinned in `data/duval_known_hosts`; later connections refuse a different key |
| Client | `paramiko` 3.5.x. Version 4 and later dropped ssh-dss and fail with "no acceptable host key" |

**How the protocol was worked out** (the brief allowed two attempts per protocol):
1. SFTP with `paramiko` 5.1: failed during key exchange, "no acceptable host key". The server speaks SSH but only with ssh-dss.
2. SFTP with `paramiko` 3.5.1: connected and logged in. Listing `Recording Indexes` without the leading slash failed.

Three more connections followed: one to list the top folder, one to list `/Recording Indexes`, and one for the download itself. Five connections in total.

**Download behaviour:** one connection, one file at a time, 0.5-second pause between files, no retry. 2,716 files (213 MB) took 38 minutes. A file already on disk at the same size is not requested again.

## What is in the folder

10,617 entries on 2026-11-12, no sub-folders. About 2,650 of each of the four kinds, which fits one set per day since mid-2019 (the brief says 2019-07-31; the first date was not checked). Also present and ignored: `Thumbs.db` and 11 files whose names end `.16c` or `.16d`.

**In scope (dated 2025-01-01 onward):** 2,716 files, 679 of each kind, 2025-01-01 through 2026-11-11. There is a file for every calendar day; on 122 days the documents, parties and links files are the 7-byte `EOF|0` (nothing recorded).

## File kinds and layouts

All four: pipe-delimited text, CRLF line endings, no header, no quoting, last line `EOF|<record count>`.

### `dYYYYMMDD01id.16`: documents

`DDA|16|instrument|type code|type name|legal description|OR|book|page||pages|record date|time|amount|`

| # | Field | Notes |
|---|---|---|
| 1 | Record type | `DDA` |
| 2 | County | `16` = Duval |
| 3 | Instrument number | Year recorded + running number, e.g. `2025000582` |
| 4 | Document type code | 73 codes seen, e.g. `LN`, `N/C`, `JDG`, `RELEASE` |
| 5 | Document type name | The code in words |
| 6 | Legal description | Free text: parcel and lot, a case number, sometimes a phone number |
| 7–9 | Book type, book, page | `OR` = Official Records |
| 10 | (empty) | Always empty; meaning unknown |
| 11 | Page count | |
| 12 | Record date | MM/DD/YYYY |
| 13 | Record time | Digits without a leading zero: `113841` = 11:38:41 |
| 14 | Amount | Dollars; `0.00` when none. Above zero on 181,350 of 753,259 loaded rows |

Each row ends with a pipe, so a split gives a 15th, empty field.

### `pYYYYMMDD01id.16`: parties

`DPA|16|instrument|seq|FRM or TO|name|` : one row per party per document. `FRM` and `TO` are the two sides of the document; which side is the debtor depends on the document type and is not decided here.

### `lYYYYMMDD01id.16`: links

`instrument|book|page|OR|type|linked instrument|linked book|linked page|OR|linked type` : one row per document. When the document refers to no earlier one, the linked fields are empty and the last field is the word `NONE`. No trailing pipe.

Of 788,122 loaded link rows, 161,890 point at an earlier document. On 10,674 of those the linked instrument number is empty and only the linked book and page are given, so a link sometimes has to be followed by book and page.

### `mYYYYMMDD01d.16`: document-type lookup

`code|family|` : 85 codes in 37 families, repeated unchanged in every day's file. Eight codes have no family.

## Families asked for in the brief

Distinct documents among those loaded (2025-01-01 onward, 12 days missing, see "Mismatches"). The family comes from the Clerk's lookup.

| Group | Family | Code | Name | Documents |
|---|---|---|---|---|
| Liens | LN | `LN` | Lien | 47,358 |
| | LN | `WRT` | Warrant | 2,687 |
| | LN | `WRTNF` | Warrant no fee | 275 |
| | LN | `JVRL` | Juvenile restitution lien | 12 |
| Judgments | JUD | `JDG` | Judgment | 72,828 |
| | JUD | `JDGS` | Judgment/sentence | 41,654 |
| | JUD | `JDGR` | Judgment/restitution | 2,833 |
| | JUD | `DVJ` | Domestic violence judgment | 2,166 |
| | JUD | `FJPD` | Final judgment public defender | 438 |
| | JUD | `DVJMV` | Domestic violence judgment (minor victim) | 365 |
| | JUD | `RPOFJ` | RPO final judgment | 5 |
| | CCJ | `CCCJUDG` | CC court judgment | 11,305 |
| Releases | REL | `RELEASE` | Release | 21,418 |
| | REL | `CAN` | Cancellation | 80 |
| | REL | `WDL` | Withdrawal | 45 |
| | PR | `PTL REL` | Partial release | 2,435 |
| Satisfactions | SAT | `SAT` | Satisfaction | 48,290 |
| | SAT | `SATNF` | Satisfaction no fee | 187 |
| Notices of commencement | NOC | `N/C` | Notice commencement | 63,752 |
| Lis pendens | LP | `LP` | Lis pendens | 5,495 |

Totals: liens 50,332 · judgments 131,594 · releases 23,978 · satisfactions 48,477 · notices of commencement 63,752 · lis pendens 5,495.

**The Clerk's families mix criminal and civil records.** The judgment family holds judgment/sentence, restitution, domestic violence and public defender judgments; the lien family holds warrants and juvenile restitution liens. By their names these are criminal or personal matters. The project rule is that criminal judgments stay out of everything past staging, so Phase B cannot use the family alone: it needs an explicit list of codes. Which codes count as criminal is Andres's call.

## Parties: business-shaped names (counts only)

A rough pattern count over 2,050,173 loaded party rows:

| Name contains | Rows | Share |
|---|---|---|
| A legal-entity word (LLC, INC, CORP, CO, COMPANY, LTD, LP, LLP, PLLC, PA, PC and similar) | 525,989 | 25.7% |
| No such word, but an organisation word (BANK, ASSOCIATION, MORTGAGE, TRUST, CITY OF, COUNTY, SERVICES…) | 329,610 | 16.1% |
| Neither: mostly individuals | 1,194,573 | 58.3% |

728,543 distinct names, 63,883 of them with a legal-entity word. The patterns are rough: short words like `CO`, `PA` and `NA` can match part of a person's name, and a business with no such word is counted as "neither". Treat these as an estimate of size, not a classifier.

## Re-indexing

The file's date is not the recording date. Of 753,259 loaded document rows, 170,066 were recorded before 2025-01-01 (the oldest record date in the data is 1775-01-01, presumably a placeholder). 36,013 instrument numbers appear in more than one daily file (up to four). Within one file an instrument number never repeats.

## Mismatches: 13 files failed verification and were not loaded

`src/datum/duval.py` counts the lines above the trailer and compares with `EOF|<count>`. 2,703 of 2,716 files matched. 13 did not:

| File | Lines | EOF count | File | Lines | EOF count |
|---|---|---|---|---|---|
| `d2025090201id.16` | 462 | 460 | `d2026031401id.16` | 254 | 253 |
| `d2025090301id.16` | 1,370 | 1,369 | `d2026040801id.16` | 3,208 | 3,206 |
| `d2026010901id.16` | 1,174 | 1,172 | `d2026061101id.16` | 1,344 | 1,343 |
| `d2026011501id.16` | 523 | 520 | `d2026072801id.16` | 1,372 | 1,371 |
| `d2026021901id.16` | 2,494 | 2,492 | `d2026081201id.16` | 1,668 | 1,665 |
| `d2026022501id.16` | 2,669 | 2,668 | `d2026101601id.16` | 1,868 | 1,867 |
| `l2026021901id.16` | 2,564 | 2,563 | | | |

**Cause, confirmed in every file:** in the 12 documents files, a legal description contains a line break, so one record is spread over two or three lines. Counting lines that begin `DDA|` gives exactly the EOF count in all 12, so the Clerk's count is right and no record is missing. The links file has one blank line.

They sit in `data/raw/duval/rejected/`. Not loaded: 18,386 document records (2.4% of the 771,645 in scope) and 2,563 link rows. The effect is visible downstream: all 45,173 party rows and all 14,464 link rows that have no matching document are from those 12 days. Outside those days there are zero orphans.

A repair is possible (join the broken lines into one record in a copy, keep the original) and has not been done: the brief says a mismatch fails the file.

## Other things found in the files

- 3 documents files begin with a UTF-8 byte-order mark, so the first row's record type loads as `ï»¿DDA`. The row is otherwise normal and is kept.
- Documents files contain 6,242 NUL bytes in text fields, and 960 double-quote characters. Both load as ordinary characters.
- One party name contains a pipe, so that row has an extra field and its name is cut at the pipe.
- 206 documents carry a type code that is not in the lookup, and 141 a code with no family.

## Open questions

- Terms of use (asked 2026-11-05, unanswered).
- Is the ssh-dss fingerprint above the Clerk's? Worth confirming with their IT contact.
- May the 12 documents files be repaired by joining broken lines?
- Which document type codes are criminal and must be excluded after staging?
- What is field 10 of the documents file?
- How should a citation point at a record? There is no per-record URL; the instrument number can be searched at the Clerk's Official Records site.
