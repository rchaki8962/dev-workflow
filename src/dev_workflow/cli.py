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
        "workspaces": [str(w) for w in task.workspaces],
        "task_folder": str(task.task_folder),
        "created": task.created.isoformat(),
        "updated": task.updated.isoformat(),
    }


def _print_task_table(task: Task) -> None:
    """Print a single task as a human-readable block."""
    click.echo(f"Task:    {task.title}")
    click.echo(f"Slug:    {task.slug}")
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
@click.pass_context
def main(ctx: click.Context, base_dir: str | None) -> None:
    """dev-workflow: Durable multi-session task management for coding agents."""
    ctx.ensure_object(dict)
    config = load_config(base_dir_override=base_dir)
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
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_tasks(ctx: click.Context, stage: str | None, output_format: str) -> None:
    """List all tasks."""
    config = ctx.obj["config"]
    store = FileTaskStore(config.space_dir)
    manager = TaskManager(store, config)

    stage_filter = Stage(stage) if stage else None

    try:
        tasks = manager.list_tasks(stage_filter=stage_filter)
    except DevWorkflowError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(json.dumps([_task_to_json_dict(t) for t in tasks], indent=2))
    else:
        _print_task_list_table(tasks)


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
