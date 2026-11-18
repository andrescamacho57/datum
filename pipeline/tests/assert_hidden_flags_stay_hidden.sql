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
-- Both variables default to false in dbt_project.yml. This test fails if a
-- flag's is_shown disagrees with its switch, in either direction, and if a
-- federal lien or license flag is ever hidden by accident.
--
-- var('name') in double curly braces is replaced by the variable's value
-- before the query runs, so today the two comparisons read "is_shown <> False".
-- ---------------------------------------------------------------------------

select
    document_number,
    flag_type,
    source_record_id,
    is_shown
from {{ ref('company_flags') }}
where (source = 'duval'                and is_shown <> {{ var('show_duval') }})
   or (flag_type = 'dbpr_discipline'   and is_shown <> {{ var('show_dbpr_discipline') }})
   or (flag_type in ('federal_tax_lien', 'dbpr_license_inactive') and not is_shown)
