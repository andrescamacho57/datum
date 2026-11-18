# Leg B1: link models

Branch `leg/b1-links` (stacked on `leg/b0-close-gaps`) · run 2026-11-18 (UTC) · status: **done, all tests pass. Three assumptions to read in section 3, because each one lowers the number of CONFIRMED links on purpose**

Rulings implemented: R1, R2, R3, R4, R11, R13, R14, R17, R19, plus the document-type allowlist of R16 and the date rule of R22 where the link models need them (`docs/phase_b_rulings.md`).

## 1. What I built

Until now each source sat on its own in staging. This leg adds the layer where sources meet: a lien's debtor, a license's business name and a party on a recorded document are each matched to a company in the state's corporate register.

```
entity_lookup (13.0M companies)
        │
        ▼
int_company_match_keys ──────────────┐   one row per company: match_key, ZIP5, status, filing date
                                     │
stg_sunbiz__flr_debtors ─────────────┼─▶ int_federal_lien_links
stg_dbpr__licenses ──────────────────┼─▶ int_dbpr_license_links ──▶ int_dbpr_discipline_links
stg_duval__parties + documents ──────┴─▶ int_duval_party_links          ▲
                                                                        │
seeds: duval_doc_type_allowlist (R16) ─▶ Duval          dbpr_license_type_map (R14) + stg_dbpr__discipline
```

**The match key.** `match_key` is the simplified name (`name_key`: capitals, punctuation turned into spaces) minus one trailing legal suffix. `ACME, L.L.C.` and `ACME INC` both become `ACME`. Source names go through the same macro as company names, so both sides are simplified by one rule.

**The rule, in order (rulings R1 and R2).** One macro, `link_to_companies` in `pipeline/macros/company_matching.sql`, used by every link model:

| Step | Question | Outcome |
|---|---|---|
| 1 | Does any company, of any status, have the source's match key? | No → **NO_MATCH** |
| 2 | The source has a 5-digit ZIP code, and exactly one company with that key is at that ZIP code | → candidate for CONFIRMED (`name_zip`); namesakes at other ZIP codes are dropped |
| 3 | The source has a ZIP code, and two or more such companies share it, or none does | → **AMBIGUOUS** (`several_companies_same_zip`, `zip_differs`) |
| 4 | The source has no ZIP code: exactly one company has the key AND the source name contains a legal-entity word | → candidate for CONFIRMED (`unique_name`); otherwise **AMBIGUOUS** (`several_companies`, `no_entity_word`) |
| 5 | Ruling R2: is the record dated before the company's own filing date, or is either date missing? | Yes → **AMBIGUOUS** (`before_company_filed`, `date_unknown`); no → **CONFIRMED** |

**Every link model has the same seven columns:**

| Column | What it holds |
|---|---|
| `source_record_id` | The source's own identifier: lien filing number, license number as printed, DBPR complaint number, Clerk's instrument number |
| `party_seq` | Which party on that record (a lien can have several debtors). 1 when the record has one name |
| `document_number` | The company's Sunbiz document number. NULL on NO_MATCH |
| `link_status` | CONFIRMED, AMBIGUOUS or NO_MATCH |
| `matched_on` | `name_zip` or `unique_name` on a CONFIRMED row, otherwise NULL |
| `link_reason` | Why the row got its status (the step above that decided it) |
| `source_date` | The record's date, which ruling R2 compares with the company's filing date |

No source name is in any of them. A CONFIRMED party has exactly one row; an AMBIGUOUS party has one row per possible company.

| New file | What it is |
|---|---|
| `pipeline/dbt_project.yml` | + `intermediate` folder (schema `DEV_INTERMEDIATE`, built as tables), + settings for two seeds (schema `DEV_REFERENCE`) |
| `pipeline/macros/company_matching.sql` | `name_key`, `legal_suffixes`, `entity_words`, `match_key`, `has_entity_word`, `link_to_companies` |
| `pipeline/models/intermediate/int_company_match_keys.sql` | One row per company: `match_key`, `zip5`, `status_code`, `file_date`, `match_key_company_count` (all statuses) |
| `…/int_federal_lien_links.sql` | Corporate lien debtors → companies |
| `…/int_dbpr_license_links.sql` | Contractor licenses through `dba_name`; `QB` business records through their own name |
| `…/int_dbpr_discipline_links.sql` | Complaint → license (through the seed) → company |
| `…/int_duval_party_links.sql` | TO-side business parties on `LN`, `WRT`, `JDG`, `CCCJUDG` → companies, unique-name branch only |
| `…/_intermediate__models.yml` | Column tests and three unit tests |
| `pipeline/seeds/dbpr_license_type_map.csv` | License kind in words → occupation code, 19 rows (R14) |
| `pipeline/seeds/duval_doc_type_allowlist.csv` | The only Duval type codes allowed past staging: 4 that can flag, 7 that close, 1 partial release (R16) |
| `pipeline/seeds/_seeds.yml` | Seed tests |
| `pipeline/tests/assert_no_name_columns_past_staging.sql` | Fails if any intermediate table other than `int_company_match_keys` has a column named like a name |
| `pipeline/tests/assert_no_confirmed_link_before_company_filed.sql` | Ruling R2, re-checked on the result |
| `pipeline/tests/assert_link_rows_are_consistent.sql` | Six promises about the shape of link rows |

New in Snowflake: schemas `DEV_INTERMEDIATE` (5 tables) and `DEV_REFERENCE` (2 seed tables). Nothing existing changed.

## 2. Checks

### The done-when table: CONFIRMED, AMBIGUOUS and NO_MATCH per source

Counted per source party (a party with five possible companies counts once as AMBIGUOUS). Counts only.

| Source | Parties | CONFIRMED | AMBIGUOUS | NO_MATCH | CONFIRMED by `name_zip` | CONFIRMED by `unique_name` |
|---|---|---|---|---|---|---|
| Federal lien debtors | 22,532 | 10,046 (44.6%) | 6,672 (29.6%) | 5,814 (25.8%) | 10,043 (99.97%) | 3 (0.03%) |
| DBPR licenses and `QB` records | 227,845 | 120,672 (53.0%) | 95,345 (41.8%) | 11,828 (5.2%) | 119,561 (99.1%) | 1,111 (0.9%) |
| DBPR discipline complaints | 788 | 379 (48.1%) | 357 (45.3%) | 52 (6.6%) | 374 (98.7%) | 5 (1.3%) |
| Duval TO-side business parties | 24,198 | 14,121 (58.4%) | 2,773 (11.5%) | 7,304 (30.2%) | 0 | 14,121 (100%) |

The command (the same query gives the reasons table below):

```
snow sql -c datum -q "WITH links AS (SELECT 'federal_lien' src, * FROM datum.dev_intermediate.int_federal_lien_links UNION ALL SELECT 'dbpr_license', * FROM datum.dev_intermediate.int_dbpr_license_links UNION ALL SELECT 'dbpr_discipline', * FROM datum.dev_intermediate.int_dbpr_discipline_links UNION ALL SELECT 'duval', * FROM datum.dev_intermediate.int_duval_party_links), party AS (SELECT src, source_record_id, party_seq, MIN(link_status) link_status, MIN(matched_on) matched_on, COUNT(*) row_count FROM links GROUP BY 1,2,3) SELECT src, COUNT(*) parties, COUNT_IF(link_status='CONFIRMED') confirmed, COUNT_IF(link_status='AMBIGUOUS') ambiguous, COUNT_IF(link_status='NO_MATCH') no_match, COUNT_IF(matched_on='name_zip') by_name_zip, COUNT_IF(matched_on='unique_name') by_unique_name, SUM(row_count) table_rows, MAX(row_count) max_candidates FROM party GROUP BY 1 ORDER BY 1"

| SRC             | PARTIES | CONFIRMED | AMBIGUOUS | NO_MATCH | BY_NAME_ZIP | BY_UNIQUE_NAME | TABLE_ROWS | MAX_CANDIDATES |
| dbpr_discipline | 788     | 379       | 357       | 52       | 374         | 5              | 920        | 9              |
| dbpr_license    | 227845  | 120672    | 95345     | 11828    | 119561      | 1111           | 262923     | 19             |
| duval           | 24198   | 14121     | 2773      | 7304     | 0           | 14121          | 28767      | 12             |
| federal_lien    | 22532   | 10046     | 6672      | 5814     | 10043       | 3              | 25058      | 25             |
```

The most companies ever offered for one party is 25, so AMBIGUOUS rows do not blow up.

**Why each party got its status**

| Source | Status | Reason | Parties | Of those, exactly one candidate company |
|---|---|---|---|---|
| Federal lien | CONFIRMED | `name_zip` | 10,043 | |
| | CONFIRMED | `unique_name` | 3 | |
| | AMBIGUOUS | `zip_differs` | 6,204 | 5,115 |
| | AMBIGUOUS | `several_companies_same_zip` | 433 | |
| | AMBIGUOUS | `before_company_filed` (R2) | 35 | |
| | NO_MATCH | no company with this match key | 5,814 | |
| DBPR license | CONFIRMED | `name_zip` | 119,561 | |
| | CONFIRMED | `unique_name` | 1,111 | |
| | AMBIGUOUS | `zip_differs` | 83,157 | 67,869 |
| | AMBIGUOUS | `before_company_filed` (R2) | 6,764 | |
| | AMBIGUOUS | `several_companies_same_zip` | 4,985 | |
| | AMBIGUOUS | `several_companies` | 310 | |
| | AMBIGUOUS | `no_entity_word` | 129 | |
| | NO_MATCH | no company with this match key | 11,828 | |
| DBPR discipline | CONFIRMED | `name_zip` / `unique_name` | 374 / 5 | |
| | AMBIGUOUS | `zip_differs` | 265 | 203 |
| | AMBIGUOUS | `before_company_filed` (R2) | 68 | |
| | AMBIGUOUS | `several_companies_same_zip` / `several_companies` | 23 / 1 | |
| | NO_MATCH | no company with this match key | 52 | |
| Duval | CONFIRMED | `unique_name` | 14,121 | |
| | AMBIGUOUS | `several_companies` | 2,620 | |
| | AMBIGUOUS | `before_company_filed` (R2) | 153 | |
| | NO_MATCH | no company with this match key | 7,304 | |

**DBPR, split by kind of record**

| Kind | Records | CONFIRMED | AMBIGUOUS | NO_MATCH |
|---|---|---|---|---|
| Contractor license with a business name (`dba_name`) | 98,948 | 48,633 | 43,151 | 7,164 |
| `QB` business record | 128,897 | 72,039 | 52,194 | 4,664 |

**Companies reached by at least one CONFIRMED link:** federal liens 5,462 companies (9,895 liens) · DBPR licenses 85,185 · discipline 318 · Duval 6,609 companies (12,917 documents). Of the 5,462 lien companies, 3,492 are inactive on Sunbiz and 1,970 active.

### dbt: models, column tests, singular tests and unit tests

`cd pipeline && dbt build --select "dbpr_license_type_map duval_doc_type_allowlist int_company_match_keys int_federal_lien_links int_dbpr_license_links int_dbpr_discipline_links int_duval_party_links"`

```
 Succeeded seed  DEV_reference.duval_doc_type_allowlist (table)
 Succeeded seed  DEV_reference.dbpr_license_type_map (table)
 Succeeded model DEV_intermediate.int_company_match_keys (table)
 Succeeded model DEV_intermediate.int_dbpr_license_links (table)
 Succeeded model DEV_intermediate.int_duval_party_links (table)
 Succeeded model DEV_intermediate.int_dbpr_discipline_links (table)
 Succeeded model DEV_intermediate.int_federal_lien_links (table)
    Passed unit_test DEV_intermediate_dbt_test__audit.match_key_strips_one_trailing_legal_suffix
    Passed unit_test DEV_intermediate_dbt_test__audit.lien_links_follow_rulings_r1_and_r2
    Passed unit_test DEV_intermediate_dbt_test__audit.duval_links_keep_only_to_side_businesses_on_allowlisted_documents
    Passed test  accepted_values_int_federal_lien_links_link_status__CONFIRMED__AMBIGUOUS__NO_MATCH
    Passed test  accepted_values_int_dbpr_license_links_link_status__CONFIRMED__AMBIGUOUS__NO_MATCH
    Passed test  accepted_values_int_dbpr_discipline_links_link_status__CONFIRMED__AMBIGUOUS__NO_MATCH
    Passed test  accepted_values_int_duval_party_links_link_status__CONFIRMED__AMBIGUOUS__NO_MATCH
    Passed test  relationships_int_federal_lien_links_document_number__document_number__ref_entity_lookup_
    Passed test  relationships_int_dbpr_license_links_document_number__document_number__ref_entity_lookup_
    Passed test  relationships_int_dbpr_discipline_links_document_number__document_number__ref_entity_lookup_
    Passed test  relationships_int_duval_party_links_document_number__document_number__ref_entity_lookup_
    Passed test  assert_no_name_columns_past_staging
    Passed test  assert_no_confirmed_link_before_company_filed
    Passed test  assert_link_rows_are_consistent
    ... (33 more passing column tests, left out here: not_null, unique, accepted_values on matched_on and on the seeds)
Finished 'build' successfully for target 'dev' [18.5s]
Processed: 5 models | 44 tests | 2 seeds | 3 unit tests
Summary: 54 total | 54 success
```

The four tests the brief names are all in that list: `accepted_values` on `link_status`; `relationships` to `entity_lookup` for every non-NO_MATCH row; the name-column test; the R2 test.

**What the unit tests prove.** A unit test runs a model's SQL on a few made-up rows written in the test file and compares the result with the rows we expect. No real data is involved, and the names in them are invented.
- `lien_links_follow_rulings_r1_and_r2`: nine debtors, one per branch of the rule. The output must be exactly: CONFIRMED by `name_zip` (and the namesake at another ZIP code dropped), `zip_differs`, `before_company_filed`, two rows for `several_companies_same_zip`, CONFIRMED by `unique_name`, `no_entity_word`, two rows for `several_companies`, NO_MATCH, `date_unknown`.
- `duval_links_keep_only_to_side_businesses_on_allowlisted_documents`: ten parties go in, three come out. Left out: the FRM side, a judgment the State of Florida brought, a name with no entity word, a mortgage, and a release.
- `match_key_strips_one_trailing_legal_suffix`: `ACME L L C` → `ACME`; `ACME CO INC` → `ACME CO`; `SMITH M D P A` → `SMITH M D`; a name that is only `INC` stays; `LINCOLN GROUP` is untouched.

### Offline checks

```
$ pytest
60 passed in 0.21s
$ ruff check src tests
All checks passed!
```

### The seed for license kinds (R14)

All 19 license kinds in the discipline files map to a code; **none is unmapped**. I checked the draft against the data: when a complaint's kind and number find a license, is the respondent the same person as the license holder? (Names compared inside the query; only counts come out.)

| Code | Complaints | License found | Same person | | Code | Complaints | License found | Same person |
|---|---|---|---|---|---|---|---|---|
| `CPC` pool/spa | 767 | 49 | 48 | | `CMC` mechanical | 15 | 13 | 13 |
| `CGC` general | 669 | 266 | 263 | | `CVC` solar | 8 | 3 | 3 |
| `CCC` roofing | 468 | 191 | 191 | | `RR` reg. residential | 7 | 1 | 1 |
| `FRO` financial officer | 466 | 15 | 15 | | `RC` reg. roofing | 5 | 3 | 3 |
| `CBC` building | 303 | 130 | 130 | | `RP` reg. pool/spa | 5 | 0 | — |
| `CRC` residential | 145 | 40 | 40 | | `RF` reg. plumbing | 2 | 2 | 2 |
| `CAC` air conditioning | 134 | 96 | 96 | | `RX` reg. specialty | 1 | 1 | 1 |
| `SCC` specialty | 115 | 13 | 13 | | `CUC` underground | 1 | 1 | 1 |
| `CFC` plumbing | 47 | 40 | 39 | | `RG` reg. general | 1 | 0 | — |
| | | | | | `RB` reg. building | 1 | 1 | 1 |

860 of 865 found licenses belong to the same person, across 17 codes. ✅ Two codes, `RP` and `RG`, found no license at all, so their mapping is unverified 🟡 (6 complaints).

### Where discipline complaints stop (3,160 complaints in the five files)

| Step | Complaints left |
|---|---|
| All complaints | 3,160 |
| Minus complaints against a financial officer (`FRO`: not a contractor license) | 2,694 |
| The license is in the state's current license file | 850 |
| That license names a business (`dba_name`) | 788 ← the rows of `int_dbpr_discipline_links` |
| CONFIRMED to a company | 379 |

**1,844 of 2,694 contractor complaints (68%) point at a license that is not in the license file.** The state leaves delinquent, void and involuntarily inactive licenses out of that file, and a disciplined contractor is exactly who ends up in those groups. So discipline reaches a company for 12% of complaints. This is a limit of the source, not of the link.

### What goes into the Duval link model (documents as of the newest file for each)

| Type | Documents | With the State of Florida on the FRM side | TO-side parties | After leaving out State judgments | With a legal-entity word (the model's input) |
|---|---|---|---|---|---|
| `LN` lien | 48,985 | 120 | 54,762 | 54,762 | 12,274 |
| `WRT` tax warrant | 2,776 | 2 | 2,790 | 2,790 | 2,310 |
| `JDG` judgment | 74,647 | 4,717 | 95,983 | 90,875 | 8,998 |
| `CCCJUDG` county civil judgment | 11,654 | 77 | 14,164 | 14,087 | 616 |
| Total | 138,062 | | 167,699 | 162,514 | **24,198** |

138,316 TO-side party rows without a legal-entity word stay in staging (ruling R19).

| Type | CONFIRMED | AMBIGUOUS | NO_MATCH |
|---|---|---|---|
| `LN` | 7,616 | 1,792 | 2,866 |
| `WRT` | 1,970 | 256 | 84 |
| `JDG` | 4,119 | 648 | 4,231 |
| `CCCJUDG` | 416 | 77 | 123 |

## 3. Decisions I made and why

**Three assumptions that lower the CONFIRMED count on purpose.** The brief says: when unclear, take the reading that shows less, write it down, keep going.

| # | Assumption | Why this reading | What it costs, in counts |
|---|---|---|---|
| A1 | **A source ZIP code that disagrees is never rescued by a unique name.** R1's second branch starts "Without a ZIP code", so I apply it only to records that have none. A lien debtor whose name is unique in Florida but whose ZIP code differs from the company's principal address is AMBIGUOUS | R1 as written. The older wording in d19 ("or the only company with that name") would confirm these | **5,115 lien debtors (22.7%)**, 67,869 DBPR records and 203 complaints have exactly one candidate company and a different ZIP code. Lien coverage is 44.6%, **below the 50% mark at which d19 says to revisit the rule** |
| A2 | **For a license, "the record's date" in R2 is the license's effective date** (when its current period began), not the original licensure date | R2 needs one date per record. The original date would demote almost every license (a contractor licensed in 1995 who formed an LLC in 2010). The effective date is the date of the record as it stands | 6,107 contractor licenses and 657 `QB` records are AMBIGUOUS only because the license period began before the company was filed. Some are surely true links (a contractor who formed a company mid-period) |
| A3 | **A missing date blocks CONFIRMED.** If the record's date or the company's filing date is unknown, R2 can't be checked, so the link is AMBIGUOUS (`date_unknown`) | "Unknown" is not "after" | 0 rows today in the real data (1,964 companies have no filing date; none is a confirmed candidate). It is there for the day one appears |

**Other decisions**

| Decision | Why | Tradeoff |
|---|---|---|
| The linking rule is one macro used by all four models | The most expensive error is a wrong link, so the rule has one implementation, one review and one set of unit tests | A reader has to open the macro file, or run `dbt compile`, to see the SQL a model really runs. Phase A repeated logic for readability; here I chose one copy for safety |
| Grain is one row per source party per candidate company | A7 in the spec needs "possible match: verify" on the company's report, so an AMBIGUOUS record must name each possible company. CONFIRMED stays one row | The table is not one row per record. `assert_link_rows_are_consistent` guards the shape |
| When the ZIP code singles out one company, namesakes at other ZIP codes are dropped, even if R2 then demotes the link | The address already said which company it is. Offering the others would put a "possible match" on companies the address rules out | A record demoted by R2 shows one possible company, not all namesakes |
| Extra columns `party_seq` and `link_reason` beyond the brief's five | `party_seq` because a lien has several debtors and a Duval document several parties: the identifier needs it. `link_reason` because the report must explain every AMBIGUOUS count, and the hand check will want to know why | Two more columns than listed. Neither is a name |
| Only one trailing suffix is stripped | The brief: "minus a trailing legal suffix" | `ACME CO INC` and `ACME INC` do not match each other |
| The entity-word list leaves out the spaced two-letter forms (`L C`, `P A`, `P C`, `L P`, `P L`) | In a person's name they can be two initials (`SMITH L C`). Reading initials as "this is a company" is the mistake R1 exists to stop | A real `SMITH P A` (a professional association) is not CONFIRMED by unique name. It is still matched when a ZIP code agrees |
| Individuals' records are not carried as NO_MATCH rows | R19: an individual's party row goes no further than staging. So the models leave out licenses with no business name, Duval names with no entity word, and complaints that reach no business | The models don't account for every staging row. The funnels above do |
| `QB` records get an identifier made from a checksum of the row | The state's file gives them no number, and a row number would change on every reload | An identifier nobody can look up. The flags mart will need a different citation for a `QB` record |
| The State-of-Florida test covers `FLORIDA STATE OF`, `FLORIDA STATE OF ETAL` and `STATE OF FLORIDA` | It is the same party written three ways (4,838, 2 and 5 judgment party rows). State agencies (Department of Revenue, 3,757 rows) are different parties and are not excluded, as R16 says | One row typed `FLORIDA STATE OF REV DEPT ETAL` is caught too |
| Seeds go to a new schema, `DEV_REFERENCE` | The existing seed schema is `DEV_EVALS`, for test cases. These are lookup tables the pipeline depends on | One more schema |
| Intermediate models are tables, not views | Each link model joins 13 million companies. As views, every test and every downstream query would redo that | A little storage; the tables go stale until the next `dbt build` |
| The latest daily file wins when the Clerk re-indexes a document | 38,218 instruments appear in more than one file; 98 changed type | A party list from an older file is ignored |

While measuring, I created one temporary table of simplified names in `DEV_INTERMEDIATE` and dropped it in the same script. It existed for a few seconds. I should have used a query-only step and did so afterwards.

## 4. What I couldn't verify, and open questions for Andres

1. **A1 is the big one.** Does "Without a ZIP code" in R1 mean "the record has no ZIP code" (what I built) or "the ZIP codes don't agree"? The second reading would add up to 5,115 lien debtors, before R2 and the entity-word test. A middle path that needs no ruling change: the corporate file also carries each company's **mailing** address, which staging does not parse today. Matching on either ZIP code would lift coverage without loosening the rule. It means changing `stg_sunbiz__cor` and `entity_lookup`, which this leg may not touch.
2. **Legal form is not compared.** A CONFIRMED link needs the same match key, so `ACME INC` can link to `ACME LLC` when that is the only `ACME` (or the only one at that ZIP code). Counts among CONFIRMED links where both names carry a suffix of a different kind: **96 federal liens (1.0%), 148 Duval parties (1.0%), 97 licenses (0.2%)**. Most CONFIRMED names are identical once simplified (90.7% of liens, 96.5% of Duval). The hand check in B3 is the place to see whether those 1% are wrong; if they are, "same kind of suffix" is a small addition to R1.
3. **A2: is the effective date the right date for a license?** 6,107 licenses hang on it.
4. **Discipline rarely reaches a company** (12% of complaints), because the license file leaves out the licenses most likely to be disciplined. Worth knowing before counsel spends time on Q1: the feature may be small either way.
5. **Two seed rows are unverified**: `Registered Pool/Spa Contractor` → `RP` and `Registered General Contractor` → `RG`. No complaint of those kinds found a license to compare with.
6. **Liens and warrants held by the State of Florida.** R16 applies the State test to judgments only. Three such documents (1 `LN`, 2 `WRT`) have a CONFIRMED business party. I followed the ruling and left them in.
7. **5,814 lien debtors (25.8%) match no company at all.** That is the size of the fuzzy-linking question (Q20): typos, abbreviations and names the IRS wrote differently.
8. I could not check any link by eye against Sunbiz: that is the B3 hand check, and it is yours.

## 5. Credits used

**About 0.116 credits** on `datum_wh` (roughly $0.23).

```
snow sql -c datum -q "SELECT start_time, end_time, credits_used FROM TABLE(datum.information_schema.warehouse_metering_history(DATEADD('hour', -12, CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(), 'DATUM_WH')) ORDER BY start_time"
after B0 (23:20 Pacific, Nov 17):  0.159036111
after B1 (23:34 Pacific, Nov 17):  0.275495278
```

The difference is this leg, including the exploration queries. Phase B running total: 0.28 of the 3-credit cap.

## 6. Three questions you should be able to answer

1. `match_key_company_count` counts companies of every status, not just active ones. Describe a case where counting only active companies would pin a lien on the wrong company.
2. A lien debtor is named `BOLT INC` at ZIP code 32256. Exactly one company in Florida is called `BOLT`, and its principal address is in 33101. What status does the link get, which line of the macro decides it, and what would d19's older wording have said?
3. The four link models never store the source's name, yet they match on it. Where does the name live while the match is computed, and which test would fail if someone added a `debtor_name` column "just for debugging"?
