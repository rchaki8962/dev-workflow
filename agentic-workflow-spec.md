# Spec: External Task Folder Workflow for Coding Agents

Status: Draft v3
Primary target: Claude Code
Secondary target: plain shell + editor usage
Storage model: External to workspaces

## 1. Overview

This spec describes a personal task-folder system for doing larger software tasks with coding agents.

The core idea:
- The real work happens in one or more workspaces (repos and folders).
- The planning, review, progress tracking, and coordination files live outside those workspaces in a durable task folder.
- The task moves through three stages: spec, plan, and execution.
- Each stage has a pluggable engine that does the creative work, and a review gate before proceeding.
- Each stage can run in a fresh session.

This system is a **bookkeeping and coordination layer**. It does not implement the engines that produce specs, plans, or code. It provides the scaffolding around them: durable task folders, artifact management, progress tracking, review gates, and stage transitions. Any combination of external tools, agent skills, or manual effort can serve as the engine for each stage.

The three stage engines:
1. **Spec engine**: produces a spec/PRD/requirements document given an original prompt and workspace access. Examples: a brainstorming skill, a PRD generator, manual authoring.
2. **Plan engine**: produces an implementation plan — a set of numbered tasks, each with title, description, and verification steps — given an approved spec. The plan may optionally include dependency information between tasks. The plan is the single source of truth for what needs to be done; `run-stage` uses it to create subtask files before execution begins. Examples: `superpowers:writing-plans`, Taskmaster AI, manual planning.
3. **Execution engine**: receives pre-created subtask files and implements them. Decides execution strategy (subagents, parallelism, sequential, manual). Examples: `superpowers:subagent-driven-development`, parallel agent dispatch, manual step-by-step execution.

This solves a common problem: once a task spans multiple sessions, important context gets trapped in chat history. The main session gets bloated, handoffs get weak, reviews lose independence, and it becomes hard to tell what changed, what was approved, and what still needs attention.

The task folder fixes that. A fresh session should be able to resume work by reading `00-progress.md`, `01-original-prompt.md`, and the linked approved files — without needing the original chat.

Important: the task folder does not contain the actual implementation. Code changes, tests, docs, and configs still live in the workspaces. The task folder only holds the support files needed to guide and track that work.

## 2. Core Concepts

- **Workspace**: a repo or folder where the real work happens. The task may touch one or more workspaces. Workspace paths are listed in the progress file.
- **Task**: one feature, project, or body of work being tracked.
- **Task folder**: the external folder for one task. Stores specs, plans, reviews, logs, progress, and subtask files.
- **Stage**: one of three steps: spec, plan, or execution.
- **Stage engine**: a pluggable external tool, skill, or process that does the creative work for one stage. This system defines input/output contracts for each engine (section 8) but does not constrain how the engine works internally.
  - **Spec engine**: receives the original prompt and workspace paths; produces a spec draft.
  - **Plan engine**: receives the approved spec and workspace paths; produces a plan with numbered tasks.
  - **Execution engine**: receives pre-created subtask files and the task folder path; implements the subtasks and records results.
- **Subtask file**: one file per subtask during execution. Contains description, status, verification, and execution summary. Designed so parallel agents can each own their own file without contention. Created by `run-stage` from the approved plan before the execution engine is invoked.
- **Progress file**: the index and control document for the task. The first thing any session reads.
- **Real output**: the actual work in the workspaces — code, tests, configs, docs, generated assets.

## 3. Goals

- Provide durable working memory for multi-session agentic work.
- Keep the orchestrator session lean and focused.
- Support producer/reviewer separation at each stage gate.
- Make it easy for a fresh session to pick up where the last one left off.
- Support tasks that span one or more workspaces.
- Reduce friction without hiding human approval gates.
- Be engine-agnostic: any tool, skill, or manual process can serve as the engine for any stage.

## 4. Non-Goals

- Full autonomous delivery with no human approval.
- Repo-local workflow configuration.
- Cursor/Windsurf native integration (deferred).
- Cloud agent orchestration (deferred).
- Automatic PR creation or merge automation.
- Implementing the stage engines themselves — only the bookkeeping contracts.

## 5. High-Level Architecture

### 5.1 Root layout

```text
~/.agentic-workflow/
  templates/
    progress.md
    spec.md
    implementation-plan.md
    subtask.md
    review.md

  scripts/
    task-start
    task-status
    run-stage
    stage-review
    stage-approve

  state/
    active-task.json

  tasks/
    <task-id>/
      ...
```

### 5.2 Integration surface

V1 integrates with Claude Code through personal configuration only:
- `~/.claude/commands/` for personal commands
- `~/.claude/settings.json` for hooks

No repo-local workflow config is required.

## 6. Task Folder Layout

```text
<task-id>/
  00-progress.md
  01-original-prompt.md

  10-spec/
    spec-v1.md
    spec-review-v1.md
    spec-approved.md

  20-plan/
    plan-v1.md
    plan-review-v1.md
    plan-approved.md

  30-execution/
    subtask-01.md
    subtask-02.md
    ...
    execution-review-v1.md
    implementation-summary.md

  90-logs/
    activity-log.md
```

Files are created as needed. A task that has just started will only have `00-progress.md` and `01-original-prompt.md`.

## 7. Workflow Stages

Each stage follows the same pattern:
1. `run-stage` validates prerequisites and invokes the configured stage engine.
2. The engine produces the stage artifact (spec draft, plan draft, or implemented subtasks).
3. `run-stage` handles teardown (updating progress, logging).
4. A reviewer (separate session) produces a review.
5. If approved, the artifact is promoted and `00-progress.md` is updated.

### 7.1 Spec stage

1. `run-stage spec` invokes the spec engine with the original prompt and workspace paths.
2. The engine produces `10-spec/spec-v1.md`.
3. `run-stage` updates `00-progress.md` and logs the activity.
4. Reviewer produces `10-spec/spec-review-v1.md`.
5. If approved, `10-spec/spec-approved.md` is created (copy of the approved draft).
6. `00-progress.md` is updated with the approved spec path.

If revision is needed, the engine (or author) creates `spec-v2.md` and the cycle repeats.

### 7.2 Plan stage

1. `run-stage plan` invokes the plan engine with the approved spec path and workspace paths.
2. The engine produces `20-plan/plan-v1.md` containing numbered tasks, each with title, description, and verification steps. The plan may optionally include dependency information between tasks.
3. `run-stage` updates `00-progress.md` and logs the activity.
4. Reviewer produces `20-plan/plan-review-v1.md`.
5. If approved, `20-plan/plan-approved.md` is created.
6. `00-progress.md` is updated.

### 7.3 Execution stage

1. `run-stage execution` reads the approved plan and creates subtask files in `30-execution/` (one per task from the plan), populating each with the task's title, description, and verification steps. It updates `00-progress.md` with the subtask index.
2. `run-stage` then invokes the execution engine, passing the task folder path and the list of subtask file paths.
3. The engine decides how to implement the subtasks — sequentially, in parallel, via subagents, or manually. Each agent owns its subtask file.
4. When all subtasks are complete, `run-stage` creates `30-execution/implementation-summary.md`.
5. `run-stage` updates `00-progress.md` and logs the activity.
6. Reviewer produces `30-execution/execution-review-v1.md`.
7. `00-progress.md` is updated.

## 8. Stage Engine Contracts

This system defines input/output contracts for each stage engine. The engines are free to use any internal strategy — the contracts specify only what the engine receives and what it must produce.

### 8.1 Spec engine contract

**Input:**
- Path to `01-original-prompt.md`
- List of workspace paths

**Output:**
- A spec draft file at `10-spec/spec-v<N>.md`

The spec draft should include at minimum: overview, requirements, constraints, and open questions. The engine may inspect workspaces to understand the codebase. The engine does not need to update `00-progress.md` — `run-stage` handles that.

### 8.2 Plan engine contract

**Input:**
- Path to the approved spec (`10-spec/spec-approved.md`)
- List of workspace paths

**Output:**
- A plan draft file at `20-plan/plan-v<N>.md`

The plan must contain numbered tasks, each with: title, description, and verification steps. These tasks are the unit of work — `run-stage` will create one subtask file per task before invoking the execution engine. The plan may optionally include dependency information between tasks (ordering, parallelism hints, dependency graph). The engine may inspect workspaces to understand the codebase. The engine does not need to update `00-progress.md` — `run-stage` handles that.

### 8.3 Execution engine contract

The execution engine receives pre-created subtask files and implements them. It does **not** decompose the plan — that decomposition is already done by the plan engine, and `run-stage` has already created subtask files from it.

**Input:**
- Path to the task folder
- List of subtask file paths in `30-execution/` (already created by `run-stage`, each with title, description, verification steps, and status `not-started`)

**Before starting a subtask:**
1. Set the subtask file's status to `in-progress`.

**After completing a subtask:**
1. Update the subtask file with: status (`done`), files changed, execution summary, and verification results.
2. Update the subtask index in `00-progress.md`.
3. Append a log entry to `90-logs/activity-log.md`.

**If a subtask is blocked:**
1. Set the subtask file's status to `blocked` and fill in the Blockers section.
2. Update `00-progress.md` with the blocker.

**After all subtasks are complete:**
Signal `run-stage` that execution is done (or simply return). `run-stage` handles the teardown (implementation summary, progress update).

The engine decides the execution strategy: which subtasks to run in parallel, whether to use subagents, how to handle dependencies. If the plan included dependency information, the engine should respect it.

### 8.4 Engine examples

| Stage | Example engine | Notes |
|-------|---------------|-------|
| Spec | `superpowers:brainstorming` | Explores intent and requirements before drafting |
| Spec | Manual authoring | Human writes the spec directly |
| Spec | PRD generator tool | External tool that produces requirements docs |
| Plan | `superpowers:writing-plans` | Reads spec, produces numbered implementation plan |
| Plan | Taskmaster AI | External tool that decomposes specs into task lists |
| Plan | Manual planning | Human writes the plan directly |
| Execution | `superpowers:subagent-driven-development` | Dispatches subagents per task with review stages |
| Execution | Parallel agent dispatch | Multiple agents claim and work subtasks concurrently |
| Execution | Manual step-by-step | Human implements tasks one at a time |

### 8.5 Example: integrating with subagent-driven-development

The `superpowers:subagent-driven-development` skill is one concrete execution engine. It dispatches a fresh subagent per task, then runs two review subagents (spec compliance, then code quality) before marking each task done.

Here is how it maps to the execution engine contract:

**Setup:**
The skill receives the list of subtask file paths (already created by `run-stage`). It reads each subtask file to understand the work. The skill may also use TodoWrite for in-session tracking — TodoWrite is ephemeral while subtask files are the durable cross-session record.

**Per subtask (the skill's normal flow, augmented):**
1. Set subtask file status to `in-progress`.
2. Dispatch implementer subagent. The prompt must include:
   - The subtask description (provide the full text — avoid making the subagent read files unnecessarily).
   - The subtask file path, with instructions to update it on completion:
     ```
     When you complete your work, update the subtask file at:
       <task-folder>/30-execution/subtask-NN.md

     Fill in:
     - Status → done
     - Files Changed → list of files you added/modified/deleted
     - What Changed → concise summary
     - Verification → check off items you verified
     ```
   - Relevant context about the workspace and codebase.
3. Handle implementer status (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED) as the skill prescribes.
4. Dispatch spec compliance reviewer subagent (the skill's first review stage).
5. Dispatch code quality reviewer subagent (the skill's second review stage).
6. Once both reviews pass: update `00-progress.md` subtask index, append to activity log.

**Review model overlap:**
The skill's per-subtask reviews (spec compliance + code quality) happen *during* execution as quality gates. The spec's execution review (section 10) happens *after* all subtasks are done as a formal approval gate. They serve different purposes and both apply.

**After all subtasks:**
The skill returns control to `run-stage`, which handles teardown (implementation summary, progress update). The formal execution review (section 10) proceeds as normal.

## 9. Subtask File Design

Each subtask gets its own file: `30-execution/subtask-NN.md`.

This is a deliberate design choice: parallel agents can each update their own subtask file without contention on a shared file.

### 9.1 Subtask file structure

```markdown
# Subtask NN: <title>

## Description
<what needs to be done>

## Verification
- [ ] <verification step 1>
- [ ] <verification step 2>

## Status
<not-started | in-progress | done | blocked>

## Execution Summary
<filled in by the agent after completing the subtask>

### Files Changed
<list of files added/modified/deleted>

### What Changed
<concise summary of the changes and why>

## Blockers
<any blockers or open questions — empty if none>
```

### 9.2 Subtask file fields — Files Changed

The "Files Changed" section records what the subtask actually modified in the workspaces. This is filled in by the agent after completing the subtask. It serves as the per-subtask change record — there is no separate change tracking system.

For git workspaces, the agent can derive this from `git diff`. For non-git folders, the agent self-reports.

### 9.3 Coordination model

- `run-stage execution` creates all subtask files from the approved plan before invoking the execution engine.
- The progress file (`00-progress.md`) contains the subtask index with status and links.
- Each subtask file is owned by one agent at a time.
- The execution engine updates the subtask index in the progress file as subtasks complete.
- For parallel execution: agents claim subtasks, update their own files, and the orchestrator reconciles the progress file.

## 10. Review Model

### 10.1 Review points

Reviews happen when each stage is complete:
- After spec draft is produced
- After plan draft is produced
- After execution is complete

### 10.2 Reviewer independence

A review must be performed by a different session than the producer.

The reviewer must receive:
- `00-progress.md`
- `01-original-prompt.md`
- Approved files from earlier stages
- The artifact under review

The reviewer must not require prior chat history.

### 10.3 Review output structure

Every review must use this structure:

```markdown
# <Stage> Review

## Verdict
<APPROVE | REVISE | BLOCKED>

## Inputs Read
<list of files reviewed>

## Findings
### Critical
<issues that must be fixed>

### Important
<issues that should be fixed>

### Minor
<suggestions>

## Required Revisions
<specific changes needed before approval — empty if APPROVE>

## Residual Risks
<known risks that remain even after approval>
```

## 11. Progress File Design

`00-progress.md` is the most important file in the task folder. It is the first thing any session reads.

### 11.1 Top section (must fit one screen)

```markdown
# Task: <title>

- **Task ID**: <id>
- **Current Stage**: <spec | plan | execution | complete>
- **Approved Spec**: <path or "pending">
- **Approved Plan**: <path or "pending">
- **Last Updated**: <timestamp>

## Workspaces
- ~/projects/my-app (primary, executing from here)
- ~/projects/shared-lib
```

### 11.2 Full sections

After the top section:

- **Stage Status**: current stage details, what's been completed
- **Subtask Index**: table of subtask id, title, status, and file path — the coordination point for parallel agents
- **Blockers / Open Questions**: anything blocking progress
- **Recent Activity**: last 5-10 log entries (append new, trim old)
- **Next Actions**: what the next session should do
- **Reader Guide**: different instructions for implementer vs reviewer roles

## 12. Change Tracking

There is no separate change tracking system. Each subtask file records the files it changed in its "Files Changed" section. The `implementation-summary.md` aggregates this across all subtasks.

For git workspaces, the agent can use `git diff` to populate the change list. For non-git folders, the agent self-reports.

## 13. Verification

Verification commands belong in the implementation plan's subtask descriptions, not in a separate metadata file. The plan author decides what needs to be verified for each subtask.

During execution, the agent runs verification as part of its work and records results in the subtask file's verification checklist. Verification output is also appended to `90-logs/activity-log.md` with timestamp, command, pass/fail, and summary.

## 14. Templates

The following templates live in `~/.agentic-workflow/templates/`. Scripts use them to seed new task files.

### 14.1 `progress.md`

Seeds `00-progress.md`. Contains:
- Header with task title, id, current stage, approved file paths, last updated
- Workspaces section (list of paths, filled in by `task-start`)
- Stage status section
- Subtask index (empty table, populated during execution)
- Blockers / open questions section
- Recent activity section (last 5-10 entries)
- Next actions section
- Reader guide (implementer vs reviewer instructions)

### 14.2 `spec.md`

Seeds `10-spec/spec-v1.md`. Contains:
- Header with task title
- Sections: overview, requirements, constraints, open questions
- Placeholder for the spec author to fill in

### 14.3 `implementation-plan.md`

Seeds `20-plan/plan-v1.md`. Contains:
- Header with task title
- Reference to approved spec path
- Approach / design section
- Numbered subtask list, where each subtask has: title, description, verification steps
- Dependencies between subtasks (if any)
- Risks / open questions

### 14.4 `subtask.md`

Seeds `30-execution/subtask-NN.md`. Contains the structure defined in section 9.1.

### 14.5 `review.md`

Seeds review files (`spec-review-v1.md`, `plan-review-v1.md`, `execution-review-v1.md`). Contains the structure defined in section 10.3.

## 15. Scripts

### 15.1 `task-start`

```
task-start <title> [--workspace <path>]...
```

Must:
- Accept one or more workspace paths (defaults to current directory if none given)
- Create the task folder under `~/.agentic-workflow/tasks/<task-id>/`
- Generate `task-id` as `<date>-<slugified-title>` (e.g. `2026-04-08-auth-rewrite`)
- Create `01-original-prompt.md` (captures the user's original request)
- Initialize `00-progress.md` from template, including the workspace paths in the Workspaces section
- Create empty subdirectories: `10-spec/`, `20-plan/`, `30-execution/`, `90-logs/`
- Set the active task pointer in `~/.agentic-workflow/state/active-task.json`
- If an active task already exists, archive the pointer (record previous task id, do not delete files)
- Append to `90-logs/activity-log.md`

### 15.2 `task-status`

```
task-status
```

Must:
- Read the active task from `state/active-task.json`
- Print: task id, title, current stage, workspaces, blockers, next actions
- Output should fit in a terminal screen

### 15.3 `run-stage <stage>`

```
run-stage <spec|plan|execution>
```

`run-stage` is the generic glue between the bookkeeping layer and the stage engines. It does not produce specs, write plans, or implement code — all of that is the engine's job.

**For all stages — setup:**
- Validate prerequisites for the requested stage (see below)
- Log stage start to `90-logs/activity-log.md`
- Invoke the configured engine for the stage, providing the required inputs (see section 8)

**For all stages — teardown (after the engine completes):**
- Update `00-progress.md` to reflect stage completion
- Log stage completion to `90-logs/activity-log.md`

**Stage-specific prerequisites, setup, and teardown:**

| Stage | Prerequisites | Setup before engine | Engine inputs | Additional teardown |
|-------|--------------|-------------------|---------------|-------------------|
| `spec` | `01-original-prompt.md` exists | None | Original prompt path, workspace paths | None |
| `plan` | `10-spec/spec-approved.md` exists | None | Approved spec path, workspace paths | None |
| `execution` | `20-plan/plan-approved.md` exists | Parse approved plan, create subtask files in `30-execution/` (one per task), update `00-progress.md` with subtask index | Task folder path, list of subtask file paths | Create `30-execution/implementation-summary.md` (aggregated from subtask files) |

### 15.4 `stage-review <stage>`

```
stage-review <spec|plan|execution>
```

Must:
- Validate that the stage's artifact exists (spec draft, plan draft, or completed execution)
- Print the list of files the reviewer should read, in order
- Print the expected output file path for the review
- Update `00-progress.md` to reflect "in review" status

### 15.5 `stage-approve <stage>`

```
stage-approve <spec|plan|execution>
```

Must:
- For spec: copy the latest reviewed spec draft to `spec-approved.md`
- For plan: copy the latest reviewed plan draft to `plan-approved.md`
- For execution: mark execution as complete in `00-progress.md`
- Update `00-progress.md` with approved file paths and stage transitions
- Append to `90-logs/activity-log.md`

## 16. Claude Code Integration

### 16.1 Personal commands

The following personal commands should be created in `~/.claude/commands/`:

| Command | Maps to |
|---------|---------|
| `/task-start` | `task-start` script |
| `/task-status` | `task-status` script |
| `/run-stage` | `run-stage` script |
| `/stage-review` | `stage-review` script |
| `/stage-approve` | `stage-approve` script |

### 16.2 Hooks

Personal hooks in `~/.claude/settings.json`:

- **SessionStart**: if an active task exists, inject a summary (task id, stage, workspaces, next actions) into the session context.
- **PostToolUse** (optional): after file edit tools, record the touched file path in the active subtask file or activity log.

### 16.3 No repo-local config

The system must not require changes to:
- Repo-local `CLAUDE.md`
- `.cursor/rules`
- `.gitignore` or `.git/info/exclude`

## 17. Edge Cases

### 17.1 Execution crash recovery

The progress file records the last completed subtask. If a session crashes mid-execution:
1. A new session reads `00-progress.md`.
2. It identifies which subtasks are `done` vs `in-progress` vs `not-started`.
3. It resumes from the first non-completed subtask.

Subtask files that are `in-progress` at crash time may have partial execution summaries. The resuming agent should verify the state of those subtasks before continuing.

### 17.2 Plan divergence during execution

During execution, the agent may discover the plan was wrong or incomplete.

Rules:
- **Minor deviations**: note them in the subtask file's execution summary. Continue.
- **Major deviations** (new subtask needed, subtask should be skipped, approach fundamentally changes): pause execution and update `00-progress.md` with a blocker. Wait for user decision.

The approved plan is not updated retroactively. Deviations are recorded in subtask files and the implementation summary.

### 17.3 Context window management

Not every file needs to be loaded at once:
- **Always load**: `00-progress.md` (the index)
- **Load on demand**: individual subtask files (only the ones being worked on)
- **Load for review**: approved spec, approved plan
- **Rarely needed during execution**: spec drafts, review files from earlier stages

The progress file's reader guide should make this explicit.

### 17.4 Task abandonment

In v1, abandoned tasks are handled minimally:
- `task-start` with a new task overwrites the active task pointer but does not delete old task files.
- Old task folders persist under `~/.agentic-workflow/tasks/` until manually cleaned up.
- The previous active task id is recorded in the new task's activity log.

### 17.5 Engine not configured

If `run-stage` is invoked but no engine is configured for the requested stage:
- Print a message explaining that no engine is set for that stage.
- Suggest the user can run the stage manually (e.g., write the spec draft by hand) and then proceed to review.
- Do not fail silently.

## 18. Safety and Isolation

- The system must not write task files into the workspaces.
- The system must not modify repo-local AI config.
- The system must not require `.gitignore` changes.
- The system may read workspaces to inspect files and metadata.
- The only changes to workspaces are the real implementation work carried out during execution.

## 19. Acceptance Criteria

### 19.1 Single workspace

- Starting a task creates a task folder under `~/.agentic-workflow/tasks/`.
- `00-progress.md` lists the workspace path and is readable.
- Active task pointer is set.

### 19.2 Multiple workspaces

- Starting a task with multiple workspace paths creates one shared task folder.
- `00-progress.md` lists all workspace paths.
- A fresh session can identify all workspaces from `00-progress.md`.

### 19.3 Review workflow

- A review can be initiated for spec, plan, and execution stages.
- A review result can be created with the verdict structure.
- Approving a stage updates `00-progress.md` and creates the approved file.

### 19.4 Stage engine invocation

- `run-stage` can invoke the configured engine for each stage.
- Each engine receives the correct inputs per its contract.
- `run-stage` handles teardown after the engine completes.

### 19.5 Execution automation

- The execution stage runs in one engine-driven pass.
- Subtask files are created and updated automatically.
- No per-subtask closeout command is needed.
- Verification runs are recorded.

### 19.6 Resume from files

- A fresh session can determine current state by reading `00-progress.md`, `01-original-prompt.md`, and linked approved files.
- No prior chat history is required.

### 19.7 Prompt capture

- The original user prompt is saved in `01-original-prompt.md`.

### 19.8 No repo pollution

- No changes to repo-local `CLAUDE.md`, `.cursor/rules`, or `.gitignore`.
- Task files remain outside the workspaces.

## 20. Version Roadmap

### V1 (this spec)
- Core three-stage workflow: spec → plan → execute
- Three pluggable stage engines with defined contracts
- Review gates with producer/reviewer separation
- Durable task folder with progress file, subtask files, activity log
- Multi-workspace support (paths listed in progress file)
- 5 scripts (`task-start`, `task-status`, `run-stage`, `stage-review`, `stage-approve`), 5 templates
- Claude Code integration via personal commands and hooks
- Parallel-safe subtask files

### V2
- Folder-mode snapshot/diff system (baseline manifests, checkpoint snapshots, automated change detection)
- Separate handoff files for multi-person workflows
- `decisions.md` and `blockers.md` as standalone files
- Plan amendment protocol (formal process for mid-execution changes)
- `task-archive` and `task-cancel` commands
- Review depth modes (standard / strict)
- Structured workspace metadata file (git branch, SHA, remote URL, worktree path)
- `validate-task` as a user-facing command with structured output
- Engine configuration file for persisting engine preferences per stage

### V3
- Cursor / Windsurf native integration
- Cross-tool support (agent-tool-agnostic daemon)
- Dashboard UI for task overview
- Cloud agent orchestration

## 21. Preferred Implementation Order

1. Templates (5 files)
2. `task-start` script
3. `task-status` script
4. `run-stage` script
5. `stage-review` script
6. `stage-approve` script
7. Claude Code personal commands
8. Claude Code personal hooks

## 22. Design Principle

Optimize for explicitness, inspectability, and restartability over cleverness. Durable files are the source of truth. Chats are disposable. Engines are replaceable.
