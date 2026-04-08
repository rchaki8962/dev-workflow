# /stage-approve

Approve a stage and advance the task to the next stage.

## Arguments

- `stage` (required): One of `spec`, `plan`, or `execution`.
- `slug` (optional): The task slug. If omitted, uses the session default or prompts.

## Slug Resolution

Resolve the slug in this order:

1. **Explicit argument**: slug passed directly.
2. **Session context**: if `/task-start` or `/task-switch` was run earlier in this conversation, use the remembered slug.
3. **Prompt**: run `dev-workflow task list --format table` and ask the user to pick a task.

## Steps

1. Resolve the slug.

2. Run:

   ```
   dev-workflow review approve <stage> --task <slug>
   ```

3. Respond based on which stage was approved:

   - If `spec` was approved:
     > Stage `spec` approved. Next: `/run-stage plan`.

   - If `plan` was approved:
     > Stage `plan` approved. Next: `/run-stage execution`.

   - If `execution` was approved:
     > Stage `execution` approved. Task is done.
