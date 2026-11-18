# Checklist to validate AI-generated code

Copy this list into every pull request that contains AI-written code. The
author answers it before asking for review, and the reviewer checks the
answers before approving. If an item doesn't apply, say why.

## Before the PR

- [ ] Does the change do what the issue's acceptance criteria ask, and nothing more?
- [ ] Did the AI work from the right files and follow the code that's already merged?
- [ ] Does everything the code uses actually exist (actions, runners, commands, flags, packages)?
- [ ] Does it use the versions the project pins (Python 3.14, the linter versions in `.pre-commit-config.yaml`)?
- [ ] Are all actions pinned to a commit SHA, with only the permissions each job needs?
- [ ] Are new dependencies checked for known vulnerabilities and licenses, and does the secret scan pass?
- [ ] Do zizmor, actionlint, yamllint and prettier pass on our versions?

## Testing

- [ ] Does the pipeline pass on every way it runs: pull request, push and manual run?
- [ ] Do the checks that ran actually test this change, rather than a stub that always passes?
- [ ] Does breaking it on purpose make the right stage fail (`inject_failure` or a planted error)?
- [ ] Were tests and checks left as they were, not weakened, skipped or silenced to get a pass?
- [ ] Is there anything that still has to be checked by hand, such as a staging deploy?

## Review and record

- [ ] Did someone other than the author read the code and approve it?
- [ ] Can the author explain every line without the AI?
- [ ] Is the AI log filled in: the prompt, what the AI produced, what we changed, and the time?
- [ ] After merging, is the code really on `main`, not just the docs?
- [ ] If something went wrong, did we record it (an ADR or the AI log) and use it to improve the next prompt?

## Why each item is here

Each item comes from a real problem on this project:

| Item | What happened |
|---|---|
| Things actually exist | Copilot's first pipeline used a `self-hosted` runner that didn't exist, so the job sat queued for 24 h. |
| Pinned versions | Copilot chose Python 3.12; we once linted with zizmor 1.16.3 while the project pins 1.30.1. |
| Every way it runs | Gitleaks passed on PRs but failed every manual run with 1,240 false findings ([ADR 0001](adr/0001-gitleaks-scan-range.md)). |
| Checks really test the change | PR #40 changed Foscam code and passed, but the test stage was still a stub. |
| Breaking it on purpose | [failure-injection.md](failure-injection.md) shows each stage failing when forced. |
| Someone else approved | PR #40 merged with no review. |
| AI log filled in | Five of the seven merged AI logs still had blanks on Nov 18. |
| Code really on `main` | C2's code was dropped while a merge conflict was resolved; A1's log merged without its code. |

For a large PR, a security change, or AI added *inside* the pipeline, also go
through the [detailed checklist](ai-code-review-checklist-detailed.md).
