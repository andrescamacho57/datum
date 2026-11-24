-- 22_size_q28_spaced_suffix.sql: size open question Q28. It prints counts only, and it changes nothing.

-- Why: the match key of ruling R1 is a company's simplified name minus one trailing legal suffix. The
-- simplified name writes L.L.C. as "L L C", and the suffix list tries longer forms first, so a name
-- that ends in "P L L C" loses all four letters, as if it ended in PLLC. That is right for
-- "SMITH, P.L.L.C." and wrong for "A.B.C.P., L.L.C.", where the P is the last initial of the name and
-- the suffix is only L.L.C. The second company's match key comes out one letter short, and it could
-- then share a match key with a different company. Q28 asks how many companies this touches.
--
-- What this script counts:
--   CHECK 1  the companies whose match key lost FOUR spaced letters (P L L C or L L L P) where the last
--            three alone are also a legal suffix (L L C or L L P), split by how the registered name
--            writes those letters
--   CHECK 2  the CONFIRMED links, in each of the four link models, that point at one of those companies
--   CHECK 3  the same misreading one size down: a name that ends "L, L.C." or "L, L.P." and lost three
--            letters, where two alone are also a suffix. Counted for completeness
--
-- No name is printed. The registered name is read only to count how it writes the suffix.
-- Run from the VS Code terminal:
--     snow sql -c datum -f snowflake/22_size_q28_spaced_suffix.sql
-- Safe to rerun: every statement is a SELECT.

USE ROLE SYSADMIN;                                         -- the role that owns DATUM
USE WAREHOUSE datum_wh;                                    -- the cost-capped X-Small warehouse (the only one we use)

-- ---------------------------------------------------------------------------
-- The group every check starts from, saved as a temporary table so the three checks read one list.
-- A TEMPORARY table lives only for this session and is dropped when the script ends.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TEMPORARY TABLE q28_companies AS         -- one row per company whose match key lost four spaced letters
SELECT k.document_number,                                  -- the company
       CASE WHEN k.name_key LIKE '% P L L C' THEN 'P L L C'    -- % = any text, so this reads "ends in a space and P L L C"
            ELSE 'L L L P'                                 -- the only other four-letter spaced form in the suffix list
       END                                     AS letters_removed,
       CASE
         WHEN REGEXP_LIKE(UPPER(e.entity_name), '.*[^A-Z0-9.](P\\.?L\\.?L\\.?C|L\\.?L\\.?L\\.?P)\\.?[^A-Z0-9]*')
           THEN 'one unit, apart from the name'            -- ", P.L.L.C." or " P.L.L.C.": only periods between the four letters, and in front of them a character that is not a letter, a digit or a period (a space or a comma, as a rule)
         WHEN REGEXP_LIKE(UPPER(e.entity_name), '.*[PL]\\.?,[ ]*(L\\.? ?L\\.? ?C|L\\.? ?L\\.? ?P)\\.?[^A-Z0-9]*')
           THEN 'comma after the first letter'             -- "... P., L.L.C.": the comma puts the first letter with the name
         WHEN REGEXP_LIKE(UPPER(e.entity_name), '.*(P\\.?L\\.?L\\.?C|L\\.?L\\.?L\\.?P)\\.?[^A-Z0-9]*')
           THEN 'one unit, run together with the name'     -- "A.B.C.P.L.L.C.": a period or nothing at all right in front of the four letters, so the name does not say where it ends
         ELSE 'spaces only'                                -- "... P L L C" or "... P. L. L. C.": readable either way
       END                                     AS how_the_name_writes_it,
       REGEXP_LIKE(k.match_key, '(.* )?[A-Z]')  AS rest_ends_in_one_letter   -- TRUE when the last word of what is left is a single letter: "A B C", and also "SMITH J"
FROM datum.dev_intermediate.int_company_match_keys AS k    -- one row per company, with its name_key and match_key
INNER JOIN datum.dev_marts.entity_lookup AS e              -- the registered name, read for the count only
  ON e.document_number = k.document_number
WHERE k.name_key LIKE '% P L L C'                          -- the simplified name ends in four spaced letters ...
   OR k.name_key LIKE '% L L L P';                         -- ... that the match key removes as one suffix

-- ---------------------------------------------------------------------------
-- CHECK 1: how many companies, by how the registered name writes the four letters.
-- "one unit, apart from the name" is the reading the name itself gives: the four letters stand together, and the character before them is not a letter, a digit or a period.
-- "comma after the first letter" is the group Q28 describes: the match key is very likely one letter short.
-- "one unit, run together with the name" and "spaces only" could be either reading.
-- ---------------------------------------------------------------------------
SELECT letters_removed,
       how_the_name_writes_it,
       COUNT(*)                          AS companies,             -- companies in this group
       COUNT_IF(rest_ends_in_one_letter) AS rest_ends_in_one_letter    -- of those, the ones whose remaining name ends in a single letter. Q28's example has this shape, and so does "SMITH J"
FROM q28_companies
GROUP BY ROLLUP (letters_removed, how_the_name_writes_it)  -- ROLLUP adds a subtotal row per first column and a grand total row, with NULL in the rolled-up columns
ORDER BY letters_removed NULLS LAST, how_the_name_writes_it NULLS LAST;

-- ---------------------------------------------------------------------------
-- CHECK 2: the CONFIRMED links that point at one of those companies, by source and by group.
-- A link here is not known to be wrong. It is a link whose company has a match key that may be one
-- letter short, which is the only way this misreading could have put a record on the wrong company.
-- ---------------------------------------------------------------------------
WITH confirmed_links AS (                                  -- every CONFIRMED link of the four link models, labelled with its source
  SELECT 'federal_lien' AS source, source_record_id, document_number FROM datum.dev_intermediate.int_federal_lien_links WHERE link_status = 'CONFIRMED'
  UNION ALL
  SELECT 'dbpr_license', source_record_id, document_number FROM datum.dev_intermediate.int_dbpr_license_links WHERE link_status = 'CONFIRMED'
  UNION ALL
  SELECT 'dbpr_discipline', source_record_id, document_number FROM datum.dev_intermediate.int_dbpr_discipline_links WHERE link_status = 'CONFIRMED'
  UNION ALL
  SELECT 'duval', source_record_id, document_number FROM datum.dev_intermediate.int_duval_party_links WHERE link_status = 'CONFIRMED'
)
SELECT l.source,
       q.how_the_name_writes_it,
       COUNT(*)                          AS confirmed_link_rows,   -- link rows (one per party on a record)
       COUNT(DISTINCT l.source_record_id) AS records,              -- distinct liens, licenses, complaints or instruments
       COUNT(DISTINCT l.document_number) AS companies              -- distinct companies they point at
FROM confirmed_links AS l
INNER JOIN q28_companies AS q                              -- keep only links whose company is in the Q28 group
  ON q.document_number = l.document_number
GROUP BY ROLLUP (l.source, q.how_the_name_writes_it)       -- subtotals per source, and a grand total
ORDER BY l.source NULLS LAST, q.how_the_name_writes_it NULLS LAST;

-- ---------------------------------------------------------------------------
-- CHECK 3: the same misreading one size down. A name that ends "L, L.C." or "L, L.P." simplifies to
-- "... L L C" or "... L L P" and loses three letters, where "L C" or "L P" alone is also a suffix.
-- Millions of names end in L.L.C., so only the names with a comma after the first L are counted:
-- that comma is the one sign the first L belongs to the name. Counted so that nothing in Q28's class
-- is left unsized. Expected: small numbers.
-- ---------------------------------------------------------------------------
WITH three_letter_companies AS (                           -- the companies whose three removed letters are split by a comma after the first
  SELECT document_number
  FROM datum.dev_marts.entity_lookup
  WHERE (name_key LIKE '% L L C' OR name_key LIKE '% L L P')   -- three spaced letters that the match key removes
    AND name_key NOT LIKE '% P L L C'                      -- not the four-letter forms counted above
    AND name_key NOT LIKE '% L L L P'
    AND REGEXP_LIKE(UPPER(entity_name), '.*L\\.?,[ ]*L\\.? ?[CP]\\.?[^A-Z0-9]*')   -- "... L., L.C." or "... L, LP"
),
confirmed_links AS (                                       -- every CONFIRMED link of the four link models
  SELECT document_number FROM datum.dev_intermediate.int_federal_lien_links WHERE link_status = 'CONFIRMED'
  UNION ALL
  SELECT document_number FROM datum.dev_intermediate.int_dbpr_license_links WHERE link_status = 'CONFIRMED'
  UNION ALL
  SELECT document_number FROM datum.dev_intermediate.int_dbpr_discipline_links WHERE link_status = 'CONFIRMED'
  UNION ALL
  SELECT document_number FROM datum.dev_intermediate.int_duval_party_links WHERE link_status = 'CONFIRMED'
)
SELECT (SELECT COUNT(*) FROM three_letter_companies)  AS companies_with_a_comma_inside_l_l_c_or_l_l_p,   -- a query in parentheses that returns one value can stand where a value goes
       (SELECT COUNT(*)
        FROM confirmed_links AS l
        INNER JOIN three_letter_companies AS t
          ON t.document_number = l.document_number)   AS confirmed_links_pointing_at_them;

-- Syntax: REGEXP_LIKE(text, pattern) is TRUE only when the pattern matches the WHOLE text, which is why each pattern starts with .* (any characters). Inside a pattern, \\. is a literal dot (the backslash is typed twice because SQL text uses one backslash to escape the next character), ? means "the thing before me is optional", and [^A-Z0-9]* means "any run of characters that are not letters or digits", which lets a name end in a period or a parenthesis. GROUP BY ROLLUP (a, b) returns the normal groups plus a subtotal row for each a and one grand total row; the rolled-up columns are NULL on those rows. CREATE TEMPORARY TABLE makes a table that only this session can see and that disappears when the session ends.

-- Concept: sizing before deciding. A rule that might be wrong is first counted, at its widest and at its narrowest, and only then does anyone decide whether to change it. The wide count says how many records the change could touch. The narrow count says how many are probably wrong today. A fix with a narrow count of zero can wait, and a fix with a wide count in the thousands needs its own review.

-- Design decision: counts only, and nothing is changed. The match key is the heart of the linking rule, and ruling R1 owns it, so changing it is a ruling and a High-tier leg of its own, not a side effect of the leg that builds the app's tables. The script reads the registered name to tell "P.L.L.C." from "P., L.L.C.", and it never prints one: a company's name is public, but the leg reports are written to hold counts. The four groups are kept apart because they call for different answers. "One unit, apart from the name" needs no fix, "comma after the first letter" is the real misreading, and the other two cannot be settled from the name at all.
