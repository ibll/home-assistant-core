# Step 1 – AI response: stated intent and test plan (before any code)

**AI tool:** Claude (Opus 5.5) · **Prompt:** Kalyani's M4S4 D6 prompt, bracketed file paths filled in

## Stated intent
When a release is cut, a script collects the pull requests merged between the previous tag and the new tag,
groups them by label, and asks an AI model to draft release notes. The notes always start with an advisory
banner and are saved as a *draft* GitHub release so a maintainer edits and publishes them by hand. If the AI
call fails, a plain bulleted list of PR titles is used instead; if nothing was merged, no AI call is made.

## Note on the prompt
The prompt says "use the name given above" for functions that don't exist yet, but it never names any
functions. So the AI had to choose the module API itself:
`script/team_release_notes.py` with `select_prs`, `group_by_label`, `generate_release_notes`,
`create_draft_release`, and the constant `ADVISORY_BANNER`.

## Planned tests (expected result)
| # | Test | Criterion | Expected result |
|---|------|-----------|-----------------|
| 1 | `test_only_prs_merged_between_tags_are_selected` | AC1 | Only PRs merged after the previous tag and at/before the new tag are returned; earlier and unmerged PRs are excluded |
| 2 | `test_prs_are_grouped_into_sections_by_label` | AC2 | `feature`→Features, `bugfix`→Bug Fixes, other/no label→Other |
| 3 | `test_notes_start_with_advisory_banner` | AC3 | Output starts with `ADVISORY_BANNER`, followed by the AI text |
| 4 | `test_ai_prompt_contains_every_selected_pr` | AC1/AC3 | Prompt sent to the AI includes each PR's number and title |
| 5 | `test_release_is_created_as_draft` | AC4 | `create_release` called once with `draft=True` and the notes as body |
| 6 | `test_release_is_never_published` | AC4 | No publish/update call is made on the GitHub client |
| 7 | `test_falls_back_to_pr_list_when_ai_fails` | AC5 | On an AI exception, output = banner + bulleted list of titles and links; no exception raised |
| 8 | `test_falls_back_when_ai_times_out` | AC5 | Same as 7 for `TimeoutError` |
| 9 | `test_no_changes_skips_ai_call` | AC6 | Output contains "No changes since v1.0.0"; AI client never called |
