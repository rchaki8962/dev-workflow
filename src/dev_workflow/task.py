"""Task lifecycle: create, list, search, switch, info."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.config import Config
from dev_workflow.models import (
    Task,
    TaskProgress,
    ActivityEntry,
    Stage,
)
from dev_workflow.store import FileTaskStore
from dev_workflow.slug import generate_slug, generate_task_id


class TaskManager:
    def __init__(self, store: FileTaskStore, config: Config):
        self.store = store
        self.config = config

    def create_task(
        self,
        title: str,
        workspaces: list[Path] | None = None,
        slug_override: str | None = None,
        prompt: str | None = None,
        prompt_file: Path | None = None,
    ) -> Task:
        """
        Create a new task with full folder scaffolding.

        1. Generate task_id and slug (or use override)
        2. Create task folder with subdirectories
        3. Render and write 00-progress.md
        4. Create 01-original-prompt.md
        5. Initialize 90-logs/activity-log.md
        6. Save state JSON
        7. Return Task
        """
        now = datetime.now(timezone.utc)

        # Generate identifiers
        task_id = generate_task_id(title, date=now)
        # Handle task_id collision
        existing_ids = [t.task_id for t in self.store.list_tasks()]
        base_id = task_id
        counter = 2
        while task_id in existing_ids:
            task_id = f"{base_id}-{counter}"
            counter += 1

        if slug_override:
            slug = slug_override
        else:
            existing_slugs = self.store.state.all_slugs()
            slug = generate_slug(title, self.config.strip_words, existing_slugs)

        workspaces = workspaces or [Path.cwd()]
        task_folder = self.config.tasks_dir / task_id

        task = Task(
            task_id=task_id,
            slug=slug,
            title=title,
            summary="",
            stage=Stage.SPEC,
            workspaces=workspaces,
            task_folder=task_folder,
            created=now,
            updated=now,
            space=self.config._active_space,
        )

        # Create folder structure
        task_folder.mkdir(parents=True, exist_ok=True)
        (task_folder / "10-spec").mkdir(exist_ok=True)
        (task_folder / "20-plan").mkdir(exist_ok=True)
        (task_folder / "30-execution").mkdir(exist_ok=True)
        (task_folder / "90-logs").mkdir(exist_ok=True)

        # Write 00-progress.md
        progress = TaskProgress(task=task)
        self.store.save_progress(task_id, progress)

        # Write 01-original-prompt.md
        prompt_path = task_folder / "01-original-prompt.md"
        prompt_content = ""
        if prompt:
            prompt_content = prompt
        elif prompt_file and prompt_file.exists():
            prompt_content = prompt_file.read_text()
        prompt_path.write_text(prompt_content)

        # Initialize activity log
        self.store.append_activity(
            task_id,
            ActivityEntry(
                timestamp=now,
                action="Task created",
                detail=f"Title: {title}, Slug: {slug}",
            ),
        )

        # Save state JSON
        self.store.save_task(task)

        return task

    def list_tasks(self, stage_filter: Stage | None = None) -> list[Task]:
        """List all tasks, optionally filtered by stage."""
        return self.store.state.list_all(stage_filter=stage_filter)

    def search_tasks(self, query: str) -> list[Task]:
        """Search tasks by substring match on slug, title, summary."""
        return self.store.search_tasks(query)

    def get_task_info(self, slug: str) -> Task:
        """Get task info by slug. Raises TaskNotFoundError if not found."""
        return self.store.load_task(slug)

    def switch_task(self, slug: str) -> str:
        """
        Load task context for a session: progress + spec summary + plan summary.
        Returns concatenated text for Claude to ingest.
        """
        task = self.store.load_task(slug)
        task_dir = self.config.tasks_dir / task.task_id

        sections = []

        # Always include progress file
        progress_path = task_dir / "00-progress.md"
        if progress_path.exists():
            sections.append(f"## Progress\n\n{progress_path.read_text()}")

        # Spec summary (not full text)
        spec_approved = task_dir / "10-spec" / "spec-approved.md"
        if spec_approved.exists():
            content = spec_approved.read_text()
            # Extract title and overview only
            summary = _extract_summary(content, ["Overview", "Requirements"])
            sections.append(f"## Spec Summary\n\n{summary}")

        # Plan summary (subtask titles and statuses, not full descriptions)
        plan_approved = task_dir / "20-plan" / "plan-approved.md"
        if plan_approved.exists():
            content = plan_approved.read_text()
            # Extract just the task list titles
            summary = _extract_plan_summary(content)
            sections.append(f"## Plan Summary\n\n{summary}")

        return "\n\n---\n\n".join(sections)


def _extract_summary(content: str, sections: list[str]) -> str:
    """Extract title and specified sections from markdown for a brief summary."""
    lines = []

    # Get title
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        lines.append(f"**{title_match.group(1).strip()}**\n")

    for section_name in sections:
        pattern = re.compile(
            rf"^##\s+{re.escape(section_name)}\s*\n(.*?)(?=\n##\s|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(content)
        if match:
            lines.append(f"### {section_name}\n{match.group(1).strip()}\n")

    return "\n".join(lines)


def _extract_plan_summary(content: str) -> str:
    """Extract task titles from a plan for a brief summary."""
    lines = []

    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        lines.append(f"**{title_match.group(1).strip()}**\n")

    # Find all task headings
    task_pattern = re.compile(r"^#{2,3}\s+Task\s+(\d+):\s*(.+)$", re.MULTILINE)
    for match in task_pattern.finditer(content):
        lines.append(f"- Task {match.group(1)}: {match.group(2).strip()}")

    return "\n".join(lines)
