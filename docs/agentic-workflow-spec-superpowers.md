# Spec: External Task Folder Workflow — Superpowers Variant

Status: Draft v1
Companion to: `agentic-workflow-spec.md` (standalone spec)

## 1. Overview

This spec describes the Superpowers variant of the external task folder workflow. It shares all structure, stages, review model, and integration patterns with the standalone spec (`agentic-workflow-spec.md`). This document only describes what changes when Superpowers skills are used as the stage engines.

**Read the standalone spec first.** This document assumes familiarity with it.

### Engine mapping

| Stage | Superpowers skill | Role |
|-------|------------------|------|
| Spec | `superpowers:brainstorming` | Explores intent, asks clarifying questions, proposes approaches, writes design spec |
| Plan | `superpowers:writing-plans` | Reads spec, produces bite-sized TDD tasks with file-level detail |
| Execution | `superpowers:subagent-driven-development` | Dispatches one subagent per task with two-stage review (spec compliance + code quality) |

Supporting skills used during execution:
- `superpowers:verification-before-completion` — enforced before any completion claim
- `superpowers:requesting-code-review` — dispatches code-reviewer subagent after each task and after all tasks
- `superpowers:receiving-code-review` — handles review feedback with technical rigor
- `superpowers:executing-plans` — alternative to subagent-driven-development for same-session sequential execution

### What stays the same

Everything else:
- Task folder layout
- Review model (the formal review gates from the standalone spec)
- Progress file design
- Safety and isolation rules
- Claude Code integration (commands and hooks)
- All v1/v2/v3 scoping

## 2. Spec Stage: `superpowers:brainstorming`

### 2.1 How it maps

The brainstorming skill is a guided conversation that explores the user's intent before producing a design spec. When integrated with this workflow:

**Standard skill flow:**
1. Explore project context (files, docs, recent commits in workspaces).
2. Ask clarifying questions one at a time.
3. Propose 2-3 approaches with trade-offs and a recommendation.
4. Present design sections and get user approval.
5. Write design spec.
6. Run spec review loop via `spec-document-reviewer` subagent (up to 3 iterations).

**Workflow integration:**
- The skill reads `01-original-prompt.md` as its starting input (instead of the chat prompt).
- The skill writes its output to `10-spec/spec-v<N>.md` (instead of its default `docs/superpowers/specs/` location).
- The skill's internal spec review loop (subagent-driven, up to 3 iterations) happens *before* the formal review gate from the standalone spec. They are complementary: the skill's loop is a quality pass; the formal review is an independent approval gate.
- After the skill completes, `run-stage` updates `00-progress.md` and logs the activity.
- The skill does **not** invoke `superpowers:writing-plans` at the end (as it normally would). Instead, control returns to `run-stage`, and the formal review gate proceeds.

### 2.2 Output location override

The brainstorming skill normally writes to `docs/superpowers/specs/`. In this workflow, `run-stage spec` must direct the skill to write to `10-spec/spec-v<N>.md` instead. The skill's output content is unchanged — only the path is overridden.

### 2.3 Review overlap

| Review | When | Who | Purpose |
|--------|------|-----|---------|
| Skill's internal spec review | During spec authoring | `spec-document-reviewer` subagent | Quality pass (catch issues before the draft is "done") |
| Formal spec review (standalone spec, section 10) | After spec draft is complete | Independent reviewer session | Approval gate (decide if spec is ready to plan against) |

Both apply. The skill's internal review is not a substitute for the formal review.

## 3. Plan Stage: `superpowers:writing-plans`

### 3.1 How it maps

The writing-plans skill reads a spec and produces a detailed implementation plan with bite-sized, TDD-driven tasks.

**Standard skill flow:**
1. Check scope — if multiple independent subsystems, break into separate plans.
2. Map file structure (files to create/modify, responsibilities).
3. Write plan with: goal, architecture, tech stack, numbered tasks.
4. Each task is bite-sized (2-5 minutes), TDD-oriented: write failing test → verify failure → implement → verify pass → commit.
5. Run plan review loop via `plan-document-reviewer` subagent (up to 3 iterations).

**Workflow integration:**
- The skill reads `10-spec/spec-approved.md` as its input.
- The skill writes its output to `20-plan/plan-v<N>.md` (instead of its default `docs/superpowers/plans/` location).
- The skill's internal plan review loop happens *before* the formal plan review gate. Both apply.
- After the skill completes, `run-stage` updates `00-progress.md` and logs the activity.
- The skill does **not** offer the execution choice at the end (subagent-driven vs inline). Instead, control returns to `run-stage`, and the formal review gate proceeds. Execution happens via `run-stage execution`.

### 3.2 Output location override

Same as spec stage — `run-stage plan` directs the skill to write to `20-plan/plan-v<N>.md` instead of `docs/superpowers/plans/`.

### 3.3 Task granularity

The writing-plans skill produces very fine-grained tasks (each 2-5 minutes, single actions). These map 1:1 to subtask files that `run-stage execution` will create. This granularity is a good fit for the subagent-driven-development execution engine, which dispatches one subagent per task.

If the granularity is too fine for the task at hand, the user can consolidate tasks during plan review before approval.

### 3.4 Review overlap

| Review | When | Who | Purpose |
|--------|------|-----|---------|
| Skill's internal plan review | During plan authoring | `plan-document-reviewer` subagent | Quality pass |
| Formal plan review (standalone spec, section 10) | After plan draft is complete | Independent reviewer session | Approval gate |

## 4. Execution Stage: `superpowers:subagent-driven-development`

### 4.1 How it maps

The subagent-driven-development skill dispatches a fresh subagent per task, with two-stage review (spec compliance, then code quality) after each.

**Workflow integration:**

`run-stage execution` creates subtask files from the approved plan (as specified in the standalone spec), then invokes the skill.

**Setup:**
The skill receives the list of subtask file paths. It reads each to understand the work. The skill also creates a TodoWrite for in-session tracking (ephemeral — subtask files are the durable record).

**Per subtask:**
1. Set subtask file status to `in-progress`.
2. Dispatch implementer subagent with:
   - Full subtask description (from the subtask file — avoid making the subagent read files).
   - Subtask file path with update instructions:
     ```
     When you complete your work, update the subtask file at:
       <task-folder>/30-execution/subtask-NN.md

     Fill in:
     - Status → done
     - Files Changed → list of files you added/modified/deleted
     - What Changed → concise summary
     - Verification → check off items you verified
     ```
   - Workspace paths and codebase context.
3. Handle implementer status:
   - **DONE**: proceed to review.
   - **DONE_WITH_CONCERNS**: note concerns, proceed to review.
   - **NEEDS_CONTEXT**: provide missing info, re-dispatch.
   - **BLOCKED**: assess blocker — provide context, upgrade model, break down task, or escalate to user.
4. Dispatch spec compliance reviewer subagent.
5. If issues found: implementer fixes, reviewer re-checks.
6. Dispatch code quality reviewer subagent.
7. If issues found: implementer fixes, reviewer re-checks.
8. Once both reviews pass: update `00-progress.md` subtask index, append to `90-logs/activity-log.md`.

**After all subtasks:**
1. Dispatch final code reviewer for the entire implementation (using `superpowers:requesting-code-review`).
2. Return control to `run-stage`, which creates `30-execution/implementation-summary.md` and updates progress.
3. The formal execution review (standalone spec, section 10) proceeds.

### 4.2 Alternative: `superpowers:executing-plans`

For simpler tasks or when subagent overhead is undesirable, `superpowers:executing-plans` can be used instead. It executes all tasks sequentially in the current session (no subagent dispatch).

**Differences from subagent-driven-development:**
- No subagent dispatch — the current session implements each task directly.
- No per-task spec compliance or code quality review subagents.
- Uses `superpowers:finishing-a-development-branch` at the end.
- Better for small plans (<5 tasks) or tasks that are tightly coupled.

The bookkeeping contract is the same — subtask files are updated identically.

### 4.3 Verification enforcement

The `superpowers:verification-before-completion` skill is enforced throughout execution:
- Before any subtask is marked `done`, verification commands must be run and evidence recorded.
- Before the final completion claim, all tests must pass with fresh output.
- No "should pass" or "probably works" — only verified evidence.

This applies to both subagent-driven and inline execution.

### 4.4 Review layers during execution

The Superpowers variant has the most review layers of any engine combination:

| Review | When | Who | Scope |
|--------|------|-----|-------|
| Implementer self-review | After implementing each subtask | Implementer subagent | Own changes |
| Spec compliance review | After each subtask | Reviewer subagent | Subtask vs spec |
| Code quality review | After each subtask | Reviewer subagent | Code standards |
| Final code review | After all subtasks | Reviewer subagent | Entire implementation |
| Formal execution review | After execution stage | Independent reviewer session | Approval gate |

The first four are the skill's internal quality gates. The last is the standalone spec's formal approval gate. All five apply.

## 5. Modified `run-stage` Behavior

### 5.1 `run-stage spec`

1. Validate `01-original-prompt.md` exists.
2. Invoke `superpowers:brainstorming` with:
   - Input: path to `01-original-prompt.md`, workspace paths.
   - Output override: write to `10-spec/spec-v<N>.md`.
   - Suppress: do not chain to `superpowers:writing-plans` at end.
3. Teardown: update `00-progress.md`, log activity.

### 5.2 `run-stage plan`

1. Validate `10-spec/spec-approved.md` exists.
2. Invoke `superpowers:writing-plans` with:
   - Input: path to `10-spec/spec-approved.md`, workspace paths.
   - Output override: write to `20-plan/plan-v<N>.md`.
   - Suppress: do not offer execution choice at end.
3. Teardown: update `00-progress.md`, log activity.

### 5.3 `run-stage execution`

1. Validate `20-plan/plan-approved.md` exists.
2. Parse approved plan, create subtask files in `30-execution/`, update `00-progress.md` with subtask index.
3. Invoke `superpowers:subagent-driven-development` (or `superpowers:executing-plans`) with:
   - Input: task folder path, list of subtask file paths.
4. Teardown: create `30-execution/implementation-summary.md`, update `00-progress.md`, log activity.

## 6. Skill Output Location Overrides

The Superpowers skills normally write their outputs to `docs/superpowers/` inside the workspace. In this workflow, all skill outputs are redirected to the task folder:

| Skill | Default output | Workflow output |
|-------|---------------|----------------|
| `superpowers:brainstorming` | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` | `<task-folder>/10-spec/spec-v<N>.md` |
| `superpowers:writing-plans` | `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` | `<task-folder>/20-plan/plan-v<N>.md` |

This keeps the workspace clean and the task folder self-contained.

Implementation note: the `run-stage` script must communicate the output path to the skill. This can be done via the skill invocation prompt (instructing the skill where to write) or via environment variables. The exact mechanism depends on how Claude Code skill invocation supports path overrides.

## 7. Workflow Chaining

The Superpowers skills have built-in chaining: brainstorming invokes writing-plans, writing-plans offers execution. In this workflow, **that chaining is suppressed**. Each skill runs in isolation within its stage, and the formal review gates sit between them:

```
brainstorming → [formal spec review] → writing-plans → [formal plan review] → subagent-driven-development → [formal execution review]
```

This is intentional. The review gates are the workflow's quality control. Letting skills chain directly would skip them.

## 8. When to Use This Variant

Use the Superpowers variant when:
- You want the most structured, review-heavy workflow
- You are using Claude Code as your primary tool
- You want automated per-task review (spec compliance + code quality) during execution
- You want TDD-driven task granularity in plans
- You are comfortable with subagent dispatch overhead

Use the standalone variant when:
- You want to mix engines freely (e.g., Taskmaster for planning, manual execution)
- You want less review overhead
- You want to use non-Claude-Code tools for some stages
- You want coarser task granularity

Use the Taskmaster variant when:
- You need explicit dependency graphs and automated execution ordering
- You want complexity-based model routing
- You have many tasks (10+) with complex interdependencies

## 9. Prerequisites

The Superpowers variant requires:
- Claude Code with the Superpowers plugin installed (v5.0.5+)
- All referenced skills available: `brainstorming`, `writing-plans`, `subagent-driven-development`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`

No additional MCP servers or external tools are required.

## 10. Acceptance Criteria (additions to standalone)

In addition to the standalone spec's acceptance criteria:

### 10.1 Spec engine
- `run-stage spec` invokes `superpowers:brainstorming`.
- The skill writes to `10-spec/spec-v<N>.md`, not `docs/superpowers/specs/`.
- The skill does not chain to `writing-plans`.

### 10.2 Plan engine
- `run-stage plan` invokes `superpowers:writing-plans`.
- The skill writes to `20-plan/plan-v<N>.md`, not `docs/superpowers/plans/`.
- The skill does not offer an execution choice.
- Tasks are bite-sized and TDD-oriented.

### 10.3 Execution engine
- `run-stage execution` creates subtask files before invoking the skill.
- `superpowers:subagent-driven-development` dispatches one subagent per subtask.
- Per-subtask spec compliance and code quality reviews run.
- Final code review runs after all subtasks.
- Subtask files are updated with status, files changed, and execution summary.

### 10.4 Verification
- `superpowers:verification-before-completion` is enforced before any done claim.
- Fresh verification evidence is recorded in subtask files and activity log.

### 10.5 Review gates preserved
- Formal review gates (spec, plan, execution) are not bypassed by skill-internal reviews.
- Skill chaining is suppressed between stages.

### 10.6 Workspace cleanliness
- No `docs/superpowers/` directory created in workspaces.
- All skill outputs go to the task folder.
