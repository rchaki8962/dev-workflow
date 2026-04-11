"""Tests for slug generation and collision handling."""

import pytest

from dev_workflow.slug import generate_slug, resolve_slug
from dev_workflow.errors import SlugCollisionError


class TestGenerateSlug:
    def test_simple_title(self):
        assert generate_slug("Auth Middleware Rewrite") == "auth-middleware-rewrite"

    def test_strips_special_chars(self):
        assert generate_slug("Fix bug #123 (urgent!)") == "fix-bug-123-urgent"

    def test_collapses_multiple_hyphens(self):
        assert generate_slug("foo---bar") == "foo-bar"

    def test_strips_leading_trailing_hyphens(self):
        assert generate_slug("--hello world--") == "hello-world"

    def test_truncates_to_60_chars(self):
        long_title = "a" * 100
        result = generate_slug(long_title)
        assert len(result) <= 60

    def test_unicode_characters(self):
        result = generate_slug("café résumé")
        assert result == "caf-r-sum"

    def test_empty_title_raises(self):
        with pytest.raises(ValueError, match="empty"):
            generate_slug("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            generate_slug("   ")


class TestResolveSlug:
    def test_no_collision(self):
        result = resolve_slug("My Task", lambda s, sp: False, "default")
        assert result == "my-task"

    def test_first_collision_appends_2(self):
        existing = {"my-task"}
        result = resolve_slug(
            "My Task", lambda s, sp: s in existing, "default"
        )
        assert result == "my-task-2"

    def test_multiple_collisions(self):
        existing = {"my-task", "my-task-2", "my-task-3"}
        result = resolve_slug(
            "My Task", lambda s, sp: s in existing, "default"
        )
        assert result == "my-task-4"

    def test_exhausts_attempts_raises(self):
        with pytest.raises(SlugCollisionError):
            resolve_slug("My Task", lambda s, sp: True, "default")
