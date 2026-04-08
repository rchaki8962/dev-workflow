"""Tests for dev_workflow.cli — Click CLI wiring layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dev_workflow.cli import main
from dev_workflow.config import Config
from dev_workflow.models import Stage
from dev_workflow.store import FileTaskStore
from dev_workflow.task import TaskManager
from dev_workflow.stage import StageManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def base_dir(tmp_path):
    """Provide a temporary base directory and return its string path."""
    return str(tmp_path)


def invoke(runner: CliRunner, args: list[str], base_dir: str) -> object:
    """Invoke the CLI with --base-dir prepended."""
    return runner.invoke(main, ["--base-dir", base_dir] + args)


def _create_task_via_manager(base_dir: str, title: str = "Test task", slug: str | None = None, prompt: str | None = None) -> object:
    """Create a task through the manager (not CLI) for setup purposes."""
    base = Path(base_dir)
    config = Config(base_dir=base)
    config._active_space = "harness"
    # Create the space directory structure
    (base / "harness" / "state").mkdir(parents=True, exist_ok=True)
    (base / "harness" / "tasks").mkdir(parents=True, exist_ok=True)
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)
    return manager.create_task(title=title, workspaces=[base], slug_override=slug, prompt=prompt)


def _get_store_and_config(base_dir: str) -> tuple[FileTaskStore, Config]:
    """Helper to get store and config for a base directory with space setup."""
    base = Path(base_dir)
    config = Config(base_dir=base)
    config._active_space = "harness"
    # Create the space directory structure if it doesn't exist
    (base / "harness" / "state").mkdir(parents=True, exist_ok=True)
    (base / "harness" / "tasks").mkdir(parents=True, exist_ok=True)
    store = FileTaskStore(config.space_dir)
    return store, config


# ---------------------------------------------------------------------------
# main group
# ---------------------------------------------------------------------------


class TestMainGroup:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "dev-workflow" in result.output

    def test_base_dir_option(self, runner, base_dir):
        result = invoke(runner, ["task", "list"], base_dir)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# task start
# ---------------------------------------------------------------------------


class TestTaskStart:
    def test_creates_task_table(self, runner, base_dir):
        result = invoke(runner, ["task", "start", "My new task"], base_dir)
        assert result.exit_code == 0
        assert "My new task" in result.output
        assert "Task:" in result.output
        assert "Slug:" in result.output

    def test_creates_task_json(self, runner, base_dir):
        result = invoke(runner, ["task", "start", "My new task", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "My new task"
        assert data["stage"] == "spec"
        assert "task_id" in data
        assert "slug" in data

    def test_with_slug_override(self, runner, base_dir):
        result = invoke(runner, ["task", "start", "My task", "--slug", "custom-slug", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "custom-slug"

    def test_with_prompt(self, runner, base_dir):
        result = invoke(runner, ["task", "start", "My task", "--prompt", "Build a CSV exporter", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Verify prompt was written to disk
        task_folder = Path(data["task_folder"])
        prompt_path = task_folder / "01-original-prompt.md"
        assert prompt_path.exists()
        assert prompt_path.read_text() == "Build a CSV exporter"

    def test_with_prompt_file(self, runner, base_dir, tmp_path):
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Content from file")
        result = invoke(runner, ["task", "start", "My task", "--prompt-file", str(prompt_file), "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        task_folder = Path(data["task_folder"])
        prompt_path = task_folder / "01-original-prompt.md"
        assert prompt_path.read_text() == "Content from file"

    def test_with_workspace(self, runner, base_dir, tmp_path):
        ws = str(tmp_path / "my-workspace")
        result = invoke(runner, ["task", "start", "My task", "--workspace", ws, "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert ws in data["workspaces"]

    def test_creates_folder_structure(self, runner, base_dir):
        result = invoke(runner, ["task", "start", "My task", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        task_folder = Path(data["task_folder"])
        assert task_folder.exists()
        assert (task_folder / "10-spec").is_dir()
        assert (task_folder / "20-plan").is_dir()
        assert (task_folder / "30-execution").is_dir()
        assert (task_folder / "90-logs").is_dir()

    def test_json_output_has_iso_dates(self, runner, base_dir):
        result = invoke(runner, ["task", "start", "My task", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        # ISO datetime strings should contain 'T'
        assert "T" in data["created"]
        assert "T" in data["updated"]


# ---------------------------------------------------------------------------
# task list
# ---------------------------------------------------------------------------


class TestTaskList:
    def test_empty_list(self, runner, base_dir):
        result = invoke(runner, ["task", "list"], base_dir)
        assert result.exit_code == 0
        assert "No tasks found" in result.output

    def test_list_shows_tasks(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Alpha task", slug="alpha")
        _create_task_via_manager(base_dir, "Beta task", slug="beta")

        result = invoke(runner, ["task", "list"], base_dir)
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_list_json(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Alpha task", slug="alpha")

        result = invoke(runner, ["task", "list", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["slug"] == "alpha"

    def test_list_with_stage_filter(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Alpha task", slug="alpha")
        _create_task_via_manager(base_dir, "Beta task", slug="beta")

        # All tasks are in spec stage
        result = invoke(runner, ["task", "list", "--stage", "spec", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2

        result = invoke(runner, ["task", "list", "--stage", "plan", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 0


# ---------------------------------------------------------------------------
# task search
# ---------------------------------------------------------------------------


class TestTaskSearch:
    def test_search_finds_match(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Build CSV export", slug="csv")
        _create_task_via_manager(base_dir, "Fix auth bug", slug="auth")

        result = invoke(runner, ["task", "search", "CSV"], base_dir)
        assert result.exit_code == 0
        assert "csv" in result.output

    def test_search_no_match(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Build CSV export", slug="csv")

        result = invoke(runner, ["task", "search", "nonexistent"], base_dir)
        assert result.exit_code == 0
        assert "No tasks found" in result.output

    def test_search_json(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Build CSV export", slug="csv")

        result = invoke(runner, ["task", "search", "CSV", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["slug"] == "csv"


# ---------------------------------------------------------------------------
# task switch
# ---------------------------------------------------------------------------


class TestTaskSwitch:
    def test_switch_prints_context(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Build CSV export", slug="csv")

        result = invoke(runner, ["task", "switch", "csv"], base_dir)
        assert result.exit_code == 0
        assert "Progress" in result.output

    def test_switch_unknown_slug(self, runner, base_dir):
        result = invoke(runner, ["task", "switch", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# task info
# ---------------------------------------------------------------------------


class TestTaskInfo:
    def test_info_table(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Build CSV export", slug="csv")

        result = invoke(runner, ["task", "info", "csv"], base_dir)
        assert result.exit_code == 0
        assert "Build CSV export" in result.output
        assert "csv" in result.output

    def test_info_json(self, runner, base_dir):
        _create_task_via_manager(base_dir, "Build CSV export", slug="csv")

        result = invoke(runner, ["task", "info", "csv", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "csv"
        assert data["title"] == "Build CSV export"

    def test_info_unknown_slug(self, runner, base_dir):
        result = invoke(runner, ["task", "info", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# stage setup
# ---------------------------------------------------------------------------


class TestStageSetup:
    def test_spec_setup_table(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        result = invoke(runner, ["stage", "setup", "spec", "--task", "my-task"], base_dir)
        assert result.exit_code == 0
        assert "spec" in result.output
        assert "my-task" in result.output

    def test_spec_setup_json(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        result = invoke(runner, ["stage", "setup", "spec", "--task", "my-task", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "output_path" in data
        assert "version" in data
        assert data["version"] == 1

    def test_plan_setup_prerequisite_error(self, runner, base_dir):
        """Plan setup without approved spec should fail with a friendly message."""
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        result = invoke(runner, ["stage", "setup", "plan", "--task", "my-task"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output
        assert "prerequisite" in result.output.lower() or "spec" in result.output.lower()

    def test_execution_setup_prerequisite_error(self, runner, base_dir):
        """Execution setup without approved plan should fail with a friendly message."""
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        result = invoke(runner, ["stage", "setup", "execution", "--task", "my-task"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_unknown_task_error(self, runner, base_dir):
        result = invoke(runner, ["stage", "setup", "spec", "--task", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_spec_setup_empty_prompt_error(self, runner, base_dir):
        """Spec setup with empty prompt should fail."""
        _create_task_via_manager(base_dir, "My task", slug="my-task")

        result = invoke(runner, ["stage", "setup", "spec", "--task", "my-task"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_missing_task_option(self, runner, base_dir):
        """--task is required."""
        result = invoke(runner, ["stage", "setup", "spec"], base_dir)
        assert result.exit_code != 0

    def test_invalid_stage_name(self, runner, base_dir):
        """Invalid stage name should be rejected by Click's Choice."""
        result = invoke(runner, ["stage", "setup", "invalid", "--task", "my-task"], base_dir)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# stage teardown
# ---------------------------------------------------------------------------


class TestStageTeardown:
    def test_teardown_after_setup(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        # Setup spec first
        invoke(runner, ["stage", "setup", "spec", "--task", "my-task"], base_dir)

        # Create a spec draft so teardown has something to process
        store, config = _get_store_and_config(base_dir)
        task = store.load_task("my-task")
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        (spec_dir / "spec-v1.md").write_text("# Spec: My task\n\n## Overview\nSomething.\n")

        result = invoke(runner, ["stage", "teardown", "spec", "--task", "my-task"], base_dir)
        assert result.exit_code == 0
        assert "teardown complete" in result.output.lower()

    def test_teardown_unknown_task(self, runner, base_dir):
        result = invoke(runner, ["stage", "teardown", "spec", "--task", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# stage status
# ---------------------------------------------------------------------------


class TestStageStatus:
    def test_status_table(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task")

        result = invoke(runner, ["stage", "status", "--task", "my-task"], base_dir)
        assert result.exit_code == 0
        assert "spec" in result.output

    def test_status_json(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task")

        result = invoke(runner, ["stage", "status", "--task", "my-task", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "my-task"
        assert data["stage"] == "spec"

    def test_status_unknown_task(self, runner, base_dir):
        result = invoke(runner, ["stage", "status", "--task", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# review setup
# ---------------------------------------------------------------------------


class TestReviewSetup:
    def test_review_setup_after_spec_draft(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        # Create a spec draft
        store, config = _get_store_and_config(base_dir)
        task = store.load_task("my-task")
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        (spec_dir / "spec-v1.md").write_text("# Spec: My task\n\n## Overview\nSomething.\n")

        result = invoke(runner, ["review", "setup", "spec", "--task", "my-task", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "review_file" in data
        assert "files_to_review" in data
        assert data["version"] == 1

    def test_review_setup_no_draft_error(self, runner, base_dir):
        """Review setup without a draft should fail."""
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        result = invoke(runner, ["review", "setup", "spec", "--task", "my-task"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_review_setup_unknown_task(self, runner, base_dir):
        result = invoke(runner, ["review", "setup", "spec", "--task", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# review approve
# ---------------------------------------------------------------------------


class TestReviewApprove:
    def test_approve_spec(self, runner, base_dir):
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        # Create a spec draft
        store, config = _get_store_and_config(base_dir)
        task = store.load_task("my-task")
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        (spec_dir / "spec-v1.md").write_text("# Spec: My task\n\n## Overview\nSomething.\n")

        result = invoke(runner, ["review", "approve", "spec", "--task", "my-task"], base_dir)
        assert result.exit_code == 0
        assert "approved" in result.output.lower()

        # Stage should have advanced to plan
        updated_task = store.load_task("my-task")
        assert updated_task.stage == Stage.PLAN

    def test_approve_advances_to_execution(self, runner, base_dir):
        """Approve plan to advance to execution stage."""
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        store, config = _get_store_and_config(base_dir)
        task = store.load_task("my-task")
        task_dir = config.tasks_dir / task.task_id

        # Approve spec first
        spec_dir = task_dir / "10-spec"
        (spec_dir / "spec-v1.md").write_text("# Spec: My task\n\n## Overview\nBuild it.\n")
        invoke(runner, ["review", "approve", "spec", "--task", "my-task"], base_dir)

        # Create plan draft
        plan_dir = task_dir / "20-plan"
        (plan_dir / "plan-v1.md").write_text(
            "# Implementation Plan: My task\n\n"
            "**Approved Spec**: 10-spec/spec-approved.md\n\n"
            "## Approach\nDo it step by step.\n\n"
            "## Tasks\n\n### Task 1: First step\nDo the first thing.\n"
        )

        result = invoke(runner, ["review", "approve", "plan", "--task", "my-task"], base_dir)
        assert result.exit_code == 0

        updated_task = store.load_task("my-task")
        assert updated_task.stage == Stage.EXECUTION

    def test_approve_no_draft_error(self, runner, base_dir):
        """Approve without a draft should fail."""
        _create_task_via_manager(base_dir, "My task", slug="my-task", prompt="Build something")

        result = invoke(runner, ["review", "approve", "spec", "--task", "my-task"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_approve_unknown_task(self, runner, base_dir):
        result = invoke(runner, ["review", "approve", "spec", "--task", "nonexistent"], base_dir)
        assert result.exit_code != 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# End-to-end workflow
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_create_list_info_workflow(self, runner, base_dir):
        """Create a task, list it, get info."""
        # Create
        result = invoke(runner, ["task", "start", "E2E test task", "--slug", "e2e", "--format", "json"], base_dir)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["slug"] == "e2e"

        # List
        result = invoke(runner, ["task", "list", "--format", "json"], base_dir)
        assert result.exit_code == 0
        tasks = json.loads(result.output)
        assert any(t["slug"] == "e2e" for t in tasks)

        # Info
        result = invoke(runner, ["task", "info", "e2e", "--format", "json"], base_dir)
        assert result.exit_code == 0
        info = json.loads(result.output)
        assert info["title"] == "E2E test task"

    def test_full_spec_cycle(self, runner, base_dir):
        """Create task -> stage setup spec -> teardown -> review -> approve."""
        # Create with prompt
        result = invoke(
            runner,
            ["task", "start", "Full cycle", "--slug", "cycle", "--prompt", "Build it all"],
            base_dir,
        )
        assert result.exit_code == 0

        # Stage setup spec
        result = invoke(
            runner,
            ["stage", "setup", "spec", "--task", "cycle", "--format", "json"],
            base_dir,
        )
        assert result.exit_code == 0
        setup_data = json.loads(result.output)
        output_path = setup_data["output_path"]

        # Write a spec draft (simulating agent work)
        Path(output_path).write_text("# Spec: Full cycle\n\n## Overview\nBuild everything.\n")

        # Teardown
        result = invoke(runner, ["stage", "teardown", "spec", "--task", "cycle"], base_dir)
        assert result.exit_code == 0

        # Review setup
        result = invoke(
            runner,
            ["review", "setup", "spec", "--task", "cycle", "--format", "json"],
            base_dir,
        )
        assert result.exit_code == 0

        # Approve
        result = invoke(runner, ["review", "approve", "spec", "--task", "cycle"], base_dir)
        assert result.exit_code == 0

        # Verify stage advanced
        result = invoke(runner, ["stage", "status", "--task", "cycle", "--format", "json"], base_dir)
        assert result.exit_code == 0
        status = json.loads(result.output)
        assert status["stage"] == "plan"


# ---------------------------------------------------------------------------
# space create
# ---------------------------------------------------------------------------


class TestSpaceCreate:
    def test_creates_space(self, runner, base_dir):
        result = invoke(runner, ["space", "create", "personal", "--description", "My stuff"], base_dir)
        assert result.exit_code == 0
        assert "personal" in result.output

    def test_rejects_invalid_name(self, runner, base_dir):
        result = invoke(runner, ["space", "create", "Invalid"], base_dir)
        assert result.exit_code == 1

    def test_rejects_duplicate(self, runner, base_dir):
        invoke(runner, ["space", "create", "personal"], base_dir)
        result = invoke(runner, ["space", "create", "personal"], base_dir)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# space list
# ---------------------------------------------------------------------------


class TestSpaceList:
    def test_lists_spaces(self, runner, base_dir):
        invoke(runner, ["space", "create", "alpha"], base_dir)
        invoke(runner, ["space", "create", "beta"], base_dir)
        result = invoke(runner, ["space", "list"], base_dir)
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_json_output(self, runner, base_dir):
        invoke(runner, ["space", "create", "test-space"], base_dir)
        result = invoke(runner, ["space", "list", "--format", "json"], base_dir)
        data = json.loads(result.output)
        assert any(s["name"] == "test-space" for s in data)


# ---------------------------------------------------------------------------
# space remove
# ---------------------------------------------------------------------------


class TestSpaceRemove:
    def test_removes_empty_space(self, runner, base_dir):
        invoke(runner, ["space", "create", "temp"], base_dir)
        result = invoke(runner, ["space", "remove", "temp"], base_dir)
        assert result.exit_code == 0

    def test_refuses_nonempty(self, runner, base_dir):
        invoke(runner, ["space", "create", "busy"], base_dir)
        invoke(runner, ["--space", "busy", "task", "start", "My Task", "--prompt", "test"], base_dir)
        result = invoke(runner, ["space", "remove", "busy"], base_dir)
        assert result.exit_code == 1

    def test_force_removes_nonempty(self, runner, base_dir):
        invoke(runner, ["space", "create", "busy"], base_dir)
        invoke(runner, ["--space", "busy", "task", "start", "My Task", "--prompt", "test"], base_dir)
        result = invoke(runner, ["space", "remove", "busy", "--force"], base_dir)
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# space info
# ---------------------------------------------------------------------------


class TestSpaceInfo:
    def test_info(self, runner, base_dir):
        invoke(runner, ["space", "create", "personal", "--description", "My stuff"], base_dir)
        result = invoke(runner, ["space", "info", "personal"], base_dir)
        assert result.exit_code == 0
        assert "personal" in result.output
        assert "My stuff" in result.output

    def test_nonexistent(self, runner, base_dir):
        result = invoke(runner, ["space", "info", "ghost"], base_dir)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# task list --all-spaces
# ---------------------------------------------------------------------------


class TestTaskListAllSpaces:
    def test_lists_across_spaces(self, runner, base_dir):
        invoke(runner, ["space", "create", "alpha"], base_dir)
        invoke(runner, ["space", "create", "beta"], base_dir)
        invoke(runner, ["--space", "alpha", "task", "start", "Alpha Task", "--prompt", "test"], base_dir)
        invoke(runner, ["--space", "beta", "task", "start", "Beta Task", "--prompt", "test"], base_dir)
        result = invoke(runner, ["task", "list", "--all-spaces"], base_dir)
        assert result.exit_code == 0
        assert "alpha" in result.output.lower()
        assert "beta" in result.output.lower()

    def test_json_includes_space(self, runner, base_dir):
        invoke(runner, ["space", "create", "alpha"], base_dir)
        invoke(runner, ["--space", "alpha", "task", "start", "Alpha Task", "--prompt", "test"], base_dir)
        result = invoke(runner, ["task", "list", "--all-spaces", "--format", "json"], base_dir)
        data = json.loads(result.output)
        assert len(data) >= 1
        assert data[0]["space"] == "alpha"
