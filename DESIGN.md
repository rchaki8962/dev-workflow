# Design Document

Low-level design for the dev-workflow CLI and Claude Code plugin.

## Architecture

Three layers with strict separation of concerns:

```
Claude Code Plugin Commands (orchestrators)
    |
    |---> Python CLI (deterministic mechanics)
    |       TaskManager, StageManager, FileTaskStore
    |
    |---> Superpowers Skills (creative work)
            brainstorming, writing-plans, subagent-driven-development
```

- **Python CLI** is fully testable and usable standalone, no Claude Code dependency.
- **Plugin commands** are thin orchestrators -- they call the CLI and invoke skills. They never know about file layouts or persistence.
- **Python never knows about Superpowers.** Skills are invoked by plugin commands, not by Python code.

## Domain Model

All domain types are plain dataclasses in `models.py`. No ORMs, no base classes, no magic.

### Enums

```python
class Stage(str, Enum):       # spec -> plan -> execution -> complete
class SubtaskStatus(str, Enum): # not-started, in-progress, done, blocked
class ReviewVerdict(str, Enum): # approve, revise, blocked
```

`str, Enum` so they serialize naturally and compare with plain strings.

### Core Entities

```python
@dataclass
class Task:
    task_id: str            # "2026-04-08-csv-export" -- date + slugified title
    slug: str               # "csv-export" -- short human identifier
    title: str
    summary: str            # populated after spec approval
    stage: Stage
    workspaces: list[Path]  # informational, captured at creation
    task_folder: Path
    created: datetime
    updated: datetime
    space: str = ""         # space name, set at creation, immutable

@dataclass
class Space:
    name: str               # lowercase alphanumeric + hyphens, max 40 chars
    description: str
    created: datetime
```

Other entities: `TaskProgress`, `SubtaskEntry`, `Subtask`, `Spec`, `Plan`, `PlanTask`, `Review`, `ActivityEntry`, `VerificationStep`. All are plain dataclasses with no behavior -- logic lives in managers.

## Persistence Layer

### TaskStore Protocol

```python
class TaskStore(Protocol):
    def save_task(self, task: Task) -> None: ...
    def load_task(self, slug: str) -> Task: ...
    def list_tasks(self) -> list[Task]: ...
    def search_tasks(self, query: str) -> list[Task]: ...
    def delete_task(self, slug: str) -> None: ...
    def save_progress(self, task_id: str, progress: TaskProgress) -> None: ...
    def load_progress(self, task_id: str) -> TaskProgress: ...
    def save_subtask(self, task_id: str, subtask: Subtask) -> None: ...
    def load_subtask(self, task_id: str, subtask_id: int) -> Subtask: ...
    def list_subtasks(self, task_id: str) -> list[SubtaskEntry]: ...
    def save_spec(self, task_id: str, spec: Spec) -> None: ...
    def save_plan(self, task_id: str, plan: Plan) -> None: ...
    def save_review(self, task_id: str, review: Review) -> None: ...
    def append_activity(self, task_id: str, entry: ActivityEntry) -> None: ...
```

The protocol enables a future DB backend without changing the domain model. V1 uses `FileTaskStore` (markdown files + JSON state).

### FileTaskStore

```python
class FileTaskStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir               # a space directory, not the global base
        self.state = StateManager(base_dir / "state")
        self.tasks_dir = base_dir / "tasks"
```

The store does not know about spaces. It takes a directory and works within it. The CLI passes `config.space_dir` to give it the right scope.

### State Registry (state.py)

One JSON file per task in `<space>/state/<slug>.json`:

```json
{
  "task_id": "2026-04-08-csv-export",
  "slug": "csv-export",
  "title": "User data CSV export",
  "summary": "",
  "stage": "spec",
  "progress": "0/0 subtasks",
  "workspaces": ["~/workspace/my-api"],
  "task_folder": "~/.dev-workflow/harness/tasks/2026-04-08-csv-export/",
  "space": "harness",
  "created": "2026-04-08T11:05:00Z",
  "updated": "2026-04-08T11:05:00Z"
}
```

- `StateManager` handles save/load/list_all/search/update/exists/all_slugs/delete.
- `_task_to_dict` / `_dict_to_task` handle serialization. Extra JSON fields (like `progress`) survive round-trips without being on the dataclass.
- `space` field defaults to `""` for backward compatibility with pre-space JSON files.

### Spaces Registry

`spaces.json` at the global `base_dir` root (outside any space directory). A JSON array of space metadata:

```json
[
  {"name": "harness", "description": "Default workspace", "created": "2026-04-08T12:00:00Z"},
  {"name": "personal", "description": "Personal projects", "created": "2026-04-08T12:05:00Z"}
]
```

## Space Isolation

### Config Wiring

```python
@dataclass
class Config:
    base_dir: Path
    strip_words: list[str]
    default_space: str = "harness"

    # _active_space: str -- set post-init, NOT a dataclass field (avoids serialization)

    @property
    def space_dir(self) -> Path:
        return self.base_dir / self._active_space

    @property
    def state_dir(self) -> Path:
        return self.space_dir / "state"       # was: base_dir / "state"

    @property
    def tasks_dir(self) -> Path:
        return self.space_dir / "tasks"       # was: base_dir / "tasks"
```

This is the key isolation mechanism. By routing `state_dir` and `tasks_dir` through `space_dir`, all downstream code (`FileTaskStore`, `StageManager`, `TaskManager`, `progress.py`, `plan_parser.py`, `templates.py`, `slug.py`) gets space isolation for free without any changes.

### Active Space Resolution

Resolution order (first match wins):
1. `--space` CLI flag
2. `DEV_WORKFLOW_SPACE` env var
3. `default_space` from config file
4. Hardcoded default: `"harness"`

Resolved once at CLI startup. Every command in that invocation operates within the same space.

### SpaceManager

```python
class SpaceManager:
    def __init__(self, base_dir: Path): ...
    def create(self, name: str, description: str = "") -> Space
    def list_all(self) -> list[Space]
    def get(self, name: str) -> Space
    def remove(self, name: str, force: bool = False) -> None
    def exists(self, name: str) -> bool
    def ensure(self, name: str) -> Space     # auto-create if missing
```

- Name validation: `^[a-z0-9]+(-[a-z0-9]+)*$`, max 40 chars.
- `create` adds to registry and creates `<space>/state/` + `<space>/tasks/` directories.
- `remove` refuses if space has tasks unless `--force`.
- `ensure` is called in the CLI `main()` on every invocation to auto-create the default space.

### Cross-Space Listing

`task list --all-spaces` is the only cross-space operation. Implemented in the CLI layer (not in TaskManager or StateManager): iterate `SpaceManager.list_all()`, create a temporary `FileTaskStore` per space, merge results.

## Stage Workflow

### Stage Lifecycle

```
spec -> plan -> execution -> complete
```

Each stage has: **setup** -> (creative work) -> **teardown** -> **review** -> **approve**

- `setup`: validates prerequisites, returns paths as JSON
- `teardown`: updates progress and state. **Does NOT advance stage.**
- `review setup`: creates review template
- `review approve`: copies draft to `*-approved.md`, **advances stage**

### Prerequisites

| Stage | Requires |
|-------|----------|
| spec | `01-original-prompt.md` exists and is non-empty |
| plan | `10-spec/spec-approved.md` exists |
| execution | `20-plan/plan-approved.md` exists |

### Stage Setup Returns

```
spec:      { original_prompt_path, output_path, version }
plan:      { approved_spec_path, output_path, version }
execution: { task_folder, subtask_files: [...] }
```

### Version Detection

Stateless filesystem scan. `spec-v1.md`, `spec-v2.md`, ... -- next version = max existing + 1.

## Slug Generation

- Strip common words: `add`, `fix`, `update`, `implement`, `create`, `the`, `a`, `an`, `for`, `with`, `to`, `in` (configurable).
- Slugify remainder, max 40 chars, truncated at word boundary.
- On collision: append `-2`, `-3`, etc.
- User override: `--slug my-custom-slug`.
- Scoped per-space -- two spaces can have the same slug.

## Plugin Command Orchestration

### /run-stage Flow

```
/run-stage <stage>
  1. Resolve slug (explicit arg > session context > prompt user)
  2. dev-workflow stage setup <stage> --task <slug> --format json
  3. Invoke Superpowers skill:
     - spec:      brainstorming (output to task folder, no chaining)
     - plan:      writing-plans (output to task folder, no execution offer)
     - execution: subagent-driven-development (subtask files)
  4. dev-workflow stage teardown <stage> --task <slug>
```

### Superpowers Wiring Rules

1. **Output path override**: all skill outputs go to the task folder, never `docs/superpowers/`.
2. **Chaining suppression**: brainstorming does NOT chain to writing-plans. writing-plans does NOT offer execution choice.
3. **Review gate preservation**: skills' internal review loops are complementary. Formal review gates are independent.
4. **Verification enforcement**: `superpowers:verification-before-completion` enforced during execution.

### Slug Resolution

All plugin commands resolve the task slug in this order:
1. Explicit argument
2. Session context (remembered from `/task-start` or `/task-switch`)
3. Prompt: run `task list --format table`, ask user to pick

There are no real session variables. The slug is remembered by Claude in conversation context.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Unknown slug | `TaskNotFoundError` with helpful message |
| Unknown space | `SpaceNotFoundError` with helpful message |
| Stage prerequisite not met | `PrerequisiteError` naming the missing artifact |
| Invalid space name | `ValueError` with validation rules |
| Duplicate task_id | Append `-2`, `-3`, etc. |
| Duplicate slug | Append `-2`, `-3`, etc. |
| `review approve` with no draft | Error: run `/run-stage` first |
| `space remove` with tasks | Refuses unless `--force` |

## Crash Recovery

1. New session runs `/task-switch <slug>`.
2. Progress file shows subtask statuses.
3. `/run-stage execution` resumes from first non-completed subtask.
4. No prior chat history required -- durable files are the source of truth.

## What's Deferred

- Hooks (SessionStart, PostToolUse)
- Task archive/cancel commands
- Engine configuration file
- DB backend (enabled by TaskStore protocol)
- Plan amendment protocol
- Dashboard UI
