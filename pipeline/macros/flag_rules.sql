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

  How a model uses them: the two flag macros each produce the body of one
  CTE, and that body reads two CTEs that the calling model defines first,
  with the two small macros at the top of this file.
      manifest             source, source_file, fetched_at_utc and
                           is_approximate: one row per fetched file. Its
                           body is the macro fetch_manifest_rows
      lien_files_through   one row, one column, through_date: the date of
                           the newest federal lien file loaded. Its body is
                           the macro lien_files_through_rows
  (CTE = common table expression, a named step inside one query.)
  So a calling model starts like this, with each call inside double curly
  braces:
      with manifest as ( fetch_manifest_rows() ),
      lien_files_through as ( lien_files_through_rows() ),
      some_name as ( federal_lien_flag_rows() ),
      another_name as ( dbpr_license_flag_rows() )

  A note on the Jinja in the two flag macros: a tag written with a dash,
  such as "if" opened by curly-brace-percent-dash, removes the line break
  next to it. So the comma that joins the last column to link_reason is
  attached to a line of SQL on purpose. Attached to a line that ends in a
  "--" comment, it would become part of the comment and break the query.

  The SQL below was moved here from models/marts/company_flags.sql without a
  change, and the column fetched_at_is_approximate was added afterwards, in
  a commit of its own. The leg report of leg C1 shows the row count and
  checksum of company_flags before and after each of the two steps.
  ---------------------------------------------------------------------------
#}


{% macro fetch_manifest_rows() %}
    {#- When each source file was fetched, and whether that time is an
        estimate (ruling R23). One row per fetched file. -#}
    select
        source,
        source_file,
        fetched_at_utc,
        is_approximate
        -- TRUE when fetched_at_utc is a file's modification time and not a
        -- measured fetch. It becomes fetched_at_is_approximate on each flag.
    from {{ ref('stg_datum__fetch_manifest') }}
{% endmacro %}


{% macro lien_files_through_rows() %}
    {#- The date of the newest federal lien file loaded. The lien caveat says
        "published through" this date, so both marts must read one value. -#}
    select max(published_on) as through_date
    from {{ ref('stg_sunbiz__flr_events') }}
{% endmacro %}


{% macro federal_lien_flag_rows(possible_match=false) %}
    {#- One row per federal tax lien per company it is linked to (rulings R5
        to R9). Reads the caller's CTEs `manifest` and `lien_files_through`.
        possible_match: false (the default) reads CONFIRMED links, for
        company_flags. true reads AMBIGUOUS links, for
        company_possible_matches, and then two things change and nothing
        else: is_shown comes from the seed possible_match_reasons, and the
        link's reason code is added as the last column. -#}
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

        {% if possible_match -%}
        coalesce(pr.is_shown, false)                 as is_shown,
        -- A possible match is shown only when the seed possible_match_reasons
        -- says its reason may be shown. coalesce makes a reason that is
        -- missing from the seed hidden, not unknown.
        {%- else -%}
        true                                         as is_shown,
        {%- endif %}

        mf.is_approximate or coalesce(mr.is_approximate, false) as fetched_at_is_approximate
        {%- if possible_match %},{% endif %}
        -- TRUE when the fetch time above rests on an estimate: the file the
        -- lien came from, or the file its release came from, has a fetch
        -- time taken from a modification time (ruling R23). Either one is
        -- enough, because the fact rests on both files. coalesce turns the
        -- NULL of "no release" into FALSE, so an open lien is judged on its
        -- own file alone.
        {% if possible_match -%}
        l.link_reason
        -- WHY the link is AMBIGUOUS (zip_differs, before_company_filed ...).
        {%- endif %}
    from {{ ref('int_federal_lien_links') }} as l
    inner join {{ ref('int_federal_liens_status') }} as s
        on s.filing_doc_number = l.source_record_id
    cross join lien_files_through as t
    left join manifest as mf
        on mf.source = 'sunbiz_flr' and mf.source_file = s.filing_source_file
    left join manifest as mr
        on mr.source = 'sunbiz_flr' and mr.source_file = s.release_source_file
    {% if possible_match -%}
    left join {{ ref('possible_match_reasons') }} as pr
        on pr.link_reason = l.link_reason
    where l.link_status = 'AMBIGUOUS'
    {%- else -%}
    where l.link_status = 'CONFIRMED'
    {%- endif %}
      and not s.is_unexplained
      -- Ruling R7: a lien with a cancellation date, a status-C party row or
      -- an unexplained earlier release produces no flag.
    -- select distinct: a lien with two debtors that are both linked to the
    -- same company in the same way is still ONE row.
{% endmacro %}


{% macro dbpr_license_flag_rows(possible_match=false) %}
    {#- One row per INACTIVE contractor license per company it is linked to
        (rulings R11 and R27). Reads the caller's CTE `manifest`.
        possible_match: the same switch as in federal_lien_flag_rows. -#}
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
        {% if possible_match -%}
        coalesce(pr.is_shown, false)                 as is_shown,
        {%- else -%}
        true                                         as is_shown,
        {%- endif %}
        m.is_approximate                             as fetched_at_is_approximate
        {%- if possible_match %},{% endif %}
        -- TRUE when the license file's fetch time is an estimate (ruling R23).
        {% if possible_match -%}
        ll.link_reason
        -- WHY the link is AMBIGUOUS.
        {%- endif %}
    from {{ ref('int_dbpr_license_links') }} as ll
    inner join {{ ref('stg_dbpr__licenses') }} as lic
        on  lic.alternate_license_number = ll.source_record_id
        and lic.record_kind = 'contractor_license'
    left join manifest as m
        on m.source = 'dbpr' and m.source_file = lic.source_file
    {% if possible_match -%}
    left join {{ ref('possible_match_reasons') }} as pr
        on pr.link_reason = ll.link_reason
    where ll.link_status = 'AMBIGUOUS'
    {%- else -%}
    where ll.link_status = 'CONFIRMED'
    {%- endif %}
      and lic.secondary_status = 'I'
      -- I = inactive in DBPR's file. A = active is not a flag. QB business
      -- records never reach here: the state gives them no active/inactive
      -- status that says "inactive".
{% endmacro %}
