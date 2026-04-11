# Product Requirements Document: dev-workflow

Status: Draft
Date: 2026-04-11

## 1. Document Intent

This is a greenfield PRD. It assumes no existing implementation. It captures the requirements and architectural direction for a checkpoint-oriented task continuity system, derived from first-principles analysis of the user's pain points and desired workflow.

## 2. Product Summary

dev-workflow is a behind-the-scenes continuity and history layer for agent-assisted technical work.

Users work naturally with any coding agent. When they want to persist a milestone, hand off to another agent, resume in a new session, or later understand how work was done, they invoke dev-workflow. What happens on invocation can be rich and complex. Invoking it should not be.

The product has three layers:
- A **deterministic CLI** backed by SQLite that owns all persistence and structure
- **Generated markdown views** in a task folder for human and agent consumption
- **Two agent skills** (generic, not tied to one agent) that reduce friction: one for context awareness, one for checkpoint capture

## 3. Problem Statement

Users doing serious work with coding agents face recurring problems:

1. **Session continuity**: Tasks exceed context windows. When a session ends, the user must re-brief a fresh agent from scratch. The user knows what they were doing, but the agent doesn't.
2. **Artifact preservation**: Specs, plans, design decisions, and other key documents produced during work are trapped in chat history unless deliberately saved.
3. **Agent-agnostic handoff**: Users want to review work with a different coding agent, or switch tools mid-task. There's no standard way to package task state for a cold handoff.
4. **Development history**: Months later, users need to understand how a task was implemented -- what decisions shaped it, what alternatives were rejected, what was verified. Chat history is ephemeral and unstructured.
5. **Progress visibility**: During long executions, users want to see what's done, what's running, and what's left.
6. **Workflow overhead**: Existing task management tools impose rigid pipelines (spec -> plan -> execute) with explicit commands for each step. This ceremony is proportional to every task regardless of size.

The core problem is not a lack of brainstorming or planning tools. The core problem is the lack of a reliable continuity, artifact capture, and history layer around that work.

## 4. Product Vision

A private, structured, agent-readable task workspace that acts as durable memory, handoff package, review surface, and implementation history for long-running technical work.

**Guiding principle: trivial to invoke, rich when it runs.**

## 5. Goals

The product must:

- Preserve task context across sessions so a fresh agent can resume without prior chat
- Support reliable handoff to a completely different coding agent
- Capture important milestones as structured checkpoints
- Preserve artifacts (specs, plans, etc.) produced between checkpoints, not just summaries
- Support review of current work by a different coding agent
- Maintain a structured development record for historical traceability
- Provide a deterministic control plane (CLI) so state stays understandable and recoverable
- Keep user-facing interaction lightweight -- no rigid command sequences
- Allow rich internal structure when it improves reliability
- Store everything outside the code repository by default
- Support multiple concurrent tasks across isolated spaces, with cross-space visibility

## 6. Non-Goals

The product must not:

- Become a brainstorming, planning, or execution engine (use existing tools)
- Require every task to follow a prescribed multi-step workflow
- Require the user to memorize a command sequence
- Depend on chat transcripts as the source of truth
- Lock the user into one coding agent ecosystem
- Force overhead on small tasks that don't need it

## 7. Target Users

- Developers doing long-running implementation work with coding agents
- Developers who switch between multiple agents for implementation and review
- Developers who care about durable specs, plans, and design history
- Solo developers working across many interrupted sessions

## 8. Jobs To Be Done

### 8.1 Session Continuity

When I leave a session and return later, I want enough structured context that the next agent can pick up where the last one left off, without me re-explaining everything.

### 8.2 Milestone Preservation

When a spec crystallizes, a key decision is made, or a chunk of implementation lands, I want to persist that milestone with its context, decisions, and artifacts.

### 8.3 Cross-Agent Handoff

When I want another coding agent to continue or review the work, I want a self-contained handoff package that any tool can consume.

### 8.4 Cross-Agent Review

When I want a different coding agent to review progress, artifacts, or quality, I want enough structured context that the review is meaningful without replaying the conversation.

### 8.5 Development History

When I revisit a task months later, I want to understand: what was the intent, what decisions shaped it, what alternatives were rejected, what code changed, what was verified, and what was the quality.

### 8.6 Progress Visibility

When work spans many subtasks over a long time, I want a dashboard view of what's done, what's in progress, and what's next.

### 8.7 Artifact Control

When coding agents produce intermediate documents (specs, plans, notes), I want control over where those artifacts are stored and how they're organized.

### 8.8 Multi-Task, Multi-Space Work

I work on multiple tasks concurrently across different contexts (personal projects, org work, different teams). Each task is in a different session, at a different stage of progress. I want each task isolated in its own space, with the ability to see everything at a glance across all spaces when I need to.

## 9. Core Principles

### 9.1 Checkpoint Over Pipeline

The mental model is: initialize a task, work naturally, checkpoint at meaningful moments, resume or hand off later.

Not: remember a fixed series of stages and approvals for every task.

Checkpoints have freeform labels (not enforced stages). The user can checkpoint twice during spec work, skip straight from brainstorming to coding, revise anything -- whatever the actual work demands.

### 9.2 Deterministic Persistence

Every important state mutation flows through the CLI. The CLI produces consistent structure, validates inputs, and maintains referential integrity.

Skills and agents add intelligence about *when* and *what* to capture. The CLI owns *how* it's stored.

### 9.3 Rich Internals, Light Surface

The product may maintain complex internal structure (multiple tables, cross-referenced records, generated views) if that improves handoff quality, resume reliability, or historical traceability.

This complexity is paid by the tool, not the user. The user sees: "checkpoint saved." The tool does: insert checkpoint record, merge decisions, upsert artifacts, update open questions, regenerate handoff document.

### 9.4 Progressive Disclosure for Agent Context

Agents have finite context windows. The task workspace should be designed for progressive disclosure:

- **Index layer** (~500-2K tokens): a single handoff document with summaries and links. Enough for a quick resume.
- **Operational layer** (~2-5K tokens): current state, decisions, open questions. Enough for deep context.
- **Archival layer** (unbounded): full development record, checkpoint history, raw artifacts. For audit and review.

No file repeats another file's content. Each file owns one level of detail. Summaries point down to detail; detail files don't duplicate upward.

### 9.5 Storage / Presentation Split

The source of truth is a structured store (SQLite). The task folder on disk is a generated view -- markdown files produced from the structured data.

This means:
- The task folder is a cache, not a store. Delete it and regenerate.
- Backup is one file.
- Cross-task queries are trivial.
- Atomic writes -- no half-written checkpoint if a session dies.
- Different output formats (JSON for agents, markdown for humans) from the same source.

### 9.6 Agent-Agnostic by Default

The persistence model and generated views must work with any coding agent that can read files and call CLI commands. Skills are designed as generic markdown instruction files, not tied to one agent's framework.

Claude Code is the primary target for skill invocation patterns. But the CLI and task folder work with Cursor, OpenCode, Copilot, or a human with a terminal.

## 10. Architecture

```
Agent Skills (awareness + capture)
    |
    |---> CLI (deterministic checkpoint engine)
    |       init, checkpoint, resume, status, list, regenerate
    |
    |---> SQLite store (source of truth)
    |       tasks, checkpoints, decisions, artifacts, verifications
    |
    |---> Generated task folder (markdown views)
            HANDOFF.md, context/, artifacts/, record/
```

### 10.1 SQLite Store

One database file. All structured data lives here: tasks, checkpoints, decisions, artifacts (including document content), verifications, open questions.

Artifact content (specs, plans, design docs) is stored as text in the artifacts table. These are typically small documents. Binary artifact support is deferred.

### 10.2 Generated Task Folder

Markdown files generated from SQLite by the CLI. Organized for progressive disclosure:

```
<task-folder>/

  HANDOFF.md                     # The index. Summaries + links.
                                 # Any agent reads ONLY this to start.

  context/
    original-prompt.md           # What the user originally asked for
    current-state.md             # Latest checkpoint: milestone, summary,
                                 #   next steps, open questions
    decisions.md                 # All decisions with rationale.
                                 #   Links to artifacts/checkpoints for detail.
    open-questions.md            # Unresolved questions

  artifacts/
    <type>-<name>-v<N>.md        # Versioned artifact content

  record/
    development-record.md        # Structured archival document:
                                 #   intent, decisions, verifications,
                                 #   quality reviews, outcome.
                                 #   Sections with summaries + links.
    checkpoints.md               # Chronological log:
                                 #   number, timestamp, milestone, summary
```

**HANDOFF.md** is the star. It's the ONE file a cold-starting agent reads. It contains: task summary, current status, key decisions (one line each with links), artifact index (type + version + link), open questions, next steps, and a pointer to the development record for full history.

### 10.3 CLI Commands

Six core commands:

| Command | Purpose |
|---------|---------|
| `init <name>` | Create task. Store original prompt. Generate initial task folder. Return paths as JSON. |
| `checkpoint <slug>` | Accept structured payload (JSON via stdin). Persist to SQLite. Regenerate all markdown views. |
| `resume <slug>` | Return context bundle (JSON or markdown). The cold-start entry point. |
| `status [slug]` | Quick dashboard. No slug = all tasks. With slug = current state detail. |
| `list` | List tasks with one-line status. Supports cross-space listing. |
| `regenerate <slug>` | Rebuild all markdown views from SQLite. Recovery and refresh. |

Plus space management: `space create`, `space list`, `space remove`, `space info`.

**Spaces** are isolated namespaces for separating work contexts (e.g., personal projects vs org work vs different teams). Each task belongs to exactly one space. Tasks don't move between spaces. Slugs can repeat across spaces without collision.

**Active space resolution** (first match wins):
1. `--space` CLI flag on the command
2. `DEV_WORKFLOW_SPACE` environment variable
3. `default_space` from config file
4. Hardcoded default: `"default"`

The default space is auto-created on first use. Every CLI invocation operates within one active space. The only cross-space operation is `list --all-spaces`, which shows all tasks across all spaces with space labels.

**Typical multi-space usage:**

```bash
# Create spaces once
dev-workflow space create personal --description "Side projects"
dev-workflow space create acme-eng --description "Acme engineering"

# Work in org space (default)
dev-workflow init "Auth Rewrite"
dev-workflow checkpoint auth-rewrite < payload.json

# Work in personal space
DEV_WORKFLOW_SPACE=personal dev-workflow init "Blog Engine"
dev-workflow --space personal status

# See everything
dev-workflow list --all-spaces
```

### 10.4 Checkpoint Payload

What the agent sends to the CLI when checkpointing:

```json
{
  "milestone": "spec-finalized",
  "summary": "Finalized auth spec after evaluating three approaches...",
  "decisions": [
    {
      "title": "JWT over session tokens",
      "rationale": "Stateless, better for horizontal scaling",
      "alternatives": ["session tokens", "OAuth2 delegation"],
      "context": "User prioritized horizontal scaling"
    }
  ],
  "artifacts": [
    {
      "type": "spec",
      "name": "auth-middleware-spec",
      "version": 1,
      "description": "Auth middleware spec, approach B",
      "content": "# Auth Middleware Spec\n..."
    }
  ],
  "verifications": [
    {
      "type": "test-run",
      "result": "pass",
      "detail": "42/42 unit tests passing",
      "command": "pytest tests/ -v"
    }
  ],
  "insights": ["Existing middleware is more coupled to session store than expected"],
  "next_steps": ["Plan implementation"],
  "open_questions": ["Support refresh tokens?"],
  "resolved_questions": ["Which auth approach? -> JWT"]
}
```

All fields except `milestone` and `summary` are optional. A minimal checkpoint:

```json
{
  "milestone": "session-end",
  "summary": "Explored three auth approaches, leaning toward JWT"
}
```

### 10.5 Resume Output

`resume <slug> --format json` returns a structured context bundle:

```json
{
  "slug": "auth-task",
  "title": "Auth Middleware Rewrite",
  "space": "default",
  "last_milestone": "spec-finalized",
  "last_checkpoint_at": "2026-04-11T14:30:00Z",
  "checkpoint_count": 3,
  "summary": "JWT-based auth spec finalized after evaluating three approaches...",
  "next_steps": ["Plan implementation", "Decide on refresh token strategy"],
  "open_questions": ["Support refresh tokens?"],
  "decisions": [
    { "number": 1, "title": "JWT over session tokens", "rationale": "Stateless, scales horizontally" },
    { "number": 2, "title": "Postgres for session audit log", "rationale": "Existing infra, ACID guarantees" }
  ],
  "artifacts": [
    { "type": "spec", "name": "auth-middleware-spec", "version": 2, "description": "JWT-based auth spec, final" }
  ],
  "recent_verifications": [
    { "type": "test-run", "result": "pass", "detail": "42/42 unit tests" }
  ],
  "handoff_path": "~/.dev-workflow/default/tasks/2026-04-11-auth-task/HANDOFF.md",
  "detail_paths": {
    "decisions": "~/.dev-workflow/default/tasks/2026-04-11-auth-task/context/decisions.md",
    "record": "~/.dev-workflow/default/tasks/2026-04-11-auth-task/record/development-record.md",
    "checkpoints": "~/.dev-workflow/default/tasks/2026-04-11-auth-task/record/checkpoints.md"
  }
}
```

This is the summary layer (~500 tokens). An agent reads this and follows `detail_paths` only if it needs more depth. `resume --format md` regenerates the task folder if stale and returns the path to HANDOFF.md.

### 10.6 Two Agent Skills

Generic markdown instruction files. Any agent framework with a skill/rule mechanism can load them. Claude Code is the primary invocation target.

**Skill 1: task-awareness**

Invoked at session start or resume. Loads the last checkpoint via `dev-workflow resume`, presents brief status, and primes the agent with checkpoint-recognition signals:

- A decision was made (approach chosen, trade-off resolved)
- An artifact was produced or significantly revised
- A meaningful implementation milestone was reached
- A direction change happened (pivot, scope change)
- An open question was resolved or a new blocker surfaced
- The user is about to end the session

When the agent recognizes a checkpoint-worthy moment, it suggests saving. The skill teaches the agent *when* to suggest, relative to what was last captured.

**Skill 2: task-checkpoint**

Invoked when actually checkpointing. Drafts the structured payload by analyzing the conversation since the last checkpoint:

1. Summarizes what happened
2. Extracts decisions with rationale and alternatives
3. Identifies artifacts and captures their content
4. Notes verifications, insights, resolved/new questions
5. Proposes next steps
6. Presents draft to user for review/edit
7. On approval, calls `dev-workflow checkpoint <slug>` with the payload

The heavy lifting is in the drafting. A good draft means the user just approves.

## 11. Functional Requirements

### FR-1 Task Initialization

The system must allow creating a task context with a name, optional original prompt, optional workspace paths, and optional space assignment.

Slug generation must be deterministic with collision handling.

### FR-2 Checkpoint Creation

The system must accept a structured checkpoint payload and atomically persist it: inserting the checkpoint record, merging decisions, upserting artifacts with content, recording verifications, updating open questions, and regenerating all markdown views.

### FR-3 Checkpoint History

The system must preserve all checkpoints chronologically. Each checkpoint records: milestone name, timestamp, summary, decisions made, artifacts produced, verifications performed, insights, next steps, and question changes.

### FR-4 Resume / Cold-Start

The system must synthesize a context bundle from the latest task state that is sufficient for a fresh agent to resume without prior chat history.

The bundle must support both structured (JSON) and human-readable (markdown) formats.

### FR-5 Cross-Agent Handoff and Review

The generated task folder must be self-contained and tool-agnostic. Any agent that can read markdown files or call CLI commands can consume it.

The handoff document (HANDOFF.md) must provide enough context for a reviewing agent to understand: current state, key decisions, artifacts produced, verification results, and what's next.

### FR-6 Progressive Disclosure

The task folder must be organized for progressive disclosure. The handoff document contains summaries with links to detail files. No file repeats another file's content.

An agent doing a quick resume loads the index layer. An agent doing deep review follows links. Each pays only for the depth it needs.

### FR-7 Development Record

The system must maintain a structured development record distinct from the checkpoint log. The record is archival: organized by topic (decisions, verifications, outcomes), not chronologically.

It must support answering: what was the intent, what decisions shaped the implementation, what alternatives were rejected, what changed, what was verified, what was the quality.

### FR-8 Artifact Preservation

The system must store artifact content (specs, plans, design docs, etc.) in the structured store, versioned by name and version number. Artifacts are registered during checkpoints.

Generated copies in the task folder are views, not the source of truth.

### FR-9 Verification Capture

The system must capture verification evidence (test runs, code reviews, manual checks) with: type, result, detail, and command. This feeds both the development record and the handoff document.

### FR-10 Deterministic CLI

All state mutations must flow through the CLI. The CLI must produce consistent structure, validate inputs, and maintain referential integrity in the SQLite store.

Skills and agents add intelligence. The CLI owns correctness.

### FR-11 Storage Control

All data must live outside the code repository by default. The storage location must be configurable (base directory, environment variable).

### FR-12 Space Isolation and Multi-Task Work

Tasks must be organized into spaces (isolated namespaces). Each task belongs to one space. Tasks don't move between spaces. Slugs can repeat across spaces.

The user works on multiple tasks concurrently (each in a separate session), potentially across different spaces. The system must support:

- Creating and managing multiple spaces (personal, org, team-specific)
- Active space resolution via CLI flag, env var, config, or default
- Per-space task isolation (each space has independent task sets)
- Cross-space visibility via `list --all-spaces` showing all tasks with space labels
- Quick status across all active tasks to see what's in progress where

### FR-13 View Regeneration

All markdown views in the task folder must be regenerable from the SQLite store at any time. A `regenerate` command must rebuild the complete task folder.

### FR-14 Progress and Status

The system must provide a status view showing: all tasks with last milestone and date (list view), or detailed status for one task (checkpoint count, decisions, artifacts, open questions, next steps).

### FR-15 Task Closure

The system must support explicit task closure with a final summary capturing: what was accomplished, what changed, what was verified, remaining risks, and follow-up work. (Deferred from v1; schema supports it via `closed_at` column.)

## 12. Checkpoint Semantics

A checkpoint is the primary persistence action. It is freeform, not stage-gated.

### Invocation

Two paths:
1. **User-triggered**: The user says "checkpoint this" or approves after the agent suggests.
2. **Agent-suggested**: The awareness skill primes the agent to recognize checkpoint-worthy moments and suggest saving.

In both cases, the checkpoint skill drafts the payload, the user reviews and approves, and the CLI persists.

### Checkpoint Flow

```
Agent notices checkpoint-worthy moment
  -> Suggests: "Want to save a checkpoint?"
  -> User approves (or triggers manually)
  -> task-checkpoint skill drafts payload from conversation
  -> User reviews draft, edits if needed, approves
  -> CLI persists atomically to SQLite
  -> CLI regenerates all markdown views
  -> Confirmation: "Checkpoint #N saved"
```

### What the CLI Does on Checkpoint

| Action | Target | How |
|--------|--------|-----|
| Save raw payload | `checkpoints` table | Insert record |
| Merge decisions | `decisions` table | Append, auto-number per task |
| Upsert artifacts | `artifacts` table | Insert or update by name+version, store content |
| Record verifications | `verifications` table | Insert linked to checkpoint |
| Update questions | Derive from checkpoint | Add new open, mark resolved |
| Update task record | `tasks` table | Last milestone, timestamp, summary |
| Regenerate views | Task folder | Rebuild HANDOFF.md and all markdown files |

## 13. SQLite Schema

```sql
CREATE TABLE spaces (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    space TEXT NOT NULL REFERENCES spaces(name),
    summary TEXT NOT NULL DEFAULT '',
    last_milestone TEXT NOT NULL DEFAULT '',
    last_checkpoint_at TEXT,
    checkpoint_count INTEGER NOT NULL DEFAULT 0,
    workspaces TEXT NOT NULL DEFAULT '[]',
    task_folder TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    closed_at TEXT,
    UNIQUE(slug, space)
);

CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_number INTEGER NOT NULL,
    milestone TEXT NOT NULL,
    summary TEXT NOT NULL,
    insights TEXT NOT NULL DEFAULT '[]',
    next_steps TEXT NOT NULL DEFAULT '[]',
    open_questions TEXT NOT NULL DEFAULT '[]',
    resolved_questions TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    UNIQUE(task_id, checkpoint_number)
);

CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    decision_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    alternatives TEXT NOT NULL DEFAULT '[]',
    context TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    UNIQUE(task_id, decision_number)
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    UNIQUE(task_id, name, version)
);

CREATE TABLE verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    command TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
```

## 14. Risks and Trade-offs

### 14.1 Over-Capture

If checkpoints capture too much low-value information, the workspace becomes noisy. Mitigation: the skill drafts checkpoints from conversation analysis, user reviews before persisting. Quality is gated by human approval.

### 14.2 Under-Capture

If checkpoints are too shallow, resumption quality fails. Mitigation: the checkpoint skill is designed to extract decisions, artifacts, verifications, and insights -- not just a summary. The payload schema encourages richness.

### 14.3 Checkpoint Fatigue

If the awareness skill suggests too often, users will ignore it. Mitigation: the skill compares against the last checkpoint and only suggests when meaningful delta exists.

### 14.4 Skill Quality Variance

Skills are instructions, not code. Agent compliance varies. Mitigation: the CLI validates the payload structure and enforces schema. Bad skill output is caught at persistence time.

### 14.5 SQLite as Single Point

All data in one file. Corruption means data loss. Mitigation: SQLite is battle-tested for single-writer workloads. Periodic backups are one `cp` command.

### 14.6 Agent Lock-In Perception

Despite being agent-agnostic, the skills are optimized for Claude Code. Mitigation: CLI and task folder work with any tool. Skills are portable markdown. The value proposition doesn't require skills.

## 15. What's Deferred

- Task close / archive command (schema supports it via `closed_at`)
- Structured mode (typed checkpoints like spec-approval, plan-approval)
- Binary artifact support (v1 is text content only)
- Claude Code hooks (SessionStart auto-resume, PostToolUse auto-suggest)
- Skill auto-detection of checkpoint moments (v1 is suggest + approve)
- Task import (ingest artifacts from an existing directory)
- Dashboard UI

## 16. Differences from Companion PRD

A separate PRD (`agent-task-continuity-prd.md`) was written by another agent for the same problem space. Key differences:

| Topic | This PRD | Companion PRD |
|-------|----------|---------------|
| **Storage architecture** | SQLite as source of truth, markdown as generated views | Not specified (implementation choice) |
| **Progressive disclosure** | Core principle with defined layers | Not addressed |
| **Skill design** | Two concrete skills (awareness + capture) with defined behavior | Abstract ("skills may assist") |
| **Checkpoint flow** | Agent drafts, user approves, CLI persists | Not specified beyond "lightweight" |
| **Structured mode** | Deferred entirely | Proposed as optional overlay (typed checkpoints, signoffs) |
| **Canonical vs raw artifacts** | All content in SQLite, views are generated | Distinguishes canonical files from raw imports on disk |
| **Task folder** | Generated cache, deletable and regenerable | Primary artifact store |

The companion PRD is more abstract and requirement-focused. This PRD makes concrete architectural commitments based on specific design decisions reached during brainstorming.

## 17. Success Criteria

1. A fresh session can resume a task by calling one CLI command -- no prior chat needed.
2. A different coding agent can read HANDOFF.md cold and understand the task state, decisions, artifacts, and next steps.
3. HANDOFF.md uses progressive disclosure: summaries with links, no content duplication.
4. All structured data lives in SQLite. All task folder files are regenerable.
5. A checkpoint captures: milestone, summary, decisions with rationale, artifacts with content, verifications, insights, next steps, and open questions.
6. The development record provides a structured archival view of how the task was developed.
7. Small tasks work with just `init` + one or two checkpoints. No mandatory stages.
8. The skills work as generic markdown files consumable by any coding agent.
9. Space isolation works (create, list, remove, per-space task listing).
10. Multiple concurrent tasks across spaces work independently, with `list --all-spaces` providing a unified view.
11. Space resolution (CLI flag > env var > config > default) works correctly.
