#!/usr/bin/env bash
# Offline test for .claude/hooks/block-secrets.sh: pipes JSON payloads in and asserts exit codes.
# Run from anywhere: bash tests/hooks/test_block_secrets.sh   (exit 0 = all passed, 1 = a case failed)
# No network, no credentials: every payload is an inline string, nothing is executed or read.

# Fail on unset variables and pipe errors so the test itself cannot silently misbehave.
set -uo pipefail

# Resolve this test's own directory regardless of the caller's cwd.
here="$(cd "$(dirname "$0")" && pwd)"

# Path to the hook under test, relative to this file (tests/hooks -> repo root -> .claude/hooks).
hook="$here/../../.claude/hooks/block-secrets.sh"

# Count of failed cases; the script exits non-zero if this ends above 0.
failed=0

# check NAME EXPECTED_EXIT PAYLOAD: run the hook on PAYLOAD and compare its exit code.
check() {
  # Run the hook with PAYLOAD on stdin, discarding its output; we only assert the exit code.
  printf '%s' "$3" | "$hook" >/dev/null 2>&1
  # Capture the hook's exit code immediately, before anything else overwrites $?.
  got=$?
  # Compare the actual exit code with the expected one.
  if [ "$got" -eq "$2" ]; then
    # Passing case: report it.
    echo "ok    $1"
  else
    # Failing case: report expected vs actual and remember the failure.
    echo "FAIL  $1 (expected exit $2, got $got)"
    # Record the failure so the script's final exit code reflects it.
    failed=$((failed + 1))
  fi  # end of the comparison
}  # end of check()

# --- Must block (exit 2): one case per protected name in the hook's pattern. ---
# The dotenv file itself.
check "blocks dotenv file"            2 '{"tool_input":{"command":"cat .env"}}'
# A dotenv variant; the unanchored pattern also catches it.
check "blocks dotenv variant"         2 '{"tool_input":{"command":"cat .env.local"}}'
# dbt's credentials file.
check "blocks dbt profiles file"      2 '{"tool_input":{"command":"head ~/.dbt/profiles.yml"}}'
# The Snowflake config directory.
check "blocks snowflake dir"          2 '{"tool_input":{"command":"ls ~/.snowflake"}}'
# A private-key file.
check "blocks p8 key file"            2 '{"tool_input":{"command":"openssl pkey -in rsa_key.p8"}}'

# --- Known over-matches, pinned so a change to the pattern is a deliberate decision. ---
# A commit message that merely mentions the dotenv file is blocked (plain substring match).
check "pinned: blocks commit message" 2 '{"tool_input":{"command":"git commit -m \"load key from .env\""}}'
# A different file that merely starts with the same characters is blocked too.
check "pinned: blocks .envrc"         2 '{"tool_input":{"command":"cat .envrc"}}'

# --- Must allow (exit 0): ordinary project commands. ---
# Plain git.
check "allows git status"             0 '{"tool_input":{"command":"git status"}}'
# The documented dbt command (run from pipeline/).
check "allows dbt build"              0 '{"tool_input":{"command":"cd pipeline && dbt build --select entity_lookup"}}'
# Venv activation: ".venv" must not be mistaken for the dotenv file.
check "allows venv activate"          0 '{"tool_input":{"command":"source .venv/bin/activate"}}'
# A payload with no command field at all: pinned as allow (nothing to inspect).
check "pinned: allows empty payload"  0 '{}'

# --- Fail closed (exit 2): the hook cannot inspect the command. ---
# Input that is not JSON must block rather than allow.
check "blocks invalid JSON"           2 'this is not json'

# jq-missing branch: run the hook with an empty PATH so jq cannot be found, and expect exit 2.
printf '%s' '{"tool_input":{"command":"git status"}}' | env -i PATH=/nonexistent /bin/bash "$hook" >/dev/null 2>&1
# Capture the exit code right away.
got=$?
# Assert it blocked.
if [ "$got" -eq 2 ]; then
  # Passing case.
  echo "ok    blocks when jq is missing"
else
  # Failing case: report and count it.
  echo "FAIL  blocks when jq is missing (expected exit 2, got $got)"
  # Record the failure.
  failed=$((failed + 1))
fi  # end of the jq-missing assertion

# Summarize and set the exit code: non-zero if any case failed.
echo "failed cases: $failed"
# Exit 0 only when nothing failed.
[ "$failed" -eq 0 ]
