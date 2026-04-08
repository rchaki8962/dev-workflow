"""Configuration loading with resolution order: CLI flag > env var > config file > default."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_DIR = "~/.dev-workflow"
DEFAULT_STRIP_WORDS = [
    "add", "fix", "update", "implement", "create",
    "the", "a", "an", "for", "with", "to", "in",
]


@dataclass
class Config:
    base_dir: Path
    strip_words: list[str] = field(default_factory=lambda: list(DEFAULT_STRIP_WORDS))

    @property
    def state_dir(self) -> Path:
        return self.base_dir / "state"

    @property
    def tasks_dir(self) -> Path:
        return self.base_dir / "tasks"


def load_config(
    base_dir_override: str | None = None,
    config_path: str | None = None,
) -> Config:
    """
    Load config with resolution order:
    1. base_dir_override (CLI flag)
    2. DEV_WORKFLOW_DIR env var
    3. config file (if provided)
    4. hardcoded default (~/.dev-workflow)
    """
    base_dir: str | None = None
    strip_words: list[str] | None = None

    # Try config file first (lowest priority for base_dir, but has strip_words)
    if config_path:
        config_file = Path(config_path).expanduser()
        if config_file.exists():
            with open(config_file, "rb") as f:
                data = tomllib.load(f)
            base_dir = data.get("paths", {}).get("base_dir")
            strip_words = data.get("slug", {}).get("strip_words")

    # Env var overrides config file
    env_dir = os.environ.get("DEV_WORKFLOW_DIR")
    if env_dir:
        base_dir = env_dir

    # CLI flag overrides everything
    if base_dir_override:
        base_dir = base_dir_override

    # Fall back to default
    if base_dir is None:
        base_dir = DEFAULT_BASE_DIR

    resolved_base = Path(base_dir).expanduser().resolve()

    return Config(
        base_dir=resolved_base,
        strip_words=strip_words if strip_words is not None else list(DEFAULT_STRIP_WORDS),
    )
