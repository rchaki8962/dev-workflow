# dev-workflow

Durable, multi-session task management for coding agents. A Python CLI + Claude Code plugin that guides tasks through a structured **spec -> plan -> execution** workflow with formal review gates between stages.

Tasks are organized into **spaces** -- isolated namespaces for separating personal projects, org work, or different teams.

## Why

Long-running coding tasks span multiple sessions. Context is lost, work drifts, and quality suffers. dev-workflow solves this by:

- **Persisting everything to files** -- specs, plans, subtasks, progress, activity logs. Chats are disposable; files are the source of truth.
- **Enforcing a stage workflow** -- no skipping from idea to code. Spec first, then plan, then execute. Each stage requires explicit approval to advance.
- **Supporting multi-task, multi-space workflows** -- work on several tasks across isolated spaces, each at its own stage, resumable from any session.

## Quick Start

```bash
pip install -e .

# Create your first task (auto-creates the default "harness" space)
dev-workflow task start "Build CSV exporter" --prompt "Export user data to RFC 4180 CSV"

# See what's active
dev-workflow task list

# Manage spaces
dev-workflow space create personal --description "Side projects"
dev-workflow --space personal task start "Blog engine" --prompt "Static site generator"
dev-workflow task list --all-spaces
```

## Claude Code Plugin

Install the Claude Code plugin (from within Claude Code):

```
/plugin marketplace add /path/to/dev-workflow/claude_plugin
/plugin install dev-workflow
```

Or from the remote repo:

```
/plugin marketplace add rchaki8962/dev-workflow/claude_plugin
/plugin install dev-workflow
```

Then use slash commands that orchestrate the CLI with [Superpowers](https://github.com/anthropics/claude-code-plugins) skills:

```
/task-start Build CSV exporter       # create task, capture prompt
/run-stage spec                      # brainstorm -> write spec
/stage-approve spec                  # approve, advance to plan
/run-stage plan                      # write implementation plan
/stage-approve plan                  # approve, advance to execution
/run-stage execution                 # subagent-driven development
/stage-approve execution             # done
```

Other commands: `/task-list`, `/task-search`, `/task-switch`, `/task-status`, `/stage-review`.

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

## Documentation

- **[HOW_TO.md](HOW_TO.md)** -- detailed usage guide, CLI reference, multi-space workflows
- **[DESIGN.md](DESIGN.md)** -- architecture, domain model, persistence layer, design decisions

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
