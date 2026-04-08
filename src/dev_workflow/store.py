"""TaskStore protocol and FileTaskStore implementation."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from dev_workflow.models import (
    Task, TaskProgress, Subtask, SubtaskEntry, Spec, Plan, PlanTask,
    Review, ActivityEntry, VerificationStep,
    Stage, SubtaskStatus, ReviewVerdict,
)
from dev_workflow.state import StateManager
from dev_workflow.progress import parse_progress
from dev_workflow.templates import render_progress, render_subtask, render_review, render_review_template
from dev_workflow.exceptions import TaskNotFoundError


class TaskStore(Protocol):
    def save_task(self, task: Task) -> None: ...
    def load_task(self, slug: str) -> Task: ...
    def list_tasks(self) -> list[Task]: ...
    def search_tasks(self, query: str) -> list[Task]: ...
    def delete_task(self, slug: str) -> None: ...
    def save_progress(self, task_id: str, progress: TaskProgress) -> None: ...
    def load_progress(self, task_id: str) -> TaskProgress: ...
    def save_subtask(self, task_id: str, subtask: Subtask) -> None: ...
    def load_subtask(self, task_id: str, subtask_id: int) -> Subtask: ...
    def list_subtasks(self, task_id: str) -> list[SubtaskEntry]: ...
    def save_spec(self, task_id: str, spec: Spec) -> None: ...
    def load_spec(self, task_id: str, version: int) -> Spec: ...
    def save_plan(self, task_id: str, plan: Plan) -> None: ...
    def load_plan(self, task_id: str, version: int) -> Plan: ...
    def save_review(self, task_id: str, review: Review) -> None: ...
    def load_review(self, task_id: str, stage: str, version: int) -> Review: ...
    def append_activity(self, task_id: str, entry: ActivityEntry) -> None: ...


class FileTaskStore:
    """V1 implementation: markdown files + JSON state registry."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.state = StateManager(base_dir / "state")
        self.tasks_dir = base_dir / "tasks"

    def _task_dir(self, task_id: str) -> Path:
        return self.tasks_dir / task_id

    # --- Task (delegates to StateManager) ---
    def save_task(self, task: Task) -> None:
        self.state.save(task)

    def load_task(self, slug: str) -> Task:
        return self.state.load(slug)

    def list_tasks(self) -> list[Task]:
        return self.state.list_all()

    def search_tasks(self, query: str) -> list[Task]:
        return self.state.search(query)

    def delete_task(self, slug: str) -> None:
        self.state.delete(slug)

    # --- Progress ---
    def save_progress(self, task_id: str, progress: TaskProgress) -> None:
        path = self._task_dir(task_id) / "00-progress.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_progress(progress))

    def load_progress(self, task_id: str) -> TaskProgress:
        path = self._task_dir(task_id) / "00-progress.md"
        if not path.exists():
            raise FileNotFoundError(f"Progress file not found: {path}")
        return parse_progress(path.read_text())

    # --- Subtasks ---
    def save_subtask(self, task_id: str, subtask: Subtask) -> None:
        path = self._task_dir(task_id) / "30-execution" / f"subtask-{subtask.id:02d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_subtask(subtask))

    def load_subtask(self, task_id: str, subtask_id: int) -> Subtask:
        path = self._task_dir(task_id) / "30-execution" / f"subtask-{subtask_id:02d}.md"
        if not path.exists():
            raise FileNotFoundError(f"Subtask file not found: {path}")
        return _parse_subtask(path.read_text(), subtask_id)

    def list_subtasks(self, task_id: str) -> list[SubtaskEntry]:
        exec_dir = self._task_dir(task_id) / "30-execution"
        if not exec_dir.exists():
            return []
        entries = []
        for path in sorted(exec_dir.glob("subtask-*.md")):
            match = re.match(r"subtask-(\d+)\.md", path.name)
            if match:
                subtask_id = int(match.group(1))
                subtask = _parse_subtask(path.read_text(), subtask_id)
                entries.append(SubtaskEntry(
                    id=subtask.id,
                    title=subtask.title,
                    status=subtask.status,
                    file_path=Path(f"30-execution/{path.name}"),
                ))
        return entries

    # --- Spec ---
    def save_spec(self, task_id: str, spec: Spec) -> None:
        path = self._task_dir(task_id) / "10-spec" / f"spec-v{spec.version}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec.raw_content if spec.raw_content else _render_spec_content(spec))

    def load_spec(self, task_id: str, version: int) -> Spec:
        path = self._task_dir(task_id) / "10-spec" / f"spec-v{version}.md"
        if not path.exists():
            raise FileNotFoundError(f"Spec file not found: {path}")
        content = path.read_text()
        return _parse_spec(content, version)

    # --- Plan ---
    def save_plan(self, task_id: str, plan: Plan) -> None:
        path = self._task_dir(task_id) / "20-plan" / f"plan-v{plan.version}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan.raw_content if plan.raw_content else "")

    def load_plan(self, task_id: str, version: int) -> Plan:
        path = self._task_dir(task_id) / "20-plan" / f"plan-v{version}.md"
        if not path.exists():
            raise FileNotFoundError(f"Plan file not found: {path}")
        content = path.read_text()
        return _parse_plan_metadata(content, version)

    # --- Review ---
    def save_review(self, task_id: str, review: Review) -> None:
        stage_dirs = {"spec": "10-spec", "plan": "20-plan", "execution": "30-execution"}
        subdir = stage_dirs.get(review.stage, "10-spec")
        path = self._task_dir(task_id) / subdir / f"{review.stage}-review-v{review.version}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_review(review))

    def load_review(self, task_id: str, stage: str, version: int) -> Review:
        stage_dirs = {"spec": "10-spec", "plan": "20-plan", "execution": "30-execution"}
        subdir = stage_dirs.get(stage, "10-spec")
        path = self._task_dir(task_id) / subdir / f"{stage}-review-v{version}.md"
        if not path.exists():
            raise FileNotFoundError(f"Review file not found: {path}")
        # For V1, just return a Review with raw content; full parsing deferred
        return Review(stage=stage, version=version, verdict=ReviewVerdict.APPROVE)

    # --- Activity Log ---
    def append_activity(self, task_id: str, entry: ActivityEntry) -> None:
        path = self._task_dir(task_id) / "90-logs" / "activity-log.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = f"- [{entry.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')}] {entry.action}: {entry.detail}\n"
        with open(path, "a") as f:
            f.write(line)

    def load_activity_log(self, task_id: str) -> list[ActivityEntry]:
        """Load all activity entries from the log file."""
        path = self._task_dir(task_id) / "90-logs" / "activity-log.md"
        if not path.exists():
            return []
        entries = []
        for line in path.read_text().split("\n"):
            line = line.strip()
            match = re.match(r'^-\s*\[(.+?)\]\s*(.+?):\s*(.+)$', line)
            if match:
                ts = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
                entries.append(ActivityEntry(
                    timestamp=ts,
                    action=match.group(2).strip(),
                    detail=match.group(3).strip(),
                ))
        return entries


# ---------------------------------------------------------------------------
# Private parsing helpers
# ---------------------------------------------------------------------------


def _extract_md_section(content: str, heading: str) -> str:
    """Extract content under a ## or ### heading until the next heading of same or higher level."""
    pattern = re.compile(
        rf'^(#{{2,3}})\s+{re.escape(heading)}\s*\n(.*?)(?=\n#{{2,3}}\s|\Z)',
        re.MULTILINE | re.DOTALL
    )
    match = pattern.search(content)
    return match.group(2).strip() if match else ""


def _parse_subtask(content: str, subtask_id: int) -> Subtask:
    """Parse a subtask markdown file back into a Subtask dataclass."""
    # Title from first heading: # Subtask N: <title>
    title_match = re.search(r'^#\s+Subtask\s+\d+:\s*(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract sections
    description = _extract_md_section(content, "Description")
    status_str = _extract_md_section(content, "Status").strip()
    execution_summary = _extract_md_section(content, "Execution Summary")
    what_changed = _extract_md_section(content, "What Changed")

    # Verification steps
    verif_section = _extract_md_section(content, "Verification")
    verification = []
    for line in verif_section.split("\n"):
        line = line.strip()
        match = re.match(r'^-\s*\[([ x])\]\s*(.+)$', line)
        if match:
            verification.append(VerificationStep(
                description=match.group(2).strip(),
                checked=match.group(1) == "x",
            ))

    # Files changed
    files_section = _extract_md_section(content, "Files Changed")
    files_changed = []
    for line in files_section.split("\n"):
        line = line.strip()
        if line.startswith("- ") and line[2:].strip() != "(none)":
            files_changed.append(line[2:].strip())

    # Blockers
    blockers_section = _extract_md_section(content, "Blockers")
    blockers = []
    for line in blockers_section.split("\n"):
        line = line.strip()
        if line.startswith("- ") and line[2:].strip() != "(none)":
            blockers.append(line[2:].strip())

    # Parse status
    try:
        status = SubtaskStatus(status_str)
    except ValueError:
        status = SubtaskStatus.NOT_STARTED

    # Clean up "(not yet completed)" placeholders
    if execution_summary == "(not yet completed)":
        execution_summary = None
    if what_changed == "(not yet completed)":
        what_changed = None

    return Subtask(
        id=subtask_id,
        title=title,
        description=description,
        verification=verification,
        status=status,
        execution_summary=execution_summary or None,
        files_changed=files_changed,
        what_changed=what_changed or None,
        blockers=blockers,
    )


def _parse_spec(content: str, version: int) -> Spec:
    """Parse spec markdown into Spec dataclass. Extracts structured fields from raw content."""
    title_match = re.search(r'^#\s+(?:Spec:\s*)?(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    overview = _extract_md_section(content, "Overview")

    requirements = []
    req_section = _extract_md_section(content, "Requirements")
    for line in req_section.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            requirements.append(line[2:].strip())

    constraints = []
    con_section = _extract_md_section(content, "Constraints")
    for line in con_section.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            constraints.append(line[2:].strip())

    open_questions = []
    oq_section = _extract_md_section(content, "Open Questions")
    for line in oq_section.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            open_questions.append(line[2:].strip())

    return Spec(
        version=version,
        title=title,
        overview=overview,
        requirements=requirements,
        constraints=constraints,
        open_questions=open_questions,
        raw_content=content,
    )


def _render_spec_content(spec: Spec) -> str:
    """Render a Spec to markdown when raw_content is not available."""
    lines = [f"# Spec: {spec.title}", ""]
    lines += ["## Overview", spec.overview, ""]
    lines += ["## Requirements"]
    for r in spec.requirements:
        lines.append(f"- {r}")
    lines += ["", "## Constraints"]
    for c in spec.constraints:
        lines.append(f"- {c}")
    lines += ["", "## Open Questions"]
    for q in spec.open_questions:
        lines.append(f"- {q}")
    lines.append("")
    return "\n".join(lines)


def _parse_plan_metadata(content: str, version: int) -> Plan:
    """Parse plan markdown into Plan dataclass (metadata only, not full task decomposition)."""
    title_match = re.search(r'^#\s+(?:Implementation Plan:\s*)?(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    spec_match = re.search(r'\*\*Approved Spec\*\*:\s*(.+)$', content, re.MULTILINE)
    spec_path = Path(spec_match.group(1).strip()) if spec_match else Path("")

    approach = _extract_md_section(content, "Approach")

    risks = []
    risks_section = _extract_md_section(content, "Risks")
    for line in risks_section.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            risks.append(line[2:].strip())

    # For full task parsing, use plan_parser.py separately
    from dev_workflow.plan_parser import parse_plan
    tasks = parse_plan(content)

    return Plan(
        version=version,
        title=title,
        spec_path=spec_path,
        approach=approach,
        tasks=tasks,
        risks=risks,
        raw_content=content,
    )
