"""Slug generation for task IDs and short aliases."""

import re
from datetime import datetime, timezone

DEFAULT_STRIP_WORDS = [
    "add", "fix", "update", "implement", "create",
    "the", "a", "an", "for", "with", "to", "in",
]
DEFAULT_MAX_LENGTH = 40


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug: lowercase, hyphens, no special chars."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    text = text.strip("-")
    return text


def generate_slug(
    title: str,
    strip_words: list[str] | None = None,
    existing_slugs: list[str] | None = None,
    max_length: int = DEFAULT_MAX_LENGTH,
) -> str:
    """
    Generate a short slug from a title.

    - Strip configured words (case-insensitive)
    - Slugify the remainder
    - Truncate at word boundary to max_length
    - On collision with existing_slugs, append -2, -3, etc.
    """
    if strip_words is None:
        strip_words = DEFAULT_STRIP_WORDS
    if existing_slugs is None:
        existing_slugs = []

    # Strip words (as whole words, case-insensitive)
    words = title.split()
    stripped = [w for w in words if w.lower() not in strip_words]

    # If all words were stripped, fall back to the original title
    if not stripped:
        stripped = title.split()

    slug = slugify(" ".join(stripped))

    # Truncate at word (hyphen) boundary
    if len(slug) > max_length:
        truncated = slug[:max_length]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            slug = truncated[:last_hyphen]
        else:
            slug = truncated

    # Handle collisions
    base_slug = slug
    counter = 2
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


def generate_task_id(title: str, date: datetime | None = None) -> str:
    """
    Generate a task ID: <YYYY-MM-DD>-<slugified-full-title>.

    Unlike generate_slug, this uses the FULL title (no word stripping)
    because task_id should be descriptive and unique.
    """
    if date is None:
        date = datetime.now(timezone.utc)
    date_str = date.strftime("%Y-%m-%d")
    slug = slugify(title)
    return f"{date_str}-{slug}"
