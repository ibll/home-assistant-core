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

Output from the pipeline's own verify step, run [38855004458](https://github.com/ibll/home-assistant-core/actions/runs/38855004458) on
`d2-push-and-sign`. The certificate identity there ends in
`@refs/heads/d2-push-and-sign`, because the run came from that branch:

```text
<paste the "Verify signature" step output here>
```

### Evidence

From run [38855004458](https://github.com/ibll/home-assistant-core/actions/runs/38855004458) (commit `4f6d78e`):

| | |
|---|---|
| Image | `ghcr.io/ibll/home-assistant-core@sha256:0cf057d5e89c7b3500dac6a8c61c4a734d68f128e9ad25c47c05a96c5a9b165a` |
| Tags | `:4f6d78e99e2b451a2e445e385e9c8fee58a9e817`, `:d2-push-and-sign` |
| Size in GHCR (compressed) | 693 MB (725,828,695 bytes); 2.1 GB uncompressed (see "Image build") |
| Build and push time | 16 s, with 45% of the build cached from earlier runs |
| Signature verified | success |
| Package | [ghcr.io/ibll/home-assistant-core](https://github.com/ibll/home-assistant-core/pkgs/container/home-assistant-core) |

To verify this exact image yourself:

```bash
cosign verify ghcr.io/ibll/home-assistant-core@sha256:0cf057d5e89c7b3500dac6a8c61c4a734d68f128e9ad25c47c05a96c5a9b165a \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity https://github.com/ibll/home-assistant-core/.github/workflows/team-package.yml@refs/heads/d2-push-and-sign
```

### Notes

- **Package visibility.** GHCR makes a new package private. D4 pulls it in
  the same repository with the job's token, so that works either way. To
  let anyone `docker pull` or `cosign verify` it without logging in, make
  the package public under its Package settings.
- **Signed digest.** `build-push-action` attaches a provenance attestation
  by default, so the pushed digest is an image index that contains the
  amd64 image and the attestation. cosign signs that index.

