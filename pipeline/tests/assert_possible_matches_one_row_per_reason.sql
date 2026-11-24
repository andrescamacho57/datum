-- ---------------------------------------------------------------------------
-- assert_possible_matches_one_row_per_reason.sql: a SINGULAR test (returns
-- the BAD rows; zero rows = PASS).
--
-- The rule: a company has a given record as a given kind of possible match,
-- for a given reason, at most once. This is the grain of the mart. A lien
-- whose two debtors are both AMBIGUOUS for the same company for the same
-- reason is one row, not two.
-- ---------------------------------------------------------------------------

select
    document_number,                             -- the company
    flag_type,                                   -- the kind of record
    source_record_id,                            -- the record
    link_reason,                                 -- why the link is AMBIGUOUS
    count(*) as times_seen                       -- how many rows say so
from {{ ref('company_possible_matches') }}
group by document_number, flag_type, source_record_id, link_reason
having count(*) > 1                              -- keep only the duplicates
