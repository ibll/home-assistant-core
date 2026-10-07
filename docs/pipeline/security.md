# Security

## Dependencies

The security stage audits `requirements.txt` with `pip-audit` on every run and
uploads the JSON report as the `pip-audit` artifact. A vulnerability found by
the audit fails the stage.

When A1 reports `requirements-changed` on a pull request, the stage also runs
the SHA-pinned `actions/dependency-review-action` with `fail-on-severity: high`.
This checks the pull request's dependency changes against GitHub's advisory
database. The action is limited to pull requests because it reviews a base/head
dependency diff.
