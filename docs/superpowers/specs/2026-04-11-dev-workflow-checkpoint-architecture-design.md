# Tech Spec: dev-workflow Checkpoint Architecture

Status: Draft
Date: 2026-04-11
PRD: [dev-workflow PRD](2026-04-11-dev-workflow-prd.md)

## 1. Overview

This spec describes the implementation design for dev-workflow, a checkpoint-oriented task continuity system. It translates the PRD's requirements into module boundaries, interfaces, data flow, and testing strategy.

The implementation is a clean rewrite. No code from prior iterations is reused.

## 2. Architecture

Three-layer stack:

```
CLI Layer (cli.py)
  Thin Click wrappers. Parse args, call domain, format output.
  │
Domain Layer (task.py, checkpoint.py, resume.py, space.py, views.py, config.py, slug.py)
  Business logic. Validation, checkpoint merging, view generation.
  │
Storage Layer (store.py)
  All SQLite access. Schema, queries, transactions. Only module that imports sqlite3.
```

Plus two standalone agent skill files (`skills/`) that are markdown, not code.

## 3. Project Structure

```
dev-workflow/
├── pyproject.toml
├── skills/
│   ├── task-awareness.md
│   └── task-checkpoint.md
├── src/dev_workflow/
│   ├── __init__.py              # version, public API
│   ├── cli.py                   # Click CLI entry point
│   ├── config.py                # Config file + env var resolution
│   ├── store.py                 # All SQLite access
│   ├── task.py                  # Task lifecycle (init, close)
│   ├── checkpoint.py            # Checkpoint creation, merging, dedup
│   ├── resume.py                # Context bundle synthesis
│   ├── space.py                 # Space CRUD + resolution
│   ├── views.py                 # Markdown view generation
│   ├── models.py                # Dataclasses for all domain objects
│   ├── slug.py                  # Slug generation + collision handling
│   └── errors.py                # Exception hierarchy
└── tests/
    ├── conftest.py              # Shared fixtures (temp DB, Click test runner)
    ├── test_cli.py              # Integration tests through CLI
    ├── test_store.py            # Store unit tests
    ├── test_checkpoint.py       # Checkpoint logic unit tests
    ├── test_views.py            # View generation tests
    ├── test_slug.py             # Slug edge cases
    └── test_config.py           # Config resolution tests
```

## 4. Storage Layer (`store.py`)

### 4.1 Responsibilities

- Schema creation and migration on first connection
- All CRUD operations as focused methods
- Transaction management -- checkpoint persistence is one atomic transaction
- Connection lifecycle (open/close, WAL mode)

### 4.2 Schema

Matches PRD Section 13 with two additions: `checksum` on artifacts, `schema_version` table.

```sql
CREATE TABLE schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE spaces (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    space TEXT NOT NULL REFERENCES spaces(name),
    summary TEXT NOT NULL DEFAULT '',
    last_milestone TEXT NOT NULL DEFAULT '',
    last_checkpoint_at TEXT,
    checkpoint_count INTEGER NOT NULL DEFAULT 0,
    workspaces TEXT NOT NULL DEFAULT '[]',
    task_folder TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    closed_at TEXT,
    UNIQUE(slug, space)
);

CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_number INTEGER NOT NULL,
    milestone TEXT NOT NULL,
    summary TEXT NOT NULL,
    user_directives TEXT NOT NULL DEFAULT '[]',
    insights TEXT NOT NULL DEFAULT '[]',
    next_steps TEXT NOT NULL DEFAULT '[]',
    open_questions TEXT NOT NULL DEFAULT '[]',
    resolved_questions TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL,
    UNIQUE(task_id, checkpoint_number)
);

CREATE TABLE decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    decision_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    alternatives TEXT NOT NULL DEFAULT '[]',
    context TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    UNIQUE(task_id, decision_number)
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    created TEXT NOT NULL,
    UNIQUE(task_id, name, version)
);

CREATE TABLE verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(task_id),
    checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id),
    type TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    command TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL
);
```

### 4.3 Interface

```python
class Store:
    def __init__(self, db_path: Path):
        """Open or create the database. Auto-creates schema if needed."""

    # Spaces
    def create_space(self, name: str, description: str) -> None
    def get_space(self, name: str) -> Space | None
    def list_spaces(self) -> list[Space]
    def remove_space(self, name: str) -> None  # fails if tasks exist
    def ensure_space(self, name: str) -> None  # create if not exists

    # Tasks
    def create_task(self, task: Task) -> None
    def get_task(self, slug: str, space: str) -> Task | None
    def get_task_by_id(self, task_id: str) -> Task | None
    def list_tasks(self, space: str | None = None) -> list[Task]
    def update_task(self, task_id: str, **fields) -> None
    def slug_exists(self, slug: str, space: str) -> bool

    # Checkpoints (atomic multi-table write)
    def save_checkpoint(self, checkpoint: Checkpoint,
                        decisions: list[Decision],
                        artifacts: list[Artifact],
                        verifications: list[Verification]) -> int:
        """Atomic transaction: insert checkpoint, merge decisions,
        upsert artifacts (skip if checksum matches), record verifications,
        update task record. Returns checkpoint number."""

    # Reads
    def get_checkpoints(self, task_id: str) -> list[Checkpoint]
    def get_decisions(self, task_id: str) -> list[Decision]
    def get_artifacts(self, task_id: str) -> list[Artifact]
    def get_artifact_latest(self, task_id: str, name: str) -> Artifact | None
    def get_verifications(self, task_id: str) -> list[Verification]
    def get_next_decision_number(self, task_id: str) -> int
    def get_next_checkpoint_number(self, task_id: str) -> int

    def close(self) -> None
```

### 4.4 Key Behaviors

- `save_checkpoint` wraps everything in a single transaction. If any part fails, nothing is written.
- Artifact upsert computes SHA-256 of content, compares against latest version for that name. Skips insert if checksum matches, auto-increments version if different.
- `remove_space` raises `SpaceNotEmptyError` if the space has tasks. No cascade deletes.
- Schema uses `CREATE TABLE IF NOT EXISTS`. Future migrations keyed off `schema_version`.
- WAL mode enabled on connection for reliability.

## 5. Domain Models (`models.py`)

Plain dataclasses. No ORM. These are the currency passed between layers.

```python
@dataclass
class Space:
    name: str
    description: str
    created: datetime

@dataclass
class Task:
    task_id: str           # UUID
    slug: str
    title: str
    space: str
    summary: str
    last_milestone: str
    last_checkpoint_at: datetime | None
    checkpoint_count: int
    workspaces: list[str]  # paths to code repos this task touches
    task_folder: Path
    created: datetime
    updated: datetime
    closed_at: datetime | None

@dataclass
class Checkpoint:
    id: int | None         # None before persistence
    task_id: str
    checkpoint_number: int
    milestone: str
    summary: str
    user_directives: list[str]
    insights: list[str]
    next_steps: list[str]
    open_questions: list[str]
    resolved_questions: list[str]
    created: datetime

@dataclass
class Decision:
    id: int | None
    task_id: str
    checkpoint_id: int | None
    decision_number: int
    title: str
    rationale: str
    alternatives: list[str]
    context: str
    created: datetime

@dataclass
class Artifact:
    id: int | None
    task_id: str
    checkpoint_id: int | None
    type: str              # "spec", "plan", "design-doc", etc.
    name: str
    version: int
    description: str
    content: str
    checksum: str          # SHA-256 of content
    created: datetime

@dataclass
class Verification:
    id: int | None
    task_id: str
    checkpoint_id: int | None
    type: str              # "test-run", "code-review", "manual-check"
    result: str            # "pass", "fail", "partial"
    detail: str
    command: str
    created: datetime

@dataclass
class CheckpointPayload:
    """Raw JSON payload from agent. Validated before decomposition
    into domain objects by checkpoint.py."""
    milestone: str
    summary: str
    decisions: list[dict] | None = None
    artifacts: list[dict] | None = None
    verifications: list[dict] | None = None
    user_directives: list[str] | None = None
    insights: list[str] | None = None
    next_steps: list[str] | None = None
    open_questions: list[str] | None = None
    resolved_questions: list[str] | None = None
```

**Conventions:**

- `id` fields are `None` before the store assigns them.
- List fields (`insights`, `alternatives`, etc.) are Python lists. The store serializes them as JSON text for SQLite.
- `checksum` is computed by checkpoint domain logic, not by the model.
- All timestamps are UTC `datetime` objects. The store serializes as ISO-8601 strings.

## 6. Domain Logic Modules

### 6.1 `config.py` -- Configuration Resolution

```python
@dataclass
class Config:
    base_dir: Path         # default: ~/.dev-workflow
    default_space: str     # default: "default"

def load_config(config_path: Path | None = None) -> Config:
    """Resolution order for each field:
    - base_dir: DEV_WORKFLOW_BASE_DIR env var > config file > ~/.dev-workflow
    - default_space: config file > "default"
    (DEV_WORKFLOW_SPACE is handled by resolve_space, not here.)
    """

def resolve_space(cli_flag: str | None, config: Config) -> str:
    """Active space resolution (PRD order):
    1. --space CLI flag
    2. DEV_WORKFLOW_SPACE env var
    3. config.default_space
    4. "default"
    """
```

Config file is TOML at `<base_dir>/config.toml`. Optional, not required. Read via `tomllib` (stdlib in Python 3.11+).

v1 schema:

```toml
default_space = "personal"
```

### 6.2 `slug.py` -- Slug Generation

```python
def generate_slug(title: str) -> str:
    """Deterministic: lowercase, strip non-alphanumeric, hyphens for spaces,
    truncate to 60 chars."""

def resolve_slug(title: str, slug_exists_fn: Callable[[str], bool]) -> str:
    """Generate slug, check for collision via callback, append -2, -3, etc."""
```

Collision check is a callback so slug logic doesn't depend on the store directly.

### 6.3 `task.py` -- Task Lifecycle

```python
def init_task(store: Store, base_dir: Path, title: str, space: str,
              prompt: str | None = None,
              workspaces: list[str] | None = None) -> Task:
    """Create a task:
    1. Ensure space exists (auto-create "default" if needed)
    2. Generate slug with collision handling
    3. Generate task_id (UUID)
    4. Compute task_folder path: <base_dir>/<space>/tasks/<date>-<slug>/
    5. Insert task record
    6. If prompt provided, create implicit checkpoint #0
       (milestone="task-initialized", summary=title) and store
       prompt as its artifact (type="prompt", name="original-prompt")
    Returns the created Task.
    """
```

The original prompt is stored as an artifact via an implicit initial checkpoint. This satisfies the `checkpoint_id NOT NULL` constraint on the artifacts table while keeping the prompt versioned/checksummed like everything else.

### 6.4 `checkpoint.py` -- Checkpoint Creation

```python
def create_checkpoint(store: Store, task: Task,
                      payload: CheckpointPayload) -> int:
    """The core operation:
    1. Validate payload (milestone and summary required)
    2. Build Checkpoint from payload fields (including user_directives)
    3. Build Decision list -- assign decision_numbers via store
    4. Build Artifact list -- compute SHA-256 checksums
    5. Build Verification list
    6. Call store.save_checkpoint() (atomic transaction)
    7. Return checkpoint number
    """

def validate_payload(payload: CheckpointPayload) -> None:
    """Strict validation. Raises PayloadError with clear message
    for: missing milestone/summary, empty artifact content,
    unknown verification result values, etc."""
```

### 6.5 `resume.py` -- Context Bundle Synthesis

```python
def resume_task(store: Store, task: Task,
                format: str = "json") -> str:
    """Synthesize context bundle:
    - json: structured dict matching PRD Section 10.5, serialized to JSON
    - md: regenerate task folder via views.py, return path to HANDOFF.md
    """
```

For `--format md`, calls `views.regenerate_task_folder()` then returns the HANDOFF.md path.

### 6.6 `space.py` -- Space Management

```python
def create_space(store: Store, name: str, description: str) -> Space
def list_spaces(store: Store) -> list[Space]
def remove_space(store: Store, name: str) -> None  # fails if tasks exist
def get_space_info(store: Store, name: str) -> dict  # space + task count
```

Thin wrappers over store methods with validation (name format, not-empty checks).

## 7. View Generation (`views.py`)

### 7.1 Generated Folder Structure

```
<task-folder>/
  HANDOFF.md                     # Index. Summaries + links. Agent reads ONLY this.
  context/
    original-prompt.md           # What the user originally asked for
    current-state.md             # Latest checkpoint state
    decisions.md                 # All decisions with rationale
    open-questions.md            # Unresolved questions
  artifacts/
    <type>-<name>-v<N>.md        # Latest version of each artifact
  record/
    development-record.md        # Structured archival document
    checkpoints.md               # Chronological checkpoint log
```

### 7.2 Interface

```python
def regenerate_task_folder(store: Store, task: Task) -> Path:
    """Regenerate the entire task folder from SQLite.
    1. Wipe existing folder (it's a cache)
    2. Create directory structure
    3. Generate each file
    Returns path to task folder.
    """
```

Internal generators (one per file):

```python
def _generate_handoff(task, checkpoints, decisions, artifacts, verifications) -> str
def _generate_original_prompt(prompt_artifact: Artifact | None) -> str
def _generate_current_state(task, latest_checkpoint) -> str
def _generate_decisions(decisions: list[Decision]) -> str
def _generate_open_questions(latest_checkpoint: Checkpoint | None) -> str
def _generate_artifact_file(artifact: Artifact) -> str
def _generate_development_record(task, checkpoints, decisions, verifications) -> str
def _generate_checkpoints_log(checkpoints: list[Checkpoint]) -> str
```

### 7.3 Key Behaviors

- `regenerate_task_folder` fetches all data from the store in one batch, then generates files. Full regeneration every time, no incremental updates.
- **HANDOFF.md** contains one-line summaries with relative links to detail files. No content duplication across files. Includes user directives from the latest checkpoint so a cold-starting agent knows the user's explicit constraints and feedback.
- **Artifact files** render only the latest version. Older versions live in SQLite; `checkpoints.md` records the history.
- If a task has zero checkpoints (just initialized), the folder is minimal: HANDOFF.md with title/status, and `context/original-prompt.md` if a prompt was stored.
- Lazy regeneration: views are only generated on `resume --format md` or explicit `regenerate`. Mutations (checkpoint, init) update SQLite only.

## 8. CLI Layer (`cli.py`)

### 8.1 Entry Point

```python
@click.group()
@click.option('--space', default=None, help='Override active space')
@click.option('--base-dir', default=None, type=click.Path(), help='Override base directory')
@click.pass_context
def cli(ctx, space, base_dir):
    """dev-workflow: checkpoint-oriented task continuity."""
    config = load_config()
    if base_dir:
        config.base_dir = Path(base_dir)
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['space'] = resolve_space(space, config)
    ctx.obj['store'] = Store(config.base_dir / 'store.db')
```

### 8.2 Commands

| Command | Signature | Output |
|---------|-----------|--------|
| `init` | `init <title> [--prompt TEXT] [--workspace PATH...]` | `{"slug", "task_id", "task_folder"}` |
| `checkpoint` | `checkpoint <slug> [--payload FILE]` (or stdin) | `{"checkpoint_number", "message"}` |
| `resume` | `resume <slug> [--format json\|md]` | JSON context bundle or HANDOFF.md path |
| `status` | `status [slug]` | All tasks (no slug) or detailed task status |
| `list` | `list [--all-spaces]` | JSON array of tasks with space labels |
| `regenerate` | `regenerate <slug>` | `{"task_folder", "message"}` |

### 8.3 Space Subcommands

| Command | Signature | Output |
|---------|-----------|--------|
| `space create` | `space create <name> [--description TEXT]` | JSON confirmation |
| `space list` | `space list` | JSON array |
| `space remove` | `space remove <name>` | JSON confirmation |
| `space info` | `space info <name>` | Space details + task count |

### 8.4 Key Decisions

- **All output is JSON** to stdout. Errors go to stderr as plain text.
- **`checkpoint` reads payload** from stdin by default, `--payload` for file path. Click detects whether stdin has data.
- **Exit codes:** 0 = success, 1 = user error (bad input, not found), 2 = internal error.
- Store teardown via `@cli.result_callback()`.

## 9. Error Handling (`errors.py`)

```python
class DevWorkflowError(Exception):
    """Base. CLI catches this: message to stderr, exit 1."""

class TaskNotFoundError(DevWorkflowError)
class SpaceNotFoundError(DevWorkflowError)
class SpaceNotEmptyError(DevWorkflowError)
class PayloadError(DevWorkflowError)        # validation failures
class SlugCollisionError(DevWorkflowError)  # exhausted collision attempts
class StoreError(DevWorkflowError)          # SQLite errors wrapped
```

CLI error handling pattern:

```python
try:
    # domain logic
except DevWorkflowError as e:
    click.echo(str(e), err=True)
    raise SystemExit(1)
except Exception as e:
    click.echo(f"Internal error: {e}", err=True)
    raise SystemExit(2)
```

Every `DevWorkflowError` carries a human-readable message. No stack traces for user errors (exit 1). Stack traces only for unexpected failures (exit 2).

## 10. Agent Skills

Two standalone markdown files in `skills/`. Detailed and prescriptive. These are the intelligence layer; the CLI is the correctness layer.

### 10.1 `skills/task-awareness.md`

Loaded at session start or resume. Primes the agent to recognize checkpoint-worthy moments.

**Contents:**

1. **Session start flow** -- run `dev-workflow status` to check for active tasks, then `dev-workflow resume <slug> --format json` if one exists. Present brief status to user.
2. **Checkpoint-worthy signals:**
   - A decision was made (approach chosen, trade-off resolved)
   - An artifact was produced or significantly revised
   - A meaningful implementation milestone was reached
   - A direction change happened (pivot, scope change)
   - The user gave significant new direction, constraints, or feedback
   - An open question was resolved or a new blocker surfaced
   - The user is about to end the session
3. **Delta heuristic** -- compare against last checkpoint's summary, decisions, and artifacts. Only suggest when meaningful new information exists. Don't suggest if conversation has only been exploration with no decisions or outputs.
4. **Suggestion phrasing** -- brief, not pushy. Accept "no" without re-asking.
5. **What NOT to do** -- don't checkpoint automatically, don't nag, don't suggest after trivial exchanges.

### 10.2 `skills/task-checkpoint.md`

Invoked when creating a checkpoint. Drafts the structured payload from conversation context.

**Contents:**

1. **Payload schema** -- full JSON schema with all fields, types, required vs optional. Includes examples for each field.
2. **Extraction instructions** (step by step):
   - Summarize what happened since the last checkpoint
   - Extract key user directives, constraints, and feedback from the conversation
   - Extract decisions: title, rationale, alternatives considered, context
   - Identify artifacts: capture full content of specs/plans/docs
   - Note verifications: test runs, reviews, manual checks with results
   - Collect insights: non-obvious observations worth preserving
   - Determine next steps and open/resolved questions
3. **Draft review flow** -- present draft to user in readable form (not raw JSON). Proceed only on explicit approval.
4. **CLI invocation** -- exact command: `dev-workflow checkpoint <slug> --payload <file>` or pipe via stdin. Instructions for writing JSON to temp file for large payloads.
5. **Minimal checkpoint example** -- just milestone + summary for quick session-end saves.
6. **Rich checkpoint example** -- full payload with decisions, artifacts, verifications.
7. **Error handling** -- if CLI returns error, show message and help fix payload.

### 10.3 Key Skill Design Decisions

- Skills reference CLI commands by exact invocation, not abstractly.
- Skills include full examples so the agent doesn't infer payload structure.
- The checkpoint skill explicitly instructs capturing artifact **content**, not just names.
- Neither skill auto-executes anything. Both gate on user approval.

## 11. Testing Strategy

### 11.1 Framework

pytest, using Click's `CliRunner` for integration tests.

### 11.2 Shared Fixtures (`conftest.py`)

```python
@pytest.fixture
def tmp_base_dir(tmp_path):
    """Isolated base directory. No test touches real ~/.dev-workflow."""
    return tmp_path / "dev-workflow"

@pytest.fixture
def store(tmp_base_dir):
    """Fresh Store with auto-created schema."""
    db_path = tmp_base_dir / "store.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    s = Store(db_path)
    yield s
    s.close()

@pytest.fixture
def cli_runner(tmp_base_dir):
    """Click CliRunner with --base-dir pointed at temp directory."""
    runner = CliRunner()
    def invoke(*args):
        return runner.invoke(cli, ['--base-dir', str(tmp_base_dir)] + list(args))
    return invoke
```

### 11.3 Test Distribution

| File | What it tests | Style |
|------|---------------|-------|
| `test_cli.py` | Full command flows, space commands, error cases, cross-space listing | Integration |
| `test_store.py` | Schema creation, CRUD, atomic checkpoint save, constraints, artifact checksum dedup | Unit |
| `test_checkpoint.py` | Payload validation, decision numbering, checksum logic, version auto-increment | Unit |
| `test_views.py` | Generated markdown structure, progressive disclosure, empty task folder | Unit |
| `test_slug.py` | Unicode, long titles, collision suffixes, special characters | Unit |
| `test_config.py` | Resolution order (env > config > defaults), missing config, malformed TOML | Unit |

### 11.4 Key Integration Test Scenarios (`test_cli.py`)

1. **Full lifecycle** -- init, checkpoint, resume (JSON and markdown), status, list
2. **Multiple checkpoints** -- checkpoint count increments, decisions auto-number, artifact versions increment
3. **Artifact dedup** -- same content twice, verify only one version stored
4. **Multi-space** -- two spaces, tasks in each, `list --all-spaces` shows both
5. **Error paths** -- nonexistent slug, remove space with tasks, malformed JSON, missing fields
6. **Regenerate** -- checkpoint, delete task folder, regenerate, verify folder rebuilt

### 11.5 What's Not Tested

- Skills (markdown, not code)
- Exact markdown wording (test structure and presence, not formatting)

## 12. Packaging

```toml
[project]
name = "dev-workflow"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
]

[project.scripts]
dev-workflow = "dev_workflow.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
]
```

**Key decisions:**

- **Single runtime dependency: Click.** SQLite is stdlib. TOML parsing via `tomllib` (stdlib 3.11+).
- **Python 3.11+** required for `tomllib` and `datetime.fromisoformat` improvements.
- **Hatchling** build backend.
- Entry point via `[project.scripts]` -- `dev-workflow` available after `pip install -e .`.
