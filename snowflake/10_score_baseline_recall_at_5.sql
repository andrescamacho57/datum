-- 10_score_baseline_recall_at_5.sql: same baseline search as 09, scored two ways.
--   top-1 correct : was the FIRST answer the right company?            (09 said 60%)
--   recall@5      : was the right company ANYWHERE in the first 5?     (what a shortlist UI needs)
-- The app will show a short list for the contractor to confirm, so recall@5 is the honest measure.
-- Run:  snow sql -c datum -f snowflake/10_score_baseline_recall_at_5.sql   (🟡 1-3 minutes)

USE ROLE SYSADMIN;                                        -- owner role
USE WAREHOUSE datum_wh;                                   -- cost-capped warehouse

CREATE OR REPLACE TEMPORARY TABLE datum.dev_evals.baseline_top5 AS  -- scratch table for this session
WITH tests AS (
    SELECT case_id,
           case_group,
           input_text,
           expected_document_number,
           TRIM(REGEXP_REPLACE(UPPER(input_text), '[^A-Z0-9]+', ' ')) AS input_key  -- same cleaning as name_key
    FROM datum.dev_evals.test_set
)
SELECT t.case_id,
       t.case_group,
       t.input_text,
       t.expected_document_number,
       e.document_number,
       e.entity_name,
       JAROWINKLER_SIMILARITY(t.input_key, e.name_key) AS similarity,          -- 0-100 string likeness
       ROW_NUMBER() OVER (PARTITION BY t.case_id ORDER BY similarity DESC) AS rank_in_list
       -- rank_in_list: 1 = most similar company for this input, 2 = runner-up, ...
FROM tests t
CROSS JOIN datum.dev_marts.entity_lookup e                -- every input against every company
QUALIFY rank_in_list <= 5;                                -- keep the top 5 per input

-- RESULT 1: per case — top answer, and where (if anywhere) the right company landed.
SELECT case_id,
       case_group,
       input_text,
       MAX(IFF(rank_in_list = 1, entity_name, NULL))    AS top_answer,
       -- IFF(condition, a, b) = a when true, else b. MAX over the group just picks out the one non-NULL value.
       MAX(IFF(rank_in_list = 1, similarity, NULL))     AS top_similarity,
       MAX(IFF(rank_in_list = 2, similarity, NULL))     AS runner_up_similarity,
       -- the gap between these two is a confidence signal we'll test later
       MIN(IFF(document_number = expected_document_number, rank_in_list, NULL)) AS rank_of_correct
       -- the position of the right company in the top 5; NULL = not in the top 5
FROM datum.dev_evals.baseline_top5
GROUP BY case_id, case_group, input_text
ORDER BY case_id;

-- RESULT 2: the two scores per group, plus a grand total (ROLLUP).
WITH per_case AS (
    SELECT case_id,
           case_group,
           MIN(IFF(document_number = expected_document_number, rank_in_list, NULL)) AS rank_of_correct
    FROM datum.dev_evals.baseline_top5
    GROUP BY case_id, case_group
)
SELECT case_group,
       COUNT(*)                                    AS cases,
       COUNT_IF(rank_of_correct = 1)               AS top1_correct,
       COUNT_IF(rank_of_correct <= 5)              AS in_top5,
       ROUND(100 * COUNT_IF(rank_of_correct <= 5) / COUNT(*)) AS recall_at_5_pct
FROM per_case
GROUP BY ROLLUP (case_group)
ORDER BY case_group;


-- Syntax: QUALIFY can filter on a window-function column defined in the same SELECT (rank_in_list). IFF is Snowflake's two-way if. COUNT_IF counts rows where the condition is TRUE; a NULL rank never counts.

-- Concept: recall@k = share of cases where the right answer appears in the first k results. It measures a SHORTLIST, the way search engines are measured. NEEDS_MORE_INFO cases can never pass here: "ask for more" needs a confidence rule we haven't built yet, so they stay honest failures.

-- Design decision: suffix stripping (LLC/INC) was considered for this step and NOT built. Computed offline first: it doesn't flip any test case (KROM PROPERTIES still outscores KROMAH PROPERTY, 98 vs 95). Build what moves the number.
