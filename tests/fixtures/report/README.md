# Report fixtures

Three small files that stand in for the three Postgres tables the report builder reads. `tests/test_report_builder.py`, `tests/test_report_cli.py` and the web app's tests build reports from them with no database.

| File | Rows | Origin | Captured |
|---|---|---|---|
| `source_coverage.csv` | 5 | The five rows of the mart `source_coverage`, read from the local Postgres copy (`datum_dev`) with `select ... from source_coverage order by list_order`. They are unchanged. A row describes a source, and it is about nobody | Nov 24, 2026, during leg C3 of Phase C |
| `company_flags.csv` | 4 | Four rows of the mart `company_flags`, read from the same Postgres copy: an open federal lien, a federal lien closed by a certificate of release, an open federal lien with a certificate of discharge, and an inactive DBPR (Department of Business and Professional Regulation) license. The words in `citation`, `status`, `status_note` and `caveat` are the mart's own, which is the point of the fixture | Nov 24, 2026 |
| `company_search.csv` | 6 | Invented. No row is cut from a real company | Written by hand on Nov 24, 2026 |

## What was replaced in `company_flags.csv`

- **Every filing number and license number is invented.** A federal lien filing number has the shape of two digits, `FLR`, then seven digits. The invented ones have a running number of 9900000 or more, and the largest real one in the mart on Nov 24, 2026 was 0018670. The license number is in the invented range the DBPR fixtures already use (`CGC99` and five digits). The same invented number replaces the real one inside `citation` and `status_note`.
- **Every document number is invented.** It starts with `T`, and no company in the state's file has a document number that starts with `T` (counted on Nov 24, 2026).
- **The dates on the license row are invented too** (`fact_date`, and the expiry date inside `status_note`). A license is held by a person, and a real effective date next to a real expiry date narrows the search for that person.
- The dates on the three federal lien rows are real. A federal lien in this mart is filed against a business.

## Why the companies are invented

Phase C's brief allows a fixture row to be cut from a real mart row about a company. A small company's principal address is often somebody's home, the repo is public, and the report builder's tests need the shape of a company row and not any particular company. So the six companies are made up: their names hold the word INVENTED, their addresses are `1 INVENTED WAY` and so on, and their document numbers start with `T`. One of them has no address, no date and an entity-type code that has no label, to test what the report says about a gap.

`tests/test_fixture_privacy.py` checks all of the above on every run.

To refresh `source_coverage.csv` or the wording in `company_flags.csv`, read the rows again, replace the numbers the same way, and commit the refresh on its own (`CLAUDE.md` rule 5).
