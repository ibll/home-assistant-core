# CI/CD Pipeline Documentation

We've forked and the repository and asked GitHub Copilot:

> **Asked GitHub Copilot, do these 3 things and ignore the current CI/CD
> pipeline being used:**
>
> -   Generate the pipeline configuration.
> -   Explain the configuration.
> -   Modify the workflow when your system requires something different.

It created 7 files:

-   `github-actions.base.yml`
-   `github-actions.custom.yml`
-   `.gitlab-ci.base.yml`
-   `.gitlab-ci.custom.yml`
-   `azure-pipelines.base.yml`
-   `azure-pipelines.custom.yml`
-   `README.md`

## GitHub Actions

-   **Base workflow:** hosted Linux, Python matrix, pip cache, lint +
    unit tests
-   **Modified workflow:** self-hosted runners, split lint/integration
    jobs, Docker Compose integration tests and cleanup

## GitLab CI

-   **Base workflow:** lint + test stages with Python image and pip
    cache
-   **Modified workflow:** runner tags, PostgreSQL service for test
    dependencies, package stage with dist artifact output

## Azure Pipelines

-   **Base workflow:** hosted Ubuntu, Python matrix, lint + tests
-   **Modified workflow:** self-hosted pool, staged jobs for lint/tests
    and publish, publish stage gated to main branch only

------------------------------------------------------------------------

## Initial Approach

We tried getting the AI tools to generate a basic CI/CD setup from
scratch. Even after a few attempts, it wasn't able to pass all of its
tests.

This makes sense because Home Assistant is a massive project, and the
upstream repository has a significantly large pipeline with many steps
and individual things being tested. We didn't provide much formal
guidance on what needed to be tested, so the generated tests were not
sufficient to test the entire repository.

While Copilot struggled to run the testing setup it generated from
scratch, it was able to make some suggestions to build on top of the
existing one. Because the existing actions themselves already
functioned, most of these changes were concerned with the implementation
of the pipeline itself.

This included specific workflows being tied to the main branch of an
external repository, meaning changes on external repositories could
suddenly cause failures or problems with no warning. The actions setup
also had indefinite timeouts on some steps that could potentially fail
and cost a lot of runner hours.

------------------------------------------------------------------------

## Run 2

The first generated workflow failed during testing. We gave GitHub
Copilot the following error information:

``` text
test (3.12), Process completed with exit code 1
Node.js 20 is deprecated
The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026
test (3.13), Process completed with exit code
test, Node.js 20 is deprecated
The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026
```

### Copilot's Changes

Copilot responded that it changed only the files inside `ci-templates`.

The GitHub Actions base template was identified as the one needing an
update for the warnings shown in the run. Copilot changed:

`ci-templates/github-actions.base.yml`

The changes included:

-   Replacing `ubuntu-latest` with `ubuntu-24.04`
-   Updating `actions/checkout` to `actions/checkout@v7`
-   Updating `actions/setup-python` to `actions/setup-python@v7`
-   Updating `actions/cache` to `actions/cache@v6`
-   Updating the explanation in `ci-templates/README.md` to match the
    changes

Copilot reported that validation passed on both edited files.

------------------------------------------------------------------------

## Run 3

Run 2 failed with a Python dependency-resolution error. We gave GitHub
Copilot the following output:

``` text
Run python -m pip install --upgrade pip

Requirement already satisfied: pip in /opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages (26.2.1)

Collecting aiodns==4.0.4 (from -r requirements.txt (line 6))

Downloading aiodns-4.0.4-py3-none-any.whl.metadata (9.0 kB)

Cannot install aiogithubapi==26.0.0 because these package versions have conflicting dependencies.
The conflict is caused by:
The user requested aiogithubapi==26.0.0

The user requested (constraint) aiogithubapi==26.0.0

Additionally, some packages in these conflicts have no matching distributions available for your environment:

aiogithubapi

To fix this you could try to:

1. loosen the range of package versions you've specified
2. remove package versions to allow pip to attempt to solve the dependency conflict

ResolutionImpossible: for help visit:
https://pip.pypa.io/en/latest/topics/dependency-resolution/#dealing-with-dependency-conflicts

Error: Process completed with exit code 1.
```

### Copilot's Changes

Copilot changed the active GitHub workflow files rather than the
template copies:

-   `.github/workflows/github-actions.base.yml`
-   `.github/workflows/github-actions.custom.yml`

The installation process was changed so that it no longer relied on
`pip` to resolve the project requirements directly.

The new approach:

1.  Bootstraps `uv`.
2.  Creates a local virtual environment.
3.  Installs `requirements.txt` and `requirements_test.txt` using
    `uv pip install`.
4.  Runs `ruff` and `pytest` from that virtual environment.
5.  Moves the workflow to `ubuntu-24.04`.
6.  Updates the GitHub Action major versions to current versions.

Copilot reported that validation passed on both edited workflow files.

It also noted that the same fix could be mirrored into the
`ci-templates` copies so that the examples remain in sync.

------------------------------------------------------------------------

Rather than continuing to generate an entirely new CI/CD pipeline from
scratch, the approach shifted toward modifying and improving the
existing pipeline. This is more appropriate for a project such as Home
Assistant because the upstream CI/CD configuration already contains
substantial project-specific knowledge and testing infrastructure.

The AI tools were therefore more useful when analyzing and modifying the
existing workflow than when attempting to recreate a complete CI/CD
system without sufficient project-specific testing requirements.
