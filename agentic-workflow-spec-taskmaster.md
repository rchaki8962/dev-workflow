# Spec: External Task Folder Workflow — Taskmaster AI Variant

Status: Draft v3
Companion to: `agentic-workflow-spec.md` (standalone spec)

## 1. Overview

This spec describes the Taskmaster AI variant of the external task folder workflow. It shares all structure, stages, review model, and integration patterns with the standalone spec (`agentic-workflow-spec.md`). This document only describes what changes when Taskmaster AI is used.

**Read the standalone spec first.** This document assumes familiarity with it.

### What changes

Taskmaster AI participates in **two stages**:

1. **Plan engine**: Taskmaster decomposes the approved spec into a structured task list with dependency graphs and complexity scores. This replaces the default plan engine.
2. **Execution helper**: During execution, Taskmaster's `next_task` API provides dependency-aware task selection and model routing recommendations. The execution engine (e.g., `superpowers:subagent-driven-development`) uses Taskmaster as an advisor, not a replacement.

### What stays the same

Everything else:
- Task folder layout (with one addition: `.taskmaster/`)
- Spec stage (Taskmaster is not a spec engine)
- Review model
- Progress file design
- Safety and isolation rules
- Claude Code integration (commands and hooks)
- All v1/v2/v3 scoping

## 2. Taskmaster AI Integration Model

### 2.1 Where Taskmaster lives

Taskmaster normally stores its state in `.taskmaster/` at the project root. In this workflow, Taskmaster's state directory is relocated to live **inside the task folder**, not inside the workspace:

```text
<task-id>/
  ...
  30-execution/
    subtask-01.md
    subtask-02.md
    ...
  .taskmaster/          <-- Taskmaster state lives here
    tasks/
      tasks.json
    ...
```

This keeps the workspace clean and the task folder self-contained.

Taskmaster is configured to use this path via its `TASKMASTER_DIR` environment variable or equivalent configuration, set by `run-stage` before invoking Taskmaster.

### 2.2 Source of truth

The **subtask files** (`30-execution/subtask-NN.md`) and the **approved plan** (`20-plan/plan-approved.md`) remain the sources of truth for this workflow. Taskmaster is a tool for planning decomposition and execution ordering, not the canonical record.

Data flow during the **plan stage**:
1. `run-stage plan` invokes Taskmaster as the plan engine.
2. Taskmaster reads the approved spec and produces a plan with numbered tasks, dependencies, and complexity scores.
3. The output is written to `20-plan/plan-v<N>.md`.
4. Taskmaster also populates its own `.taskmaster/tasks/tasks.json` with the same tasks, dependencies, and metadata.

Data flow during the **execution stage**:
1. `run-stage execution` creates subtask files from the approved plan (same as standalone).
2. `run-stage` also syncs Taskmaster task statuses to match the subtask files (all `not-started`).
3. During execution, the engine uses Taskmaster's `next_task` to determine what to work on next (respecting dependencies).
4. As each subtask completes, the agent updates **both** the subtask file and the Taskmaster task status.
5. `00-progress.md` is updated from the subtask files (not from Taskmaster).

If Taskmaster state and subtask files ever disagree, the subtask files win.

### 2.3 Mapping between subtask files and Taskmaster tasks

Each subtask file corresponds to one Taskmaster task:

| Subtask file field | Taskmaster task field |
|---|---|
| Subtask id (NN) | `id` |
| Title | `title` |
| Description | `description` |
| Status | `status` |
| Verification steps | `testStrategy` |

Additional Taskmaster-only fields (not in subtask files):
- `dependencies`: list of subtask ids this task depends on
- `complexityScore`: estimated complexity (1-10)
- `recommendedModel`: suggested model for this subtask's complexity level

### 2.4 Dependency management

Taskmaster produces the dependency graph as part of its plan output. When `run-stage execution` creates subtask files, it does not encode dependencies in the subtask files themselves — the dependency graph lives in Taskmaster's state and in the approved plan.

During execution:
- `next_task` returns only subtasks whose dependencies are satisfied.
- Parallel agents can work on independent subtasks simultaneously.
- The dependency graph prevents out-of-order execution.

This is the primary advantage over standalone mode, where the execution engine must manage execution order manually or rely on the plan's ordering hints.

### 2.5 Complexity scoring and model routing

Taskmaster scores each task's complexity during planning and recommends a model:

| Complexity | Recommended model | Example |
|---|---|---|
| 1-3 (low) | Haiku / fast model | Config changes, simple renames |
| 4-7 (medium) | Sonnet | Standard feature implementation |
| 8-10 (high) | Opus | Architecture changes, complex algorithms |

The execution engine may use this to route subtasks to subagents running different models. This is optional — the engine can ignore the recommendations and use a single model.

## 3. Modified Scripts

### 3.1 `run-stage plan` (modified behavior)

When Taskmaster is the configured plan engine, `run-stage plan` does:
1. Set `TASKMASTER_DIR` to `<task-folder>/.taskmaster/`.
2. Initialize Taskmaster in that directory (if not already initialized).
3. Invoke Taskmaster to decompose the approved spec into tasks with dependencies and complexity scores.
4. Write the plan to `20-plan/plan-v<N>.md` in the standard format (numbered tasks with title, description, verification steps, plus dependency and complexity metadata).

The Taskmaster tasks in `.taskmaster/tasks/tasks.json` are populated as a side effect of this step.

### 3.2 `run-stage execution` (modified behavior)

When Taskmaster is available, `run-stage execution` does additional setup:
1. Create subtask files from the approved plan (same as standalone).
2. Sync Taskmaster task statuses to match subtask files.
3. Pass the execution engine a flag or config indicating that Taskmaster's `next_task` is available for execution ordering.

The execution engine then uses `next_task` instead of sequential ordering. All other behavior (subtask file updates, progress updates, verification, logging) remains the same.

### 3.3 `task-sync` (new, optional)

```
task-sync
```

An optional utility to reconcile Taskmaster state with subtask files:
- Reads all subtask files in `30-execution/`.
- Compares status with Taskmaster tasks.
- Reports discrepancies.
- Optionally updates Taskmaster to match subtask files (subtask files are authoritative).

This is a diagnostic tool, not part of the normal workflow.

## 4. Modified Task Folder Layout

The only structural addition is the `.taskmaster/` directory:

```text
<task-id>/
  00-progress.md
  01-original-prompt.md
  10-spec/
    ...
  20-plan/
    ...
  30-execution/
    subtask-01.md
    subtask-02.md
    ...
    execution-review-v1.md
    implementation-summary.md
  .taskmaster/              <-- NEW: Taskmaster state
    tasks/
      tasks.json
  90-logs/
    activity-log.md
```

## 5. When to Use This Variant

Use the Taskmaster variant when:
- The task has many subtasks (10+) with complex dependencies
- You want automated dependency resolution for parallel execution
- You want complexity-based model routing
- You want Taskmaster to handle the plan decomposition (instead of another plan engine)

Use the standalone variant when:
- The task has few subtasks (<10) with simple linear ordering
- You want minimal tooling overhead
- You don't want an additional MCP server dependency
- You want the simplest possible setup

## 6. Prerequisites

The Taskmaster variant requires:
- Taskmaster AI installed (`npm install -g task-master-ai` or `npx task-master-ai`)
- Taskmaster MCP server configured in Claude Code (`claude mcp add task-master-ai -- npx -y task-master-ai`)
- An API key for at least one supported LLM provider (Anthropic, OpenAI, etc.)

The standalone variant has no additional dependencies beyond the shell scripts.

## 7. Acceptance Criteria (additions to standalone)

In addition to the standalone spec's acceptance criteria:

### 7.1 Taskmaster initialization
- `run-stage plan` with Taskmaster creates `.taskmaster/` inside the task folder, not in the workspace.

### 7.2 Plan decomposition
- Taskmaster produces a plan with numbered tasks, dependencies, and complexity scores.
- The plan is written to `20-plan/plan-v<N>.md` in the standard format.
- Taskmaster's internal state (`.taskmaster/tasks/tasks.json`) is consistent with the plan.

### 7.3 Subtask file creation
- `run-stage execution` creates subtask files from the approved plan (same as standalone).
- Taskmaster task statuses are synced to match.

### 7.4 Execution ordering
- `next_task` correctly respects dependencies.
- Parallel agents can work on independent subtasks.

### 7.5 State consistency
- After execution, subtask files and Taskmaster tasks are in sync.
- If they disagree, subtask files are authoritative.

### 7.6 Repo cleanliness
- `.taskmaster/` lives in the task folder, not in any workspace.

## 8. Version Roadmap Additions

### V2 additions for Taskmaster variant
- Automatic dependency inference from code analysis
- Subtask re-planning when blocked tasks cascade
- Taskmaster dashboard integration with task folder state

### V3 additions for Taskmaster variant
- Cross-task dependency tracking (tasks depending on other tasks)
- Taskmaster cloud sync for team workflows
