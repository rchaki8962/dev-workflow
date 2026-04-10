"""Tests for dev_workflow configuration loading."""

from pathlib import Path

import pytest

from dev_workflow.config import (
    DEFAULT_BASE_DIR,
    DEFAULT_STRIP_WORDS,
    Config,
    load_config,
)


# ---------------------------------------------------------------------------
# Config dataclass tests
# ---------------------------------------------------------------------------


class TestConfigDataclass:
    def test_state_dir_property(self):
        cfg = Config(base_dir=Path("/data"))
        cfg._active_space = "default"
        assert cfg.state_dir == Path("/data/default/state")

    def test_tasks_dir_property(self):
        cfg = Config(base_dir=Path("/data"))
        cfg._active_space = "default"
        assert cfg.tasks_dir == Path("/data/default/tasks")

    def test_default_strip_words(self):
        cfg = Config(base_dir=Path("/data"))
        assert cfg.strip_words == DEFAULT_STRIP_WORDS

    def test_custom_strip_words(self):
        cfg = Config(base_dir=Path("/data"), strip_words=["foo", "bar"])
        assert cfg.strip_words == ["foo", "bar"]


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------


class TestLoadConfigDefaults:
    def test_default_base_dir(self, monkeypatch):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        cfg = load_config()
        expected = Path(DEFAULT_BASE_DIR).expanduser().resolve()
        assert cfg.base_dir == expected

    def test_default_strip_words_match_constant(self, monkeypatch):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        cfg = load_config()
        assert cfg.strip_words == DEFAULT_STRIP_WORDS


class TestLoadConfigEnvVar:
    def test_env_var_overrides_default(self, monkeypatch, tmp_path):
        env_dir = str(tmp_path / "env-data")
        monkeypatch.setenv("DEV_WORKFLOW_DIR", env_dir)
        cfg = load_config()
        assert cfg.base_dir == Path(env_dir).resolve()

    def test_cli_flag_overrides_env_var(self, monkeypatch, tmp_path):
        env_dir = str(tmp_path / "env-data")
        cli_dir = str(tmp_path / "cli-data")
        monkeypatch.setenv("DEV_WORKFLOW_DIR", env_dir)
        cfg = load_config(base_dir_override=cli_dir)
        assert cfg.base_dir == Path(cli_dir).resolve()


class TestLoadConfigFile:
    def test_config_file_base_dir_and_strip_words(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[paths]\nbase_dir = "/custom/dir"\n\n'
            '[slug]\nstrip_words = ["only", "these"]\n'
        )
        cfg = load_config(config_path=str(config_file))
        assert cfg.base_dir == Path("/custom/dir").resolve()
        assert cfg.strip_words == ["only", "these"]

    def test_cli_flag_overrides_config_file_base_dir(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text('[paths]\nbase_dir = "/from-file"\n')
        cli_dir = str(tmp_path / "cli-data")
        cfg = load_config(base_dir_override=cli_dir, config_path=str(config_file))
        assert cfg.base_dir == Path(cli_dir).resolve()

    def test_missing_config_file_uses_defaults(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        cfg = load_config(config_path=str(tmp_path / "nonexistent.toml"))
        expected = Path(DEFAULT_BASE_DIR).expanduser().resolve()
        assert cfg.base_dir == expected
        assert cfg.strip_words == DEFAULT_STRIP_WORDS

    def test_empty_toml_uses_defaults(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        config_file = tmp_path / "empty.toml"
        config_file.write_text("")
        cfg = load_config(config_path=str(config_file))
        expected = Path(DEFAULT_BASE_DIR).expanduser().resolve()
        assert cfg.base_dir == expected
        assert cfg.strip_words == DEFAULT_STRIP_WORDS

    def test_toml_missing_keys_graceful_defaults(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        config_file = tmp_path / "partial.toml"
        config_file.write_text('[other]\nkey = "value"\n')
        cfg = load_config(config_path=str(config_file))
        expected = Path(DEFAULT_BASE_DIR).expanduser().resolve()
        assert cfg.base_dir == expected
        assert cfg.strip_words == DEFAULT_STRIP_WORDS

    def test_strip_words_from_toml_overrides_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text('[slug]\nstrip_words = ["custom", "words"]\n')
        cfg = load_config(config_path=str(config_file))
        assert cfg.strip_words == ["custom", "words"]
        assert cfg.strip_words != DEFAULT_STRIP_WORDS


# ---------------------------------------------------------------------------
# Space support tests
# ---------------------------------------------------------------------------


class TestConfigSpaceProperties:
    def test_space_dir(self, tmp_path):
        cfg = Config(base_dir=tmp_path, default_space="default")
        cfg._active_space = "default"
        assert cfg.space_dir == tmp_path / "default"

    def test_state_dir_routes_through_space(self, tmp_path):
        cfg = Config(base_dir=tmp_path, default_space="default")
        cfg._active_space = "personal"
        assert cfg.state_dir == tmp_path / "personal" / "state"

    def test_tasks_dir_routes_through_space(self, tmp_path):
        cfg = Config(base_dir=tmp_path, default_space="default")
        cfg._active_space = "personal"
        assert cfg.tasks_dir == tmp_path / "personal" / "tasks"

    def test_spaces_file(self, tmp_path):
        cfg = Config(base_dir=tmp_path)
        assert cfg.spaces_file == tmp_path / "spaces.json"

    def test_default_space_is_default(self):
        cfg = Config(base_dir=Path("/data"))
        assert cfg.default_space == "default"


class TestLoadConfigSpace:
    def test_space_override(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        monkeypatch.delenv("DEV_WORKFLOW_SPACE", raising=False)
        cfg = load_config(base_dir_override=str(tmp_path), space_override="personal")
        assert cfg._active_space == "personal"

    def test_space_env_var(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        monkeypatch.setenv("DEV_WORKFLOW_SPACE", "work")
        cfg = load_config(base_dir_override=str(tmp_path))
        assert cfg._active_space == "work"

    def test_space_override_beats_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DEV_WORKFLOW_SPACE", "env-space")
        cfg = load_config(base_dir_override=str(tmp_path), space_override="cli-space")
        assert cfg._active_space == "cli-space"

    def test_default_space_from_config_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        monkeypatch.delenv("DEV_WORKFLOW_SPACE", raising=False)
        config_file = tmp_path / "config.toml"
        config_file.write_text('[spaces]\ndefault = "mydefault"\n')
        cfg = load_config(base_dir_override=str(tmp_path), config_path=str(config_file))
        assert cfg._active_space == "mydefault"

    def test_default_space_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEV_WORKFLOW_DIR", raising=False)
        monkeypatch.delenv("DEV_WORKFLOW_SPACE", raising=False)
        cfg = load_config(base_dir_override=str(tmp_path))
        assert cfg._active_space == "default"
