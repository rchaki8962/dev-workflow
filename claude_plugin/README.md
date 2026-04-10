# dev-workflow — Claude Code Plugin

Slash commands for durable, multi-session task management with a spec → plan → execution workflow.

## Prerequisites

The plugin commands call the `dev-workflow` CLI. Install it first:

```bash
pip install -e /path/to/dev-workflow
```

Verify: `dev-workflow --help`

## Installation

### From local path (persistent, available across all projects)

From within Claude Code:

```
/plugin marketplace add /path/to/dev-workflow/claude_plugin
/plugin install dev-workflow
```

### From remote repo

```
/plugin marketplace add rchaki8962/dev-workflow/claude_plugin
/plugin install dev-workflow
```

Note: the remote path includes `/claude_plugin` because the plugin lives in a subdirectory of the repo.

### Local development (temporary, current session only)

```bash
claude --plugin-dir /path/to/dev-workflow/claude_plugin
```

### Reload after changes

```
/reload-plugins
```

## Plugin Structure

```
claude_plugin/                    # plugin root
├── .claude-plugin/               # metadata (required by Claude Code)
│   ├── plugin.json               # plugin manifest
│   └── marketplace.json          # marketplace manifest
├── commands/                     # slash command definitions (.md)
├── config.toml
└── README.md
```

## Available Commands

| Command | Description |
|---------|-------------|
| `/task-start <title>` | Create a new task and capture the original prompt |
| `/task-status [slug]` | Show detailed task information |
| `/task-list [stage]` | List tasks, optionally filtered by stage |
| `/task-search <query>` | Search tasks by text |
| `/task-switch <slug>` | Switch session to an existing task |
| `/run-stage <stage> [slug]` | Run a workflow stage (spec, plan, or execution) |
| `/stage-review <stage> [slug]` | Set up a review for a completed stage |
| `/stage-approve <stage> [slug]` | Approve a stage and advance to the next |

## Workflow

```
/task-start "my feature"
/run-stage spec
/stage-approve spec
/run-stage plan
/stage-approve plan
/run-stage execution
/stage-approve execution
```
