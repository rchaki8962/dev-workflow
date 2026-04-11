# Task Awareness

Load this skill at session start or when resuming work on a task managed by dev-workflow.

## Session Start Flow

1. Run `dev-workflow status` to check for active tasks in the current space.
2. If tasks exist, ask the user which task to resume (or if starting fresh).
3. For an active task, run `dev-workflow resume <slug> --format json` and present a brief status:
   - Current milestone and checkpoint count
   - Last summary
   - Open questions and next steps
   - Any user directives from the last checkpoint

## Checkpoint-Worthy Signals

Monitor the conversation for moments worth capturing. A checkpoint is warranted when:

- **A decision was made** -- an approach was chosen, a trade-off was resolved, a technology was selected
- **An artifact was produced or significantly revised** -- a spec, plan, design doc, or config was written or substantially changed
- **A meaningful implementation milestone was reached** -- a feature works end-to-end, a test suite passes, a module is complete
- **A direction change happened** -- a pivot, scope change, or requirement was discovered that alters the plan
- **The user gave significant new direction, constraints, or feedback** -- explicit priorities, requirements, constraints, or corrections that should be preserved for future sessions
- **An open question was resolved or a new blocker surfaced** -- clarity was gained or a problem was identified
- **The user is about to end the session** -- always suggest a checkpoint before session end

## Delta Heuristic

Before suggesting a checkpoint, compare against the last checkpoint:

- What decisions have been made since then?
- What artifacts were created or changed?
- What did the user explicitly direct or constrain?
- What questions were resolved?

Only suggest when **meaningful new information** exists since the last save. Do NOT suggest after:

- Purely exploratory conversation with no decisions or outputs
- Reading files or reviewing code without making changes
- Trivial exchanges or small clarifications

## Suggesting a Checkpoint

When you recognize a checkpoint-worthy moment:

> "We've made some progress since the last checkpoint -- want to save one?"

Or more specific:

> "We just finalized the auth approach and wrote the spec. Good time for a checkpoint?"

**Rules:**
- Be brief, not pushy
- Accept "no" without re-asking
- Don't suggest more than once for the same set of changes
- Don't suggest after trivial exchanges

## What NOT To Do

- **Never checkpoint automatically** -- always ask the user first
- **Never nag** -- if the user declines, don't bring it up again until meaningful new work happens
- **Never suggest right after the last checkpoint** -- wait for substantive new work
- **Never checkpoint exploration-only sessions** -- reading code, asking questions, and browsing files does not warrant a checkpoint unless decisions emerged
