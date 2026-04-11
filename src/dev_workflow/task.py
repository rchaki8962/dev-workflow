# src/dev_workflow/task.py
"""Task lifecycle -- init and lookup."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from dev_workflow.errors import TaskNotFoundError
from dev_workflow.models import Artifact, Checkpoint, Task
from dev_workflow.slug import resolve_slug
from dev_workflow.store import Store


def init_task(
    store: Store,
    base_dir: Path,
    title: str,
    space: str,
    prompt: str | None = None,
    workspaces: list[str] | None = None,
) -> Task:
    """Create a new task.

    1. Ensure space exists (auto-create if needed)
    2. Generate slug with collision handling
    3. Generate task_id (UUID)
    4. Compute task_folder path
    5. Insert task record
    6. If prompt provided, create implicit checkpoint #0 with prompt as artifact
    """
    store.ensure_space(space)
    slug = resolve_slug(title, store.slug_exists, space)
    task_id = str(uuid.uuid4())
    today = date.today().isoformat()
    task_folder = base_dir / space / "tasks" / f"{today}-{slug}"
    now = datetime.now(timezone.utc)

    task = Task(
        task_id=task_id,
        slug=slug,
        title=title,
        space=space,
        summary="",
        last_milestone="",
        last_checkpoint_at=None,
        checkpoint_count=0,
        workspaces=workspaces or [],
        task_folder=task_folder,
        created=now,
        updated=now,
    )
    store.create_task(task)

    if prompt is not None:
        _save_initial_checkpoint(store, task, prompt, now)
        # Refresh task after checkpoint updated it
        task = store.get_task_by_id(task_id)

    return task


def _save_initial_checkpoint(
    store: Store, task: Task, prompt: str, now: datetime
) -> None:
    """Create implicit checkpoint #0 with the original prompt as an artifact."""
    checkpoint = Checkpoint(
        id=None,
        task_id=task.task_id,
        checkpoint_number=0,
        milestone="task-initialized",
        summary=task.title,
        user_directives=[],
        insights=[],
        next_steps=[],
        open_questions=[],
        resolved_questions=[],
        created=now,
    )
    artifact = Artifact(
        id=None,
        task_id=task.task_id,
        checkpoint_id=None,
        type="prompt",
        name="original-prompt",
        version=1,
        description="Original task prompt",
        content=prompt,
        checksum=hashlib.sha256(prompt.encode()).hexdigest(),
        created=now,
    )
    store.save_checkpoint(checkpoint, [], [artifact], [])


def get_task(store: Store, slug: str, space: str) -> Task:
    """Get a task by slug, raising if not found."""
    task = store.get_task(slug, space)
    if task is None:
        raise TaskNotFoundError(f"Task '{slug}' not found in space '{space}'")
    return task
