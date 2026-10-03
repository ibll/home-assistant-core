# Team pipeline

This folder documents the CI/CD pipeline our team is building on top of this
Home Assistant Core fork, and how we use AI while building and running it.

- [PLAN.md](PLAN.md): the full plan, with findings about the existing pipeline and every issue.
- [checklist.md](checklist.md): the evaluation checklist the tech lead scores us with.
- [issues/](issues/): one file per issue, used to create the GitHub issues.
- [ai-log/](ai-log/): one entry per issue on how AI was used. Start from [ai-log/TEMPLATE.md](ai-log/TEMPLATE.md).

## Why a separate pipeline

The fork already contains upstream's CI (`.github/workflows/ci.yaml` and
friends). Most of the upstream workflows skip on this fork because they check
`github.repository_owner == 'home-assistant'`. Editing them would cause merge
conflicts every time we sync from upstream.

So everything we build lives in new `team-*` files, and **we never edit the
upstream workflows**.

## How it fits together

```
team-pipeline.yml  (pull request, push to dev, manual run)
 ├─ changes      team-changes.yml      Member A
 ├─ build        team-build.yml        Member A
 ├─ test         team-test.yml         Member B
 ├─ security     team-security.yml     Member C
 ├─ ai-advisory  team-ai-advisory.yml  one AI job from each member
 └─ package      team-package.yml      Member D   (push to dev and manual runs only)
     └─ deploy   team-deploy.yml       Member D   (needs approval in the `staging` environment)
```

`team-pipeline.yml` (owned by the tech lead) only wires the stages together.
Each stage is a reusable workflow (`on: workflow_call`) that its owner fills
in. Right now every stage is a stub that passes, so each of you can replace
your stub without touching anyone else's file.

## Deterministic automation vs AI automation

| Job | Kind | Can it block a merge? |
|---|---|---|
| changes, build, test, security, package, deploy | Deterministic | Yes |
| ai-advisory (failure triage, test gaps, dependency risk, release notes) | AI (GitHub Models) | **No, never** |

AI output is advice that a human reads. It must never decide whether code
merges or deploys.

## Rules for every change

1. **Only add `team-*` files.** Never edit `ci.yaml`, `builder.yml` or any
   other upstream workflow.
2. **Python 3.14 through uv.** Use the existing
   `./.github/actions/setup-uv-python` action. Get the uv version the same
   way `ci.yaml` does: `grep '^uv==' requirements.txt | cut -d'=' -f3`.
   Do not use `actions/setup-python` with 3.12 or 3.13. That is why our first
   attempt failed: the project requires Python `>=3.14.2`.
3. **Pin every action to a full commit SHA** with a version comment. Reuse a
   pin from the table below whenever the action is listed there.
4. **Least privilege.** Keep the top-level `permissions: {}`. Grant
   permissions per job, with a comment on each line saying why
   (`contents: read # To check out the repository`). Always check out with
   `persist-credentials: false`.
5. **Never put `${{ ... }}` inside a `run:` script.** Pass values through
   `env:` and use `"$VAR"` in the script. This blocks script injection from
   PR titles, branch names and the like.
6. **Fast by default.** Test only the integrations a change touched, plus the
   contract suite. The full test suite is upstream CI's job.
7. **AI jobs:**
   - Permissions are `contents: read` and `models: read` only.
   - Untrusted text (logs, diffs, PR text) goes in as data, never as instructions.
   - Parse and validate the model's answer before using it (see how
     `detect-duplicate-issues.yml` keeps only issue numbers from its candidate list).
   - Set `max-tokens` on every call.
   - Upload an `ai-<job>.json` artifact with `{model, prompt_hash, tokens, latency_ms, output}`.
8. **Every issue ships three things:** the code, its artifact(s), and docs.
   The docs are a section in `docs/pipeline/<stage>.md` plus an entry in
   `docs/pipeline/ai-log/`.

### Pinned actions already used upstream

| Action | Pin |
|---|---|
| actions/checkout | `3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1` |
| actions/upload-artifact | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1` |
| actions/download-artifact | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1` |
| actions/cache | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0` |
| actions/github-script | `3a2844b7e9c422d3c10d287c895573f7108da1b3 # v9.0.0` |
| actions/ai-inference | `a7805884c80886efc241e94a5351df715968a0ad # v2.1.1` |
| actions/dependency-review-action | `a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0` |
| actions/attest | `1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2` |
| dorny/paths-filter | `ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3` |
| docker/setup-buildx-action | `f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1` |
| docker/login-action | `dbcb813823bdd20940b903addbd779551569679f # v4.6.0` |
| docker/metadata-action | `dc802804100637a589fabce1cb79ff13a1411302 # v6.2.0` |
| docker/build-push-action | `c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0` |
| sigstore/cosign-installer | `6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2` |

For an action that is not listed, look up the commit SHA of its latest
release tag and add the pin to this table in your PR.

## Adding a stage

1. Copy a stub such as `team-security.yml` to `team-<stage>.yml`. Keep
   `on: workflow_call`, `permissions: {}` and the `concurrency` block, and
   change the stage name in the group.
2. Add one job to `team-pipeline.yml` that `uses:` it. Give that job only the
   permissions the stage needs.
3. If the stage should support failure injection, add the stage name to the
   `inject_failure` options and call `./.github/actions/team-inject-failure`.
4. Document it in `docs/pipeline/<stage>.md`.

## Proving the pipeline fails correctly

Run the pipeline by hand with one stage forced to fail:

```bash
gh workflow run team-pipeline.yml --ref <branch> -f inject_failure=test
gh run watch
```

The chosen stage must fail, every stage after it must be skipped, and nothing
may be deployed. Options are `none`, `lint`, `test`, `security` and `smoke`.

## Checking your workflow locally

```bash
uv run --no-sync prek run --files .github/workflows/team-*.yml   # zizmor, yamllint, prettier
actionlint .github/workflows/team-*.yml
```

`prek` needs the dev environment from `script/setup`. If you don't have it,
`pip install yamllint zizmor actionlint-py` works too. Run zizmor with
`--pedantic`, as upstream does.
