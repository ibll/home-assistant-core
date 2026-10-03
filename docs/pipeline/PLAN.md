# Plan: AI-assisted CI/CD pipeline for the `ibll/home-assistant-core` fork

## Context

The course asks a 5-person team to build a CI/CD pipeline on GitHub Actions and evaluate how AI helps. The project is a fork of Home Assistant Core, which already ships a very large upstream pipeline. The team's first attempt failed. Goal of this plan:

- Map what already exists.
- Define a **separate, additive pipeline** the team owns.
- Split it into issues so that 4 members build one stage each and the tech lead owns the orchestrator and validation.
- Upgrade the tech lead's evaluation checklist so every question needs evidence.

Decisions made: the pipeline calls AI through **GitHub Models** (`actions/ai-inference`, `models: read`). Deploy means **pushing to GHCR, then a `staging` GitHub Environment with an approval gate and a smoke test**. The **tech lead owns the orchestrator**.

## What exists today (findings)

| Workflow | Trigger | On the fork |
|---|---|---|
| `ci.yaml` (1,600 lines): change detection (`info`), prek, zizmor, hadolint, hassfest, pylint, mypy, dependency-review, license audit, split pytest, MariaDB/Postgres, Codecov | push/PR | **Runs.** Last run passed in 12m49s. Codecov steps need a secret. |
| `builder.yml`: Docker images, cosign, PyPI, E2E | release/schedule | **Skipped**, guarded by `github.repository_owner == 'home-assistant'` |
| `wheels.yml`, `e2e-tests.yml`, `translations.yml`, `stale.yml` | various | **Skipped**, same guard |
| `codeql.yml` | weekly | **Runs** (~19 min) |
| `detect-duplicate-issues.yml`, `detect-non-english-issues.yml` | issues | AI via GitHub Models (gpt-4o / gpt-4o-mini). Dormant, because **Issues are disabled on the fork**. |
| `check-requirements.md` → `.lock.yml` | workflow_run | **AI agentic workflow** (gh-aw + Copilot engine, firewall, threat detection, safe-outputs). A good reference for AI guardrails. |
| `.github/renovate.json` | — | Dependency bot config |

**Why the first attempt failed** (commits `b151b963600`, `60de69d8988`, runs 36728109818 / 36726778129):
- It used Python 3.12/3.13, but `pyproject.toml` requires `>=3.14.2`.
- It ran `pip install -r requirements.txt` plus the *entire* test suite with `--maxfail=1`.
- Actions were unpinned (`@v7`).
- The "Custom" workflow targeted a self-hosted runner that never existed, so it sat queued for 24h until cancelled.

These make good "before/after" evidence for checklist Q2.

**Commit `7574e94c160` "Implement AI-suggested changes"** is a real AI change to validate:
- Adds `timeout-minutes` to jobs.
- Hardens the parsing of AI output in duplicate detection (a good anti-prompt-injection change).
- Moves the lock/stale crons from hourly to daily.
- Adds `actions: read` to `build_base`. This is **questionable**: it widens permissions, and the tech lead should verify it is needed.

**Reusable pieces in the repo:**
- `.github/actions/setup-uv-python` (sets up Python 3.14 via uv)
- `.github/actions/restore-or-build-venv`
- `script/hassfest`
- `script/licenses.py`
- `script/split_tests.py`
- `.pre-commit-config.yaml` (ruff, codespell, zizmor, yamllint)
- `Dockerfile` (takes `BUILD_FROM=ghcr.io/home-assistant/amd64-homeassistant-base:<ver>`, which is public)
- `tests/components/api`, `tests/components/websocket_api`, `tests/test_core.py`, `tests/helpers/`

## Design rules (apply to every issue)

1. **Additive only.** All new files are `.github/workflows/team-*.yml`. Never edit `ci.yaml` or the other upstream files, which keeps upstream syncs conflict-free.
2. **Python 3.14 via `./.github/actions/setup-uv-python`.** Never use `actions/setup-python` with 3.12/3.13.
3. **Pin every action to a full commit SHA** with a `# vX.Y.Z` comment, the same convention as upstream.
4. **Least privilege.** Set top-level `permissions: {}` and grant per job. Use `persist-credentials: false` on checkout.
5. **Fast by default.** Only test the integrations a PR changed, plus a fixed contract suite. The full suite stays upstream's job.
6. **AI is advisory and never a merge gate.**
   - AI jobs get read-only permissions plus `models: read`.
   - Untrusted text (PR titles, logs, diffs) is passed as data and never interpolated into `run:`.
   - Validate model output against an allow-list before acting on it, following the pattern in `7574e94c160`.
   - Each AI job writes `ai-<job>.json` with `{model, prompt_hash, tokens, latency, output}` as an artifact, for metrics.
7. **Each stage is a reusable workflow** (`on: workflow_call`). The orchestrator only wires them, so adding a stage means adding one file and one `uses:` line.
8. **Every issue ships three things:**
   - Code
   - Artifact(s)
   - A doc in `docs/pipeline/<stage>.md` plus an AI log entry in `docs/pipeline/ai-log/<issue>.md` recording:
     - Tool and model
     - Prompt
     - Raw output
     - What the human changed and why

## Target pipeline

```
team-pipeline.yml  (PR + push to dev + workflow_dispatch)        [Lead]
 ├─ changes      → which integrations/files changed               [A]
 ├─ build        → lint, hassfest, wheel/sdist  ─┐                [A]
 ├─ test         → changed-integration tests + contract suite     [B]
 ├─ security     → secrets, deps, SAST, SBOM, new-dep tracker     [C]
 ├─ ai-advisory  → triage / test-gap / dep-risk / release notes   [A–D, one each]
 └─ (dev only) package → docker build → GHCR → sign → scan        [D]
                    └─ deploy-staging (Environment approval) → smoke test → rollback-on-fail [D]
team-metrics.yml   (nightly) → DORA + pipeline + AI metrics → artifact + job summary [Lead]
team-model-compare.yml (dispatch) → same prompt × N models → comparison artifact     [Lead]
```

## Workstreams and issues

The tech lead assigns Members A–D to the four collaborators (`ibll`, `odinsean`, `Aaron-Massey`, `kalyanivalath`). Each issue lists **Deliverable / Artifact / AI use / Done when**.

### Lead (tech lead): orchestrator, validation, metrics

- **L0 Pipeline skeleton** (do first, it unblocks everyone). **Done in this branch** as stubs.
  - Deliverable: `team-pipeline.yml` with stub `workflow_call` jobs, `concurrency`, `permissions: {}`, and a fork guard (`github.repository == 'ibll/home-assistant-core'`).
  - Also add `docs/pipeline/README.md` and the AI-log template.
  - Done when: a green run of the stubs.
- **L1 Repo setup** (manual settings):
  - Enable Issues.
  - Create the `staging` environment with the tech lead as required reviewer.
  - Add branch protection on `dev` that requires the `team-pipeline` checks.
  - Add a PR template section "AI used? link to ai-log".
- **L2 Failure-proof suite.** Add a `workflow_dispatch` input `inject_failure: {none,lint,test,security,smoke}` that makes the chosen stage fail on purpose. This proves "fails correctly" (Q14). Artifact: a run link per mode.
- **L3 Metrics collector** (`team-metrics.yml`, nightly). Uses `gh api` on the Actions runs/jobs endpoints to compute:
  - Duration (p50/p95) per stage
  - Queue time
  - Success rate
  - Flaky reruns
  - DORA metrics: deploy frequency, lead time, change-failure rate, MTTR
  - Sums from the AI logs: tokens, latency, accept rate

  Artifact: `metrics.json` plus a markdown job summary.
- **L4 Model comparison** (`team-model-compare.yml`, dispatch).
  - Sends one fixed prompt, "generate a GitHub Actions CI workflow for <this repo summary>", to about 4 GitHub Models: for example `openai/gpt-4.1`, `openai/gpt-4o-mini`, `meta/llama-...`, `mistral-ai/...`, `deepseek/...`.
  - Lints each output with `actionlint` and `zizmor`.
  - Scores CI/CD concept coverage: build, test, cache, matrix, security, artifacts, deploy, permissions, pinning.

  Artifact: `model-comparison.md` (answers Q4).
- **L5 Checklist evaluation and final report.** Fill in the upgraded checklist below with evidence links.

### Member A: change detection, build, quality

- **A1 Change detection.**
  - Job outputs: `integrations` (JSON list), `core_changed`, `requirements_changed`, `workflows_changed`.
  - Compute from `git diff` against the merge base. Mirror the logic of the `info` job in `ci.yaml`, simplified.
  - Done when: a PR touching `homeassistant/components/demo` outputs `["demo"]`.
- **A2 Lint gate.** Run ruff check/format, codespell, and yamllint on changed files, using `setup-uv-python` and versions pinned from `requirements_test_pre_commit.txt`. Run `python -m script.hassfest --integration-path` for each changed integration.
- **A3 Build artifact.**
  - Run `uv build` to produce the sdist and wheel, plus a `SHA256SUMS` file.
  - Upload with `actions/upload-artifact` (retention 14 days).
  - Done when: the artifact is downloadable and the checksums verify.
- **A4 Caching.** Cache the uv cache and venv keyed on `hashFiles('requirements*.txt', 'pyproject.toml')`. Record cold vs warm build time in the doc.
- **A5 AI failure triage** (AI).
  - When any stage fails, take the last ~200 log lines, send them to GitHub Models, and get a JSON `{root_cause, suspected_file, suggested_fix}` back.
  - Post the result in the job summary and as a PR comment.
  - Never auto-fixes anything. Log precision manually: was the triage right?

### Member B: tests and contract safety

- **B1 Targeted tests.** Run `pytest tests/components/<each changed integration>`, using the matrix from A1. Use `--junitxml` and `--cov` scoped to those integrations.
- **B2 Contract suite** ("doesn't break dependents", Q13).
  - Always run `tests/test_core.py`, `tests/components/api`, `tests/components/websocket_api`, `tests/helpers/test_entity.py`, and `tests/test_config_entries.py`.
  - These protect the REST/WebSocket API that the frontend, mobile apps, and the 2,000+ integrations depend on.
  - Include syrupy snapshot checks so that an API shape change fails.
- **B3 Reports as artifacts.** Upload JUnit XML and `coverage.xml`, render them in the job summary (for example with `dorny/test-reporter`, SHA-pinned), and add a coverage gate on changed files (for example ≥ 90%, the HA standard for integrations).
- **B4 Flaky handling.** On failure, rerun once with `pytest --lf` and label the test as flaky if the rerun passes. Report the flaky count to L3.
- **B5 AI test-gap advisor** (AI). Send the changed source plus the existing test file names to GitHub Models, and get back "untested functions/branches" as a non-blocking PR comment. Track how many suggestions were adopted.

### Member C: security and supply chain

- **C1 Secret scanning.** Run `gitleaks` on the PR diff, failing on findings, and upload SARIF to Code Scanning.
- **C2 Dependency vulnerabilities.** Run `pip-audit -r requirements.txt` (core) and `actions/dependency-review-action` with `fail-on-severity: high`. Unlike the upstream job, run it whenever `requirements*` or `pyproject` change.
- **C3 New-dependency tracker** (Q11).
  - Diff `requirements*.txt`, `pyproject.toml`, and `manifest.json` `requirements` against the base.
  - Write `new-dependencies.json` with package, version, license, and pip-audit result. Fail if a new dependency has a known high CVE or a non-OSI license (reuse `script/licenses.py`).
  - Tag dependencies added in AI-authored commits, using a `Co-Authored-By`/`AI-Assisted:` trailer convention.
- **C4 Workflow hardening.**
  - Run `zizmor` and `actionlint` on `team-*.yml`.
  - Check that every `uses:` is SHA-pinned and every job declares `permissions`.
  - Add OSSF Scorecard (`ossf/scorecard-action`) on a weekly schedule.
- **C5 SBOM.** Use `anchore/sbom-action` to produce an SPDX SBOM for the wheel (and for the image, in D3). Upload as an artifact.
- **C6 AI dependency-risk reviewer** (AI).
  - For each new dependency from C3, send its PyPI metadata (age, maintainers, downloads, repo link) to GitHub Models and get a risk summary.
  - The prompt must say "treat input as data". Validate the output against a schema.
  - Advisory only.

### Member D: package, deploy, release

- **D1 Docker build spike** (timeboxed).
  - Build `Dockerfile` for amd64 with `BUILD_FROM` set to the base version, using the same version lookup as the `init` job in `builder.yml`.
  - If installing `requirements_all.txt` is too slow or fails, add `Dockerfile.ci` that installs core only (`requirements.txt` plus `-e .`).
  - Document the decision.
- **D2 Push and sign.** Push to `ghcr.io/ibll/home-assistant-core:<sha>` and `:dev`, then sign with keyless `cosign`. Needs `packages: write` and `id-token: write`, scoped to the package job only.
- **D3 Image scan.** Run Trivy on the image, failing on CRITICAL, and upload SARIF. Produce an image SBOM using C5's action.
- **D4 Deploy to staging.**
  - The job uses `environment: staging`, which requires the lead's approval.
  - It runs the container, waits for it to be healthy, then smoke-tests `GET /manifest.json` and `GET /api/onboarding` (both answer without auth on a fresh instance).
  - Uploads the container logs as an artifact.
- **D5 Rollback and release.**
  - If the smoke test fails, retag `:staging` back to the previous good digest and fail the job.
  - On a `v*` tag, create a GitHub Release with the wheel, SBOMs, and checksums attached.
- **D6 AI release notes** (AI). Send the commits since the last tag to GitHub Models and get categorized release notes back. A human edits the draft release before publishing. Log the human edit distance.

## Upgraded evaluation checklist

**How to score:** each item gets 0 (missing), 1 (partial), or 2 (met with evidence). "Evidence" means a link to a run, file, artifact, or AI-log entry. The professor's original 16 questions are kept word for word as Q1–Q16. New items are N1–N10.

| # | Question | Owner | Evidence required | "2 = met" when |
|---|---|---|---|---|
| Q1 | Which CI/CD concepts did you focus on? What CI/CD tool did you use and how does it support using AI to reduce manual labor? | Lead | `docs/pipeline/README.md` | Lists concepts per stage and names GitHub Actions + GitHub Models with the AI jobs |
| Q2 | What current CI/CD pipeline already exists for your project and what change, if any, did the AI tool create? | Lead | "Findings" table + diffs of `7574e94c160` and the team PRs | Before/after documented. Every AI change is justified or reverted (incl. `actions: read`) |
| Q3 | What metrics did you use to measure the effectiveness and efficiency of the AI assisted CI/CD pipeline? | Lead (L3) | `metrics.json` | DORA + duration + success rate + AI tokens/latency/accept rate, over ≥ 2 weeks |
| Q4 | Have you compared how different models generated different CI/CD pipelines? If yes, what CI/CD concepts did each one focus more on? | Lead (L4) | `model-comparison.md` | ≥ 3 models, same prompt, scored concept matrix + lint results |
| Q5 | What criteria did you use to evaluate the effectiveness of the CI/CD pipeline within the architecture? | Lead | This checklist + metrics | Criteria are measurable (thresholds stated) |
| Q6 | How did you develop the CI/CD pipeline so that it aligns with principles of scalability, maintainability and extensibility? | All | Reusable workflows, composite actions, matrix | New stage = 1 file + 1 line. Matrix scales with changed integrations |
| Q7 | Where in your CI/CD pipeline did you use simple automation and where did you use AI for automation? | All | Table in README | Each job tagged *deterministic* or *AI-advisory*. No AI job gates merges |
| Q8 | What security guardrails did you implement and how does it support the security hardening and compliance? | C | C1–C6, D2–D3 runs, Scorecard | Pinned SHAs, least privilege, secrets scanning, SBOM, signed image, AI-input sanitization |
| Q9 | Is the proposed CI/CD pipeline aligned with the project's architecture? | Lead | README | Uses hassfest, the integration layout, Python 3.14/uv, the HA Docker base |
| Q10 | How much of human intervention is required in the pipeline? | Lead | Run timeline | Human only at: PR review, staging approval, release-note edit. Counted per run |
| Q11 | Are you tracking all the new dependencies added by the AI tool and checking for any security issues with them? | C (C3) | `new-dependencies.json` | Every new dependency listed with CVE + license result. AI-origin flagged |
| Q12 | Are the modifications human readable? | All | Code review + AI logs | Named steps, comments explain "why", every AI output reviewed and logged |
| Q13 | Does the pipeline make sure changes do not break the applications that depend on the shared backend? | B (B2) | Contract-suite runs | Contract suite runs on every PR, and an injected API break fails it |
| Q14 | Does the pipeline run end to end without errors, and does it fail correctly when a test or step fails? | Lead (L2) | Green run + 5 injected-failure runs | Each injected failure fails the right stage and blocks deploy |
| Q15 | Does the new CI/CD pipeline perform all the expected CI/CD tasks: build, test, security scanning, artifact storage, and deployment? | All | One run link per task | All 5 present in a single `dev` run |
| Q16 | Can everyone in your team explain how the AI developed the CI/CD pipelines and/or the changes made to the already existing one? | Lead | AI logs + a 5-min walkthrough by each member | Each member presents their AI log without notes |
| N1 | Are all actions SHA-pinned, and does every job declare minimal `permissions`? | C | zizmor/actionlint output | Zero findings |
| N2 | Can AI steps be prompt-injected by untrusted input (PR text, logs, issue bodies)? | C | Test PR with an injection string | Output validated, no write action taken |
| N3 | What is the AI cost/budget per run, and is it capped? | Lead | `ai-*.json` sums | Tokens per run reported. `max-tokens` set on every call |
| N4 | Are artifacts traceable to a commit (checksums, SBOM, signature, retention)? | A/D | Artifacts | sha256 + SBOM + cosign verify passes |
| N5 | Can a failed deploy be rolled back automatically? | D | D5 run | Injected smoke failure restores the previous digest |
| N6 | Is the pipeline fast enough for PR feedback? | Lead | `metrics.json` | p50 PR run ≤ 15 min (upstream CI is ~13 min for a small change) |
| N7 | Does the pipeline work on the fork without upstream secrets or runners? | Lead | Run on the fork | No skipped-by-guard or secret-missing failures in `team-*` |
| N8 | Are flaky tests detected and reported instead of silently retried? | B | B4 output | Flaky list in the metrics |
| N9 | Is every AI-generated change attributed and reviewed by a human before merge (OHF AI policy, `AI_POLICY.md`)? | Lead | PR history | Trailer present + an approving human review |
| N10 | Is the pipeline documented well enough for a new member to add a stage? | All | `docs/pipeline/` | A peer adds a dummy stage using only the docs |

## Order of work

1. **Week 1:** L0, L1, A1, and the D1 spike. Every member writes their stage as a stub that passes.
2. **Week 2:** A2–A4, B1–B3, C1–C3, D2–D3. L2 failure injection.
3. **Week 3:** the AI jobs (A5, B5, C6, D6), C4–C5, B4, D4–D5. L3 metrics begin collecting.
4. **Week 4:** L4 model comparison, final metrics, scored checklist, and each member's walkthrough (Q16).

## Files to be created (no upstream files modified)

- `.github/workflows/team-pipeline.yml` (Lead)
- `.github/workflows/team-{changes,build,test,security,package,deploy,ai-advisory}.yml`
- `.github/workflows/team-metrics.yml`
- `.github/workflows/team-model-compare.yml`
- `.github/ai-prompts/*.prompt.yml`: versioned prompts so the models can be compared
- `Dockerfile.ci`: only if D1 needs it
- `docs/pipeline/README.md`
- `docs/pipeline/<stage>.md`
- `docs/pipeline/ai-log/<issue>.md`
- `docs/pipeline/checklist.md`
- `docs/pipeline/model-comparison.md`

## Verification

- `uv run --no-sync prek run --files .github/workflows/team-*.yml`: covers zizmor, yamllint, and prettier for the new workflows.
- `actionlint .github/workflows/team-*.yml`
- Push to a branch, then `gh run watch` on `team-pipeline`. The stubs should go green.
- `gh workflow run team-pipeline.yml -f inject_failure=test` should fail at the test stage and skip deploy.
- `gh run list -w team-pipeline` provides the run links that go into the checklist evidence column.
