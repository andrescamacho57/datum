# Datum — Engineering Rules

Product, architecture, and scope: `docs/PROJECT_CONTEXT.md`. Rules only here.
If a rule blocks the task, say so and stop. Don't route around one.

## 1. Code retrieves; the model adjudicates

Deterministic work is plain Python: URL construction, parsing, normalization,
fuzzy candidate scoring, dates, addresses. Anything a test can assert.

Model calls are for genuine ambiguity only, usually whether two candidates are
the same legal entity after the scorer fails to separate them. Say in the commit
what ambiguity it resolves that a rule cannot.

## 2. Business and public records only

Registries, court judgments, liens, UCC filings. Never personal credit on an
owner or guarantor — that's FCRA and we have no permissible purpose. Crossing
that line needs legal review first, not a code change.

Public ≠ scrapeable. Check terms of use before writing a retriever, quote the
clause in `docs/access/<source>.md`, respect robots.txt and rate limits.

Surface what the record says, never a conclusion about the business.

## 3. Every fact carries a source URL and a UTC fetch timestamp

Schema-level, not convention: a fact type constructible without both is a bug in
the type. The URL points at the specific record. Derived values carry their
inputs' provenance. No score without the underlying facts shown.

Resolution returns `CONFIRMED` / `AMBIGUOUS` / `NO_MATCH`. Never collapse it to a
boolean, never fill a gap with an inference. Track `wrong_match`.

## 4. Fixtures only. No network in tests.

The suite runs offline, no credentials. Parsers test against real responses
committed under `tests/fixtures/`, each recording its origin and capture date.
Refresh fixtures in their own commit. Don't mock what you can fixture.

## 5. One concern per commit, with its test

No refactor mixed with a behavior change, no fixture refresh mixed with a parser
fix. New logic arrives with its test. Find something unrelated mid-task — note
it, finish the current concern first.

## Commands that prove work

Run these and show the output before claiming something works.

- Activate env: `source .venv/bin/activate`
- dbt, from `pipeline/`: `cd pipeline && dbt build --select <model>`
- Snowflake script: `snow sql -c datum -f snowflake/NN_name.sql`
- Tests: `pytest`
- Secrets live in `.env`, `~/.dbt/profiles.yml`, `~/.snowflake/` and `*.p8` files. Never read them.
- Review: `REVIEW.md` sets the risk tier of a change and what a reviewer must check before a pull request opens.
