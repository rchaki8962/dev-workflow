"""Click CLI: thin wiring layer delegating to TaskManager and StageManager."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import click

from dev_workflow.config import load_config
from dev_workflow.exceptions import DevWorkflowError
from dev_workflow.models import Stage, Task
from dev_workflow.space import SpaceManager
from dev_workflow.stage import StageManager
from dev_workflow.store import FileTaskStore
from dev_workflow.task import TaskManager


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _task_to_json_dict(task: Task) -> dict:
    """Convert a Task to a JSON-serialisable dict."""
    return {
        "task_id": task.task_id,
        "slug": task.slug,
        "title": task.title,
        "summary": task.summary,
        "stage": task.stage.value,
        "space": task.space,
        "workspaces": [str(w) for w in task.workspaces],
        "task_folder": str(task.task_folder),
        "created": task.created.isoformat(),
        "updated": task.updated.isoformat(),
    }


def _print_task_table(task: Task) -> None:
    """Print a single task as a human-readable block."""
    click.echo(f"Task:    {task.title}")
    click.echo(f"Slug:    {task.slug}")
    click.echo(f"Space:   {task.space}")
    click.echo(f"ID:      {task.task_id}")
    click.echo(f"Stage:   {task.stage.value}")
    click.echo(f"Folder:  {task.task_folder}")
    click.echo(f"Created: {task.created.isoformat()}")


def _print_task_list_table(tasks: list[Task]) -> None:
    """Print a list of tasks as a human-readable table."""
    if not tasks:
        click.echo("No tasks found.")
        return
    for task in tasks:
        click.echo(f"  {task.slug:<25s} {task.stage.value:<12s} {task.title}")


# ---------------------------------------------------------------------------
# Top-level group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--base-dir",
    envvar="DEV_WORKFLOW_DIR",
    default=None,
    help="Override base directory",
)
@click.option(
    "--space",
    "space_name",
    envvar="DEV_WORKFLOW_SPACE",
    default=None,
    help="Active space",
)
@click.pass_context
def main(ctx: click.Context, base_dir: str | None, space_name: str | None) -> None:
    """dev-workflow: Durable multi-session task management for coding agents."""
    ctx.ensure_object(dict)
    config = load_config(base_dir_override=base_dir, space_override=space_name)
    sm = SpaceManager(config.base_dir)
    sm.ensure(config._active_space)
    ctx.obj["config"] = config


# ---------------------------------------------------------------------------
# task group
# ---------------------------------------------------------------------------


@main.group()
def task() -> None:
    """Manage tasks."""


@task.command()
@click.argument("title")
@click.option("--workspace", multiple=True, help="Workspace directories")
@click.option("--slug", default=None, help="Custom slug override")
@click.option("--prompt", default=None, help="Inline prompt text")
@click.option(
    "--prompt-file", default=None, type=click.Path(exists=True), help="Path to prompt file"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def start(
    ctx: click.Context,
    title: str,
    workspace: tuple[str, ...],
    slug: str | None,
    prompt: str | None,
    prompt_file: str | None,
    output_format: str,
) -> None:
    """Create a new task."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)

    workspaces = [Path(w) for w in workspace] if workspace else None
    pf = Path(prompt_file) if prompt_file else None

    try:
        t = manager.create_task(
            title=title,
            workspaces=workspaces,
            slug_override=slug,
            prompt=prompt,
            prompt_file=pf,
        )
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps(_task_to_json_dict(t), indent=2))
    else:
        _print_task_table(t)


@task.command("list")
@click.option("--stage", default=None, help="Filter by stage")
@click.option("--all-spaces", "all_spaces", is_flag=True, help="List tasks across all spaces")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_tasks(ctx: click.Context, stage: str | None, all_spaces: bool, output_format: str) -> None:
    """List all tasks."""
    config = ctx.obj["config"]
    stage_filter = Stage(stage) if stage else None

    if all_spaces:
        sm = SpaceManager(config.base_dir)
        all_tasks = []
        for s in sm.list_all():
            store = FileTaskStore(config.base_dir / s.name)
            tasks = store.state.list_all(stage_filter=stage_filter)
            all_tasks.extend(tasks)
        all_tasks.sort(key=lambda t: t.updated, reverse=True)
    else:
        store = FileTaskStore(config.space_dir)
        manager = TaskManager(store, config)
        all_tasks = manager.list_tasks(stage_filter=stage_filter)

    if output_format == "json":
        click.echo(json.dumps([_task_to_json_dict(t) for t in all_tasks], indent=2))
    else:
        if not all_tasks:
            click.echo("No tasks found.")
            return
        if all_spaces:
            for t in all_tasks:
                click.echo(f"  [{t.space}]  {t.slug:<25s} {t.stage.value:<12s} {t.title}")
        else:
            _print_task_list_table(all_tasks)


@task.command()
@click.argument("query")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def search(ctx: click.Context, query: str, output_format: str) -> None:
    """Search tasks by query."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)

    try:
        tasks = manager.search_tasks(query)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps([_task_to_json_dict(t) for t in tasks], indent=2))
    else:
        _print_task_list_table(tasks)


@task.command()
@click.argument("slug")
@click.pass_context
def switch(ctx: click.Context, slug: str) -> None:
    """Switch to a task (load context)."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)

    try:
        context = manager.switch_task(slug)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(context)


@task.command()
@click.argument("slug")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def info(ctx: click.Context, slug: str, output_format: str) -> None:
    """Show info for a task."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)

    try:
        t = manager.get_task_info(slug)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps(_task_to_json_dict(t), indent=2))
    else:
        _print_task_table(t)


# ---------------------------------------------------------------------------
# stage group
# ---------------------------------------------------------------------------


@main.group()
def stage() -> None:
    """Manage stage lifecycle."""


@stage.command("setup")
@click.argument("stage_name", type=click.Choice(["spec", "plan", "execution"]))
@click.option("--task", "task_slug", required=True, help="Task slug")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def stage_setup(
    ctx: click.Context, stage_name: str, task_slug: str, output_format: str
) -> None:
    """Set up a stage for a task."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = StageManager(store, config)

    try:
        result = manager.setup(task_slug, stage_name)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Stage '{stage_name}' set up for task '{task_slug}'.")
        for key, value in result.items():
            click.echo(f"  {key}: {value}")


@stage.command("teardown")
@click.argument("stage_name", type=click.Choice(["spec", "plan", "execution"]))
@click.option("--task", "task_slug", required=True, help="Task slug")
@click.pass_context
def stage_teardown(ctx: click.Context, stage_name: str, task_slug: str) -> None:
    """Tear down a stage for a task."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = StageManager(store, config)

    try:
        manager.teardown(task_slug, stage_name)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Stage '{stage_name}' teardown complete for task '{task_slug}'.")


@stage.command("status")
@click.option("--task", "task_slug", required=True, help="Task slug")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def stage_status(ctx: click.Context, task_slug: str, output_format: str) -> None:
    """Show stage status for a task."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    tm = TaskManager(store, config)

    try:
        t = tm.get_task_info(task_slug)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps({"slug": t.slug, "stage": t.stage.value}, indent=2))
    else:
        click.echo(f"Task '{t.slug}' is at stage: {t.stage.value}")


# ---------------------------------------------------------------------------
# review group
# ---------------------------------------------------------------------------


@main.group()
def review() -> None:
    """Manage reviews."""


@review.command("setup")
@click.argument("stage_name", type=click.Choice(["spec", "plan", "execution"]))
@click.option("--task", "task_slug", required=True, help="Task slug")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def review_setup(
    ctx: click.Context, stage_name: str, task_slug: str, output_format: str
) -> None:
    """Set up a review for a stage."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = StageManager(store, config)

    try:
        result = manager.review_setup(task_slug, stage_name)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Review set up for stage '{stage_name}' on task '{task_slug}'.")
        for key, value in result.items():
            click.echo(f"  {key}: {value}")


@review.command("approve")
@click.argument("stage_name", type=click.Choice(["spec", "plan", "execution"]))
@click.option("--task", "task_slug", required=True, help="Task slug")
@click.pass_context
def review_approve(ctx: click.Context, stage_name: str, task_slug: str) -> None:
    """Approve a review for a stage."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = StageManager(store, config)

    try:
        manager.review_approve(task_slug, stage_name)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Stage '{stage_name}' approved for task '{task_slug}'.")


# ---------------------------------------------------------------------------
# space group
# ---------------------------------------------------------------------------


@main.group()
def space() -> None:
    """Manage spaces."""


@space.command("create")
@click.argument("name")
@click.option("--description", default="", help="Space description")
@click.pass_context
def space_create(ctx: click.Context, name: str, description: str) -> None:
    """Create a new space."""
    config = ctx.obj["config"]
    sm = SpaceManager(config.base_dir)
    try:
        s = sm.create(name, description)
    except (ValueError, DevWorkflowError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Space '{s.name}' created.")


@space.command("list")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
@click.pass_context
def space_list(ctx: click.Context, output_format: str) -> None:
    """List all spaces."""
    config = ctx.obj["config"]
    sm = SpaceManager(config.base_dir)
    spaces = sm.list_all()

    if output_format == "json":
        result = []
        for s in spaces:
            state_dir = config.base_dir / s.name / "state"
            task_count = len(list(state_dir.glob("*.json"))) if state_dir.exists() else 0
            result.append({
                "name": s.name,
                "description": s.description,
                "created": s.created.isoformat(),
                "task_count": task_count,
            })
        click.echo(json.dumps(result, indent=2))
    else:
        if not spaces:
            click.echo("No spaces found.")
            return
        for s in spaces:
            state_dir = config.base_dir / s.name / "state"
            task_count = len(list(state_dir.glob("*.json"))) if state_dir.exists() else 0
            task_label = "task" if task_count == 1 else "tasks"
            click.echo(f"  {s.name:<20s} {s.description:<30s} {task_count} {task_label}")


@space.command("remove")
@click.argument("name")
@click.option("--force", is_flag=True, help="Remove even if space has tasks")
@click.pass_context
def space_remove(ctx: click.Context, name: str, force: bool) -> None:
    """Remove a space."""
    config = ctx.obj["config"]
    sm = SpaceManager(config.base_dir)
    try:
        sm.remove(name, force=force)
    except (ValueError, DevWorkflowError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"Space '{name}' removed.")


@space.command("info")
@click.argument("name")
@click.option("--format", "output_format", type=click.Choice(["json", "table"]), default="table")
@click.pass_context
def space_info(ctx: click.Context, name: str, output_format: str) -> None:
    """Show info for a space."""
    config = ctx.obj["config"]
    sm = SpaceManager(config.base_dir)
    try:
        s = sm.get(name)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    state_dir = config.base_dir / s.name / "state"
    task_count = len(list(state_dir.glob("*.json"))) if state_dir.exists() else 0

    if output_format == "json":
        click.echo(json.dumps({
            "name": s.name,
            "description": s.description,
            "created": s.created.isoformat(),
            "task_count": task_count,
        }, indent=2))
    else:
        click.echo(f"Name:        {s.name}")
        click.echo(f"Description: {s.description}")
        click.echo(f"Created:     {s.created.isoformat()}")
        click.echo(f"Tasks:       {task_count}")
