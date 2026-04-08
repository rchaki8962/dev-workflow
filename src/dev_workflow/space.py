"""Space management: CRUD for isolated task namespaces."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from dev_workflow.exceptions import SpaceNotFoundError
from dev_workflow.models import Space

SPACE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_SPACE_NAME_LENGTH = 40


def validate_space_name(name: str) -> None:
    """Validate space name. Raises ValueError if invalid."""
    if not name:
        raise ValueError("Space name cannot be empty")
    if len(name) > MAX_SPACE_NAME_LENGTH:
        raise ValueError(f"Space name must be at most {MAX_SPACE_NAME_LENGTH} characters")
    if name != name.lower():
        raise ValueError("Space name must be lowercase")
    if not SPACE_NAME_PATTERN.match(name):
        raise ValueError(
            f"Space name must be lowercase alphanumeric with hyphens: {name!r}"
        )


class SpaceManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.spaces_file = base_dir / "spaces.json"

    def _load_registry(self) -> list[dict]:
        if not self.spaces_file.exists():
            return []
        return json.loads(self.spaces_file.read_text())

    def _save_registry(self, entries: list[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.spaces_file.write_text(json.dumps(entries, indent=2) + "\n")

    def _dict_to_space(self, data: dict) -> Space:
        return Space(
            name=data["name"],
            description=data.get("description", ""),
            created=datetime.fromisoformat(data["created"].replace("Z", "+00:00")),
        )

    def _space_to_dict(self, space: Space) -> dict:
        return {
            "name": space.name,
            "description": space.description,
            "created": space.created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def create(self, name: str, description: str = "") -> Space:
        validate_space_name(name)
        entries = self._load_registry()
        if any(e["name"] == name for e in entries):
            raise ValueError(f"Space '{name}' already exists")

        space = Space(
            name=name,
            description=description,
            created=datetime.now(timezone.utc),
        )
        entries.append(self._space_to_dict(space))
        self._save_registry(entries)

        space_dir = self.base_dir / name
        (space_dir / "state").mkdir(parents=True, exist_ok=True)
        (space_dir / "tasks").mkdir(parents=True, exist_ok=True)

        return space

    def list_all(self) -> list[Space]:
        entries = self._load_registry()
        spaces = [self._dict_to_space(e) for e in entries]
        spaces.sort(key=lambda s: s.name)
        return spaces

    def get(self, name: str) -> Space:
        entries = self._load_registry()
        for e in entries:
            if e["name"] == name:
                return self._dict_to_space(e)
        raise SpaceNotFoundError(name)

    def remove(self, name: str, force: bool = False) -> None:
        entries = self._load_registry()
        found = False
        for e in entries:
            if e["name"] == name:
                found = True
                break
        if not found:
            raise SpaceNotFoundError(name)

        state_dir = self.base_dir / name / "state"
        if not force and state_dir.exists() and list(state_dir.glob("*.json")):
            raise ValueError(
                f"Space '{name}' has tasks. Use --force to remove anyway."
            )

        entries = [e for e in entries if e["name"] != name]
        self._save_registry(entries)

        space_dir = self.base_dir / name
        if space_dir.exists():
            shutil.rmtree(space_dir)

    def exists(self, name: str) -> bool:
        entries = self._load_registry()
        return any(e["name"] == name for e in entries)

    def ensure(self, name: str) -> Space:
        if self.exists(name):
            return self.get(name)
        return self.create(name)
