"""Tests for dev_workflow domain models and exceptions."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_workflow.exceptions import (
    DevWorkflowError,
    PlanParseError,
    PrerequisiteError,
    SpaceNotFoundError,
    TaskNotFoundError,
)
from dev_workflow.models import (
    ActivityEntry,
    Plan,
    PlanTask,
    Review,
    ReviewVerdict,
    Space,
    Spec,
    Stage,
    Subtask,
    SubtaskEntry,
    SubtaskStatus,
    Task,
    TaskProgress,
    VerificationStep,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestStageEnum:
    def test_values(self):
        assert Stage.SPEC.value == "spec"
        assert Stage.PLAN.value == "plan"
        assert Stage.EXECUTION.value == "execution"
        assert Stage.COMPLETE.value == "complete"

    def test_membership(self):
        assert "spec" in [s.value for s in Stage]
        assert "plan" in [s.value for s in Stage]
        assert "execution" in [s.value for s in Stage]
        assert "complete" in [s.value for s in Stage]

    def test_str_enum_construction(self):
        assert Stage("spec") == Stage.SPEC
        assert Stage("plan") == Stage.PLAN
        assert Stage("execution") == Stage.EXECUTION
        assert Stage("complete") == Stage.COMPLETE

    def test_str_enum_is_string(self):
        assert isinstance(Stage.SPEC, str)
        assert Stage.SPEC == "spec"

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            Stage("invalid")


class TestSubtaskStatusEnum:
    def test_values(self):
        assert SubtaskStatus.NOT_STARTED.value == "not-started"
        assert SubtaskStatus.IN_PROGRESS.value == "in-progress"
        assert SubtaskStatus.DONE.value == "done"
        assert SubtaskStatus.BLOCKED.value == "blocked"

    def test_str_enum_construction(self):
        assert SubtaskStatus("not-started") == SubtaskStatus.NOT_STARTED
        assert SubtaskStatus("in-progress") == SubtaskStatus.IN_PROGRESS
        assert SubtaskStatus("done") == SubtaskStatus.DONE
        assert SubtaskStatus("blocked") == SubtaskStatus.BLOCKED

    def test_str_enum_is_string(self):
        assert isinstance(SubtaskStatus.NOT_STARTED, str)
        assert SubtaskStatus.NOT_STARTED == "not-started"


class TestReviewVerdictEnum:
    def test_values(self):
        assert ReviewVerdict.APPROVE.value == "approve"
        assert ReviewVerdict.REVISE.value == "revise"
        assert ReviewVerdict.BLOCKED.value == "blocked"

    def test_str_enum_construction(self):
        assert ReviewVerdict("approve") == ReviewVerdict.APPROVE
        assert ReviewVerdict("revise") == ReviewVerdict.REVISE
        assert ReviewVerdict("blocked") == ReviewVerdict.BLOCKED

    def test_str_enum_is_string(self):
        assert isinstance(ReviewVerdict.APPROVE, str)
        assert ReviewVerdict.APPROVE == "approve"


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 8, 12, 0, 0)


class TestActivityEntry:
    def test_construct_and_access(self):
        entry = ActivityEntry(timestamp=NOW, action="create", detail="Created task")
        assert entry.timestamp == NOW
        assert entry.action == "create"
        assert entry.detail == "Created task"


class TestVerificationStep:
    def test_construct_and_access(self):
        step = VerificationStep(description="Run unit tests")
        assert step.description == "Run unit tests"
        assert step.checked is False

    def test_checked_default(self):
        step = VerificationStep(description="Check")
        assert step.checked is False

    def test_checked_override(self):
        step = VerificationStep(description="Check", checked=True)
        assert step.checked is True


class TestTask:
    def test_construct_and_access(self):
        task = Task(
            task_id="001",
            slug="my-task",
            title="My Task",
            summary="A test task",
            stage=Stage.SPEC,
            workspaces=[Path("/workspace/a")],
            task_folder=Path("/tasks/001"),
            created=NOW,
            updated=NOW,
        )
        assert task.task_id == "001"
        assert task.slug == "my-task"
        assert task.title == "My Task"
        assert task.summary == "A test task"
        assert task.stage == Stage.SPEC
        assert task.workspaces == [Path("/workspace/a")]
        assert task.task_folder == Path("/tasks/001")
        assert task.created == NOW
        assert task.updated == NOW


class TestSpaceDataclass:
    def test_construction(self):
        now = datetime.now(timezone.utc)
        space = Space(name="personal", description="Personal projects", created=now)
        assert space.name == "personal"
        assert space.description == "Personal projects"
        assert space.created == now

    def test_empty_description(self):
        now = datetime.now(timezone.utc)
        space = Space(name="work", description="", created=now)
        assert space.description == ""


class TestTaskSpaceField:
    def test_default_space_is_empty_string(self):
        now = datetime.now(timezone.utc)
        task = Task(
            task_id="2026-04-08-test", slug="test", title="Test",
            summary="", stage=Stage.SPEC, workspaces=[Path(".")],
            task_folder=Path("/tmp/test"), created=now, updated=now,
        )
        assert task.space == ""

    def test_space_set_at_construction(self):
        now = datetime.now(timezone.utc)
        task = Task(
            task_id="2026-04-08-test", slug="test", title="Test",
            summary="", stage=Stage.SPEC, workspaces=[Path(".")],
            task_folder=Path("/tmp/test"), created=now, updated=now,
            space="harness",
        )
        assert task.space == "harness"


class TestSubtaskEntry:
    def test_construct_and_access(self):
        entry = SubtaskEntry(
            id=1,
            title="Subtask 1",
            status=SubtaskStatus.IN_PROGRESS,
            file_path=Path("/tasks/001/subtask-1.md"),
        )
        assert entry.id == 1
        assert entry.title == "Subtask 1"
        assert entry.status == SubtaskStatus.IN_PROGRESS
        assert entry.file_path == Path("/tasks/001/subtask-1.md")


def _make_task() -> Task:
    return Task(
        task_id="001",
        slug="my-task",
        title="My Task",
        summary="A test task",
        stage=Stage.SPEC,
        workspaces=[Path("/workspace/a")],
        task_folder=Path("/tasks/001"),
        created=NOW,
        updated=NOW,
    )


class TestTaskProgress:
    def test_construct_minimal(self):
        task = _make_task()
        progress = TaskProgress(task=task)
        assert progress.task is task
        assert progress.approved_spec is None
        assert progress.approved_plan is None
        assert progress.subtask_index == []
        assert progress.blockers == []
        assert progress.recent_activity == []
        assert progress.next_actions == []

    def test_construct_with_all_fields(self):
        task = _make_task()
        entry = SubtaskEntry(
            id=1,
            title="Sub",
            status=SubtaskStatus.DONE,
            file_path=Path("/tasks/001/sub.md"),
        )
        activity = ActivityEntry(timestamp=NOW, action="done", detail="Finished")
        progress = TaskProgress(
            task=task,
            approved_spec=Path("/specs/v1.md"),
            approved_plan=Path("/plans/v1.md"),
            subtask_index=[entry],
            blockers=["blocked on X"],
            recent_activity=[activity],
            next_actions=["Review spec"],
        )
        assert progress.approved_spec == Path("/specs/v1.md")
        assert progress.approved_plan == Path("/plans/v1.md")
        assert len(progress.subtask_index) == 1
        assert progress.blockers == ["blocked on X"]
        assert len(progress.recent_activity) == 1
        assert progress.next_actions == ["Review spec"]


class TestSubtask:
    def test_construct_minimal(self):
        subtask = Subtask(id=1, title="Do thing", description="Details here")
        assert subtask.id == 1
        assert subtask.title == "Do thing"
        assert subtask.description == "Details here"
        assert subtask.verification == []
        assert subtask.status == SubtaskStatus.NOT_STARTED
        assert subtask.execution_summary is None
        assert subtask.files_changed == []
        assert subtask.what_changed is None
        assert subtask.blockers == []

    def test_default_status_is_not_started(self):
        subtask = Subtask(id=1, title="T", description="D")
        assert subtask.status == SubtaskStatus.NOT_STARTED

    def test_construct_with_all_fields(self):
        step = VerificationStep(description="Verify output", checked=True)
        subtask = Subtask(
            id=2,
            title="Build module",
            description="Build the module",
            verification=[step],
            status=SubtaskStatus.DONE,
            execution_summary="Completed successfully",
            files_changed=["src/foo.py"],
            what_changed="Added foo module",
            blockers=[],
        )
        assert subtask.status == SubtaskStatus.DONE
        assert subtask.execution_summary == "Completed successfully"
        assert subtask.files_changed == ["src/foo.py"]
        assert subtask.what_changed == "Added foo module"
        assert len(subtask.verification) == 1
        assert subtask.verification[0].checked is True


class TestPlanTask:
    def test_construct_minimal(self):
        pt = PlanTask(id=1, title="Task", description="Desc")
        assert pt.id == 1
        assert pt.title == "Task"
        assert pt.description == "Desc"
        assert pt.verification_steps == []
        assert pt.dependencies == []

    def test_construct_with_all_fields(self):
        pt = PlanTask(
            id=2,
            title="Second",
            description="Depends on first",
            verification_steps=["Check output"],
            dependencies=[1],
        )
        assert pt.verification_steps == ["Check output"]
        assert pt.dependencies == [1]


class TestSpec:
    def test_construct_minimal(self):
        spec = Spec(version=1, title="My Spec", overview="An overview")
        assert spec.version == 1
        assert spec.title == "My Spec"
        assert spec.overview == "An overview"
        assert spec.requirements == []
        assert spec.constraints == []
        assert spec.open_questions == []
        assert spec.raw_content == ""

    def test_construct_with_all_fields(self):
        spec = Spec(
            version=2,
            title="Full Spec",
            overview="Detailed overview",
            requirements=["Req 1", "Req 2"],
            constraints=["Must use Python"],
            open_questions=["What about edge cases?"],
            raw_content="# Full Spec\n...",
        )
        assert len(spec.requirements) == 2
        assert spec.constraints == ["Must use Python"]
        assert spec.raw_content == "# Full Spec\n..."


class TestPlan:
    def test_construct_minimal(self):
        plan = Plan(
            version=1,
            title="My Plan",
            spec_path=Path("/specs/v1.md"),
            approach="Incremental",
        )
        assert plan.version == 1
        assert plan.title == "My Plan"
        assert plan.spec_path == Path("/specs/v1.md")
        assert plan.approach == "Incremental"
        assert plan.tasks == []
        assert plan.risks == []
        assert plan.raw_content == ""

    def test_construct_with_tasks(self):
        pt = PlanTask(id=1, title="Step 1", description="First step")
        plan = Plan(
            version=1,
            title="Plan",
            spec_path=Path("/specs/v1.md"),
            approach="Big bang",
            tasks=[pt],
            risks=["Might fail"],
            raw_content="# Plan\n...",
        )
        assert len(plan.tasks) == 1
        assert plan.tasks[0].title == "Step 1"
        assert plan.risks == ["Might fail"]


class TestReview:
    def test_construct_minimal(self):
        review = Review(
            stage="spec",
            version=1,
            verdict=ReviewVerdict.APPROVE,
        )
        assert review.stage == "spec"
        assert review.version == 1
        assert review.verdict == ReviewVerdict.APPROVE
        assert review.inputs_read == []
        assert review.critical == []
        assert review.important == []
        assert review.minor == []
        assert review.required_revisions == []
        assert review.residual_risks == []

    def test_construct_with_all_fields(self):
        review = Review(
            stage="plan",
            version=2,
            verdict=ReviewVerdict.REVISE,
            inputs_read=["spec-v1.md"],
            critical=["Missing error handling"],
            important=["Add logging"],
            minor=["Typo in comment"],
            required_revisions=["Fix error handling"],
            residual_risks=["Performance unknown"],
        )
        assert review.verdict == ReviewVerdict.REVISE
        assert len(review.critical) == 1
        assert review.required_revisions == ["Fix error handling"]


# ---------------------------------------------------------------------------
# Exception tests
# ---------------------------------------------------------------------------


class TestDevWorkflowError:
    def test_is_exception(self):
        assert issubclass(DevWorkflowError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(DevWorkflowError):
            raise DevWorkflowError("something went wrong")


class TestTaskNotFoundError:
    def test_message(self):
        err = TaskNotFoundError("my-task")
        assert "my-task" in str(err)
        assert "not found" in str(err)
        assert "task list" in str(err)

    def test_slug_attribute(self):
        err = TaskNotFoundError("my-task")
        assert err.slug == "my-task"

    def test_is_dev_workflow_error(self):
        assert issubclass(TaskNotFoundError, DevWorkflowError)

    def test_catch_as_base(self):
        with pytest.raises(DevWorkflowError):
            raise TaskNotFoundError("foo")


class TestPrerequisiteError:
    def test_message(self):
        err = PrerequisiteError("plan", "spec not approved")
        assert "plan" in str(err)
        assert "spec not approved" in str(err)
        assert "prerequisite not met" in str(err)

    def test_stage_attribute(self):
        err = PrerequisiteError("execution", "no plan")
        assert err.stage == "execution"

    def test_is_dev_workflow_error(self):
        assert issubclass(PrerequisiteError, DevWorkflowError)


class TestPlanParseError:
    def test_message(self):
        err = PlanParseError("invalid YAML")
        assert "Failed to parse plan" in str(err)
        assert "invalid YAML" in str(err)

    def test_is_dev_workflow_error(self):
        assert issubclass(PlanParseError, DevWorkflowError)


class TestSpaceNotFoundError:
    def test_message(self):
        err = SpaceNotFoundError("personal")
        assert "personal" in str(err)
        assert err.name == "personal"

    def test_is_dev_workflow_error(self):
        assert issubclass(SpaceNotFoundError, DevWorkflowError)
