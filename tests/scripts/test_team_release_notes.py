"""Tests for the D6 AI release notes script (advisory, human edits before publishing)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from script.team_release_notes import (
    ADVISORY_BANNER,
    create_draft_release,
    generate_release_notes,
    group_by_label,
    select_prs,
)

PREVIOUS_TAG_DATE = datetime(2026, 10, 1, tzinfo=UTC)
NEW_TAG_DATE = datetime(2026, 11, 1, tzinfo=UTC)


def _pr(number: int, title: str, merged_at: datetime | None, labels: list[str]) -> dict:
    return {
        "number": number,
        "title": title,
        "merged_at": merged_at,
        "labels": labels,
        "url": f"https://github.com/ibll/home-assistant-core/pull/{number}",
    }


@pytest.fixture
def prs() -> list[dict]:
    return [
        _pr(1, "Old feature", datetime(2026, 9, 15, tzinfo=UTC), ["feature"]),
        _pr(2, "Add Foscam stop_ptz", datetime(2026, 10, 10, tzinfo=UTC), ["feature"]),
        _pr(3, "Fix pipeline cache", datetime(2026, 10, 20, tzinfo=UTC), ["bugfix"]),
        _pr(4, "Update docs", datetime(2026, 10, 25, tzinfo=UTC), []),
        _pr(5, "Unmerged experiment", None, ["feature"]),
    ]


def test_only_prs_merged_between_tags_are_selected(prs: list[dict]) -> None:
    selected = select_prs(prs, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    assert [pr["number"] for pr in selected] == [2, 3, 4]


def test_tag_boundaries_exclude_previous_and_include_new_tag() -> None:
    """EDITED: boundary case missing from the AI's tests."""
    prs = [
        _pr(10, "Merged at previous tag", PREVIOUS_TAG_DATE, []),
        _pr(11, "Merged at new tag", NEW_TAG_DATE, []),
    ]

    assert [pr["number"] for pr in select_prs(prs, PREVIOUS_TAG_DATE, NEW_TAG_DATE)] == [11]


def test_prs_are_grouped_into_sections_by_label(prs: list[dict]) -> None:
    sections = group_by_label(select_prs(prs, PREVIOUS_TAG_DATE, NEW_TAG_DATE))

    assert [pr["number"] for pr in sections["Features"]] == [2]
    assert [pr["number"] for pr in sections["Bug Fixes"]] == [3]
    assert [pr["number"] for pr in sections["Other"]] == [4]


def test_notes_start_with_advisory_banner(prs: list[dict]) -> None:
    ai_client = MagicMock()
    ai_client.complete.return_value = "## Features\n- Foscam can stop PTZ movement"

    notes = generate_release_notes(prs, "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    assert notes.startswith(ADVISORY_BANNER)
    assert "Foscam can stop PTZ movement" in notes


def test_ai_prompt_contains_every_selected_pr(prs: list[dict]) -> None:
    ai_client = MagicMock()
    ai_client.complete.return_value = "draft"

    generate_release_notes(prs, "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    prompt = ai_client.complete.call_args.args[0]
    for number, title in [(2, "Add Foscam stop_ptz"), (3, "Fix pipeline cache"), (4, "Update docs")]:
        assert f"#{number}" in prompt
        assert title in prompt
    assert "Old feature" not in prompt
    assert "Unmerged experiment" not in prompt


def test_release_is_created_as_draft() -> None:
    github = MagicMock()

    create_draft_release(github, "v1.1.0", "notes body")

    # EDITED: assert only what AC4 requires instead of the exact argument list.
    github.create_release.assert_called_once()
    kwargs = github.create_release.call_args.kwargs
    assert kwargs["tag"] == "v1.1.0"
    assert kwargs["body"] == "notes body"
    assert kwargs["draft"] is True
    assert len(github.mock_calls) == 1  # nothing else (e.g. a publish) is called


def test_falls_back_to_pr_list_when_ai_fails(prs: list[dict]) -> None:
    ai_client = MagicMock()
    ai_client.complete.side_effect = RuntimeError("model unavailable")

    notes = generate_release_notes(prs, "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    # EDITED: AC5 asks for a bulleted list of titles and links, not one exact format.
    assert notes.startswith(ADVISORY_BANNER)
    bullets = [line for line in notes.splitlines() if line.startswith("- ")]
    assert len(bullets) == 3
    for number, title in [(2, "Add Foscam stop_ptz"), (3, "Fix pipeline cache"), (4, "Update docs")]:
        assert any(
            title in line and f"https://github.com/ibll/home-assistant-core/pull/{number}" in line
            for line in bullets
        )


def test_falls_back_when_ai_times_out(prs: list[dict]) -> None:
    ai_client = MagicMock()
    ai_client.complete.side_effect = TimeoutError()

    notes = generate_release_notes(prs, "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    # EDITED: check title and link without depending on bullet formatting.
    assert notes.startswith(ADVISORY_BANNER)
    assert any(
        "Add Foscam stop_ptz" in line and "/pull/2" in line
        for line in notes.splitlines()
        if line.startswith("- ")
    )


def test_no_changes_skips_ai_call() -> None:
    ai_client = MagicMock()

    notes = generate_release_notes([], "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    assert "No changes since v1.0.0" in notes
    ai_client.complete.assert_not_called()
