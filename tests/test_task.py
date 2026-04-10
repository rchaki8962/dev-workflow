"""Tests for dev_workflow.task — TaskManager lifecycle operations."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from dev_workflow.config import Config
from dev_workflow.exceptions import TaskNotFoundError
from dev_workflow.models import Stage, Task
from dev_workflow.store import FileTaskStore
from dev_workflow.task import TaskManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def setup(tmp_path):
    config = Config(base_dir=tmp_path)
    config._active_space = "default"
    # Create the space directory structure so FileTaskStore works
    (tmp_path / "default" / "state").mkdir(parents=True)
    (tmp_path / "default" / "tasks").mkdir(parents=True)
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)
    return manager, config, store


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


class TestCreateTask:
    def test_creates_folder_structure(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task("Build CSV export", workspaces=[tmp_path])

        task_dir = config.tasks_dir / task.task_id
        assert task_dir.exists()
        assert (task_dir / "10-spec").is_dir()
        assert (task_dir / "20-plan").is_dir()
        assert (task_dir / "30-execution").is_dir()
        assert (task_dir / "90-logs").is_dir()

    def test_progress_file_exists_and_parseable(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task("Build CSV export", workspaces=[tmp_path])

        progress_path = config.tasks_dir / task.task_id / "00-progress.md"
        assert progress_path.exists()

        content = progress_path.read_text()
        assert "Build CSV export" in content
        assert task.task_id in content

    def test_original_prompt_exists_empty(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task("Build CSV export", workspaces=[tmp_path])

        prompt_path = config.tasks_dir / task.task_id / "01-original-prompt.md"
        assert prompt_path.exists()
        assert prompt_path.read_text() == ""

    def test_state_json_written(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task("Build CSV export", workspaces=[tmp_path])

        # Should be loadable from the store by slug
        loaded = store.load_task(task.slug)
        assert loaded.task_id == task.task_id
        assert loaded.title == "Build CSV export"

    def test_activity_log_has_created_entry(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task("Build CSV export", workspaces=[tmp_path])

        entries = store.load_activity_log(task.task_id)
        assert len(entries) == 1
        assert entries[0].action == "Task created"
        assert "Build CSV export" in entries[0].detail
        assert task.slug in entries[0].detail

    def test_task_defaults(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task("Build CSV export", workspaces=[tmp_path])

        assert task.stage == Stage.SPEC
        assert task.summary == ""
        assert task.task_folder == config.tasks_dir / task.task_id

    def test_with_prompt(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task(
            "Build CSV export",
            workspaces=[tmp_path],
            prompt="Please build a CSV export feature for users.",
        )

        prompt_path = config.tasks_dir / task.task_id / "01-original-prompt.md"
        assert prompt_path.read_text() == "Please build a CSV export feature for users."

    def test_with_prompt_file(self, setup, tmp_path):
        manager, config, store = setup

        prompt_file = tmp_path / "my-prompt.md"
        prompt_file.write_text("Content from a file.\nWith multiple lines.")

        task = manager.create_task(
            "Build CSV export",
            workspaces=[tmp_path],
            prompt_file=prompt_file,
        )

        prompt_path = config.tasks_dir / task.task_id / "01-original-prompt.md"
        assert prompt_path.read_text() == "Content from a file.\nWith multiple lines."

    def test_with_slug_override(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task(
            "Build CSV export",
            workspaces=[tmp_path],
            slug_override="my-custom-slug",
        )

        assert task.slug == "my-custom-slug"
        loaded = store.load_task("my-custom-slug")
        assert loaded.task_id == task.task_id

    def test_task_id_collision(self, setup, tmp_path):
        manager, config, store = setup

        # Patch datetime to force same date for both tasks
        fixed_now = datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)
        with patch("dev_workflow.task.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            task1 = manager.create_task(
                "Build CSV export",
                workspaces=[tmp_path],
                slug_override="csv1",
            )
            task2 = manager.create_task(
                "Build CSV export",
                workspaces=[tmp_path],
                slug_override="csv2",
            )

        assert task1.task_id != task2.task_id
        assert task2.task_id == f"{task1.task_id}-2"


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_list_returns_all(self, setup, tmp_path):
        manager, config, store = setup

        manager.create_task("Alpha task", workspaces=[tmp_path], slug_override="alpha")
        manager.create_task("Beta task", workspaces=[tmp_path], slug_override="beta")
        manager.create_task("Gamma task", workspaces=[tmp_path], slug_override="gamma")

        tasks = manager.list_tasks()
        slugs = {t.slug for t in tasks}
        assert len(tasks) == 3
        assert slugs == {"alpha", "beta", "gamma"}

    def test_list_with_stage_filter(self, setup, tmp_path):
        manager, config, store = setup

        task1 = manager.create_task("Alpha task", workspaces=[tmp_path], slug_override="alpha")
        task2 = manager.create_task("Beta task", workspaces=[tmp_path], slug_override="beta")

        # Manually update one task's stage to PLAN
        from dataclasses import replace

        updated = replace(task2, stage=Stage.PLAN, updated=datetime.now(timezone.utc))
        store.save_task(updated)

        spec_tasks = manager.list_tasks(stage_filter=Stage.SPEC)
        plan_tasks = manager.list_tasks(stage_filter=Stage.PLAN)

        assert len(spec_tasks) == 1
        assert spec_tasks[0].slug == "alpha"
        assert len(plan_tasks) == 1
        assert plan_tasks[0].slug == "beta"


# ---------------------------------------------------------------------------
# search_tasks
# ---------------------------------------------------------------------------


class TestSearchTasks:
    def test_search_finds_by_title(self, setup, tmp_path):
        manager, config, store = setup

        manager.create_task("Build CSV export", workspaces=[tmp_path], slug_override="csv")
        manager.create_task("Fix auth bug", workspaces=[tmp_path], slug_override="auth")

        results = manager.search_tasks("CSV")
        assert len(results) == 1
        assert results[0].slug == "csv"

    def test_search_no_results(self, setup, tmp_path):
        manager, config, store = setup

        manager.create_task("Build CSV export", workspaces=[tmp_path], slug_override="csv")

        results = manager.search_tasks("nonexistent")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# get_task_info
# ---------------------------------------------------------------------------


class TestGetTaskInfo:
    def test_returns_correct_task(self, setup, tmp_path):
        manager, config, store = setup

        created = manager.create_task(
            "Build CSV export", workspaces=[tmp_path], slug_override="csv"
        )

        task = manager.get_task_info("csv")
        assert task.task_id == created.task_id
        assert task.title == "Build CSV export"
        assert task.slug == "csv"

    def test_raises_for_unknown_slug(self, setup):
        manager, config, store = setup

        with pytest.raises(TaskNotFoundError):
            manager.get_task_info("nonexistent-slug")


# ---------------------------------------------------------------------------
# switch_task
# ---------------------------------------------------------------------------


class TestSwitchTask:
    def test_basic_returns_progress(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task(
            "Build CSV export", workspaces=[tmp_path], slug_override="csv"
        )

        context = manager.switch_task("csv")
        assert "## Progress" in context
        assert "Build CSV export" in context

    def test_with_spec_approved(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task(
            "Build CSV export", workspaces=[tmp_path], slug_override="csv"
        )

        # Write a spec-approved.md
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec-approved.md").write_text(
            "# Spec: CSV Export\n\n"
            "## Overview\nExport user data to CSV.\n\n"
            "## Requirements\n- Support RFC 4180\n- Handle large files\n"
        )

        context = manager.switch_task("csv")
        assert "## Spec Summary" in context
        assert "CSV Export" in context
        assert "Overview" in context

    def test_with_plan_approved(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task(
            "Build CSV export", workspaces=[tmp_path], slug_override="csv"
        )

        # Write a plan-approved.md
        plan_dir = config.tasks_dir / task.task_id / "20-plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "plan-approved.md").write_text(
            "# Implementation Plan: CSV Export\n\n"
            "## Tasks\n\n"
            "### Task 1: CSV Serializer\nBuild it.\n\n"
            "### Task 2: API Endpoint\nExpose it.\n"
        )

        context = manager.switch_task("csv")
        assert "## Plan Summary" in context
        assert "Task 1: CSV Serializer" in context
        assert "Task 2: API Endpoint" in context

    def test_with_all_sections(self, setup, tmp_path):
        manager, config, store = setup

        task = manager.create_task(
            "Build CSV export", workspaces=[tmp_path], slug_override="csv"
        )

        task_dir = config.tasks_dir / task.task_id

        # Write spec-approved.md
        (task_dir / "10-spec" / "spec-approved.md").write_text(
            "# Spec: CSV Export\n\n## Overview\nExport data.\n"
        )

        # Write plan-approved.md
        (task_dir / "20-plan" / "plan-approved.md").write_text(
            "# Plan: CSV Export\n\n## Task 1: Serializer\nDo it.\n"
        )

        context = manager.switch_task("csv")
        assert "## Progress" in context
        assert "## Spec Summary" in context
        assert "## Plan Summary" in context
        # Sections are separated by ---
        assert "---" in context

    def test_raises_for_unknown_slug(self, setup):
        manager, config, store = setup

        with pytest.raises(TaskNotFoundError):
            manager.switch_task("nonexistent-slug")


# ---------------------------------------------------------------------------
# space field
# ---------------------------------------------------------------------------


class TestCreateTaskSpace:
    def test_space_set_from_config(self, setup, tmp_path):
        manager, config, store = setup
        task = manager.create_task("Build CSV export", workspaces=[tmp_path])
        assert task.space == "default"

    def test_space_persisted_in_state(self, setup, tmp_path):
        manager, config, store = setup
        task = manager.create_task("Build CSV export", workspaces=[tmp_path])
        loaded = store.load_task(task.slug)
        assert loaded.space == "default"
