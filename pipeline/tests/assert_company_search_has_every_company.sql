-- ---------------------------------------------------------------------------
-- assert_company_search_has_every_company.sql: a SINGULAR test (returns the
-- BAD rows; zero rows = PASS).
--
-- The rule: company_search holds exactly the companies of entity_lookup, no
-- more and no fewer, with the same name, status, dates and address. The app
-- searches company_search and the link models match against entity_lookup,
-- so a company missing from one of them would be a company that has a flag
-- and can't be found, or one that can be found and whose flags can't attach.
--
-- How it checks: a FULL OUTER JOIN keeps a company that is on either side
-- only, and the comparison catches a company whose details differ.
-- `is distinct from` is "<>" that treats two NULLs as equal, so an empty
-- address on both sides is not reported as a difference.
-- ---------------------------------------------------------------------------

select
    coalesce(e.document_number, s.document_number) as document_number,   -- the company with a problem
    case
        when s.document_number is null then 'in entity_lookup, missing from company_search'
        when e.document_number is null then 'in company_search, missing from entity_lookup'
        else 'the two tables disagree about this company'
    end as problem
from {{ ref('entity_lookup') }} as e
full outer join {{ ref('company_search') }} as s
    on s.document_number = e.document_number
where e.document_number is null
   or s.document_number is null
   or e.entity_name         is distinct from s.entity_name
   or e.name_key            is distinct from s.name_key
   or e.status_code         is distinct from s.status_code
   or e.filing_type         is distinct from s.filing_type
   or e.file_date           is distinct from s.file_date
   or e.principal_address_1 is distinct from s.principal_address_1
   or e.principal_city      is distinct from s.principal_city
   or e.principal_state     is distinct from s.principal_state
   or e.principal_zip       is distinct from s.principal_zip
   or e.published_on        is distinct from s.published_on
