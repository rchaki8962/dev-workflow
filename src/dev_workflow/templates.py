"""Template rendering: dataclasses → markdown."""

from pathlib import Path
from dev_workflow.models import (
    TaskProgress, Subtask, Review, SubtaskEntry, ActivityEntry, VerificationStep
)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    """Load a template file from the templates directory."""
    return (TEMPLATES_DIR / name).read_text()


def render_progress(progress: TaskProgress) -> str:
    """Render a full 00-progress.md from a TaskProgress dataclass."""
    # Format workspace list
    workspaces = "\n".join(f"- {ws}" for ws in progress.task.workspaces) or "- (none)"

    # Format subtask index table rows
    subtask_rows = ""
    for entry in progress.subtask_index:
        subtask_rows += f"| {entry.id} | {entry.title} | {entry.status.value} | {entry.file_path} |\n"

    # Format blockers
    blockers = "\n".join(f"- {b}" for b in progress.blockers) or "(none)"

    # Format recent activity
    recent = ""
    for act in progress.recent_activity:
        recent += f"- [{act.timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')}] {act.action}: {act.detail}\n"
    recent = recent or "(none)"

    # Format next actions
    next_actions = "\n".join(f"- {a}" for a in progress.next_actions) or "(none)"

    template = _load_template("progress.md")
    return template.format(
        title=progress.task.title,
        task_id=progress.task.task_id,
        stage=progress.task.stage.value,
        approved_spec=progress.approved_spec or "pending",
        approved_plan=progress.approved_plan or "pending",
        updated=progress.task.updated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        workspaces=workspaces,
        stage_status=f"Currently in **{progress.task.stage.value}** stage.",
        subtask_rows=subtask_rows,
        blockers=blockers,
        recent_activity=recent,
        next_actions=next_actions,
    )


def render_subtask(subtask: Subtask) -> str:
    """Render a subtask-NN.md from a Subtask dataclass."""
    # Format verification checklist
    verification = ""
    for step in subtask.verification:
        check = "x" if step.checked else " "
        verification += f"- [{check}] {step.description}\n"
    verification = verification or "(none)"

    # Format files changed
    files_changed = "\n".join(f"- {f}" for f in subtask.files_changed) or "(none)"

    # Format blockers
    blockers = "\n".join(f"- {b}" for b in subtask.blockers) or "(none)"

    template = _load_template("subtask.md")
    return template.format(
        id=subtask.id,
        title=subtask.title,
        description=subtask.description,
        verification=verification,
        status=subtask.status.value,
        execution_summary=subtask.execution_summary or "(not yet completed)",
        files_changed=files_changed,
        what_changed=subtask.what_changed or "(not yet completed)",
        blockers=blockers,
    )


def render_review_template(stage: str, version: int, inputs: list[str]) -> str:
    """Render an empty review template (seeded for the reviewer to fill in)."""
    inputs_read = "\n".join(f"- {i}" for i in inputs) or "(none)"

    template = _load_template("review.md")
    return template.format(
        stage=stage.capitalize(),
        verdict="(pending)",
        inputs_read=inputs_read,
        critical="(none)",
        important="(none)",
        minor="(none)",
        required_revisions="(none)",
        residual_risks="(none)",
    )


def render_review(review: Review) -> str:
    """Render a completed review file from a Review dataclass."""
    template = _load_template("review.md")
    return template.format(
        stage=review.stage.capitalize(),
        verdict=review.verdict.value.upper(),
        inputs_read="\n".join(f"- {i}" for i in review.inputs_read) or "(none)",
        critical="\n".join(f"- {c}" for c in review.critical) or "(none)",
        important="\n".join(f"- {i}" for i in review.important) or "(none)",
        minor="\n".join(f"- {m}" for m in review.minor) or "(none)",
        required_revisions="\n".join(f"- {r}" for r in review.required_revisions) or "(none)",
        residual_risks="\n".join(f"- {r}" for r in review.residual_risks) or "(none)",
    )
