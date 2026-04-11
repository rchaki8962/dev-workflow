# dev-workflow

Checkpoint-oriented task continuity for agent-assisted development. A Python CLI that persists decisions, artifacts, and context across sessions so work can be resumed by any agent without losing history.

Tasks are organized into **spaces** -- isolated namespaces for separating projects or teams.

## Why

Long-running coding tasks span multiple sessions. Context is lost, decisions are forgotten, and new agents start from scratch. dev-workflow solves this by:

- **Checkpointing at meaningful moments** -- decisions, artifacts, verifications, and user directives are captured in structured snapshots, not lost in chat logs.
- **SQLite as source of truth** -- all state lives in a single database. Task folders are a generated cache, deletable and regenerable.
- **Progressive disclosure** -- HANDOFF.md gives an overview with links to detail files. Agents load what they need, not everything.

## Installation

```bash
pip install -e .
dev-workflow --help
```

Requires Python 3.11+. Only runtime dependency: `click>=8.0`.

## Quick Start

```bash
# Create a task with an initial prompt
dev-workflow init "Auth Middleware Rewrite" --prompt "Rewrite auth to use JWT..."

# Work happens... then save a checkpoint
echo '{"milestone": "spec-done", "summary": "Finalized JWT auth spec"}' | dev-workflow checkpoint auth-middleware-rewrite

# Resume in a new session
dev-workflow resume auth-middleware-rewrite --format json

# Regenerate the task folder (markdown views)
dev-workflow resume auth-middleware-rewrite --format md
```

## Concepts

**Task**: A unit of work identified by a slug. Tasks accumulate checkpoints over time. Each task has a folder with generated markdown views for human and agent consumption.

**Checkpoint**: A structured snapshot of progress -- milestone label, summary, decisions, artifacts, verifications, user directives, insights, open questions, and next steps. Checkpoints are freeform and happen whenever meaningful progress occurs.

**Space**: An isolated namespace for tasks. Same slug can exist in different spaces without collision.

**Artifact**: A versioned document (spec, plan, design doc, config) stored within a checkpoint. Artifacts are deduplicated by SHA-256 checksum -- if content hasn't changed, no new version is created.

## CLI Reference

### Task commands

```bash
dev-workflow init "Task Title" --prompt "Description..."   # create task
dev-workflow init "Task Title" --workspace /path/to/repo   # with workspace path
dev-workflow status                                         # all tasks in active space
dev-workflow status <slug>                                  # specific task detail
dev-workflow list                                           # list tasks in active space
dev-workflow list --all-spaces                              # list across all spaces
```

### Checkpoint commands

```bash
# Via stdin
echo '<json>' | dev-workflow checkpoint <slug>

# Via file
dev-workflow checkpoint <slug> --payload payload.json
```

The checkpoint payload is a JSON object with required fields `milestone` and `summary`, plus optional `decisions`, `artifacts`, `verifications`, `user_directives`, `insights`, `next_steps`, `open_questions`, and `resolved_questions`. See `skills/task-checkpoint.md` for the full schema.

### Resume commands

```bash
dev-workflow resume <slug> --format json   # structured context bundle
dev-workflow resume <slug> --format md     # regenerate folder, return HANDOFF.md path
dev-workflow regenerate <slug>             # regenerate task folder only
```

### Space commands

```bash
dev-workflow space create <name> --description "..."
dev-workflow space list
dev-workflow space info <name>
dev-workflow space remove <name>    # fails if space has tasks
```

Space names must be lowercase alphanumeric with hyphens, starting with a letter or digit.

### Space resolution

The active space is resolved in this order (first match wins):

1. `--space` CLI flag
2. `DEV_WORKFLOW_SPACE` environment variable
3. `default_space` in `~/.dev-workflow/config.toml`
4. `"default"`

## Data Directory

All data lives under `~/.dev-workflow/` (configurable via `--base-dir` or `DEV_WORKFLOW_DIR`):

```
~/.dev-workflow/
  store.db                         # SQLite database (source of truth)
  config.toml                      # optional config (default_space)
  default/                         # default space
    tasks/
      2026-04-11-auth-rewrite/     # generated task folder (cache)
        HANDOFF.md                 # index -- overview with links
        context/
          original-prompt.md       # initial task prompt
          current-state.md         # latest checkpoint state
          decisions.md             # all decisions with rationale
          open-questions.md        # unresolved questions
        artifacts/
          spec-auth-spec-v2.md     # versioned artifacts
        record/
          checkpoints.md           # chronological checkpoint log
          development-record.md    # archival summary
  personal/                        # another space, same structure
    tasks/
```

The task folder is a **generated cache**. Delete it anytime -- `dev-workflow regenerate <slug>` rebuilds it from SQLite.

## Architecture

```
CLI (Click)
  |
  |---> Domain Logic (space, task, checkpoint, resume, views)
  |       Stateless functions that accept a Store instance
  |
  |---> Storage (SQLite via Store)
          Single module importing sqlite3
          WAL mode, foreign keys, atomic transactions
```

- **Three-layer separation**: CLI is a thin wrapper over domain functions. Domain functions call the Store. Only `store.py` imports `sqlite3`.
- **Checkpoint-oriented**: No rigid stage pipeline. Users checkpoint at meaningful moments.
- **Progressive disclosure**: HANDOFF.md is a summary with links. Detail files have full content. No duplication between files.

## Agent Skills

The `skills/` directory contains markdown skill files for agent integration:

- `skills/task-awareness.md` -- Session start flow, checkpoint-worthy signal detection
- `skills/task-checkpoint.md` -- Checkpoint payload drafting, review flow, CLI invocation

## Project Structure

```
src/dev_workflow/          # Python package
  models.py                #   dataclasses: Task, Space, Checkpoint, Decision, Artifact, etc.
  errors.py                #   exception hierarchy (DevWorkflowError base)
  config.py                #   config loading + space resolution
  slug.py                  #   slug generation with collision handling
  store.py                 #   SQLite storage layer
  space.py                 #   space domain logic
  task.py                  #   task init + lookup
  checkpoint.py            #   checkpoint validation + creation
  views.py                 #   markdown view generation
  resume.py                #   context bundle synthesis
  cli.py                   #   Click CLI entry point

skills/                    # agent skill files
tests/                     # 94 tests
```

## Development

```bash
uv venv --python 3.13
uv pip install -e ".[dev]"
uv run pytest                                    # full suite
uv run pytest tests/test_cli.py -v               # specific module
uv run pytest tests/test_store.py -k checkpoint   # specific test
uv run dev-workflow --help
```

## License

MIT
