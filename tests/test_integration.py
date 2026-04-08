"""Integration tests: end-to-end workflows exercised through the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dev_workflow.cli import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def base(tmp_path):
    """Return tmp_path as a string for --base-dir."""
    return str(tmp_path)


def cli(runner: CliRunner, base_dir: str, args: list[str]):
    """Invoke the CLI with --base-dir prepended. Returns Click Result."""
    return runner.invoke(main, ["--base-dir", base_dir] + args)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SPEC_CONTENT = """\
# Spec: Test Task

## Overview
Build a test feature.

## Requirements
- Must be testable
- Must be fast

## Constraints
- Python only
"""

PLAN_CONTENT = """\
# Implementation Plan: Test

**Approved Spec**: 10-spec/spec-approved.md

## Approach
Test approach

## Tasks

### Task 1: First task

**Description:**
Do the first thing.

**Verification:**
- [ ] Verify it works

**Dependencies:** none

### Task 2: Second task

**Description:**
Do the second thing.

**Verification:**
- [ ] Verify it works

**Dependencies:** Task 1
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_task(runner, base, title, slug, prompt="Build something"):
    """Create a task via CLI and return parsed JSON."""
    result = cli(
        runner,
        base,
        ["task", "start", title, "--slug", slug, "--prompt", prompt, "--format", "json"],
    )
    assert result.exit_code == 0, f"task start failed: {result.output}"
    return json.loads(result.output)


def _setup_stage(runner, base, stage_name, slug):
    """Run stage setup and return parsed JSON."""
    result = cli(
        runner,
        base,
        ["stage", "setup", stage_name, "--task", slug, "--format", "json"],
    )
    assert result.exit_code == 0, f"stage setup {stage_name} failed: {result.output}"
    return json.loads(result.output)


def _teardown_stage(runner, base, stage_name, slug):
    """Run stage teardown."""
    result = cli(runner, base, ["stage", "teardown", stage_name, "--task", slug])
    assert result.exit_code == 0, f"stage teardown {stage_name} failed: {result.output}"
    return result


def _approve_stage(runner, base, stage_name, slug):
    """Run review approve."""
    result = cli(runner, base, ["review", "approve", stage_name, "--task", slug])
    assert result.exit_code == 0, f"review approve {stage_name} failed: {result.output}"
    return result


def _get_stage(runner, base, slug) -> str:
    """Return the current stage string for a task."""
    result = cli(runner, base, ["stage", "status", "--task", slug, "--format", "json"])
    assert result.exit_code == 0
    return json.loads(result.output)["stage"]


def _complete_spec(runner, base, slug, spec_content=SPEC_CONTENT):
    """Drive a task through the complete spec stage."""
    setup = _setup_stage(runner, base, "spec", slug)
    Path(setup["output_path"]).write_text(spec_content)
    _teardown_stage(runner, base, "spec", slug)
    _approve_stage(runner, base, "spec", slug)


def _complete_plan(runner, base, slug, plan_content=PLAN_CONTENT):
    """Drive a task through the complete plan stage."""
    setup = _setup_stage(runner, base, "plan", slug)
    Path(setup["output_path"]).write_text(plan_content)
    _teardown_stage(runner, base, "plan", slug)
    _approve_stage(runner, base, "plan", slug)


# ===========================================================================
# 1. Task creation flow
# ===========================================================================


class TestTaskCreationFlow:
    """task start -> verify folder structure, progress file, state JSON."""

    def test_folder_structure_created(self, runner, base, tmp_path):
        data = _create_task(runner, base, "My Feature", "my-feature")
        task_folder = Path(data["task_folder"])

        assert task_folder.exists()
        assert (task_folder / "10-spec").is_dir()
        assert (task_folder / "20-plan").is_dir()
        assert (task_folder / "30-execution").is_dir()
        assert (task_folder / "90-logs").is_dir()

    def test_progress_file_created(self, runner, base):
        data = _create_task(runner, base, "My Feature", "my-feature")
        progress = Path(data["task_folder"]) / "00-progress.md"
        assert progress.exists()
        content = progress.read_text()
        assert "My Feature" in content

    def test_original_prompt_written(self, runner, base):
        data = _create_task(runner, base, "My Feature", "my-feature", prompt="Build CSV export")
        prompt_path = Path(data["task_folder"]) / "01-original-prompt.md"
        assert prompt_path.exists()
        assert prompt_path.read_text() == "Build CSV export"

    def test_state_json_created(self, runner, base, tmp_path):
        _create_task(runner, base, "My Feature", "my-feature")
        state_dir = tmp_path / "harness" / "state"
        state_files = list(state_dir.glob("*.json"))
        assert len(state_files) == 1
        state_data = json.loads(state_files[0].read_text())
        assert state_data["slug"] == "my-feature"
        assert state_data["stage"] == "spec"

    def test_initial_stage_is_spec(self, runner, base):
        data = _create_task(runner, base, "My Feature", "my-feature")
        assert data["stage"] == "spec"


# ===========================================================================
# 2. Spec stage flow
# ===========================================================================


class TestSpecStageFlow:
    """stage setup spec -> write spec -> stage teardown spec -> review approve spec."""

    def test_full_spec_cycle(self, runner, base, tmp_path):
        _create_task(runner, base, "Spec Test", "spec-test")

        # Stage setup spec
        setup = _setup_stage(runner, base, "spec", "spec-test")
        assert setup["version"] == 1
        output_path = Path(setup["output_path"])
        assert "spec-v1.md" in output_path.name

        # Write the spec draft
        output_path.write_text(SPEC_CONTENT)
        assert output_path.exists()

        # Stage teardown
        _teardown_stage(runner, base, "spec", "spec-test")

        # Review approve
        _approve_stage(runner, base, "spec", "spec-test")

        # Verify spec-approved.md exists
        spec_dir = output_path.parent
        approved = spec_dir / "spec-approved.md"
        assert approved.exists()
        assert approved.read_text() == SPEC_CONTENT

        # Verify stage advanced to plan
        assert _get_stage(runner, base, "spec-test") == "plan"

    def test_spec_approved_content_matches_draft(self, runner, base):
        _create_task(runner, base, "Content Test", "content-test")
        setup = _setup_stage(runner, base, "spec", "content-test")
        output_path = Path(setup["output_path"])
        output_path.write_text(SPEC_CONTENT)
        _teardown_stage(runner, base, "spec", "content-test")
        _approve_stage(runner, base, "spec", "content-test")

        approved = output_path.parent / "spec-approved.md"
        assert approved.read_text() == SPEC_CONTENT


# ===========================================================================
# 3. Plan stage flow
# ===========================================================================


class TestPlanStageFlow:
    """stage setup plan -> write plan -> stage teardown plan -> review approve plan."""

    def test_full_plan_cycle(self, runner, base):
        _create_task(runner, base, "Plan Test", "plan-test")
        _complete_spec(runner, base, "plan-test")

        # Now in plan stage
        assert _get_stage(runner, base, "plan-test") == "plan"

        # Stage setup plan
        setup = _setup_stage(runner, base, "plan", "plan-test")
        assert setup["version"] == 1
        output_path = Path(setup["output_path"])
        assert "plan-v1.md" in output_path.name

        # Write the plan draft
        output_path.write_text(PLAN_CONTENT)

        # Stage teardown
        _teardown_stage(runner, base, "plan", "plan-test")

        # Review approve
        _approve_stage(runner, base, "plan", "plan-test")

        # Verify plan-approved.md exists
        plan_dir = output_path.parent
        approved = plan_dir / "plan-approved.md"
        assert approved.exists()
        assert approved.read_text() == PLAN_CONTENT

        # Verify stage advanced to execution
        assert _get_stage(runner, base, "plan-test") == "execution"


# ===========================================================================
# 4. Execution stage flow
# ===========================================================================


class TestExecutionStageFlow:
    """stage setup execution -> verify subtask files -> teardown -> approve -> complete."""

    def test_full_execution_cycle(self, runner, base):
        _create_task(runner, base, "Exec Test", "exec-test")
        _complete_spec(runner, base, "exec-test")
        _complete_plan(runner, base, "exec-test")

        # Now in execution stage
        assert _get_stage(runner, base, "exec-test") == "execution"

        # Stage setup execution
        setup = _setup_stage(runner, base, "execution", "exec-test")
        subtask_files = setup["subtask_files"]

        # Plan has 2 tasks, so should create 2 subtask files
        assert len(subtask_files) == 2
        for sf in subtask_files:
            assert Path(sf).exists()

        # Verify subtask file content
        subtask1 = Path(subtask_files[0]).read_text()
        assert "First task" in subtask1

        subtask2 = Path(subtask_files[1]).read_text()
        assert "Second task" in subtask2

        # Stage teardown
        _teardown_stage(runner, base, "execution", "exec-test")

        # Create execution summary draft (required for review approve to find a draft)
        exec_dir = Path(subtask_files[0]).parent
        (exec_dir / "execution-v1.md").write_text(
            "# Execution Summary\n\nAll tasks completed."
        )

        # Review approve
        _approve_stage(runner, base, "execution", "exec-test")

        # Verify stage is complete
        assert _get_stage(runner, base, "exec-test") == "complete"

    def test_subtask_files_created_from_plan(self, runner, base):
        _create_task(runner, base, "Subtask Test", "subtask-test")
        _complete_spec(runner, base, "subtask-test")
        _complete_plan(runner, base, "subtask-test")

        setup = _setup_stage(runner, base, "execution", "subtask-test")
        subtask_files = setup["subtask_files"]

        # Each subtask file should have structured content
        for sf in subtask_files:
            content = Path(sf).read_text()
            assert "## Description" in content
            assert "## Verification" in content
            assert "## Status" in content


# ===========================================================================
# 5. Multi-task
# ===========================================================================


class TestMultiTask:
    """Create two tasks, verify both appear in list and search finds the right one."""

    def test_both_tasks_in_list(self, runner, base):
        _create_task(runner, base, "Build CSV Export", "csv-export")
        _create_task(runner, base, "Fix Auth Bug", "auth-bug")

        result = cli(runner, base, ["task", "list", "--format", "json"])
        assert result.exit_code == 0
        tasks = json.loads(result.output)
        slugs = {t["slug"] for t in tasks}
        assert "csv-export" in slugs
        assert "auth-bug" in slugs
        assert len(tasks) == 2

    def test_search_finds_correct_task(self, runner, base):
        _create_task(runner, base, "Build CSV Export", "csv-export")
        _create_task(runner, base, "Fix Auth Bug", "auth-bug")

        result = cli(runner, base, ["task", "search", "CSV", "--format", "json"])
        assert result.exit_code == 0
        tasks = json.loads(result.output)
        assert len(tasks) == 1
        assert tasks[0]["slug"] == "csv-export"

    def test_search_by_slug(self, runner, base):
        _create_task(runner, base, "Build CSV Export", "csv-export")
        _create_task(runner, base, "Fix Auth Bug", "auth-bug")

        result = cli(runner, base, ["task", "search", "auth", "--format", "json"])
        assert result.exit_code == 0
        tasks = json.loads(result.output)
        assert len(tasks) == 1
        assert tasks[0]["slug"] == "auth-bug"

    def test_tasks_have_independent_state(self, runner, base):
        _create_task(runner, base, "Task Alpha", "alpha")
        _create_task(runner, base, "Task Beta", "beta")

        # Advance alpha through spec
        _complete_spec(runner, base, "alpha")

        # Alpha should be in plan, beta still in spec
        assert _get_stage(runner, base, "alpha") == "plan"
        assert _get_stage(runner, base, "beta") == "spec"


# ===========================================================================
# 6. Task switch
# ===========================================================================


class TestTaskSwitch:
    """Create task, advance through spec+plan, switch -> verify output."""

    def test_switch_shows_progress(self, runner, base):
        _create_task(runner, base, "Switch Test", "switch-test")

        result = cli(runner, base, ["task", "switch", "switch-test"])
        assert result.exit_code == 0
        assert "Progress" in result.output

    def test_switch_shows_spec_summary_after_spec_approved(self, runner, base):
        _create_task(runner, base, "Switch Test", "switch-test")
        _complete_spec(runner, base, "switch-test")

        result = cli(runner, base, ["task", "switch", "switch-test"])
        assert result.exit_code == 0
        assert "Progress" in result.output
        assert "Spec Summary" in result.output

    def test_switch_shows_plan_summary_after_plan_approved(self, runner, base):
        _create_task(runner, base, "Switch Test", "switch-test")
        _complete_spec(runner, base, "switch-test")
        _complete_plan(runner, base, "switch-test")

        result = cli(runner, base, ["task", "switch", "switch-test"])
        assert result.exit_code == 0
        assert "Progress" in result.output
        assert "Spec Summary" in result.output
        assert "Plan Summary" in result.output

    def test_switch_plan_summary_contains_task_titles(self, runner, base):
        _create_task(runner, base, "Switch Test", "switch-test")
        _complete_spec(runner, base, "switch-test")
        _complete_plan(runner, base, "switch-test")

        result = cli(runner, base, ["task", "switch", "switch-test"])
        assert result.exit_code == 0
        # Plan summary should mention the task titles from the plan
        assert "First task" in result.output
        assert "Second task" in result.output


# ===========================================================================
# 7. Version detection
# ===========================================================================


class TestVersionDetection:
    """Run stage setup spec twice -> verify second produces spec-v2.md."""

    def test_second_spec_setup_produces_v2(self, runner, base):
        _create_task(runner, base, "Version Test", "ver-test")

        # First setup: version 1
        setup1 = _setup_stage(runner, base, "spec", "ver-test")
        assert setup1["version"] == 1
        assert "spec-v1.md" in setup1["output_path"]

        # Write the v1 draft so it exists on disk
        Path(setup1["output_path"]).write_text("# Spec v1\n\n## Overview\nFirst draft.\n")

        # Second setup: version 2 (because spec-v1.md exists)
        setup2 = _setup_stage(runner, base, "spec", "ver-test")
        assert setup2["version"] == 2
        assert "spec-v2.md" in setup2["output_path"]

    def test_second_plan_setup_produces_v2(self, runner, base):
        _create_task(runner, base, "Version Test", "ver-test")
        _complete_spec(runner, base, "ver-test")

        # First plan setup: version 1
        setup1 = _setup_stage(runner, base, "plan", "ver-test")
        assert setup1["version"] == 1

        # Write the v1 plan draft
        Path(setup1["output_path"]).write_text(PLAN_CONTENT)

        # Second plan setup: version 2
        setup2 = _setup_stage(runner, base, "plan", "ver-test")
        assert setup2["version"] == 2
        assert "plan-v2.md" in setup2["output_path"]


# ===========================================================================
# 8. Error cases
# ===========================================================================


class TestErrorCases:
    """Verify proper error messages for invalid operations."""

    def test_stage_setup_spec_without_prompt(self, runner, base):
        """spec setup requires 01-original-prompt.md to be non-empty."""
        # Create task without a prompt (empty prompt file)
        result = cli(
            runner,
            base,
            ["task", "start", "Empty Prompt", "--slug", "no-prompt", "--format", "json"],
        )
        assert result.exit_code == 0

        result = cli(runner, base, ["stage", "setup", "spec", "--task", "no-prompt"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_stage_setup_plan_without_approved_spec(self, runner, base):
        """plan setup requires spec-approved.md."""
        _create_task(runner, base, "No Spec", "no-spec")

        result = cli(runner, base, ["stage", "setup", "plan", "--task", "no-spec"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_stage_setup_execution_without_approved_plan(self, runner, base):
        """execution setup requires plan-approved.md."""
        _create_task(runner, base, "No Plan", "no-plan")
        _complete_spec(runner, base, "no-plan")

        result = cli(runner, base, ["stage", "setup", "execution", "--task", "no-plan"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_approve_without_draft(self, runner, base):
        """review approve without any draft should fail."""
        _create_task(runner, base, "No Draft", "no-draft")

        result = cli(runner, base, ["review", "approve", "spec", "--task", "no-draft"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_unknown_slug_stage_setup(self, runner, base):
        """stage setup with unknown slug should fail."""
        result = cli(runner, base, ["stage", "setup", "spec", "--task", "nonexistent"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_unknown_slug_review_approve(self, runner, base):
        """review approve with unknown slug should fail."""
        result = cli(runner, base, ["review", "approve", "spec", "--task", "nonexistent"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_unknown_slug_task_info(self, runner, base):
        """task info with unknown slug should fail."""
        result = cli(runner, base, ["task", "info", "nonexistent"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_unknown_slug_task_switch(self, runner, base):
        """task switch with unknown slug should fail."""
        result = cli(runner, base, ["task", "switch", "nonexistent"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_invalid_stage_name(self, runner, base):
        """Invalid stage name should be rejected by Click."""
        _create_task(runner, base, "Test", "test-task")
        result = cli(runner, base, ["stage", "setup", "invalid", "--task", "test-task"])
        assert result.exit_code != 0

    def test_review_setup_without_draft(self, runner, base):
        """review setup without a draft should fail."""
        _create_task(runner, base, "No Draft", "no-draft-review")

        result = cli(runner, base, ["review", "setup", "spec", "--task", "no-draft-review"])
        assert result.exit_code != 0
        assert "Error" in result.output


# ===========================================================================
# 9. Full end-to-end workflow (spec -> plan -> execution -> complete)
# ===========================================================================


class TestFullWorkflow:
    """Drive a task all the way from creation to completion."""

    def test_complete_lifecycle(self, runner, base):
        # 1. Create task
        data = _create_task(runner, base, "Full E2E Task", "e2e-full")
        task_folder = Path(data["task_folder"])
        assert data["stage"] == "spec"

        # 2. Spec stage
        _complete_spec(runner, base, "e2e-full")
        assert _get_stage(runner, base, "e2e-full") == "plan"
        assert (task_folder / "10-spec" / "spec-approved.md").exists()

        # 3. Plan stage
        _complete_plan(runner, base, "e2e-full")
        assert _get_stage(runner, base, "e2e-full") == "execution"
        assert (task_folder / "20-plan" / "plan-approved.md").exists()

        # 4. Execution stage
        setup = _setup_stage(runner, base, "execution", "e2e-full")
        assert len(setup["subtask_files"]) == 2

        _teardown_stage(runner, base, "execution", "e2e-full")

        # Create execution summary draft (required for review approve)
        exec_dir = Path(setup["subtask_files"][0]).parent
        (exec_dir / "execution-v1.md").write_text(
            "# Execution Summary\n\nAll tasks completed."
        )
        _approve_stage(runner, base, "execution", "e2e-full")

        # 5. Task is complete
        assert _get_stage(runner, base, "e2e-full") == "complete"

        # 6. Verify all artifacts exist
        assert (task_folder / "00-progress.md").exists()
        assert (task_folder / "01-original-prompt.md").exists()
        assert (task_folder / "10-spec" / "spec-v1.md").exists()
        assert (task_folder / "10-spec" / "spec-approved.md").exists()
        assert (task_folder / "20-plan" / "plan-v1.md").exists()
        assert (task_folder / "20-plan" / "plan-approved.md").exists()
        assert (task_folder / "30-execution" / "subtask-01.md").exists()
        assert (task_folder / "30-execution" / "subtask-02.md").exists()
        assert (task_folder / "90-logs" / "activity-log.md").exists()

        # 7. Activity log should have entries for all stages
        log_content = (task_folder / "90-logs" / "activity-log.md").read_text()
        assert "Task created" in log_content
        assert "Spec stage" in log_content
        assert "Plan stage" in log_content
        assert "Execution stage" in log_content

    def test_info_reflects_final_state(self, runner, base):
        """task info should show complete stage after full lifecycle."""
        _create_task(runner, base, "Info Test", "info-test")
        _complete_spec(runner, base, "info-test")
        _complete_plan(runner, base, "info-test")
        setup = _setup_stage(runner, base, "execution", "info-test")
        _teardown_stage(runner, base, "execution", "info-test")
        # Create execution summary draft (required for review approve)
        exec_dir = Path(setup["subtask_files"][0]).parent
        (exec_dir / "execution-v1.md").write_text(
            "# Execution Summary\n\nAll tasks completed."
        )
        _approve_stage(runner, base, "execution", "info-test")

        result = cli(runner, base, ["task", "info", "info-test", "--format", "json"])
        assert result.exit_code == 0
        info = json.loads(result.output)
        assert info["stage"] == "complete"
        assert info["slug"] == "info-test"


# ===========================================================================
# 10. Space integration
# ===========================================================================


class TestSpaceIntegration:
    """Space CRUD, task isolation, cross-space listing, and full workflows in spaces."""

    def test_create_and_list_spaces(self, runner, base):
        """Create multiple spaces and verify they appear in list."""
        result = cli(runner, base, ["space", "create", "personal", "--description", "Mine"])
        assert result.exit_code == 0
        result = cli(runner, base, ["space", "create", "work", "--description", "Job"])
        assert result.exit_code == 0
        result = cli(runner, base, ["space", "list"])
        assert result.exit_code == 0
        assert "personal" in result.output
        assert "work" in result.output

    def test_task_isolation_between_spaces(self, runner, base):
        """Tasks created in different spaces should not appear in each other's lists."""
        cli(runner, base, ["space", "create", "alpha"])
        cli(runner, base, ["space", "create", "beta"])
        cli(runner, base, ["--space", "alpha", "task", "start", "My Task", "--prompt", "alpha"])
        cli(runner, base, ["--space", "beta", "task", "start", "My Task", "--prompt", "beta"])

        result_a = cli(runner, base, ["--space", "alpha", "task", "list", "--format", "json"])
        result_b = cli(runner, base, ["--space", "beta", "task", "list", "--format", "json"])
        tasks_a = json.loads(result_a.output)
        tasks_b = json.loads(result_b.output)
        assert len(tasks_a) == 1
        assert len(tasks_b) == 1
        assert tasks_a[0]["space"] == "alpha"
        assert tasks_b[0]["space"] == "beta"

    def test_all_spaces_listing(self, runner, base):
        """--all-spaces flag should list tasks across all spaces."""
        cli(runner, base, ["space", "create", "alpha"])
        cli(runner, base, ["space", "create", "beta"])
        cli(runner, base, ["--space", "alpha", "task", "start", "Alpha Task", "--prompt", "a"])
        cli(runner, base, ["--space", "beta", "task", "start", "Beta Task", "--prompt", "b"])
        result = cli(runner, base, ["task", "list", "--all-spaces", "--format", "json"])
        data = json.loads(result.output)
        spaces = {t["space"] for t in data}
        assert "alpha" in spaces
        assert "beta" in spaces

    def test_default_space_auto_created(self, runner, base):
        """Default 'harness' space should be auto-created on first task."""
        result = cli(runner, base, ["task", "start", "First Task", "--prompt", "test"])
        assert result.exit_code == 0
        result = cli(runner, base, ["space", "list", "--format", "json"])
        data = json.loads(result.output)
        assert any(s["name"] == "harness" for s in data)

    def test_space_flag_overrides_default(self, runner, base):
        """--space flag should override default harness space."""
        cli(runner, base, ["space", "create", "custom"])
        result = cli(runner, base, ["--space", "custom", "task", "start", "Custom Task", "--prompt", "test", "--format", "json"])
        data = json.loads(result.output)
        assert data["space"] == "custom"

    def test_full_workflow_in_space(self, runner, base):
        """Full spec cycle within a non-default space."""
        cli(runner, base, ["space", "create", "test-space"])
        result = cli(runner, base, ["--space", "test-space", "task", "start", "Workflow Test", "--prompt", "Build something", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        slug = data["slug"]

        result = cli(runner, base, ["--space", "test-space", "stage", "setup", "spec", "--task", slug, "--format", "json"])
        assert result.exit_code == 0
        setup_data = json.loads(result.output)

        spec_path = Path(setup_data["output_path"])
        spec_path.write_text("# Spec: Test\n\n## Overview\nTest spec\n")

        result = cli(runner, base, ["--space", "test-space", "stage", "teardown", "spec", "--task", slug])
        assert result.exit_code == 0
        result = cli(runner, base, ["--space", "test-space", "review", "approve", "spec", "--task", slug])
        assert result.exit_code == 0

        result = cli(runner, base, ["--space", "test-space", "task", "info", slug, "--format", "json"])
        data = json.loads(result.output)
        assert data["stage"] == "plan"
