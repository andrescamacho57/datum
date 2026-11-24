-- ---------------------------------------------------------------------------
-- assert_possible_matches_cite_an_approved_search_page.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule (CLAUDE.md rule 3, rulings R9 and R27): a possible match cites
-- the one search page the seed search_page_sources approves for its source.
--
-- The sister test for company_flags only looks at flags that may be shown.
-- Here every row is hidden today, so a test limited to shown rows would look
-- at nothing and could never fail. This one checks every row, shown or not,
-- so the citation is already right on the day a reason is switched on.
-- ---------------------------------------------------------------------------

select
    p.document_number,
    p.flag_type,
    p.source,                                    -- the source with no approved exception, or
    p.source_record_id,
    p.source_url                                 -- the address that is not the approved one
from {{ ref('company_possible_matches') }} as p
left join {{ ref('search_page_sources') }} as a  -- keep every possible match, approved or not
    on  a.source = p.source
    and a.search_page_url = p.source_url
where a.source is null                           -- no approved (source, address) pair behind it
