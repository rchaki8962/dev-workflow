"""Tests for dev_workflow.templates — rendering dataclasses to markdown."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_workflow.models import (
    ActivityEntry,
    Review,
    ReviewVerdict,
    Stage,
    Subtask,
    SubtaskEntry,
    SubtaskStatus,
    Task,
    TaskProgress,
    VerificationStep,
)
from dev_workflow.templates import (
    TEMPLATES_DIR,
    render_progress,
    render_review,
    render_review_template,
    render_subtask,
)


# ---------------------------------------------------------------------------
# Helper factories
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
    task = make_sample_task(stage=Stage.SPEC)
    return TaskProgress(task=task)


def make_full_subtask() -> Subtask:
    return Subtask(
        id=1,
        title="Create CSV serializer",
        description="Implement a CSV serializer that converts query results to RFC 4180 CSV.",
        verification=[
            VerificationStep(description="Unit tests pass", checked=True),
            VerificationStep(description="Handles unicode", checked=False),
        ],
        status=SubtaskStatus.DONE,
        execution_summary="Implemented csv_serializer.py with streaming support.",
        files_changed=["src/export/csv_serializer.py", "tests/test_csv_serializer.py"],
        what_changed="Added CSVSerializer class with stream() and to_string() methods.",
        blockers=[],
    )


def make_minimal_subtask() -> Subtask:
    return Subtask(
        id=3,
        title="TBD integration",
        description="Integrate with external service.",
    )


def make_full_review() -> Review:
    return Review(
        stage="spec",
        version=1,
        verdict=ReviewVerdict.REVISE,
        inputs_read=["spec-v1.md", "00-progress.md"],
        critical=["Missing error handling for malformed rows"],
        important=["Add rate limiting to export endpoint"],
        minor=["Typo in section header"],
        required_revisions=["Add error handling section", "Define rate limit policy"],
        residual_risks=["Large exports may timeout without streaming"],
    )


# ---------------------------------------------------------------------------
# Templates directory and file presence
# ---------------------------------------------------------------------------


class TestTemplatesDirectory:
    def test_templates_dir_exists(self):
        assert TEMPLATES_DIR.is_dir(), f"Templates directory not found: {TEMPLATES_DIR}"

    @pytest.mark.parametrize(
        "filename",
        [
            "progress.md",
            "spec.md",
            "implementation-plan.md",
            "subtask.md",
            "review.md",
        ],
    )
    def test_template_file_exists(self, filename):
        path = TEMPLATES_DIR / filename
        assert path.is_file(), f"Template file missing: {path}"


# ---------------------------------------------------------------------------
# render_progress
# ---------------------------------------------------------------------------


class TestRenderProgress:
    def test_full_progress_contains_header(self):
        output = render_progress(make_full_progress())
        assert "# Task: CSV Export" in output

    def test_full_progress_contains_task_id(self):
        output = render_progress(make_full_progress())
        assert "2026-04-08-csv-export" in output

    def test_full_progress_contains_stage(self):
        output = render_progress(make_full_progress())
        assert "execution" in output

    def test_full_progress_contains_approved_spec(self):
        output = render_progress(make_full_progress())
        assert "spec-v1.md" in output

    def test_full_progress_contains_approved_plan(self):
        output = render_progress(make_full_progress())
        assert "implementation-plan-v1.md" in output

    def test_full_progress_contains_updated_timestamp(self):
        output = render_progress(make_full_progress())
        assert "2026-04-08T14:30:00Z" in output

    def test_full_progress_contains_workspaces(self):
        output = render_progress(make_full_progress())
        assert "## Workspaces" in output
        assert "~/workspace/my-api" in output

    def test_full_progress_contains_stage_status(self):
        output = render_progress(make_full_progress())
        assert "## Stage Status" in output
        assert "Currently in **execution** stage." in output

    def test_full_progress_contains_subtask_index_table(self):
        output = render_progress(make_full_progress())
        assert "## Subtask Index" in output
        assert "| # | Title | Status | File |" in output
        assert "| 1 | Create CSV serializer | done | subtask-01.md |" in output
        assert "| 2 | Add API endpoint | in-progress | subtask-02.md |" in output

    def test_full_progress_contains_blockers(self):
        output = render_progress(make_full_progress())
        assert "## Blockers / Open Questions" in output
        assert "Waiting for schema migration approval" in output

    def test_full_progress_contains_recent_activity(self):
        output = render_progress(make_full_progress())
        assert "## Recent Activity" in output
        assert "[2026-04-08T14:00:00Z] subtask-done: Subtask 1 completed" in output
        assert "[2026-04-08T14:30:00Z] subtask-start: Started subtask 2" in output

    def test_full_progress_contains_next_actions(self):
        output = render_progress(make_full_progress())
        assert "## Next Actions" in output
        assert "- Complete API endpoint" in output
        assert "- Write integration tests" in output

    def test_full_progress_contains_reader_guide(self):
        output = render_progress(make_full_progress())
        assert "## Reader Guide" in output
        assert "If you are an implementer:" in output
        assert "If you are a reviewer:" in output

    def test_empty_progress_pending_spec(self):
        output = render_progress(make_empty_progress())
        assert "pending" in output

    def test_empty_progress_no_workspaces_shows_none(self):
        progress = make_empty_progress()
        progress.task.workspaces = []
        output = render_progress(progress)
        assert "- (none)" in output

    def test_empty_progress_no_blockers_shows_none(self):
        output = render_progress(make_empty_progress())
        assert "(none)" in output

    def test_empty_progress_no_activity_shows_none(self):
        output = render_progress(make_empty_progress())
        # Recent activity section should show (none)
        lines = output.split("\n")
        activity_idx = next(i for i, l in enumerate(lines) if "## Recent Activity" in l)
        # The line after the section header should be (none)
        assert "(none)" in lines[activity_idx + 1]

    def test_empty_progress_no_next_actions_shows_none(self):
        output = render_progress(make_empty_progress())
        lines = output.split("\n")
        actions_idx = next(i for i, l in enumerate(lines) if "## Next Actions" in l)
        assert "(none)" in lines[actions_idx + 1]


# ---------------------------------------------------------------------------
# render_subtask
# ---------------------------------------------------------------------------


class TestRenderSubtask:
    def test_full_subtask_header(self):
        output = render_subtask(make_full_subtask())
        assert "# Subtask 1: Create CSV serializer" in output

    def test_full_subtask_description(self):
        output = render_subtask(make_full_subtask())
        assert "## Description" in output
        assert "RFC 4180 CSV" in output

    def test_full_subtask_verification_checklist(self):
        output = render_subtask(make_full_subtask())
        assert "## Verification" in output
        assert "- [x] Unit tests pass" in output
        assert "- [ ] Handles unicode" in output

    def test_full_subtask_status(self):
        output = render_subtask(make_full_subtask())
        assert "## Status" in output
        assert "done" in output

    def test_full_subtask_execution_summary(self):
        output = render_subtask(make_full_subtask())
        assert "## Execution Summary" in output
        assert "streaming support" in output

    def test_full_subtask_files_changed(self):
        output = render_subtask(make_full_subtask())
        assert "### Files Changed" in output
        assert "- src/export/csv_serializer.py" in output
        assert "- tests/test_csv_serializer.py" in output

    def test_full_subtask_what_changed(self):
        output = render_subtask(make_full_subtask())
        assert "### What Changed" in output
        assert "CSVSerializer class" in output

    def test_full_subtask_blockers_empty(self):
        output = render_subtask(make_full_subtask())
        assert "## Blockers" in output
        assert "(none)" in output

    def test_minimal_subtask_defaults(self):
        output = render_subtask(make_minimal_subtask())
        assert "# Subtask 3: TBD integration" in output
        assert "not-started" in output

    def test_minimal_subtask_no_execution_summary(self):
        output = render_subtask(make_minimal_subtask())
        assert "(not yet completed)" in output

    def test_minimal_subtask_no_verification(self):
        output = render_subtask(make_minimal_subtask())
        lines = output.split("\n")
        verif_idx = next(i for i, l in enumerate(lines) if "## Verification" in l)
        assert "(none)" in lines[verif_idx + 1]

    def test_minimal_subtask_no_files_changed(self):
        output = render_subtask(make_minimal_subtask())
        assert "(none)" in output

    def test_subtask_with_blockers(self):
        subtask = make_minimal_subtask()
        subtask.blockers = ["Waiting on API keys"]
        output = render_subtask(subtask)
        assert "- Waiting on API keys" in output


# ---------------------------------------------------------------------------
# render_review_template
# ---------------------------------------------------------------------------


class TestRenderReviewTemplate:
    def test_produces_pending_verdict(self):
        output = render_review_template("spec", 1, ["spec-v1.md"])
        assert "(pending)" in output

    def test_contains_stage_header(self):
        output = render_review_template("spec", 1, ["spec-v1.md"])
        assert "# Spec Review" in output

    def test_contains_inputs(self):
        output = render_review_template("plan", 1, ["spec-v1.md", "plan-v1.md"])
        assert "- spec-v1.md" in output
        assert "- plan-v1.md" in output

    def test_empty_inputs(self):
        output = render_review_template("spec", 1, [])
        assert "(none)" in output

    def test_all_findings_sections_show_none(self):
        output = render_review_template("spec", 1, ["spec-v1.md"])
        assert "### Critical" in output
        assert "### Important" in output
        assert "### Minor" in output
        # All findings sections should contain (none)
        lines = output.split("\n")
        for heading in ["### Critical", "### Important", "### Minor"]:
            idx = next(i for i, l in enumerate(lines) if heading in l)
            assert "(none)" in lines[idx + 1]

    def test_required_revisions_none(self):
        output = render_review_template("spec", 1, [])
        assert "## Required Revisions" in output

    def test_residual_risks_none(self):
        output = render_review_template("spec", 1, [])
        assert "## Residual Risks" in output


# ---------------------------------------------------------------------------
# render_review
# ---------------------------------------------------------------------------


class TestRenderReview:
    def test_contains_stage_header(self):
        output = render_review(make_full_review())
        assert "# Spec Review" in output

    def test_contains_verdict(self):
        output = render_review(make_full_review())
        assert "REVISE" in output

    def test_contains_inputs_read(self):
        output = render_review(make_full_review())
        assert "- spec-v1.md" in output
        assert "- 00-progress.md" in output

    def test_contains_critical_findings(self):
        output = render_review(make_full_review())
        assert "Missing error handling for malformed rows" in output

    def test_contains_important_findings(self):
        output = render_review(make_full_review())
        assert "Add rate limiting to export endpoint" in output

    def test_contains_minor_findings(self):
        output = render_review(make_full_review())
        assert "Typo in section header" in output

    def test_contains_required_revisions(self):
        output = render_review(make_full_review())
        assert "- Add error handling section" in output
        assert "- Define rate limit policy" in output

    def test_contains_residual_risks(self):
        output = render_review(make_full_review())
        assert "Large exports may timeout without streaming" in output

    def test_approve_verdict(self):
        review = Review(
            stage="plan",
            version=1,
            verdict=ReviewVerdict.APPROVE,
        )
        output = render_review(review)
        assert "# Plan Review" in output
        assert "APPROVE" in output

    def test_empty_lists_show_none(self):
        review = Review(
            stage="spec",
            version=1,
            verdict=ReviewVerdict.APPROVE,
        )
        output = render_review(review)
        # All list sections should have (none)
        assert output.count("(none)") >= 6  # inputs, critical, important, minor, revisions, risks
