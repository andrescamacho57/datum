#!/usr/bin/env bash
# PreToolUse hook for the Bash tool: refuse any command that mentions a secrets file.
# Claude Code feeds the pending tool call to this script as JSON on stdin.
# Exit 0 lets the command run; exit 2 blocks it and shows stderr to Claude.
# This is a guardrail, not a boundary: obfuscated paths (e.g. `cat .e*`) get through.
# settings.json is strict JSON and cannot hold comments, so its wiring is explained here:
#   permissions.deny lists Read/Edit/Write rules for the same files (blocks the file tools);
#   hooks.PreToolUse (matcher "Bash") runs this script (blocks shell access to them).

# Fail closed on unset variables and pipe errors, so a broken script cannot silently allow.
set -uo pipefail

# Fail closed if jq (the JSON parser) is missing: we could not inspect the command.
if ! command -v jq >/dev/null 2>&1; then
  # Tell Claude why the call was blocked.
  echo "block-secrets: jq is not installed, cannot inspect the command. Blocking." >&2
  # Exit 2 means block.
  exit 2
fi  # end of the jq-missing check

# Read the whole hook payload from stdin into a variable.
payload="$(cat)"

# Pull out the shell command Claude wants to run; '// empty' yields "" when absent.
# If the payload is not valid JSON, jq fails and the || branch blocks the call.
command_text="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')" || {
  # Explain the parse failure.
  echo "block-secrets: could not parse hook input as JSON. Blocking." >&2
  # Block, because an uninspectable command is treated as unsafe.
  exit 2
}  # end of the parse-failure handler

# Case-sensitive extended-regex of the four protected names; dots are escaped to be literal.
# .env covers .env and .env.local; profiles.yml is dbt's credentials file;
# .snowflake is the ~/.snowflake config directory; .p8 is a private-key file.
pattern='\.env|profiles\.yml|\.snowflake|\.p8'

# If the command text mentions any protected name, refuse it.
if printf '%s' "$command_text" | grep -Eq -- "$pattern"; then
  # Say what matched and why, so Claude does not retry with a variation.
  echo "block-secrets: command mentions a secrets file (.env, profiles.yml, .snowflake, .p8). Secrets must never be read. Blocked." >&2
  # Exit 2 blocks the tool call.
  exit 2
fi  # end of the secrets-match check

# Nothing sensitive found: allow the command.
exit 0
