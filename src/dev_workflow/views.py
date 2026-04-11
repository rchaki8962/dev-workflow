# src/dev_workflow/views.py
"""Markdown view generation from SQLite data.

Generates the task folder as a cache -- wipe and rebuild on each call.
Files follow progressive disclosure: HANDOFF.md has summaries with links,
detail files have full content. No file duplicates another's content.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from dev_workflow.models import Artifact, Checkpoint, Decision, Task, Verification
from dev_workflow.store import Store


def regenerate_task_folder(store: Store, task: Task) -> Path:
    """Regenerate the entire task folder from SQLite.

    1. Wipe existing folder
    2. Create directory structure
    3. Fetch all data in one batch
    4. Generate each file
    Returns path to task folder.
    """
    folder = task.task_folder
    if folder.exists():
        shutil.rmtree(folder)

    folder.mkdir(parents=True)
    (folder / "context").mkdir()
    (folder / "artifacts").mkdir()
    (folder / "record").mkdir()

    checkpoints = store.get_checkpoints(task.task_id)
    decisions = store.get_decisions(task.task_id)
    artifacts = store.get_artifacts(task.task_id)
    verifications = store.get_verifications(task.task_id)

    # Find prompt artifact
    prompt_artifact = store.get_artifact_latest(task.task_id, "original-prompt")

    # Latest checkpoint (highest number)
    latest_cp = checkpoints[-1] if checkpoints else None

    # Latest version of each artifact (excluding prompt)
    latest_artifacts: dict[str, Artifact] = {}
    for a in artifacts:
        if a.name == "original-prompt":
            continue
        if a.name not in latest_artifacts or a.version > latest_artifacts[a.name].version:
            latest_artifacts[a.name] = a

    # Write files
    (folder / "HANDOFF.md").write_text(
        _generate_handoff(task, latest_cp, decisions, latest_artifacts, verifications)
    )

    if prompt_artifact:
        (folder / "context" / "original-prompt.md").write_text(
            _generate_original_prompt(prompt_artifact)
        )

    if latest_cp:
        (folder / "context" / "current-state.md").write_text(
            _generate_current_state(task, latest_cp)
        )

    if decisions:
        (folder / "context" / "decisions.md").write_text(
            _generate_decisions(decisions)
        )

    if latest_cp and latest_cp.open_questions:
        (folder / "context" / "open-questions.md").write_text(
            _generate_open_questions(latest_cp)
        )

    for a in latest_artifacts.values():
        filename = f"{a.type}-{a.name}-v{a.version}.md"
        (folder / "artifacts" / filename).write_text(
            _generate_artifact_file(a)
        )

    if checkpoints:
        (folder / "record" / "checkpoints.md").write_text(
            _generate_checkpoints_log(checkpoints)
        )
        (folder / "record" / "development-record.md").write_text(
            _generate_development_record(task, checkpoints, decisions, verifications)
        )

    return folder


def _generate_handoff(
    task: Task,
    latest_cp: Checkpoint | None,
    decisions: list[Decision],
    latest_artifacts: dict[str, Artifact],
    verifications: list[Verification],
) -> str:
    lines = [f"# {task.title}", ""]
    lines.append(f"**Space:** {task.space}")
    lines.append(f"**Slug:** {task.slug}")

    if latest_cp:
        lines.append(f"**Status:** {latest_cp.milestone}")
        lines.append(f"**Last checkpoint:** #{latest_cp.checkpoint_number} -- {latest_cp.summary}")
    else:
        lines.append("**Status:** initialized")

    lines.append("")

    # User directives
    if latest_cp and latest_cp.user_directives:
        lines.append("## User Directives")
        lines.append("")
        for ud in latest_cp.user_directives:
            lines.append(f"- {ud}")
        lines.append("")

    # Decisions summary (one line each, link to detail)
    if decisions:
        lines.append("## Decisions")
        lines.append("")
        for d in decisions:
            lines.append(f"- **#{d.decision_number}: {d.title}**")
        lines.append("")
        lines.append("See [context/decisions.md](context/decisions.md) for rationale and alternatives.")
        lines.append("")

    # Artifacts index
    if latest_artifacts:
        lines.append("## Artifacts")
        lines.append("")
        for a in latest_artifacts.values():
            filename = f"{a.type}-{a.name}-v{a.version}.md"
            lines.append(f"- [{a.type}: {a.name} (v{a.version})](artifacts/{filename}) -- {a.description}")
        lines.append("")

    # Open questions
    if latest_cp and latest_cp.open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for q in latest_cp.open_questions:
            lines.append(f"- {q}")
        lines.append("")

    # Next steps
    if latest_cp and latest_cp.next_steps:
        lines.append("## Next Steps")
        lines.append("")
        for s in latest_cp.next_steps:
            lines.append(f"- {s}")
        lines.append("")

    # Verification summary
    if verifications:
        latest_verifs = verifications[-3:]  # Last 3
        lines.append("## Recent Verifications")
        lines.append("")
        for v in latest_verifs:
            lines.append(f"- [{v.result}] {v.type}: {v.detail}")
        lines.append("")

    # Links to detail
    lines.append("## Detail")
    lines.append("")
    lines.append("- [Original prompt](context/original-prompt.md)")
    lines.append("- [Current state](context/current-state.md)")
    lines.append("- [Decisions](context/decisions.md)")
    lines.append("- [Open questions](context/open-questions.md)")
    lines.append("- [Development record](record/development-record.md)")
    lines.append("- [Checkpoint log](record/checkpoints.md)")
    lines.append("")

    return "\n".join(lines)


def _generate_original_prompt(prompt_artifact: Artifact) -> str:
    return f"# Original Prompt\n\n{prompt_artifact.content}\n"


def _generate_current_state(task: Task, latest_cp: Checkpoint) -> str:
    lines = ["# Current State", ""]
    lines.append(f"**Milestone:** {latest_cp.milestone}")
    lines.append(f"**Checkpoint:** #{latest_cp.checkpoint_number}")
    lines.append(f"**Summary:** {latest_cp.summary}")
    lines.append("")

    if latest_cp.user_directives:
        lines.append("## User Directives")
        lines.append("")
        for ud in latest_cp.user_directives:
            lines.append(f"- {ud}")
        lines.append("")

    if latest_cp.next_steps:
        lines.append("## Next Steps")
        lines.append("")
        for s in latest_cp.next_steps:
            lines.append(f"- {s}")
        lines.append("")

    if latest_cp.open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for q in latest_cp.open_questions:
            lines.append(f"- {q}")
        lines.append("")

    if latest_cp.insights:
        lines.append("## Insights")
        lines.append("")
        for i in latest_cp.insights:
            lines.append(f"- {i}")
        lines.append("")

    return "\n".join(lines)


def _generate_decisions(decisions: list[Decision]) -> str:
    lines = ["# Decisions", ""]
    for d in decisions:
        lines.append(f"## #{d.decision_number}: {d.title}")
        lines.append("")
        if d.rationale:
            lines.append(f"**Rationale:** {d.rationale}")
            lines.append("")
        if d.alternatives:
            lines.append("**Alternatives considered:**")
            for alt in d.alternatives:
                lines.append(f"- {alt}")
            lines.append("")
        if d.context:
            lines.append(f"**Context:** {d.context}")
            lines.append("")
    return "\n".join(lines)


def _generate_open_questions(latest_cp: Checkpoint) -> str:
    lines = ["# Open Questions", ""]
    for q in latest_cp.open_questions:
        lines.append(f"- {q}")
    lines.append("")
    return "\n".join(lines)


def _generate_artifact_file(artifact: Artifact) -> str:
    lines = [
        f"# {artifact.type}: {artifact.name} (v{artifact.version})",
        "",
        f"*{artifact.description}*" if artifact.description else "",
        "",
        artifact.content,
        "",
    ]
    return "\n".join(lines)


def _generate_checkpoints_log(checkpoints: list[Checkpoint]) -> str:
    lines = ["# Checkpoint Log", ""]
    for cp in checkpoints:
        lines.append(f"## Checkpoint #{cp.checkpoint_number}: {cp.milestone}")
        lines.append("")
        lines.append(f"**Date:** {cp.created.isoformat()}")
        lines.append(f"**Summary:** {cp.summary}")
        lines.append("")
    return "\n".join(lines)


def _generate_development_record(
    task: Task,
    checkpoints: list[Checkpoint],
    decisions: list[Decision],
    verifications: list[Verification],
) -> str:
    lines = [f"# Development Record: {task.title}", ""]

    lines.append("## Intent")
    lines.append("")
    lines.append(f"Task created in space '{task.space}' on {task.created.strftime('%Y-%m-%d')}.")
    lines.append("")

    if decisions:
        lines.append("## Key Decisions")
        lines.append("")
        for d in decisions:
            lines.append(f"- **#{d.decision_number}: {d.title}** -- {d.rationale}")
        lines.append("")
        lines.append("See [decisions.md](../context/decisions.md) for full detail.")
        lines.append("")

    if verifications:
        lines.append("## Verifications")
        lines.append("")
        for v in verifications:
            lines.append(f"- [{v.result}] {v.type}: {v.detail}")
            if v.command:
                lines.append(f"  Command: `{v.command}`")
        lines.append("")

    lines.append("## Checkpoint History")
    lines.append("")
    lines.append(f"{len(checkpoints)} checkpoint(s). See [checkpoints.md](checkpoints.md) for chronological detail.")
    lines.append("")

    return "\n".join(lines)
