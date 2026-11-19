# Which model does what, and how fast to spend the plan (Nov 18, 2026)

## Models

| Work | Model | Why |
|---|---|---|
| Building a leg in Claude Code | Fable 5.2 | The strongest model writes the code |
| Reviewing a leg (`reviewer` subagent) | Opus 5.5 | A reviewer that is a different model from the author reads the change independently |
| Scheduled tasks (roadmap refresh, outreach) | Opus 5.5 | Judgment-heavy and unattended |
| Field extraction inside the app (`src/datum/extract.py`) | Haiku 5.5 | Paid per token through the API, not the plan. The smallest model that passes the eval |

A subagent with no `model:` line in its file runs on the same model as the session that calls it.

## Pace

The plan's weekly allowance resets Thursday at 9:00 PM Eastern. Allowance that is unused at the reset is gone, so the target is to use it on work that saves Andres's attention.

- Five working days in each week (Friday, Monday, Tuesday, Wednesday, Thursday): a pace of 20% a day.
- **Under pace** (used less than 20% times the working days so far): spend the room, in this order:
  1. Deep review (three reviewers and a verifier) on every High-tier pull request.
  2. A nightly bug hunt over code already on `main`, one folder a night.
  3. Growing the evals: draft test cases and link samples for Andres to check.
- **On pace:** reviews run at the depth `REVIEW.md` sets. Nothing extra.
- **More than 15 points over pace:** High stays Deep, Medium drops to one pass with no security pass unless `src/` changed, and the nightly bug hunt pauses. The builder stays on Fable 5.2.

Nothing reads the plan's usage automatically. Andres reads it in Claude Code with `/usage` and tells a Datum chat ("usage is 55%"); the chat updates the pace card on the Datum Roadmap dashboard.
