#!/usr/bin/env bash
# Offline test for .claude/hooks/offline-checks.sh (the Stop hook). Asserts exit codes only.
# Run from anywhere: bash tests/hooks/test_offline_checks.sh   (exit 0 = all passed, 1 = a case failed)
# No network: dbt parse uses the committed placeholder profile (unresolvable account, no credentials).
# Three cases need the real ruff and the real dbt. ruff is taken from .venv/bin, or from PATH when there is no .venv.
# With no ruff anywhere the three cases are skipped with a message on a person's machine, and counted as a failure in CI.

# Fail on unset variables and pipe errors so the test itself cannot silently misbehave.
set -uo pipefail

# Resolve this test's own directory regardless of the caller's cwd.
here="$(cd "$(dirname "$0")" && pwd)"

# Repo root: tests/hooks -> tests -> root.
root="$(cd "$here/../.." && pwd)"

# The hook under test.
hook="$root/.claude/hooks/offline-checks.sh"

# Count of failed cases; the script exits non-zero if this ends above 0.
failed=0

# expect NAME EXPECTED GOT: compare an exit code and report.
expect() {
  # Passing case when the codes match.
  if [ "$3" -eq "$2" ]; then
    # Report the pass.
    echo "ok    $1"
  else
    # Report expected vs actual.
    echo "FAIL  $1 (expected exit $2, got $3)"
    # Count the failure.
    failed=$((failed + 1))
  fi  # end of the comparison
}  # end of expect()

# Case 1: loop guard. With stop_hook_active=true the hook must stand down (exit 0) without running checks.
printf '%s' '{"stop_hook_active":true}' | CLAUDE_PROJECT_DIR="$root" "$hook" >/dev/null 2>&1
# Assert exit 0.
expect "loop guard stands down" 0 $?

# Case 2: ruff missing. Point RUFF_BIN at a path that does not exist; expect non-blocking exit 1.
printf '%s' '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="$root" RUFF_BIN=/nonexistent/ruff "$hook" >/dev/null 2>&1
# Assert exit 1.
expect "missing ruff is non-blocking (exit 1)" 1 $?

# Case 3: jq missing. `env -i` starts the hook with an empty environment, and the PATH given holds no programs, so jq cannot be found.
# HOME is passed back in on purpose. The hook reads $HOME on an early line, and without it the hook would stop there
# with exit 1 for the wrong reason, before it ever looked for jq.
out="$(printf '%s' '{"stop_hook_active":false}' | env -i HOME="$root" PATH=/nonexistent /bin/bash "$hook" 2>&1 >/dev/null)"
# Capture the exit code right after the command substitution.
code=$?
# Assert the non-blocking exit 1.
expect "missing jq is non-blocking (exit 1)" 1 "$code"
# Assert the reason too, so this case cannot pass because of some other early failure.
case "$out" in *"jq is not installed"*) echo "ok    missing jq is the stated reason" ;; *) echo "FAIL  missing jq is not the stated reason"; failed=$((failed + 1)) ;; esac

# Cases 4-6 need the real ruff. Look in the project's own environment first, which is where it is on the Mac.
ruff_bin="$root/.venv/bin/ruff"
# The CI machine has no .venv: it installs ruff with pip, which puts it on PATH. Fall back to that copy.
if [ ! -x "$ruff_bin" ]; then
  # `command -v` prints the full path of a program, or nothing when there is none; `|| true` keeps "none" from stopping the script.
  ruff_bin="$(command -v ruff || true)"
fi  # end of the fallback

# Run the three cases when a ruff was found in either place.
if [ -n "$ruff_bin" ] && [ -x "$ruff_bin" ]; then
  # Build a throwaway project: a temp dir that reuses the real pipeline/ and .claude/ via symlinks.
  tmp="$(mktemp -d)"
  # Link the real dbt project so dbt parse has something valid to parse.
  ln -s "$root/pipeline" "$tmp/pipeline"
  # Link .claude so the hook finds the placeholder dbt profile at its relative path.
  ln -s "$root/.claude" "$tmp/.claude"
  # Give the temp project its own src/ that we control.
  mkdir -p "$tmp/src"
  # Case 4 fixture: a lint-clean Python file.
  printf 'X = 1\n' > "$tmp/src/clean.py"
  # Case 4: clean code + valid dbt project -> exit 0.
  printf '%s' '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="$tmp" RUFF_BIN="$ruff_bin" "$hook" >/dev/null 2>&1
  # Assert exit 0.
  expect "clean src + valid dbt project passes" 0 $?
  # Case 5 fixture: an unused import, which ruff's default rules (F401) reject.
  printf 'import os\n' > "$tmp/src/dirty.py"
  # Case 5: lint error -> blocking exit 2, with ruff's output on stderr.
  out="$(printf '%s' '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="$tmp" RUFF_BIN="$ruff_bin" "$hook" 2>&1 >/dev/null)"
  # Capture the exit code right after the command substitution.
  code=$?
  # Assert exit 2.
  expect "lint error blocks (exit 2)" 2 "$code"
  # Also assert the ruff section header reached stderr, so Claude sees what failed.
  case "$out" in *"ruff check src"*) echo "ok    lint error output reaches stderr" ;; *) echo "FAIL  lint error output missing from stderr"; failed=$((failed + 1)) ;; esac
  # Remove the temp project (symlinks only; the real pipeline/ and .claude/ are untouched).
  rm -rf "$tmp"
  # Case 6 needs a dbt project it may break, so this second temp project gets its own COPY of pipeline/, not a link.
  tmp2="$(mktemp -d)"
  # Make the folders the copy and the clean source file go into.
  mkdir -p "$tmp2/pipeline" "$tmp2/src"
  # Copy pipeline/ without target/ and logs/, which dbt writes and which can be large. tar packs on the left and unpacks on the right.
  (cd "$root/pipeline" && tar -cf - --exclude ./target --exclude ./logs .) | tar -xf - -C "$tmp2/pipeline"
  # Copy the placeholder dbt profile to the same relative path. A copy and not a link, because dbt writes a small
  # file of its own next to the profile when a parse fails, and that file must not land in the real repo.
  mkdir -p "$tmp2/.claude/hooks" && cp -R "$root/.claude/hooks/offline-profile" "$tmp2/.claude/hooks/"
  # A lint-clean Python file, so ruff passes and only dbt can fail.
  printf 'X = 1\n' > "$tmp2/src/clean.py"
  # Case 6 fixture: a model whose template is cut off mid-call, which dbt cannot parse.
  printf 'select * from {{ ref( }}\n' > "$tmp2/pipeline/models/staging/broken_on_purpose.sql"
  # Case 6: dbt parse error -> blocking exit 2, with dbt's output on stderr.
  out="$(printf '%s' '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="$tmp2" RUFF_BIN="$ruff_bin" "$hook" 2>&1 >/dev/null)"
  # Capture the exit code right after the command substitution.
  code=$?
  # Assert exit 2.
  expect "dbt parse error blocks (exit 2)" 2 "$code"
  # Also assert the dbt section header reached stderr, and that ruff's did not: the block must come from dbt.
  case "$out" in *"ruff check src"*) echo "FAIL  the block came from ruff, not from dbt"; failed=$((failed + 1)) ;; *"dbt parse"*) echo "ok    dbt parse error output reaches stderr" ;; *) echo "FAIL  dbt parse error output missing from stderr"; failed=$((failed + 1)) ;; esac
  # Remove the second temp project, which holds only the copy.
  rm -rf "$tmp2"
elif [ "${CI:-}" = "true" ]; then
  # GitHub sets CI=true on its machines. There a skip would be a check that quietly stopped checking, so it counts as a failure.
  echo "FAIL  clean/lint-error cases could not run: no ruff in .venv/bin or on PATH"
  # Count the failure.
  failed=$((failed + 1))
else
  # On a person's machine, say plainly what was not tested and how to enable it.
  echo "skip  clean/lint-error cases: ruff not installed (source .venv/bin/activate && pip install ruff)"
fi  # end of the ruff-dependent cases

# Summarize and set the exit code: non-zero if any case failed.
echo "failed cases: $failed"
# Exit 0 only when nothing failed.
[ "$failed" -eq 0 ]
