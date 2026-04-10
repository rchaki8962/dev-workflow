# dev-workflow

Durable, multi-session task management for coding agents. A Python CLI + Claude Code plugin that guides tasks through a structured **spec -> plan -> execution** workflow with formal review gates between stages.

Tasks are organized into **spaces** -- isolated namespaces for separating personal projects, org work, or different teams.

## Why

Long-running coding tasks span multiple sessions. Context is lost, work drifts, and quality suffers. dev-workflow solves this by:

- **Persisting everything to files** -- specs, plans, subtasks, progress, activity logs. Chats are disposable; files are the source of truth.
- **Enforcing a stage workflow** -- no skipping from idea to code. Spec first, then plan, then execute. Each stage requires explicit approval to advance.
- **Supporting multi-task, multi-space workflows** -- work on several tasks across isolated spaces, each at its own stage, resumable from any session.

## Installation

Two steps: install the Python CLI (the engine), then the Claude Code plugin (the interface).

### From local clone

If you've cloned the repo, run these from the repo root:

**1. Install the CLI:**

```bash
pip install -e .
dev-workflow --help   # verify
```

**2. Install the Claude Code plugin** (from within a Claude Code session):

```
/plugin marketplace add ./claude_plugin
/plugin install dev-workflow
```

### From remote (no clone needed)

**1. Install the CLI:**

```bash
pip install git+https://github.com/rchaki8962/dev-workflow.git
dev-workflow --help   # verify
```

**2. Install the Claude Code plugin** (from within a Claude Code session):

```
/plugin marketplace add rchaki8962/dev-workflow/claude_plugin
/plugin install dev-workflow
```

Both methods install the plugin at user scope -- available across all your projects.

## Concepts

**Task**: A unit of work that moves through three stages: spec, plan, execution. Each task gets a unique slug, a folder with structured files, and a state JSON entry.

**Space**: An isolated namespace for tasks. Spaces keep work separated -- for example, personal projects vs. org work vs. different teams. Each space has its own `state/` and `tasks/` directories, so slugs can repeat across spaces without collision.

**Stage**: Each task moves through `spec` -> `plan` -> `execution` -> `complete`. Stages advance only through formal review approval, never automatically.

## Quick Start

```
/task-start Build CSV exporter
/run-stage spec
/stage-approve spec
/run-stage plan
/stage-approve plan
/run-stage execution
/stage-approve execution
```

## Usage

The plugin provides slash commands that orchestrate the CLI with [Superpowers](https://github.com/anthropics/claude-code-plugins) skills. This is the intended way to use dev-workflow.

### Starting a task

```
/task-start CSV Export Feature
```

Claude will create the task, ask you to describe what you want to build, save your response as the original prompt, and remember the slug for the session.

### Running the spec stage

```
/run-stage spec
```

This runs `stage setup` -> Superpowers brainstorming skill -> `stage teardown`. The brainstorming skill asks clarifying questions, proposes approaches, and writes a design spec. Output goes to the task folder, not to `docs/superpowers/`.

### Reviewing and approving

```
/stage-review spec       # creates a review template for a separate session
/stage-approve spec      # approves the stage, advances task to plan
```

You can skip the formal review and go straight to approve if you're satisfied.

### Running the plan stage

```
/run-stage plan
```

This reads the approved spec and invokes the writing-plans skill. Same flow: `stage setup` -> skill -> `stage teardown`.

```
/stage-approve plan      # advances task to execution
```

### Running the execution stage

```
/run-stage execution
```

This invokes subagent-driven-development to execute the plan task-by-task.

```
/stage-review execution
/stage-approve execution  # marks task complete
```

### Other plugin commands

```
/task-list               # list tasks in active space
/task-search query       # search tasks
/task-status             # show current task details
/task-switch slug        # switch session to a different task
```

### Working across multiple spaces

**Terminal setup** -- create your spaces once:

```bash
dev-workflow space create personal --description "Side projects"
dev-workflow space create acme-eng --description "Acme engineering"
```

**Claude Code session for org work** (default space):

```
/task-start Auth Middleware Rewrite
> Rewrite the auth middleware to comply with new session token storage requirements...
/run-stage spec
/stage-approve spec
/run-stage plan
```

**Claude Code session for personal project** -- set space via env var or flag:

```bash
# Option A: env var (applies to entire shell session)
export DEV_WORKFLOW_SPACE=personal
claude

# Option B: always pass --space in CLI commands
dev-workflow --space personal task list
```

Then in Claude Code:

```
/task-start Blog Engine
> Build a static blog generator with markdown support...
/run-stage spec
```

### Switching between tasks within a space

Inside a Claude Code session, you work on one task at a time. The slug is remembered per-session:

```
/task-switch auth-refactor     # load context for this task
/run-stage execution           # continues where you left off

/task-switch csv-export        # switch to another task
/task-status                   # see where it stands
/run-stage plan                # pick up from the plan stage
```

### Key rules

- **One space per CLI invocation.** Every command operates within the active space. Cross-space visibility is only through `task list --all-spaces`.
- **One task per session.** `/task-start` or `/task-switch` sets the session's active task. Subsequent `/run-stage`, `/stage-review`, `/stage-approve` use that slug.
- **Tasks don't move between spaces.** The space is set at creation time and is immutable.
- **Stages only advance through approval.** `stage teardown` does NOT advance the stage. Only `review approve` does.

## CLI Reference

The Python CLI handles all deterministic operations under the hood. You can also use it directly from the terminal.

### Task commands

**Create a task:**

```bash
dev-workflow task start "CSV Export Feature" --prompt "Build a CSV exporter for user data"
dev-workflow task start "Auth Refactor" --slug auth-refactor --workspace /path/to/repo
dev-workflow --space personal task start "Blog Engine" --prompt "Static site generator"
```

Options: `--slug` (custom slug), `--prompt` (inline prompt text), `--prompt-file` (path to prompt file), `--workspace` (working directory, repeatable), `--format json|table`.

**List tasks:**

```bash
dev-workflow task list                          # active space only
dev-workflow task list --stage spec             # filter by stage
dev-workflow task list --all-spaces             # all tasks across all spaces
dev-workflow task list --all-spaces --format json
```

**Search, info, switch:**

```bash
dev-workflow task search "csv"                  # substring match on slug/title/summary
dev-workflow task info csv-export               # show task details
dev-workflow task switch csv-export             # load task context (progress + spec + plan summaries)
```

### Stage commands

```bash
dev-workflow stage setup spec --task csv-export --format json
dev-workflow stage teardown spec --task csv-export
dev-workflow stage status --task csv-export
```

### Review commands

```bash
dev-workflow review setup spec --task csv-export --format json
dev-workflow review approve spec --task csv-export
```

Approving a review is the only way to advance a task to the next stage.

### Spaces

**Creating spaces:**

```bash
dev-workflow space create personal --description "Personal projects"
dev-workflow space create acme-eng --description "Acme engineering"
```

Space names must be lowercase alphanumeric with hyphens, max 40 characters.

**Listing spaces:**

```bash
dev-workflow space list
```

Output:

```
  default              Default workspace              3 tasks
  personal             Personal projects              1 task
  acme-eng             Acme engineering               0 tasks
```

JSON output: `dev-workflow space list --format json`

**Space info and removal:**

```bash
dev-workflow space info personal
dev-workflow space remove temp-space           # fails if space has tasks
dev-workflow space remove temp-space --force   # removes even with tasks
```

**Default space:** The default space is `default`. It is auto-created on first use -- no setup required.

**Selecting the active space** -- resolution order (first match wins):

1. `--space` CLI flag: `dev-workflow --space personal task list`
2. `DEV_WORKFLOW_SPACE` env var: `export DEV_WORKFLOW_SPACE=personal`
3. `default_space` in config file (`claude_plugin/config.toml` under `[spaces]`)
4. Hardcoded default: `default`

**Checking across spaces:**

```bash
dev-workflow task list --all-spaces

# Output:
#   [default]     auth-refactor    execution    Auth Middleware Rewrite
#   [default]     csv-export       plan         CSV Export Feature
#   [personal]    blog-engine      spec         Blog Engine
```

## Data Directory

All data lives under `~/.dev-workflow/` (configurable via `--base-dir` or `DEV_WORKFLOW_DIR`):

```
~/.dev-workflow/
  spaces.json                    # space registry (name, description, created)
  default/                       # default space
    state/
      csv-export.json            # task state (stage, metadata, timestamps)
      auth-refactor.json
    tasks/
      2026-04-08-csv-export/     # task folder
        00-progress.md           # current status dashboard
        01-original-prompt.md    # user's original description
        10-spec/
          spec-v1.md             # draft spec
          spec-approved.md       # approved spec (copied from latest draft)
        20-plan/
          plan-v1.md
          plan-approved.md
        30-execution/
          subtask-01.md, subtask-02.md, ...
          implementation-summary.md
        90-logs/
          activity-log.md        # append-only activity history
  personal/                      # another space, same structure
    state/
    tasks/
```

## Architecture

```
Claude Code Plugin Commands (orchestrators)
    |
    |---> Python CLI (deterministic mechanics)
    |       TaskManager, StageManager, FileTaskStore
    |
    |---> Superpowers Skills (creative work)
            brainstorming, writing-plans, subagent-driven-development
```

- **Python CLI** handles all deterministic operations: task CRUD, stage lifecycle, file I/O, state management. Fully testable, no Claude Code dependency.
- **Plugin commands** are thin orchestrators that call the CLI and invoke Superpowers skills.
- **Spaces** provide data isolation via Config wiring -- downstream code (store, stage, progress) is unaware of spaces.

See [DESIGN.md](docs/DESIGN.md) for the full architecture document.

## Project Structure

```
src/dev_workflow/          # Python package
  models.py                #   dataclasses: Task, Space, Stage, Spec, Plan, etc.
  config.py                #   config + space resolution
  space.py                 #   SpaceManager CRUD
  store.py                 #   TaskStore protocol + FileTaskStore
  state.py                 #   per-task JSON state
  task.py                  #   TaskManager
  stage.py                 #   StageManager
  cli.py                   #   Click CLI
  progress.py, plan_parser.py, templates.py, slug.py

claude_plugin/             # Claude Code plugin
  .claude-plugin/          #   plugin + marketplace manifests
  config.toml              #   plugin configuration
  commands/                #   slash command definitions (markdown)

tests/                     # 423 tests
```

## Development

```bash
# Setup
uv venv --python 3.13
uv pip install -e ".[dev]"

# Run tests
uv run pytest
uv run pytest tests/test_cli.py -v          # specific module
uv run pytest tests/test_space.py -k ensure  # specific test

# CLI
uv run dev-workflow --help
```

Requires Python 3.11+. Only runtime dependency: `click>=8.0`.

## License

MIT
