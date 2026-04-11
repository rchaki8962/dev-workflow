# Design: dev-workflow Checkpoint Architecture

Status: Draft
Date: 2026-04-11

## Summary

Redesign dev-workflow from a stage-pipeline system (spec -> plan -> execution with formal gates) to a checkpoint-oriented continuity layer. The CLI becomes a deterministic checkpoint engine backed by SQLite. The plugin slash commands are replaced by two generic agent skills. The task folder becomes a generated view, not a store.

The guiding principle: **trivial to invoke, rich when it runs.**

## Problem

The current dev-workflow imposes a rigid stage pipeline (`/run-stage spec`, `/stage-approve spec`, `/run-stage plan`, ...) that creates ceremony proportional to every task, regardless of size or complexity. Users must remember the command sequence and invoke each step explicitly.

The actual pain points are:

1. **Session continuity** -- re-briefing a fresh agent with full context when resuming across sessions is the sharpest pain point. The user knows what they were doing but has to re-explain everything.
2. **Artifact preservation** -- specs, plans, decisions, and other key documents must survive outside chat history as durable files.
3. **Agent-agnostic handoff** -- a completely different coding agent must be able to read the task state cold and either review or continue the work.
4. **Development record** -- months later, the user needs to understand how a task was developed: what decisions shaped it, what alternatives were rejected, what code changed, what verification was done.
5. **Progress visibility** -- during long executions, seeing what's done, running, and remaining.

The current design over-serves orchestration and under-serves continuity.

## Product Boundary

dev-workflow is:
- A checkpoint-oriented task continuity engine
- A deterministic CLI backed by SQLite
- A generator of agent-consumable context bundles (markdown views + structured JSON)
- A normalizer and preserver of artifacts produced by other tools

dev-workflow is not:
- A brainstorming, planning, or execution engine (use Superpowers, Taskmaster, etc.)
- A rigid stage pipeline
- A tool that requires every task to follow spec -> plan -> execution

## Architecture

```
Agent Skills (awareness + capture)
    |
    |---> Python CLI (deterministic checkpoint engine)
    |       init, checkpoint, resume, status, list, regenerate
    |
    |---> SQLite store (source of truth)
    |       tasks, checkpoints, decisions, artifacts, verifications
    |
    |---> Generated markdown views (task folder)
            HANDOFF.md, context/, record/, artifacts/
```

### Storage / Presentation Split

- **SQLite** is the source of truth. One database at `~/.dev-workflow/store.db`. All structured data (tasks, checkpoints, decisions, artifacts including content, verifications) lives here.
- **Task folder** is a generated view. Markdown files are produced by the CLI from SQLite data. They can be deleted and regenerated at any time.
- **Artifact content** is stored in SQLite (specs, plans, and similar documents are typically small text documents). The task folder contains generated copies for human/agent reading.

This means:
- Backup is one file.
- Cross-task queries are trivial SQL.
- Atomic writes -- no half-written checkpoint if a session dies.
- The task folder is a cache, not a store.

## CLI Commands

Six commands plus space management (kept from current design).

### `dev-workflow init <name>`

Creates a new task.

**Input:** Task name. Optional `--prompt` (inline text), `--prompt-file` (path), `--space`, `--slug`, `--workspace` (repeatable).

**Behavior:**
1. Generate slug from name (existing slug logic, kept as-is). On collision: append `-2`, `-3`, etc.
2. Insert task record into SQLite.
3. Store original prompt as the first artifact (type: `prompt`).
4. Generate task folder with initial `HANDOFF.md`.
5. Return JSON: `{ slug, task_id, task_folder, handoff_path }`.

### `dev-workflow checkpoint <slug>`

Persists a checkpoint. This is the core command.

**Input:** JSON payload via stdin (see Checkpoint Payload below). Optional `--space`.

**Behavior:**
1. Validate payload structure.
2. Insert checkpoint record into SQLite (`checkpoints` table).
3. Merge decisions into `decisions` table (auto-numbered, linked to checkpoint).
4. Upsert artifacts: store metadata and content into `artifacts` table.
5. Insert verifications into `verifications` table.
6. Update open questions: add new, mark resolved.
7. Update task record: last milestone, last checkpoint timestamp, summary.
8. Regenerate all markdown views in the task folder.
9. Return JSON: `{ checkpoint_number, decisions_added, artifacts_added, handoff_path }`.

### `dev-workflow resume <slug>`

Returns the full context bundle for a cold start.

**Input:** Slug. Optional `--format json|md` (default: json), `--space`.

**Behavior:**
- `--format json`: Query SQLite, return structured JSON with: task metadata, current state summary, decisions list (title + rationale, no full detail), artifact index (type + description + path), open questions, next steps, last N checkpoints (summary level), and paths to detail files.
- `--format md`: Regenerate task folder if stale, return path to `HANDOFF.md`.

The JSON format is designed for agent consumption. The md format is for human reading or agents that prefer markdown.

### `dev-workflow status [slug]`

Quick progress dashboard.

**Input:** Optional slug. Optional `--space`, `--all-spaces`, `--format json|table`.

**Behavior:**
- No slug: list all tasks in active space with one-line status (slug, last milestone, last checkpoint date, summary).
- With slug: current state detail -- milestone, checkpoint count, decisions count, artifacts count, open questions, next steps.

### `dev-workflow list`

List tasks.

**Input:** Optional `--space`, `--all-spaces`, `--format json|table`, `--milestone <filter>`.

**Behavior:** Query SQLite for tasks. Display: slug, title, last milestone, last checkpoint date, one-line summary. `--all-spaces` queries across all spaces.

### `dev-workflow regenerate <slug>`

Regenerate all markdown views from SQLite.

**Input:** Slug. Optional `--space`.

**Behavior:**
1. Query all data for the task from SQLite.
2. Delete existing task folder contents (except any untracked files, warn about those).
3. Regenerate: `HANDOFF.md`, `context/current-state.md`, `context/decisions.md`, `context/open-questions.md`, `artifacts/*`, `record/development-record.md`, `record/checkpoints.md`.
4. Return JSON: `{ task_folder, files_generated }`.

Useful when: a view is corrupted, you want a clean regeneration after manual edits to SQLite, or after a schema migration.

### Space Management (kept as-is)

`space create`, `space list`, `space remove`, `space info`. Unchanged from current design.

## Checkpoint Payload Schema

The JSON payload sent to `dev-workflow checkpoint` via stdin:

```json
{
  "milestone": "spec-finalized",
  "summary": "Finalized auth spec after evaluating three approaches...",
  "decisions": [
    {
      "title": "JWT over session tokens",
      "rationale": "Stateless, better for horizontal scaling",
      "alternatives": ["session tokens", "OAuth2 delegation"],
      "context": "Discussed during brainstorming, user prioritized scaling"
    }
  ],
  "artifacts": [
    {
      "type": "spec",
      "name": "auth-middleware-spec",
      "version": 1,
      "description": "Auth middleware spec, approach B -- JWT-based",
      "content": "# Auth Middleware Spec\n\n## Overview\n..."
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
  "insights": [
    "The existing middleware is more coupled to the session store than expected"
  ],
  "next_steps": ["Plan implementation", "Decide on refresh token strategy"],
  "open_questions": ["Support refresh tokens?"],
  "resolved_questions": ["Which auth approach? -> JWT (decision #1)"]
}
```

All fields except `milestone` and `summary` are optional. A minimal checkpoint is just:

```json
{
  "milestone": "session-end",
  "summary": "Explored three auth approaches, leaning toward JWT"
}
```

## SQLite Schema

One database at `~/.dev-workflow/store.db`.

```sql
CREATE TABLE spaces (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL  -- ISO 8601
);

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,      -- "2026-04-11-auth-task"
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    space TEXT NOT NULL REFERENCES spaces(name),
    summary TEXT NOT NULL DEFAULT '',
    last_milestone TEXT NOT NULL DEFAULT '',
    last_checkpoint_at TEXT,       -- ISO 8601
    checkpoint_count INTEGER NOT NULL DEFAULT 0,
    workspaces TEXT NOT NULL DEFAULT '[]',  -- JSON array of paths
    task_folder TEXT NOT NULL,     -- generated view path
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    closed_at TEXT,                -- NULL until task is closed
    UNIQUE(slug, space)
);

CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_number INTEGER NOT NULL,
    milestone TEXT NOT NULL,
    summary TEXT NOT NULL,
    insights TEXT NOT NULL DEFAULT '[]',     -- JSON array
    next_steps TEXT NOT NULL DEFAULT '[]',   -- JSON array
    open_questions TEXT NOT NULL DEFAULT '[]',
    resolved_questions TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    UNIQUE(task_id, checkpoint_number)
);

CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    decision_number INTEGER NOT NULL,  -- per-task auto-increment
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    alternatives TEXT NOT NULL DEFAULT '[]',  -- JSON array
    context TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    UNIQUE(task_id, decision_number)
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,            -- "spec", "plan", "prompt", "summary", etc.
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
    type TEXT NOT NULL,            -- "test-run", "code-review", "manual-check"
    result TEXT NOT NULL,          -- "pass", "fail", "partial"
    detail TEXT NOT NULL DEFAULT '',
    command TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
```

## Generated Task Folder Structure

```
~/.dev-workflow/<space>/tasks/<date>-<slug>/

  HANDOFF.md                     # Index document. Summaries + links.
                                 # Any agent reads ONLY this to start.
                                 # ~1-2 pages. Regenerated every checkpoint.

  context/
    original-prompt.md           # The initial request (from init --prompt)
    current-state.md             # Latest checkpoint: milestone, summary,
                                 #   next steps, open questions
    decisions.md                 # All decisions: number, title, rationale
                                 #   Links to artifacts/checkpoints for detail
    open-questions.md            # Unresolved questions

  artifacts/
    spec-v1.md                   # Artifact content, versioned
    spec-v2.md
    plan-v1.md
    <type>-<name>-v<N>.md

  record/
    development-record.md        # Structured archival document:
                                 #   intent, decisions, changes,
                                 #   verifications, quality reviews, outcome
                                 #   Sections with summaries + links to detail
    checkpoints.md               # Chronological checkpoint log:
                                 #   number, timestamp, milestone, one-line summary
```

### Progressive Disclosure Principle

No file repeats another file's content. Each file owns one level of detail.

**HANDOFF.md** is the index layer (~500-2K tokens):
- Task summary and current status
- Key decisions (one line each) with links to `context/decisions.md#N`
- Artifact index (type, version, one line) with links to `artifacts/<file>`
- Open questions (list)
- Next steps (list)
- Pointer to `record/development-record.md` for full history

**context/ files** are the operational layer:
- `current-state.md`: latest checkpoint snapshot, next actions
- `decisions.md`: all decisions with rationale, links to checkpoints
- `open-questions.md`: unresolved items

**record/ files** are the archival layer:
- `development-record.md`: full structured history, with summaries per section and links to raw checkpoints and artifacts
- `checkpoints.md`: chronological log

**artifacts/** hold actual content. Referenced by other files, never duplicated.

An agent doing a quick resume loads HANDOFF.md (~500-2K tokens). An agent doing a deep review follows links (~5-15K). An agent auditing history goes into record/ and reads checkpoints. Each pays only for the depth it needs.

## Skill Design

Two generic skills. Designed as markdown instruction files consumable by any coding agent (Claude Code, Cursor, OpenCode, etc.). Claude Code is the primary target for invocation patterns.

### Skill 1: task-awareness

**Purpose:** Loads task context into the session and primes the agent to recognize checkpoint-worthy moments.

**When invoked:** Session start, or when resuming a task.

**Behavior:**
1. Calls `dev-workflow resume <slug> --format json` to load the latest state.
2. Presents a brief status to the user: current milestone, what's next, open questions.
3. Primes the agent with checkpoint recognition signals:
   - A decision was made (approach chosen, technology picked, trade-off resolved)
   - An artifact was produced or significantly revised (spec, plan, design doc)
   - A meaningful implementation milestone was reached (module complete, tests passing)
   - A direction change happened (pivot, scope change, requirement clarified)
   - An open question was resolved or a new blocker surfaced
   - The user is about to end the session
4. When the agent recognizes a checkpoint-worthy moment since the last checkpoint, it suggests: "We've made progress since the last checkpoint -- [reason]. Want me to save?"

**Key principle:** The skill loads context and gets out of the way. It does not impose workflow. It makes the agent aware that checkpoints exist and when they'd be valuable.

**Requires:** `dev-workflow` CLI installed and on PATH.

### Skill 2: task-checkpoint

**Purpose:** Drafts a rich checkpoint payload and persists it via the CLI.

**When invoked:** User says "checkpoint this", or approves after task-awareness suggests one.

**Behavior:**
1. Analyzes conversation since the last checkpoint.
2. Drafts the checkpoint payload:
   - Summarizes what happened (milestone name + narrative summary)
   - Extracts decisions with rationale, alternatives, and context
   - Identifies artifacts produced and captures their content
   - Captures verification results (test runs, reviews)
   - Notes insights and resolved/new open questions
   - Proposes next steps
3. Presents the draft to the user for review and editing.
4. On approval, calls `dev-workflow checkpoint <slug> --stdin` with the JSON payload.
5. Confirms: "Checkpoint #N saved: `<milestone>`. [N] decisions, [N] artifacts captured."

**Key principle:** The heavy lifting is in the drafting. A good draft means the user just approves, maybe tweaks one line. The skill earns its value by distilling the conversation into structured, preservable context.

**Requires:** `dev-workflow` CLI installed and on PATH. task-awareness should have been invoked earlier in the session (to establish the active task slug and last checkpoint baseline).

### How They Work Together

```
New session
  |-- User: "continue working on auth-task"
  |-- task-awareness invoked
  |     |-- Calls: dev-workflow resume auth-task --format json
  |     |-- Presents brief status to user
  |     |-- Primes agent with checkpoint signals
  |
  |-- [freeform work: brainstorming, coding, reviewing, whatever]
  |
  |-- Agent notices: "we just finalized the JWT decision"
  |     |-- Agent: "checkpoint-worthy -- want to save?"
  |     |-- User: "yes"
  |
  |-- task-checkpoint invoked
  |     |-- Drafts payload from conversation
  |     |-- User reviews/approves
  |     |-- Calls: dev-workflow checkpoint auth-task --stdin
  |     |-- CLI persists to SQLite, regenerates views
  |
  |-- [freeform work continues...]
```

### Agent-Agnostic Design

For non-Claude-Code agents:
- Call `dev-workflow resume <slug>` directly to get context (JSON or HANDOFF.md).
- Work normally.
- Call `dev-workflow checkpoint <slug>` with a JSON payload to persist.
- The skills are markdown files -- any agent framework with a skill/rule mechanism can load them.

## Resume Flow

The critical path for session continuity.

`dev-workflow resume <slug> --format json` returns:

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
    { "number": 2, "title": "Postgres for session audit log", "rationale": "..." }
  ],
  "artifacts": [
    { "type": "spec", "name": "auth-middleware-spec", "version": 2, "description": "..." }
  ],
  "recent_verifications": [
    { "type": "test-run", "result": "pass", "detail": "42/42 tests" }
  ],
  "handoff_path": "~/.dev-workflow/default/tasks/2026-04-11-auth-task/HANDOFF.md",
  "detail_paths": {
    "decisions": ".../context/decisions.md",
    "record": ".../record/development-record.md",
    "checkpoints": ".../record/checkpoints.md"
  }
}
```

This is the summary layer. An agent reads this (~500 tokens), gets the full picture, and follows `detail_paths` only if it needs more depth.

## Migration Path

### What Gets Thrown Away
- Entire `claude_plugin/` directory (8 slash commands, config, manifests)
- `StageManager` (`stage.py`) -- rigid pipeline
- Review system (review setup, review approve)
- Stage setup / teardown orchestration
- Models: `Review`, `ReviewVerdict`, `Stage` as enforced pipeline
- `FileTaskStore` (replaced by SQLite)
- `StateManager` (replaced by SQLite)
- `templates.py` (replaced by markdown generation from SQLite)
- Most of the 423 existing tests

### What Gets Kept / Adapted
- `Config` + space resolution logic (kept, adapted for SQLite path)
- `SpaceManager` (adapted to use SQLite instead of `spaces.json`)
- Slug generation (`slug.py`) -- works as-is
- `Space` and `Task` dataclasses (simplified, adapted)
- `progress.py` concepts (adapted for checkpoint-based progress)
- `exceptions.py` -- error types still useful
- `cli.py` -- Click CLI structure (rewritten with new commands)

### New Components
- SQLite store module (replaces `FileTaskStore` + `StateManager`)
- Markdown view generator (generates task folder from SQLite data)
- Checkpoint processor (parses payload, distributes across tables)
- Two skill files (markdown, no Python code)

## What's Deferred

- Claude Code hooks (SessionStart auto-resume, PostToolUse auto-checkpoint suggestions)
- Task close / archive command (the `closed_at` column exists in the schema for future use)
- Task import (ingest artifacts from an existing directory)
- Structured mode (typed checkpoints like spec-approval, plan-approval)
- Dashboard UI
- Skill auto-detection of checkpoint moments (v1 is agent-suggested, user-approved)
- Binary artifact support (v1 stores text content only; binary files like screenshots would need a blob column or file-reference approach)

## Acceptance Criteria

1. A fresh session can resume a task by calling `dev-workflow resume <slug>` -- no prior chat history needed.
2. A different coding agent can read `HANDOFF.md` cold and understand the task state, key decisions, and what's next.
3. `HANDOFF.md` uses progressive disclosure: summaries with links, not content duplication.
4. All structured data lives in SQLite. All task folder files are regenerable via `dev-workflow regenerate <slug>`.
5. A checkpoint captures: milestone, summary, decisions, artifacts (with content), verifications, insights, next steps, and open questions.
6. The development record (`record/development-record.md`) provides a structured archival view: intent, decisions with rationale, verification results, quality outcomes.
7. Small tasks work with just `init` + one or two checkpoints. No mandatory stages.
8. The skills work as generic markdown instruction files consumable by any coding agent.
9. Space management continues to work (create, list, remove, isolation).
10. `dev-workflow list` and `dev-workflow status` provide cross-task visibility.
