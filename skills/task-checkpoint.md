# Task Checkpoint

Invoke this skill when creating a checkpoint for a dev-workflow task. This skill drafts the structured payload from the conversation context, presents it for review, and persists it via the CLI.

## Checkpoint Payload Schema

The CLI accepts a JSON payload via stdin or `--payload <file>`. Required fields are marked with *.

```json
{
  "milestone": "*string -- short label for this checkpoint (e.g., 'spec-finalized', 'auth-implemented', 'session-end')",
  "summary": "*string -- 1-3 sentence summary of what happened since the last checkpoint",
  "user_directives": ["string -- key user directives, constraints, and feedback from the conversation"],
  "decisions": [
    {
      "title": "*string -- what was decided",
      "rationale": "string -- why this choice was made",
      "alternatives": ["string -- other options that were considered"],
      "context": "string -- background that influenced the decision"
    }
  ],
  "artifacts": [
    {
      "type": "*string -- category: 'spec', 'plan', 'design-doc', 'config', 'notes'",
      "name": "*string -- unique name for this artifact (e.g., 'auth-middleware-spec')",
      "content": "*string -- the FULL content of the artifact (not a summary)",
      "description": "string -- brief description of what this artifact is"
    }
  ],
  "verifications": [
    {
      "type": "*string -- 'test-run', 'code-review', 'manual-check'",
      "result": "*string -- 'pass', 'fail', 'partial'",
      "detail": "string -- e.g., '42/42 tests passing'",
      "command": "string -- the command that was run, e.g., 'pytest tests/ -v'"
    }
  ],
  "insights": ["string -- non-obvious observations worth preserving"],
  "next_steps": ["string -- what should happen next"],
  "open_questions": ["string -- unresolved questions"],
  "resolved_questions": ["string -- questions answered in this checkpoint, format: 'question -> answer'"]
}
```

## Extraction Instructions

Analyze the conversation since the last checkpoint (or since task start) and extract:

1. **Summary** -- What happened? What was accomplished? Write 1-3 sentences.

2. **User directives** -- What did the user explicitly direct, constrain, or give feedback on? Look for:
   - Explicit priorities ("prioritize X", "X is more important than Y")
   - Constraints ("must work with X", "can't use Y", "needs to support Z")
   - Feedback on approach ("I prefer A over B", "don't do X")
   - Requirements stated during conversation ("it should also handle X")
   Capture these as direct, actionable statements.

3. **Decisions** -- What choices were made? For each:
   - What was the decision?
   - Why was it chosen? (rationale)
   - What alternatives were considered?
   - What context influenced it?

4. **Artifacts** -- Were any documents produced or significantly revised? Specs, plans, design docs, configs? If so, capture the **full content** -- not a summary. This is critical for handoff quality.

5. **Verifications** -- Were tests run? Code reviewed? Manual checks performed? Capture the type, result, detail, and command.

6. **Insights** -- Any non-obvious observations? Things that surprised you, unexpected coupling, performance characteristics, etc.

7. **Next steps** -- What should happen next? Be specific enough that a fresh agent can act on these.

8. **Questions** -- What questions were resolved? What new questions emerged?

## Draft Review Flow

1. Draft the payload by analyzing the conversation
2. Present it to the user in readable form (NOT raw JSON):

   > **Checkpoint Draft: `spec-finalized`**
   >
   > **Summary:** Finalized the auth middleware spec after evaluating three approaches...
   >
   > **User Directives:**
   > - Prioritize horizontal scaling
   > - Must work with existing Postgres infrastructure
   >
   > **Decisions:**
   > 1. JWT over session tokens -- Stateless, better for horizontal scaling
   >
   > **Artifacts:**
   > - spec: auth-middleware-spec (full content captured)
   >
   > **Next Steps:**
   > - Implement the middleware
   >
   > Does this look right? Any changes before I save it?

3. Wait for explicit user approval before saving
4. On approval, save and invoke the CLI

## CLI Invocation

For small payloads, pipe via stdin:

```bash
echo '<json>' | dev-workflow checkpoint <slug>
```

For larger payloads, write to a temp file:

```bash
# Write payload to temp file
cat > /tmp/checkpoint-payload.json << 'EOF'
{
  "milestone": "spec-finalized",
  "summary": "..."
}
EOF

# Save checkpoint
dev-workflow checkpoint <slug> --payload /tmp/checkpoint-payload.json
```

## Minimal Checkpoint Example

For quick session-end saves when not much happened:

```json
{
  "milestone": "session-end",
  "summary": "Explored three auth approaches, leaning toward JWT. No decisions finalized yet."
}
```

## Rich Checkpoint Example

After a productive session with decisions, artifacts, and verifications:

```json
{
  "milestone": "spec-finalized",
  "summary": "Finalized auth spec after evaluating three approaches. JWT chosen for horizontal scaling. Spec written and tests passing.",
  "user_directives": [
    "Prioritize horizontal scaling over simplicity",
    "Must work with existing Postgres infrastructure"
  ],
  "decisions": [
    {
      "title": "JWT over session tokens",
      "rationale": "Stateless, better for horizontal scaling. User explicitly prioritized scaling.",
      "alternatives": ["session tokens", "OAuth2 delegation"],
      "context": "Existing infra is Postgres-backed, team has JWT experience"
    }
  ],
  "artifacts": [
    {
      "type": "spec",
      "name": "auth-middleware-spec",
      "description": "JWT-based auth middleware specification",
      "content": "# Auth Middleware Spec\n\n## Overview\n\nJWT-based authentication middleware for the API gateway...\n\n## Endpoints\n\n..."
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
    "Existing middleware is more coupled to the session store than expected -- migration will need a compatibility shim for 2 weeks"
  ],
  "next_steps": [
    "Implement JWT middleware (see spec)",
    "Set up token rotation"
  ],
  "open_questions": [
    "Should we support refresh tokens in v1?"
  ],
  "resolved_questions": [
    "Which auth approach? -> JWT (stateless, scales horizontally)"
  ]
}
```

## Error Handling

If the CLI returns an error:
1. Show the error message to the user
2. Diagnose the issue (usually a payload validation error)
3. Fix the payload and retry
4. Common issues:
   - Missing `milestone` or `summary`
   - Empty artifact `content` (must be non-empty)
   - Missing artifact `name` or `type`
   - Task slug doesn't exist (check with `dev-workflow status`)
