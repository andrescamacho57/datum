-- ---------------------------------------------------------------------------
-- assert_no_name_columns_past_staging.sql: a SINGULAR test (returns the BAD
-- rows; zero rows = PASS).
--
-- The rule (ruling R4): no person's name goes past staging. A link model
-- carries the source record's identifier, the company's document number and
-- the outcome, and never the source's raw name.
--
-- How it checks: it doesn't look at data, it looks at the tables' SHAPE.
-- Snowflake keeps a catalogue of every table and column in a schema called
-- information_schema. This test lists the columns of every table in the
-- INTERMEDIATE schema and in the MARTS schema, and returns any whose name
-- looks like it holds a name. So a model can't gain a debtor_name or
-- party_name column by accident: the build fails the moment one appears.
--
-- The marts schema is scanned too because the mart is what the app reads:
-- company_flags is one step from a report, so a name column there matters
-- most of all.
--
-- The three exceptions, each named below, each a table of REGISTERED BUSINESS
-- names from the state's corporate register, never a person's name:
--   INT_COMPANY_MATCH_KEYS   (intermediate)  name_key
--   ENTITY_LOOKUP            (marts)         entity_name, name_key: the
--                            company's own name, which a report has to show
--   COMPANY_SEARCH           (marts)         entity_name and name_key, and
--                            ONLY those two columns. It is the copy of the
--                            company register that the app searches (leg C1).
--                            Any other name-like column there still fails.
-- A new exception needs a reason written here, not just a line in the query.
--
-- Which column names count: any that contain NAME, LICENSEE, RESPONDENT or
-- DBA, and (since the review of leg C1) any that contain a role a person can
-- hold: DEBTOR, OFFICER, AGENT, OWNER, HOLDER, QUALIF, GRANT or PARTY.
--
-- What it can't see: a name hidden inside a column called something else.
-- The link models' headers say what each column holds; review covers that.
--
-- The depends_on lines below are how dbt learns to run this test AFTER the
-- models are built. They are comments to Snowflake, and dbt reads the ref()
-- calls inside them. Add a line when a new intermediate or mart model is
-- added.
-- ---------------------------------------------------------------------------

-- depends_on: {{ ref('int_company_match_keys') }}
-- depends_on: {{ ref('int_federal_lien_links') }}
-- depends_on: {{ ref('int_dbpr_license_links') }}
-- depends_on: {{ ref('int_dbpr_discipline_links') }}
-- depends_on: {{ ref('int_duval_party_links') }}
-- depends_on: {{ ref('int_federal_liens_status') }}
-- depends_on: {{ ref('int_duval_document_status') }}
-- depends_on: {{ ref('entity_lookup') }}
-- depends_on: {{ ref('company_flags') }}
-- depends_on: {{ ref('company_search') }}
-- depends_on: {{ ref('company_possible_matches') }}
-- depends_on: {{ ref('source_coverage') }}

{% set an_intermediate_model = ref('int_company_match_keys') %}
{% set a_mart_model = ref('company_flags') %}
{#- set stores a value in a Jinja variable. Each of these is the relation
    object for one model, which knows the database and schema it was built
    in. Every intermediate model is built in one schema and every mart in
    another, so one model of each kind is enough to find both schemas. -#}

select
    table_schema,                                -- DEV_INTERMEDIATE or DEV_MARTS
    table_name,                                  -- the model with the offending column
    column_name                                  -- the column whose name looks like a name
from {{ an_intermediate_model.database }}.information_schema.columns
-- The catalogue of every column in the DATUM database.
where (
        (    upper(table_schema) = upper('{{ an_intermediate_model.schema }}')
         and table_name <> 'INT_COMPANY_MATCH_KEYS' )   -- the one allowed exception in intermediate
     or (    upper(table_schema) = upper('{{ a_mart_model.schema }}')
         and table_name <> 'ENTITY_LOOKUP'              -- an allowed exception in marts: the whole table
         and not (table_name = 'COMPANY_SEARCH' and column_name in ('ENTITY_NAME', 'NAME_KEY')) )
         -- The other allowed exception in marts, and a narrower one: only
         -- the company's own two name columns. `not (a and b)` is true for
         -- every other column of COMPANY_SEARCH, so those are still scanned.
      )
-- upper() on both sides because Snowflake stores names in capitals.
  and (   column_name ilike '%NAME%'             -- ilike = like, ignoring upper/lower case; % = any text
       or column_name ilike '%LICENSEE%'
       or column_name ilike '%RESPONDENT%'
       or column_name ilike '%DBA%'
       -- Added in the review of leg C1: a person can also sit in a column
       -- named for a ROLE and not for a name. None of these words is in any
       -- column today.
       or column_name ilike '%DEBTOR%'
       or column_name ilike '%OFFICER%'
       or column_name ilike '%AGENT%'
       or column_name ilike '%OWNER%'
       or column_name ilike '%HOLDER%'
       or column_name ilike '%QUALIF%'           -- qualifier, qualifying agent: the person who holds a license for a business
       or column_name ilike '%GRANT%'            -- grantor, grantee: the two sides of a recorded document
       or (column_name ilike '%PARTY%' and column_name <> 'PARTY_SEQ'))
       -- PARTY_SEQ is the one allowed PARTY column: the link models' number
       -- for which party on a record a row is about (1, 2, 3 ...), not a name.
