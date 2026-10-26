-- 09_score_baseline_search.sql: score the simplest possible search against the test set.
-- Baseline v0 = normalize the input exactly like name_key, then pick the single most similar
-- company name in the whole register. No LLM, no city handling, no suffix stripping.
-- Run after `dbt seed` loaded the test set:  snow sql -c datum -f snowflake/09_score_baseline_search.sql
-- Cost: 10 inputs x 13M names = 130M comparisons. 🟡 Expect 1-3 minutes on X-Small.

USE ROLE SYSADMIN;                                        -- owner role
USE WAREHOUSE datum_wh;                                   -- cost-capped warehouse

CREATE OR REPLACE TEMPORARY TABLE datum.dev_evals.baseline_results AS  -- scratch table, gone when the session ends; full name needed (no default database)
WITH tests AS (
    SELECT case_id,
           case_group,
           input_text,
           expected_document_number,
           TRIM(REGEXP_REPLACE(UPPER(input_text), '[^A-Z0-9]+', ' ')) AS input_key
           -- the SAME normalization as name_key in entity_lookup: both sides cleaned identically
    FROM datum.dev_evals.test_set                         -- the seed table dbt loaded from the CSV
),
candidates AS (
    SELECT t.case_id,
           t.case_group,
           t.input_text,
           t.expected_document_number,
           e.document_number,                             -- the company this row proposes
           e.entity_name,
           JAROWINKLER_SIMILARITY(t.input_key, e.name_key) AS similarity
           -- 0-100: how alike two strings are; 100 = identical. Tolerant of typos.
    FROM tests t
    CROSS JOIN datum.dev_marts.entity_lookup e            -- every test input against every company
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY t.case_id                            -- one group per test input
        ORDER BY similarity DESC                          -- most similar company first
    ) = 1                                                 -- keep only the top match per input
)
SELECT *,
       CASE
         WHEN expected_document_number = 'NEEDS_MORE_INFO'
           THEN similarity < 90                           -- correct = NOT confident (90 is a starting guess)
         ELSE document_number = expected_document_number  -- correct = top match is the right company
       END AS is_correct
FROM candidates;

-- RESULT 1: every test case, what search returned, and whether it was right.
SELECT case_id, case_group, input_text, entity_name AS top_match, similarity,
       expected_document_number, document_number AS returned_document_number, is_correct
FROM datum.dev_evals.baseline_results
ORDER BY case_id;

-- RESULT 2: the score, overall and per group.
SELECT case_group,
       COUNT_IF(is_correct) AS correct,                   -- how many TRUE
       COUNT(*)             AS total,
       ROUND(100 * COUNT_IF(is_correct) / COUNT(*)) AS pct_correct
FROM datum.dev_evals.baseline_results
GROUP BY ROLLUP (case_group)                              -- ROLLUP adds a grand-total row (case_group = NULL)
ORDER BY case_group;


-- Syntax: CROSS JOIN pairs every row on the left with every row on the right. QUALIFY + ROW_NUMBER keeps the top-ranked row per group. A CASE whose branches are TRUE/FALSE expressions returns a boolean. GROUP BY ROLLUP adds subtotal rows.

-- Concept: a baseline is the score of the simplest reasonable approach. Every improvement later (extracting the name from the input with an LLM, stripping LLC/INC, blocking by first letter for speed) is judged against this number.

-- Design decision: comparing against all 13M names is brute force, fine for 10 test cases and wasteful at production scale. A temporary table stores results once so both result queries read it without recomputing 130M comparisons.
