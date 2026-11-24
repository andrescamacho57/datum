-- ---------------------------------------------------------------------------
-- assert_flags_mark_an_estimated_fetch_time.sql: a SINGULAR test (returns the
-- BAD rows; zero rows = PASS).
--
-- The rule (working rule W1, ruling R23): a flag whose fetch time is an
-- estimate says so. fetched_at_is_approximate must be TRUE whenever the file
-- the flag's record came from has an estimated fetch time in the manifest.
--
-- Why this test exists next to the not_null test: not_null only proves the
-- column has a value. A model that wrote FALSE on every row would pass it,
-- and the report would then say "fetched Nov 12" about a time nobody
-- measured. This test recomputes the mark for the record's own file and
-- compares.
--
-- What it does not recompute: a closed lien and a closed Duval document also
-- depend on the file their release came from, and the mart marks the flag
-- when EITHER file's time is an estimate. So the mark may be TRUE while this
-- test's file is measured, and that is allowed. The opposite is not: the
-- mark may never be FALSE while the record's own file is estimated.
-- ---------------------------------------------------------------------------

select
    f.document_number,
    f.flag_type,
    f.source_record_id,
    f.source_file,                               -- the file whose fetch time is an estimate
    f.fetched_at_is_approximate                  -- FALSE or NULL here, which is the problem
from {{ ref('company_flags') }} as f
inner join {{ ref('stg_datum__fetch_manifest') }} as m
    on  m.source = f.source
    and m.source_file = f.source_file
where m.is_approximate                           -- the record's own file has an estimated fetch time ...
  and f.fetched_at_is_approximate is distinct from true   -- ... and the flag does not say so
