# CLAUDE.md

dev-workflow: Claude Code plugin + Python CLI for durable, multi-session task management with a spec -> plan -> execution workflow. Tasks are organized into **spaces** (isolated namespaces).

See [HOW_TO.md](HOW_TO.md) for usage guide. See [DESIGN.md](DESIGN.md) for architecture and design decisions.

## Quick reference

```bash
pip install -e .
pytest                    # 423 tests
dev-workflow --help
```

## Module map

- `models.py` -- dataclasses and enums (Task, Space, Stage, Subtask, Spec, Plan, Review, etc.)
- `config.py` -- config + space resolution
- `space.py` -- `SpaceManager` CRUD
- `store.py` -- `TaskStore` protocol + `FileTaskStore`
- `state.py` -- per-task JSON state
- `task.py` -- `TaskManager` (create, list, search, switch)
- `stage.py` -- `StageManager` (setup, teardown, review_setup, review_approve)
- `cli.py` -- Click CLI
- `progress.py`, `plan_parser.py`, `templates.py`, `slug.py` -- utilities
- `exceptions.py` -- `DevWorkflowError`, `TaskNotFoundError`, `SpaceNotFoundError`, `PrerequisiteError`, `PlanParseError`

## Testing

- Python 3.11+, only dependency: `click>=8.0`
- All tests use `tmp_path` -- never touch real `~/.dev-workflow/`
- Test fixtures must set `config._active_space` and create space directories
- `FileTaskStore` in tests takes `config.space_dir` (not `config.base_dir`)

## Plugin commands

Commands in `claude_plugin/commands/`: task-start, task-status, task-list, task-search, task-switch, run-stage, stage-review, stage-approve.

`/run-stage` orchestrates: CLI setup -> Superpowers skill -> CLI teardown. Output paths override to task folder, skill chaining suppressed, formal review gates preserved.

Space management (`space create/list/remove/info`) is CLI-only.
