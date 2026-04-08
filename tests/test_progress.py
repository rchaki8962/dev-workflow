"""Tests for dev_workflow.progress — parsing and updating 00-progress.md."""

from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.models import (
    ActivityEntry,
    Stage,
    SubtaskEntry,
    SubtaskStatus,
    Task,
    TaskProgress,
)
from dev_workflow.progress import (
    parse_progress,
    update_progress_recent_activity,
    update_progress_stage_status,
    update_progress_subtask_index,
)
from dev_workflow.templates import render_progress


# ---------------------------------------------------------------------------
# Helper factories (mirrors test_templates.py style)
# ---------------------------------------------------------------------------


def make_sample_task(**overrides) -> Task:
    defaults = dict(
        task_id="2026-04-08-csv-export",
        slug="csv-export",
        title="CSV Export",
        summary="Export user data as CSV",
        stage=Stage.EXECUTION,
        workspaces=[Path("~/workspace/my-api")],
        task_folder=Path("~/.dev-workflow/tasks/2026-04-08-csv-export"),
        created=datetime(2026, 4, 8, tzinfo=timezone.utc),
        updated=datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


def make_full_progress() -> TaskProgress:
    task = make_sample_task()
    return TaskProgress(
        task=task,
        approved_spec=Path("spec-v1.md"),
        approved_plan=Path("implementation-plan-v1.md"),
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
        blockers=["Waiting for schema migration approval"],
        recent_activity=[
            ActivityEntry(
                timestamp=datetime(2026, 4, 8, 14, 0, tzinfo=timezone.utc),
                action="subtask-done",
                detail="Subtask 1 completed",
            ),
            ActivityEntry(
                timestamp=datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc),
                action="subtask-start",
                detail="Started subtask 2",
            ),
        ],
        next_actions=["Complete API endpoint", "Write integration tests"],
    )


def make_empty_progress() -> TaskProgress:
    task = make_sample_task(stage=Stage.SPEC, workspaces=[])
    return TaskProgress(task=task)


# ---------------------------------------------------------------------------
# Round-trip: render → parse
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Render a TaskProgress, parse it back, verify key fields match."""

    def test_round_trip_title(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.task.title == original.task.title

    def test_round_trip_task_id(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.task.task_id == original.task.task_id

    def test_round_trip_stage(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.task.stage == original.task.stage

    def test_round_trip_workspaces(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.task.workspaces == original.task.workspaces

    def test_round_trip_approved_spec(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.approved_spec == original.approved_spec

    def test_round_trip_approved_plan(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.approved_plan == original.approved_plan

    def test_round_trip_subtask_count(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert len(parsed.subtask_index) == len(original.subtask_index)

    def test_round_trip_subtask_fields(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        for orig, parsed_entry in zip(original.subtask_index, parsed.subtask_index):
            assert parsed_entry.id == orig.id
            assert parsed_entry.title == orig.title
            assert parsed_entry.status == orig.status
            assert parsed_entry.file_path == orig.file_path

    def test_round_trip_blockers(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.blockers == original.blockers

    def test_round_trip_recent_activity(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert len(parsed.recent_activity) == len(original.recent_activity)
        for orig, parsed_act in zip(original.recent_activity, parsed.recent_activity):
            assert parsed_act.action == orig.action
            assert parsed_act.detail == orig.detail

    def test_round_trip_next_actions(self):
        original = make_full_progress()
        content = render_progress(original)
        parsed = parse_progress(content)
        assert parsed.next_actions == original.next_actions


# ---------------------------------------------------------------------------
# Parse header metadata
# ---------------------------------------------------------------------------


class TestParseHeaderMetadata:
    def setup_method(self):
        self.progress = make_full_progress()
        self.content = render_progress(self.progress)
        self.parsed = parse_progress(self.content)

    def test_task_id(self):
        assert self.parsed.task.task_id == "2026-04-08-csv-export"

    def test_stage(self):
        assert self.parsed.task.stage == Stage.EXECUTION

    def test_approved_spec(self):
        assert self.parsed.approved_spec == Path("spec-v1.md")

    def test_approved_plan(self):
        assert self.parsed.approved_plan == Path("implementation-plan-v1.md")

    def test_updated_timestamp(self):
        assert self.parsed.task.updated == datetime(
            2026, 4, 8, 14, 30, tzinfo=timezone.utc
        )


# ---------------------------------------------------------------------------
# Parse empty / "(none)" progress
# ---------------------------------------------------------------------------


class TestParseEmptyProgress:
    """Progress with '(none)' in all list sections yields empty lists."""

    def setup_method(self):
        self.progress = make_empty_progress()
        self.content = render_progress(self.progress)
        self.parsed = parse_progress(self.content)

    def test_no_workspaces(self):
        assert self.parsed.task.workspaces == []

    def test_no_subtasks(self):
        assert self.parsed.subtask_index == []

    def test_no_blockers(self):
        assert self.parsed.blockers == []

    def test_no_recent_activity(self):
        assert self.parsed.recent_activity == []

    def test_no_next_actions(self):
        assert self.parsed.next_actions == []

    def test_pending_spec(self):
        assert self.parsed.approved_spec is None

    def test_pending_plan(self):
        assert self.parsed.approved_plan is None


# ---------------------------------------------------------------------------
# Parse subtask table
# ---------------------------------------------------------------------------


class TestParseSubtaskTable:
    def test_three_subtask_entries(self):
        task = make_sample_task()
        progress = TaskProgress(
            task=task,
            subtask_index=[
                SubtaskEntry(1, "Setup DB", SubtaskStatus.DONE, Path("subtask-01.md")),
                SubtaskEntry(
                    2, "Write API", SubtaskStatus.IN_PROGRESS, Path("subtask-02.md")
                ),
                SubtaskEntry(
                    3, "Add tests", SubtaskStatus.NOT_STARTED, Path("subtask-03.md")
                ),
            ],
        )
        content = render_progress(progress)
        parsed = parse_progress(content)

        assert len(parsed.subtask_index) == 3

    def test_subtask_entry_fields(self):
        task = make_sample_task()
        progress = TaskProgress(
            task=task,
            subtask_index=[
                SubtaskEntry(1, "Setup DB", SubtaskStatus.DONE, Path("subtask-01.md")),
                SubtaskEntry(
                    2, "Write API", SubtaskStatus.IN_PROGRESS, Path("subtask-02.md")
                ),
                SubtaskEntry(
                    3, "Add tests", SubtaskStatus.NOT_STARTED, Path("subtask-03.md")
                ),
            ],
        )
        content = render_progress(progress)
        parsed = parse_progress(content)

        assert parsed.subtask_index[0].id == 1
        assert parsed.subtask_index[0].title == "Setup DB"
        assert parsed.subtask_index[0].status == SubtaskStatus.DONE
        assert parsed.subtask_index[0].file_path == Path("subtask-01.md")

        assert parsed.subtask_index[1].id == 2
        assert parsed.subtask_index[1].title == "Write API"
        assert parsed.subtask_index[1].status == SubtaskStatus.IN_PROGRESS

        assert parsed.subtask_index[2].id == 3
        assert parsed.subtask_index[2].title == "Add tests"
        assert parsed.subtask_index[2].status == SubtaskStatus.NOT_STARTED


# ---------------------------------------------------------------------------
# Parse activity entries
# ---------------------------------------------------------------------------


class TestParseActivityEntries:
    def test_parse_single_activity(self):
        content = render_progress(
            TaskProgress(
                task=make_sample_task(),
                recent_activity=[
                    ActivityEntry(
                        timestamp=datetime(2026, 4, 8, 11, 5, 0, tzinfo=timezone.utc),
                        action="Task created",
                        detail="Initial setup",
                    )
                ],
            )
        )
        parsed = parse_progress(content)

        assert len(parsed.recent_activity) == 1
        entry = parsed.recent_activity[0]
        assert entry.action == "Task created"
        assert entry.detail == "Initial setup"
        assert entry.timestamp == datetime(2026, 4, 8, 11, 5, 0, tzinfo=timezone.utc)

    def test_parse_raw_activity_line(self):
        """Parse an activity entry from raw markdown (not rendered)."""
        raw = (
            "# Task: Test\n\n"
            "- **Task ID**: test-001\n"
            "- **Current Stage**: spec\n"
            "- **Approved Spec**: pending\n"
            "- **Approved Plan**: pending\n"
            "- **Last Updated**: 2026-04-08T11:05:00Z\n\n"
            "## Workspaces\n"
            "- (none)\n\n"
            "## Stage Status\nCurrently in **spec** stage.\n\n"
            "## Subtask Index\n\n"
            "| # | Title | Status | File |\n"
            "|---|-------|--------|------|\n\n"
            "## Blockers / Open Questions\n(none)\n\n"
            "## Recent Activity\n"
            "- [2026-04-08T11:05:00Z] Task created: Initial setup\n\n"
            "## Next Actions\n(none)\n\n"
            "## Reader Guide\n"
        )
        parsed = parse_progress(raw)
        assert len(parsed.recent_activity) == 1
        assert parsed.recent_activity[0].action == "Task created"
        assert parsed.recent_activity[0].detail == "Initial setup"
        assert parsed.recent_activity[0].timestamp == datetime(
            2026, 4, 8, 11, 5, 0, tzinfo=timezone.utc
        )


# ---------------------------------------------------------------------------
# update_progress_stage_status
# ---------------------------------------------------------------------------


class TestUpdateStageStatus:
    def test_changes_stage(self):
        progress = make_full_progress()
        updated = update_progress_stage_status(progress, Stage.COMPLETE, "All done")
        assert updated.task.stage == Stage.COMPLETE

    def test_updates_timestamp(self):
        progress = make_full_progress()
        before = datetime.now(timezone.utc)
        updated = update_progress_stage_status(progress, Stage.PLAN, "Planning")
        assert updated.task.updated >= before

    def test_preserves_other_fields(self):
        progress = make_full_progress()
        updated = update_progress_stage_status(progress, Stage.PLAN, "Planning")
        assert updated.task.task_id == progress.task.task_id
        assert updated.task.title == progress.task.title
        assert updated.blockers == progress.blockers
        assert updated.subtask_index == progress.subtask_index


# ---------------------------------------------------------------------------
# update_progress_subtask_index
# ---------------------------------------------------------------------------


class TestUpdateSubtaskIndex:
    def test_replaces_subtask_entries(self):
        progress = make_full_progress()
        new_entries = [
            SubtaskEntry(10, "New task", SubtaskStatus.NOT_STARTED, Path("subtask-10.md"))
        ]
        updated = update_progress_subtask_index(progress, new_entries)
        assert len(updated.subtask_index) == 1
        assert updated.subtask_index[0].id == 10
        assert updated.subtask_index[0].title == "New task"

    def test_updates_timestamp(self):
        progress = make_full_progress()
        before = datetime.now(timezone.utc)
        updated = update_progress_subtask_index(progress, [])
        assert updated.task.updated >= before

    def test_preserves_other_fields(self):
        progress = make_full_progress()
        new_entries = [
            SubtaskEntry(10, "New task", SubtaskStatus.NOT_STARTED, Path("subtask-10.md"))
        ]
        updated = update_progress_subtask_index(progress, new_entries)
        assert updated.task.task_id == progress.task.task_id
        assert updated.blockers == progress.blockers
        assert updated.recent_activity == progress.recent_activity


# ---------------------------------------------------------------------------
# update_progress_recent_activity
# ---------------------------------------------------------------------------


class TestUpdateRecentActivity:
    def test_keeps_only_last_n_entries(self):
        progress = make_full_progress()
        many_activities = [
            ActivityEntry(
                timestamp=datetime(2026, 4, 8, i, 0, tzinfo=timezone.utc),
                action=f"action-{i}",
                detail=f"Detail {i}",
            )
            for i in range(15)
        ]
        updated = update_progress_recent_activity(progress, many_activities, max_entries=5)
        assert len(updated.recent_activity) == 5
        # Should keep the last 5 (indices 10-14)
        assert updated.recent_activity[0].action == "action-10"
        assert updated.recent_activity[-1].action == "action-14"

    def test_keeps_all_when_under_max(self):
        progress = make_full_progress()
        activities = [
            ActivityEntry(
                timestamp=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc),
                action="only-one",
                detail="The only entry",
            )
        ]
        updated = update_progress_recent_activity(progress, activities, max_entries=10)
        assert len(updated.recent_activity) == 1
        assert updated.recent_activity[0].action == "only-one"

    def test_updates_timestamp(self):
        progress = make_full_progress()
        before = datetime.now(timezone.utc)
        updated = update_progress_recent_activity(progress, [], max_entries=10)
        assert updated.task.updated >= before

    def test_default_max_entries_is_10(self):
        progress = make_full_progress()
        many_activities = [
            ActivityEntry(
                timestamp=datetime(2026, 4, 8, i, 0, tzinfo=timezone.utc),
                action=f"action-{i}",
                detail=f"Detail {i}",
            )
            for i in range(20)
        ]
        updated = update_progress_recent_activity(progress, many_activities)
        assert len(updated.recent_activity) == 10
        assert updated.recent_activity[0].action == "action-10"
