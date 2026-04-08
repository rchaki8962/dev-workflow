# /task-list

List all tasks, optionally filtered by stage.

## Arguments

- `stage` (optional): Filter by stage name (`spec`, `plan`, `execution`, `done`).

## Steps

1. Run:

   ```
   dev-workflow task list
   ```

   If a stage filter was provided, add `--stage <stage>`:

   ```
   dev-workflow task list --stage <stage>
   ```

   To list tasks across all spaces, add `--all-spaces`:

   ```
   dev-workflow task list --all-spaces
   ```

2. Display the output to the user.
