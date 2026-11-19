"""Draft advisory release notes with AI (issue D6).

The notes are a starting point only. They are always saved as a *draft*
GitHub release; a maintainer edits and publishes them by hand.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Protocol

_LOGGER = logging.getLogger(__name__)

ADVISORY_BANNER = (
    "> [!WARNING]\n"
    "> AI-generated draft. Review and edit these notes before publishing.\n"
)

SECTION_LABELS: dict[str, str] = {
    "feature": "Features",
    "new-feature": "Features",
    "bugfix": "Bug Fixes",
    "bug": "Bug Fixes",
}
SECTION_ORDER = ("Features", "Bug Fixes", "Other")


class AIClient(Protocol):
    """Anything that turns a prompt into text."""

    def complete(self, prompt: str) -> str:
        """Return the model's completion for the prompt."""


class GitHubClient(Protocol):
    """The subset of the GitHub releases API this script uses."""

    def create_release(self, *, tag: str, name: str, body: str, draft: bool) -> Any:
        """Create a release."""


def _as_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def select_prs(
    prs: Iterable[dict[str, Any]], previous_tag_date: datetime, new_tag_date: datetime
) -> list[dict[str, Any]]:
    """Return merged PRs with previous_tag_date < merged_at <= new_tag_date."""
    selected = []
    for pr in prs:
        merged_at = _as_datetime(pr.get("merged_at"))
        if merged_at is not None and previous_tag_date < merged_at <= new_tag_date:
            selected.append(pr)
    return sorted(selected, key=lambda pr: _as_datetime(pr["merged_at"]))


def group_by_label(prs: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group PRs into release-note sections; unlabelled PRs go under Other."""
    sections: dict[str, list[dict[str, Any]]] = {name: [] for name in SECTION_ORDER}
    for pr in prs:
        section = next(
            (SECTION_LABELS[label] for label in pr.get("labels", []) if label in SECTION_LABELS),
            "Other",
        )
        sections[section].append(pr)
    return sections


def build_prompt(sections: dict[str, list[dict[str, Any]]], previous_tag: str, new_tag: str) -> str:
    """Build the instruction sent to the model."""
    lines = [
        f"Write concise release notes for {new_tag} (changes since {previous_tag}).",
        "Keep the section headings. Do not invent changes that are not listed.",
        "",
    ]
    for name in SECTION_ORDER:
        if sections[name]:
            lines.append(f"## {name}")
            lines.extend(f"- #{pr['number']} {pr['title']}" for pr in sections[name])
            lines.append("")
    return "\n".join(lines)


def fallback_notes(sections: dict[str, list[dict[str, Any]]]) -> str:
    """Plain list of PR titles and links, used when the AI is unavailable."""
    lines = []
    for name in SECTION_ORDER:
        if sections[name]:
            lines.append(f"## {name}")
            lines.extend(f"- [{pr['title']}]({pr['url']}) (#{pr['number']})" for pr in sections[name])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_release_notes(
    prs: Iterable[dict[str, Any]],
    previous_tag: str,
    new_tag: str,
    ai_client: AIClient,
    previous_tag_date: datetime,
    new_tag_date: datetime,
) -> str:
    """Return advisory release notes; never raises because the AI failed."""
    selected = select_prs(prs, previous_tag_date, new_tag_date)
    if not selected:
        return f"{ADVISORY_BANNER}\nNo changes since {previous_tag}.\n"

    sections = group_by_label(selected)
    try:
        body = ai_client.complete(build_prompt(sections, previous_tag, new_tag))
    except Exception:  # noqa: BLE001 - any AI failure must fall back, not fail the release
        _LOGGER.warning("AI release notes failed; using the plain PR list", exc_info=True)
        body = fallback_notes(sections)
    return f"{ADVISORY_BANNER}\n{body.strip()}\n"


def create_draft_release(github: GitHubClient, tag: str, notes: str) -> Any:
    """Save the notes as a draft release. Publishing is left to a human."""
    return github.create_release(tag=tag, name=tag, body=notes, draft=True)


def main() -> None:
    """Write advisory notes to a file for the release workflow to attach to a draft."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prs", type=Path, required=True, help="JSON list of PRs from the GitHub API")
    parser.add_argument("--previous-tag", required=True)
    parser.add_argument("--previous-tag-date", required=True)
    parser.add_argument("--new-tag", required=True)
    parser.add_argument("--new-tag-date", required=True)
    parser.add_argument("--output", type=Path, default=Path("release-notes.md"))
    args = parser.parse_args()

    from script.team_ai_client import default_client  # noqa: PLC0415 - optional dependency

    notes = generate_release_notes(
        json.loads(args.prs.read_text()),
        args.previous_tag,
        args.new_tag,
        default_client(),
        _as_datetime(args.previous_tag_date),
        _as_datetime(args.new_tag_date),
    )
    args.output.write_text(notes)


if __name__ == "__main__":
    main()
