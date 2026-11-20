{#
  ---------------------------------------------------------------------------
  company_matching.sql: the MACROS that link a source record to a company.

  What a macro is: a named, reusable piece of SQL. A model calls it inside
  double curly braces, and dbt pastes the macro's SQL in its place before
  sending the query to Snowflake. Everything between the curly-brace-hash
  marks, like this block, is a Jinja comment: dbt removes it, so Snowflake
  never sees it.

  Why these are macros and not SQL repeated in each model: four link models
  (federal liens, DBPR licenses, DBPR discipline, Duval parties) must apply
  the SAME rule. Linking a lien to the wrong company is the most expensive
  mistake Datum can make (decision d19), so the rule lives in exactly one
  place, where one review and one set of tests covers all four.

  The rule itself is rulings R1, R2, R29 and R30 in docs/phase_b_rulings.md.

  To see the SQL a macro produces: run `dbt compile --select <model>` from
  pipeline/ and open the file under pipeline/target/compiled/.
  ---------------------------------------------------------------------------
#}


{% macro name_key(column) -%}
    {#- A simplified name: capitals, with every run of punctuation and spaces
        turned into one space. "Acme, L.L.C." becomes "ACME L L C". This is the
        same expression entity_lookup uses for its name_key column, so a source
        name and a company name are simplified the same way. -#}
    trim(regexp_replace(upper({{ column }}), '[^A-Z0-9]+', ' '))
{%- endmacro %}


{% macro legal_suffixes() -%}
    {#- The legal-form endings removed from the END of a name to make its match
        key, written the way they look inside a name_key (L.L.C. is "L L C").
        Longer forms come first, so "P L L C" is tried before "L L C".
        Kept to legal forms only (R1: "LLC, INC, CORP, CO, LTD, LP, LLP, PLLC,
        PA, PC and similar"). Words such as ASSOCIATION, TRUST or GROUP are part
        of a name, not a legal form, and stay. -#}
    L L L P|P L L C|L L C|L L P|INCORPORATED|CORPORATION|COMPANY|LIMITED|LLLP|PLLC|LLC|LLP|INC|CORP|LTD|PLC|CO|LC|LP|PA|PC|PL|L C|L P|P A|P C|P L
{%- endmacro %}


{% macro entity_words() -%}
    {#- The words that mark a name as a business (R1: "the source name contains
        a legal-entity word"). Shorter than the suffix list on purpose: the
        two-letter spaced forms (L C, L P, P A, P C, P L) are left out, because
        in a person's name they can be two initials ("SMITH L C"), and reading
        initials as "this is a company" is the mistake R1 exists to prevent. -#}
    P L L C|L L C|INCORPORATED|CORPORATION|COMPANY|LIMITED|LLLP|PLLC|LLC|LLP|INC|CORP|LTD|PLC|CO|LC|LP|PA|PC|PL
{%- endmacro %}


{% macro match_key(name_key_column) -%}
    {#- The name_key minus ONE trailing legal suffix: "ACME L L C" and
        "ACME INC" both become "ACME". Only one suffix is removed, so
        "ACME CO INC" becomes "ACME CO", not "ACME".
        The pattern reads: a space, one of the suffixes, then $ = the end of
        the text. A name that IS only a suffix ("INC") has no space before it
        and is left alone. -#}
    trim(regexp_replace({{ name_key_column }}, ' ({{ legal_suffixes() }})$', ''))
{%- endmacro %}


{% macro namesake_key(match_key_column) -%}
    {#- A LOOSER key than the match key, used only to COUNT near-namesakes
        (ruling R30). It is never used to find a record's company: that is
        still the match key's job. Two companies whose names differ only in
        the ways below get the same namesake key, and a record filed against
        one name can't be pinned on one of two such companies.
        Read the four steps from the inside out:
          1. every whole word AND becomes a space. A name_key has already
             turned & into a space, so "A AND B" and "A & B" now look the
             same. \\b means "the edge of a word", so the AND inside
             "SANDY" stays. The backslash is typed twice because SQL text
             uses one backslash to escape the next character.
          2. runs of spaces left by step 1 become one space, and the ends
             are trimmed.
          3. a leading THE is removed: "THE ACME" becomes "ACME".
          4. EVERY trailing legal suffix is removed, where the match key
             removed only one: "ACME CO" (from ACME CO INC) becomes "ACME".
             The + after the group means "one or more of these in a row".
        A name that IS only a suffix, or only THE, is left alone, as in
        match_key. A match key that is only the word AND becomes an empty
        namesake key, which it shares with any other such name. That can
        only make a link AMBIGUOUS, never CONFIRMED. -#}
    trim(regexp_replace(
        regexp_replace(
            trim(regexp_replace(
                regexp_replace({{ match_key_column }}, '\\bAND\\b', ' '),
                ' +', ' ')),
            '^THE ', ''),
        '( ({{ legal_suffixes() }}))+$', ''))
{%- endmacro %}


{% macro has_entity_word(name_key_column) -%}
    {#- TRUE when the name contains a legal-entity word as a whole word.
        regexp_like must match the WHOLE text, so the pattern is: optionally
        anything followed by a space, then one of the words, then optionally a
        space followed by anything. "ACME INC OF FLORIDA" is TRUE; "LINCOLN"
        is FALSE, because INC there is inside a longer word. -#}
    regexp_like({{ name_key_column }}, '(.* )?({{ entity_words() }})( .*)?')
{%- endmacro %}


{% macro link_to_companies(names_relation, use_zip) %}
    {#-
      The linking rule (R1, R2, R29 and R30), as the tail of a query. A link
      model prepares one CTE of source names and calls this macro after it.

      names_relation: the name of a CTE with exactly these columns
          source_record_id   the source record's identifier (a lien number, a license number ...)
          party_seq          which party on that record (1 when the record has one name)
          source_name_key    the party's name, simplified with name_key(); used here and NOT output (R4)
          source_zip5        the party's ZIP code as staging has it: 5 digits when it is good, NULL when
                             the source gave none, and anything else when the source's ZIP code is malformed
          source_date        the record's date
      use_zip: true when the source carries an address. false for Duval, whose
          records have none, so only the unique-name branch applies (R3).

      One output row per source party per candidate company:
          CONFIRMED  exactly one row for that party
          AMBIGUOUS  one row per company that has the party's match key. A near-namesake that
                     blocked the link (R30) is counted, and it is not added as a row of its own
          NO_MATCH   one row, document_number NULL
    -#}
    keyed as (
        -- Turn each source name into the same match key companies have.
        select
            source_record_id,
            party_seq,
            source_date,
            {% if use_zip -%}
            case when regexp_like(source_zip5, '[0-9]{5}') then source_zip5 end as source_zip5,
            -- Only a real 5-digit ZIP code is kept for matching. regexp_like
            -- must match the WHOLE text, so '3225' and '3225-' both fail.
            source_zip5 is not null
                and trim(source_zip5) <> ''
                and not regexp_like(source_zip5, '[0-9]{5}') as source_zip_is_unreadable,
            -- Here source_zip5 is the column as the link model sent it, not
            -- the cleaned value on the line above. When a column and a new
            -- name made in the same SELECT share a name, Snowflake reads the
            -- column. The R29 unit tests fail if that ever stops being true.
            -- Ruling R29: TRUE when the source DID give a ZIP code, but it is
            -- not 5 digits. That is different from giving none. An empty ZIP
            -- code (NULL, or only spaces) says "nothing to compare", while a
            -- malformed one says "there was something here that we can't
            -- read", and so the row can't be confirmed on its name alone.
            {%- else -%}
            cast(null as varchar) as source_zip5,
            -- This source has no address: every row takes the unique-name branch (R3).
            false as source_zip_is_unreadable,
            -- With no ZIP code column at all, there is nothing to misread.
            {%- endif %}
            {{ match_key('source_name_key') }} as source_match_key,
            {{ namesake_key(match_key('source_name_key')) }} as source_namesake_key,
            -- The looser key of ruling R30, made from the match key. It is
            -- used below only to count near-namesakes, never to match.
            {{ has_entity_word('source_name_key') }} as source_has_entity_word
        from {{ names_relation }}
    ),

    company_namesake_keys as (
        -- Ruling R30, step 1: every company's namesake key, next to its ZIP
        -- code. One row per company.
        select
            {{ namesake_key('match_key') }} as namesake_key,
            zip5
        from {{ ref('int_company_match_keys') }}
    ),

    company_namesakes as (
        -- Ruling R30, step 2: how many companies share each namesake key at
        -- each ZIP code. One row per namesake key per ZIP code. Companies
        -- with no ZIP code form a group of their own (zip5 is NULL), which
        -- the same-ZIP join below can never pick up, because NULL = NULL is
        -- not true in SQL.
        select
            namesake_key,
            zip5,
            count(*) as company_count
        from company_namesake_keys
        group by namesake_key, zip5
    ),

    namesakes_anywhere as (
        -- Ruling R30, step 3: the same counts added up over every ZIP code,
        -- including the companies with none. One row per namesake key:
        -- how many companies in Florida, of any status, share it.
        select
            namesake_key,
            sum(company_count) as company_count
        from company_namesakes
        group by namesake_key
    ),

    candidates as (
        -- Every company whose match key equals the source's. A LEFT JOIN, so
        -- a source party with no such company is kept, with NULLs on the
        -- company side: that row becomes NO_MATCH.
        select
            k.source_record_id,
            k.party_seq,
            k.source_date,
            k.source_zip5,
            k.source_zip_is_unreadable,
            k.source_has_entity_word,
            c.document_number,
            c.zip5      as company_zip5,
            c.file_date as company_file_date,
            count(c.document_number) over (partition by k.source_record_id, k.party_seq) as candidate_count,
            -- How many companies share this party's match key. count(column)
            -- skips NULLs, so a party with no company gets 0.
            count_if(c.zip5 = k.source_zip5) over (partition by k.source_record_id, k.party_seq) as same_zip_count,
            -- How many of those companies are also at the party's ZIP code.
            -- "over (partition by ...)" computes the count per source party
            -- and writes it on each of that party's rows (a window function).
            a.company_count as namesake_count,
            -- Ruling R30: how many companies anywhere in Florida share the
            -- party's NAMESAKE key. Every company with the party's match key
            -- has the same namesake key too, because the namesake key is
            -- made from the match key. So this count is never smaller than
            -- candidate_count, and it is larger exactly when a near-namesake
            -- exists.
            z.company_count as namesake_same_zip_count
            -- Ruling R30: how many of those companies are at the party's ZIP
            -- code. NULL when the party has no usable ZIP code.
        from keyed as k
        left join {{ ref('int_company_match_keys') }} as c
            on  c.match_key = k.source_match_key
            and k.source_match_key <> ''
            -- An empty key (a name made only of punctuation) matches nothing.
        left join namesakes_anywhere as a
            on a.namesake_key = k.source_namesake_key
        left join company_namesakes as z
            on  z.namesake_key = k.source_namesake_key
            and z.zip5 = k.source_zip5
        -- Both of these joins find at most one row for a party, and so they
        -- add columns without adding rows.
    ),

    r1 as (
        -- Ruling R1, as one label per row. Read the branches top to bottom:
        -- the first one that fits wins.
        select
            *,
            case
                when document_number is null then 'no_company_with_this_match_key'
                -- No company in Florida, of any status, has this match key.

                when source_zip_is_unreadable then 'zip_unreadable'
                -- Ruling R29: the source gave a ZIP code that is not 5 digits.
                -- The row can't take the ZIP code branches below, because
                -- there is no ZIP code to compare. It doesn't take the
                -- unique-name branch either, because that branch is only for
                -- a source that gave no ZIP code at all. Every company with
                -- this match key is offered as a possible match.

                when source_zip5 is not null and same_zip_count = 1 and company_zip5 = source_zip5
                     and namesake_same_zip_count = 1 then 'name_zip'
                -- The source has a ZIP code, and exactly one company with this
                -- match key is at that ZIP code: this row is that company.
                -- Ruling R30 adds the last condition: that company must also
                -- be the only one at that ZIP code with the looser namesake
                -- key. The test is "= 1" and not "not more than 1" on
                -- purpose, so that a missing count can never confirm a link.

                when source_zip5 is not null and same_zip_count = 1 and company_zip5 = source_zip5 then 'several_similar_names_same_zip'
                -- Ruling R30: same as above, except that a near-namesake (a
                -- name that differs only by a leading THE, by AND versus &,
                -- or by trailing legal suffixes) is at the same ZIP code. The
                -- record can't be pinned on one of the two.

                when source_zip5 is not null and same_zip_count = 1 then 'drop_other_zip'
                -- Same party, but this row is a namesake at ANOTHER ZIP code.
                -- The ZIP code already singled out one company, so the
                -- namesakes are dropped below, not offered as possible matches.

                when source_zip5 is not null and same_zip_count > 1 then 'several_companies_same_zip'
                -- Two or more companies share the match key AND the ZIP code:
                -- the address can't tell them apart.

                when source_zip5 is not null then 'zip_differs'
                -- The name matches, but no company with this match key is at
                -- the source's ZIP code. R1's unique-name branch is only for
                -- sources WITHOUT a ZIP code, so this is never CONFIRMED.

                -- From here down is the unique-name branch. A row only gets
                -- this far when the source gave no ZIP code at all.

                when candidate_count > 1 then 'several_companies'
                -- No ZIP code to go on, and more than one company (of any
                -- status) has this match key.

                when not source_has_entity_word then 'no_entity_word'
                -- One company has this match key, but the source name has no
                -- LLC / INC / CORP ... It may be a person whose name equals a
                -- company's once "LLC" is stripped.

                when namesake_count = 1 then 'unique_name'
                -- No ZIP code, exactly one company in Florida has this match
                -- key, and the source name carries a legal-entity word.
                -- Ruling R30 adds this condition: that company is also the
                -- only one in Florida with the looser namesake key.

                else 'several_similar_names'
                -- Ruling R30: one company has this match key, but another
                -- company somewhere in Florida is a near-namesake of it.
            end as r1_outcome
        from candidates
    ),

    decided as (
        -- Ruling R2 on top of R1: a record dated before the company's own
        -- filing date on Sunbiz is never CONFIRMED.
        select
            source_record_id,
            party_seq,
            document_number,
            source_date,
            case
                when r1_outcome = 'no_company_with_this_match_key' then 'NO_MATCH'
                when r1_outcome not in ('name_zip', 'unique_name')  then 'AMBIGUOUS'
                when source_date is null or company_file_date is null then 'AMBIGUOUS'
                -- R2 can't be checked without both dates. Unknown is not
                -- "after", so the link is not confirmed.
                when source_date < company_file_date                then 'AMBIGUOUS'
                -- The record is older than the company: a company can't owe a
                -- lien from before it existed. Usually a dissolved company
                -- whose name a newer one took.
                else 'CONFIRMED'
            end as link_status,
            case
                when r1_outcome not in ('name_zip', 'unique_name')            then r1_outcome
                when source_date is null or company_file_date is null         then 'date_unknown'
                when source_date < company_file_date                          then 'before_company_filed'
                else r1_outcome
            end as link_reason
            -- WHY the row got its status: the R1 branch, or the R2 reason that
            -- overrode it. For a CONFIRMED row it equals matched_on.
        from r1
        where r1_outcome <> 'drop_other_zip'
    )

    select
        source_record_id,
        party_seq,
        document_number,
        -- The company's Sunbiz document number. NULL on a NO_MATCH row.
        link_status,
        -- CONFIRMED, AMBIGUOUS or NO_MATCH. Never a yes/no (CLAUDE.md rule 3).
        case when link_status = 'CONFIRMED' then link_reason end as matched_on,
        -- name_zip or unique_name on a CONFIRMED row; NULL otherwise.
        link_reason,
        source_date
        -- The source record's date, carried so R2 can be re-checked by a test.
    from decided
{% endmacro %}
