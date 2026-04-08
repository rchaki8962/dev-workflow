# /run-stage

Run a workflow stage (spec, plan, or execution) for a task.

## Arguments

- `stage` (required): One of `spec`, `plan`, or `execution`.
- `slug` (optional): The task slug. If omitted, uses the session default or prompts.

## Slug Resolution

Resolve the slug in this order:

1. **Explicit argument**: slug passed directly.
2. **Session context**: if `/task-start` or `/task-switch` was run earlier in this conversation, use the remembered slug.
3. **Prompt**: run `dev-workflow task list --format table` and ask the user to pick a task.

---

## Stage: spec

1. Resolve the slug.

2. Run stage setup:

   ```
   dev-workflow stage setup spec --task <slug> --format json
   ```

   Parse the returned JSON. It contains:
   - `original_prompt_path` -- path to the original prompt file
   - `output_path` -- where to write the spec
   - `version` -- the draft version number

3. Read the contents of `original_prompt_path`.

4. Invoke the `superpowers:brainstorming` skill with the original prompt as input.

   **Output path override**: Write the spec output to `output_path` (the path returned by stage setup), NOT to `docs/superpowers/specs/` or any other default location.

   **Chaining suppression**: Do NOT chain to `writing-plans` after brainstorming completes. Control must return here.

5. Run stage teardown:

   ```
   dev-workflow stage teardown spec --task <slug>
   ```

6. Respond:

   > Spec draft v`<version>` written. Run `/stage-review spec` or `/stage-approve spec`.

---

## Stage: plan

1. Resolve the slug.

2. Run stage setup:

   ```
   dev-workflow stage setup plan --task <slug> --format json
   ```

   Parse the returned JSON. It contains:
   - `approved_spec_path` -- path to the approved spec
   - `output_path` -- where to write the plan
   - `version` -- the draft version number

3. Read the contents of `approved_spec_path`.

4. Invoke the `superpowers:writing-plans` skill with the approved spec as input.

   **Output path override**: Write the plan output to `output_path` (the path returned by stage setup), NOT to `docs/superpowers/plans/` or any other default location.

   **Chaining suppression**: Do NOT offer the execution choice after writing the plan. Control must return here.

5. Run stage teardown:

   ```
   dev-workflow stage teardown plan --task <slug>
   ```

6. Respond:

   > Plan draft v`<version>` written. Run `/stage-review plan` or `/stage-approve plan`.

---

## Stage: execution

1. Resolve the slug.

2. Run stage setup:

   ```
   dev-workflow stage setup execution --task <slug> --format json
   ```

   Parse the returned JSON. It contains:
   - `task_folder` -- path to the task folder
   - `subtask_files` -- list of subtask file paths

3. Invoke the `superpowers:subagent-driven-development` skill with:
   - The task folder path
   - The list of subtask file paths
   - Subagent instructions: update each subtask file on completion

4. **Verification enforcement**: Invoke `superpowers:verification-before-completion` to verify all work before claiming completion.

5. Run stage teardown:

   ```
   dev-workflow stage teardown execution --task <slug>
   ```

6. Respond:

   > Execution complete. Run `/stage-review execution`.

---

## Superpowers Wiring Rules

These rules apply to ALL stages:

1. **Output path override**: All skill outputs go to the task folder paths returned by `stage setup`, never to `docs/superpowers/`.
2. **Chaining suppression**: `brainstorming` does NOT chain to `writing-plans`. `writing-plans` does NOT offer execution choice. Control always returns to this command.
3. **Review gate preservation**: The skills' internal review loops are complementary quality passes. The formal review gates (`/stage-review`, `/stage-approve`) are independent approval gates. Both apply.
4. **Verification enforcement**: `superpowers:verification-before-completion` is enforced during execution.
