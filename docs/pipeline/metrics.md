# Pipeline metrics (issue L3)

Checklist Q3 asks how we measured whether the AI-assisted pipeline is
effective and efficient. This page defines every number the metrics job
produces and how each one is computed.

## How it runs

| | |
|---|---|
| Workflow | [`team-metrics.yml`](../../.github/workflows/team-metrics.yml) |
| Script | [`.github/scripts/team_metrics.py`](../../.github/scripts/team_metrics.py) (Python 3.14, standard library only) |
| When | Every night at 04:17 UTC, or by hand: `gh workflow run team-metrics.yml -f days=30` |
| Data | The last 30 days of `team-pipeline.yml` runs (change with `days`) |
| Permissions | `actions: read` to read runs, jobs and artifacts; `contents: read` to check out the script |
| Output | A `metrics-<date>` artifact holding `metrics.json` (kept 90 days), plus a summary on the run page |

Each nightly artifact is a snapshot of the last 30 days. Download the artifacts
from different nights to see the trend: two weeks of nights covers the final
report.

To run it locally (needs the GitHub CLI, logged in):

```bash
uv run --no-project --python 3.14 python .github/scripts/team_metrics.py \
  --repo ibll/home-assistant-core --days 30 --output metrics.json --summary summary.md
```

## What each number means

Durations are in seconds. **p50** is the median and **p95** the value 95% of
samples are at or under, both by the nearest-rank method. A metric with no
samples is `null`, so a window with zero runs still produces a complete file.

### Runs (`runs`)

| Field | Definition |
|---|---|
| `total`, `completed`, `not_finished` | Runs created in the window; `not_finished` includes runs waiting for staging approval |
| `by_event` | Completed runs per event (`push`, `pull_request`, `workflow_dispatch`), split by conclusion |
| `success_rate` | `success ÷ (success + failure + timed_out)` over **push and pull-request runs only**. Manual runs are left out because they include `inject_failure` runs, which fail on purpose. Cancelled runs are left out too. |
| `success_rate_by_event` | The same rate for each event separately, manual runs included |
| `reruns.runs_rerun`, `reruns.extra_attempts` | Runs re-run at least once, and the total number of extra attempts (`run_attempt − 1`) |

### Stages (`stages`, `queue_time`, `approval_wait`)

A job's stage is the part of its name before `" / "`: `Build / Lint and build`
belongs to `build`.

| Field | Definition |
|---|---|
| `stages.<stage>.outcomes` | Count of each job conclusion: success, failure, skipped, cancelled |
| `stages.<stage>.duration` | `completed_at − started_at` for jobs that succeeded, failed or timed out |
| `queue_time` | `started_at − created_at`: how long a job waited for a runner. Skipped and cancelled jobs, and the deploy job, are left out. |
| `approval_wait` | The same gap for the deploy job, which is the wait for a person to approve the `staging` environment. It's reported separately so human wait time doesn't look like slow runners (checklist Q10). |

### Flaky tests (`flaky`)

The total number of tests, and the number of runs, listed in `flaky*.json`
artifacts. Issue B4 writes these files, so this stays 0 until B4 is merged.

### DORA (`dora`)

Computed from **deploy jobs in push runs on `main`**, the path every change
takes to staging. Manual runs (branch testing, `inject_failure`) and tag
pushes are left out.

| Field | Definition |
|---|---|
| `deploy_attempts` | Deploy jobs that succeeded or failed |
| `deployments`, `deployment_frequency_per_day` | Successful deploys, and that count divided by the window's days |
| `lead_time` | Time from the run's head commit to the end of a successful deploy. On `main` the head commit is the PR's merge commit, so this measures merge to deployed, approval wait included. |
| `change_failure_rate` | Failed deploys ÷ deploy attempts |
| `time_to_restore` | For each failed deploy: the time to the next successful one. `mean_s` is the mean time to restore. |
| `unresolved_failures` | 1 if the most recent deploy failed and nothing has fixed it yet |

### AI jobs (`ai`)

Read from the `ai-<job>.json` files that every AI job uploads (the format is
in the [README](README.md#rules-for-every-change)).

| Field | Definition |
|---|---|
| `jobs.<job>.runs` | Number of `ai-<job>.json` records |
| `jobs.<job>.statuses` | Count of each `status` the job wrote, for example `valid` or `invalid`. That share is the AI's success rate. |
| `jobs.<job>.tokens`, `runs_reporting_tokens` | Tokens summed over the runs that reported them. `actions/ai-inference` doesn't report usage, so `tokens` is often `null`; `runs_reporting_tokens` shows how many runs the total covers. |
| `jobs.<job>.latency_ms_avg` | Average `latency_ms` |
| `total_tokens`, `tokens_per_pipeline_run` | All reported tokens, and that total divided by completed pipeline runs (checklist N3) |

## First measurement (Nov 19, last 60 days)

A local run of the script over Sep 21 to Nov 20:

| Metric | Value |
|---|---|
| Runs | 54 completed |
| Success rate, push + PR | 84% |
| Reruns | 5 runs, 5 extra attempts |
| Queue time p50 / p95 | 2 s / 3 s |
| Staging approval wait p50 | 20 s |
| Slowest stages (p50) | package 2.1 min (p95 7.2 min), security 1.0 min |
| Deployments from `main` | 8 (0.13 per day), lead time p50 9.4 min |
| Change-failure rate | 0%: all 8 deploys from `main` succeeded |
| AI jobs | `release-notes`: 1 run, status `invalid`, no tokens reported |

What it tells us:

- **Runners aren't the bottleneck.** Queue time is 2 s; the slowest step is
  building the Docker image.
- **Every deploy from `main` succeeded,** but the deploy stage shows 11
  failures elsewhere:
  - 7 from manual test runs on the D1–D4 branches while that work was built
  - 2 from the `smoke` injection runs on `main`
  - 2 from pushing the release tags `v0.0.1-team` and `v0.0.2-team`

  The tag failures are worth checking under D5.
- **The only AI job that has run in the pipeline didn't produce usable
  output:** D6's release notes came back `invalid`. This is the evidence for
  Q3 that AI output has to be validated.

## Limits

- **Stub stages.** Until the real test stage (B1) lands, test durations
  measure a stub.
- **Lead time starts at the merge, not the first commit.** Measuring from
  the first commit would need one more API call per pull request.
- **The window is set by run creation time.** A run created before the
  window that deployed inside it isn't counted.
- **Artifacts expire after 90 days,** so download any you need for the
  final report before then.
