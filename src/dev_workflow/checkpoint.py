# src/dev_workflow/checkpoint.py
"""Checkpoint creation -- validation, payload decomposition, persistence."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from dev_workflow.errors import PayloadError
from dev_workflow.models import (
    Artifact,
    Checkpoint,
    CheckpointPayload,
    Decision,
    Task,
    Verification,
)
from dev_workflow.store import Store


def validate_payload(payload: CheckpointPayload) -> None:
    """Strict validation of checkpoint payload.

    Raises PayloadError with a clear message on any invalid field.
    """
    if not payload.milestone or not payload.milestone.strip():
        raise PayloadError("Checkpoint payload requires a non-empty 'milestone'")
    if not payload.summary or not payload.summary.strip():
        raise PayloadError("Checkpoint payload requires a non-empty 'summary'")

    for i, d in enumerate(payload.decisions or []):
        if not d.get("title"):
            raise PayloadError(f"Decision {i + 1} requires a 'title'")

    for i, a in enumerate(payload.artifacts or []):
        if not a.get("name"):
            raise PayloadError(f"Artifact {i + 1} requires a 'name'")
        if not a.get("type"):
            raise PayloadError(f"Artifact {i + 1} requires a 'type'")
        if not a.get("content"):
            raise PayloadError(f"Artifact {i + 1} requires non-empty 'content'")

    for i, v in enumerate(payload.verifications or []):
        if not v.get("type"):
            raise PayloadError(f"Verification {i + 1} requires a 'type'")
        if not v.get("result"):
            raise PayloadError(f"Verification {i + 1} requires a 'result'")


def create_checkpoint(
    store: Store, task: Task, payload: CheckpointPayload
) -> int:
    """Create a checkpoint from a validated payload.

    1. Validate payload
    2. Build domain objects
    3. Persist atomically via store
    4. Return checkpoint number
    """
    validate_payload(payload)
    now = datetime.now(timezone.utc)

    checkpoint_number = store.get_next_checkpoint_number(task.task_id)

    checkpoint = Checkpoint(
        id=None,
        task_id=task.task_id,
        checkpoint_number=checkpoint_number,
        milestone=payload.milestone,
        summary=payload.summary,
        user_directives=payload.user_directives or [],
        insights=payload.insights or [],
        next_steps=payload.next_steps or [],
        open_questions=payload.open_questions or [],
        resolved_questions=payload.resolved_questions or [],
        created=now,
    )

    next_decision = store.get_next_decision_number(task.task_id)
    decisions = []
    for i, d in enumerate(payload.decisions or []):
        decisions.append(
            Decision(
                id=None,
                task_id=task.task_id,
                checkpoint_id=None,
                decision_number=next_decision + i,
                title=d["title"],
                rationale=d.get("rationale", ""),
                alternatives=d.get("alternatives", []),
                context=d.get("context", ""),
                created=now,
            )
        )

    artifacts = []
    for a in payload.artifacts or []:
        content = a["content"]
        artifacts.append(
            Artifact(
                id=None,
                task_id=task.task_id,
                checkpoint_id=None,
                type=a["type"],
                name=a["name"],
                version=0,  # Store auto-increments
                description=a.get("description", ""),
                content=content,
                checksum=hashlib.sha256(content.encode()).hexdigest(),
                created=now,
            )
        )

    verifications = []
    for v in payload.verifications or []:
        verifications.append(
            Verification(
                id=None,
                task_id=task.task_id,
                checkpoint_id=None,
                type=v["type"],
                result=v["result"],
                detail=v.get("detail", ""),
                command=v.get("command", ""),
                created=now,
            )
        )

    return store.save_checkpoint(checkpoint, decisions, artifacts, verifications)
