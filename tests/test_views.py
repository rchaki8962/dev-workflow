# tests/test_views.py
"""Tests for markdown view generation."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dev_workflow.models import Artifact, Checkpoint, Decision, Task, Verification
from dev_workflow.task import init_task
from dev_workflow.checkpoint import create_checkpoint
from dev_workflow.models import CheckpointPayload
from dev_workflow.views import regenerate_task_folder


class TestRegenerateTaskFolder:
    def _init_task(self, store, tmp_base_dir, prompt=None):
        task = init_task(store, tmp_base_dir, "Auth Rewrite", "default", prompt=prompt)
        return task

    def test_creates_folder_structure(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir)
        folder = regenerate_task_folder(store, task)
        assert (folder / "HANDOFF.md").exists()
        assert (folder / "context").is_dir()
        assert (folder / "record").is_dir()

    def test_handoff_contains_title(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir)
        regenerate_task_folder(store, task)
        handoff = (task.task_folder / "HANDOFF.md").read_text()
        assert "Auth Rewrite" in handoff

    def test_with_prompt_creates_original_prompt(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir, prompt="Build an auth system")
        regenerate_task_folder(store, task)
        prompt_file = task.task_folder / "context" / "original-prompt.md"
        assert prompt_file.exists()
        assert "Build an auth system" in prompt_file.read_text()

    def test_with_checkpoint_creates_all_files(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir, prompt="Build auth")
        payload = CheckpointPayload(
            milestone="spec-done",
            summary="Finalized spec",
            decisions=[{"title": "Use JWT", "rationale": "Stateless"}],
            artifacts=[{
                "type": "spec",
                "name": "auth-spec",
                "content": "# Auth Spec\nJWT-based auth",
            }],
            verifications=[{
                "type": "test-run",
                "result": "pass",
                "detail": "10/10 tests",
                "command": "pytest -v",
            }],
            user_directives=["Must scale horizontally"],
            insights=["Legacy code is tightly coupled"],
            next_steps=["Implement middleware"],
            open_questions=["Support refresh tokens?"],
        )
        # Refresh task after init checkpoint
        task = store.get_task(task.slug, task.space)
        create_checkpoint(store, task, payload)
        task = store.get_task(task.slug, task.space)

        folder = regenerate_task_folder(store, task)

        assert (folder / "HANDOFF.md").exists()
        assert (folder / "context" / "current-state.md").exists()
        assert (folder / "context" / "decisions.md").exists()
        assert (folder / "context" / "open-questions.md").exists()
        assert (folder / "record" / "development-record.md").exists()
        assert (folder / "record" / "checkpoints.md").exists()

        # Check artifact file
        artifact_files = list((folder / "artifacts").glob("*.md"))
        assert len(artifact_files) >= 1

    def test_handoff_has_no_content_duplication(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir)
        payload = CheckpointPayload(
            milestone="spec-done",
            summary="Finalized spec",
            decisions=[{"title": "Use JWT", "rationale": "Stateless scaling"}],
        )
        task = store.get_task(task.slug, task.space)
        create_checkpoint(store, task, payload)
        task = store.get_task(task.slug, task.space)
        regenerate_task_folder(store, task)

        handoff = (task.task_folder / "HANDOFF.md").read_text()
        # HANDOFF should mention the decision title but NOT the full rationale
        assert "Use JWT" in handoff
        # Full rationale lives in decisions.md, not HANDOFF
        decisions_md = (task.task_folder / "context" / "decisions.md").read_text()
        assert "Stateless scaling" in decisions_md

    def test_regenerate_wipes_and_rebuilds(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir)
        regenerate_task_folder(store, task)
        # Drop a stale file
        stale = task.task_folder / "stale-file.txt"
        stale.write_text("should be removed")
        regenerate_task_folder(store, task)
        assert not stale.exists()

    def test_user_directives_in_handoff(self, store, tmp_base_dir):
        task = self._init_task(store, tmp_base_dir)
        payload = CheckpointPayload(
            milestone="spec-done",
            summary="Done",
            user_directives=["Must scale horizontally", "Use Postgres"],
        )
        task = store.get_task(task.slug, task.space)
        create_checkpoint(store, task, payload)
        task = store.get_task(task.slug, task.space)
        regenerate_task_folder(store, task)
        handoff = (task.task_folder / "HANDOFF.md").read_text()
        assert "Must scale horizontally" in handoff
