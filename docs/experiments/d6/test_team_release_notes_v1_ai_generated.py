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

    github.create_release.assert_called_once_with(tag="v1.1.0", body="notes body", draft=True)


def test_release_is_never_published() -> None:
    github = MagicMock()

    create_draft_release(github, "v1.1.0", "notes body")

    github.publish_release.assert_not_called()
    github.update_release.assert_not_called()


def test_falls_back_to_pr_list_when_ai_fails(prs: list[dict]) -> None:
    ai_client = MagicMock()
    ai_client.complete.side_effect = RuntimeError("model unavailable")

    notes = generate_release_notes(prs, "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    assert notes.startswith(ADVISORY_BANNER)
    assert "- Add Foscam stop_ptz (https://github.com/ibll/home-assistant-core/pull/2)" in notes
    assert "- Fix pipeline cache (https://github.com/ibll/home-assistant-core/pull/3)" in notes
    assert "- Update docs (https://github.com/ibll/home-assistant-core/pull/4)" in notes


def test_falls_back_when_ai_times_out(prs: list[dict]) -> None:
    ai_client = MagicMock()
    ai_client.complete.side_effect = TimeoutError()

    notes = generate_release_notes(prs, "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    assert notes.startswith(ADVISORY_BANNER)
    assert "- Add Foscam stop_ptz" in notes


def test_no_changes_skips_ai_call() -> None:
    ai_client = MagicMock()

    notes = generate_release_notes([], "v1.0.0", "v1.1.0", ai_client, PREVIOUS_TAG_DATE, NEW_TAG_DATE)

    assert "No changes since v1.0.0" in notes
    ai_client.complete.assert_not_called()
