# dev-workflow

Checkpoint-oriented task continuity for agent-assisted development. A Python CLI that persists decisions, artifacts, and context across sessions so work can be resumed by any agent without losing history.

Tasks are organized into **spaces** -- isolated namespaces for separating projects or teams.

## Why

Long-running coding tasks span multiple sessions. Context is lost, decisions are forgotten, and new agents start from scratch. dev-workflow solves this by:

- **Checkpointing at meaningful moments** -- decisions, artifacts, verifications, and user directives are captured in structured snapshots, not lost in chat logs.
- **SQLite as source of truth** -- all state lives in a single database. Task folders are a generated cache, deletable and regenerable.
- **Progressive disclosure** -- HANDOFF.md gives an overview with links to detail files. Agents load what they need, not everything.

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### From a local clone

```bash
git clone https://github.com/rchaki8962/dev-workflow.git
cd dev-workflow
uv venv --python 3.13
uv pip install -e .
dev-workflow --help   # verify installation
```

### From remote (no clone needed)

```bash
pip install git+https://github.com/rchaki8962/dev-workflow.git
dev-workflow --help
```

### Verify it works

```bash
$ dev-workflow --help
Usage: dev-workflow [OPTIONS] COMMAND [ARGS]...

  dev-workflow: checkpoint-oriented task continuity.

Options:
  --space TEXT    Override active space
  --base-dir PATH  Override base directory
  --help         Show this message and exit.

Commands:
  checkpoint  Save a checkpoint for a task.
  init        Initialize a new task.
  list        List tasks.
  regenerate  Regenerate task folder from SQLite.
  resume      Resume a task -- output context bundle.
  space       Manage spaces.
  status      Show task status.
```

## Concepts

**Task**: A unit of work identified by a slug (e.g., `auth-middleware-rewrite`). Tasks accumulate checkpoints over time. Each task gets a folder with generated markdown views for human and agent consumption.

**Checkpoint**: A structured snapshot of progress -- milestone label, summary, decisions, artifacts, verifications, user directives, insights, open questions, and next steps. Checkpoints are freeform and happen whenever meaningful progress occurs.

**Space**: An isolated namespace for tasks. The same slug can exist in different spaces without collision. The default space is `"default"` and is auto-created on first use.

**Artifact**: A versioned document (spec, plan, design doc, config) stored within a checkpoint. Artifacts are deduplicated by SHA-256 checksum -- if content hasn't changed between checkpoints, no new version is created.

## Quick Start

Create a task, do some work, save a checkpoint, resume later:

```bash
# 1. Create a task with an initial prompt
dev-workflow init "Auth Middleware Rewrite" --prompt "Rewrite auth to use JWT for stateless scaling"

# 2. Work happens... then save a checkpoint
echo '{"milestone": "spec-done", "summary": "Finalized JWT auth spec"}' \
  | dev-workflow checkpoint auth-middleware-rewrite

# 3. Resume in a new session -- get structured context
dev-workflow resume auth-middleware-rewrite --format json

# 4. Or regenerate the markdown task folder
dev-workflow resume auth-middleware-rewrite --format md
```

## How-To Guides

### Creating and managing tasks

**Create a task with a prompt:**

The prompt captures the original intent. It's stored as an artifact in an implicit checkpoint #0, so it's always available for context.

```bash
dev-workflow init "CSV Export Feature" --prompt "Build a CSV exporter for user data with streaming support"
```

Output:
```json
{"slug": "csv-export-feature", "task_id": "a1b2c3d4-...", "task_folder": "/Users/you/.dev-workflow/default/tasks/2026-04-11-csv-export-feature"}
```

**Create a task without a prompt** (you can add context later via checkpoints):

```bash
dev-workflow init "Fix Login Bug"
```

**Create a task with workspace paths** (tells agents where the relevant code lives):

```bash
dev-workflow init "Refactor API" --workspace /path/to/api-repo --workspace /path/to/shared-lib
```

**Check what tasks exist:**

```bash
# All tasks in the active space
dev-workflow status

# Detailed status for a specific task
dev-workflow status csv-export-feature
```

A specific task's status output:
```json
{
  "slug": "csv-export-feature",
  "title": "CSV Export Feature",
  "space": "default",
  "last_milestone": "spec-done",
  "checkpoint_count": 2,
  "decision_count": 1,
  "artifact_count": 1,
  "last_checkpoint_at": "2026-04-11T14:30:00+00:00",
  "summary": "Finalized export spec with streaming approach"
}
```

**List tasks:**

```bash
dev-workflow list                  # active space
dev-workflow list --all-spaces     # everything
```

### Saving checkpoints

Checkpoints capture what happened since the last save. The payload is a JSON object piped via stdin or passed as a file.

**Minimal checkpoint** (just a milestone and summary):

```bash
echo '{"milestone": "session-end", "summary": "Explored three approaches, leaning toward streaming"}' \
  | dev-workflow checkpoint csv-export-feature
```

**Rich checkpoint with decisions, artifacts, and verifications:**

```bash
cat > /tmp/checkpoint.json << 'EOF'
{
  "milestone": "spec-finalized",
  "summary": "Finalized CSV export spec. Chose streaming approach for memory efficiency.",
  "user_directives": [
    "Must handle files over 1GB without loading into memory",
    "Use existing S3 infrastructure for storage"
  ],
  "decisions": [
    {
      "title": "Streaming CSV generation over batch",
      "rationale": "User requires 1GB+ file support. Streaming keeps memory constant.",
      "alternatives": ["batch generation", "chunked writes"],
      "context": "Production data sets average 500MB, some reach 2GB"
    }
  ],
  "artifacts": [
    {
      "type": "spec",
      "name": "csv-export-spec",
      "description": "CSV export feature specification",
      "content": "# CSV Export Spec\n\n## Overview\n\nStreaming CSV generation with S3 upload...\n\n## API\n\nPOST /exports { filters, format }\n\n## Streaming Strategy\n\n..."
    }
  ],
  "verifications": [
    {
      "type": "test-run",
      "result": "pass",
      "detail": "12/12 unit tests passing",
      "command": "pytest tests/test_export.py -v"
    }
  ],
  "insights": ["The existing ORM eager-loads relations by default -- need to switch to lazy loading for streaming"],
  "next_steps": ["Implement streaming CSV writer", "Add S3 multipart upload"],
  "open_questions": ["Should we support XLSX in addition to CSV?"],
  "resolved_questions": ["Which storage backend? -> S3 (existing infrastructure)"]
}
EOF

dev-workflow checkpoint csv-export-feature --payload /tmp/checkpoint.json
```

Output:
```json
{"checkpoint_number": 2, "message": "Checkpoint #2 saved"}
```

**Checkpoint payload fields:**

| Field                | Required | Description                                                      |
|----------------------|----------|------------------------------------------------------------------|
| `milestone`          | Yes      | Short label (e.g., `spec-done`, `auth-implemented`, `session-end`) |
| `summary`            | Yes      | 1-3 sentence summary of what happened                            |
| `user_directives`    | No       | Key user directives, constraints, and feedback                   |
| `decisions`          | No       | List of decisions with title, rationale, alternatives, context   |
| `artifacts`          | No       | List of versioned documents (full content, not summaries)        |
| `verifications`      | No       | Test runs, code reviews, manual checks                           |
| `insights`           | No       | Non-obvious observations worth preserving                        |
| `next_steps`         | No       | What should happen next                                          |
| `open_questions`     | No       | Unresolved questions                                             |
| `resolved_questions` | No       | Questions answered in this checkpoint                            |

### Resuming a task

When starting a new session, resume a task to get its full context.

**Get a structured JSON context bundle:**

```bash
dev-workflow resume csv-export-feature --format json
```

This returns everything an agent needs: current summary, decisions, latest artifact metadata, open questions, next steps, user directives, recent verifications, and paths to detail files.

```json
{
  "slug": "csv-export-feature",
  "title": "CSV Export Feature",
  "space": "default",
  "last_milestone": "spec-finalized",
  "checkpoint_count": 2,
  "summary": "Finalized CSV export spec. Chose streaming approach for memory efficiency.",
  "next_steps": ["Implement streaming CSV writer", "Add S3 multipart upload"],
  "open_questions": ["Should we support XLSX in addition to CSV?"],
  "user_directives": ["Must handle files over 1GB without loading into memory", "Use existing S3 infrastructure"],
  "decisions": [
    {"number": 1, "title": "Streaming CSV generation over batch", "rationale": "..."}
  ],
  "artifacts": [
    {"type": "spec", "name": "csv-export-spec", "version": 1, "description": "CSV export feature specification"}
  ],
  "recent_verifications": [
    {"type": "test-run", "result": "pass", "detail": "12/12 unit tests passing"}
  ],
  "handoff_path": "/Users/you/.dev-workflow/default/tasks/2026-04-11-csv-export-feature/HANDOFF.md",
  "detail_paths": {
    "decisions": ".../context/decisions.md",
    "record": ".../record/development-record.md",
    "checkpoints": ".../record/checkpoints.md"
  }
}
```

**Generate the markdown task folder:**

```bash
dev-workflow resume csv-export-feature --format md
```

This regenerates the entire task folder from SQLite and returns the path to `HANDOFF.md`. The folder contains:

- `HANDOFF.md` -- overview with links to everything else
- `context/original-prompt.md` -- the initial task prompt
- `context/current-state.md` -- latest checkpoint state, next steps, open questions
- `context/decisions.md` -- all decisions with full rationale and alternatives
- `context/open-questions.md` -- unresolved questions
- `artifacts/*.md` -- versioned artifact files
- `record/checkpoints.md` -- chronological checkpoint log
- `record/development-record.md` -- archival summary

**Regenerate the folder without resuming:**

```bash
dev-workflow regenerate csv-export-feature
```

The task folder is a generated cache. You can delete it anytime and rebuild from SQLite.

### Working with spaces

Spaces let you separate tasks by project, team, or context. The default space is `"default"` and requires no setup.

**Create spaces:**

```bash
dev-workflow space create personal --description "Side projects"
dev-workflow space create work --description "Work tasks"
```

Space names must be lowercase alphanumeric with hyphens, starting with a letter or digit.

**List spaces:**

```bash
dev-workflow space list
```

```json
[
  {"name": "personal", "description": "Side projects", "created": "2026-04-11T10:00:00+00:00"},
  {"name": "work", "description": "Work tasks", "created": "2026-04-11T10:00:01+00:00"}
]
```

**Get space details (including task count):**

```bash
dev-workflow space info personal
```

```json
{"name": "personal", "description": "Side projects", "created": "2026-04-11T10:00:00+00:00", "task_count": 3}
```

**Remove a space** (must have no tasks):

```bash
dev-workflow space remove temp-space
```

**Create tasks in a specific space:**

```bash
dev-workflow --space personal init "Blog Engine" --prompt "Static site generator with markdown"
dev-workflow --space work init "API Rate Limiter" --prompt "Token bucket rate limiting"
```

**Work within a space:**

```bash
# All commands target the specified space
dev-workflow --space personal status
dev-workflow --space personal checkpoint blog-engine --payload /tmp/cp.json
dev-workflow --space personal resume blog-engine --format json
```

**List tasks across all spaces:**

```bash
dev-workflow list --all-spaces
```

### Selecting the active space

The active space is resolved in this order (first match wins):

1. **`--space` CLI flag**: `dev-workflow --space personal status`
2. **`DEV_WORKFLOW_SPACE` env var**: `export DEV_WORKFLOW_SPACE=personal`
3. **`default_space` in config file**: set in `~/.dev-workflow/config.toml`
4. **Hardcoded default**: `"default"`

**Using an env var for a whole terminal session:**

```bash
export DEV_WORKFLOW_SPACE=work
dev-workflow init "New Task"        # created in "work" space
dev-workflow status                  # shows "work" tasks
dev-workflow list                    # lists "work" tasks
```

**Config file (`~/.dev-workflow/config.toml`):**

```toml
default_space = "personal"
```

### Overriding the data directory

By default, all data lives in `~/.dev-workflow/`. Override with:

```bash
# Via environment variable
export DEV_WORKFLOW_DIR=/path/to/custom/dir
dev-workflow init "Task"

# Via CLI flag (per command)
dev-workflow --base-dir /tmp/test-workflow init "Task"
```

### Typical multi-session workflow

**Session 1: Start the task and write a spec**

```bash
# Create the task
dev-workflow init "Auth Middleware Rewrite" --prompt "Rewrite auth middleware to use JWT for horizontal scaling. Must work with existing Postgres."

# ... work on the spec with your agent ...

# Save a checkpoint with the spec artifact
dev-workflow checkpoint auth-middleware-rewrite --payload /tmp/spec-checkpoint.json
```

**Session 2: Pick up where you left off**

```bash
# Resume -- get full context
dev-workflow resume auth-middleware-rewrite --format json

# ... agent reads the context, continues implementation ...

# Save progress
echo '{"milestone": "middleware-implemented", "summary": "JWT middleware working end-to-end, 28/28 tests passing"}' \
  | dev-workflow checkpoint auth-middleware-rewrite
```

**Session 3: Different agent picks it up**

```bash
# New agent gets everything: decisions, artifacts, open questions, user directives
dev-workflow resume auth-middleware-rewrite --format json

# Or generate the task folder for file-based browsing
dev-workflow resume auth-middleware-rewrite --format md
# Agent reads HANDOFF.md -> drills into context/decisions.md, artifacts/, etc.
```

### Agent integration

The `skills/` directory contains markdown instructions for agent integration:

- **`skills/task-awareness.md`** -- How agents should check for active tasks at session start, detect checkpoint-worthy moments during work, and suggest checkpoints without being pushy.

- **`skills/task-checkpoint.md`** -- How agents should extract checkpoint data from conversation context, draft the payload, present it for user review, and invoke the CLI.

**Workflow for agents:**

1. At session start, run `dev-workflow status` to check for active tasks
2. If resuming, run `dev-workflow resume <slug> --format json` to load context
3. During work, watch for checkpoint-worthy moments (decisions made, artifacts produced, direction changes)
4. Draft the checkpoint payload, present it to the user for review
5. On approval, pipe the payload to `dev-workflow checkpoint <slug>`
6. Before session end, suggest a final checkpoint if meaningful work happened

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
- **Artifact dedup**: Artifacts are versioned by name. If content (SHA-256 checksum) hasn't changed, no new version is stored.
- **Atomic checkpoints**: Each checkpoint writes the checkpoint record, decisions, artifacts, and verifications in a single SQLite transaction. If any part fails, nothing is saved.

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

skills/                    # agent skill markdown files
tests/                     # 94 tests
```

## Development

```bash
# Setup
uv venv --python 3.13
uv pip install -e ".[dev]"

# Run tests
uv run pytest                                    # full suite (94 tests)
uv run pytest tests/test_cli.py -v               # specific module
uv run pytest tests/test_store.py -k checkpoint   # specific test pattern

# CLI
uv run dev-workflow --help
```

Requires Python 3.11+. Only runtime dependency: `click>=8.0`.

## License

MIT
