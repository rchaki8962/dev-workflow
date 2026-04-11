"""Domain model dataclasses.

Plain data containers passed between layers. No behavior, no ORM.
List fields are Python lists -- the store serializes them as JSON for SQLite.
All timestamps are UTC datetime objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Space:
    name: str
    description: str
    created: datetime


@dataclass
class Task:
    task_id: str  # UUID
    slug: str
    title: str
    space: str
    summary: str
    last_milestone: str
    last_checkpoint_at: datetime | None
    checkpoint_count: int
    workspaces: list[str]
    task_folder: Path
    created: datetime
    updated: datetime
    closed_at: datetime | None = None


@dataclass
class Checkpoint:
    id: int | None  # None before persistence
    task_id: str
    checkpoint_number: int
    milestone: str
    summary: str
    user_directives: list[str]
    insights: list[str]
    next_steps: list[str]
    open_questions: list[str]
    resolved_questions: list[str]
    created: datetime


@dataclass
class Decision:
    id: int | None
    task_id: str
    checkpoint_id: int | None
    decision_number: int
    title: str
    rationale: str
    alternatives: list[str]
    context: str
    created: datetime


@dataclass
class Artifact:
    id: int | None
    task_id: str
    checkpoint_id: int | None
    type: str
    name: str
    version: int
    description: str
    content: str
    checksum: str  # SHA-256 of content
    created: datetime


@dataclass
class Verification:
    id: int | None
    task_id: str
    checkpoint_id: int | None
    type: str
    result: str
    detail: str
    command: str
    created: datetime


@dataclass
class CheckpointPayload:
    """Raw JSON payload from agent input. Validated before decomposition
    into domain objects by checkpoint.py."""

    milestone: str
    summary: str
    decisions: list[dict] | None = None
    artifacts: list[dict] | None = None
    verifications: list[dict] | None = None
    user_directives: list[str] | None = None
    insights: list[str] | None = None
    next_steps: list[str] | None = None
    open_questions: list[str] | None = None
    resolved_questions: list[str] | None = None
