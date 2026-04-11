# src/dev_workflow/cli.py
"""Click CLI entry point.

Thin wrappers over domain functions. All output is JSON to stdout.
Errors go to stderr as plain text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from dev_workflow.config import load_config, resolve_space
from dev_workflow.errors import DevWorkflowError
from dev_workflow.store import Store


@click.group()
@click.option("--space", default=None, help="Override active space")
@click.option(
    "--base-dir",
    default=None,
    type=click.Path(),
    help="Override base directory",
)
@click.pass_context
def cli(ctx: click.Context, space: str | None, base_dir: str | None) -> None:
    """dev-workflow: checkpoint-oriented task continuity."""
    config = load_config()
    if base_dir:
        config.base_dir = Path(base_dir)
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["space"] = resolve_space(space, config)
    ctx.obj["store"] = Store(config.base_dir / "store.db")


@cli.result_callback()
@click.pass_context
def cleanup(ctx: click.Context, *args, **kwargs) -> None:
    store = ctx.obj.get("store")
    if store:
        store.close()


def _handle_error(fn):
    """Decorator for CLI commands to catch domain errors."""
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        try:
            return ctx.invoke(fn, *args, **kwargs)
        except DevWorkflowError as e:
            click.echo(str(e), err=True)
            raise SystemExit(1)
        except Exception as e:
            click.echo(f"Internal error: {e}", err=True)
            raise SystemExit(2)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# --- Space commands ---

@cli.group()
def space() -> None:
    """Manage spaces."""


@space.command("create")
@click.argument("name")
@click.option("--description", default="", help="Space description")
@click.pass_context
def space_create(ctx: click.Context, name: str, description: str) -> None:
    """Create a new space."""
    try:
        from dev_workflow.space import create_space as do_create
        s = do_create(ctx.obj["store"], name, description)
        click.echo(json.dumps({"name": s.name, "message": f"Space '{s.name}' created"}))
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@space.command("list")
@click.pass_context
def space_list(ctx: click.Context) -> None:
    """List all spaces."""
    from dev_workflow.space import list_spaces as do_list
    spaces = do_list(ctx.obj["store"])
    result = [
        {"name": s.name, "description": s.description, "created": s.created.isoformat()}
        for s in spaces
    ]
    click.echo(json.dumps(result, indent=2))


@space.command("remove")
@click.argument("name")
@click.pass_context
def space_remove(ctx: click.Context, name: str) -> None:
    """Remove a space (fails if tasks exist)."""
    try:
        from dev_workflow.space import remove_space as do_remove
        do_remove(ctx.obj["store"], name)
        click.echo(json.dumps({"name": name, "message": f"Space '{name}' removed"}))
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@space.command("info")
@click.argument("name")
@click.pass_context
def space_info(ctx: click.Context, name: str) -> None:
    """Show space details."""
    try:
        from dev_workflow.space import get_space_info
        info = get_space_info(ctx.obj["store"], name)
        click.echo(json.dumps(info, indent=2))
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


# --- Core commands ---

@cli.command()
@click.argument("title")
@click.option("--prompt", default=None, help="Original task prompt")
@click.option(
    "--workspace",
    multiple=True,
    type=click.Path(),
    help="Workspace paths (can be repeated)",
)
@click.pass_context
def init(ctx: click.Context, title: str, prompt: str | None, workspace: tuple[str, ...]) -> None:
    """Initialize a new task."""
    try:
        from dev_workflow.task import init_task
        task = init_task(
            ctx.obj["store"],
            ctx.obj["config"].base_dir,
            title,
            ctx.obj["space"],
            prompt=prompt,
            workspaces=list(workspace) if workspace else None,
        )
        click.echo(json.dumps({
            "slug": task.slug,
            "task_id": task.task_id,
            "task_folder": str(task.task_folder),
        }))
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("slug")
@click.option(
    "--payload",
    type=click.Path(exists=True),
    default=None,
    help="Path to JSON payload file (reads stdin if not provided)",
)
@click.pass_context
def checkpoint(ctx: click.Context, slug: str, payload: str | None) -> None:
    """Save a checkpoint for a task."""
    try:
        from dev_workflow.checkpoint import create_checkpoint
        from dev_workflow.models import CheckpointPayload
        from dev_workflow.task import get_task

        task = get_task(ctx.obj["store"], slug, ctx.obj["space"])

        if payload:
            raw = Path(payload).read_text()
        else:
            raw = sys.stdin.read()

        data = json.loads(raw)
        cp_payload = CheckpointPayload(
            milestone=data["milestone"],
            summary=data["summary"],
            decisions=data.get("decisions"),
            artifacts=data.get("artifacts"),
            verifications=data.get("verifications"),
            user_directives=data.get("user_directives"),
            insights=data.get("insights"),
            next_steps=data.get("next_steps"),
            open_questions=data.get("open_questions"),
            resolved_questions=data.get("resolved_questions"),
        )

        num = create_checkpoint(ctx.obj["store"], task, cp_payload)
        click.echo(json.dumps({
            "checkpoint_number": num,
            "message": f"Checkpoint #{num} saved",
        }))
    except (json.JSONDecodeError, KeyError) as e:
        click.echo(f"Invalid payload: {e}", err=True)
        raise SystemExit(1)
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("slug")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "md"]),
    default="json",
    help="Output format",
)
@click.pass_context
def resume(ctx: click.Context, slug: str, fmt: str) -> None:
    """Resume a task -- output context bundle."""
    try:
        from dev_workflow.resume import resume_task
        from dev_workflow.task import get_task

        task = get_task(ctx.obj["store"], slug, ctx.obj["space"])
        output = resume_task(ctx.obj["store"], task, format=fmt)
        click.echo(output)
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("slug", required=False, default=None)
@click.pass_context
def status(ctx: click.Context, slug: str | None) -> None:
    """Show task status. No slug = all tasks in active space."""
    try:
        store = ctx.obj["store"]
        if slug:
            from dev_workflow.task import get_task
            task = get_task(store, slug, ctx.obj["space"])
            checkpoints = store.get_checkpoints(task.task_id)
            decisions = store.get_decisions(task.task_id)
            artifacts = store.get_artifacts(task.task_id)
            result = {
                "slug": task.slug,
                "title": task.title,
                "space": task.space,
                "last_milestone": task.last_milestone,
                "checkpoint_count": task.checkpoint_count,
                "decision_count": len(decisions),
                "artifact_count": len(artifacts),
                "last_checkpoint_at": (
                    task.last_checkpoint_at.isoformat()
                    if task.last_checkpoint_at
                    else None
                ),
                "summary": task.summary,
            }
            click.echo(json.dumps(result, indent=2))
        else:
            tasks = store.list_tasks(space=ctx.obj["space"])
            result = [
                {
                    "slug": t.slug,
                    "title": t.title,
                    "last_milestone": t.last_milestone,
                    "checkpoint_count": t.checkpoint_count,
                    "updated": t.updated.isoformat(),
                }
                for t in tasks
            ]
            click.echo(json.dumps(result, indent=2))
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@cli.command("list")
@click.option("--all-spaces", is_flag=True, help="List across all spaces")
@click.pass_context
def list_tasks(ctx: click.Context, all_spaces: bool) -> None:
    """List tasks."""
    store = ctx.obj["store"]
    if all_spaces:
        tasks = store.list_tasks(space=None)
    else:
        tasks = store.list_tasks(space=ctx.obj["space"])
    result = [
        {
            "slug": t.slug,
            "title": t.title,
            "space": t.space,
            "last_milestone": t.last_milestone,
            "checkpoint_count": t.checkpoint_count,
            "updated": t.updated.isoformat(),
        }
        for t in tasks
    ]
    click.echo(json.dumps(result, indent=2))


@cli.command()
@click.argument("slug")
@click.pass_context
def regenerate(ctx: click.Context, slug: str) -> None:
    """Regenerate task folder from SQLite."""
    try:
        from dev_workflow.task import get_task
        from dev_workflow.views import regenerate_task_folder

        task = get_task(ctx.obj["store"], slug, ctx.obj["space"])
        folder = regenerate_task_folder(ctx.obj["store"], task)
        click.echo(json.dumps({
            "task_folder": str(folder),
            "message": "Regenerated",
        }))
    except DevWorkflowError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)
