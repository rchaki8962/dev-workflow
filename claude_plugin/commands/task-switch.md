# /task-switch

Switch the session to an existing task, loading its context.

## Arguments

- `slug` (required): The task slug to switch to.

## Steps

1. Run:

   ```
   dev-workflow task switch <slug>
   ```

   This prints a progress summary, spec summary, and plan summary for the task.

2. **Remember the slug as the session default** so subsequent commands can use it without an explicit argument.

3. Ingest the output as session context so you understand the task's current state.

4. Respond:

   > Switched to task `<slug>`. Current stage: `<stage>`.

   Where `<stage>` is extracted from the command output.
