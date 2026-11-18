# Duval recording index fixtures

Cut from real files in the Duval County Clerk's bulk recording index so the tests run offline (CLAUDE.md rule 4).

Origin: SFTP `ftp.duvalclerk.com`, folder `/Recording Indexes`, the four files dated 2025-01-03. Captured 2026-11-12T13:10Z.

| Fixture | What it is |
|---|---|
| `d2025010301id.16` | 12 real document rows (satisfactions, releases, a judgment, notices of commencement), trailer rewritten to `EOF|12` |
| `p2025010301id.16` | The 34 real party rows for those 12 documents, trailer rewritten to `EOF|34` |
| `l2025010301id.16` | The 14 real link rows for those 12 documents, trailer rewritten to `EOF|14` |
| `m2025010301d.16` | The real document-type lookup file, whole and unchanged |
| `d2025010401id.16` | Corrupted on purpose: the same 12 rows with a trailer that says `EOF|13` |
| `d2025010501id.16` | Corrupted on purpose: the same 12 rows with no trailer (a cut-off download) |

**Broken files, for the repair (ruling R15).** In `rejected/`, mirroring `data/raw/duval/rejected/`. Cut on 2026-11-18 from two of the 13 files that failed verification (downloaded 2026-11-12). They hold document and link rows only, so no party names.

| Fixture | What it is |
|---|---|
| `rejected/d2026011501id.16` | Lines 102–118 of the real file: 14 mortgage records from 2004. Two are split by a line break inside the legal description, and one of those also has a blank line, so the file has 17 lines above a trailer rewritten to `EOF|14` |
| `rejected/l2026021901id.16` | Lines 2207–2214 of the real file: 7 link rows and the one blank line, trailer rewritten to `EOF|7` |
| `rejected/d2026011601id.16` | Corrupted on purpose: the same 14 records with a trailer that says `EOF|15`. No repair can make it match, so it must stay out |

**Redaction.** No file in git may hold a person's name. Every party name that is not plainly a company is replaced with `REDACTED PERSON`. Company names, instrument numbers, dates, type codes, the pipe layout and the CRLF line endings are as the Clerk sent them.

**Not for display.** The Clerk has not yet said whether terms of use apply to this data. Nothing from Duval is shown outside this repo until Andres says so.
