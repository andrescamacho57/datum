# How code review works in Datum (adopted Nov 18, 2026)

Source: Anthropic, "How the Claude Code team does code review" (Oct 15, 2026), https://claude.dev/blog/solving-code-review-at-anthropic/. Its core idea: "did a human read the code?" is a weak stand-in for "what could go wrong with this change, and which check, automated or human, is the right one to catch it?"

The goal here is the article's goal, scaled to one person: most pull requests merge with Andres as the only human in the loop, his attention goes to the High-tier changes, and reverts do not go up.

## The layers, and where Datum stands

| # | Layer | In Datum | State |
|---|---|---|---|
| 1 | Work is verified before a pull request exists | Each leg has done-when checks with pasted output. Stop hook runs `ruff` and `dbt parse`. The `reviewer` subagent reviews the diff in a fresh context | Checks: in place since Nov 6. Fresh-context review: required from Nov 18 (`docs/prompts/florida_master.md`, section 3) |
| 2 | AI review on every pull request | The author agent runs `reviewer` subagents on Opus at the depth the tier calls for, before opening the pull request | From Nov 18. A hosted reviewer on GitHub is a later step (see "Not yet") |
| 3 | Security review that can block | `/security-review` when `src/` changes | From Nov 18 |
| 4 | Automated checks on every pull request | `.github/workflows/ci.yml` runs on every pull request: lint, tests, the secrets-hook test and the Stop-hook test. There is no secret scan yet (see "Not yet"). The checks do not block a merge yet. A red check is a signal, and the merge button still works, because blocking waits on branch protection for `main` (see "Not yet") | Checks: from Nov 18. The Stop-hook test: from Nov 19. Blocking: not yet |
| 5 | Human approval, scaled by risk | Three tiers by path in `REVIEW.md`. Low merges on green checks. High gets an explain-back | From Nov 18. Before that the tier was chosen per leg by feel |
| 6 | Safe merge and gradual release | One leg per branch. Duval and discipline flags ship switched off (`show_duval`, `show_dbpr_discipline`). Every pull request says how to revert | Flags: in place. Revert notes: from Nov 18 |
| 7 | Fast detection and rollback | dbt tests on every build; the hand check of 20 links before anything is shown | In place. No users yet, so no incidents yet |

## What each pull request goes through

```
agent builds the leg -> done-when checks pass -> tier set from REVIEW.md
   -> fresh-context AI review at that depth (3 rounds at most, findings answered)
   -> pull request opens with the template filled in -> CI runs
   -> Low: merge on green | Medium: read report + findings, skim | High: explain it back
   -> row added to docs/review_log.csv
```

## What we measure

`docs/review_log.csv` has one row per pull request. The Datum Roadmap dashboard's Reviews tab reads it.

| Measure | Why |
|---|---|
| Human depth per pull request (explain-back, report-and-skim, checks-only) | Is attention going where the risk is? |
| Hours a pull request waits on a person | The cost of review in calendar time |
| Share of pull requests with an AI review, and with at least one Important finding | Is the reviewer finding real things? |
| Rounds to pass | A reviewer that never converges is noise |
| Reverts and wrong flags found after merge | The guardrail. If these rise, human time was not saved, only moved |

## When a review misses something

Ask what the reviewer did not have in front of it, then put the fix where it will be read next time: a question in `REVIEW.md`, a rule in `CLAUDE.md`, a dbt test, or a lint rule. A miss that reached `main` also gets a row in `evals/review_misses.csv` (the change, the bug, the file and line), so a future reviewer can be scored against real misses.

## Not yet

- **A hosted AI reviewer on GitHub.** The Claude Code GitHub Action can review every pull request on GitHub itself. It needs a token stored as a repo secret. Worth adding once pull requests come from more than one place.
- **A secret scan on every pull request.** A gitleaks step was built on Nov 19 and left out after three review rounds, because a commit made on purpose to hide a secret could still get past it (a link that swallows the list of files, or a file that starts like a PDF). It caught accidental secrets. GitHub's own secret scanning with push protection is the next thing to try: it is a repo setting and a commit cannot switch it off. 🟡 It is free on a public repo as far as I know, which was not checked on Nov 19.
- **Branch protection on `main`** (require the `checks` job to pass before merging). Free on a public repo. A GitHub setting, not a file.
- **A merge queue.** Not needed while one leg merges at a time.
- **Circuit breakers** that tighten review when reverts rise. Needs users and incidents first.
