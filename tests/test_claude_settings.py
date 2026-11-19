"""test_claude_settings.py: the two guardrails in .claude/settings.json still cover what they are meant to cover.

.claude/settings.json is strict JSON, so it cannot explain itself in comments, and one wrong character
in it switches a guardrail off without any error. This test reads the file and checks two things:

1. The secrets hook runs for the shell tools we know of: every tool with "bash" in its name, in any
   letter case, plus Monitor and PowerShell, which run shell commands under other names. Claude Code
   reads a hook's "matcher" as an exact tool name when it holds only letters, digits and a few plain
   characters, and as an unanchored JavaScript regular expression otherwise
   (https://code.claude.com/docs/en/hooks, "Matcher patterns"). The exact name "Bash" would miss a
   tool called "bash" or "mcp__server__run_bash". A shell tool under a name nobody has listed here is
   still not covered: a matcher can only name what is known.
2. The Read, Edit and Write tools are denied the dotenv file and its variants (.env.local and so on).
   Path rules use gitignore patterns (https://code.claude.com/docs/en/permissions).

It checks the settings as written. It cannot prove how Claude Code applies them: that is Claude Code's
own behaviour, and the two pages above are the source for it. One thing was observed and not just
read: on Nov 19, 2026, on this Mac, Claude Code refused to write a file whose name ended in capitals
(.P8) under the lower-case rule for private keys, so the path rules ignored letter case that day.

Run from the repo root:  pytest tests/test_claude_settings.py
"""

import json                                 # reads the settings file
import re                                   # regular expressions, to try the matcher on tool names
from pathlib import Path                    # file paths

import pytest                               # the test runner; parametrize runs one test body over several cases

SETTINGS = json.loads((Path(__file__).parent.parent / ".claude" / "settings.json").read_text())

FILE_TOOLS = ("Read", "Edit", "Write")                     # the three tools that open a file by its path
EXACT_NAME_ONLY = re.compile(r"[A-Za-z0-9_\- ,|]*")        # a matcher made only of these is an exact name, not a pattern
# The only pieces the matcher may be built from: plain letters, a bracketed set of letters such as [Bb], and | for "or".
# Python tries the matcher below, but Claude Code runs it as JavaScript, and the two do not accept the same syntax:
# "(?i)bash" works in Python and is an error in JavaScript, which would switch the hook off. These pieces mean the same in both.
SAFE_IN_BOTH = re.compile(r"(\[[A-Za-z]+\]|[A-Za-z]+|\|)+")


def secrets_hook_matcher() -> str:
    """The matcher of the PreToolUse entry that runs block-secrets.sh."""
    entries = [e for e in SETTINGS["hooks"]["PreToolUse"] if any("block-secrets.sh" in h["command"] for h in e["hooks"])]
    assert len(entries) == 1, "exactly one PreToolUse entry should run block-secrets.sh"
    return entries[0]["matcher"]


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
