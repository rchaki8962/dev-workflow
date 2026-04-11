# Design: dev-workflow as a Hybrid Continuity Layer

Status: Draft
Date: 2026-04-11

## Summary

`dev-workflow` should not try to become the best brainstorming, planning, or implementation engine. Those jobs are already served by tools like Superpowers, Taskmaster, feature-dev, and similar systems.

Its strongest value proposition is narrower and more durable: a private, human-readable, agent-usable continuity layer that preserves task context across sessions and across agents, while keeping artifacts outside normal repo workflows unless the user explicitly wants them in the repo.

The product should be lightweight by default, with an optional structured mode for large or risky tasks. Underneath that low-ceremony experience, it should keep a deterministic CLI companion that preserves order, validation, and inspectability.

The user-facing workflow should be checkpoint-centric rather than stage-centric.

The moment of invocation should be light and optional. What happens after invocation can be rich, structured, and even internally complex if that complexity improves reliability of handoff, resume, and auditability.

## Problem

The user problem is not "I need one more workflow engine."

The user problem is:

- Long-running tasks exceed context windows.
- Important reasoning is often lost across sessions.
- Specs, plans, design decisions, and verification evidence need to survive outside chat history.
- Different coding agents may need to review or continue the same task.
- Users want control over where these artifacts live.
- Heavy workflow ceremony becomes frustrating for smaller tasks.
- Remembering and invoking a prescribed plugin command flow creates avoidable cognitive overhead.

This means `dev-workflow` should optimize first for continuity, handoff, and artifact control, not for stage enforcement.

It should also avoid a false choice between "automatic" and "structured." The right goal is minimal user ceremony with deterministic mechanics under the hood.

The user is not asking for less structure in the stored artifacts. The user is asking for less ceremony in how that structure is activated.

## Product Boundary

`dev-workflow` is:

- A private task packet manager
- A resumable context and handoff system
- A normalizer for artifacts produced by other agent tools
- A progress and verification tracker for long-running work
- A deterministic CLI-backed control plane for packet operations

`dev-workflow` is not:

- A replacement for brainstorming skills
- A replacement for planning tools
- A replacement for execution engines or subagent frameworks
- A mandatory stage machine for every task
- A tool that requires every task to pass through `spec -> plan -> execution`

## Core Value Proposition

If `dev-workflow` disappeared, users should lose something that is difficult to recreate with prompt discipline alone:

- A durable task packet that a fresh session can use without prior chat history
- A concise, trustworthy handoff between humans and agents
- A canonical place for specs, plans, decisions, progress, and summaries
- A checkpoint history that explains how the work reached its current state
- A clean way to redirect and normalize outputs from external tools
- A private working memory outside the main repo workflow

This is the center of gravity for the product.

## Deterministic Backbone

Minimal direct interaction does not mean removing the CLI. It means the CLI should become the stable control plane while hooks, plugins, slash commands, and agent instructions provide the ergonomic layer.

The CLI should own:

- Task packet creation and path resolution
- Canonical file writes and versioning
- Checkpoint creation and milestone recording
- Validation of required artifacts and fields
- State transitions such as approvals and closure
- Append-only activity logging and timestamps
- Status, handoff, and resume synthesis

Automation should call the CLI rather than mutating packet files ad hoc whenever possible.

Skills may add richer judgment about when to checkpoint and what to capture, but the resulting persistence should still flow through deterministic CLI operations.

This is important for four reasons:

- **Determinism**
  - The same command should produce the same file layout and validation behavior
- **Inspectability**
  - Users can understand what happened without trusting hidden agent behavior
- **Portability**
  - The workflow can be used across different agent environments
- **Debuggability**
  - When state becomes confusing, the CLI provides a clear source of truth and recovery path

## Operating Model

### Lightweight Mode

The default mode should minimize ceremony.

Typical flow:

1. Initialize or select a task context.
2. Work normally with the coding agent and any preferred tools.
3. At meaningful milestones, create a checkpoint that persists the current state.
4. Resume later or hand off to another agent using synthesized handoff context.
5. Close the task with a final summary.

The default user experience should feel like normal agent interaction with occasional persistence, not like following a workflow script.

That does not imply shallow persistence. A single checkpoint can perform substantial structured work behind the scenes if it materially improves the quality of future handoff or resumption.

Small tasks may need only one or two checkpoints and may never need a formal spec or plan.

### Checkpoint Model

A checkpoint is the primary user-visible persistence action in the default workflow.

Each checkpoint should capture enough context for a later session or a different agent to continue safely:

- Milestone name and timestamp
- Current objective and state of the work
- Important insights discovered since the last checkpoint
- Decisions made and trade-offs considered
- Key artifacts produced or updated
- Open questions, blockers, or unresolved risks
- Recommended next action

Checkpoints may be:

- **User-triggered**
  - The user explicitly asks to persist the current milestone
- **Agent-suggested**
  - A skill or hook notices a likely milestone and proposes checkpointing

The system should optimize for making checkpoints easy and reliable, because they are the foundation for both handoff and session continuity.

A checkpoint may legitimately do several things at once:

- Update current progress and state summaries
- Persist newly clarified requirements or plan details
- Record decisions, trade-offs, and important insights
- Save or register important artifacts
- Regenerate `70-handoff.md`
- Append to the activity or checkpoint history

This complexity is acceptable as long as the invocation stays lightweight and the resulting structure is deterministic and inspectable.

### Structured Mode

Large or risky tasks can opt into stronger checkpoint types and approvals:

- Spec checkpoint or approval
- Plan checkpoint or approval
- Review checkpoints
- Stronger verification capture

Structured mode should be additive. It should not redefine the entire product.

Where possible, structured mode should feel like adding typed checkpoints to the same packet rather than forcing an entirely different mental model.

## Canonical Task Packet

The main artifact is a portable task packet designed for both human and agent consumption.

The task packet can be more structured and information-dense than the user-facing workflow suggests. Internal richness is desirable if it improves reliability.

Suggested structure:

- `00-overview.md`
  - Task title
  - Current status
  - Active objective
  - Repo or workspace pointers
  - Last updated metadata
- `10-context.md`
  - Original prompt
  - Distilled background
  - Constraints
  - Relevant links or references
- `20-decisions.md`
  - Important insights
  - Trade-off analysis
  - Rejected options
  - Why decisions were made
- `30-spec.md`
  - Current agreed requirements, when needed
- `40-plan.md`
  - Current execution plan, when needed
- `50-progress.md`
  - Current snapshot: done, in-progress, blocked, next
- `55-checkpoints/`
  - Timestamped checkpoint records describing milestone state, decisions, artifacts, and next steps
- `60-verification.md`
  - Commands run
  - Evidence captured
  - Remaining validation gaps
- `70-handoff.md`
  - Shortest reliable resume summary for the next human or agent, synthesized from current packet state and checkpoint history
- `80-summary.md`
  - Final outcome
  - What changed
  - Residual risks
  - Follow-up work
- `artifacts/`
  - Optional raw exports from tools
  - Imported plans or specs
  - Screenshots
  - Transcript snippets

### Packet Design Principles

- Distilled context is more valuable than full transcript replay.
- Raw transcripts are optional support material, not the primary interface.
- Canonical packet files are the source of truth. Raw tool outputs are supporting evidence.
- Checkpoints are the durable milestone history. `70-handoff.md` is the compressed working view.
- Missing artifacts are acceptable. Not every task needs a spec or plan.
- `70-handoff.md` should be treated as a first-class artifact, not an afterthought.
- Rich internal structure is acceptable if it remains behind the scenes and improves continuity.

### Internal Structure Tolerance

The product should tolerate and even encourage a richer task-folder structure when that improves session continuity and cross-agent handoff.

Examples of acceptable internal complexity:

- Typed checkpoint records instead of a single flat log
- Separate summaries for progress, decisions, verification, and handoff
- Imported raw artifacts plus normalized canonical views
- Generated indexes or manifests for reliable resume behavior
- More detailed metadata needed by CLI or skills to classify milestones

This complexity should be paid by the tool, not by the user. Users should not need to memorize the folder model in order to benefit from it.

## Interaction Model

The product should center on capture and resume rather than stage execution.

The CLI is the primary deterministic interface, even if many users invoke it indirectly through plugins, hooks, or agent commands.

Minimal useful commands:

- `task init`
- `task checkpoint`
- `task handoff`
- `task resume`
- `task status`
- `task close`

These commands should be designed as stable primitives. A plugin or hook can make them feel nearly invisible, but the underlying packet mutations should still happen through explicit CLI operations.

The exact command names can vary, but the workflow should be shaped around task context initialization, checkpoint persistence, handoff generation, resumption, and closure.

### Checkpoint Semantics

The checkpoint action is the most important default interaction after task initialization.

It should support both:

- A simple mode where the user says "checkpoint this"
- A richer mode where the agent or a skill classifies the checkpoint, gathers the right context, and persists it via the CLI

The richer mode is desirable when it improves structure. The user should be able to trigger a simple action and let the skill or CLI perform a complex persistence operation behind the scenes.

Typical checkpoint moments include:

- Requirements or spec becoming clear enough to preserve
- A major trade-off or design decision being finalized
- A plan reaching a reviewable state
- A meaningful implementation milestone being completed
- A session ending with useful context worth preserving

Optional structured-mode commands:

- `spec approve`
- `plan approve`
- `review create`
- `review apply`

This is intentionally smaller than a default flow of:

- `run-stage spec`
- `stage-approve spec`
- `run-stage plan`
- `stage-approve plan`
- `run-stage execution`

That full flow may still exist, but only as a strict mode for tasks that benefit from it.

The design goal is not "no commands." The design goal is "few commands for the user, deterministic commands for the system."

## Automation Strategy

The best user experience is low-invocation, not zero-invocation at all costs.

Recommended automation:

- Auto-select, suggest, or create the active task packet when the conversation clearly centers on a task
- Suggest or trigger checkpoint capture at meaningful milestones
- Auto-refresh `70-handoff.md` after major milestones or before session end
- Auto-save imported tool outputs into `artifacts/` or canonical files
- Auto-append verification evidence when practical

The system should use hooks and lightweight agent instructions where possible instead of forcing explicit commands for every phase.

However, that automation should generally orchestrate the CLI rather than bypass it. Direct file mutation by the agent should be the exception, not the default path for important state changes.

An ideal experience is:

- The user initializes a task context once, or the agent notices the task boundary and suggests doing so
- The conversation proceeds normally
- The agent or skill notices likely milestone boundaries
- The user can accept, ignore, or manually trigger a checkpoint
- Handoff and resume views stay current without requiring a memorized command flow
- The underlying task folder may become richly structured without increasing user-facing workflow burden

## Tool Integration

External tools should remain the engines. `dev-workflow` should wrap them lightly.

## Plugin Philosophy

The Claude plugin should be a thin ergonomic layer over the CLI, not a workflow teacher that asks the user to remember a command sequence.

The same philosophy applies to skills: they may impose more structure on capture and classification, but they should reduce cognitive load rather than increase it.

In the default case, the plugin should help with only a few high-value actions:

- Initialize or select task context
- Create a checkpoint
- Generate or refresh handoff and resume context
- Close the task

If stricter stage-oriented commands exist, they should be treated as structured-mode tools for tasks that genuinely benefit from them, not as the normal interaction model for every task.

### Superpowers and Similar Skills

- Direct specs and plans to user-controlled output locations
- Import or normalize outputs into canonical packet files
- Preserve structured review only when the user opts into it
- Use the CLI to register and normalize resulting artifacts whenever possible
- Help detect likely checkpoint moments when that improves continuity

### Taskmaster and Similar Systems

- Redirect tool state into the task packet or a packet-owned subdirectory
- Use the tool's decomposition or execution ordering when it adds value
- Keep the canonical packet as the source of truth for human handoff
- Use CLI-owned import or sync commands instead of relying on implicit file conventions alone

### Generic Agent Workflows

If a tool cannot be controlled directly, `dev-workflow` should capture its outputs after the fact and normalize them into the packet rather than reimplementing the tool.

## What To Keep vs. What To Demote

### Keep

- External task packet storage
- Checkpoint-centric persistence and handoff
- Durable handoff summaries
- Progress synthesis
- Verification evidence capture
- Controlled artifact locations
- Optional approvals for important work
- Deterministic CLI primitives under every important packet mutation
- Rich task-folder structure when it improves reliability and remains mostly behind the scenes

### Demote or Remove

- Mandatory stage workflow for every task
- Product positioning centered on orchestrating other tools
- Large user-facing command surfaces for the normal path
- Plugin flows that require users to remember a prescribed sequence
- Deep workflow ceremony on small tasks
- Overly rich domain modeling before the packet model is proven

## Failure Modes

The design should explicitly handle continuity failures:

- **Stale handoff**
  - Regenerate `70-handoff.md` from canonical packet files
- **Tool output mismatch**
  - Preserve raw output in `artifacts/` and mark normalization status
- **Partial packet**
  - Allow tasks with no spec or no plan
- **Ambiguous state**
  - Record uncertainty in `20-decisions.md` or `70-handoff.md`
- **Execution drift**
  - Require `50-progress.md` to always state current target, blocker, and next action

## Acceptance Criteria

The redesign is successful if:

1. A fresh session with no prior chat history can resume a task from the packet.
2. A different coding agent can understand how the spec was reached.
3. Specs, plans, and related artifacts can be stored outside normal repo workflows or in user-chosen locations.
4. Small tasks feel lighter than the current structured flow.
5. Large tasks can opt into stronger checkpoints without forcing that overhead on every task.
6. External tools can be used without making `dev-workflow` duplicate their core reasoning behavior.
7. Important task packet operations remain available as deterministic CLI commands, whether invoked directly or through automation.
8. Users can preserve meaningful milestones through checkpoints without needing to remember a stage command flow.
9. A different agent can resume from checkpoint history plus synthesized handoff without needing prior chat context.
10. The task folder can hold richer structure and more captured information without forcing equivalent complexity onto the user interaction model.

## Recommended Product Direction

The recommended direction is a hybrid system:

- Lightweight continuity layer by default
- Structured workflow only when useful
- External tool integration instead of tool replacement
- Human-readable packet as the canonical interface

In short:

`dev-workflow` should be the memory and handoff layer around agentic work, not the central brain that tries to own every stage of it.
