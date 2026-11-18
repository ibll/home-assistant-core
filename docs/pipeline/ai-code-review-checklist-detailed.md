# Checklist details: reviewing and validating AI-generated code

The longer companion to the [short checklist](ai-code-review-checklist.md).
It covers the same checks, split into finer items. Each item comes from a
mistake we actually made, linked under it, so the reason for the check is
visible. Use it when a PR is large, touches security, or adds AI inside the
pipeline.

## A. Ownership

- [ ] **I read every line the AI produced and can explain it without the
      AI.** _Checklist Q16; the issues' definition of done._
- [ ] **The AI log is complete:** `docs/pipeline/ai-log/<issue>.md` has the
      exact prompt, the raw output, what I changed and why,
      accepted/edited/rejected, new dependencies and the time, with no
      `<placeholders>` left. _Five of seven merged logs still have blanks._
- [ ] **"Author" in the log is a person.** _The B1–B5 logs listed "GitHub
      Copilot"._
- [ ] **The commit has an `AI-Assisted: <tool>` trailer, and the PR's AI Usage
      section is filled in.** _PR #40 left it blank._

## B. Correct for this project

- [ ] **Versions match what the project pins.** Python ≥ 3.14.2 through
      `./.github/actions/setup-uv-python`. Linters at the versions in
      `.pre-commit-config.yaml`. _Copilot chose Python 3.12; we linted with
      zizmor 1.16.3 instead of 1.30.1._
- [ ] **Everything the code refers to exists:** runners, actions and their
      inputs, CLI commands and flags, packages, file paths, URLs and API
      endpoints. _A `self-hosted` runner that didn't exist queued for 24 h;
      `gh run view --log-failed` refuses mid-run._
- [ ] **It was tested on every trigger it runs on** (`pull_request`, `push`,
      `workflow_dispatch`). _Gitleaks worked on PRs and failed on every manual
      run ([ADR 0001](adr/0001-gitleaks-scan-range.md))._
- [ ] **Every `else` branch, default and fallback was read:** what happens
      when an input is empty? _The `--all` fallback scanned 1,240 findings._
- [ ] **It follows the conventions already merged** (for example the `./` plus
      `zizmor: ignore[self-repository]` form). _C2 used `$/` while C1 used
      `./`._

## C. GitHub Actions specifics

- [ ] **Each action is pinned to a full commit SHA, with a version comment,**
      and new pins are added to the README's pin table.
- [ ] **The top-level `permissions: {}` is kept,** and each job grants the
      least it needs, with a comment saying why. _The AI-suggested commit
      `7574e94` added `actions: read` that nobody justified._
- [ ] **No `${{ … }}` inside `run:`;** values go through `env:`. (This blocks
      script injection.)
- [ ] **The concurrency group can't cancel unrelated runs:** it includes the
      stage, the event and the ref. _Manual runs and push runs cancelled each
      other three times._
- [ ] **Checkouts use `persist-credentials: false`.**
- [ ] **Output from zizmor `--pedantic` (pinned version), actionlint,
      yamllint and prettier is pasted in the PR.**

## D. Security and dependencies

- [ ] **Every new dependency or action is in the AI log** with its version,
      license, and pip-audit or CVE result, and it exists on PyPI or GitHub.
      (AI tools sometimes invent package names.)
- [ ] **No secrets, tokens or credentials are in the change,** and Gitleaks
      passes.
- [ ] **Every suppression has a written reason, and the reviewer agrees:**
      `# zizmor: ignore`, `noqa`, allow-lists, ignored vulnerabilities.
      _Codex's zizmor suppression turned out to be justified, but only after
      a review._

## E. Tests and evidence

- [ ] **The checks that ran actually exercise the change.** A stub stage
      passing is not a test. _PR #40 changed Foscam code and merged green,
      but the test stage is still a stub._
- [ ] **For application code:** tests were added and run
      (`pytest tests/components/<domain>`), failure paths included.
- [ ] **The PR links a green run,** plus a failing run where the stage
      supports one (`inject_failure`, or a real planted failure).
      _See [failure-injection.md](failure-injection.md)._
- [ ] **Every artifact the issue names is on the run.**

## F. Reviewer and merge

- [ ] **At least one person other than the author approved.** _PR #40 merged
      with no review._
- [ ] **After the merge, `main` really contains the code:** run
      `git show --stat <merge commit>` or check the file. _C2's code was
      dropped in a merge; A1's log merged without its code._
- [ ] **The issue is closed with links to its evidence,** and any incident
      has an [ADR](adr/README.md).

## G. Only if the change adds AI *inside* the pipeline

- [ ] **It's advisory only and never a required check.** It has `models: read`
      and nothing more, and it sets `max-tokens`.
- [ ] **The prompt says the input is untrusted data.** Logs, diffs and PR text
      can contain instructions, so a test input with "ignore previous
      instructions" shouldn't change the output.
- [ ] **The output is parsed and allow-listed before use, and the job still
      passes when the output is invalid.** _Upstream's AI checker failed
      27/27 because the model answered "OK" instead of JSON._
- [ ] **It uploads `ai-<job>.json`** with the model, a prompt hash, tokens,
      latency and the output, for the metrics in L3.
