#!/usr/bin/env bash
# PreToolUse hook for shell tools: refuse any command that mentions a secrets file.
# Claude Code feeds the pending tool call to this script as JSON on stdin.
# Exit 0 lets the command run; exit 2 blocks it and shows stderr to Claude.
# This is a guardrail, not a boundary: obfuscated paths (e.g. `cat .e*`) get through.
# settings.json is strict JSON and cannot hold comments, so its wiring is explained here:
#   permissions.deny lists Read/Edit/Write rules for the same files (blocks the file tools).
#     `**/.env` is the dotenv file and `**/.env.*` is every variant of it (.env.local and so on).
#   hooks.PreToolUse (matcher "[Bb][Aa][Ss][Hh]") runs this script (blocks shell access to them).
#     The matcher is a regular expression, tested anywhere in the tool's name, so it fires for the
#     built-in Bash tool and for any other tool with "bash" in its name, in any letter case.
#     The plain word "Bash" would be read as one exact name and would miss a tool called "bash".
#     Source: https://code.claude.com/docs/en/hooks, "Matcher patterns".
# What it reads: every piece of text in the tool's input, whatever the field is called.
#   The cost is one known over-match: a description that merely names a secrets file is blocked too.

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

# Pull out every piece of text in the tool's input, one per line. The Bash tool keeps its command in
# .tool_input.command, but another shell tool may name the field differently or nest it, so no field is trusted
# to be the only one. In jq, `..` walks every value at every depth and `strings` keeps the ones that are text.
# A payload with no tool input gives "", which is allowed below: there is nothing to inspect.
# If the payload is not valid JSON, jq fails and the || branch blocks the call.
command_text="$(printf '%s' "$payload" | jq -r '[.tool_input | .. | strings] | join("\n")')" || {
  # Explain the parse failure.
  echo "block-secrets: could not parse hook input as JSON. Blocking." >&2
  # Block, because an uninspectable command is treated as unsafe.
  exit 2
}  # end of the parse-failure handler

# Extended regular expression of the four protected names; dots are escaped to be literal.
# It is written in lower case, and grep's -i flag below makes it match any letter case.
# .env covers .env and .env.local; profiles.yml is dbt's credentials file;
# .snowflake is the ~/.snowflake config directory; .p8 is a private-key file.
pattern='\.env|profiles\.yml|\.snowflake|\.p8'

# If any of that text mentions a protected name, in any letter case, refuse the call.
# -i is here because the Mac's disk does not tell upper case from lower: `cat .ENV` opens the dotenv file.
if printf '%s' "$command_text" | grep -Eqi -- "$pattern"; then
  # Say what matched and why, so Claude does not retry with a variation.
  echo "block-secrets: command mentions a secrets file (.env, profiles.yml, .snowflake, .p8, in any letter case). Secrets must never be read. Blocked." >&2
  # Exit 2 blocks the tool call.
  exit 2
fi  # end of the secrets-match check

# Nothing sensitive found: allow the command.
exit 0
