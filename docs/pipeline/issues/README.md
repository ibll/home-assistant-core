# Issue drafts

One file per GitHub issue, 28 in total. Issues are disabled on the fork until
issue L1 turns them on. Then the tech lead reviews these drafts and creates
them:

```bash
ASSIGNEE_L=<lead> ASSIGNEE_A=<handle> ASSIGNEE_B=<handle> ASSIGNEE_C=<handle> ASSIGNEE_D=<handle> \
  ./create-issues.sh            # dry run: prints what it would do
# ...same variables... ./create-issues.sh --create
```

The first two lines of each file (HTML comments) hold the title and labels.
The script strips them from the issue body.

| Issue | Title | Week | Depends on | AI job |
|---|---|---|---|---|
| [L0](L0.md) | Pipeline skeleton: orchestrator and stub stages | 1 | nothing |  |
| [L1](L1.md) | Repo setup: issues, staging environment, branch protection, PR template | 1 | L0 |  |
| [L2](L2.md) | Failure-injection runs prove the pipeline fails correctly | 2 | L0 |  |
| [L3](L3.md) | Metrics collector: pipeline, DORA and AI metrics | 3 | L0 |  |
| [L4](L4.md) | Model comparison: same prompt, several models, scored | 4 | L0 | yes |
| [L5](L5.md) | Final evaluation: score the checklist with evidence | 4 | L2, L3, L4 |  |
| [A1](A1.md) | Change detection: which integrations and files changed | 1 | L0 |  |
| [A2](A2.md) | Lint gate: ruff, codespell, yamllint and hassfest on changed files | 2 | A1 |  |
| [A3](A3.md) | Build artifact: wheel, sdist and checksums | 2 | A2 |  |
| [A4](A4.md) | Caching and timing for build and test | 2 | A2 |  |
| [A5](A5.md) | AI failure triage (advisory) | 3 | A2, B1 | yes |
| [B1](B1.md) | Targeted tests for changed integrations | 2 | A1 |  |
| [B2](B2.md) | Contract suite: protect what depends on the core | 2 | L0 |  |
| [B3](B3.md) | Test reports, coverage gate and artifacts | 2 | B1 |  |
| [B4](B4.md) | Flaky test detection | 3 | B1 |  |
| [B5](B5.md) | AI test-gap advisor (advisory) | 3 | B1, A1 | yes |
| [C1](C1.md) | Secret scanning | 2 | L0 |  |
| [C2](C2.md) | Dependency vulnerability scanning | 2 | A1 |  |
| [C3](C3.md) | New-dependency tracker (flags AI-added dependencies) | 2 | A1, C2 |  |
| [C4](C4.md) | Workflow hardening: zizmor, actionlint, pin check, Scorecard | 3 | L0 |  |
| [C5](C5.md) | SBOM for the wheel (and the image, with D3) | 3 | A3 |  |
| [C6](C6.md) | AI dependency-risk reviewer (advisory) | 3 | C3 | yes |
| [D1](D1.md) | Docker build spike (timeboxed: 1 day) | 1 | L0 |  |
| [D2](D2.md) | Push image to GHCR and sign it | 2 | D1 |  |
| [D3](D3.md) | Image vulnerability scan and image SBOM | 2 | D2, C5 |  |
| [D4](D4.md) | Deploy to staging with approval and a smoke test | 3 | D2, L1 |  |
| [D5](D5.md) | Automatic rollback and GitHub Release | 3 | D4, A3, C5 |  |
| [D6](D6.md) | AI release notes (advisory, human edits before publishing) | 3 | D5 | yes |
