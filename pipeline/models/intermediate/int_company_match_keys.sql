-- ---------------------------------------------------------------------------
-- int_company_match_keys.sql: one row per company, with the key other
-- sources are matched on.
--
-- "int_" = the INTERMEDIATE layer. Staging describes each source as it is.
-- Intermediate is where sources meet: a lien's debtor, a license's business
-- name or a party on a recorded document is matched to a company here.
-- Marts then shape the result for the app.
--
-- What this model does: takes every company from entity_lookup and adds
--   match_key   the simplified name minus one trailing legal suffix:
--               "ACME, L.L.C." and "ACME INC" both become "ACME"
--   zip5        the 5-digit ZIP code of the principal address
--   match_key_company_count
--               how many companies, of ANY status, share that match key
--
-- Why count every status (ruling R1): if only active companies were counted,
-- a dissolved company would be invisible, and its old lien would be pinned
-- on a newer company that took the same name.
--
-- Names: this is the only intermediate model allowed to hold a name-like
-- column (name_key). Every name here is a registered business name from the
-- state's corporate register. The link models built on it carry no names
-- (ruling R4); a test checks that.
--
-- Grain: one row per company (document_number is unique).
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_COMPANY_MATCH_KEYS.
-- ---------------------------------------------------------------------------


with companies as (
    -- STEP 1: every company, one row each (entity_lookup already guarantees that).
    select
        document_number,                             -- the state's ID for the company
        name_key,                                    -- the simplified name: capitals, punctuation turned into spaces
        principal_zip,                               -- ZIP code as filed: 5 digits, or ZIP+4
        status_code,                                 -- A = active, I = inactive
        file_date                                    -- the company's filing date on Sunbiz (ruling R2 compares records with it)
    from {{ ref('entity_lookup') }}
),

keyed as (
    -- STEP 2: the match key and the 5-digit ZIP code.
    select
        document_number,
        name_key,

        {{ match_key('name_key') }}                  as match_key,
        -- A macro call (macros/company_matching.sql). It removes ONE trailing
        -- legal suffix (LLC, L L C, INC, CORP, CO, LTD, LP, PA ...) from the
        -- name_key. The link models apply the same macro to source names, so
        -- both sides are simplified by the same rule.

        case
            when regexp_like(left(trim(principal_zip), 5), '[0-9]{5}')
                then left(trim(principal_zip), 5)
        end                                          as zip5,
        -- The first 5 characters, but only when they are 5 digits. A blank or
        -- foreign postal code becomes NULL: "no ZIP code" must never equal
        -- another "no ZIP code". (A case with no else returns NULL.)

        status_code,
        file_date
    from companies
)

-- STEP 3: count the companies that share each match key.
select
    document_number,
    name_key,
    match_key,
    zip5,
    status_code,
    file_date,
    count(*) over (partition by match_key)           as match_key_company_count
    -- A window function: count the rows that have this row's match_key and
    -- write that number on every one of them. Unlike GROUP BY, the rows are
    -- not collapsed. 1 means the name is unique in Florida across active AND
    -- inactive companies.
from keyed
