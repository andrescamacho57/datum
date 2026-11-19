-- ---------------------------------------------------------------------------
-- assert_company_flags_one_row_per_flag.sql: a SINGULAR test (returns the
-- BAD rows; zero rows = PASS).
--
-- The rule: a company has a given record as a given kind of flag at most
-- once. A lien with two debtors that both resolve to the same company is
-- one flag, not two; a report that counted it twice would say "2 flags" for
-- one lien.
-- ---------------------------------------------------------------------------

select
    document_number,                             -- the company
    flag_type,                                   -- the kind of flag
    source_record_id,                            -- the record it is about
    count(*) as times_seen                       -- how many rows say so
from {{ ref('company_flags') }}
group by document_number, flag_type, source_record_id
having count(*) > 1                              -- keep only the duplicates
