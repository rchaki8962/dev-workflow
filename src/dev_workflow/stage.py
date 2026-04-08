"""Stage lifecycle: setup, teardown, review setup, review approve."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.config import Config
from dev_workflow.models import (
    Task, TaskProgress, Subtask, SubtaskEntry, ActivityEntry, VerificationStep,
    Stage, SubtaskStatus,
)
from dev_workflow.store import FileTaskStore
from dev_workflow.plan_parser import parse_plan
from dev_workflow.progress import (
    parse_progress, update_progress_stage_status,
    update_progress_subtask_index, update_progress_recent_activity,
)
from dev_workflow.templates import render_progress, render_subtask, render_review_template
from dev_workflow.exceptions import PrerequisiteError


class StageManager:
    def __init__(self, store: FileTaskStore, config: Config):
        self.store = store
        self.config = config

    def setup(self, slug: str, stage_name: str) -> dict:
        """
        Stage setup: validate prerequisites, determine version, prepare.

        Returns dict of paths needed by the engine (JSON-serializable).
        """
        task = self.store.load_task(slug)
        task_dir = self.config.tasks_dir / task.task_id
        stage = Stage(stage_name)

        # Check if stage already completed
        if _stage_order(task.stage) > _stage_order(stage):
            raise PrerequisiteError(
                stage_name,
                f"Stage '{stage_name}' already completed. Current stage: {task.stage.value}",
            )

        if stage == Stage.SPEC:
            return self._setup_spec(task, task_dir)
        elif stage == Stage.PLAN:
            return self._setup_plan(task, task_dir)
        elif stage == Stage.EXECUTION:
            return self._setup_execution(task, task_dir)
        else:
            raise PrerequisiteError(stage_name, f"Invalid stage: {stage_name}")

    def _setup_spec(self, task: Task, task_dir: Path) -> dict:
        prompt_path = task_dir / "01-original-prompt.md"
        if not prompt_path.exists() or prompt_path.stat().st_size == 0:
            raise PrerequisiteError(
                "spec", "01-original-prompt.md must exist and be non-empty"
            )

        version = self._next_version(task_dir / "10-spec", "spec")
        output_path = str(task_dir / "10-spec" / f"spec-v{version}.md")

        self._log_activity(
            task.task_id, "Stage setup", f"Spec stage started, version {version}"
        )

        return {
            "original_prompt_path": str(prompt_path),
            "output_path": output_path,
            "version": version,
        }

    def _setup_plan(self, task: Task, task_dir: Path) -> dict:
        spec_approved = task_dir / "10-spec" / "spec-approved.md"
        if not spec_approved.exists():
            raise PrerequisiteError(
                "plan",
                "10-spec/spec-approved.md must exist. Run /stage-approve spec first.",
            )

        version = self._next_version(task_dir / "20-plan", "plan")
        output_path = str(task_dir / "20-plan" / f"plan-v{version}.md")

        self._log_activity(
            task.task_id, "Stage setup", f"Plan stage started, version {version}"
        )

        return {
            "approved_spec_path": str(spec_approved),
            "output_path": output_path,
            "version": version,
        }

    def _setup_execution(self, task: Task, task_dir: Path) -> dict:
        plan_approved = task_dir / "20-plan" / "plan-approved.md"
        if not plan_approved.exists():
            raise PrerequisiteError(
                "execution",
                "20-plan/plan-approved.md must exist. Run /stage-approve plan first.",
            )

        # Parse plan and create subtask files
        plan_content = plan_approved.read_text()
        plan_tasks = parse_plan(plan_content)

        exec_dir = task_dir / "30-execution"
        exec_dir.mkdir(exist_ok=True)

        subtask_entries = []
        subtask_files = []

        for pt in plan_tasks:
            subtask_path = exec_dir / f"subtask-{pt.id:02d}.md"

            # Idempotent: skip if file already exists
            if not subtask_path.exists():
                subtask = Subtask(
                    id=pt.id,
                    title=pt.title,
                    description=pt.description,
                    verification=[
                        VerificationStep(description=s) for s in pt.verification_steps
                    ],
                    status=SubtaskStatus.NOT_STARTED,
                )
                self.store.save_subtask(task.task_id, subtask)

            subtask_files.append(str(subtask_path))
            subtask_entries.append(SubtaskEntry(
                id=pt.id,
                title=pt.title,
                status=SubtaskStatus.NOT_STARTED,
                file_path=Path(f"30-execution/subtask-{pt.id:02d}.md"),
            ))

        # Update progress with subtask index
        progress = self.store.load_progress(task.task_id)
        progress = update_progress_subtask_index(progress, subtask_entries)
        self.store.save_progress(task.task_id, progress)

        # Update state progress field
        total = len(subtask_entries)
        self.store.state.update(task.slug, progress=f"0/{total} subtasks")

        self._log_activity(
            task.task_id,
            "Stage setup",
            f"Execution stage started, {total} subtask files created",
        )

        return {
            "task_folder": str(task_dir),
            "subtask_files": subtask_files,
        }

    def teardown(self, slug: str, stage_name: str) -> None:
        """
        Stage teardown: update progress and state (does NOT advance stage).
        For execution: also generate implementation-summary.md.
        """
        task = self.store.load_task(slug)
        task_dir = self.config.tasks_dir / task.task_id

        # Update progress
        progress = self.store.load_progress(task.task_id)
        progress = update_progress_stage_status(
            progress, task.stage, f"{stage_name} draft completed"
        )

        # Sync recent activity from log
        all_activity = self.store.load_activity_log(task.task_id)
        progress = update_progress_recent_activity(progress, all_activity)

        self.store.save_progress(task.task_id, progress)

        # Log
        self._log_activity(
            task.task_id,
            "Stage teardown",
            f"{stage_name.capitalize()} stage teardown complete",
        )

        # Update state (progress and updated, NOT stage)
        if stage_name == "execution":
            # Generate implementation summary
            self._generate_implementation_summary(task, task_dir)
            # Update progress count
            entries = self.store.list_subtasks(task.task_id)
            done = sum(1 for e in entries if e.status == SubtaskStatus.DONE)
            total = len(entries)
            self.store.state.update(slug, progress=f"{done}/{total} subtasks")
        else:
            self.store.state.update(slug)  # just updates timestamp

    def review_setup(self, slug: str, stage_name: str) -> dict:
        """
        Review setup: validate draft exists, seed review template.
        Returns review file path and files to review.
        """
        task = self.store.load_task(slug)
        task_dir = self.config.tasks_dir / task.task_id

        stage_dirs = {"spec": "10-spec", "plan": "20-plan", "execution": "30-execution"}
        subdir = stage_dirs[stage_name]

        # Find latest draft version
        version = self._latest_version(task_dir / subdir, stage_name)
        if version == 0:
            raise PrerequisiteError(
                stage_name,
                f"No {stage_name} draft found. Run `/run-stage {stage_name}` first.",
            )

        # Determine files to review
        files_to_review = [
            str(task_dir / "00-progress.md"),
            str(task_dir / "01-original-prompt.md"),
        ]

        if stage_name in ("plan", "execution"):
            files_to_review.append(str(task_dir / "10-spec" / "spec-approved.md"))
        if stage_name == "execution":
            files_to_review.append(str(task_dir / "20-plan" / "plan-approved.md"))

        # The draft under review
        draft_path = str(task_dir / subdir / f"{stage_name}-v{version}.md")
        files_to_review.append(draft_path)

        # Seed review template
        review_path = str(task_dir / subdir / f"{stage_name}-review-v{version}.md")
        review_content = render_review_template(stage_name, version, files_to_review)
        Path(review_path).write_text(review_content)

        self._log_activity(
            task.task_id,
            "Review setup",
            f"{stage_name.capitalize()} review v{version} template created",
        )

        return {
            "review_file": review_path,
            "files_to_review": files_to_review,
            "version": version,
        }

    def review_approve(self, slug: str, stage_name: str) -> None:
        """
        Review approve: copy latest draft to *-approved.md, advance stage.
        """
        task = self.store.load_task(slug)
        task_dir = self.config.tasks_dir / task.task_id

        stage_dirs = {"spec": "10-spec", "plan": "20-plan", "execution": "30-execution"}
        subdir = stage_dirs[stage_name]

        # Find latest draft
        version = self._latest_version(task_dir / subdir, stage_name)
        if version == 0:
            raise PrerequisiteError(
                stage_name,
                f"No {stage_name} draft found. Run `/run-stage {stage_name}` first.",
            )

        draft_path = task_dir / subdir / f"{stage_name}-v{version}.md"
        approved_path = task_dir / subdir / f"{stage_name}-approved.md"

        # Copy draft to approved
        shutil.copy2(draft_path, approved_path)

        # Advance stage
        next_stage = _next_stage(stage_name)

        # Update progress
        progress = self.store.load_progress(task.task_id)
        from dataclasses import replace as dc_replace

        new_task = dc_replace(
            progress.task, stage=next_stage, updated=datetime.now(timezone.utc)
        )

        # Set approved path
        if stage_name == "spec":
            progress = dc_replace(
                progress,
                task=new_task,
                approved_spec=Path(f"{subdir}/{stage_name}-approved.md"),
            )
        elif stage_name == "plan":
            progress = dc_replace(
                progress,
                task=new_task,
                approved_plan=Path(f"{subdir}/{stage_name}-approved.md"),
            )
        elif stage_name == "execution":
            progress = dc_replace(progress, task=new_task)

        self.store.save_progress(task.task_id, progress)

        # Update state: advance stage
        update_fields: dict = {"stage": next_stage}
        if stage_name == "spec":
            # Populate summary from spec
            spec_content = draft_path.read_text()
            title_match = re.search(
                r"^#\s+(?:Spec:\s*)?(.+)$", spec_content, re.MULTILINE
            )
            if title_match:
                update_fields["summary"] = title_match.group(1).strip()

        self.store.state.update(slug, **update_fields)

        self._log_activity(
            task.task_id,
            "Review approved",
            f"{stage_name.capitalize()} v{version} approved, advancing to {next_stage.value}",
        )

    def _next_version(self, dir_path: Path, prefix: str) -> int:
        """Scan directory for existing drafts, return next version number."""
        if not dir_path.exists():
            return 1
        max_v = 0
        for path in dir_path.glob(f"{prefix}-v*.md"):
            match = re.search(r"-v(\d+)\.md$", path.name)
            if match:
                v = int(match.group(1))
                if v > max_v:
                    max_v = v
        return max_v + 1

    def _latest_version(self, dir_path: Path, prefix: str) -> int:
        """Return the highest existing version number (0 if none)."""
        return self._next_version(dir_path, prefix) - 1

    def _log_activity(self, task_id: str, action: str, detail: str) -> None:
        self.store.append_activity(
            task_id,
            ActivityEntry(
                timestamp=datetime.now(timezone.utc),
                action=action,
                detail=detail,
            ),
        )

    def _generate_implementation_summary(self, task: Task, task_dir: Path) -> None:
        """Generate 30-execution/implementation-summary.md from subtask files."""
        entries = self.store.list_subtasks(task.task_id)
        lines = [f"# Implementation Summary: {task.title}", ""]

        all_files_changed: list[str] = []

        for entry in entries:
            subtask = self.store.load_subtask(task.task_id, entry.id)
            status = "\u2713" if entry.status == SubtaskStatus.DONE else entry.status.value
            lines.append(f"## Subtask {entry.id}: {entry.title} [{status}]")
            if subtask.what_changed:
                lines.append(f"\n{subtask.what_changed}")
            if subtask.files_changed:
                lines.append("\n**Files:**")
                for f in subtask.files_changed:
                    lines.append(f"- {f}")
                    if f not in all_files_changed:
                        all_files_changed.append(f)
            lines.append("")

        lines.append("## All Files Changed")
        for f in sorted(all_files_changed):
            lines.append(f"- {f}")
        lines.append("")

        summary_path = task_dir / "30-execution" / "implementation-summary.md"
        summary_path.write_text("\n".join(lines))


def _stage_order(stage: Stage) -> int:
    """Return numeric order for stage comparison."""
    return {
        Stage.SPEC: 0,
        Stage.PLAN: 1,
        Stage.EXECUTION: 2,
        Stage.COMPLETE: 3,
    }[stage]


def _next_stage(stage_name: str) -> Stage:
    """Return the stage that follows the given stage name."""
    return {
        "spec": Stage.PLAN,
        "plan": Stage.EXECUTION,
        "execution": Stage.COMPLETE,
    }[stage_name]
