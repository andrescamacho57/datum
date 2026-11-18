-- ---------------------------------------------------------------------------
-- warn_flr_filings_year_out_of_range.sql: a SINGULAR test at WARN severity.
--
-- The rule: a lien's assessment year and expiration year fall in 1990–2040.
-- The state's file has a few mistyped years (expiration 2510, 9211;
-- assessment 8200, 9201). They still parse as MMDDYYYY, so nothing else
-- catches them. Known on the 2026-10-03 snapshot: 28 liens
-- (docs/access/sunbiz_flr.md, finding 7).
--
-- Why warn, not error: the bad values are the state's, not ours. An error
-- would block every build over 28 rows we can't fix. A warning keeps them
-- visible in every `dbt build` output, and Phase B must not compute "expires
-- on" from these rows.
-- ---------------------------------------------------------------------------

{{ config(severity = 'warn') }}
-- config(...) in double curly braces sets options for this one test.
-- severity 'warn' = report the bad rows, but don't fail the build.

select
    source_file,                                 -- the state file the lien came from
    filing_doc_number,                           -- the lien with the odd year
    assessment_date,                             -- shown so the reader sees which date is off
    expiration_date
from {{ ref('stg_sunbiz__flr_filings') }}
where year(assessment_date) not between 1990 and 2040
   -- year(date) takes the year out of a date. not between a and b = outside the range.
   or year(expiration_date) not between 1990 and 2040
   -- A NULL date is not reported here: NULL compared with anything is "unknown", which where treats as false.
