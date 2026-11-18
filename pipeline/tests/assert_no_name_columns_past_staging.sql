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
-- intermediate schema and returns any whose name looks like it holds a name.
-- So a model can't gain a debtor_name or party_name column by accident: the
-- build fails the moment one appears.
--
-- The one exception: int_company_match_keys, whose name_key holds registered
-- business names from the state's corporate register.
--
-- What it can't see: a name hidden inside a column called something else.
-- The link models' headers say what each column holds; review covers that.
--
-- The depends_on lines below are how dbt learns to run this test AFTER the
-- intermediate models are built. They are comments to Snowflake, and dbt
-- reads the ref() calls inside them. Add a line when a new intermediate
-- model is added.
-- ---------------------------------------------------------------------------

-- depends_on: {{ ref('int_company_match_keys') }}
-- depends_on: {{ ref('int_federal_lien_links') }}
-- depends_on: {{ ref('int_dbpr_license_links') }}
-- depends_on: {{ ref('int_dbpr_discipline_links') }}
-- depends_on: {{ ref('int_duval_party_links') }}
-- depends_on: {{ ref('int_federal_liens_status') }}
-- depends_on: {{ ref('int_duval_document_status') }}

{% set a_model = ref('int_company_match_keys') %}
{#- set stores a value in a Jinja variable. Here it is the relation object for
    one intermediate model, which knows the database and schema it was built
    in. Every intermediate model is built in the same schema. -#}

select
    table_name,                                  -- the model with the offending column
    column_name                                  -- the column whose name looks like a name
from {{ a_model.database }}.information_schema.columns
-- The catalogue of every column in the DATUM database.
where upper(table_schema) = upper('{{ a_model.schema }}')
-- Only the intermediate schema (DEV_INTERMEDIATE). upper() on both sides
-- because Snowflake stores names in capitals.
  and table_name <> 'INT_COMPANY_MATCH_KEYS'     -- the one allowed exception
  and (   column_name ilike '%NAME%'             -- ilike = like, ignoring upper/lower case; % = any text
       or column_name ilike '%LICENSEE%'
       or column_name ilike '%RESPONDENT%'
       or column_name ilike '%DBA%')
