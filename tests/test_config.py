"""Tests for config resolution."""

import os
from pathlib import Path

import pytest

from dev_workflow.config import Config, load_config, resolve_space


class TestLoadConfig:
    def test_defaults_when_no_config_file(self, tmp_path):
        config = load_config(base_dir_default=tmp_path / "nonexistent")
        assert config.base_dir == tmp_path / "nonexistent"
        assert config.default_space == "default"

    def test_reads_config_file(self, tmp_path):
        base = tmp_path / "dev-workflow"
        base.mkdir()
        config_file = base / "config.toml"
        config_file.write_text('default_space = "personal"\n')
        config = load_config(base_dir_default=base)
        assert config.default_space == "personal"

    def test_env_var_overrides_base_dir(self, tmp_path, monkeypatch):
        env_dir = tmp_path / "from-env"
        monkeypatch.setenv("DEV_WORKFLOW_BASE_DIR", str(env_dir))
        config = load_config(base_dir_default=tmp_path / "default")
        assert config.base_dir == env_dir

    def test_malformed_toml_raises(self, tmp_path):
        base = tmp_path / "dev-workflow"
        base.mkdir()
        config_file = base / "config.toml"
        config_file.write_text("this is not valid toml [[[")
        with pytest.raises(Exception):
            load_config(base_dir_default=base)

    def test_empty_config_file_uses_defaults(self, tmp_path):
        base = tmp_path / "dev-workflow"
        base.mkdir()
        (base / "config.toml").write_text("")
        config = load_config(base_dir_default=base)
        assert config.default_space == "default"


class TestResolveSpace:
    def test_cli_flag_wins(self):
        config = Config(base_dir=Path("/tmp"), default_space="from-config")
        assert resolve_space("from-flag", config) == "from-flag"

    def test_env_var_over_config(self, monkeypatch):
        monkeypatch.setenv("DEV_WORKFLOW_SPACE", "from-env")
        config = Config(base_dir=Path("/tmp"), default_space="from-config")
        assert resolve_space(None, config) == "from-env"

    def test_config_default_used(self, monkeypatch):
        monkeypatch.delenv("DEV_WORKFLOW_SPACE", raising=False)
        config = Config(base_dir=Path("/tmp"), default_space="from-config")
        assert resolve_space(None, config) == "from-config"

    def test_hardcoded_default(self, monkeypatch):
        monkeypatch.delenv("DEV_WORKFLOW_SPACE", raising=False)
        config = Config(base_dir=Path("/tmp"), default_space="default")
        assert resolve_space(None, config) == "default"
