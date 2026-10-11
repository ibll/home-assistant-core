# Failure injection (issue L2)

Checklist Q14 asks whether the pipeline fails *correctly*. A pipeline that
only ever goes green proves nothing. We force each stage to fail on purpose
and check three things:

- the right stage fails,
- every stage that depends on it is skipped,
- nothing is packaged or deployed.

## How it works

`team-pipeline.yml` has a manual-run input, `inject_failure`. The orchestrator
passes it to every stage. Each stage starts with the shared action
`.github/actions/team-inject-failure`, which fails the job only when the input
names that stage:

| `inject_failure` | Fails in | Job |
|---|---|---|
| `lint` | `team-build.yml` | Build / Lint and build |
| `test` | `team-test.yml` | Test / Targeted and contract tests |
| `security` | `team-security.yml` | Security / Security scans |
| `smoke` | `team-deploy.yml` | Deploy / Deploy to staging and smoke test |

The stages depend on each other like this, which decides what must be skipped:

```text
changes ─┬─ build ── test ─┬─ package ── deploy
         └─ security ──────┘
ai-advisory runs after build, test and security, even when they fail
```

## Running it

Run the modes **one at a time**: a new manual run on a branch cancels the
previous manual run there. Since Oct 11 the concurrency groups include the
event name, so a manual run no longer cancels a push run, or the other way
round.

```bash
gh workflow run team-pipeline.yml --ref main -f inject_failure=lint
gh run watch          # wait for it to finish before starting the next mode
```

The `smoke` mode reaches the deploy job, which waits for a reviewer to approve
the `staging` environment. Approve it on the run page, and the job then fails
at the injection step.

## Results

All runs are on `main`. The stages were still stubs at the time, so these runs
prove the wiring and the dependencies between stages, not the stages'
real checks.

| Mode | Commit | Failed | Skipped | Still ran | Verdict | Run |
|---|---|---|---|---|---|---|
| none (baseline) | `da3948f` | nothing | nothing | all 7 stages | ✅ green | [37149515893](https://github.com/ibll/home-assistant-core/actions/runs/37149515893) |
| `test` | `da3948f` | Test | package, deploy | changes, build, security, ai-advisory | ✅ as expected | [37149559256](https://github.com/ibll/home-assistant-core/actions/runs/37149559256) |
| `lint` | `1bb449a` | Build | test, package, deploy | changes, security, ai-advisory | ✅ as expected | [38164316906](https://github.com/ibll/home-assistant-core/actions/runs/38164316906) |
| `security` | `1bb449a` | Security | package, deploy | changes, build, test, ai-advisory | ✅ as expected | [38164362989](https://github.com/ibll/home-assistant-core/actions/runs/38164362989) |
| `smoke` | `1bb449a` | — | — | all stages up to deploy passed | ⚠️ cancelled while waiting for approval: the PR #31 merge push started a run in the same concurrency group | [38164426398](https://github.com/ibll/home-assistant-core/actions/runs/38164426398) |

In the `lint` run, security still runs because it doesn't depend on build.
That's correct: one failing stage shouldn't hide another stage's findings.

## Real failures (not injected)

These failures came from the real checks in the C1 and C2 pull requests.
They show the security stage stopping the pipeline on real problems.

| What happened | Stage | Result | Run |
|---|---|---|---|
| PR #32 planted a fake secret to test Gitleaks (C1) | Security | ✅ failed: `leaks found: 1` | [37670795416](https://github.com/ibll/home-assistant-core/actions/runs/37670795416) |
| PR #33 audited `requirements.txt` with pip-audit (C2) | Security | ✅ failed: 15 known vulnerabilities, 14 in pyjwt 2.13.0 and 1 in uv 0.12.17 | [37690019419](https://github.com/ibll/home-assistant-core/actions/runs/37690019419) |

## What we learned

- **Manual runs and push runs on `main` cancelled each other.** It happened
  three times:
  - Oct 3: the `test` run cancelled a push run.
  - Oct 11: the `lint` run cancelled the push run for the PR #30 merge.
  - Oct 11: the PR #31 merge push cancelled the `smoke` run while it waited
    for approval.

  The fix (Oct 11, branch `l2-failure-injection`) adds `github.event_name`
  to the orchestrator's concurrency group and to every stage's group.
  Two runs of the same event on the same branch still replace each other,
  which is the point of the group.
- **A real check can hide an injected failure.** After C1 merged, Gitleaks
  scanned the full history on every manual run (1,240 findings) and failed
  the security stage first. Run 38165813211 never got near deploy. Since
  manual runs now scan only the commit being built, an injected failure is
  the only failure again. When a stage's real checks land, rerun its mode and
  confirm the injected stage is the *only* one that fails.
- **The approval gate holds.** A deploy can't reach the smoke test until the
  staging reviewer approves. One push run waited 8 days for approval before it
  was cancelled.

## Still to do

- [ ] Run `smoke` again once the Gitleaks scan-range fix is merged, and
      approve the staging deployment. (The concurrency fix is merged.)
- [ ] Repeat all four modes once the real stages are merged (A2, B1, C1, C2,
      D4). The injection step must stay first in every stage; each branch has
      kept it so far.
- [ ] A real broken-test PR, once B1's targeted tests are merged.
- [ ] A real failed smoke test, once D4's smoke test exists. Checking that the
      rollback works is D5's job (checklist N5).
