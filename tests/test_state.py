"""Tests for state registry module."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from dev_workflow.exceptions import TaskNotFoundError
from dev_workflow.models import Stage, Task
from dev_workflow.state import StateManager, _task_to_dict


def _make_task(
    slug: str = "csv-export",
    title: str = "User data CSV export",
    stage: Stage = Stage.SPEC,
    summary: str = "",
    created: datetime | None = None,
    updated: datetime | None = None,
    space: str = "",
) -> Task:
    """Helper to build a Task for tests."""
    now = datetime.now(timezone.utc)
    created = created or now
    updated = updated or now
    return Task(
        task_id=f"2026-04-08-{slug}",
        slug=slug,
        title=title,
        summary=summary,
        stage=stage,
        workspaces=[Path("~/workspace/my-api")],
        task_folder=Path(f"~/.dev-workflow/tasks/2026-04-08-{slug}/"),
        created=created,
        updated=updated,
        space=space,
    )


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        task = _make_task()
        mgr.save(task)
        loaded = mgr.load("csv-export")

        assert loaded.task_id == task.task_id
        assert loaded.slug == task.slug
        assert loaded.title == task.title
        assert loaded.summary == task.summary
        assert loaded.stage == task.stage
        assert [str(w) for w in loaded.workspaces] == [str(w) for w in task.workspaces]
        assert str(loaded.task_folder) == str(task.task_folder)
        # Datetimes lose sub-second precision through strftime %S
        assert loaded.created.replace(microsecond=0) == task.created.replace(microsecond=0)
        assert loaded.updated.replace(microsecond=0) == task.updated.replace(microsecond=0)

    def test_load_nonexistent_raises(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        with pytest.raises(TaskNotFoundError):
            mgr.load("no-such-task")

    def test_json_file_written(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task())
        json_path = tmp_path / "state" / "csv-export.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["slug"] == "csv-export"
        assert data["stage"] == "spec"
        assert data["progress"] == "0/0 subtasks"


class TestListAll:
    def test_multiple_tasks_sorted_by_updated_desc(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        now = datetime.now(timezone.utc)

        t1 = _make_task(slug="oldest", title="Oldest", updated=now - timedelta(hours=3))
        t2 = _make_task(slug="newest", title="Newest", updated=now)
        t3 = _make_task(slug="middle", title="Middle", updated=now - timedelta(hours=1))

        mgr.save(t1)
        mgr.save(t2)
        mgr.save(t3)

        tasks = mgr.list_all()
        slugs = [t.slug for t in tasks]
        assert slugs == ["newest", "middle", "oldest"]

    def test_empty_state_dir(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        assert mgr.list_all() == []

    def test_stage_filter(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="spec-task", stage=Stage.SPEC))
        mgr.save(_make_task(slug="plan-task", stage=Stage.PLAN))
        mgr.save(_make_task(slug="exec-task", stage=Stage.EXECUTION))

        spec_tasks = mgr.list_all(stage_filter=Stage.SPEC)
        assert len(spec_tasks) == 1
        assert spec_tasks[0].slug == "spec-task"

        plan_tasks = mgr.list_all(stage_filter=Stage.PLAN)
        assert len(plan_tasks) == 1
        assert plan_tasks[0].slug == "plan-task"

        complete_tasks = mgr.list_all(stage_filter=Stage.COMPLETE)
        assert len(complete_tasks) == 0


class TestSearch:
    def test_search_by_slug(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="csv-export", title="CSV Export"))
        mgr.save(_make_task(slug="auth-fix", title="Auth Fix"))

        results = mgr.search("csv")
        assert len(results) == 1
        assert results[0].slug == "csv-export"

    def test_search_by_title(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="task-one", title="User data CSV export"))
        mgr.save(_make_task(slug="task-two", title="Auth module refactor"))

        results = mgr.search("CSV")
        assert len(results) == 1
        assert results[0].slug == "task-one"

    def test_search_by_summary(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="task-a", title="Title A", summary="Handles pagination"))
        mgr.save(_make_task(slug="task-b", title="Title B", summary="Handles caching"))

        results = mgr.search("pagination")
        assert len(results) == 1
        assert results[0].slug == "task-a"

    def test_search_case_insensitive(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task", title="FooBar Feature"))

        assert len(mgr.search("foobar")) == 1
        assert len(mgr.search("FOOBAR")) == 1

    def test_search_no_results(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="task-one", title="Some Title"))
        assert mgr.search("nonexistent") == []


class TestUpdate:
    def test_update_stage(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task", stage=Stage.SPEC))

        updated = mgr.update("my-task", stage=Stage.PLAN)
        assert updated.stage == Stage.PLAN

        reloaded = mgr.load("my-task")
        assert reloaded.stage == Stage.PLAN

    def test_update_summary(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task", summary=""))

        updated = mgr.update("my-task", summary="Now with a summary")
        assert updated.summary == "Now with a summary"
        assert mgr.load("my-task").summary == "Now with a summary"

    def test_update_bumps_updated_timestamp(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mgr.save(_make_task(slug="my-task", updated=old_time))

        updated = mgr.update("my-task", summary="changed")
        assert updated.updated > old_time

    def test_update_nonexistent_raises(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        with pytest.raises(TaskNotFoundError):
            mgr.update("ghost", summary="nope")


class TestExists:
    def test_exists_true(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="present"))
        assert mgr.exists("present") is True

    def test_exists_false(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        assert mgr.exists("absent") is False


class TestAllSlugs:
    def test_returns_slug_strings(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="alpha"))
        mgr.save(_make_task(slug="beta"))
        mgr.save(_make_task(slug="gamma"))

        slugs = sorted(mgr.all_slugs())
        assert slugs == ["alpha", "beta", "gamma"]

    def test_empty_when_no_tasks(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        assert mgr.all_slugs() == []


class TestDelete:
    def test_delete_removes_file(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="doomed"))
        assert mgr.exists("doomed") is True

        mgr.delete("doomed")
        assert mgr.exists("doomed") is False

    def test_delete_nonexistent_raises(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        with pytest.raises(TaskNotFoundError):
            mgr.delete("ghost")


class TestProgressField:
    def test_default_progress_in_json(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task"))

        raw = json.loads((tmp_path / "state" / "my-task.json").read_text())
        assert raw["progress"] == "0/0 subtasks"

    def test_progress_preserved_through_update(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task"))

        # Update progress via extra field
        mgr.update("my-task", progress="3/6 subtasks")

        raw = json.loads((tmp_path / "state" / "my-task.json").read_text())
        assert raw["progress"] == "3/6 subtasks"

    def test_progress_survives_dataclass_field_update(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task"))

        # First set progress
        mgr.update("my-task", progress="2/5 subtasks")
        # Then update a dataclass field -- progress should survive
        mgr.update("my-task", stage=Stage.EXECUTION)

        raw = json.loads((tmp_path / "state" / "my-task.json").read_text())
        assert raw["progress"] == "2/5 subtasks"
        assert raw["stage"] == "execution"


class TestSpaceField:
    def test_space_round_trip(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        task = _make_task(slug="my-task", space="personal")
        mgr.save(task)
        loaded = mgr.load("my-task")
        assert loaded.space == "personal"

    def test_space_in_json(self, tmp_path: Path):
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="my-task", space="default"))
        raw = json.loads((tmp_path / "state" / "my-task.json").read_text())
        assert raw["space"] == "default"

    def test_missing_space_defaults_empty(self, tmp_path: Path):
        """Backward compat: old JSON without space field loads with space=''."""
        mgr = StateManager(tmp_path / "state")
        mgr.save(_make_task(slug="old-task"))
        # Manually strip space from JSON
        path = tmp_path / "state" / "old-task.json"
        data = json.loads(path.read_text())
        del data["space"]
        path.write_text(json.dumps(data))
        loaded = mgr.load("old-task")
        assert loaded.space == ""
