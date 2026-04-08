"""Progress file parsing and updating."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.models import (
    ActivityEntry,
    Stage,
    SubtaskEntry,
    SubtaskStatus,
    Task,
    TaskProgress,
)


def parse_progress(content: str) -> TaskProgress:
    """
    Parse 00-progress.md content into a TaskProgress dataclass.

    Strategy: extract sections by heading, parse each section's content.
    The file has a known structure (from our template), so section extraction
    is reliable.
    """
    # Extract header metadata
    task_id = _extract_meta(content, "Task ID")
    stage_str = _extract_meta(content, "Current Stage")
    approved_spec_str = _extract_meta(content, "Approved Spec")
    approved_plan_str = _extract_meta(content, "Approved Plan")
    updated_str = _extract_meta(content, "Last Updated")

    # Extract title from first heading: "# Task: <title>"
    title_match = re.search(r"^#\s+Task:\s*(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Unknown"

    # Parse workspaces section
    workspaces = _parse_list_section(content, "Workspaces")
    workspace_paths = [Path(w) for w in workspaces if w != "(none)"]

    # Parse subtask index table
    subtask_index = _parse_subtask_table(content)

    # Parse blockers
    blockers = _parse_list_section(content, "Blockers / Open Questions")
    blockers = [b for b in blockers if b != "(none)"]

    # Parse recent activity
    recent_activity = _parse_activity_section(content)

    # Parse next actions
    next_actions = _parse_list_section(content, "Next Actions")
    next_actions = [a for a in next_actions if a != "(none)"]

    # Build Task (we don't have all fields from progress file alone, fill what we can)
    task = Task(
        task_id=task_id,
        slug="",  # Not stored in progress file
        title=title,
        summary="",  # Not stored in progress file
        stage=Stage(stage_str) if stage_str else Stage.SPEC,
        workspaces=workspace_paths,
        task_folder=Path(""),  # Not stored in progress file
        created=datetime.now(timezone.utc),  # Not stored; use now as placeholder
        updated=_parse_timestamp(updated_str) if updated_str else datetime.now(timezone.utc),
    )

    return TaskProgress(
        task=task,
        approved_spec=(
            Path(approved_spec_str)
            if approved_spec_str and approved_spec_str != "pending"
            else None
        ),
        approved_plan=(
            Path(approved_plan_str)
            if approved_plan_str and approved_plan_str != "pending"
            else None
        ),
        subtask_index=subtask_index,
        blockers=blockers,
        recent_activity=recent_activity,
        next_actions=next_actions,
    )


def _extract_meta(content: str, key: str) -> str:
    """Extract a metadata value: - **Key**: value"""
    pattern = re.compile(
        rf"^\s*-\s*\*\*{re.escape(key)}\*\*:\s*(.+)$", re.MULTILINE
    )
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def _extract_section(content: str, heading: str) -> str:
    """Extract everything between a ## heading and the next ## heading."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1).strip() if match else ""


def _parse_list_section(content: str, heading: str) -> list[str]:
    """Parse a section that contains a markdown bullet list."""
    section = _extract_section(content, heading)
    items = []
    for line in section.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            items.append(line[2:].strip())
    return items


def _parse_subtask_table(content: str) -> list[SubtaskEntry]:
    """Parse the subtask index markdown table."""
    section = _extract_section(content, "Subtask Index")
    entries = []
    for line in section.split("\n"):
        line = line.strip()
        # Skip header and separator rows
        if not line.startswith("|") or line.startswith("| #") or line.startswith("|--"):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 4:
            try:
                entry = SubtaskEntry(
                    id=int(parts[0]),
                    title=parts[1],
                    status=SubtaskStatus(parts[2]),
                    file_path=Path(parts[3]),
                )
                entries.append(entry)
            except (ValueError, KeyError):
                continue
    return entries


def _parse_activity_section(content: str) -> list[ActivityEntry]:
    """Parse recent activity entries: - [timestamp] action: detail"""
    section = _extract_section(content, "Recent Activity")
    entries = []
    for line in section.split("\n"):
        line = line.strip()
        match = re.match(r"^-\s*\[(.+?)\]\s*(.+?):\s*(.+)$", line)
        if match:
            timestamp = _parse_timestamp(match.group(1))
            entries.append(
                ActivityEntry(
                    timestamp=timestamp,
                    action=match.group(2).strip(),
                    detail=match.group(3).strip(),
                )
            )
    return entries


def _parse_timestamp(ts_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string."""
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def update_progress_stage_status(
    progress: TaskProgress, stage: Stage, status_text: str
) -> TaskProgress:
    """Return a new TaskProgress with updated stage and status text."""
    new_task = replace(progress.task, stage=stage, updated=datetime.now(timezone.utc))
    return replace(progress, task=new_task)


def update_progress_subtask_index(
    progress: TaskProgress, entries: list[SubtaskEntry]
) -> TaskProgress:
    """Return a new TaskProgress with updated subtask index."""
    new_task = replace(progress.task, updated=datetime.now(timezone.utc))
    return replace(progress, task=new_task, subtask_index=entries)


def update_progress_recent_activity(
    progress: TaskProgress,
    activities: list[ActivityEntry],
    max_entries: int = 10,
) -> TaskProgress:
    """Return a new TaskProgress with recent activity from the last N entries."""
    recent = activities[-max_entries:] if len(activities) > max_entries else activities
    new_task = replace(progress.task, updated=datetime.now(timezone.utc))
    return replace(progress, task=new_task, recent_activity=recent)
