-- ---------------------------------------------------------------------------
-- assert_duval_flags_respect_the_allowlist.sql: a SINGULAR test (returns the
-- BAD rows; zero rows = PASS).
--
-- The rule (ruling R16), checked on the finished flags, independently of the
-- models that built them:
--   1. Every Duval flag is about a document whose type code is on the
--      allowlist as a "flag" code (LN, WRT, JDG, CCCJUDG). Anything else,
--      including every criminal, family and personal record type, must not
--      appear.
--   2. No flagged JUDGMENT has the State of Florida on the FRM side: that is
--      the mark of a criminal or fines matter.
--
-- This test goes back to STAGING for the document's type and its parties, so
-- it does not trust the intermediate models it is checking.
-- ---------------------------------------------------------------------------

with documents as (
    -- One row per document: the newest daily file wins (same rule as the models).
    select
        instrument_number,
        doc_type_code
    from {{ ref('stg_duval__documents') }}
    qualify row_number() over (
        partition by instrument_number
        order by file_date desc, loaded_at desc
    ) = 1
),

state_on_frm_side as (
    -- Documents with the State of Florida as a FRM party, in any file. The
    -- name is simplified the same way the link model does, then compared;
    -- it is not selected.
    select distinct instrument_number
    from {{ ref('stg_duval__parties') }}
    where party_role = 'FRM'
      and (   {{ name_key('party_name') }} = 'FLORIDA STATE OF'
           or {{ name_key('party_name') }} like 'FLORIDA STATE OF %'
           or {{ name_key('party_name') }} = 'STATE OF FLORIDA')
),

duval_flags as (
    select document_number, flag_type, source_record_id
    from {{ ref('company_flags') }}
    where source = 'duval'
)

select
    f.document_number,
    f.flag_type,
    f.source_record_id,
    d.doc_type_code,
    case
        when a.doc_type_code is null then 'type code is not an allowlisted flag code'
        else 'judgment with the State of Florida on the FRM side'
    end as problem
from duval_flags as f
left join documents as d
    on d.instrument_number = f.source_record_id
left join {{ ref('duval_doc_type_allowlist') }} as a
    on  a.doc_type_code = d.doc_type_code
    and a.used_for = 'flag'
left join state_on_frm_side as s
    on s.instrument_number = f.source_record_id
where a.doc_type_code is null                    -- rule 1 broken (also true when the document can't be found)
   or (d.doc_type_code in ('JDG', 'CCCJUDG') and s.instrument_number is not null)   -- rule 2 broken
