"""test_ci_workflow.py: the secret scan in .github/workflows/ci.yml keeps the properties that make it worth trusting.

The workflow file is the one check that runs on GitHub's machine, and a small edit to it can leave a
step that still shows green and no longer checks anything. This test reads the file as text and holds
four properties in place:

1. The checkout does not keep the run's access token on disk.
2. The secret scan runs before the one step that downloads and runs an unpinned script (dbt's installer),
   so that script cannot get between the scanner and its checksum.
3. The scan takes its rules from .github/gitleaks.toml and ignores every way a commit could excuse itself.
4. The scanner is pinned by a full SHA-256 checksum, and the step first proves it can find a planted token.

It reads text and not parsed YAML, because the project has no YAML package installed and should not
gain one for a single test. It cannot prove the workflow runs: only a run on GitHub does that.

Run from the repo root:  pytest tests/test_ci_workflow.py
"""

import re                                   # regular expressions, for the checksum's shape
from pathlib import Path                    # file paths

REPO_ROOT = Path(__file__).parent.parent                               # tests/ -> repo root
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
STEPS = WORKFLOW.split("\n# Syntax:")[0]                               # the steps, without the explanation at the end of the file


def test_the_checkout_keeps_no_access_token():
    assert "persist-credentials: false" in STEPS


def test_the_secret_scan_runs_before_anything_is_piped_into_a_shell():
    scan = STEPS.index("Secret scan of the tracked files")
    piped_scripts = [match.start() for match in re.finditer(r"\|\s*(sh|bash)\b", STEPS)]
    assert piped_scripts, "expected the dbt installer step; if it is gone, delete this test's second half"
    assert all(scan < position for position in piped_scripts)


def test_the_scan_cannot_be_excused_by_the_commit_it_scans():
    scan_line = next(line for line in STEPS.splitlines() if line.strip().startswith("scan() {"))
    assert "--config .github/gitleaks.toml" in scan_line          # rules from a High-tier file, not from the scanned folder
    assert "--gitleaks-ignore-path" in scan_line                  # no ignore file from the checkout
    assert "--ignore-gitleaks-allow" in scan_line                 # no "gitleaks:allow" comments
    assert "--redact" in scan_line                                # a found secret stays out of the public log
    assert "|| true" not in STEPS                                 # nothing swallows a failing step
    assert not (REPO_ROOT / ".gitleaks.toml").exists()            # nobody should think a file here changes the scan
    assert not (REPO_ROOT / ".gitleaksignore").exists()


def test_the_rules_file_keeps_the_built_in_rules_and_allows_nothing():
    rules = (REPO_ROOT / ".github" / "gitleaks.toml").read_text()
    settings = [line.strip() for line in rules.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert settings == ["[extend]", "useDefault = true"]          # an allowlist added here must change this test too, on purpose


def test_the_scanner_is_pinned_by_checksum_and_proves_it_can_find_a_token():
    assert re.search(r'GITLEAKS_VERSION: "\d+\.\d+\.\d+"', STEPS)
    assert re.search(r'GITLEAKS_SHA256: "[0-9a-f]{64}"', STEPS)
    assert "sha256sum --check" in STEPS
    canary = STEPS.index('if scan "$RUNNER_TEMP/canary"; then')   # the planted token must be found...
    real = STEPS.index('scan "$RUNNER_TEMP/tree"')                # ...before the real scan's result means anything
    assert canary < real
