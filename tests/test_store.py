"""Tests for the SQLite store."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_workflow.errors import SpaceNotEmptyError, SpaceNotFoundError
from dev_workflow.models import Space, Task
from dev_workflow.store import Store


def _make_task(
    task_id: str = "test-id-1",
    slug: str = "test-task",
    title: str = "Test Task",
    space: str = "default",
    task_folder: str = "/tmp/test-task",
) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        task_id=task_id,
        slug=slug,
        title=title,
        space=space,
        summary="",
        last_milestone="",
        last_checkpoint_at=None,
        checkpoint_count=0,
        workspaces=[],
        task_folder=Path(task_folder),
        created=now,
        updated=now,
        closed_at=None,
    )


class TestStoreInit:
    def test_creates_database_file(self, tmp_base_dir):
        db_path = tmp_base_dir / "store.db"
        store = Store(db_path)
        assert db_path.exists()
        store.close()

    def test_creates_parent_directories(self, tmp_path):
        db_path = tmp_path / "deep" / "nested" / "store.db"
        store = Store(db_path)
        assert db_path.exists()
        store.close()

    def test_creates_all_tables(self, store):
        conn = sqlite3.connect(store._db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        # Filter out sqlite_sequence (auto-created by AUTOINCREMENT)
        tables = sorted(
            row[0] for row in cursor.fetchall() if row[0] != "sqlite_sequence"
        )
        conn.close()
        assert tables == [
            "artifacts",
            "checkpoints",
            "decisions",
            "schema_version",
            "spaces",
            "tasks",
            "verifications",
        ]

    def test_schema_version_set(self, store):
        conn = sqlite3.connect(store._db_path)
        cursor = conn.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()[0]
        conn.close()
        assert version == 1

    def test_wal_mode_enabled(self, store):
        conn = sqlite3.connect(store._db_path)
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_reopen_existing_db(self, tmp_base_dir):
        db_path = tmp_base_dir / "store.db"
        store1 = Store(db_path)
        store1.close()
        store2 = Store(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()[0]
        conn.close()
        store2.close()
        assert version == 1


class TestStoreSpaces:
    def test_create_and_get_space(self, store):
        store.create_space("personal", "Side projects")
        space = store.get_space("personal")
        assert space is not None
        assert space.name == "personal"
        assert space.description == "Side projects"

    def test_get_nonexistent_space_returns_none(self, store):
        assert store.get_space("nope") is None

    def test_list_spaces_empty(self, store):
        assert store.list_spaces() == []

    def test_list_spaces(self, store):
        store.create_space("a", "First")
        store.create_space("b", "Second")
        names = [s.name for s in store.list_spaces()]
        assert sorted(names) == ["a", "b"]

    def test_remove_space(self, store):
        store.create_space("temp", "Temporary")
        store.remove_space("temp")
        assert store.get_space("temp") is None

    @pytest.mark.skip("needs create_task from Task 7")
    def test_remove_space_with_tasks_raises(self, store):
        store.create_space("busy", "Has tasks")
        store.create_task(_make_task(slug="t1", space="busy", task_folder="/tmp/t1"))
        with pytest.raises(SpaceNotEmptyError):
            store.remove_space("busy")

    def test_ensure_space_creates_if_missing(self, store):
        store.ensure_space("auto")
        space = store.get_space("auto")
        assert space is not None
        assert space.name == "auto"

    def test_ensure_space_noop_if_exists(self, store):
        store.create_space("existing", "Already here")
        store.ensure_space("existing")
        space = store.get_space("existing")
        assert space.description == "Already here"

    def test_create_duplicate_space_raises(self, store):
        store.create_space("dup", "First")
        with pytest.raises(Exception):
            store.create_space("dup", "Second")
