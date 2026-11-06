#!/usr/bin/env bash
# Stop hook: runs cheap, offline checks when Claude finishes a turn.
# Checks: `ruff check src` and `dbt parse` on pipeline/. No warehouse, no network.
# Exit 0 = all clear. Exit 2 = a check failed; stderr goes back to Claude to fix.
# Exit 1 = a tool is missing; shown to the user but does not force Claude to continue.
# settings.json is strict JSON and cannot hold comments, so its wiring is explained here:
#   hooks.Stop runs this script at the end of every turn (no matcher; Stop has none).

# Fail on unset variables and pipe errors, so a typo cannot silently pass.
set -uo pipefail

# Hooks run in a minimal shell; make sure the standalone dbt binary in ~/.local/bin is found.
PATH="$HOME/.local/bin:$PATH"

# Read the hook payload (JSON) from stdin into a variable.
payload="$(cat)"

# jq is needed to read the payload; without it we cannot apply the loop guard safely.
if ! command -v jq >/dev/null 2>&1; then
  # Tell the user what is missing.
  echo "offline-checks: jq is not installed, skipping checks." >&2
  # Non-blocking error: exit 1 so Claude is not forced to continue.
  exit 1
fi  # end of the jq-missing check

# Loop guard: Claude Code sets stop_hook_active=true when this hook already forced a continuation.
active="$(printf '%s' "$payload" | jq -r '.stop_hook_active // false')"

# If we already blocked once this turn, stand down; exit 2 again would loop forever.
if [ "$active" = "true" ]; then
  # Allow Claude to stop.
  exit 0
fi  # end of the loop guard

# Locate the repo root: Claude Code exports CLAUDE_PROJECT_DIR; fall back to two dirs above this script.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Work from the repo root so relative paths below resolve.
cd "$root" || exit 1

# ruff lives in the project venv, not on the global PATH; RUFF_BIN overrides it (used by the test).
ruff_bin="${RUFF_BIN:-$root/.venv/bin/ruff}"

# Without ruff we cannot lint; report it instead of silently passing.
if [ ! -x "$ruff_bin" ]; then
  # Give the exact install command.
  echo "offline-checks: ruff not found. Install: source .venv/bin/activate && pip install ruff" >&2
  # Non-blocking error so a missing tool does not trap the turn.
  exit 1
fi  # end of the ruff-missing check

# dbt is a standalone binary (not in the venv); make sure it is reachable.
if ! command -v dbt >/dev/null 2>&1; then
  # Say where it was expected.
  echo "offline-checks: dbt not found on PATH (expected ~/.local/bin/dbt)." >&2
  # Non-blocking error, same reasoning as for ruff.
  exit 1
fi  # end of the dbt-missing check

# Collect failure reports here; empty at the end means everything passed.
failures=""

# Lint src; capture stdout and stderr together. A non-zero ruff exit means lint errors.
ruff_out="$("$ruff_bin" check src 2>&1)" || failures+="--- ruff check src ---"$'\n'"$ruff_out"$'\n'

# Parse the dbt project offline. The placeholder profile has no credentials (and an unresolvable
# account), --no-version-check skips the update ping, --no-manage-state skips the state service.
dbt_out="$(dbt parse --project-dir pipeline --profiles-dir .claude/hooks/offline-profile --no-version-check --no-manage-state 2>&1)" || failures+="--- dbt parse (pipeline/) ---"$'\n'"$dbt_out"$'\n'

# If anything failed, hand the output back to Claude.
if [ -n "$failures" ]; then
  # Print every failure report to stderr, which exit 2 delivers to Claude.
  printf '%s' "$failures" >&2
  # Exit 2: block the stop so Claude fixes the problems.
  exit 2
fi  # end of the failure report

# Both checks passed.
exit 0
