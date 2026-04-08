"""Parse approved plan markdown into PlanTask objects."""

import re

from dev_workflow.exceptions import PlanParseError
from dev_workflow.models import PlanTask


def parse_plan(content: str) -> list[PlanTask]:
    """
    Parse an approved plan markdown into a list of PlanTask objects.

    Parser rules:
    - Tasks identified by ### Task N: <title> headings (also accept ## Task N: for leniency)
    - Each task has Description and Verification subsections
    - Dependencies is optional, defaults to empty list
    - Verification steps are "- [ ] <text>" lines
    - Dependencies parsed as comma-separated "Task N" references -> extract integers
    """
    # Split by task headings (## or ### Task N: <title>)
    task_pattern = re.compile(r"^#{2,3}\s+Task\s+(\d+):\s*(.+)$", re.MULTILINE)
    matches = list(task_pattern.finditer(content))

    if not matches:
        raise PlanParseError("No tasks found. Expected headings like '### Task 1: <title>'")

    tasks = []
    for i, match in enumerate(matches):
        task_id = int(match.group(1))
        title = match.group(2).strip()

        # Extract the section content between this heading and the next
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section = content[start:end]

        # Extract description
        description = _extract_section(section, "Description")

        # Extract verification steps
        verification_steps = _extract_verification(section)

        # Extract dependencies
        dependencies = _extract_dependencies(section)

        tasks.append(
            PlanTask(
                id=task_id,
                title=title,
                description=description,
                verification_steps=verification_steps,
                dependencies=dependencies,
            )
        )

    return tasks


def _extract_section(content: str, heading: str) -> str:
    """Extract text under a **Heading:** or bold heading."""
    # Match **Heading:** or **Heading**:\n
    pattern = re.compile(
        rf"\*\*{heading}:?\*\*:?\s*\n(.*?)(?=\n\*\*|\Z)",
        re.DOTALL,
    )
    match = pattern.search(content)
    if match:
        return match.group(1).strip()
    return ""


def _extract_verification(content: str) -> list[str]:
    """Extract verification steps (lines matching - [ ] <text>)."""
    steps = []
    # Find the verification section first
    verif_content = _extract_section(content, "Verification")
    if verif_content:
        for line in verif_content.split("\n"):
            line = line.strip()
            match = re.match(r"^-\s*\[[ x]?\]\s*(.+)$", line)
            if match:
                steps.append(match.group(1).strip())
    return steps


def _extract_dependencies(content: str) -> list[int]:
    """Extract dependency task numbers from Dependencies line."""
    pattern = re.compile(r"\*\*Dependencies:?\*\*:?\s*(.+)", re.IGNORECASE)
    match = pattern.search(content)
    if not match:
        return []

    dep_text = match.group(1).strip().lower()
    if dep_text in ("none", "n/a", "-", ""):
        return []

    # Extract "Task N" references
    dep_ids = re.findall(r"task\s+(\d+)", dep_text, re.IGNORECASE)
    return [int(d) for d in dep_ids]
