-- 12_score_search_v2.sql: test two changes to search v1, one at a time, in ONE run.
--   v1  : what we scored on 10/27 (re-computed here as the control)
--   v2a : change 1 only. A vague note still gets searched; ask for more info ONLY if no
--         registered name matches the extracted name exactly (ignoring LLC/INC/CORP...).
--   v2b : change 1 + change 2. Among the top 20 similar names, a city match ranks first.
-- Pattern: RETRIEVE candidates once (the expensive 130M comparisons), then RE-RANK them
-- several ways (cheap). Real search engines are built the same way.
-- Run:  snow sql -c datum -f snowflake/12_score_search_v2.sql   (🟡 1-3 minutes)

USE ROLE SYSADMIN;                                        -- owner role
USE WAREHOUSE datum_wh;                                   -- cost-capped warehouse

-- STEP 1 — RETRIEVE: the 20 most similar company names for every test case.
CREATE OR REPLACE TEMPORARY TABLE datum.dev_evals.v2_candidates AS
WITH cases AS (
    SELECT t.case_id,
           t.case_group,
           t.input_text,
           t.expected_document_number,
           x.is_specific,                                 -- the LLM's "does this name a business?"
           TRIM(REGEXP_REPLACE(UPPER(x.business_name), '[^A-Z0-9]+', ' ')) AS search_key,
           UPPER(TRIM(x.city))                                             AS city_key
    FROM datum.dev_evals.test_set t
    JOIN datum.dev_evals.extracted_inputs x ON t.case_id = x.case_id
)
SELECT c.*,                                               -- every column from cases
       e.document_number,
       e.entity_name,
       e.principal_city,
       JAROWINKLER_SIMILARITY(c.search_key, e.name_key) AS similarity,
       IFF(c.city_key <> '' AND UPPER(e.principal_city) LIKE c.city_key || '%', 1, 0) AS city_match,
       IFF(REGEXP_REPLACE(e.name_key,
               '( (L L C|LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LP|LLP|LLLP|PA|PLLC))+$', '')
           = REGEXP_REPLACE(c.search_key,
               '( (L L C|LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LP|LLP|LLLP|PA|PLLC))+$', ''),
           1, 0) AS exact_name
       -- 1 when the names are identical once a trailing legal suffix is removed:
       -- "REALLY GOOD BEER LLC" -> "REALLY GOOD BEER". ( ... )+$ = one or more suffixes at the END.
FROM cases c
CROSS JOIN datum.dev_marts.entity_lookup e                -- every case against all 13M companies
QUALIFY ROW_NUMBER() OVER (PARTITION BY c.case_id
                           ORDER BY similarity DESC, e.document_number) <= 20;  -- keep 20 per case

-- STEP 2 — RE-RANK: two orderings over the same 20 candidates (cheap: 200 rows).
CREATE OR REPLACE TEMPORARY TABLE datum.dev_evals.v2_ranked AS
SELECT *,
       ROW_NUMBER() OVER (PARTITION BY case_id
                          ORDER BY similarity DESC, city_match DESC, document_number) AS rank_name_first,
       -- v1 ordering: name similarity decides; city only breaks exact ties
       ROW_NUMBER() OVER (PARTITION BY case_id
                          ORDER BY city_match DESC, similarity DESC, document_number) AS rank_city_first
       -- v2b ordering: any candidate in the right city beats every candidate outside it
FROM datum.dev_evals.v2_candidates;

-- STEP 3 — DECIDE + SCORE each variant per case.
CREATE OR REPLACE TEMPORARY TABLE datum.dev_evals.v2_scored AS
WITH per_case AS (
    SELECT case_id, case_group, input_text, expected_document_number, is_specific,
           MAX(exact_name)                                                              AS has_exact_name,
           MAX(IFF(rank_name_first = 1, entity_name, NULL))                             AS top_name_first,
           MAX(IFF(rank_city_first = 1, entity_name, NULL))                             AS top_city_first,
           MIN(IFF(document_number = expected_document_number, rank_name_first, NULL))  AS pos_name_first,
           MIN(IFF(document_number = expected_document_number, rank_city_first, NULL))  AS pos_city_first
    FROM datum.dev_evals.v2_ranked
    GROUP BY case_id, case_group, input_text, expected_document_number, is_specific
),
decided AS (
    SELECT *,
           NOT is_specific                            AS ask_v1,   -- v1: vague note -> always ask
           NOT is_specific AND has_exact_name = 0     AS ask_v2,   -- v2: ask only if nothing matches exactly
           expected_document_number = 'NEEDS_MORE_INFO' AS should_ask
    FROM per_case
)
SELECT *,
       IFF(should_ask, ask_v1, NOT ask_v1 AND COALESCE(pos_name_first = 1,  FALSE)) AS v1_top1,
       IFF(should_ask, ask_v1, NOT ask_v1 AND COALESCE(pos_name_first <= 5, FALSE)) AS v1_top5,
       IFF(should_ask, ask_v2, NOT ask_v2 AND COALESCE(pos_name_first = 1,  FALSE)) AS v2a_top1,
       IFF(should_ask, ask_v2, NOT ask_v2 AND COALESCE(pos_name_first <= 5, FALSE)) AS v2a_top5,
       IFF(should_ask, ask_v2, NOT ask_v2 AND COALESCE(pos_city_first = 1,  FALSE)) AS v2b_top1,
       IFF(should_ask, ask_v2, NOT ask_v2 AND COALESCE(pos_city_first <= 5, FALSE)) AS v2b_top5
       -- Read each line as: if the right answer is "ask for more", did this variant ask?
       -- Otherwise: did it NOT ask, AND was the right company at #1 (or in the top 5)?
FROM decided;

-- RESULT 1: per case, what changed.
SELECT case_id, input_text, is_specific, has_exact_name,
       top_name_first, pos_name_first,
       top_city_first, pos_city_first,
       v1_top1, v2a_top1, v2b_top1
FROM datum.dev_evals.v2_scored
ORDER BY case_id;

-- RESULT 2: the scoreboard (counts out of each group; NULL group = total).
SELECT case_group,
       COUNT(*)            AS cases,
       COUNT_IF(v1_top1)   AS v1_top1,   COUNT_IF(v1_top5)   AS v1_top5,
       COUNT_IF(v2a_top1)  AS v2a_top1,  COUNT_IF(v2a_top5)  AS v2a_top5,
       COUNT_IF(v2b_top1)  AS v2b_top1,  COUNT_IF(v2b_top5)  AS v2b_top5
FROM datum.dev_evals.v2_scored
GROUP BY ROLLUP (case_group)
ORDER BY case_group;


-- Syntax: c.* selects every column of c. ( A | B )+$ in a regex = one or more of A or B at the end of the text. IFF(cond, x, y) returns x or y; booleans combine with AND / NOT.

-- Concept: retrieve-then-rerank. Step 1 does the expensive search once and keeps a small candidate pool; steps 2-3 try different ranking and decision rules on that pool for almost no cost. It also makes each change measurable on its own (v2a vs v2b).

-- Design decisions: (1) "Exact name match" is a rule, not a tuned threshold: no number was chosen by looking at the test cases. (2) 20 candidates is a pool size, not a tuned score; city-first can only promote companies already similar enough to be in the pool. (3) Suffix stripping is built now because a real case needs it (exact_name), not before.
