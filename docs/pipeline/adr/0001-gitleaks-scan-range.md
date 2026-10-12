# 0001. Scope Gitleaks scans to the commits being built

- **Status:** Accepted. Merged in PR #35 (`b6cc471`).
- **Date:** 2026-10-11
- **Deciders:** EBOD13 (tech lead). C1 owner `odinsean` reviews.
- **Related:** issue #18 (C1), issue #5 (L2), PR #31 (Gitleaks), PR #35 (fix),
  run [38165813211](https://github.com/ibll/home-assistant-core/actions/runs/38165813211)

## Context

C1 (PR #31, merged Oct 11) added Gitleaks to the security stage. It chose
which commits to scan like this:

| Event | Range scanned |
|---|---|
| Pull request | `base..head` |
| Push | `before..after` |
| Anything else | `--all` (the full history) |

The `--all` fallback was meant for a branch's very first push. But manual runs
(`workflow_dispatch`) have neither a pull-request base nor a `before` commit,
so they fell into it too. That includes every `inject_failure` run from L2.

### What happened on Oct 11

| Time (UTC) | Event |
|---|---|
| 18:39 | PR #31 merged. Push runs kept passing, because they have a range. |
| 18:55 | Manual run [38165813211](https://github.com/ibll/home-assistant-core/actions/runs/38165813211) scanned the full history of Home Assistant, inherited from upstream: **1,240 findings**. Security failed, so package and deploy were skipped. |
| 18:57, 19:02 | Two full-history SARIF reports uploaded to code scanning: **1,240 open alerts** on `main`. |

### Impact

- **Every manual run failed** in the security stage, whatever the commit.
- **L2 was blocked.** An `inject_failure` run failed in security before
  reaching its own target, so the `smoke` mode could never reach deploy.
- **The Security tab filled with 1,240 alerts.** Nearly all are fake tokens
  in upstream test fixtures, which buries any real finding.
- **Pull-request and push runs were not affected.**

### Root cause

The fallback assumed only a first push has no commit range. The C1 tests
covered a pull request with a planted secret and a clean pull request, but
not a manual run.

## Options considered

| Option | Result | Verdict |
|---|---|---|
| Keep `--all`, with an ignore list (`.gitleaksignore`) for the 1,240 historical findings | A 1,240-entry file to maintain. Every manual run re-scans all history. New real findings hide among fixtures. | Rejected |
| Skip Gitleaks on manual runs | Manual runs can package and deploy, so a deployable commit would go unscanned | Rejected |
| Scan the current files instead of commits (`gitleaks dir .`) | Tested locally: **787 findings** (557 in `tests/`, 230 in `homeassistant/`), the same fixture problem | Rejected |
| **Scan `<sha>~1..<sha>`: everything the commit being built added** | Same cost as a push scan. For a merge commit, it covers every commit of the merged branch. | **Chosen** |

## Decision

Manual runs, and any other run without a pull-request or push range, scan
`${PUSH_AFTER}~1..${PUSH_AFTER}` instead of `--all`. The pipeline never scans
the full history. We only answer for commits made on this fork; history
inherited from upstream is upstream's responsibility.

The change is one line in `.github/workflows/team-security.yml`, plus a
comment saying why.

## Verification

Gitleaks 8.30.1 (the pipeline's version, checksum-verified) was run locally
with the new range:

| Commit | What it is | Result |
|---|---|---|
| `f9dbefd` | PR #34 merge, current `main` | no leaks |
| `22bd800` | PR #31 merge (C1) | no leaks |
| `15e21a6` | PR #33 merge (C2) | no leaks |
| `c2a000a` | PR #32's planted test secret | **1 leak**, still caught |

zizmor 1.30.1 `--pedantic`, yamllint and actionlint pass.

After the merge, the push run for `b6cc471`
([38166786122](https://github.com/ibll/home-assistant-core/actions/runs/38166786122))
uploaded a Gitleaks analysis with **0 results** for `main` at 19:10 UTC. The
1,240 open alerts dropped to **0**.

## Consequences

**Good:**

- Manual runs scan in seconds, and pass or fail on what they actually change.
- L2's injection runs fail only in the stage they target.
- The 1,240 alerts close on their own after the next clean scan of `main`.
  Code scanning marks an alert fixed when the latest analysis for its
  category no longer reports it.

**Accepted trade-offs:**

- **Older fork commits aren't rescanned.** A manual run on a branch scans
  only its newest commit. That's acceptable because a branch's earlier
  commits are scanned by its pull request before they can merge.
- **Upstream history is never scanned by us.**

## Follow-ups

- [x] After the fix merges, confirm the Gitleaks alerts on `main` are closed:
      0 open at 19:10 UTC on Oct 11.
- [x] Run `inject_failure=smoke` and add it to
      [failure-injection.md](../failure-injection.md) (L2): attempt 2 of
      38164426398 failed at the smoke step as expected.
- [ ] When a check picks its input by event, test it on every event the
      pipeline runs on: `pull_request`, `push` and `workflow_dispatch`.
      Consider adding this to the issues' definition of done.

## Records

- AI log: [ai-log/C1.md](../ai-log/C1.md), Interaction 2
- Docs: [security.md](../security.md), Secrets section
