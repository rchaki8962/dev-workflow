"""Tests for the SQLite store."""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_workflow.errors import SpaceNotEmptyError, SpaceNotFoundError, TaskNotFoundError
from dev_workflow.models import Artifact, Checkpoint, Decision, Space, Task, Verification
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


def _make_checkpoint(
    task_id: str = "test-id-1",
    checkpoint_number: int = 1,
    milestone: str = "test-milestone",
) -> Checkpoint:
    return Checkpoint(
        id=None,
        task_id=task_id,
        checkpoint_number=checkpoint_number,
        milestone=milestone,
        summary="Test summary",
        user_directives=["Do it fast"],
        insights=["Interesting finding"],
        next_steps=["Next thing"],
        open_questions=["Open q?"],
        resolved_questions=["Resolved q"],
        created=datetime.now(timezone.utc),
    )


def _make_decision(
    task_id: str = "test-id-1",
    decision_number: int = 1,
) -> Decision:
    return Decision(
        id=None,
        task_id=task_id,
        checkpoint_id=None,
        decision_number=decision_number,
        title="Use JWT",
        rationale="Stateless",
        alternatives=["sessions", "oauth"],
        context="User wants scaling",
        created=datetime.now(timezone.utc),
    )


def _make_artifact(
    task_id: str = "test-id-1",
    name: str = "test-spec",
    version: int = 1,
    content: str = "# Spec\nContent here",
) -> Artifact:
    return Artifact(
        id=None,
        task_id=task_id,
        checkpoint_id=None,
        type="spec",
        name=name,
        version=version,
        description="Test spec",
        content=content,
        checksum=hashlib.sha256(content.encode()).hexdigest(),
        created=datetime.now(timezone.utc),
    )


def _make_verification(task_id: str = "test-id-1") -> Verification:
    return Verification(
        id=None,
        task_id=task_id,
        checkpoint_id=None,
        type="test-run",
        result="pass",
        detail="42/42 tests",
        command="pytest -v",
        created=datetime.now(timezone.utc),
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

    def test_remove_nonexistent_space_raises(self, store):
        with pytest.raises(SpaceNotFoundError):
            store.remove_space("nonexistent")


class TestStoreTasks:
    def test_create_and_get_task(self, store):
        store.ensure_space("default")
        task = _make_task()
        store.create_task(task)
        found = store.get_task("test-task", "default")
        assert found is not None
        assert found.task_id == "test-id-1"
        assert found.title == "Test Task"
        assert found.workspaces == []

    def test_get_task_not_found(self, store):
        store.ensure_space("default")
        assert store.get_task("nope", "default") is None

    def test_get_task_by_id(self, store):
        store.ensure_space("default")
        store.create_task(_make_task())
        found = store.get_task_by_id("test-id-1")
        assert found is not None
        assert found.slug == "test-task"

    def test_list_tasks_in_space(self, store):
        store.ensure_space("default")
        store.create_task(_make_task(task_id="id1", slug="t1", task_folder="/tmp/t1"))
        store.create_task(_make_task(task_id="id2", slug="t2", task_folder="/tmp/t2"))
        tasks = store.list_tasks(space="default")
        assert len(tasks) == 2

    def test_list_tasks_all_spaces(self, store):
        store.ensure_space("a")
        store.ensure_space("b")
        store.create_task(_make_task(task_id="id1", slug="t1", space="a", task_folder="/tmp/t1"))
        store.create_task(_make_task(task_id="id2", slug="t2", space="b", task_folder="/tmp/t2"))
        tasks = store.list_tasks(space=None)
        assert len(tasks) == 2

    def test_update_task(self, store):
        store.ensure_space("default")
        store.create_task(_make_task())
        store.update_task("test-id-1", summary="Updated", last_milestone="done")
        task = store.get_task_by_id("test-id-1")
        assert task.summary == "Updated"
        assert task.last_milestone == "done"

    def test_slug_exists(self, store):
        store.ensure_space("default")
        store.create_task(_make_task())
        assert store.slug_exists("test-task", "default") is True
        assert store.slug_exists("nope", "default") is False

    def test_same_slug_different_spaces(self, store):
        store.ensure_space("a")
        store.ensure_space("b")
        store.create_task(_make_task(task_id="id1", slug="shared", space="a", task_folder="/tmp/a"))
        store.create_task(_make_task(task_id="id2", slug="shared", space="b", task_folder="/tmp/b"))
        assert store.get_task("shared", "a").task_id == "id1"
        assert store.get_task("shared", "b").task_id == "id2"

    def test_update_nonexistent_task_raises(self, store):
        with pytest.raises(TaskNotFoundError):
            store.update_task("nonexistent-id", summary="nope")


class TestStoreCheckpointSave:
    def _setup_task(self, store):
        store.ensure_space("default")
        store.create_task(_make_task())

    def test_save_minimal_checkpoint(self, store):
        self._setup_task(store)
        cp = _make_checkpoint()
        num = store.save_checkpoint(cp, [], [], [])
        assert num == 1

    def test_save_updates_task_record(self, store):
        self._setup_task(store)
        cp = _make_checkpoint()
        store.save_checkpoint(cp, [], [], [])
        task = store.get_task_by_id("test-id-1")
        assert task.checkpoint_count == 1
        assert task.last_milestone == "test-milestone"
        assert task.summary == "Test summary"
        assert task.last_checkpoint_at is not None

    def test_save_with_decisions(self, store):
        self._setup_task(store)
        cp = _make_checkpoint()
        d = _make_decision()
        store.save_checkpoint(cp, [d], [], [])
        decisions = store.get_decisions("test-id-1")
        assert len(decisions) == 1
        assert decisions[0].title == "Use JWT"
        assert decisions[0].alternatives == ["sessions", "oauth"]

    def test_save_with_artifacts(self, store):
        self._setup_task(store)
        cp = _make_checkpoint()
        a = _make_artifact()
        store.save_checkpoint(cp, [], [a], [])
        artifacts = store.get_artifacts("test-id-1")
        assert len(artifacts) == 1
        assert artifacts[0].name == "test-spec"
        assert artifacts[0].version == 1

    def test_save_with_verifications(self, store):
        self._setup_task(store)
        cp = _make_checkpoint()
        v = _make_verification()
        store.save_checkpoint(cp, [], [], [v])
        verifs = store.get_verifications("test-id-1")
        assert len(verifs) == 1
        assert verifs[0].result == "pass"

    def test_artifact_dedup_same_checksum_skips(self, store):
        self._setup_task(store)
        content = "# Same content"
        a1 = _make_artifact(content=content, version=1)
        cp1 = _make_checkpoint(checkpoint_number=1)
        store.save_checkpoint(cp1, [], [a1], [])

        a2 = _make_artifact(content=content, version=2)
        cp2 = _make_checkpoint(checkpoint_number=2)
        store.save_checkpoint(cp2, [], [a2], [])

        artifacts = store.get_artifacts("test-id-1")
        assert len(artifacts) == 1  # Deduped: only v1 stored

    def test_artifact_dedup_different_checksum_inserts(self, store):
        self._setup_task(store)
        a1 = _make_artifact(content="Version 1", version=1)
        cp1 = _make_checkpoint(checkpoint_number=1)
        store.save_checkpoint(cp1, [], [a1], [])

        a2 = _make_artifact(content="Version 2", version=2)
        cp2 = _make_checkpoint(checkpoint_number=2)
        store.save_checkpoint(cp2, [], [a2], [])

        artifacts = store.get_artifacts("test-id-1")
        assert len(artifacts) == 2

    def test_multiple_checkpoints_increment(self, store):
        self._setup_task(store)
        store.save_checkpoint(_make_checkpoint(checkpoint_number=1), [], [], [])
        store.save_checkpoint(
            _make_checkpoint(checkpoint_number=2, milestone="second"), [], [], []
        )
        task = store.get_task_by_id("test-id-1")
        assert task.checkpoint_count == 2
        assert task.last_milestone == "second"

    def test_atomic_rollback_on_failure(self, store):
        self._setup_task(store)
        cp = _make_checkpoint()
        a1 = _make_artifact(content="original", version=1)
        store.save_checkpoint(cp, [], [a1], [])

        # Now try a checkpoint with a duplicate unique constraint violation
        cp_dup = _make_checkpoint(checkpoint_number=1)
        with pytest.raises(Exception):
            store.save_checkpoint(cp_dup, [], [], [])

        # Original data should be intact
        task = store.get_task_by_id("test-id-1")
        assert task.checkpoint_count == 1


class TestStoreReads:
    def _setup_full_checkpoint(self, store):
        """Create a task with one checkpoint containing all record types."""
        store.ensure_space("default")
        store.create_task(_make_task())
        cp = _make_checkpoint()
        d = _make_decision()
        a = _make_artifact()
        v = _make_verification()
        store.save_checkpoint(cp, [d], [a], [v])

    def test_get_checkpoints(self, store):
        self._setup_full_checkpoint(store)
        cps = store.get_checkpoints("test-id-1")
        assert len(cps) == 1
        assert cps[0].milestone == "test-milestone"
        assert cps[0].user_directives == ["Do it fast"]
        assert cps[0].insights == ["Interesting finding"]

    def test_get_decisions(self, store):
        self._setup_full_checkpoint(store)
        ds = store.get_decisions("test-id-1")
        assert len(ds) == 1
        assert ds[0].decision_number == 1
        assert ds[0].checkpoint_id is not None

    def test_get_artifact_latest(self, store):
        self._setup_full_checkpoint(store)
        a = store.get_artifact_latest("test-id-1", "test-spec")
        assert a is not None
        assert a.version == 1
        assert a.content == "# Spec\nContent here"

    def test_get_artifact_latest_not_found(self, store):
        self._setup_full_checkpoint(store)
        assert store.get_artifact_latest("test-id-1", "nonexistent") is None

    def test_get_next_decision_number(self, store):
        self._setup_full_checkpoint(store)
        assert store.get_next_decision_number("test-id-1") == 2

    def test_get_next_decision_number_empty(self, store):
        store.ensure_space("default")
        store.create_task(_make_task())
        assert store.get_next_decision_number("test-id-1") == 1

    def test_get_next_checkpoint_number(self, store):
        self._setup_full_checkpoint(store)
        assert store.get_next_checkpoint_number("test-id-1") == 2

    def test_get_next_checkpoint_number_empty(self, store):
        store.ensure_space("default")
        store.create_task(_make_task())
        assert store.get_next_checkpoint_number("test-id-1") == 1

    def test_get_verifications(self, store):
        self._setup_full_checkpoint(store)
        vs = store.get_verifications("test-id-1")
        assert len(vs) == 1
        assert vs[0].command == "pytest -v"
