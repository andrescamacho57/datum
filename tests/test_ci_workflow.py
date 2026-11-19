"""test_ci_workflow.py: the secret scan in .github/workflows/ci.yml keeps the properties that make it worth trusting.

The workflow file is the one check that runs on GitHub's machine, and a small edit to it can leave a
step that still shows green and no longer checks anything. This test reads the file as text and holds
five properties in place:

1. The checkout does not keep the run's access token on disk.
2. The secret scan runs before the one step that downloads and runs an unpinned script (dbt's installer),
   so that script cannot get between the scanner and its checksum.
3. The scan takes its rules from .github/gitleaks.toml, and every tracked file is scanned under a plain numbered
   name, so no file in the commit can excuse itself or another by what it is called.
4. The scanner is pinned by a full SHA-256 checksum, and the step first proves it can find a planted token.
5. Nothing lets a failing scan pass, and no cache carries files from one run to the next.

It reads text and not parsed YAML, because the project has no YAML package installed and should not
gain one for a single test. It cannot prove the workflow runs: only a run on GitHub does that.

Run from the repo root:  pytest tests/test_ci_workflow.py
"""

import re                                   # regular expressions, for the checksum's shape
from pathlib import Path                    # file paths

REPO_ROOT = Path(__file__).parent.parent                               # tests/ -> repo root
WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
STEPS = WORKFLOW.split("\n# Syntax:")[0]                               # the steps, without the explanation at the end of the file


STEP_STARTS = re.findall(r"^      - (?:name|uses): (.+?)(?:\s+#.*)?$", STEPS, flags=re.MULTILINE)       # each step's name, in order
CODE_LINES = [line.split("   #")[0].rstrip() for line in STEPS.splitlines() if not line.strip().startswith("#")]   # the steps without their comments
CODE = "\n".join(CODE_LINES)

COPY_LINE = """git ls-files -z | { n=0; while IFS= read -r -d '' f; do n=$((n+1)); cp -- "$f" "$RUNNER_TEMP/flat/$n.txt"; printf '%s.txt is %s\\n' "$n" "$f" >> "$RUNNER_TEMP/names.txt"; done; }"""
CANARY_LINE = """if scan "$RUNNER_TEMP/canary"; then echo "The scanner missed a planted fake token, so a clean result would prove nothing."; exit 1; fi"""
REAL_SCAN_LINE = """if ! scan "$RUNNER_TEMP/flat"; then echo "Which numbered file is which:"; cat "$RUNNER_TEMP/names.txt"; exit 1; fi"""


def test_the_checkout_keeps_no_access_token():
    assert "          persist-credentials: false" in CODE_LINES     # a real setting on its own line, not a mention in a comment


def test_the_secret_scan_is_the_first_step_after_the_checkout():
    assert STEP_STARTS[:2] == ["actions/checkout@v4", "Secret scan of the tracked files"]
    piped_scripts = [match.start() for match in re.finditer(r"\|\s*(sh|bash)\b", CODE)]
    assert piped_scripts, "expected the dbt installer step; if it is gone, delete this assertion and the next"
    assert all(CODE.index("Secret scan of the tracked files") < position for position in piped_scripts)


def test_the_scan_cannot_be_excused_by_the_commit_it_scans():
    scan_line = next(line for line in CODE_LINES if line.strip().startswith("scan() {"))
    assert "--config .github/gitleaks.toml" in scan_line          # rules from a High-tier file, not from the scanned folder
    assert "--gitleaks-ignore-path" in scan_line                  # no ignore file from the checkout
    assert "--ignore-gitleaks-allow" in scan_line                 # no "gitleaks:allow" comments
    assert "--redact" in scan_line                                # a found secret stays out of the public log
    assert COPY_LINE in [line.strip() for line in CODE_LINES]     # every tracked file, each under a numbered name: no narrowing, no real names


def test_nothing_lets_a_failing_scan_pass():
    assert "continue-on-error" not in CODE                        # a step marked this way shows green when it fails
    assert not re.search(r"\|\|\s*(true|:)", CODE)                # nor may a command's failure be swallowed
    assert "\n        if:" not in CODE                            # nor may a step be made conditional
    assert "cache:" not in CODE                                   # and no cache carries files from one run to the next


def test_the_rules_file_keeps_the_built_in_rules_and_allows_nothing():
    rules = (REPO_ROOT / ".github" / "gitleaks.toml").read_text()
    settings = [line.strip() for line in rules.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert settings == ["[extend]", "useDefault = true"]          # an allowlist added here must change this test too, on purpose


def test_the_scanner_is_pinned_by_checksum_and_proves_it_can_find_a_token():
    stripped = [line.strip() for line in CODE_LINES]
    assert re.search(r'GITLEAKS_VERSION: "\d+\.\d+\.\d+"', CODE)
    assert re.search(r'GITLEAKS_SHA256: "[0-9a-f]{64}"', CODE)
    assert any(line.endswith("| sha256sum --check") for line in stripped)
    assert stripped.index(CANARY_LINE) < stripped.index(REAL_SCAN_LINE)   # the planted token must be found before the real scan means anything
