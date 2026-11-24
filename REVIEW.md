# REVIEW.md: how a change gets reviewed in Datum

`CLAUDE.md` holds the rules. This file tells a reviewer, human or agent, what to look for and how to report it. It follows the layered approach in Anthropic's "How the Claude Code team does code review" (Oct 2026): ask what could go wrong with this change and which check should catch it, not whether a person read every line.

## What failure looks like in this repo

| Failure | In one word | Example |
|---|---|---|
| A report says something false about a company | it accuses | A lien linked to the wrong company; a released lien shown as open; wording that draws a conclusion |
| A person's data gets past staging | it leaks | A name column in an intermediate model; a person's name in a fixture, sample file or report |
| A load loses or doubles rows without saying so | it miscounts | Rows loaded differ from the source's own total; a file loaded twice |
| A check that cannot fail | it reassures | A filter in `WHERE` that removes the rows the test was meant to count |
| A fact with no source | it asserts | A flag row without `source_url` or `fetched_at` |
| A secret or personal detail lands in git | it exposes | A key, a password, a personal email or phone number. The repo is public |
| A change spends money by surprise | it bills | A new or resized warehouse, a removed resource monitor, a paid service |

## Risk tiers

The change sets the tier, not the author. A pull request takes the highest tier of any file it touches. When this table changes, the pull request that changes it lists, under "What a person should look at", every open pull request whose tier rises under the new table, and each of those gets the review its new tier calls for before it merges.

| Tier | Paths | AI review | What Andres does |
|---|---|---|---|
| **High** | `pipeline/macros/`, `pipeline/models/intermediate/`, `pipeline/models/marts/`, `pipeline/seeds/` (allowlists and maps), `pipeline/dbt_project.yml`, `src/datum/report.py`, `.claude/`, `.github/`, `CLAUDE.md`, `REVIEW.md`, `docs/prompts/`, `docs/review_process.md`, `docs/phase_b_rulings.md`, `docs/mvp_plan_nov8.md`, any other file that is a brief for an unattended agent wherever it is saved, anything that decides `is_shown` or the wording on a report | Deep: three reviewers in parallel, then a verifier | Reads the report and the diff, explains the change back, answers three questions |
| **Medium** | `src/datum/` (other files), `snowflake/`, `pipeline/models/staging/`, `pipeline/tests/`, app code | Standard: one reviewer, plus a security pass when `src/` changed | Reads the leg report and the review findings, skims the diff |
| **Low** | `docs/` (except the paths named under High), the study guide `*.md` files at the root, `tests/` (tests and fixtures only), comments | Quick: one pass | Nothing once the checks are green. Merges it |

A High pull request that changes only instructions (`docs/prompts/`, `docs/review_process.md`, `docs/phase_b_rulings.md`, `docs/mvp_plan_nov8.md`, `REVIEW.md`, `CLAUDE.md`, `.claude/`, `.github/`) has no links, data or tests for the usual three hunts to find. Its three reviewers hunt these instead of the three named in section 3 of `docs/prompts/florida_master.md`: a step an unattended agent cannot carry out without asking, or two rules that contradict each other; a guardrail made weaker without saying so (a stop condition, a privacy or cost limit, a review depth or a tier); and a stale fact, a wrong path or a file that does not exist.

### Why each path is in its tier

The tier answers one question: if this change is wrong, how far does the mistake travel before anyone notices?

- **High** means the mistake reaches a contractor, or it changes the rules that catch mistakes or the instructions an unattended agent builds from.
  - `intermediate/`, `marts/`, `macros/` and `seeds/` are where records get linked to a company and turned into flags. A mistake here is how Datum would accuse the wrong company, or reassure someone about the right one.
  - `report.py`, `is_shown` and the report wording decide what a contractor actually reads.
  - `dbt_project.yml` changes how every model is built, so one line can change all of them.
  - `.claude/`, `.github/`, `CLAUDE.md` and `REVIEW.md` are the guardrails. A mistake here weakens the checking of every later change.
  - `docs/prompts/`, `docs/review_process.md` and `docs/phase_b_rulings.md` are the instructions an unattended agent follows: what to build, which rulings bind it, when to stop, and how its own work is reviewed. They sit under `docs/`, and they are not documentation. A change to them changes what every later run does, so Andres reads it. A new brief belongs in `docs/prompts/`. A brief saved anywhere else is still High, and the reviewer reports where it was saved as a finding.
  - `docs/mvp_plan_nov8.md` is High as a whole. Section 2 of the brief tells every run to read it first, its spec A1–A12 and decisions d15–d21 say what to build, and the flags table in its section 4 is report wording that the brief copies word for word.
  - Other files under `docs/` also guide an agent: `docs/open_questions.md` (its working rules), `docs/access/` (the terms of use for each source) and `docs/legs/` (earlier leg reports, which later runs read). They stay Low for now, because most legs write to them and raising them would make every leg High. A leg's own review covers what it wrote to `docs/open_questions.md` and `docs/access/`. Reviewers skip the text of `docs/legs/` reports (see "Skip these"), and the last review round checks the `## Human review` section against the diff instead. A pull request that changes a working rule or a terms-of-use finding outside a leg says so under "What a person should look at".
- **Medium** means the mistake stays inside the pipeline, where a test or a later layer can still catch it before it is shown. Loaders, staging views and Snowflake scripts are here. They can still leak a secret or spend money, which is why Python changes get a security pass.
- **Low** means nothing a contractor sees and nothing that runs in the pipeline can change. Docs, tests and comments are here, apart from the docs named under High.

One high-tier line outweighs fifty low-tier lines because harm comes from the riskiest thing a change touches, not from how much it touches.

## How to review

1. Read the pull request's stated intent and its leg report, or, for a pull request with no leg report, its Human review section and the template. Judge the change against that intent: does it solve the problem, does it fit the system, does it break something that worked?
2. Read the diff against the whole repo, not on its own. For a bug fix, look for the root cause.
3. Report findings. Every finding has:
   - **Evidence:** a file and a line, with the line quoted. Never a guess from a file or column name.
   - **A tag:** `Important` (would cause one of the failures above), `Nit` (worth fixing, never blocks), or `Pre-existing` (the problem was there before this change).
   - **The check that would catch it:** the test or count that fails when this is wrong.
4. Start the summary with a count: `3 findings: 1 Important, 2 Nit.` When there is nothing to fix, say exactly `0 findings: nothing to fix.`

## Limits

- At most 3 nits per review.
- No style opinions the rules do not cover. No praise. No restating the diff.
- Never repeat a finding already posted. When one bug has several instances, report the class once and list every instance.
- **Three rounds at most.** After the first round, review only the new diff. If Important findings remain after round three, stop and say the approach needs rethinking.
- Every Important finding is answered: fixed, or closed with a one-line reason.

## Skip these

`data/`, `target/`, `logs/`, the contents of `tests/fixtures/`, and the text of `docs/legs/` reports. Check that a fixture has no person's name in it; don't review its rows.

## Questions every review answers

1. For each new test: what input would make it fail? If none, it is a finding.
2. Do loaded row counts equal the source's own totals, and is the command shown?
3. Does any model past staging carry a name column or a person's name?
4. Does every flag row trace to a CONFIRMED link, and carry `source_url`, `fetched_at` and a record identifier?
5. Do Duval rows past staging stay inside the type allowlist?
6. Does the diff add a secret, an email address, a phone number or a street address of a person?
7. Does any Snowflake statement alter or drop an existing object, or use a warehouse other than `datum_wh`?
8. Does anything touch a source's terms of use or the FCRA (Fair Credit Reporting Act)? Flag it. Don't decide it.

## The security pass

Run `/security-review` when `src/` changes. In the downloaders, look for: certificate checks switched off, a server key accepted without pinning, a secret printed or logged, a shell command built from input, and a file written outside `data/`.
