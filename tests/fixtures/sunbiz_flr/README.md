# Sunbiz federal lien (FLR) fixtures

Cut from the state's real daily federal tax lien files so the tests run offline (CLAUDE.md rule 4).

Origin: SFTP `sftp.floridados.gov` (the Division of Corporations' public server), folders `doc/flr/filings`, `doc/flr/events` and `doc/flr/debtors`, the files dated 2026-11-04. Pulled by Andres on 2026-11-05 (about 18:25 UTC, from the files' modification times); fixtures cut 2026-11-18.

| Fixture | What it is |
|---|---|
| `20261104flrf.txt` | The real filings file, whole and unchanged: 42 liens, every line 82 characters. This layout holds no names |
| `20261104flre.txt` | The real events file, whole and unchanged: 29 certificates of release, every line 135 characters. This layout holds no names |
| `20261104flrd.txt` | The first 10 lines of the real debtors file, every line 206 characters, with the name and address fields overwritten (see below) |
| `20261105flrf.txt` | Corrupted on purpose: the filings file with line 3 cut to 77 characters |
| `20261106flrf.txt` | Corrupted on purpose: the filings file cut off mid-line, with no final line break |

**Redaction.** Debtors are businesses (every row is name format `C`), but a fixture has no need to say which business owes a tax lien. In `20261104flrd.txt` the name (positions 14–68) is overwritten with `REDACTED DEBTOR LLC` and the two address lines (positions 70–157) with `REDACTED`, padded with spaces so every field keeps its position. City, state, ZIP code, lien number and the status letters are as the state sent them.
