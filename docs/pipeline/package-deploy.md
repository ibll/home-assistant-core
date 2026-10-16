# Package, deploy and release (Member D)

This stage turns a commit on `main` into a container image, deploys it to the
`staging` environment and, on version tags, publishes a release. It runs in
`team-package.yml` and `team-deploy.yml`, and only on pushes to `main` and
manual runs. Pull requests stop after verification.

## Image build

Issue D1 (#23). Workflow: `.github/workflows/team-package.yml`, job `image`.

### What it does

1. Takes the base image version from `BASE_IMAGE_VERSION` in the workflow's
   `env` and fails if it doesn't look like a version. The issue asked to read
   it from upstream's `builder.yml`, and the first spike run did. The fork
   then removed the upstream workflows (commit `d6a5ca687a3`), so the version
   now lives in `team-package.yml`, with a comment saying where to copy it
   from when syncing with upstream.
2. Frees disk space by removing toolchains the job never uses (.NET, Android,
   GHC, CodeQL), and logs `df` before and after.
3. Builds the upstream `Dockerfile` for `linux/amd64` with
   `BUILD_FROM=ghcr.io/home-assistant/amd64-homeassistant-base:<version>`,
   using `docker/setup-buildx-action` and `docker/build-push-action`.
   - In D1 this was `push: false` with `load: true`, so the image could be
     measured on the runner. D2 replaced both with `push: true`; the size is
     now read from the registry instead (see "Registry and signing").
   - `cache-from/to: type=gha` with `mode=max` and a fixed scope, so later
     runs reuse unchanged layers.
4. Writes the build time, image size, outcome and free disk to the job
   summary. That step runs even when the build fails, so a failed spike still
   records how far it got.

The Dockerfile in use is set once, in the workflow's `env.DOCKERFILE`.

### Spike results

| Run | Dockerfile | Cache | Outcome | Build time | Image size | Free disk after |
|---|---|---|---|---|---|---|
| <run link> | `Dockerfile` | cold | <success / failure> | <m s> | <size> | <GB> |
| <run link> | `Dockerfile` | warm | <success / failure> | <m s> | <size> | <GB> |

Free disk before the build, from the "Free disk space" step log:
<before cleanup> → <after cleanup>.

Failures seen: <none, or the error and the step it came from>.

### Decision

<Full image or `Dockerfile.ci`, and why, citing the numbers above. The rule
from the issue: use `Dockerfile.ci` if the full build fails or takes more
than 40 minutes.>

### Known gaps

- **Translations are not downloaded.** Upstream's `builder.yml` downloads
  them from Lokalise with a secret we don't have. The UI still loads, and
  `/manifest.json` and the onboarding API don't depend on them, so D4's smoke
  test is unaffected. Integration UI text may show raw keys.
- **amd64 only.** Upstream also builds aarch64. One architecture is enough
  for a staging deployment.
- **No base image signature check.** Upstream verifies the base image with
  cosign (`cosign-base-verify`). That fits naturally into D2, which installs
  cosign anyway.

## Registry and signing

Issue D2 (#24). Same job as the image build, now named "Build, push and sign
container image".

### What it does

1. Logs in to `ghcr.io` with the job's `GITHUB_TOKEN`.
2. `docker/metadata-action` computes the tags:
   - `ghcr.io/ibll/home-assistant-core:<full commit sha>` on every run.
   - `:<branch name>`, which is `:main` on pushes to `main`. A manual run on
     a feature branch gets that branch's name instead, so it never moves
     `:main`.
   It also adds the standard OCI labels, including
   `org.opencontainers.image.source`, which links the package to this repo.
3. Builds and pushes in one step (`push: true`).
4. Takes the digest that `build-push-action` returns, checks it looks like
   `sha256:<64 hex>`, and outputs `image` as
   `ghcr.io/ibll/home-assistant-core@sha256:<digest>`. Everything after this
   point (signing, D3's scan, D4's deploy) uses the digest, because a tag can
   be moved to a different image and a digest cannot.
5. Installs `cosign` and signs the digest keylessly: GitHub's OIDC provider
   issues a short-lived certificate naming this workflow, and the signature
   is recorded in the public Sigstore transparency log. There is no private
   key to store or leak.
6. Verifies the signature it just made, and fails the job if verification
   fails.

### Permissions

Only the `image` job in `team-package.yml`, and the `package` job that calls
it in `team-pipeline.yml`, get the two extra permissions. A called workflow
can't have more permissions than its caller grants, so both places need them.

| Permission | Why |
|---|---|
| `contents: read` | Check out the repository |
| `packages: write` | Push the image to GHCR |
| `id-token: write` | Get the OIDC token cosign uses for keyless signing |

### Verifying an image yourself

Because the stage is a reusable workflow, the certificate's identity is
`team-package.yml`, not `team-pipeline.yml`:

```bash
cosign verify ghcr.io/ibll/home-assistant-core@sha256:<digest> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity https://github.com/ibll/home-assistant-core/.github/workflows/team-package.yml@refs/heads/main
```

The pipeline runs the same check with `--certificate-identity-regexp`, so
runs from feature branches verify too.

Output from a run on `main`:

```text
<paste the command and its output here>
```

### Evidence

- Run: <run link>
- Package: <link to the package under the repo's Packages>
- Image: `ghcr.io/ibll/home-assistant-core@sha256:<digest>`

### Notes

- **Package visibility.** GHCR makes a new package private. D4 pulls it in
  the same repository with the job's token, so that works either way. To
  let anyone `docker pull` or `cosign verify` it without logging in, make
  the package public under its Package settings.
- **Signed digest.** `build-push-action` attaches a provenance attestation
  by default, so the pushed digest is an image index that contains the
  amd64 image and the attestation. cosign signs that index.


## Image scan

Issue D3 (#25). Same job, after signing. Every package run scans the image it
just pushed, by digest.

### What it does

1. **Installs Trivy** from its GitHub release tarball, pinned to
   `TRIVY_VERSION` and checked against `TRIVY_SHA256` before it is unpacked.
   We don't use `aquasecurity/trivy-action`: its tags were hijacked in a
   supply-chain attack in March 2026, so a pinned binary with a checksum is
   the smaller trust surface.
2. **Generates the image SBOM** (`sbom-image.spdx.json`, SPDX JSON) with
   `trivy image --format spdx-json`.
3. **Scans for vulnerabilities** in both the OS packages (Alpine) and the
   Python packages in the image, and writes every HIGH and CRITICAL finding,
   fixed or not, to `trivy.sarif`.
4. **Uploads the SARIF to code scanning** under the category `trivy-image`,
   so results show in the Security tab next to Gitleaks.
5. **Uploads `trivy.sarif` and `sbom-image.spdx.json`** as the `image-scan`
   artifact. Steps 4 and 5 run even if a later step fails.
6. **Gates the job:** fails if any CRITICAL vulnerability **with an available
   fix** remains, except the reviewed exceptions in
   `.github/team-trivyignore.yaml`. A failure here stops the deploy stage.

The image is already in GHCR when the gate runs, because Trivy scans the
pushed digest. A failed gate means that digest is never deployed.

### First run: the gate caught three CRITICALs

The first D3 run (<run link>) failed the gate: Trivy found 3 CRITICAL
vulnerabilities with available fixes in the image's Alpine 3.24.1 packages:

| CVE | Package | Installed | Fixed in |
|---|---|---|---|
| <id> | <pkg> | <version> | <version> |

They came from the base image. `BASE_IMAGE_VERSION` was still `2026.07.0`,
the value in upstream's `builder.yml` when the fork deleted it, while
upstream had moved on to `2026.10.0`. Bumping the base image to match
upstream was the fix, rather than allowlisting the findings.

The second run (<run link>) had no Alpine findings left, but failed on two
more CRITICALs with fixes, both outside what this team may change:

| CVE | Where | Installed | Fixed in | Decision |
|---|---|---|---|---|
| CVE-2026-102268 | PyJWT (Python) | 2.13.0 | 2.14.0 | Allowlisted until 2026-11-12. Pinned by core; upstream is already on 2.15.1, so the next upstream sync fixes it. |
| CVE-2025-68121 | Go `stdlib` in `bin/go2rtc` | Go 1.25.6 | Go 1.25.7 | Allowlisted until 2026-11-30. go2rtc 1.9.14 is the newest release and upstream ships it too; no fix to take yet. |

Both entries are in `.github/team-trivyignore.yaml` with these reasons. The
third run (<run link>) passed the gate.

This is also why the version needs to be copied from upstream's
`builder.yml` on every upstream sync.

### Why "unfixed" CRITICALs don't fail the job

A CRITICAL with no fixed version can't be resolved by us; failing on it would
block every run until upstream ships a fix. Those still appear in the SARIF
and the Security tab. A CRITICAL that does have a fix is something we, or
upstream, can act on, so that one blocks.

### Allowlisting a finding

Add it to `.github/team-trivyignore.yaml` with:

- `id`: the CVE or GHSA ID,
- `statement`: why it's acceptable (not reachable, waiting on upstream, …),
- `expired_at`: a date after which the scan fails on it again.

The allowlist only affects the gate. The SARIF keeps every finding, so
allowlisted items stay visible.

### SBOM and C5

Issue D3 asks to generate the image SBOM with C5's reusable step. C5 hasn't
landed yet, so this stage uses Trivy, which it already has installed. When C5
merges, either switch this step to C5's step, or keep Trivy and make sure
both SBOMs use SPDX JSON so they can be compared.

### Results

| Run | Base image | HIGH/CRITICAL findings | Unfixed-CRITICAL gate | Allowlisted |
|---|---|---|---|---|
| <run link> | 2026.07.0 | <n> | fail (3 Alpine) | 0 |
| <run link> | 2026.10.0 | <n> | fail (PyJWT, go2rtc) | 0 |
| <run link> | 2026.10.0 | <n> | pass | 2 |

Security tab: <link to the code scanning results filtered by tool Trivy>

## Staging deploy

Issue D4 (#26). Workflow: `.github/workflows/team-deploy.yml`, job `staging`.
Home Assistant is self-hosted, so "deploying" means starting the signed image
in the gated `staging` environment and proving it serves requests.

### What it does

1. **Waits for approval.** The job uses `environment: staging`, so it doesn't
   start until the tech lead approves it. The environment also only allows
   deployments from `main`; a run from a feature branch fails here with
   "Branch … is not allowed to deploy to staging due to environment
   protection rules", before any step runs.
2. **Checks the image reference** from the package stage is a GHCR image
   pinned by digest, so it deploys exactly what was built, scanned and signed.
3. **Logs in to GHCR** with `packages: read` and pulls the image.
4. **Starts a fresh container** (`docker run -d -p 8123:8123`) with an empty
   `/config`, like a first install.
5. **Waits until healthy:** polls `GET /manifest.json` every 5 seconds for up
   to 3 minutes, and fails early if the container exits.
6. **Smoke test:**
   - `GET /manifest.json` returns 200, content type
     `application/manifest+json`, and JSON with a `name`. This proves the
     frontend is installed and being served.
   - `GET /api/onboarding` returns 200 and a JSON list. On a fresh instance
     this endpoint works without logging in, so it proves the core and its
     HTTP API are up.
7. **Failure injection** (`stage: smoke`) runs *after* the real smoke test,
   so `inject_failure=smoke` looks exactly like a failed smoke test to D5's
   rollback.
8. **Always** saves `docker logs` and both responses, and uploads them as
   `staging-logs-<sha>`, even when an earlier step fails.

### Permissions

| Permission | Why |
|---|---|
| `contents: read` | Check out the repository (for the inject-failure action) |
| `packages: read` | Pull the image from GHCR |

`team-pipeline.yml`'s `deploy` job grants `packages: read` too, since a
called workflow can't have more than its caller.

### Evidence

- Passing run, with the approval: <run link>
- `inject_failure=smoke` run, failing in this job: <run link>
- Logs artifact: `staging-logs-<sha>` on both runs
