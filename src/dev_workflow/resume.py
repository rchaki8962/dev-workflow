# src/dev_workflow/resume.py
"""Context bundle synthesis for task resume."""

from __future__ import annotations

import json

from dev_workflow.models import Task
from dev_workflow.store import Store
from dev_workflow.views import regenerate_task_folder


def resume_task(store: Store, task: Task, format: str = "json") -> str:
    """Synthesize a context bundle for resuming a task.

    Args:
        format: "json" for structured output, "md" for regenerated task folder path.
    """
    if format == "md":
        folder = regenerate_task_folder(store, task)
        return str(folder / "HANDOFF.md")

    return _resume_json(store, task)


def _resume_json(store: Store, task: Task) -> str:
    """Build the JSON context bundle (PRD Section 10.5)."""
    checkpoints = store.get_checkpoints(task.task_id)
    decisions = store.get_decisions(task.task_id)
    artifacts = store.get_artifacts(task.task_id)
    verifications = store.get_verifications(task.task_id)

    latest_cp = checkpoints[-1] if checkpoints else None

    # Latest version of each artifact (excluding prompt)
    latest_artifacts: dict[str, dict] = {}
    for a in artifacts:
        if a.name == "original-prompt":
            continue
        if a.name not in latest_artifacts or a.version > latest_artifacts[a.name]["version"]:
            latest_artifacts[a.name] = {
                "type": a.type,
                "name": a.name,
                "version": a.version,
                "description": a.description,
            }

    bundle = {
        "slug": task.slug,
        "title": task.title,
        "space": task.space,
        "last_milestone": task.last_milestone,
        "last_checkpoint_at": (
            task.last_checkpoint_at.isoformat() if task.last_checkpoint_at else None
        ),
        "checkpoint_count": task.checkpoint_count,
        "summary": task.summary,
        "next_steps": latest_cp.next_steps if latest_cp else [],
        "open_questions": latest_cp.open_questions if latest_cp else [],
        "user_directives": latest_cp.user_directives if latest_cp else [],
        "decisions": [
            {
                "number": d.decision_number,
                "title": d.title,
                "rationale": d.rationale,
            }
            for d in decisions
        ],
        "artifacts": list(latest_artifacts.values()),
        "recent_verifications": [
            {
                "type": v.type,
                "result": v.result,
                "detail": v.detail,
            }
            for v in verifications[-5:]
        ],
        "handoff_path": str(task.task_folder / "HANDOFF.md"),
        "detail_paths": {
            "decisions": str(task.task_folder / "context" / "decisions.md"),
            "record": str(task.task_folder / "record" / "development-record.md"),
            "checkpoints": str(task.task_folder / "record" / "checkpoints.md"),
        },
    }

    return json.dumps(bundle, indent=2)
