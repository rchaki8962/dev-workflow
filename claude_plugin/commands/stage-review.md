# /stage-review

Set up a review for a completed stage.

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

2. Run the review setup:

   ```
   dev-workflow review setup <stage> --task <slug> --format json
   ```

   Parse the returned JSON. It contains:
   - `files_to_review` -- list of file paths to review
   - `review_file` -- path to the review template file

3. Respond:

   > Review template created at `<review_file>`.
   >
   > To produce the review:
   > - Open a new Claude Code session
   > - Read the listed files: `<files_to_review>`
   > - Write your review into `<review_file>`
   >
   > Or skip the formal review and run `/stage-approve <stage>`.
