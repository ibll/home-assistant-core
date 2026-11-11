"""Tests for the team security workflow configuration."""

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parents[2] / ".github/workflows/team-security.yml"
PIPELINE_PATH = Path(__file__).parents[2] / ".github/workflows/team-pipeline.yml"


def _load_workflow(path: Path) -> dict[str, object]:
    """Load a GitHub Actions workflow without YAML 1.1 boolean coercion."""
    return yaml.load(path.read_text(), Loader=yaml.BaseLoader)


def test_secret_scanner_is_pinned_and_scans_pr_and_push_commit_ranges() -> None:
    """Gitleaks scans the commit range for the triggering event and fails on findings."""
    workflow = _load_workflow(WORKFLOW_PATH)
    steps = workflow["jobs"]["scan"]["steps"]
    install = next(step for step in steps if step.get("name") == "Install Gitleaks")
    scan = next(
        step for step in steps if step.get("name") == "Scan commits for secrets"
    )

    assert "v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz" in install["run"]
    assert scan["env"]["EVENT_NAME"] == "${{ github.event_name }}"
    assert scan["env"]["PR_BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
    assert scan["env"]["PUSH_BEFORE_SHA"] == "${{ github.event.before }}"
    assert (
        scan["env"]["HEAD_SHA"]
        == "${{ github.event.pull_request.head.sha || github.sha }}"
    )
    assert 'range="$PR_BASE_SHA..$HEAD_SHA"' in scan["run"]
    assert 'range="$PUSH_BEFORE_SHA..$HEAD_SHA"' in scan["run"]
    assert '--log-opts="$range"' in scan["run"]
    assert "--exit-code 1" in scan["run"]


def test_sarif_is_uploaded_to_code_scanning_and_as_an_artifact() -> None:
    """The report is retained and uploaded even when Gitleaks finds a secret."""
    workflow = _load_workflow(WORKFLOW_PATH)
    steps = workflow["jobs"]["scan"]["steps"]
    code_scanning = next(
        step
        for step in steps
        if step.get("name") == "Upload Gitleaks results to Code Scanning"
    )
    artifact = next(
        step for step in steps if step.get("name") == "Upload Gitleaks report artifact"
    )

    assert code_scanning["uses"].startswith("github/codeql-action/upload-sarif@")
    assert code_scanning["with"]["sarif_file"] == "gitleaks.sarif"
    assert "always()" in code_scanning["if"]
    assert artifact["uses"].startswith("actions/upload-artifact@")
    assert artifact["with"]["name"] == "gitleaks"
    assert artifact["with"]["path"] == "gitleaks.sarif"
    assert "always()" in artifact["if"]


def test_security_events_write_is_limited_to_security_job() -> None:
    """Only the reusable security job and its caller grant SARIF upload access."""
    workflow = _load_workflow(WORKFLOW_PATH)
    pipeline = _load_workflow(PIPELINE_PATH)

    assert workflow["permissions"] == {}
    assert workflow["jobs"]["scan"]["permissions"]["security-events"] == "write"
    assert pipeline["permissions"] == {}
    assert pipeline["jobs"]["security"]["permissions"]["security-events"] == "write"
    assert all(
        "security-events" not in job.get("permissions", {})
        for name, job in pipeline["jobs"].items()
        if name != "security"
    )


def test_security_failure_injection_step_is_preserved() -> None:
    """The security stage keeps its failure injection hook."""
    workflow = _load_workflow(WORKFLOW_PATH)
    steps = workflow["jobs"]["scan"]["steps"]
    injection = next(step for step in steps if step.get("name") == "Inject failure")

    assert injection["uses"] == "./.github/actions/team-inject-failure"
    assert injection["with"]["stage"] == "security"
