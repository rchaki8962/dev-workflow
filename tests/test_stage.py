"""Tests for dev_workflow.stage — StageManager lifecycle operations."""

from pathlib import Path

import pytest

from dev_workflow.config import Config
from dev_workflow.exceptions import PrerequisiteError
from dev_workflow.models import Stage, SubtaskStatus
from dev_workflow.stage import StageManager
from dev_workflow.store import FileTaskStore
from dev_workflow.task import TaskManager


# ---------------------------------------------------------------------------
# Canonical plan content used by execution-stage tests
# ---------------------------------------------------------------------------

PLAN_CONTENT = """\
# Implementation Plan: Test

**Approved Spec**: 10-spec/spec-approved.md

## Approach
Build it incrementally.

## Tasks

### Task 1: Setup project structure

**Description:**
Create the initial project layout.

**Verification:**
- [ ] Directory structure exists
- [ ] Config file is valid

**Dependencies:** None

### Task 2: Implement core logic

**Description:**
Build the main processing pipeline.

**Verification:**
- [ ] Unit tests pass
- [ ] Integration test passes

**Dependencies:** Task 1

## Risks
- Tight deadline
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path):
    config = Config(base_dir=tmp_path)
    config._active_space = "default"
    # Create the space directory structure
    (tmp_path / "default" / "state").mkdir(parents=True)
    (tmp_path / "default" / "tasks").mkdir(parents=True)
    store = FileTaskStore(config.space_dir)
    task_mgr = TaskManager(store, config)
    stage_mgr = StageManager(store, config)
    # Create a task with a non-empty prompt
    task = task_mgr.create_task("Test Task", prompt="Build something")
    return stage_mgr, task_mgr, store, config, task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approve_spec(config, task, content=None):
    """Write a spec draft and approved file for the given task."""
    spec_dir = config.tasks_dir / task.task_id / "10-spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    text = content or "# Spec: Test Title\n\n## Overview\nTest overview"
    (spec_dir / "spec-v1.md").write_text(text)
    (spec_dir / "spec-approved.md").write_text(text)


def _approve_plan(config, task, content=None):
    """Write a plan draft and approved file for the given task."""
    plan_dir = config.tasks_dir / task.task_id / "20-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    text = content or PLAN_CONTENT
    (plan_dir / "plan-v1.md").write_text(text)
    (plan_dir / "plan-approved.md").write_text(text)


# ---------------------------------------------------------------------------
# Spec setup
# ---------------------------------------------------------------------------


class TestSpecSetup:
    def test_returns_output_path_version_1(self, env):
        stage_mgr, task_mgr, store, config, task = env

        result = stage_mgr.setup(task.slug, "spec")

        assert result["version"] == 1
        assert "spec-v1.md" in result["output_path"]
        assert "01-original-prompt.md" in result["original_prompt_path"]

    def test_empty_prompt_raises(self, env):
        stage_mgr, task_mgr, store, config, task = env

        # Overwrite prompt with empty content
        prompt_path = config.tasks_dir / task.task_id / "01-original-prompt.md"
        prompt_path.write_text("")

        with pytest.raises(PrerequisiteError, match="non-empty"):
            stage_mgr.setup(task.slug, "spec")

    def test_version_detection(self, env):
        stage_mgr, task_mgr, store, config, task = env

        # Create an existing spec-v1.md
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec-v1.md").write_text("# Spec v1")

        result = stage_mgr.setup(task.slug, "spec")

        assert result["version"] == 2
        assert "spec-v2.md" in result["output_path"]


# ---------------------------------------------------------------------------
# Plan setup
# ---------------------------------------------------------------------------


class TestPlanSetup:
    def test_succeeds_with_approved_spec(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)

        result = stage_mgr.setup(task.slug, "plan")

        assert result["version"] == 1
        assert "plan-v1.md" in result["output_path"]
        assert "spec-approved.md" in result["approved_spec_path"]

    def test_without_approved_spec_raises(self, env):
        stage_mgr, task_mgr, store, config, task = env

        with pytest.raises(PrerequisiteError, match="spec-approved"):
            stage_mgr.setup(task.slug, "plan")


# ---------------------------------------------------------------------------
# Execution setup
# ---------------------------------------------------------------------------


class TestExecutionSetup:
    def test_creates_subtask_files_and_updates_progress(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)
        _approve_plan(config, task)

        result = stage_mgr.setup(task.slug, "execution")

        # Subtask files created
        assert len(result["subtask_files"]) == 2
        for sf in result["subtask_files"]:
            assert Path(sf).exists()

        # Progress updated with subtask index
        progress = store.load_progress(task.task_id)
        assert len(progress.subtask_index) == 2
        assert progress.subtask_index[0].title == "Setup project structure"
        assert progress.subtask_index[1].title == "Implement core logic"

    def test_idempotent(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)
        _approve_plan(config, task)

        result1 = stage_mgr.setup(task.slug, "execution")
        result2 = stage_mgr.setup(task.slug, "execution")

        # Same subtask files, no duplicates
        assert result1["subtask_files"] == result2["subtask_files"]

        exec_dir = config.tasks_dir / task.task_id / "30-execution"
        subtask_files = list(exec_dir.glob("subtask-*.md"))
        assert len(subtask_files) == 2

    def test_without_approved_plan_raises(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)
        # No plan approved

        with pytest.raises(PrerequisiteError, match="plan-approved"):
            stage_mgr.setup(task.slug, "execution")


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------


class TestTeardown:
    def test_spec_teardown_does_not_advance_stage(self, env):
        stage_mgr, task_mgr, store, config, task = env

        stage_mgr.teardown(task.slug, "spec")

        # Stage should still be spec (teardown does NOT advance)
        loaded = store.load_task(task.slug)
        assert loaded.stage == Stage.SPEC

    def test_execution_teardown_generates_summary(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)
        _approve_plan(config, task)
        stage_mgr.setup(task.slug, "execution")

        stage_mgr.teardown(task.slug, "execution")

        summary_path = (
            config.tasks_dir / task.task_id / "30-execution" / "implementation-summary.md"
        )
        assert summary_path.exists()
        content = summary_path.read_text()
        assert "Implementation Summary" in content
        assert "Setup project structure" in content


# ---------------------------------------------------------------------------
# Review setup
# ---------------------------------------------------------------------------


class TestReviewSetup:
    def test_creates_review_template(self, env):
        stage_mgr, task_mgr, store, config, task = env

        # Create a spec draft
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec-v1.md").write_text("# Spec: Test\n\n## Overview\nTest")

        result = stage_mgr.review_setup(task.slug, "spec")

        assert result["version"] == 1
        assert Path(result["review_file"]).exists()
        assert "spec-review-v1.md" in result["review_file"]

        # Files to review include progress, prompt, and draft
        assert any("00-progress.md" in f for f in result["files_to_review"])
        assert any("spec-v1.md" in f for f in result["files_to_review"])

    def test_without_draft_raises(self, env):
        stage_mgr, task_mgr, store, config, task = env

        with pytest.raises(PrerequisiteError, match="No spec draft"):
            stage_mgr.review_setup(task.slug, "spec")


# ---------------------------------------------------------------------------
# Review approve
# ---------------------------------------------------------------------------


class TestReviewApprove:
    def test_spec_approve_advances_to_plan(self, env):
        stage_mgr, task_mgr, store, config, task = env

        # Create spec draft
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        (spec_dir / "spec-v1.md").write_text(
            "# Spec: Test Title\n\n## Overview\nTest overview"
        )

        stage_mgr.review_approve(task.slug, "spec")

        # Draft copied to approved
        assert (spec_dir / "spec-approved.md").exists()
        assert (spec_dir / "spec-approved.md").read_text() == (
            spec_dir / "spec-v1.md"
        ).read_text()

        # Stage advanced to plan
        loaded = store.load_task(task.slug)
        assert loaded.stage == Stage.PLAN

    def test_plan_approve_advances_to_execution(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)

        # Create plan draft
        plan_dir = config.tasks_dir / task.task_id / "20-plan"
        (plan_dir / "plan-v1.md").write_text(PLAN_CONTENT)

        stage_mgr.review_approve(task.slug, "plan")

        # Stage advanced to execution
        loaded = store.load_task(task.slug)
        assert loaded.stage == Stage.EXECUTION

        # Plan approved file exists
        assert (plan_dir / "plan-approved.md").exists()

    def test_execution_approve_advances_to_complete(self, env):
        stage_mgr, task_mgr, store, config, task = env

        _approve_spec(config, task)
        _approve_plan(config, task)
        stage_mgr.setup(task.slug, "execution")

        # Create execution draft
        exec_dir = config.tasks_dir / task.task_id / "30-execution"
        (exec_dir / "execution-v1.md").write_text("# Execution Summary\nAll done.")

        stage_mgr.review_approve(task.slug, "execution")

        # Stage advanced to complete
        loaded = store.load_task(task.slug)
        assert loaded.stage == Stage.COMPLETE

    def test_spec_approval_populates_summary(self, env):
        stage_mgr, task_mgr, store, config, task = env

        # Create spec draft with a clear title
        spec_dir = config.tasks_dir / task.task_id / "10-spec"
        (spec_dir / "spec-v1.md").write_text(
            "# Spec: Build Amazing Feature\n\n## Overview\nDo stuff"
        )

        stage_mgr.review_approve(task.slug, "spec")

        import json

        state_path = config.state_dir / f"{task.slug}.json"
        data = json.loads(state_path.read_text())
        assert data["summary"] == "Build Amazing Feature"
