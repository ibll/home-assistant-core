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
   - `push: false`. D2 adds the push to GHCR and signing.
   - `load: true`, so the image is in the runner's Docker and can be measured.
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
