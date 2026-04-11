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
