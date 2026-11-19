"""test_gitignore_secrets.py: git refuses to pick up a secrets file, and still tracks the one look-alike it needs.

The repository is public. `git add .` stages every file that .gitignore does not name, so a secrets
file that .gitignore misses is one careless command away from being published. This test asks git
itself (`git check-ignore`) whether each name below would be ignored. No file is created or read:
check-ignore only compares a path, as text, with the patterns.

The one exception is .claude/hooks/offline-profile/profiles.yml. It has the same name as dbt's real
credentials file, but it is a placeholder with no credentials, and the Stop hook needs it to run
`dbt parse` offline. It must stay tracked.

Run from the repo root:  pytest tests/test_gitignore_secrets.py
"""

import subprocess                           # runs git as a separate program
from pathlib import Path                    # file paths

import pytest                               # the test runner; parametrize runs one test body over several cases

REPO_ROOT = Path(__file__).parent.parent                   # tests/ -> repo root


def is_ignored(path: str) -> bool:
    """True when git's ignore rules match the path. --no-index asks about the rules alone, whether or not the file is tracked."""
    result = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", path], cwd=REPO_ROOT, check=False)
    assert result.returncode in (0, 1), f"git check-ignore failed on {path}"    # 0 = ignored, 1 = not ignored, anything else = git error
    return result.returncode == 0


@pytest.mark.parametrize("path", [
    ".env",                                 # the dotenv file: the local secrets file
    ".env.local",                           # a dotenv variant
    "pipeline/.env.production",             # a variant in a subfolder
    "rsa_key.p8",                           # a private key in the form Snowflake's key-pair login uses
    "keys/snowflake_rsa_key.p8",            # the same, in a subfolder
    "server.pem",                           # a private key or certificate in the other common form
    ".snowflake/config.toml",               # the Snowflake command-line tool's config folder, if someone copies it in
    "profiles.yml",                         # dbt's credentials file, if someone copies it into the repo
    "pipeline/profiles.yml",                # the most likely place to copy it by mistake
])
def test_a_secrets_file_is_ignored(path):
    assert is_ignored(path)


@pytest.mark.parametrize("path", [
    ".claude/hooks/offline-profile/profiles.yml",   # the placeholder profile the Stop hook needs
    ".claude/settings.json",                # the guardrail settings themselves
    "requirements.txt",                     # an ordinary file, to show the rules are not ignoring everything
    "pipeline/dbt_project.yml",             # a .yml file that is not the credentials file
    ".venv.md",                             # a name that merely resembles the dotenv file
])
def test_a_file_the_project_needs_is_not_ignored(path):
    assert not is_ignored(path)


def test_no_tracked_file_matches_a_secrets_pattern():
    # `git ls-files -ci` lists files that are tracked AND match an ignore rule: files that were committed before a rule existed.
    # The two .codex/ files are an older, known case that has nothing to do with secrets, so they are named here and nothing else may appear.
    result = subprocess.run(["git", "ls-files", "-ci", "--exclude-standard"], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    tracked_but_ignored = set(result.stdout.split())
    assert tracked_but_ignored <= {".codex/agents/reviewer.toml", ".codex/agents/source-recon.toml"}, tracked_but_ignored
