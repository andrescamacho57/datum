-- ---------------------------------------------------------------------------
-- int_federal_liens_status.sql: is each federal tax lien open or closed?
--
-- The rule (ruling R6): a lien is OPEN if it is in the latest quarterly
-- snapshot or in a daily filings file published after it, and no certificate
-- of release (action code COR) has been published since. The snapshot lists
-- only liens the state considers active, so being in it means "active on the
-- snapshot date"; the daily events files then say what was released after.
--
-- Where the status comes from (ruling R5): the FILINGS file only. The status
-- letter repeated on debtor and secured-party rows is ignored.
--
-- A certificate of DISCHARGE (COD) does not close a lien (ruling R6). A
-- discharge normally frees one piece of property and leaves the lien on the
-- rest, so its date is carried as a fact and the lien stays as it was.
--
-- Records we can't explain produce no flag (ruling R7). They are marked
-- is_unexplained = TRUE here, and the flags mart skips them:
--   - an active lien that carries a cancellation date
--   - a lien with a debtor or secured-party row whose status is C, a value
--     the state's layout does not list
--   - a lien that is still in the active snapshot although a certificate of
--     release was recorded BEFORE the snapshot (two liens: a release, then an
--     amendment, and the state still lists them). This third case is this
--     model's own cautious addition, in the spirit of R7.
--
-- No names: this model reads filings and events, which hold none.
--
-- Grain: one row per lien (filing_doc_number is unique).
-- Becomes the table DATUM.DEV_INTERMEDIATE.INT_FEDERAL_LIENS_STATUS.
-- ---------------------------------------------------------------------------


with filing_rows as (
    -- STEP 1: one row per lien: the newest published row for it.
    select
        filing_doc_number,
        filing_date,
        filing_status,                               -- A active, L lapsed, T terminated (the authority, ruling R5)
        cancellation_date,                           -- NULL on every lien but one
        source_kind,                                 -- 'quarterly' or 'daily'
        published_on,                                -- the date the state published the file the lien is in
        source_file
    from {{ ref('stg_sunbiz__flr_filings') }}
    qualify row_number() over (
        partition by filing_doc_number
        order by published_on desc, loaded_at desc
    ) = 1
),

latest_snapshot as (
    -- STEP 2: the date of the newest quarterly snapshot loaded. Today there
    -- is one (2026-10-03). When the January 2027 snapshot is loaded, a lien
    -- that is only in the older snapshot is no longer "in the latest
    -- snapshot", and STEP 6 closes it.
    select max(published_on) as snapshot_date
    from {{ ref('stg_sunbiz__flr_filings') }}
    where source_kind = 'quarterly'
),

lien_events as (
    -- STEP 3: release and discharge events, one row each. The same event can
    -- sit in more than one file, so the rows are de-duplicated by the
    -- event's own document number, keeping the first time it was published.
    select
        filing_doc_number,                           -- the lien the event acts on
        event_doc_number,
        action_code,                                 -- COR = certificate of release, COD = certificate of discharge
        event_filing_date,                           -- the day the event was filed with the state
        published_on,                                -- the date the state published the file the event is in
        source_file
    from {{ ref('stg_sunbiz__flr_events') }}
    where action_code in ('COR', 'COD')
    qualify row_number() over (
        partition by filing_doc_number, event_doc_number, action_code
        order by published_on, loaded_at
    ) = 1
),

releases as (
    -- STEP 4: per lien, releases split by WHEN they were published compared
    -- with the file the lien itself is in.
    select
        f.filing_doc_number,
        min(case when e.published_on > f.published_on then e.event_filing_date end) as released_on,
        -- A release published AFTER the file that lists the lien: this is
        -- the "later COR" of ruling R6. min = the first one, if several.
        min_by(e.source_file, case when e.published_on > f.published_on then e.event_filing_date end) as release_source_file,
        -- min_by(a, b) returns the value of a on the row where b is
        -- smallest: here, the file holding that first later release. Rows
        -- where b is NULL are ignored.
        max(case when e.published_on <= f.published_on then e.event_filing_date end) as earlier_release_on
        -- A release that was already on record when the state published the
        -- lien as active. See "Records we can't explain" in the header.
    from filing_rows as f
    inner join lien_events as e
        on  e.filing_doc_number = f.filing_doc_number
        and e.action_code = 'COR'
    group by f.filing_doc_number
),

discharges as (
    -- STEP 5: per lien, the latest certificate of discharge, whenever it
    -- was published.
    select
        filing_doc_number,
        max(event_filing_date) as discharge_recorded_on
    from lien_events
    where action_code = 'COD'
    group by filing_doc_number
),

odd_party_rows as (
    -- Liens with a debtor or secured-party row whose status letter is C
    -- (ruling R7). union removes duplicates, so a lien appears once.
    select filing_doc_number from {{ ref('stg_sunbiz__flr_debtors') }} where filing_status = 'C'
    union
    select filing_doc_number from {{ ref('stg_sunbiz__flr_secured') }} where filing_status = 'C'
)

-- STEP 6: one row per lien, open or closed.
select
    f.filing_doc_number,
    f.filing_date,
    f.published_on                                   as lien_published_on,
    -- The date of the state file the lien is in: the snapshot date, or the
    -- date of the daily file that first carried it.

    case
        when f.filing_status <> 'A'                                  then 'closed'
        -- Ruling R5: the filings file says lapsed or terminated.
        when f.source_kind = 'quarterly' and f.published_on < s.snapshot_date then 'closed'
        -- In an older snapshot but not in the latest one: the state has
        -- dropped it from its active list.
        when f.source_kind = 'daily' and f.published_on <= s.snapshot_date    then 'closed'
        -- Filed before the latest snapshot and not in it: same reading.
        when r.released_on is not null                               then 'closed'
        -- A certificate of release was published after the lien (ruling R6).
        else 'open'
    end                                              as lien_status,

    case
        when f.filing_status <> 'A'                                  then 'filing_status_not_active'
        when f.source_kind = 'quarterly' and f.published_on < s.snapshot_date then 'not_in_latest_snapshot'
        when f.source_kind = 'daily' and f.published_on <= s.snapshot_date    then 'not_in_latest_snapshot'
        when r.released_on is not null                               then 'certificate_of_release'
    end                                              as closed_reason,
    -- Why a closed lien is closed. NULL on an open lien.

    r.released_on,
    -- The filing date of the certificate of release that closed it.

    d.discharge_recorded_on,
    -- The date of any certificate of discharge. A fact to show, not a
    -- status: the lien is open or closed regardless of it (ruling R6).

    (   f.cancellation_date is not null
     or o.filing_doc_number is not null
     or (r.earlier_release_on is not null and r.released_on is null)
    )                                                as is_unexplained,
    -- TRUE = ruling R7 applies: produce no flag from this lien.

    case
        when f.cancellation_date is not null then 'cancellation_date_on_an_active_lien'
        when o.filing_doc_number is not null then 'party_row_with_status_c'
        when r.earlier_release_on is not null and r.released_on is null then 'release_recorded_before_the_snapshot_that_lists_it'
    end                                              as unexplained_reason,

    f.source_file                                    as filing_source_file,
    -- The state file the lien row came from (provenance; joins to the fetch manifest).

    r.release_source_file
    -- The state file the closing release came from. NULL on an open lien.

from filing_rows as f
cross join latest_snapshot as s
-- cross join = attach the single snapshot_date row to every lien.
left join releases as r        on r.filing_doc_number = f.filing_doc_number
left join discharges as d      on d.filing_doc_number = f.filing_doc_number
left join odd_party_rows as o  on o.filing_doc_number = f.filing_doc_number
-- LEFT JOINs: most liens have no release, no discharge and no odd row.
