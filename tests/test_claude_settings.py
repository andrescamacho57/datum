"""test_claude_settings.py: the two guardrails in .claude/settings.json still cover what they are meant to cover.

.claude/settings.json is strict JSON, so it cannot explain itself in comments, and one wrong character
in it switches a guardrail off without any error. This test reads the file and checks three things:

1. The secrets hook runs exactly block-secrets.sh, and that script exists and may be run. Claude Code
   treats a hook that cannot start as a non-blocking error and lets the tool call go ahead
   (https://code.claude.com/docs/en/hooks, "Exit code output"), and so a one-character change to the
   command, such as block-secrets.sh.disabled, would switch the guardrail off with no error. That is
   why the command is compared whole, and not found by a part of its name.
2. The secrets hook runs for the shell tools we know of: every tool with "bash" in its name, in any
   letter case, plus Monitor and PowerShell, which run shell commands under other names. Claude Code
   reads a hook's "matcher" as an exact tool name when it holds only letters, digits and a few plain
   characters, and as an unanchored JavaScript regular expression otherwise
   (https://code.claude.com/docs/en/hooks, "Matcher patterns"). The exact name "Bash" would miss a
   tool called "bash" or "mcp__server__run_bash". A shell tool under a name nobody has listed here is
   still not covered: a matcher can only name what is known.
3. The Read and Edit tools are denied the dotenv file and its variants (.env.local and so on).
   Claude Code checks only Read and Edit path rules, and the Edit rules also cover the Write tool,
   which is why there is no Write rule to check. Path rules use gitignore patterns
   (https://code.claude.com/docs/en/permissions).

It checks the settings as written. It cannot prove how Claude Code applies them: that is Claude Code's
own behaviour, and the two pages above are the source for it. One thing was observed and not just
read: on Nov 19, 2026, on this Mac, Claude Code refused to write a file whose name ended in capitals
(.P8) under the lower-case rule for private keys, so the path rules ignored letter case that day.

Run from the repo root:  pytest tests/test_claude_settings.py
"""

import json                                 # reads the settings file
import os                                   # asks the operating system whether the hook script may be run
import re                                   # regular expressions, to try the matcher on tool names
from pathlib import Path                    # file paths

import pytest                               # the test runner; parametrize runs one test body over several cases

REPO_ROOT = Path(__file__).parent.parent                                    # tests/ -> repo root
SETTINGS = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())

SECRETS_HOOK_COMMAND = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/block-secrets.sh'   # the whole command, character for character
PROJECT_DIR_PREFIX = '"$CLAUDE_PROJECT_DIR"/'                               # Claude Code sets this variable to the repo root
# Claude Code checks only Read and Edit path rules. It accepts a path rule written for Write and never matches
# anything against it, and the Edit rules cover the Write tool, because "Edit rules apply to all built-in tools
# that edit files" (https://code.claude.com/docs/en/permissions, "What Read and Edit rules cover" and
# "Write(path), Glob(path), and Grep(path) rules don't match"). And so no Write rule is asked for here.
FILE_TOOLS = ("Read", "Edit")                              # the two tools whose path rules Claude Code checks
EXACT_NAME_ONLY = re.compile(r"[A-Za-z0-9_\- ,|]*")        # a matcher made only of these is an exact name, not a pattern
# The only pieces the matcher may be built from: plain letters, a bracketed set of letters such as [Bb], and | for "or".
# Python tries the matcher below, but Claude Code runs it as JavaScript, and the two do not accept the same syntax:
# "(?i)bash" works in Python and is an error in JavaScript, which would switch the hook off. These pieces mean the same in both.
SAFE_IN_BOTH = re.compile(r"(\[[A-Za-z]+\]|[A-Za-z]+|\|)+")


def secrets_hook_entry() -> dict:
    """The one PreToolUse entry whose hook runs exactly SECRETS_HOOK_COMMAND."""
    entries = [e for e in SETTINGS["hooks"]["PreToolUse"] if any(h.get("command") == SECRETS_HOOK_COMMAND for h in e["hooks"])]
    assert len(entries) == 1, "exactly one PreToolUse entry should run the secrets hook, by its exact command"
    return entries[0]


def secrets_hook_matcher() -> str:
    """The matcher of that entry: the pattern of tool names it runs for."""
    return secrets_hook_entry()["matcher"]


def test_the_secrets_hook_runs_its_exact_command_and_the_script_can_run():
    # One hook in the entry, and no other key on it that could change how it runs.
    assert secrets_hook_entry()["hooks"] == [{"type": "command", "command": SECRETS_HOOK_COMMAND}]
    script = REPO_ROOT / SECRETS_HOOK_COMMAND.removeprefix(PROJECT_DIR_PREFIX)    # the file the command starts
    assert script.is_file(), f"{script} is missing, and so the hook could not start"
    assert os.access(script, os.X_OK), f"{script} is not executable, and so the hook could not start"


def test_the_matcher_is_a_pattern_that_javascript_reads_the_same_way():
    matcher = secrets_hook_matcher()
    assert not EXACT_NAME_ONLY.fullmatch(matcher), "the matcher would be read as one exact tool name, not as a pattern"
    assert SAFE_IN_BOTH.fullmatch(matcher), "the matcher uses syntax that Python and JavaScript may read differently"


@pytest.mark.parametrize("tool_name", ["Bash", "bash", "BASH", "BashOutput", "mcp__server__run_bash", "mcp__ide__Bash_exec", "Monitor", "PowerShell"])
def test_secrets_hook_runs_for_the_shell_tools_we_know_of(tool_name):
    assert re.search(secrets_hook_matcher(), tool_name)


@pytest.mark.parametrize("tool_name", ["Read", "Edit", "Write", "Grep", "WebFetch"])
def test_secrets_hook_does_not_run_for_tools_that_are_not_shells(tool_name):
    # The hook reads a shell command. Running it on every tool would only slow each call down.
    assert not re.search(secrets_hook_matcher(), tool_name)


@pytest.mark.parametrize("tool", FILE_TOOLS)
def test_file_tools_are_denied_the_dotenv_file_and_its_variants(tool):
    deny = SETTINGS["permissions"]["deny"]
    assert f"{tool}(**/.env)" in deny                      # the dotenv file itself
    assert f"{tool}(**/.env.*)" in deny                    # every variant: .env.local, .env.production, ...
    assert f"{tool}(~/.dbt/profiles.yml)" in deny          # dbt's credentials file
    assert f"{tool}(~/.snowflake/**)" in deny              # the Snowflake config folder
    assert f"{tool}(**/*.p8)" in deny                      # private-key files
