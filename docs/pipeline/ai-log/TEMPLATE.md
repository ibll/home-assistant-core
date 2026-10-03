# AI log: <issue id> <issue title>

Copy this file to `docs/pipeline/ai-log/<issue id>.md` (for example `A1.md`)
and fill it in as you work, not afterwards. Add one "Interaction" section for
each meaningful prompt. Small follow-ups can share a section.

- **Author:** <GitHub handle>
- **Issue:** #<number>
- **PR:** #<number>
- **AI tools used:** <for example Claude Code (Opus 5.5), GitHub Copilot Chat (GPT-5.5), ChatGPT>

## Interaction 1: <what you asked for, in a few words>

**Tool / model:** <tool and exact model>

**Prompt** (paste it exactly):

```text
<prompt>
</prompt>
```

**What the AI produced** (paste it, or link to a commit or gist if it is long):

```text
<output>
```

**What I changed and why:**

- <for example "It used actions/setup-python with 3.12. This project needs 3.14, so I switched to ./.github/actions/setup-uv-python">
- <for example "It granted `contents: write`. Nothing writes, so I reduced it to `read`">

**Accepted as-is / edited / rejected:** <pick one>

## New dependencies or actions the AI introduced

| Name | Version / SHA | Why it is needed | Checked how (pip-audit, license, maintainer, SHA lookup) |
|---|---|---|---|
| | | | |

Write "None" if there were none. This table feeds checklist Q11.

## Could I explain this without the AI?

Two or three sentences, in your own words, on how the change works. This is
what you will present for checklist Q16.

## Time

- **Estimated time without AI:** <hours>
- **Actual time with AI, including review and fixes:** <hours>
