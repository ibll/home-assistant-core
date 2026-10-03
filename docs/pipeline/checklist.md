# Evaluation checklist

The tech lead fills this in at the end of each week and for the final report.

**Score each item:**

- 0 = missing
- 1 = partial
- 2 = met, with evidence

**Evidence** is a link to a workflow run, a file, an artifact, or an AI-log
entry. "We did it" without a link scores 0.

Q1–Q16 are the course questions, word for word. N1–N10 are extra checks the
course questions do not cover.

| # | Question | Owner | Evidence required | "2 = met" when | Score | Evidence link |
|---|---|---|---|---|---|---|
| Q1 | Which CI/CD concepts did you focus on? What CI/CD tool did you use and how does it support using AI to reduce manual labor? | Lead | `docs/pipeline/README.md` | Lists concepts per stage and names GitHub Actions + GitHub Models with the AI jobs |  |  |
| Q2 | What current CI/CD pipeline already exists for your project and what change, if any, did the AI tool create? | Lead | "Findings" table + diffs of `7574e94c160` and the team PRs | Before/after documented. Every AI change is justified or reverted (incl. `actions: read`) |  |  |
| Q3 | What metrics did you use to measure the effectiveness and efficiency of the AI assisted CI/CD pipeline? | Lead (L3) | `metrics.json` | DORA + duration + success rate + AI tokens/latency/accept rate, over ≥ 2 weeks |  |  |
| Q4 | Have you compared how different models generated different CI/CD pipelines? If yes, what CI/CD concepts did each one focus more on? | Lead (L4) | `model-comparison.md` | ≥ 3 models, same prompt, scored concept matrix + lint results |  |  |
| Q5 | What criteria did you use to evaluate the effectiveness of the CI/CD pipeline within the architecture? | Lead | This checklist + metrics | Criteria are measurable (thresholds stated) |  |  |
| Q6 | How did you develop the CI/CD pipeline so that it aligns with principles of scalability, maintainability and extensibility? | All | Reusable workflows, composite actions, matrix | New stage = 1 file + 1 line. Matrix scales with changed integrations |  |  |
| Q7 | Where in your CI/CD pipeline did you use simple automation and where did you use AI for automation? | All | Table in README | Each job tagged *deterministic* or *AI-advisory*. No AI job gates merges |  |  |
| Q8 | What security guardrails did you implement and how does it support the security hardening and compliance? | C | C1–C6, D2–D3 runs, Scorecard | Pinned SHAs, least privilege, secrets scanning, SBOM, signed image, AI-input sanitization |  |  |
| Q9 | Is the proposed CI/CD pipeline aligned with the project's architecture? | Lead | README | Uses hassfest, the integration layout, Python 3.14/uv, the HA Docker base |  |  |
| Q10 | How much of human intervention is required in the pipeline? | Lead | Run timeline | Human only at: PR review, staging approval, release-note edit. Counted per run |  |  |
| Q11 | Are you tracking all the new dependencies added by the AI tool and checking for any security issues with them? | C (C3) | `new-dependencies.json` | Every new dependency listed with CVE + license result. AI-origin flagged |  |  |
| Q12 | Are the modifications human readable? | All | Code review + AI logs | Named steps, comments explain "why", every AI output reviewed and logged |  |  |
| Q13 | Does the pipeline make sure changes do not break the applications that depend on the shared backend? | B (B2) | Contract-suite runs | Contract suite runs on every PR, and an injected API break fails it |  |  |
| Q14 | Does the pipeline run end to end without errors, and does it fail correctly when a test or step fails? | Lead (L2) | Green run + 5 injected-failure runs | Each injected failure fails the right stage and blocks deploy |  |  |
| Q15 | Does the new CI/CD pipeline perform all the expected CI/CD tasks: build, test, security scanning, artifact storage, and deployment? | All | One run link per task | All 5 present in a single `dev` run |  |  |
| Q16 | Can everyone in your team explain how the AI developed the CI/CD pipelines and/or the changes made to the already existing one? | Lead | AI logs + a 5-min walkthrough by each member | Each member presents their AI log without notes |  |  |
| N1 | Are all actions SHA-pinned, and does every job declare minimal `permissions`? | C | zizmor/actionlint output | Zero findings |  |  |
| N2 | Can AI steps be prompt-injected by untrusted input (PR text, logs, issue bodies)? | C | Test PR with an injection string | Output validated, no write action taken |  |  |
| N3 | What is the AI cost/budget per run, and is it capped? | Lead | `ai-*.json` sums | Tokens per run reported. `max-tokens` set on every call |  |  |
| N4 | Are artifacts traceable to a commit (checksums, SBOM, signature, retention)? | A/D | Artifacts | sha256 + SBOM + cosign verify passes |  |  |
| N5 | Can a failed deploy be rolled back automatically? | D | D5 run | Injected smoke failure restores the previous digest |  |  |
| N6 | Is the pipeline fast enough for PR feedback? | Lead | `metrics.json` | p50 PR run ≤ 15 min (upstream CI is ~13 min for a small change) |  |  |
| N7 | Does the pipeline work on the fork without upstream secrets or runners? | Lead | Run on the fork | No skipped-by-guard or secret-missing failures in `team-*` |  |  |
| N8 | Are flaky tests detected and reported instead of silently retried? | B | B4 output | Flaky list in the metrics |  |  |
| N9 | Is every AI-generated change attributed and reviewed by a human before merge (OHF AI policy, `AI_POLICY.md`)? | Lead | PR history | Trailer present + an approving human review |  |  |
| N10 | Is the pipeline documented well enough for a new member to add a stage? | All | `docs/pipeline/` | A peer adds a dummy stage using only the docs |  |  |

**Total:** ___ / 52

## Per-PR review checklist (tech lead)

Use this on every team PR before approving it.

- [ ] Only `team-*` workflows, `docs/pipeline/` and files the issue names were changed. No upstream workflow was edited.
- [ ] Every new `uses:` is pinned to a full SHA with a version comment.
- [ ] Top-level `permissions: {}`. Each job grants only what it needs, with a comment on each line.
- [ ] Checkouts use `persist-credentials: false`.
- [ ] No `${{ ... }}` inside `run:` scripts. Values go through `env:`.
- [ ] Python comes from `./.github/actions/setup-uv-python` (3.14).
- [ ] zizmor (`--pedantic`), actionlint and yamllint pass. Paste the output in the PR.
- [ ] The PR links a green run of `team-pipeline`, plus an `inject_failure` run if the stage supports it.
- [ ] The artifact named in the issue shows up on the run.
- [ ] `docs/pipeline/<stage>.md` is updated, and there is an AI-log entry for this issue.
- [ ] AI-written code is attributed (`AI-Assisted:` trailer or `Co-Authored-By:`), and the author can explain every line (Q16).
- [ ] If an AI job was added: it is advisory only, has `models: read` only, sets `max-tokens`, validates its output, and uploads `ai-<job>.json`.

## Rubric for each AI job (A5, B5, C6, D6, L4)

Fill one row per AI job after at least 10 runs.

| AI job | Model | Runs | Useful outputs / runs | Wrong or harmful outputs | Avg tokens | Avg latency | Human minutes saved (estimate) | Keep? |
|---|---|---|---|---|---|---|---|---|
| A5 failure triage | | | | | | | | |
| B5 test-gap advisor | | | | | | | | |
| C6 dependency-risk reviewer | | | | | | | | |
| D6 release notes | | | | | | | | |
| L4 model comparison | | | | | | | | |

"Useful" means a human acted on the output. "Wrong or harmful" means the
output was incorrect, or would have done damage if it had been acted on
without review.
