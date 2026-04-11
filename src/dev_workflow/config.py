"""Configuration resolution.

Resolution order for base_dir: DEV_WORKFLOW_BASE_DIR env var > default (~/.dev-workflow).
Resolution order for default_space: config file > "default".
Active space resolution (via resolve_space): CLI flag > DEV_WORKFLOW_SPACE env var > config > "default".
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_BASE_DIR = Path.home() / ".dev-workflow"
_DEFAULT_SPACE = "default"


@dataclass
class Config:
    base_dir: Path
    default_space: str


def load_config(base_dir_default: Path = _DEFAULT_BASE_DIR) -> Config:
    """Load configuration from env vars and config file.

    Args:
        base_dir_default: Default base directory if not set by env var.
    """
    base_dir = Path(os.environ.get("DEV_WORKFLOW_BASE_DIR", str(base_dir_default)))

    default_space = _DEFAULT_SPACE
    config_file = base_dir / "config.toml"
    if config_file.is_file():
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
        default_space = data.get("default_space", _DEFAULT_SPACE)

    return Config(base_dir=base_dir, default_space=default_space)


def resolve_space(cli_flag: str | None, config: Config) -> str:
    """Resolve active space. Priority: CLI flag > env var > config > "default"."""
    if cli_flag is not None:
        return cli_flag
    env_space = os.environ.get("DEV_WORKFLOW_SPACE")
    if env_space is not None:
        return env_space
    return config.default_space
