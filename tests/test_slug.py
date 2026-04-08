"""Tests for slug generation module."""

from datetime import datetime, timezone

import pytest

from dev_workflow.slug import (
    DEFAULT_MAX_LENGTH,
    DEFAULT_STRIP_WORDS,
    generate_slug,
    generate_task_id,
    slugify,
)


# --- slugify ---


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters_stripped(self):
        assert slugify("Fix bug #123 (urgent!)") == "fix-bug-123-urgent"

    def test_already_slugified(self):
        assert slugify("already-a-slug") == "already-a-slug"

    def test_leading_trailing_whitespace(self):
        assert slugify("  hello world  ") == "hello-world"

    def test_multiple_spaces_and_hyphens(self):
        assert slugify("hello   --  world") == "hello-world"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_only_special_characters(self):
        assert slugify("!@#$%^&*()") == ""

    def test_numbers_preserved(self):
        assert slugify("version 2 release") == "version-2-release"

    def test_mixed_case(self):
        assert slugify("CamelCase AND UPPER") == "camelcase-and-upper"


# --- generate_slug ---


class TestGenerateSlug:
    def test_strip_default_words(self):
        result = generate_slug("Add authentication to the API")
        assert result == "authentication-api"

    def test_no_strip_words_needed(self):
        result = generate_slug("User data CSV export")
        assert result == "user-data-csv-export"

    def test_truncation_at_word_boundary(self):
        result = generate_slug(
            "implement comprehensive error handling for all services"
        )
        assert len(result) <= DEFAULT_MAX_LENGTH
        # Should not end with a hyphen (truncated at word boundary)
        assert not result.endswith("-")
        # After stripping "implement" and "for", slug would be
        # "comprehensive-error-handling-all-services" (41 chars).
        # Truncated at last hyphen boundary within 40 chars.
        assert result == "comprehensive-error-handling-all"

    def test_truncation_respects_max_length(self):
        result = generate_slug("a" * 50, strip_words=[], max_length=40)
        assert len(result) <= 40

    def test_collision_appends_2(self):
        result = generate_slug(
            "User data CSV export",
            existing_slugs=["user-data-csv-export"],
        )
        assert result == "user-data-csv-export-2"

    def test_collision_appends_3(self):
        result = generate_slug(
            "User data CSV export",
            existing_slugs=["user-data-csv-export", "user-data-csv-export-2"],
        )
        assert result == "user-data-csv-export-3"

    def test_no_collision(self):
        result = generate_slug(
            "User data CSV export",
            existing_slugs=["something-else"],
        )
        assert result == "user-data-csv-export"

    def test_all_words_stripped_falls_back(self):
        # All words are in DEFAULT_STRIP_WORDS
        result = generate_slug("Add to the")
        assert result == "add-to-the"

    def test_custom_strip_words(self):
        result = generate_slug(
            "Deploy the new server",
            strip_words=["deploy", "new", "the"],
        )
        assert result == "server"

    def test_custom_strip_words_empty_list(self):
        result = generate_slug("Add the feature", strip_words=[])
        assert result == "add-the-feature"

    def test_custom_max_length(self):
        result = generate_slug("short title", strip_words=[], max_length=5)
        assert len(result) <= 5

    def test_special_characters_in_title(self):
        result = generate_slug("Fix bug #123 (urgent!)")
        assert result == "bug-123-urgent"

    def test_empty_title(self):
        result = generate_slug("")
        assert result == ""


# --- generate_task_id ---


class TestGenerateTaskId:
    def test_with_specific_date(self):
        date = datetime(2026, 4, 8, tzinfo=timezone.utc)
        result = generate_task_id("User data CSV export", date=date)
        assert result == "2026-04-08-user-data-csv-export"

    def test_uses_current_date_when_none(self):
        result = generate_task_id("Some task")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result.startswith(today)
        assert result == f"{today}-some-task"

    def test_full_title_preserved(self):
        """Task IDs should NOT strip words -- they use the full title."""
        date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = generate_task_id("Add authentication to the API", date=date)
        assert result == "2026-01-01-add-authentication-to-the-api"

    def test_special_characters(self):
        date = datetime(2026, 4, 8, tzinfo=timezone.utc)
        result = generate_task_id("Fix bug #123 (urgent!)", date=date)
        assert result == "2026-04-08-fix-bug-123-urgent"
