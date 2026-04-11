"""Integration tests for CLI commands exercising full workflows."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from dev_workflow.cli import cli


@pytest.fixture
def run(tmp_base_dir):
    """CLI runner with --base-dir pointed at temp directory."""
    runner = CliRunner()

    def invoke(*args, input=None):
        return runner.invoke(
            cli, ["--base-dir", str(tmp_base_dir)] + list(args), input=input
        )

    return invoke


class TestFullLifecycle:
    """Full lifecycle: init -> checkpoint -> resume -> status -> list."""

    def test_init_checkpoint_resume_status_list(self, run, tmp_base_dir):
        """Full workflow through all core commands."""
        # 1. Init task
        result = run("init", "test-task", "--prompt", "Build a CLI tool")
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        slug = data["slug"]
        task_id = data["task_id"]
        assert slug
        assert task_id
        task_folder = Path(data["task_folder"])
        assert task_folder.parent.parent.parent == tmp_base_dir

        # 2. Checkpoint via stdin
        payload = {
            "milestone": "design-complete",
            "summary": "Completed initial design",
            "decisions": [
                {
                    "title": "Use Click for CLI",
                    "rationale": "Industry standard with great testing support",
                    "alternatives": ["argparse", "typer"],
                }
            ],
            "artifacts": [
                {
                    "type": "design",
                    "name": "architecture",
                    "content": "# Architecture\n\nModular design with store, CLI, domain.",
                    "description": "High-level architecture document",
                }
            ],
            "next_steps": ["Implement store module", "Add CLI commands"],
            "open_questions": ["Should we support plugins?"],
        }
        result = run("checkpoint", slug, input=json.dumps(payload))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["checkpoint_number"] == 1
        assert "saved" in data["message"].lower()

        # 3. Resume (json format)
        result = run("resume", slug, "--format", "json")
        assert result.exit_code == 0, result.output
        bundle = json.loads(result.output)
        assert bundle["slug"] == slug
        assert bundle["title"] == "test-task"
        assert bundle["last_milestone"] == "design-complete"
        assert bundle["checkpoint_count"] == 2  # #0 (init) + #1
        assert len(bundle["decisions"]) == 1
        assert bundle["decisions"][0]["title"] == "Use Click for CLI"
        assert len(bundle["artifacts"]) == 1
        assert bundle["artifacts"][0]["name"] == "architecture"
        assert bundle["artifacts"][0]["version"] == 1
        assert len(bundle["next_steps"]) == 2
        assert len(bundle["open_questions"]) == 1

        # 4. Resume (md format) - creates task folder
        result = run("resume", slug, "--format", "md")
        assert result.exit_code == 0, result.output
        handoff_path = result.output.strip()
        assert Path(handoff_path).exists()
        assert Path(handoff_path).name == "HANDOFF.md"
        content = Path(handoff_path).read_text()
        assert "test-task" in content
        assert "design-complete" in content
        assert "Use Click for CLI" in content

        # 5. Status (specific task)
        result = run("status", slug)
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["slug"] == slug
        assert data["title"] == "test-task"
        assert data["last_milestone"] == "design-complete"
        assert data["checkpoint_count"] == 2
        assert data["decision_count"] == 1
        assert data["artifact_count"] == 2  # prompt + architecture

        # 6. Status (all tasks in space)
        result = run("status")
        assert result.exit_code == 0, result.output
        tasks = json.loads(result.output)
        assert len(tasks) == 1
        assert tasks[0]["slug"] == slug
        assert tasks[0]["checkpoint_count"] == 2

        # 7. List
        result = run("list")
        assert result.exit_code == 0, result.output
        tasks = json.loads(result.output)
        assert len(tasks) == 1
        assert tasks[0]["slug"] == slug
        assert tasks[0]["space"] == "default"

    def test_multiple_checkpoints(self, run):
        """Two sequential checkpoints with decisions and artifacts."""
        # Init (without prompt, so no checkpoint #0)
        result = run("init", "multi-checkpoint-task")
        assert result.exit_code == 0, result.output
        slug = json.loads(result.output)["slug"]

        # Checkpoint 1
        payload1 = {
            "milestone": "design",
            "summary": "Design phase complete",
            "decisions": [{"title": "Decision 1"}],
            "artifacts": [
                {
                    "type": "doc",
                    "name": "spec",
                    "content": "Version 1",
                }
            ],
        }
        result = run("checkpoint", slug, input=json.dumps(payload1))
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["checkpoint_number"] == 1

        # Checkpoint 2
        payload2 = {
            "milestone": "implementation",
            "summary": "Implementation started",
            "decisions": [{"title": "Decision 2"}],
            "artifacts": [
                {
                    "type": "doc",
                    "name": "spec",
                    "content": "Version 2",
                }
            ],
        }
        result = run("checkpoint", slug, input=json.dumps(payload2))
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["checkpoint_number"] == 2

        # Resume shows latest state
        result = run("resume", slug, "--format", "json")
        assert result.exit_code == 0, result.output
        bundle = json.loads(result.output)
        assert bundle["checkpoint_count"] == 2  # #1 + #2 (no #0 without prompt)
        assert len(bundle["decisions"]) == 2
        assert len(bundle["artifacts"]) == 1  # Only latest version
        assert bundle["artifacts"][0]["version"] == 2

        # Status shows counts
        result = run("status", slug)
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["checkpoint_count"] == 2
        assert data["decision_count"] == 2

    def test_artifact_dedup(self, run):
        """Two checkpoints with same artifact content results in single version."""
        # Init
        result = run("init", "dedup-task")
        assert result.exit_code == 0, result.output
        slug = json.loads(result.output)["slug"]

        # Checkpoint 1 with artifact
        content = "# Same content"
        payload1 = {
            "milestone": "m1",
            "summary": "First checkpoint",
            "artifacts": [
                {"type": "doc", "name": "readme", "content": content}
            ],
        }
        result = run("checkpoint", slug, input=json.dumps(payload1))
        assert result.exit_code == 0, result.output

        # Checkpoint 2 with identical artifact content
        payload2 = {
            "milestone": "m2",
            "summary": "Second checkpoint",
            "artifacts": [
                {"type": "doc", "name": "readme", "content": content}
            ],
        }
        result = run("checkpoint", slug, input=json.dumps(payload2))
        assert result.exit_code == 0, result.output

        # Resume shows version 1 only (no increment)
        result = run("resume", slug, "--format", "json")
        assert result.exit_code == 0, result.output
        bundle = json.loads(result.output)
        assert len(bundle["artifacts"]) == 1
        assert bundle["artifacts"][0]["version"] == 1


class TestMultiSpace:
    """Multi-space scenarios."""

    def test_two_spaces_list_all(self, run):
        """Create two spaces, init task in each, list --all-spaces shows both."""
        # Create spaces
        result = run("space", "create", "space-a", "--description", "First space")
        assert result.exit_code == 0, result.output

        result = run("space", "create", "space-b", "--description", "Second space")
        assert result.exit_code == 0, result.output

        # Init task in space-a
        result = run("--space", "space-a", "init", "task-a")
        assert result.exit_code == 0, result.output
        slug_a = json.loads(result.output)["slug"]

        # Init task in space-b
        result = run("--space", "space-b", "init", "task-b")
        assert result.exit_code == 0, result.output
        slug_b = json.loads(result.output)["slug"]

        # List in space-a shows only task-a
        result = run("--space", "space-a", "list")
        assert result.exit_code == 0, result.output
        tasks = json.loads(result.output)
        assert len(tasks) == 1
        assert tasks[0]["slug"] == slug_a
        assert tasks[0]["space"] == "space-a"

        # List with --all-spaces shows both
        result = run("list", "--all-spaces")
        assert result.exit_code == 0, result.output
        tasks = json.loads(result.output)
        assert len(tasks) == 2
        spaces = {t["space"] for t in tasks}
        assert spaces == {"space-a", "space-b"}

    def test_space_info(self, run):
        """Create space, init task, verify space info shows task_count."""
        # Create space
        result = run("space", "create", "test-space")
        assert result.exit_code == 0, result.output

        # Space info shows 0 tasks
        result = run("space", "info", "test-space")
        assert result.exit_code == 0, result.output
        info = json.loads(result.output)
        assert info["name"] == "test-space"
        assert info["task_count"] == 0

        # Init task
        result = run("--space", "test-space", "init", "test-task")
        assert result.exit_code == 0, result.output

        # Space info shows 1 task
        result = run("space", "info", "test-space")
        assert result.exit_code == 0, result.output
        info = json.loads(result.output)
        assert info["task_count"] == 1


class TestErrorPaths:
    """Error scenarios that should exit with code 1."""

    def test_checkpoint_nonexistent_task(self, run):
        """Checkpoint on non-existent task fails."""
        payload = {"milestone": "x", "summary": "y"}
        result = run("checkpoint", "nonexistent", input=json.dumps(payload))
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_remove_space_with_tasks(self, run):
        """Cannot remove space that has tasks."""
        # Create space and task
        result = run("space", "create", "busy-space")
        assert result.exit_code == 0, result.output

        result = run("--space", "busy-space", "init", "task")
        assert result.exit_code == 0, result.output

        # Try to remove
        result = run("space", "remove", "busy-space")
        assert result.exit_code == 1
        assert "task" in result.output.lower() or "not empty" in result.output.lower()

    def test_malformed_json_payload(self, run):
        """Malformed JSON triggers exit code 1."""
        result = run("init", "task")
        assert result.exit_code == 0, result.output
        slug = json.loads(result.output)["slug"]

        result = run("checkpoint", slug, input="{invalid json")
        assert result.exit_code == 1
        assert "invalid" in result.output.lower() or "json" in result.output.lower()

    def test_missing_required_fields(self, run):
        """Payload missing 'summary' field fails."""
        result = run("init", "task")
        assert result.exit_code == 0, result.output
        slug = json.loads(result.output)["slug"]

        # Milestone without summary (missing required field)
        payload = {"milestone": "x"}
        result = run("checkpoint", slug, input=json.dumps(payload))
        assert result.exit_code == 1
        # KeyError in CLI when reading data["summary"], or validation error
        assert result.exit_code == 1


class TestRegenerate:
    """Test regenerate command rebuilds task folder."""

    def test_regenerate_rebuilds_folder(self, run):
        """Init, checkpoint, resume md (creates folder), delete folder, regenerate, verify HANDOFF.md exists."""
        # Init with prompt
        result = run("init", "regen-task", "--prompt", "Test prompt")
        assert result.exit_code == 0, result.output
        slug = json.loads(result.output)["slug"]
        task_folder = Path(json.loads(result.output)["task_folder"])

        # Checkpoint
        payload = {
            "milestone": "done",
            "summary": "Finished",
            "artifacts": [{"type": "doc", "name": "output", "content": "Result"}],
        }
        result = run("checkpoint", slug, input=json.dumps(payload))
        assert result.exit_code == 0, result.output

        # Resume md to create folder
        result = run("resume", slug, "--format", "md")
        assert result.exit_code == 0, result.output
        handoff = Path(result.output.strip())
        assert handoff.exists()

        # Delete folder
        import shutil
        shutil.rmtree(task_folder)
        assert not task_folder.exists()

        # Regenerate
        result = run("regenerate", slug)
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert Path(data["task_folder"]) == task_folder

        # Verify HANDOFF.md exists
        assert (task_folder / "HANDOFF.md").exists()
        content = (task_folder / "HANDOFF.md").read_text()
        assert "regen-task" in content
        assert "done" in content


class TestPayloadFile:
    """Test checkpoint with --payload file option."""

    def test_checkpoint_via_payload_file(self, run, tmp_path):
        """Init, write payload to tmp file, checkpoint with --payload flag, verify it works."""
        # Init
        result = run("init", "file-payload-task")
        assert result.exit_code == 0, result.output
        slug = json.loads(result.output)["slug"]

        # Write payload to file
        payload_file = tmp_path / "payload.json"
        payload = {
            "milestone": "file-test",
            "summary": "Testing file-based payload",
            "decisions": [{"title": "Use file input"}],
            "artifacts": [
                {
                    "type": "test",
                    "name": "result",
                    "content": "File content works",
                }
            ],
        }
        payload_file.write_text(json.dumps(payload))

        # Checkpoint with --payload
        result = run("checkpoint", slug, "--payload", str(payload_file))
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["checkpoint_number"] == 1

        # Resume and verify
        result = run("resume", slug, "--format", "json")
        assert result.exit_code == 0, result.output
        bundle = json.loads(result.output)
        assert bundle["last_milestone"] == "file-test"
        assert bundle["summary"] == "Testing file-based payload"
        assert len(bundle["decisions"]) == 1
        assert bundle["decisions"][0]["title"] == "Use file input"
        assert len(bundle["artifacts"]) == 1
        assert bundle["artifacts"][0]["name"] == "result"
