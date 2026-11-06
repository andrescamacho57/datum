# Prompt 02: Load the federal lien files to raw (Day 2, part 1)

Normal mode. Review tier 2: Andres skims the diff.

Read snowflake/04_sunbiz_cor_quarterly_stage.sql, snowflake/06_load_sunbiz_cor_quarterly.sql and docs/access/sunbiz_flr.md. Then write `snowflake/13_federal_liens_raw.sql` that does four things:

a. **Stages:** creates 4 stages in datum.raw, one per record type (decision d9): `sunbiz_flr_filings_stage`, `sunbiz_flr_debtors_stage`, `sunbiz_flr_events_stage`, `sunbiz_flr_secured_stage`.

b. **Tables:** creates 4 raw tables, `sunbiz_flr_filings`, `sunbiz_flr_debtors`, `sunbiz_flr_events` and `sunbiz_flr_secured`, with the same columns as the existing raw tables (line, source_file, loaded_at). Each table holds both quarterly and daily rows; staging will tell them apart by source_file.

c. **Load:** COPYs each stage into its table the same way 06 does, reusing the existing fixed_width file format and METADATA$FILENAME.

d. **Validation query at the end:** row count per table and per source_file, plus min and max length(line).

Don't put PUT in the script. Instead, write the 8 PUT commands in a comment block at the top, as `snow sql -c datum -q "PUT ..."` lines, for these files in data/raw/sunbiz/flr/:
- the quarterly files: FLRF.TXT, FLRD.TXT, FLRE.TXT, FLRS.TXT
- the dailies: 20261104flrf.txt, 20261104flrd.txt, 20261104flre.txt, 20261104flrs.txt

Each file goes to its matching stage.

Follow the comment style of scripts 01–12: comment every line, and end with `-- Syntax`, `-- Concept` and `-- Design decision` sections.

Expected validation counts (from the manual inspection, docs/access/sunbiz_flr.md):

| Table | Quarterly rows | Daily 20261104 rows | Line length |
|---|---|---|---|
| filings | 20,444 | 42 | 82 |
| debtors | 22,173 | 46 | 206 |
| events | 97,256 | 29 | 135 |
| secured | 20,448 | 42 | 206 |
