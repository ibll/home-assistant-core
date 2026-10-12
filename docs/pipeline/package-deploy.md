# Package, deploy and release (Member D)

This stage turns a commit on `main` into a container image, deploys it to the
`staging` environment and, on version tags, publishes a release. It runs in
`team-package.yml` and `team-deploy.yml`, and only on pushes to `main` and
manual runs. Pull requests stop after verification.

## Image build

Issue D1 (#23). Workflow: `.github/workflows/team-package.yml`, job `image`.

### What it does

1. Reads `BASE_IMAGE_VERSION` from `.github/workflows/builder.yml` with `yq`
   and fails if the value doesn't look like a version. Upstream bumps that
   value when it updates the base image, so syncing from upstream keeps our
   base in step without a second hard-coded version.
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

