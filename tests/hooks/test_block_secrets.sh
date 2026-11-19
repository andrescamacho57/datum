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

# --- Must block (exit 2) in any letter case. ---
# The Mac's disk treats upper and lower case as the same name, so `cat .ENV` opens the dotenv file.
# A pattern that only knew the lower-case spelling would let each of these four through.
# The dotenv file, typed in capitals.
check "blocks upper-case dotenv file" 2 '{"tool_input":{"command":"cat .ENV"}}'
# The Snowflake config directory, typed in capitals.
check "blocks upper-case snowflake dir" 2 '{"tool_input":{"command":"ls ~/.SNOWFLAKE/config.toml"}}'
# dbt's credentials file, with a capital first letter.
check "blocks capitalised profiles file" 2 '{"tool_input":{"command":"head ~/.dbt/Profiles.yml"}}'
# A private-key file whose ending is in capitals.
check "blocks upper-case p8 key file" 2 '{"tool_input":{"command":"openssl pkey -in RSA_KEY.P8"}}'

# --- Must block (exit 2) wherever the tool keeps its command. ---
# The Bash tool puts its command in a field named "command". Another shell tool may name the field differently,
# so the hook reads every piece of text in the tool's input, not one field.
# A shell tool that calls the field "cmd".
check "blocks a command in a cmd field" 2 '{"tool_name":"mcp__x__run_bash","tool_input":{"cmd":"cat .env"}}'
# A shell tool that nests its script one level down.
check "blocks a command nested in the input" 2 '{"tool_name":"mcp__x__bash","tool_input":{"args":{"script":"cat .env"}}}'
# The Monitor tool, which runs a shell command in the background.
check "blocks a Monitor command"      2 '{"tool_name":"Monitor","tool_input":{"command":"tail -f .env","description":"watch a file"}}'

# --- Known over-matches, pinned so a change to the pattern is a deliberate decision. ---
# Reading every piece of text means a description that merely names the dotenv file is blocked too.
check "pinned: blocks a description"  2 '{"tool_input":{"command":"ls","description":"list the files next to .env"}}'
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
# The Monitor tool can also open a web socket, with no shell command at all. That must not be blocked.
check "allows a Monitor web socket"   0 '{"tool_name":"Monitor","tool_input":{"ws":{"url":"wss://events.example.com/stream"},"description":"deploy events"}}'
# A payload with no tool input at all: pinned as allow (nothing to inspect).
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
