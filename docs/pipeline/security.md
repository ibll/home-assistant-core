# Security

## Secrets

The security stage scans every commit introduced by a pull request or push
with Gitleaks 8.30.1. Pull requests use the base-to-head commit range; pushes
use the `before..after` range. An initial push scans all available history.
The scanner is downloaded from its versioned GitHub release and checked against
the published SHA-256 checksum before execution.

Gitleaks writes a redacted `gitleaks.sarif` report. If a clean scan produces no
report, the workflow writes an empty SARIF result so the clean run still has
the required artifact. The workflow uploads that report to GitHub Code
Scanning and attaches it to the run as an artifact. A non-zero Gitleaks
result fails the security stage after the report uploads.
Code Scanning upload is skipped for pull requests from forks because GitHub
does not grant those runs the required write permission. The artifact remains
available for those runs.

The security job has `contents: read` to check out code and
`security-events: write` to publish SARIF. The parent workflow grants the same
permissions only to the security stage. Checkout uses `persist-credentials:
false`.
