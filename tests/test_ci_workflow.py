"""test_ci_workflow.py: the workflow in .github/workflows/ci.yml keeps the properties that make its green tick worth trusting.

The workflow file is the one check that runs on GitHub's machine, and a small edit to it can leave a
step that still shows green and no longer checks anything. One step also downloads and runs a script
that is not pinned (dbt's installer). This test reads the file as text and holds six properties in place:

1. The workflow runs on every pull request and on every push to main, and on no other trigger.
2. The run's access token may only read the repo, and no job can ask for more.
3. The checkout does not keep that token on disk, where the installer script could read it.
4. Each check step runs exactly its one command, and holds no other line that could change how it runs.
5. The installer script runs after lint, the tests and the secrets-hook test, so it cannot change their results.
6. Nothing lets a failing step pass, nothing makes a step or the job conditional, and no cache carries
   files from one run to the next.

Properties 1, 2 and 4 compare whole lines, because a test that only finds a step by its name still
passes when the line under that name has been changed to do nothing.

It reads text and not parsed YAML, because the project has no YAML package installed and should not
gain one for a single test. It cannot prove the workflow runs: only a run on GitHub does that.

Run from the repo root:  pytest tests/test_ci_workflow.py
"""

import re                                   # regular expressions, to find the step names and the piped script
from pathlib import Path                    # file paths

import pytest                               # the test runner; parametrize runs one test body once per check step

REPO_ROOT = Path(__file__).parent.parent                               # tests/ -> repo root
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
STEPS = WORKFLOW.split("\n# Syntax:")[0]                               # the steps, without the explanation at the end of the file

STEP_NAMES = re.findall(r"^      - (?:name|uses): (.+?)(?:\s+#.*)?$", STEPS, flags=re.MULTILINE)      # each step's name, in order
CODE_LINES = [line.split("   #")[0].rstrip() for line in STEPS.splitlines() if not line.strip().startswith("#")]   # the steps without their comments
CODE = "\n".join(CODE_LINES)

# Each check step's name, and the one command it must run. The two install steps are not pinned here: they are
# not checks, and pinning the dbt line would mean editing this test on every dbt upgrade.
CHECK_STEPS = {
    "Lint": "ruff check src tests",
    "Tests": "pytest -q",
    "Secrets hook still blocks": "bash tests/hooks/test_block_secrets.sh",
    "Stop hook still blocks on a lint error and on a dbt parse error": "bash tests/hooks/test_offline_checks.sh",
}


def block(first_line: str, inner_indent: int) -> list[str]:
    """The line `first_line`, then every line after it indented at least `inner_indent` spaces, without comments or blank lines.

    `first_line` must appear exactly once, so a second copy of the same key, which could quietly replace the first, fails the test.
    """
    lines = [line for line in CODE_LINES if line]                       # blank lines are not part of what is compared
    starts = [i for i, line in enumerate(lines) if line == first_line]
    assert len(starts) == 1, f"exactly one line should read {first_line!r}"
    found = [first_line]
    for line in lines[starts[0] + 1:]:
        if not line.startswith(" " * inner_indent):                     # a line indented less than the block's own lines ends it
            break
        found.append(line)
    return found


def test_the_workflow_runs_on_every_pull_request_and_every_push_to_main():
    # pull_request_target in place of pull_request would run a fork's code with a token that can write, and a
    # paths or branches filter would let some pull requests skip the checks. Either one changes these lines.
    assert block("on:", 2) == ["on:", "  pull_request:", "  push:", "    branches: [main]"]
    assert len(re.findall(r"""^["']?on["']?[ \t]*:""", CODE, flags=re.MULTILINE)) == 1    # and no second "on" key replaces it


def test_the_access_token_may_only_read_the_repo():
    assert block("permissions:", 2) == ["permissions:", "  contents: read"]
    # A permissions block inside the job would replace this one for that job, so the key may appear only once, at any indent.
    assert len(re.findall(r"""^[ \t]*["']?permissions["']?[ \t]*:""", CODE, flags=re.MULTILINE)) == 1


def test_the_checkout_keeps_no_access_token():
    assert "          persist-credentials: false" in CODE_LINES     # a real setting on its own line, not a mention in a comment


@pytest.mark.parametrize("name", CHECK_STEPS)
def test_each_check_step_runs_its_one_command_and_nothing_else(name):
    # `run: "true"` in place of the command would show green and check nothing. Another line in the step, such as an
    # environment variable that tells pytest only to list the tests, could do the same, and so the step may hold no other line.
    assert block(f"      - name: {name}", 8) == [f"      - name: {name}", f"        run: {CHECK_STEPS[name]}"]


def test_the_unpinned_installer_runs_after_the_checks_it_could_spoil():
    assert STEP_NAMES[0] == "actions/checkout@v4"
    piped = [name for name in STEP_NAMES if re.search(r"\|\s*(sh|bash)\b", CODE.split(name, 1)[1].split("\n      - ", 1)[0])]
    assert piped == ["Install dbt, the same version as on the Mac"], "exactly one step may pipe a download into a shell"
    for earlier in ("Lint", "Tests", "Secrets hook still blocks"):
        assert STEP_NAMES.index(earlier) < STEP_NAMES.index(piped[0])
    assert STEP_NAMES[-1] == "Stop hook still blocks on a lint error and on a dbt parse error"   # the one step that needs dbt


def test_nothing_lets_a_failing_step_pass():
    assert "continue-on-error" not in CODE                        # a step marked this way shows green when it fails
    assert not re.search(r"\|\|\s*(true|:)", CODE)                # nor may a command's failure be swallowed
    # Nor may a step or the job be made conditional. The key is looked for at every indent, because `if: false`
    # on the job skips every step, and a skipped job does not fail the run.
    assert not re.search(r"""^[ \t-]*["']?if["']?[ \t]*:""", CODE, flags=re.MULTILINE)
    assert "cache:" not in CODE                                   # and no cache carries files from one run to the next
