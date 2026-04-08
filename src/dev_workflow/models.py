from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Stage(str, Enum):
    SPEC = "spec"
    PLAN = "plan"
    EXECUTION = "execution"
    COMPLETE = "complete"


class SubtaskStatus(str, Enum):
    NOT_STARTED = "not-started"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    BLOCKED = "blocked"


class ReviewVerdict(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    BLOCKED = "blocked"


@dataclass
class Space:
    name: str           # lowercase, alphanumeric + hyphens
    description: str    # short human-readable label
    created: datetime


@dataclass
class ActivityEntry:
    timestamp: datetime
    action: str
    detail: str


@dataclass
class VerificationStep:
    description: str
    checked: bool = False


@dataclass
class Task:
    task_id: str
    slug: str
    title: str
    summary: str
    stage: Stage
    workspaces: list[Path]
    task_folder: Path
    created: datetime
    updated: datetime
    space: str = ""


@dataclass
class SubtaskEntry:
    id: int
    title: str
    status: SubtaskStatus
    file_path: Path


@dataclass
class TaskProgress:
    task: Task
    approved_spec: Path | None = None
    approved_plan: Path | None = None
    subtask_index: list[SubtaskEntry] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    recent_activity: list[ActivityEntry] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)


@dataclass
class Subtask:
    id: int
    title: str
    description: str
    verification: list[VerificationStep] = field(default_factory=list)
    status: SubtaskStatus = SubtaskStatus.NOT_STARTED
    execution_summary: str | None = None
    files_changed: list[str] = field(default_factory=list)
    what_changed: str | None = None
    blockers: list[str] = field(default_factory=list)


@dataclass
class PlanTask:
    id: int
    title: str
    description: str
    verification_steps: list[str] = field(default_factory=list)
    dependencies: list[int] = field(default_factory=list)


@dataclass
class Spec:
    version: int
    title: str
    overview: str
    requirements: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class Plan:
    version: int
    title: str
    spec_path: Path
    approach: str
    tasks: list[PlanTask] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    raw_content: str = ""


@dataclass
class Review:
    stage: str
    version: int
    verdict: ReviewVerdict
    inputs_read: list[str] = field(default_factory=list)
    critical: list[str] = field(default_factory=list)
    important: list[str] = field(default_factory=list)
    minor: list[str] = field(default_factory=list)
    required_revisions: list[str] = field(default_factory=list)
    residual_risks: list[str] = field(default_factory=list)
