-- ---------------------------------------------------------------------------
-- assert_shown_flags_cite_an_approved_search_page.sql: a SINGULAR test
-- (returns the BAD rows; zero rows = PASS).
--
-- The rule (CLAUDE.md rule 3): a fact's source URL points at the specific
-- record. No source we use offers a link to one record, so three rulings
-- each allow ONE search page instead, together with the number a reader
-- types into it: R9 (federal liens), R21 (Duval), R27 (DBPR). Those three
-- exceptions are the rows of the seed search_page_sources.
--
-- This test fails for any flag that may be SHOWN whose source is not in the
-- seed, or whose source_url is not the exact address the seed approves for
-- that source. So a new source cannot reach a report citing a search page
-- nobody ruled on, and an address cannot change in one place only.
--
-- Why a seed and not the project variables: company_flags reads its
-- addresses from the variables in dbt_project.yml. A test that read the same
-- variables would agree with whatever they say (the reasoning of ruling
-- R28). Changing an address therefore takes two reviewed edits: the variable
-- and the seed.
--
-- When a source starts offering a link to one record (the "revisit" of R9,
-- R21 and R27), this test will fail on purpose: rewrite it then.
-- ---------------------------------------------------------------------------

select
    f.document_number,
    f.flag_type,
    f.source,                                    -- the source with no approved exception, or
    f.source_record_id,
    f.source_url                                 -- the address that is not the approved one
from {{ ref('company_flags') }} as f
left join {{ ref('search_page_sources') }} as a  -- keep every flag, approved or not
    on  a.source = f.source
    and a.search_page_url = f.source_url
where f.is_shown                                 -- only what a contractor can see
  and a.source is null                           -- no approved (source, address) pair behind it
