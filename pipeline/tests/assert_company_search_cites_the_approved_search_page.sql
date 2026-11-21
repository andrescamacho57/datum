-- ---------------------------------------------------------------------------
-- assert_company_search_cites_the_approved_search_page.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule (CLAUDE.md rule 3, ruling R9): a company's source URL is the one
-- address the seed search_page_sources approves for the source sunbiz_cor,
-- which is Sunbiz's search-by-document-number page.
--
-- Why a seed and not the project variable: company_search reads its address
-- from a variable in dbt_project.yml. A test that read the same variable
-- would agree with whatever it says (the reasoning of ruling R28). Written
-- this way, changing the address takes two reviewed edits: the variable and
-- the seed.
--
-- The output is grouped by address, so a wrong address returns one row with
-- a count and not 13 million rows. If the seed lost its sunbiz_cor row, the
-- join would find nothing and every address would be reported.
-- ---------------------------------------------------------------------------

select
    c.source_url,                                -- the address that is not the approved one
    count(*) as companies                        -- how many companies carry it
from {{ ref('company_search') }} as c
left join {{ ref('search_page_sources') }} as a  -- keep every company, approved or not
    on  a.source = 'sunbiz_cor'
    and a.search_page_url = c.source_url
where a.source is null                           -- no approved address behind this row
group by c.source_url
