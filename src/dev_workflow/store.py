"""SQLite storage layer.

This is the ONLY module that imports sqlite3. All database access goes through
the Store class. Schema is auto-created on first connection.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.errors import (
    SpaceNotEmptyError,
    SpaceNotFoundError,
    StoreError,
    TaskNotFoundError,
)
from dev_workflow.models import (
    Artifact,
    Checkpoint,
    Decision,
    Space,
    Task,
    Verification,
)

_SCHEMA_VERSION = 1

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS spaces (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    space TEXT NOT NULL REFERENCES spaces(name),
    summary TEXT NOT NULL DEFAULT '',
    last_milestone TEXT NOT NULL DEFAULT '',
    last_checkpoint_at TEXT,
    checkpoint_count INTEGER NOT NULL DEFAULT 0,
    workspaces TEXT NOT NULL DEFAULT '[]',
    task_folder TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    closed_at TEXT,
    UNIQUE(slug, space)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_number INTEGER NOT NULL,
    milestone TEXT NOT NULL,
    summary TEXT NOT NULL,
    user_directives TEXT NOT NULL DEFAULT '[]',
    insights TEXT NOT NULL DEFAULT '[]',
    next_steps TEXT NOT NULL DEFAULT '[]',
    open_questions TEXT NOT NULL DEFAULT '[]',
    resolved_questions TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    UNIQUE(task_id, checkpoint_number)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    decision_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    alternatives TEXT NOT NULL DEFAULT '[]',
    context TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    UNIQUE(task_id, decision_number)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    created TEXT NOT NULL,
    UNIQUE(task_id, name, version)
);

CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    command TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """SQLite-backed storage for all dev-workflow data."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        if cursor.fetchone() is None:
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- Spaces ---

    def create_space(self, name: str, description: str) -> None:
        """Create a new space. Raises on duplicate."""
        now = _now_iso()
        self._conn.execute(
            "INSERT INTO spaces (name, description, created) VALUES (?, ?, ?)",
            (name, description, now),
        )
        self._conn.commit()

    def get_space(self, name: str) -> Space | None:
        """Get a space by name, or None if not found."""
        row = self._conn.execute(
            "SELECT name, description, created FROM spaces WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return Space(
            name=row["name"],
            description=row["description"],
            created=datetime.fromisoformat(row["created"]),
        )

    def list_spaces(self) -> list[Space]:
        """List all spaces ordered by name."""
        rows = self._conn.execute(
            "SELECT name, description, created FROM spaces ORDER BY name"
        ).fetchall()
        return [
            Space(
                name=r["name"],
                description=r["description"],
                created=datetime.fromisoformat(r["created"]),
            )
            for r in rows
        ]

    def remove_space(self, name: str) -> None:
        """Remove a space. Raises SpaceNotEmptyError if tasks exist."""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE space = ?", (name,)
        ).fetchone()[0]
        if count > 0:
            raise SpaceNotEmptyError(
                f"Cannot remove space '{name}': {count} task(s) still exist"
            )
        self._conn.execute("DELETE FROM spaces WHERE name = ?", (name,))
        self._conn.commit()

    def ensure_space(self, name: str) -> None:
        """Create space if it doesn't exist."""
        if self.get_space(name) is None:
            self.create_space(name, "")

    # --- Tasks ---

    def create_task(self, task: Task) -> None:
        """Insert a new task record."""
        self._conn.execute(
            """INSERT INTO tasks
            (task_id, slug, title, space, summary, last_milestone,
             last_checkpoint_at, checkpoint_count, workspaces,
             task_folder, created, updated, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.task_id,
                task.slug,
                task.title,
                task.space,
                task.summary,
                task.last_milestone,
                task.last_checkpoint_at.isoformat() if task.last_checkpoint_at else None,
                task.checkpoint_count,
                json.dumps(task.workspaces),
                str(task.task_folder),
                task.created.isoformat(),
                task.updated.isoformat(),
                task.closed_at.isoformat() if task.closed_at else None,
            ),
        )
        self._conn.commit()

    def get_task(self, slug: str, space: str) -> Task | None:
        """Get a task by slug and space, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE slug = ? AND space = ?",
            (slug, space),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by ID, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def list_tasks(self, space: str | None = None) -> list[Task]:
        """List tasks. If space is None, list across all spaces."""
        if space is not None:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE space = ? ORDER BY updated DESC",
                (space,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY updated DESC"
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def update_task(self, task_id: str, **fields: object) -> None:
        """Update specific fields on a task."""
        if not fields:
            return
        allowed = {
            "summary", "last_milestone", "last_checkpoint_at",
            "checkpoint_count", "updated", "closed_at",
        }
        bad_keys = set(fields.keys()) - allowed
        if bad_keys:
            raise StoreError(f"Cannot update task fields: {bad_keys}")
        parts = []
        values = []
        for key, val in fields.items():
            parts.append(f"{key} = ?")
            if isinstance(val, datetime):
                values.append(val.isoformat())
            else:
                values.append(val)
        values.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(parts)} WHERE task_id = ?"
        self._conn.execute(sql, values)
        self._conn.commit()

    def slug_exists(self, slug: str, space: str) -> bool:
        """Check if a slug exists in a space."""
        row = self._conn.execute(
            "SELECT 1 FROM tasks WHERE slug = ? AND space = ?",
            (slug, space),
        ).fetchone()
        return row is not None

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            slug=row["slug"],
            title=row["title"],
            space=row["space"],
            summary=row["summary"],
            last_milestone=row["last_milestone"],
            last_checkpoint_at=(
                datetime.fromisoformat(row["last_checkpoint_at"])
                if row["last_checkpoint_at"]
                else None
            ),
            checkpoint_count=row["checkpoint_count"],
            workspaces=json.loads(row["workspaces"]),
            task_folder=Path(row["task_folder"]),
            created=datetime.fromisoformat(row["created"]),
            updated=datetime.fromisoformat(row["updated"]),
            closed_at=(
                datetime.fromisoformat(row["closed_at"])
                if row["closed_at"]
                else None
            ),
        )
