# Standalone script run by team-metrics.yml, not an importable package.
# ruff: noqa: INP001
"""Measure the team pipeline from the GitHub Actions API (issue L3).

Reads the runs, jobs and artifacts of team-pipeline.yml with the GitHub CLI,
then writes metrics.json and a markdown summary. docs/pipeline/metrics.md
defines every number.

Usage:
    python .github/scripts/team_metrics.py --days 30 --output metrics.json \
        --summary "$GITHUB_STEP_SUMMARY"
"""

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
import io
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any
import urllib.parse
import zipfile

WORKFLOW = "team-pipeline.yml"
DEFAULT_BRANCH = "main"
STAGE_ORDER = [
    "changes",
    "build",
    "test",
    "security",
    "ai-advisory",
    "package",
    "deploy",
]
# Manual runs include inject_failure runs, which fail on purpose, so the
# headline success rate only counts push and pull request runs.
HEADLINE_EVENTS = ("push", "pull_request")
DECIDED = ("success", "failure", "timed_out")

type Json = dict[str, Any]


def parse_time(value: str | None) -> datetime | None:
    """Parse a GitHub timestamp, or return None when it is missing."""
    if not value:
        return None
    return datetime.fromisoformat(value)


def seconds_between(start: str | None, end: str | None) -> float | None:
    """Return the seconds from start to end, or None if either is missing."""
    start_time, end_time = parse_time(start), parse_time(end)
    if start_time is None or end_time is None:
        return None
    return (end_time - start_time).total_seconds()


def percentile(values: list[float], pct: float) -> float | None:
    """Return the nearest-rank percentile, or None when there are no samples."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def describe(values: list[float]) -> Json:
    """Summarize a list of durations in seconds."""
    p50, p95 = percentile(values, 50), percentile(values, 95)
    return {
        "samples": len(values),
        "p50_s": None if p50 is None else round(p50, 1),
        "p95_s": None if p95 is None else round(p95, 1),
        "mean_s": round(sum(values) / len(values), 1) if values else None,
    }


def stage_of(job_name: str) -> str:
    """Map "Build / Lint and build" to "build" and "AI advisory" to "ai-advisory"."""
    return job_name.split(" / ", 1)[0].strip().lower().replace(" ", "-")


def run_metrics(runs: list[Json]) -> Json:
    """Count runs and compute success rates and reruns."""
    completed = [run for run in runs if run["status"] == "completed"]
    by_event: dict[str, Counter[str]] = defaultdict(Counter)
    for run in completed:
        by_event[run["event"]][run["conclusion"]] += 1

    def rate(events: tuple[str, ...]) -> float | None:
        counts: Counter[str] = Counter()
        for event in events:
            counts.update(by_event.get(event, Counter()))
        decided = sum(counts[conclusion] for conclusion in DECIDED)
        return round(counts["success"] / decided, 3) if decided else None

    reruns = [run for run in runs if run["run_attempt"] > 1]
    return {
        "total": len(runs),
        "completed": len(completed),
        "not_finished": len(runs) - len(completed),
        "by_event": {event: dict(counts) for event, counts in by_event.items()},
        "success_rate": rate(HEADLINE_EVENTS),
        "success_rate_by_event": {event: rate((event,)) for event in by_event},
        "reruns": {
            "runs_rerun": len(reruns),
            "extra_attempts": sum(run["run_attempt"] - 1 for run in reruns),
        },
    }


def stage_metrics(jobs_by_run: dict[int, list[Json]]) -> Json:
    """Compute per-stage outcomes and durations, queue time and approval wait."""
    outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    durations: dict[str, list[float]] = defaultdict(list)
    queue: list[float] = []
    approval_wait: list[float] = []
    for jobs in jobs_by_run.values():
        for job in jobs:
            if job["status"] != "completed":
                continue
            stage = stage_of(job["name"])
            outcomes[stage][job["conclusion"]] += 1
            if job["conclusion"] in DECIDED:
                duration = seconds_between(job["started_at"], job["completed_at"])
                if duration is not None:
                    durations[stage].append(duration)
            waited = seconds_between(job["created_at"], job["started_at"])
            if waited is None or job["conclusion"] in ("skipped", "cancelled"):
                continue
            # The deploy job's wait is the staging approval, not a runner queue.
            (approval_wait if stage == "deploy" else queue).append(waited)

    stages = {}
    for stage in STAGE_ORDER + sorted(set(outcomes) - set(STAGE_ORDER)):
        if stage not in outcomes:
            continue
        stages[stage] = {
            "outcomes": dict(outcomes[stage]),
            "duration": describe(durations[stage]),
        }
    return {
        "stages": stages,
        "queue_time": describe(queue),
        "approval_wait": describe(approval_wait),
    }


def deploy_attempts(runs: list[Json], jobs_by_run: dict[int, list[Json]]) -> list[Json]:
    """Return decided deploy jobs from push runs on main, oldest first."""
    attempts = [
        {
            "succeeded": job["conclusion"] == "success",
            "finished": job["completed_at"],
            "commit_time": run["commit_time"],
        }
        for run in runs
        if run["event"] == "push" and run["head_branch"] == DEFAULT_BRANCH
        for job in jobs_by_run.get(run["id"], [])
        if stage_of(job["name"]) == "deploy" and job["conclusion"] in DECIDED
    ]
    return sorted(attempts, key=lambda attempt: attempt["finished"])


def dora_metrics(attempts: list[Json], days: int) -> Json:
    """Compute deployment frequency, lead time, change-failure rate and MTTR."""
    successes = [attempt for attempt in attempts if attempt["succeeded"]]
    lead_times = [
        lead
        for attempt in successes
        if (lead := seconds_between(attempt["commit_time"], attempt["finished"]))
        is not None
    ]
    restores: list[float] = []
    broken_since: str | None = None
    for attempt in attempts:
        if not attempt["succeeded"] and broken_since is None:
            broken_since = attempt["finished"]
        elif attempt["succeeded"] and broken_since is not None:
            restored = seconds_between(broken_since, attempt["finished"])
            if restored is not None:
                restores.append(restored)
            broken_since = None
    return {
        "deploy_attempts": len(attempts),
        "deployments": len(successes),
        "deployment_frequency_per_day": round(len(successes) / days, 3),
        "lead_time": describe(lead_times),
        "change_failure_rate": (
            round((len(attempts) - len(successes)) / len(attempts), 3)
            if attempts
            else None
        ),
        "time_to_restore": describe(restores),
        "unresolved_failures": 0 if broken_since is None else 1,
    }


def token_count(tokens: Any) -> int:
    """Read a token count written as a number or as a usage object."""
    if isinstance(tokens, bool):
        return 0
    if isinstance(tokens, int | float):
        return int(tokens)
    if isinstance(tokens, dict):
        if isinstance(tokens.get("total_tokens"), int | float):
            return int(tokens["total_tokens"])
        return sum(int(v) for v in tokens.values() if isinstance(v, int | float))
    return 0


def ai_metrics(records: list[Json], completed_runs: int) -> Json:
    """Sum tokens, latency and run count per AI job from ai-*.json records."""
    per_job: dict[str, Json] = {}
    for record in records:
        job = per_job.setdefault(
            record["job"],
            {
                "runs": 0,
                "tokens": 0,
                "runs_reporting_tokens": 0,
                "latency_ms_total": 0.0,
                "statuses": Counter(),
            },
        )
        job["runs"] += 1
        # actions/ai-inference doesn't report usage, so tokens is often null.
        # Count how many runs reported it so 0 isn't misread as "free".
        if record["data"].get("tokens") is not None:
            job["runs_reporting_tokens"] += 1
            job["tokens"] += token_count(record["data"]["tokens"])
        if isinstance(status := record["data"].get("status"), str):
            job["statuses"][status] += 1
        latency = record["data"].get("latency_ms")
        if isinstance(latency, int | float) and not isinstance(latency, bool):
            job["latency_ms_total"] += latency
    for job in per_job.values():
        job["latency_ms_avg"] = round(job["latency_ms_total"] / job["runs"], 1)
        job["latency_ms_total"] = round(job["latency_ms_total"], 1)
        job["statuses"] = dict(job["statuses"])
    total = sum(job["tokens"] for job in per_job.values())
    return {
        "jobs": per_job,
        "total_tokens": total,
        "tokens_per_pipeline_run": (
            round(total / completed_runs, 1) if completed_runs else None
        ),
    }


def flaky_metrics(records: list[Json]) -> Json:
    """Count flaky tests reported in flaky*.json records (issue B4)."""
    tests = 0
    runs_with_flaky: set[int] = set()
    for record in records:
        data = record["data"]
        found = data.get("tests", []) if isinstance(data, dict) else data
        count = len(found) if isinstance(found, list) else 0
        tests += count
        if count:
            runs_with_flaky.add(record["run_id"])
    return {"tests": tests, "runs_with_flaky": len(runs_with_flaky)}


def compute(
    runs: list[Json],
    jobs_by_run: dict[int, list[Json]],
    artifact_records: list[Json],
    days: int,
    now: datetime,
) -> Json:
    """Build the full metrics document from already-fetched API data."""
    summary = run_metrics(runs)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "workflow": WORKFLOW,
        "window": {
            "days": days,
            "since": (now - timedelta(days=days)).date().isoformat(),
            "until": now.date().isoformat(),
        },
        "runs": summary,
        **stage_metrics(jobs_by_run),
        "flaky": flaky_metrics(
            [r for r in artifact_records if r["name"].startswith("flaky")]
        ),
        "dora": dora_metrics(deploy_attempts(runs, jobs_by_run), days),
        "ai": ai_metrics(
            [r for r in artifact_records if r["name"].startswith("ai-")],
            summary["completed"],
        ),
    }


def gh_json_lines(path: str, jq: str) -> list[Json]:
    """Call `gh api --paginate` and parse one JSON value per output line."""
    result = subprocess.run(
        ["gh", "api", "--paginate", path, "--jq", jq],
        check=True,
        capture_output=True,
        text=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line]


def fetch(repo: str, days: int, now: datetime) -> tuple[list[Json], dict, list[Json]]:
    """Fetch runs, their jobs and the ai-*/flaky* artifacts in the window."""
    since = (now - timedelta(days=days)).date().isoformat()
    created = urllib.parse.quote(f">={since}")
    runs = gh_json_lines(
        f"repos/{repo}/actions/workflows/{WORKFLOW}/runs"
        f"?per_page=100&created={created}",
        ".workflow_runs[] | {id, event, status, conclusion, run_attempt,"
        " head_branch, created_at, commit_time: .head_commit.timestamp}",
    )
    jobs_by_run = {
        run["id"]: gh_json_lines(
            f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100",
            ".jobs[] | {name, status, conclusion, created_at, started_at,"
            " completed_at}",
        )
        for run in runs
    }
    run_ids = set(jobs_by_run)
    artifacts = gh_json_lines(
        f"repos/{repo}/actions/artifacts?per_page=100",
        '.artifacts[] | select(.expired | not) | select(.name | test("^(ai-|flaky)"))'
        " | {id, name, run_id: .workflow_run.id}",
    )
    records = []
    for artifact in artifacts:
        if artifact["run_id"] not in run_ids:
            continue
        archive = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/artifacts/{artifact['id']}/zip"],
            check=True,
            capture_output=True,
        ).stdout
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            for member in bundle.namelist():
                if not member.endswith(".json"):
                    continue
                stem = Path(member).stem
                records.append(
                    {
                        "name": artifact["name"],
                        "run_id": artifact["run_id"],
                        "job": stem.removeprefix("ai-"),
                        "data": json.loads(bundle.read(member)),
                    }
                )
    return runs, jobs_by_run, records


def fmt_seconds(value: float | None) -> str:
    """Format seconds for the summary table."""
    if value is None:
        return "–"
    if value >= 3600:
        return f"{value / 3600:.1f} h"
    if value >= 60:
        return f"{value / 60:.1f} min"
    return f"{value:.0f} s"


def fmt_rate(value: float | None) -> str:
    """Format a rate between 0 and 1 as a percentage for the summary table."""
    return "–" if value is None else f"{value:.0%}"


def render_summary(metrics: Json) -> str:
    """Render the metrics as a markdown job summary."""
    window, runs, dora, ai = (
        metrics["window"],
        metrics["runs"],
        metrics["dora"],
        metrics["ai"],
    )
    lines = [
        f"## Team pipeline metrics, {window['since']} to {window['until']}",
        "",
    ]
    if not runs["total"]:
        lines += ["No `team-pipeline` runs in this window, so every metric is empty."]
        return "\n".join(lines) + "\n"
    lines += [
        "| Metric | Value |",
        "|---|---|",
        f"| Runs (completed / total) | {runs['completed']} / {runs['total']} |",
        f"| Success rate, push + PR | {fmt_rate(runs['success_rate'])} |",
        f"| Reruns | {runs['reruns']['runs_rerun']} runs,"
        f" {runs['reruns']['extra_attempts']} extra attempts |",
        f"| Queue time p50 / p95 | {fmt_seconds(metrics['queue_time']['p50_s'])}"
        f" / {fmt_seconds(metrics['queue_time']['p95_s'])} |",
        f"| Staging approval wait p50 | {fmt_seconds(metrics['approval_wait']['p50_s'])} |",
        f"| Flaky tests | {metrics['flaky']['tests']} |",
        "",
        "### Stages",
        "",
        "| Stage | Success | Failure | Skipped | p50 | p95 |",
        "|---|---|---|---|---|---|",
    ]
    for stage, data in metrics["stages"].items():
        outcomes, duration = data["outcomes"], data["duration"]
        lines.append(
            f"| {stage} | {outcomes.get('success', 0)} | {outcomes.get('failure', 0)}"
            f" | {outcomes.get('skipped', 0)} | {fmt_seconds(duration['p50_s'])}"
            f" | {fmt_seconds(duration['p95_s'])} |"
        )
    lines += [
        "",
        "### DORA (deploys from pushes to main)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Deployments | {dora['deployments']}"
        f" ({dora['deployment_frequency_per_day']} per day) |",
        f"| Lead time p50 | {fmt_seconds(dora['lead_time']['p50_s'])} |",
        f"| Change-failure rate | {fmt_rate(dora['change_failure_rate'])} |",
        f"| Mean time to restore | {fmt_seconds(dora['time_to_restore']['mean_s'])} |",
        "",
        "### AI jobs",
        "",
    ]
    if ai["jobs"]:
        lines += [
            "| Job | Runs | Output status | Tokens (runs reporting) | Avg latency |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {name} | {job['runs']}"
            f" | {', '.join(f'{k}: {v}' for k, v in job['statuses'].items()) or '–'}"
            f" | {job['tokens']} ({job['runs_reporting_tokens']})"
            f" | {job['latency_ms_avg']} ms |"
            for name, job in ai["jobs"].items()
        ]
        lines.append(f"\nTokens per pipeline run: {ai['tokens_per_pipeline_run']}")
    else:
        lines.append("No `ai-*.json` artifacts in this window.")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Fetch, compute and write the metrics."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--output", type=Path, default=Path("metrics.json"))
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if not 1 <= args.days <= 400:
        parser.error("--days must be between 1 and 400")
    if not args.repo:
        parser.error("--repo is required when GITHUB_REPOSITORY is not set")

    now = datetime.now(UTC)
    metrics = compute(*fetch(args.repo, args.days, now), days=args.days, now=now)
    args.output.write_text(json.dumps(metrics, indent=2) + "\n")
    if args.summary:
        with args.summary.open("a") as summary:
            summary.write(render_summary(metrics))


if __name__ == "__main__":
    main()
