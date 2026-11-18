-- ---------------------------------------------------------------------------
-- assert_fetch_manifest_one_row_per_file.sql: a SINGULAR test (returns the
-- BAD rows; zero rows = PASS).
--
-- The rule: stg_datum__fetch_manifest holds each file once per source.
-- The raw manifest table can hold a file many times (the manifest is
-- reloaded whole whenever it grows), so this proves the de-duplication in
-- the staging model works. A fact joined to a manifest with two rows for
-- its file would be doubled.
-- ---------------------------------------------------------------------------

select
    source,                                      -- which source
    source_file,                                 -- the file that appears more than once
    count(*) as times_seen                       -- how many times
from {{ ref('stg_datum__fetch_manifest') }}
group by source, source_file                     -- one group per file per source
having count(*) > 1                              -- keep only the duplicates
