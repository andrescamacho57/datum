{#
  ---------------------------------------------------------------------------
  flag_rules.sql: the MACROS that turn a linked record into a flag row, for
  the two sources whose flags may be shown today.

  What a macro is: a named, reusable piece of SQL. A model calls it inside
  double curly braces, and dbt pastes the macro's SQL in its place before
  sending the query to Snowflake.

  Why these are macros: two marts must apply the SAME rules.
      company_flags             a record on a CONFIRMED link is a flag
      company_possible_matches  a record on an AMBIGUOUS link that WOULD be a
                                shown flag if the link were CONFIRMED
                                (Phase C working rule W3)
  "Would be a flag" only means something if both marts read one definition
  of a flag: which liens are left out (ruling R7), which licenses count as
  inactive, what the fact, the status note, the citation and the caveat say.
  Written twice, the two copies would drift, and a possible match could then
  show a lien that the flags mart leaves out.

  What the calling model must provide: both macros produce the body of one
  CTE, and that body reads two CTEs the caller defines before it.
      manifest             source, source_file, fetched_at_utc: one row per
                           fetched file (from stg_datum__fetch_manifest)
      lien_files_through   one row, one column, through_date: the date of
                           the newest federal lien file loaded
  (CTE = common table expression, a named step inside one query.)

  The SQL below was moved here from models/marts/company_flags.sql without a
  change. The leg report of leg C1 shows the row count and checksum of
  company_flags before and after the move.
  ---------------------------------------------------------------------------
#}


{% macro federal_lien_flag_rows() %}
    {#- One row per federal tax lien per company it is linked to (rulings R5
        to R9). Reads the caller's CTEs `manifest` and `lien_files_through`. -#}
    select distinct
        l.document_number,
        'federal_tax_lien'                           as flag_type,
        s.filing_date                                as fact_date,
        -- The day the lien was filed with the Florida Department of State.

        s.lien_status                                as status,
        -- open or closed (ruling R6).

        nullif(array_to_string(array_construct_compact(
            case when s.released_on is not null
                 then 'Certificate of release filed ' || to_char(s.released_on, 'YYYY-MM-DD') || '.' end,
            case when s.discharge_recorded_on is not null
                 then 'Certificate of discharge recorded on ' || to_char(s.discharge_recorded_on, 'YYYY-MM-DD') || '.' end
        ), ' '), '')                                 as status_note,
        -- The events on the lien, as facts. array_construct_compact builds a
        -- list and drops the NULLs; array_to_string joins what is left with
        -- a space; nullif turns an empty result into NULL. A discharge is
        -- stated, not interpreted (ruling R6).

        'sunbiz_flr'                                 as source,
        s.filing_doc_number                          as source_record_id,
        '{{ var("sunbiz_lien_search_url") }}'        as source_url,
        -- No per-record link exists for a federal lien (ruling R9): this is
        -- the state's search page, and the filing number finds the record.
        'Florida Department of State federal lien filing ' || s.filing_doc_number as citation,
        s.filing_source_file                         as source_file,

        greatest(mf.fetched_at_utc, coalesce(mr.fetched_at_utc, mf.fetched_at_utc)) as fetched_at,
        -- The later of two fetch times: the file the lien came from and, if
        -- the lien is closed, the file its release came from. greatest
        -- returns NULL if either side is NULL, so coalesce gives it the
        -- first value again when there is no release.

        'Open or closed is read from the state''s federal lien files published through '
            || to_char(t.through_date, 'YYYY-MM-DD')
            || '. A release filed after that date is not reflected. The state''s files carry no dollar amount.' as caveat,
        -- Two single quotes inside a text value make one apostrophe.

        true                                         as is_shown
    from {{ ref('int_federal_lien_links') }} as l
    inner join {{ ref('int_federal_liens_status') }} as s
        on s.filing_doc_number = l.source_record_id
    cross join lien_files_through as t
    left join manifest as mf
        on mf.source = 'sunbiz_flr' and mf.source_file = s.filing_source_file
    left join manifest as mr
        on mr.source = 'sunbiz_flr' and mr.source_file = s.release_source_file
    where l.link_status = 'CONFIRMED'
      and not s.is_unexplained
      -- Ruling R7: a lien with a cancellation date, a status-C party row or
      -- an unexplained earlier release produces no flag.
    -- select distinct: a lien with two debtors that are both CONFIRMED as
    -- the same company is still ONE flag.
{% endmacro %}


{% macro dbpr_license_flag_rows() %}
    {#- One row per INACTIVE contractor license per company it is linked to
        (rulings R11 and R27). Reads the caller's CTE `manifest`. -#}
    select distinct
        ll.document_number,
        'dbpr_license_inactive'                      as flag_type,
        lic.effective_date                           as fact_date,
        -- When the license's current period, and so its current status, began.

        'inactive'                                   as status,
        'License ' || lic.alternate_license_number || ': inactive'
            || coalesce(', expires ' || to_char(lic.expiration_date, 'YYYY-MM-DD'), '')
            || '.'                                   as status_note,
        -- License number, status and expiry: the business fact (ruling R11).
        -- Never the license holder's name.

        'dbpr'                                       as source,
        lic.alternate_license_number                 as source_record_id,
        '{{ var("dbpr_license_search_url") }}'       as source_url,
        -- DBPR offers no link to one license (ruling R27): this is its own
        -- "verify a license" search page, and the license number finds the record.
        'Florida DBPR license ' || lic.alternate_license_number as citation,
        lic.source_file,
        m.fetched_at_utc                             as fetched_at,
        'From DBPR''s construction licensee file, which leaves out delinquent, null-and-void and involuntarily inactive licenses. A license is held by a person who qualifies the business; this line is about the license, not the person.' as caveat,
        true                                         as is_shown
    from {{ ref('int_dbpr_license_links') }} as ll
    inner join {{ ref('stg_dbpr__licenses') }} as lic
        on  lic.alternate_license_number = ll.source_record_id
        and lic.record_kind = 'contractor_license'
    left join manifest as m
        on m.source = 'dbpr' and m.source_file = lic.source_file
    where ll.link_status = 'CONFIRMED'
      and lic.secondary_status = 'I'
      -- I = inactive in DBPR's file. A = active is not a flag. QB business
      -- records never reach here: the state gives them no active/inactive
      -- status that says "inactive".
{% endmacro %}
