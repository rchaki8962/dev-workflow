# src/dev_workflow/space.py
"""Space management -- thin wrappers over store with validation."""

from __future__ import annotations

import re

from dev_workflow.errors import SpaceNotFoundError
from dev_workflow.models import Space
from dev_workflow.store import Store

_SPACE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _validate_space_name(name: str) -> None:
    if not name or not _SPACE_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid space name '{name}': must be lowercase alphanumeric with hyphens, "
            "starting with a letter or digit"
        )


def create_space(store: Store, name: str, description: str = "") -> Space:
    """Create a new space. Validates name format."""
    _validate_space_name(name)
    store.create_space(name, description)
    space = store.get_space(name)
    assert space is not None
    return space


def list_spaces(store: Store) -> list[Space]:
    """List all spaces."""
    return store.list_spaces()


def remove_space(store: Store, name: str) -> None:
    """Remove a space. Fails if tasks exist."""
    if store.get_space(name) is None:
        raise SpaceNotFoundError(f"Space '{name}' not found")
    store.remove_space(name)


def get_space_info(store: Store, name: str) -> dict:
    """Get space details including task count."""
    space = store.get_space(name)
    if space is None:
        raise SpaceNotFoundError(f"Space '{name}' not found")
    tasks = store.list_tasks(space=name)
    return {
        "name": space.name,
        "description": space.description,
        "created": space.created.isoformat(),
        "task_count": len(tasks),
    }
