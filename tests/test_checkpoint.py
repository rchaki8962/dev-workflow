# tests/test_checkpoint.py
"""Tests for checkpoint domain logic."""

import hashlib
from datetime import datetime, timezone

import pytest

from dev_workflow.checkpoint import create_checkpoint, validate_payload
from dev_workflow.errors import PayloadError
from dev_workflow.models import CheckpointPayload


class TestValidatePayload:
    def test_valid_minimal(self):
        payload = CheckpointPayload(milestone="done", summary="Finished work")
        validate_payload(payload)  # Should not raise

    def test_empty_milestone_raises(self):
        payload = CheckpointPayload(milestone="", summary="Stuff")
        with pytest.raises(PayloadError, match="milestone"):
            validate_payload(payload)

    def test_empty_summary_raises(self):
        payload = CheckpointPayload(milestone="done", summary="")
        with pytest.raises(PayloadError, match="summary"):
            validate_payload(payload)

    def test_artifact_missing_name_raises(self):
        payload = CheckpointPayload(
            milestone="done",
            summary="Stuff",
            artifacts=[{"type": "spec", "content": "x"}],
        )
        with pytest.raises(PayloadError, match="name"):
            validate_payload(payload)

    def test_artifact_empty_content_raises(self):
        payload = CheckpointPayload(
            milestone="done",
            summary="Stuff",
            artifacts=[{"type": "spec", "name": "s", "content": ""}],
        )
        with pytest.raises(PayloadError, match="content"):
            validate_payload(payload)

    def test_decision_missing_title_raises(self):
        payload = CheckpointPayload(
            milestone="done",
            summary="Stuff",
            decisions=[{"rationale": "because"}],
        )
        with pytest.raises(PayloadError, match="title"):
            validate_payload(payload)

    def test_verification_missing_type_raises(self):
        payload = CheckpointPayload(
            milestone="done",
            summary="Stuff",
            verifications=[{"result": "pass"}],
        )
        with pytest.raises(PayloadError, match="type"):
            validate_payload(payload)

    def test_verification_missing_result_raises(self):
        payload = CheckpointPayload(
            milestone="done",
            summary="Stuff",
            verifications=[{"type": "test-run"}],
        )
        with pytest.raises(PayloadError, match="result"):
            validate_payload(payload)


class TestCreateCheckpoint:
    def test_creates_checkpoint_returns_number(self, store):
        store.ensure_space("default")
        from dev_workflow.task import init_task
        from pathlib import Path

        task = init_task(store, Path("/tmp"), "Test", "default")
        payload = CheckpointPayload(milestone="first", summary="Did stuff")
        num = create_checkpoint(store, task, payload)
        assert num >= 1

    def test_decisions_get_numbered(self, store):
        store.ensure_space("default")
        from dev_workflow.task import init_task
        from pathlib import Path

        task = init_task(store, Path("/tmp"), "Test", "default")
        payload = CheckpointPayload(
            milestone="first",
            summary="Did stuff",
            decisions=[
                {"title": "A", "rationale": "because A"},
                {"title": "B", "rationale": "because B"},
            ],
        )
        create_checkpoint(store, task, payload)
        decisions = store.get_decisions(task.task_id)
        assert len(decisions) == 2
        assert decisions[0].decision_number == 1
        assert decisions[1].decision_number == 2

    def test_artifact_checksum_computed(self, store):
        store.ensure_space("default")
        from dev_workflow.task import init_task
        from pathlib import Path

        task = init_task(store, Path("/tmp"), "Test", "default")
        content = "# My Spec"
        payload = CheckpointPayload(
            milestone="first",
            summary="Did stuff",
            artifacts=[{"type": "spec", "name": "my-spec", "content": content}],
        )
        create_checkpoint(store, task, payload)
        artifact = store.get_artifact_latest(task.task_id, "my-spec")
        assert artifact is not None
        assert artifact.checksum == hashlib.sha256(content.encode()).hexdigest()

    def test_user_directives_stored(self, store):
        store.ensure_space("default")
        from dev_workflow.task import init_task
        from pathlib import Path

        task = init_task(store, Path("/tmp"), "Test", "default")
        payload = CheckpointPayload(
            milestone="first",
            summary="Did stuff",
            user_directives=["Must scale horizontally", "Use Postgres"],
        )
        create_checkpoint(store, task, payload)
        cps = store.get_checkpoints(task.task_id)
        # Find the non-init checkpoint
        cp = [c for c in cps if c.milestone == "first"][0]
        assert cp.user_directives == ["Must scale horizontally", "Use Postgres"]
