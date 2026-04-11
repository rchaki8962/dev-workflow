# CLAUDE.md

dev-workflow: Python CLI for checkpoint-oriented task continuity. Agents checkpoint at meaningful moments; SQLite is the source of truth; task folders are a generated cache.

See [README.md](README.md) for usage guide.

## Quick reference

```bash
pip install -e .
pytest                    # 94 tests
dev-workflow --help
```

## Architecture

Three layers: CLI (Click) -> Domain Logic -> Storage (SQLite). Only `store.py` imports `sqlite3`.

## Module map

- `models.py` -- dataclasses (Task, Space, Checkpoint, Decision, Artifact, Verification, CheckpointPayload)
- `errors.py` -- `DevWorkflowError` hierarchy (TaskNotFoundError, SpaceNotFoundError, SpaceNotEmptyError, PayloadError, SlugCollisionError, StoreError)
- `config.py` -- config loading + space resolution (env var > config file > "default")
- `slug.py` -- slug generation with collision handling
- `store.py` -- SQLite storage layer (WAL mode, foreign keys, atomic checkpoint save, artifact dedup)
- `space.py` -- space CRUD with name validation
- `task.py` -- `init_task` (with optional prompt -> checkpoint #0), `get_task`
- `checkpoint.py` -- `validate_payload`, `create_checkpoint` (payload decomposition + persistence)
- `views.py` -- `regenerate_task_folder` (wipe + rebuild markdown from SQLite)
- `resume.py` -- `resume_task` (JSON context bundle or regenerated folder)
- `cli.py` -- Click CLI: space commands (create, list, remove, info) + core commands (init, checkpoint, resume, status, list, regenerate)

## Testing

- Python 3.11+, only dependency: `click>=8.0`
- All tests use `tmp_path` -- never touch real `~/.dev-workflow/`
- Fixtures in `conftest.py`: `tmp_base_dir`, `store` (fresh SQLite per test)
- `test_cli.py` uses Click's `CliRunner` with `--base-dir` pointed at temp dir

## Agent skills

- `skills/task-awareness.md` -- session start, checkpoint-worthy signal detection
- `skills/task-checkpoint.md` -- checkpoint payload schema, extraction instructions, draft review flow
