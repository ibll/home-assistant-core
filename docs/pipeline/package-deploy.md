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
   - `push: false`. D2 adds the push to GHCR and signing.
   - `load: true`, so the image is in the runner's Docker and can be measured.
   - `cache-from/to: type=gha` with `mode=max` and a fixed scope, so later
     runs reuse unchanged layers.
4. Writes the build time, image size, outcome and free disk to the job
   summary. That step runs even when the build fails, so a failed spike still
   records how far it got.

The Dockerfile in use is set once, in the workflow's `env.DOCKERFILE`.

### Spike results

| Run | Dockerfile | Cache | Outcome | Build time | Image size (uncompressed) | Free disk after |
|---|---|---|---|---|---|---|
| [#29](<link to run #29>) | `Dockerfile` | cold | success | 4m 19s (259 s) | 2.1 GB (2,190,163,159 bytes) | 100 GB |
| [#39](<link to run #39>) | `Dockerfile` | <cache % from the run> | success | <from run #39> | <from run #39> | <from run #39> |

Both runs used base image `ghcr.io/home-assistant/amd64-homeassistant-base:2026.07.0`.
In run #39 the whole package job took 3m 19s.

Failures seen: none in the build. BuildKit prints one warning,
`InvalidDefaultArgInFrom` for `Dockerfile` line 6: `ARG BUILD_FROM` has no
default value. It comes from upstream's `Dockerfile` (which our rules don't let
us edit) and is harmless, because this workflow always passes `BUILD_FROM`.

### Decision

**Use the full upstream `Dockerfile`; no `Dockerfile.ci`.** The issue's rule
was to write `Dockerfile.ci` only if the full build failed or took more than
40 minutes. It succeeded in 4m 19s from a cold cache, about a tenth of that
limit, and the 2.1 GB image left 100 GB of disk free on the runner. Keeping
the full image also means staging runs exactly what upstream ships, with every
integration's requirements, which `Dockerfile.ci` would have dropped.

With 100 GB free, the disk cleanup step turned out not to be needed on
today's runners. It stays as a cheap safeguard, since the image grows with
every integration added upstream.

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
