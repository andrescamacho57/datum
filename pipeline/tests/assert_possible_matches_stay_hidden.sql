-- ---------------------------------------------------------------------------
-- assert_possible_matches_stay_hidden.sql: a SINGULAR test (returns the BAD
-- rows; zero rows = PASS).
--
-- The rule (Phase C working rule W3): every possible match is hidden until
-- Andres rules on which reasons for an AMBIGUOUS link are safe to show. A
-- record that predates the company, or one filed under a name with no
-- legal-entity word, could accuse the wrong company or surface a person's
-- record. That is a matching and privacy call, and it is his.
--
-- Ruling R28, applied here: this test compares is_shown to the word false
-- written HERE, not to the seed possible_match_reasons. The mart reads the
-- seed. If this test read it too, it would agree with whatever the seed
-- says, and changing one cell of a CSV file would show thousands of possible
-- matches with every test still green. Written this way, showing a reason
-- takes two reviewed edits: the seed row, and this test.
--
-- When Andres rules that a reason may be shown: set its seed row to true AND
-- add a line below that lets that one reason through, in one pull request,
-- citing the ruling. For example:
--     where is_shown is distinct from false
--       and link_reason <> 'zip_differs'        -- ruling Rnn
-- A reason let through there must then be checked the other way round as
-- well, the way assert_hidden_flags_stay_hidden does for the shown flags.
-- ---------------------------------------------------------------------------

select
    document_number,
    flag_type,
    source_record_id,
    link_reason,
    is_shown
from {{ ref('company_possible_matches') }}
where is_shown is distinct from false
-- "is distinct from false" is "<> false" that also catches NULL: a plain <>
-- comparison with NULL is neither true nor false, so a NULL would slip by.
