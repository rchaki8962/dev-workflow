"""Tests for dev_workflow.store — FileTaskStore persistence layer."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from dev_workflow.exceptions import TaskNotFoundError
from dev_workflow.models import (
    ActivityEntry,
    Plan,
    PlanTask,
    Review,
    ReviewVerdict,
    Spec,
    Stage,
    Subtask,
    SubtaskEntry,
    SubtaskStatus,
    Task,
    TaskProgress,
    VerificationStep,
)
from dev_workflow.store import FileTaskStore


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_task(
    slug: str = "csv-export",
    title: str = "User data CSV export",
    stage: Stage = Stage.SPEC,
    summary: str = "Export user data to CSV files",
) -> Task:
    now = datetime.now(timezone.utc)
    return Task(
        task_id=f"2026-04-08-{slug}",
        slug=slug,
        title=title,
        summary=summary,
        stage=stage,
        workspaces=[Path("~/workspace/my-api")],
        task_folder=Path(f"~/.dev-workflow/tasks/2026-04-08-{slug}"),
        created=now,
        updated=now,
    )


def _make_progress(task: Task | None = None) -> TaskProgress:
    task = task or _make_task(stage=Stage.EXECUTION)
    return TaskProgress(
        task=task,
        approved_spec=Path("spec-v1.md"),
        approved_plan=Path("plan-v1.md"),
        subtask_index=[
            SubtaskEntry(
                id=1,
                title="Create CSV serializer",
                status=SubtaskStatus.DONE,
                file_path=Path("subtask-01.md"),
            ),
            SubtaskEntry(
                id=2,
                title="Add API endpoint",
                status=SubtaskStatus.IN_PROGRESS,
                file_path=Path("subtask-02.md"),
            ),
        ],
        blockers=["Waiting for schema approval"],
        recent_activity=[
            ActivityEntry(
                timestamp=datetime(2026, 4, 8, 14, 0, tzinfo=timezone.utc),
                action="subtask-done",
                detail="Subtask 1 completed",
            ),
        ],
        next_actions=["Complete API endpoint"],
    )


def _make_subtask(
    subtask_id: int = 1,
    title: str = "Create CSV serializer",
    status: SubtaskStatus = SubtaskStatus.DONE,
) -> Subtask:
    return Subtask(
        id=subtask_id,
        title=title,
        description="Implement a CSV serializer that converts query results to RFC 4180 CSV.",
        verification=[
            VerificationStep(description="Unit tests pass", checked=True),
            VerificationStep(description="Handles unicode", checked=False),
        ],
        status=status,
        execution_summary="Implemented csv_serializer.py with streaming support.",
        files_changed=["src/export/csv_serializer.py", "tests/test_csv_serializer.py"],
        what_changed="Added CSVSerializer class with stream() and to_string() methods.",
        blockers=[],
    )


def _make_spec(version: int = 1) -> Spec:
    return Spec(
        version=version,
        title="CSV Export Feature",
        overview="Export user data as CSV files with streaming support.",
        requirements=["Support RFC 4180 format", "Handle large datasets via streaming"],
        constraints=["Must work with existing auth layer"],
        open_questions=["Maximum file size limit?"],
        raw_content=(
            "# Spec: CSV Export Feature\n\n"
            "## Overview\nExport user data as CSV files with streaming support.\n\n"
            "## Requirements\n- Support RFC 4180 format\n- Handle large datasets via streaming\n\n"
            "## Constraints\n- Must work with existing auth layer\n\n"
            "## Open Questions\n- Maximum file size limit?\n"
        ),
    )


def _make_plan(version: int = 1) -> Plan:
    raw = (
        "# Implementation Plan: CSV Export Feature\n\n"
        "**Approved Spec**: spec-v1.md\n\n"
        "## Approach\nBuild streaming CSV serializer with endpoint.\n\n"
        "## Tasks\n\n"
        "### Task 1: CSV Serializer\n\n"
        "**Description:**\nImplement CSV serializer module.\n\n"
        "**Verification:**\n- [ ] Unit tests pass\n\n"
        "**Dependencies:** None\n\n"
        "### Task 2: API Endpoint\n\n"
        "**Description:**\nAdd /export endpoint.\n\n"
        "**Verification:**\n- [ ] Integration test passes\n\n"
        "**Dependencies:** Task 1\n\n"
        "## Risks\n- Large exports may timeout\n"
    )
    return Plan(
        version=version,
        title="CSV Export Feature",
        spec_path=Path("spec-v1.md"),
        approach="Build streaming CSV serializer with endpoint.",
        tasks=[
            PlanTask(id=1, title="CSV Serializer", description="Implement CSV serializer module.",
                     verification_steps=["Unit tests pass"], dependencies=[]),
            PlanTask(id=2, title="API Endpoint", description="Add /export endpoint.",
                     verification_steps=["Integration test passes"], dependencies=[1]),
        ],
        risks=["Large exports may timeout"],
        raw_content=raw,
    )


def _make_review(stage: str = "spec", version: int = 1) -> Review:
    return Review(
        stage=stage,
        version=version,
        verdict=ReviewVerdict.APPROVE,
        inputs_read=["spec-v1.md", "00-progress.md"],
        critical=[],
        important=["Add rate limiting"],
        minor=["Typo in header"],
        required_revisions=[],
        residual_risks=["Large exports may timeout"],
    )


# ---------------------------------------------------------------------------
# Task save/load round-trip
# ---------------------------------------------------------------------------


class TestTaskSaveLoad:
    def test_round_trip(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        task = _make_task()
        store.save_task(task)
        loaded = store.load_task("csv-export")

        assert loaded.task_id == task.task_id
        assert loaded.slug == task.slug
        assert loaded.title == task.title
        assert loaded.summary == task.summary
        assert loaded.stage == task.stage

    def test_list_tasks(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_task(_make_task(slug="alpha"))
        store.save_task(_make_task(slug="beta"))

        tasks = store.list_tasks()
        slugs = {t.slug for t in tasks}
        assert slugs == {"alpha", "beta"}

    def test_search_tasks(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_task(_make_task(slug="csv-export", title="CSV Export"))
        store.save_task(_make_task(slug="auth-fix", title="Auth Fix", summary="Fix authentication bug"))

        results = store.search_tasks("csv")
        assert len(results) == 1
        assert results[0].slug == "csv-export"


# ---------------------------------------------------------------------------
# Progress save/load round-trip
# ---------------------------------------------------------------------------


class TestProgressSaveLoad:
    def test_round_trip(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        task = _make_task(stage=Stage.EXECUTION)
        progress = _make_progress(task)

        store.save_progress("my-task", progress)
        loaded = store.load_progress("my-task")

        assert loaded.task.title == task.title
        assert loaded.task.stage == Stage.EXECUTION
        assert len(loaded.subtask_index) == 2
        assert loaded.subtask_index[0].title == "Create CSV serializer"
        assert loaded.subtask_index[1].status == SubtaskStatus.IN_PROGRESS

    def test_progress_file_exists(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_progress("my-task", _make_progress())

        path = tmp_path / "tasks" / "my-task" / "00-progress.md"
        assert path.exists()


# ---------------------------------------------------------------------------
# Subtask save/load
# ---------------------------------------------------------------------------


class TestSubtaskSaveLoad:
    def test_round_trip(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        subtask = _make_subtask()

        store.save_subtask("my-task", subtask)
        loaded = store.load_subtask("my-task", 1)

        assert loaded.id == 1
        assert loaded.title == "Create CSV serializer"
        assert loaded.description == "Implement a CSV serializer that converts query results to RFC 4180 CSV."
        assert loaded.status == SubtaskStatus.DONE
        assert len(loaded.verification) == 2
        assert loaded.verification[0].description == "Unit tests pass"
        assert loaded.verification[0].checked is True
        assert loaded.verification[1].description == "Handles unicode"
        assert loaded.verification[1].checked is False
        assert "src/export/csv_serializer.py" in loaded.files_changed
        assert "tests/test_csv_serializer.py" in loaded.files_changed
        assert loaded.execution_summary is not None
        assert "streaming support" in loaded.execution_summary
        assert loaded.what_changed is not None
        assert "CSVSerializer" in loaded.what_changed

    def test_subtask_file_path(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_subtask("my-task", _make_subtask(subtask_id=3))

        path = tmp_path / "tasks" / "my-task" / "30-execution" / "subtask-03.md"
        assert path.exists()


# ---------------------------------------------------------------------------
# Subtask list
# ---------------------------------------------------------------------------


class TestSubtaskList:
    def test_list_returns_sorted_entries(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_subtask("my-task", _make_subtask(subtask_id=3, title="Third"))
        store.save_subtask("my-task", _make_subtask(subtask_id=1, title="First"))
        store.save_subtask("my-task", _make_subtask(subtask_id=2, title="Second"))

        entries = store.list_subtasks("my-task")

        assert len(entries) == 3
        assert entries[0].id == 1
        assert entries[0].title == "First"
        assert entries[1].id == 2
        assert entries[1].title == "Second"
        assert entries[2].id == 3
        assert entries[2].title == "Third"

    def test_list_empty_when_no_subtasks(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        entries = store.list_subtasks("nonexistent-task")
        assert entries == []


# ---------------------------------------------------------------------------
# Activity append and load
# ---------------------------------------------------------------------------


class TestActivityLog:
    def test_append_and_load(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        ts_base = datetime(2026, 4, 8, 10, 0, 0, tzinfo=timezone.utc)

        store.append_activity("my-task", ActivityEntry(
            timestamp=ts_base,
            action="task-created",
            detail="Task created",
        ))
        store.append_activity("my-task", ActivityEntry(
            timestamp=ts_base + timedelta(hours=1),
            action="spec-written",
            detail="Spec v1 written",
        ))
        store.append_activity("my-task", ActivityEntry(
            timestamp=ts_base + timedelta(hours=2),
            action="spec-reviewed",
            detail="Spec v1 approved",
        ))

        entries = store.load_activity_log("my-task")

        assert len(entries) == 3
        assert entries[0].action == "task-created"
        assert entries[1].action == "spec-written"
        assert entries[2].action == "spec-reviewed"
        assert entries[0].detail == "Task created"

    def test_load_empty_log(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        entries = store.load_activity_log("nonexistent-task")
        assert entries == []


# ---------------------------------------------------------------------------
# Spec save/load
# ---------------------------------------------------------------------------


class TestSpecSaveLoad:
    def test_round_trip_with_raw_content(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        spec = _make_spec()

        store.save_spec("my-task", spec)
        loaded = store.load_spec("my-task", 1)

        assert loaded.version == 1
        assert loaded.raw_content == spec.raw_content
        assert loaded.title == "CSV Export Feature"
        assert loaded.overview == "Export user data as CSV files with streaming support."
        assert "Support RFC 4180 format" in loaded.requirements
        assert "Handle large datasets via streaming" in loaded.requirements
        assert "Must work with existing auth layer" in loaded.constraints
        assert "Maximum file size limit?" in loaded.open_questions

    def test_spec_without_raw_content_renders(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        spec = Spec(
            version=2,
            title="Minimal Spec",
            overview="A minimal spec.",
            requirements=["Req 1"],
            constraints=[],
            open_questions=[],
            raw_content="",
        )

        store.save_spec("my-task", spec)
        loaded = store.load_spec("my-task", 2)

        assert loaded.title == "Minimal Spec"
        assert loaded.overview == "A minimal spec."
        assert "Req 1" in loaded.requirements

    def test_spec_file_path(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_spec("my-task", _make_spec(version=3))

        path = tmp_path / "tasks" / "my-task" / "10-spec" / "spec-v3.md"
        assert path.exists()


# ---------------------------------------------------------------------------
# Plan save/load
# ---------------------------------------------------------------------------


class TestPlanSaveLoad:
    def test_round_trip(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        plan = _make_plan()

        store.save_plan("my-task", plan)
        loaded = store.load_plan("my-task", 1)

        assert loaded.version == 1
        assert loaded.title == "CSV Export Feature"
        assert len(loaded.tasks) == 2
        assert loaded.tasks[0].title == "CSV Serializer"
        assert loaded.tasks[1].title == "API Endpoint"
        assert loaded.tasks[1].dependencies == [1]

    def test_plan_file_path(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_plan("my-task", _make_plan(version=2))

        path = tmp_path / "tasks" / "my-task" / "20-plan" / "plan-v2.md"
        assert path.exists()


# ---------------------------------------------------------------------------
# Review save/load
# ---------------------------------------------------------------------------


class TestReviewSaveLoad:
    def test_save_creates_file_at_correct_path(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        review = _make_review(stage="spec", version=1)

        store.save_review("my-task", review)

        path = tmp_path / "tasks" / "my-task" / "10-spec" / "spec-review-v1.md"
        assert path.exists()

    def test_plan_review_path(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        review = _make_review(stage="plan", version=2)

        store.save_review("my-task", review)

        path = tmp_path / "tasks" / "my-task" / "20-plan" / "plan-review-v2.md"
        assert path.exists()

    def test_execution_review_path(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        review = _make_review(stage="execution", version=1)

        store.save_review("my-task", review)

        path = tmp_path / "tasks" / "my-task" / "30-execution" / "execution-review-v1.md"
        assert path.exists()

    def test_load_review_returns_review(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        review = _make_review(stage="spec", version=1)
        store.save_review("my-task", review)

        loaded = store.load_review("my-task", "spec", 1)
        assert loaded.stage == "spec"
        assert loaded.version == 1


# ---------------------------------------------------------------------------
# Delete task
# ---------------------------------------------------------------------------


class TestDeleteTask:
    def test_delete_then_load_raises(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        store.save_task(_make_task(slug="doomed"))

        store.delete_task("doomed")

        with pytest.raises(TaskNotFoundError):
            store.load_task("doomed")


# ---------------------------------------------------------------------------
# FileNotFoundError for missing artifacts
# ---------------------------------------------------------------------------


class TestFileNotFound:
    def test_load_progress_missing(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_progress("nonexistent")

    def test_load_subtask_missing(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_subtask("nonexistent", 1)

    def test_load_spec_missing(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_spec("nonexistent", 1)

    def test_load_plan_missing(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_plan("nonexistent", 1)

    def test_load_review_missing(self, tmp_path: Path):
        store = FileTaskStore(tmp_path)
        with pytest.raises(FileNotFoundError):
            store.load_review("nonexistent", "spec", 1)
