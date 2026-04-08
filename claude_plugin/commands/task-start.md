# /task-start

Create a new dev-workflow task and capture the original prompt.

## Arguments

- `title` (required): A short title for the task.

## Steps

1. Run the CLI to create the task:

   ```
   dev-workflow task start "<title>" --workspace $(pwd) --format json
   ```

2. Parse the returned JSON. Extract `task_folder` and `slug`.

   The task is created in the active space (set via `--space` flag, `DEV_WORKFLOW_SPACE` env var, or config default).

3. **Remember the slug as the session default** so subsequent commands can use it without an explicit argument.

4. Ask the user:

   > What's the task? Describe what you want to build.

5. Write the user's response verbatim into `<task_folder>/01-original-prompt.md`.

6. Respond:

   > Task `<slug>` created. Run `/run-stage spec` to start the spec stage.
