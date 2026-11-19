-- ---------------------------------------------------------------------------
-- assert_hidden_flags_stay_hidden.sql: a SINGULAR test (returns the BAD
-- rows; zero rows = PASS).
--
-- The rule: two kinds of flag are built and NOT displayed until someone with
-- the authority says otherwise.
--   Duval flags        hidden until the Clerk answers on terms of use
--                      (ruling R20, project variable show_duval)
--   DBPR discipline    hidden until counsel has reviewed it
--                      (ruling R12, project variable show_dbpr_discipline)
--
-- Ruling R28: this test compares is_shown to the word false written HERE,
-- not to the project variables. company_flags reads the variables; if this
-- test read them too, it would agree with whatever they say, and flipping
-- one line in dbt_project.yml would show 14,000 hidden flags with every
-- test still green. Written this way, un-hiding a source takes two reviewed
-- edits: the variable, and the matching line below.
--
-- When counsel or the Clerk clears a source: flip its variable AND change
-- its line below from "false" to "true", in one pull request, citing the
-- ruling that allows it.
--
-- The last line catches the opposite mistake: a federal lien or license
-- flag hidden by accident.
-- ---------------------------------------------------------------------------

select
    document_number,
    flag_type,
    source_record_id,
    is_shown
from {{ ref('company_flags') }}
where (source = 'duval'              and is_shown is distinct from false)   -- ruling R20
   or (flag_type = 'dbpr_discipline' and is_shown is distinct from false)   -- ruling R12
   -- "is distinct from false" is "<> false" that also catches NULL: a plain
   -- <> comparison with NULL is neither true nor false, so a NULL would slip by.
   or (flag_type in ('federal_tax_lien', 'dbpr_license_inactive') and not is_shown)
