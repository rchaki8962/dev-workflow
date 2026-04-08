# /task-status

Show detailed information about a task.

## Arguments

- `slug` (optional): The task slug. If omitted, uses the session default or prompts the user to pick one.

## Slug Resolution

Resolve the slug in this order:

1. **Explicit argument**: slug passed directly.
2. **Session context**: if `/task-start` or `/task-switch` was run earlier in this conversation, use the remembered slug.
3. **Prompt**: run `dev-workflow task list --format table` and ask the user to pick a task.

## Steps

1. Resolve the slug using the process above.

2. Run:

   ```
   dev-workflow task info <slug>
   ```

3. Display the output to the user.
