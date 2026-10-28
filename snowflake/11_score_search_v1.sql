-- 11_score_search_v1.sql: score search v1 = LLM extraction -> name match -> city tie-break.
-- Inputs: DEV_EVALS.TEST_SET (answers) + DEV_EVALS.EXTRACTED_INPUTS (fields from src/datum/extract.py).
-- Compare to the baseline (09/10): top-1 6/10, recall@5 8/10.
-- Run after `dbt seed`:  snow sql -c datum -f snowflake/11_score_search_v1.sql   (🟡 1-3 minutes)

USE ROLE SYSADMIN;                                        -- owner role
USE WAREHOUSE datum_wh;                                   -- cost-capped warehouse

CREATE OR REPLACE TEMPORARY TABLE datum.dev_evals.v1_top5 AS
WITH cases AS (
    SELECT t.case_id,
           t.case_group,
           t.input_text,
           t.expected_document_number,
           x.business_name,                               -- the name the LLM pulled out
           x.city,                                        -- the city the LLM pulled out (may be empty)
           x.is_specific,                                 -- FALSE = "not enough to identify a business"
           TRIM(REGEXP_REPLACE(UPPER(x.business_name), '[^A-Z0-9]+', ' ')) AS search_key,
           -- same cleaning as name_key, applied to the EXTRACTED name instead of the raw text
           UPPER(TRIM(x.city))                                             AS city_key
    FROM datum.dev_evals.test_set t
    JOIN datum.dev_evals.extracted_inputs x               -- one extraction per test case
      ON t.case_id = x.case_id
)
SELECT c.case_id,
       c.case_group,
       c.input_text,
       c.expected_document_number,
       e.document_number,
       e.entity_name,
       e.principal_city,
       JAROWINKLER_SIMILARITY(c.search_key, e.name_key) AS similarity,
       IFF(c.city_key <> '' AND UPPER(e.principal_city) LIKE c.city_key || '%', 1, 0) AS city_match,
       -- 1 when the company's city starts with the extracted city ("PONTE VEDRA" matches
       -- "PONTE VEDRA BEACH"); UPPER() handles the mixed casing. || joins two strings.
       ROW_NUMBER() OVER (
           PARTITION BY c.case_id
           ORDER BY similarity DESC,                      -- best name match first...
                    city_match DESC,                      -- ...then, among ties, the one in the right city
                    e.document_number                     -- ...then a fixed order, so reruns can't flip
       ) AS rank_in_list
FROM cases c
CROSS JOIN datum.dev_marts.entity_lookup e
WHERE c.is_specific                                       -- only search when the note names a business
QUALIFY rank_in_list <= 5;

-- RESULT 1: per case. Non-specific notes answer NEEDS_MORE_INFO instead of searching.
WITH per_case AS (
    SELECT t.case_id, t.case_group, t.input_text, t.expected_document_number,
           x.business_name, x.city, x.is_specific,
           MAX(IFF(r.rank_in_list = 1, r.entity_name, NULL))     AS top_answer,
           MAX(IFF(r.rank_in_list = 1, r.document_number, NULL)) AS top_document_number,
           MIN(IFF(r.document_number = t.expected_document_number, r.rank_in_list, NULL)) AS rank_of_correct
    FROM datum.dev_evals.test_set t
    JOIN datum.dev_evals.extracted_inputs x ON t.case_id = x.case_id
    LEFT JOIN datum.dev_evals.v1_top5 r                   -- LEFT: keep cases that had no search
      ON r.case_id = t.case_id
    GROUP BY t.case_id, t.case_group, t.input_text, t.expected_document_number,
             x.business_name, x.city, x.is_specific
)
SELECT case_id,
       input_text,
       business_name AS extracted_name,
       city          AS extracted_city,
       IFF(is_specific, top_answer, 'NEEDS_MORE_INFO')     AS answer,
       expected_document_number,
       rank_of_correct,
       CASE WHEN expected_document_number = 'NEEDS_MORE_INFO' THEN NOT is_specific   -- right to ask for more
            ELSE COALESCE(top_document_number = expected_document_number, FALSE) END AS top1_correct,
       CASE WHEN expected_document_number = 'NEEDS_MORE_INFO' THEN NOT is_specific
            ELSE COALESCE(rank_of_correct <= 5, FALSE) END                           AS in_top5
FROM per_case
ORDER BY case_id;

-- RESULT 2: v1 scores per group + total (compare: v0 top-1 6/10, recall@5 8/10).
WITH per_case AS (
    SELECT t.case_id, t.case_group, t.expected_document_number, x.is_specific,
           MAX(IFF(r.rank_in_list = 1, r.document_number, NULL)) AS top_document_number,
           MIN(IFF(r.document_number = t.expected_document_number, r.rank_in_list, NULL)) AS rank_of_correct
    FROM datum.dev_evals.test_set t
    JOIN datum.dev_evals.extracted_inputs x ON t.case_id = x.case_id
    LEFT JOIN datum.dev_evals.v1_top5 r ON r.case_id = t.case_id
    GROUP BY t.case_id, t.case_group, t.expected_document_number, x.is_specific
),
scored AS (
    SELECT case_group,
           CASE WHEN expected_document_number = 'NEEDS_MORE_INFO' THEN NOT is_specific
                ELSE COALESCE(top_document_number = expected_document_number, FALSE) END AS top1_correct,
           CASE WHEN expected_document_number = 'NEEDS_MORE_INFO' THEN NOT is_specific
                ELSE COALESCE(rank_of_correct <= 5, FALSE) END                           AS in_top5
    FROM per_case
)
SELECT case_group,
       COUNT(*)               AS cases,
       COUNT_IF(top1_correct) AS top1_correct,
       COUNT_IF(in_top5)      AS in_top5
FROM scored
GROUP BY ROLLUP (case_group)
ORDER BY case_group;


-- Syntax: COALESCE(x, FALSE) returns FALSE when x is NULL (no correct answer in the list). || concatenates text. LIKE 'ABC%' = starts with ABC.

-- Concept: this scores the WHOLE chain (extraction + matching), so an extraction mistake shows up as a search miss. Read it next to the extraction output to know which step failed.

-- Design decision: city is a tie-breaker, not a filter. A company's registered city is its principal address, which can differ from the job site, so filtering on it would wrongly hide the right company. A fixed last sort key (document_number) makes the ranking deterministic.
