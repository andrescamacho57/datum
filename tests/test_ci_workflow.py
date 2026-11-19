"""test_ci_workflow.py: the workflow in .github/workflows/ci.yml keeps the properties that make its green tick worth trusting.

The workflow file is the one check that runs on GitHub's machine, and a small edit to it can leave a
step that still shows green and no longer checks anything. One step also downloads and runs a script
that is not pinned (dbt's installer). This test reads the file as text and holds three properties in place:

1. The checkout does not keep the run's access token on disk, where that script could read it.
2. That script runs after lint, the tests and the secrets-hook test, so it cannot change their results.
3. Nothing lets a failing step pass, and no cache carries files from one run to the next.

It reads text and not parsed YAML, because the project has no YAML package installed and should not
gain one for a single test. It cannot prove the workflow runs: only a run on GitHub does that.

Run from the repo root:  pytest tests/test_ci_workflow.py
"""

import re                                   # regular expressions, to find the step names and the piped script
from pathlib import Path                    # file paths

REPO_ROOT = Path(__file__).parent.parent                               # tests/ -> repo root
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
STEPS = WORKFLOW.split("\n# Syntax:")[0]                               # the steps, without the explanation at the end of the file

STEP_NAMES = re.findall(r"^      - (?:name|uses): (.+?)(?:\s+#.*)?$", STEPS, flags=re.MULTILINE)      # each step's name, in order
CODE_LINES = [line.split("   #")[0].rstrip() for line in STEPS.splitlines() if not line.strip().startswith("#")]   # the steps without their comments
CODE = "\n".join(CODE_LINES)


def test_the_checkout_keeps_no_access_token():
    assert "          persist-credentials: false" in CODE_LINES     # a real setting on its own line, not a mention in a comment


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
    assert "\n        if:" not in CODE                            # nor may a step be made conditional
    assert "cache:" not in CODE                                   # and no cache carries files from one run to the next
