# ADR 0001: lookups read Postgres, and builds run in Snowflake

An ADR (architecture decision record) is a one-page note on one decision: what was chosen, why, what it cost, and when to look at it again. This one records decision d18.

| | |
|---|---|
| **Status** | Decided on Nov 5, 2026 (d18 in `docs/decisions.json`). Built in leg C2 on Nov 20, 2026. One target is not yet met (see "What the first measurements say") |
| **Decided by** | Andres Camacho |
| **Applies to** | `snowflake/23_export_marts.sql`, `src/datum/load_postgres.py`, `src/datum/search.py` |

## The problem

A contractor types a note and expects a shortlist within a few seconds. The data that answers the note is 13 million Florida companies and the flags attached to them, and all of it is built in Snowflake.

Snowflake is a warehouse. It is built for a few heavy queries, it sleeps between them, and it bills for at least 60 seconds every time it wakes. A lookup is the opposite kind of work: a tiny question, at any hour, that must be answered at once.

## The decision

```
Snowflake (builds)                              Postgres (lookups)
  raw → staging → intermediate → marts            company_search, company_flags,
  runs when new data arrives                      company_possible_matches, source_coverage
        │                                               ▲
        └── script 23 unloads four marts ──▶ data/export ──▶ load_postgres.py
            (only rows with is_shown true)                   (new tables, swapped in one transaction)
```

- Snowflake builds the four marts the app reads. It is never asked a question by the app.
- After a build, script 23 copies the four marts out as compressed CSV files, and the loader copies them into Postgres.
- The app reads Postgres only. The search uses the `pg_trgm` extension, which compares names by their three-letter pieces (trigrams).

The two kinds of work have names. OLAP (online analytical processing) is the heavy scanning a warehouse does. OLTP (online transaction processing) is the small, fast lookups an app needs. Copying finished tables from the first kind of system to the second is called reverse ETL (extract, transform, load).

## Why

| Reason | The evidence |
|---|---|
| A lookup against a sleeping warehouse is slow and billed | An X-Small warehouse costs 1 credit an hour and bills at least 60 seconds per wake ✅ (`snowflake/01_cost_guardrails.sql` and the leg reports). That is 1/60 of a credit, about $0.033 at $2 a credit, for one lookup, plus the seconds it takes to wake |
| A lookup against Postgres costs nothing per lookup | The database is always on. On the Mac it is free. Hosted, it is a flat monthly price |
| The app must not depend on the Snowflake trial | The trial ends, and a lookup tool that stops answering when the warehouse is suspended by its resource monitor is not a tool |
| Hidden records should not be reachable from the app at all | The export keeps only rows with `is_shown` true (working rule W9), so a Duval record or a discipline record is not in the app's database. A forgotten filter in the app cannot leak a row the app does not have |

## The cost line

| Item | Rate | Units | Estimate |
|---|---|---|---|
| Snowflake, one export of the four marts | 1 credit an hour, at least 60 seconds per wake, about $2 a credit ✅ | About 1 minute awake per export | About 0.02 to 0.05 credits, 4 to 10 cents, per export 🟡 (leg C2 measured its whole Snowflake use, see its report) |
| Snowflake, answering lookups | The same rate | 0 lookups | $0. This is the saving: at 100 lookups a day spread through the day, waking the warehouse each time would be about $3.30 a day, roughly $100 a month |
| Postgres on the Mac | Free | Always on | $0 a month |
| Postgres on a host, later | 🟡 Railway Hobby is $5 a month including $5 of usage, then by use (the plan's figures of Oct 30, not checked since) | 4.2 GB of data | 🟡 About $5 to $20 a month. The host is Andres's choice and is not part of Phase C |

## What we gave up

- **One more copy of the data.** The marts exist twice, and the Postgres copy is only as fresh as the last export. A report says so through the "data through" date of each source.
- **One more thing to run.** An export and a load after each build: about one minute to unload, one minute to download and four minutes to load 13 million rows and build the indexes.
- **A second search engine to keep honest.** Snowflake ranks every company by Jaro-Winkler similarity. Postgres first picks a pool of candidates by trigram and then ranks that pool by the same Jaro-Winkler rule in Python. The two can disagree, so `python -m evals.run` scores both on the same test set.
- **Disk.** 4.2 GB in Postgres, of which the companies are 3.0 GB, their primary key 0.6 GB and the trigram index 0.6 GB.

## What the first measurements say (Nov 20, 2026)

| Measure | Result |
|---|---|
| Rows in Snowflake and in Postgres | Equal for all four tables ✅ |
| Search quality on the 10-case test set | Postgres: top-1 7, recall at 5 9, wrong_match 2. Snowflake: top-1 6, recall at 5 9, wrong_match 3. Postgres is at least as good on all three ✅ |
| Search speed, target p95 under 1 second | **Not met.** Over 208 searches, the first approach (plain trigram similarity) had a p50 of 5.1 seconds and a p95 of 11.2 seconds. The second (word similarity at a threshold of 0.75) has a p50 of 181 milliseconds and a p95 of 1,229 milliseconds, which is 0.23 seconds over the target ❌ |

The speed target is the open item. Leg C2's report has the numbers, the reason, and the options, and the choice between them is Andres's.

## When to look at this again

- At 100 lookups a day, or when the database outgrows its host (the revisit clause of d18).
- When the search speed target is settled, because the fix may change the shape of the search table.
- If the app ever needs data fresher than the last export. A scheduled export is the next step, and a live connection to the warehouse is not.
