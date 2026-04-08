"""State registry: one JSON file per task in state/ directory."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.exceptions import TaskNotFoundError
from dev_workflow.models import Stage, Task


class StateManager:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir

    def _ensure_dir(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, slug: str) -> Path:
        return self.state_dir / f"{slug}.json"

    def save(self, task: Task) -> None:
        """Write task to state/<slug>.json."""
        self._ensure_dir()
        data = _task_to_dict(task)
        self._path_for(task.slug).write_text(json.dumps(data, indent=2) + "\n")

    def load(self, slug: str) -> Task:
        """Read state/<slug>.json into Task. Raises TaskNotFoundError if not found."""
        path = self._path_for(slug)
        if not path.exists():
            raise TaskNotFoundError(slug)
        data = json.loads(path.read_text())
        return _dict_to_task(data)

    def list_all(self, stage_filter: Stage | None = None) -> list[Task]:
        """List all tasks, optionally filtered by stage, sorted by updated desc."""
        self._ensure_dir()
        tasks = []
        for path in self.state_dir.glob("*.json"):
            data = json.loads(path.read_text())
            task = _dict_to_task(data)
            if stage_filter is None or task.stage == stage_filter:
                tasks.append(task)
        tasks.sort(key=lambda t: t.updated, reverse=True)
        return tasks

    def search(self, query: str) -> list[Task]:
        """Fuzzy search (substring, case-insensitive) across slug, title, summary."""
        query_lower = query.lower()
        results = []
        for task in self.list_all():
            if (
                query_lower in task.slug.lower()
                or query_lower in task.title.lower()
                or query_lower in task.summary.lower()
            ):
                results.append(task)
        return results

    def update(self, slug: str, **fields) -> Task:
        """Update specific fields in state JSON. Returns updated Task.

        Supports both Task dataclass fields and extra JSON-only fields
        like ``progress``. Extra fields are preserved in the JSON file
        without needing to live on the Task dataclass.
        """
        path = self._path_for(slug)
        if not path.exists():
            raise TaskNotFoundError(slug)

        # Read existing raw JSON so non-dataclass fields (e.g. progress) survive
        raw = json.loads(path.read_text())

        # Separate Task-dataclass fields from extra fields
        task = _dict_to_task(raw)
        task_field_names = {f.name for f in task.__dataclass_fields__.values()}
        dc_updates = {}
        extra_updates = {}

        for key, value in fields.items():
            if key in task_field_names:
                dc_updates[key] = value
            else:
                extra_updates[key] = value

        if dc_updates:
            task = replace(task, **dc_updates, updated=datetime.now(timezone.utc))
        else:
            # Still bump updated even if only extra fields changed
            task = replace(task, updated=datetime.now(timezone.utc))

        # Rebuild JSON from task, then layer preserved and new extras on top
        data = _task_to_dict(task)
        # Preserve existing extra/overridden fields from the raw JSON
        # (e.g. progress may have been set to a non-default value)
        _task_dict_keys = set(data.keys())
        for key in raw:
            if key not in _task_dict_keys:
                # Truly extra field -- always preserve
                data[key] = raw[key]
            elif key not in {f.name for f in task.__dataclass_fields__.values()}:
                # Key exists in both dicts but is NOT a dataclass field
                # (like "progress") -- prefer the stored value over the default
                data[key] = raw[key]
        # Apply new extra updates (these win over everything)
        data.update(extra_updates)

        self._path_for(task.slug).write_text(json.dumps(data, indent=2) + "\n")
        return task

    def exists(self, slug: str) -> bool:
        return self._path_for(slug).exists()

    def all_slugs(self) -> list[str]:
        """Return all existing slugs (for collision detection)."""
        self._ensure_dir()
        return [p.stem for p in self.state_dir.glob("*.json")]

    def delete(self, slug: str) -> None:
        """Delete a state file. Raises TaskNotFoundError if not found."""
        path = self._path_for(slug)
        if not path.exists():
            raise TaskNotFoundError(slug)
        path.unlink()


def _task_to_dict(task: Task) -> dict:
    """Serialize Task to JSON-compatible dict."""
    return {
        "task_id": task.task_id,
        "slug": task.slug,
        "title": task.title,
        "summary": task.summary,
        "stage": task.stage.value,
        "progress": "0/0 subtasks",
        "workspaces": [str(w) for w in task.workspaces],
        "task_folder": str(task.task_folder),
        "created": task.created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated": task.updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "space": task.space,
    }


def _dict_to_task(data: dict) -> Task:
    """Deserialize dict to Task."""
    return Task(
        task_id=data["task_id"],
        slug=data["slug"],
        title=data["title"],
        summary=data.get("summary", ""),
        stage=Stage(data["stage"]),
        workspaces=[Path(w) for w in data.get("workspaces", [])],
        task_folder=Path(data["task_folder"]),
        created=datetime.fromisoformat(data["created"].replace("Z", "+00:00")),
        updated=datetime.fromisoformat(data["updated"].replace("Z", "+00:00")),
        space=data.get("space", ""),
    )
