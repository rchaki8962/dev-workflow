"""Slug generation and collision handling.

Slugs are deterministic: lowercase, strip non-alphanumeric, hyphens for spaces,
truncate to 60 chars. Collision handling appends -2, -3, etc.
"""

from __future__ import annotations

import re
from typing import Callable

from dev_workflow.errors import SlugCollisionError

_MAX_SLUG_LENGTH = 60
_MAX_COLLISION_ATTEMPTS = 100


def generate_slug(title: str) -> str:
    """Generate a URL-safe slug from a title.

    Raises ValueError if title is empty or whitespace-only.
    """
    stripped = title.strip()
    if not stripped:
        raise ValueError("Cannot generate slug from empty title")

    slug = stripped.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug[:_MAX_SLUG_LENGTH]
    slug = slug.strip("-")
    return slug


def resolve_slug(
    title: str,
    slug_exists_fn: Callable[[str, str], bool],
    space: str,
) -> str:
    """Generate a slug and handle collisions by appending -2, -3, etc.

    Args:
        title: The task title to slugify.
        slug_exists_fn: Callback(slug, space) -> bool.
        space: The space to check collisions within.

    Raises:
        SlugCollisionError: If all attempts are exhausted.
    """
    base = generate_slug(title)
    if not slug_exists_fn(base, space):
        return base

    for i in range(2, _MAX_COLLISION_ATTEMPTS + 2):
        candidate = f"{base}-{i}"
        if not slug_exists_fn(candidate, space):
            return candidate

    raise SlugCollisionError(
        f"Could not generate unique slug for '{title}' after "
        f"{_MAX_COLLISION_ATTEMPTS} attempts"
    )
