"""Tests for dev_workflow.plan_parser module."""

import pytest

from dev_workflow.exceptions import PlanParseError
from dev_workflow.models import PlanTask
from dev_workflow.plan_parser import parse_plan


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

WELL_FORMED_PLAN = """\
# Implementation Plan: Build Widget System

**Approved Spec**: specs/widget-v1.md

## Approach
Incremental approach starting with the data model.

## Tasks

### Task 1: Create data model

**Description:**
Define the Widget dataclass with all required fields.

**Verification:**
- [ ] Unit tests pass for Widget dataclass
- [ ] All fields have correct types

**Dependencies:** none

### Task 2: Build parser

**Description:**
Implement the parser that reads widget configuration
from YAML files and returns Widget instances.

This is a multi-line description that spans
several lines of text.

**Verification:**
- [ ] Parser handles valid YAML
- [ ] Parser raises on invalid input
- [ ] Edge cases covered

**Dependencies:** Task 1

### Task 3: Integration layer

**Description:**
Wire up the parser with the data model and expose a public API.

**Verification:**
- [ ] End-to-end test passes

**Dependencies:** Task 1, Task 2

## Risks
- YAML format may change
- Performance with large files
"""

PLAN_NO_DEPENDENCIES_LINE = """\
# Implementation Plan: Simple

## Tasks

### Task 1: Only task

**Description:**
Do the thing.

**Verification:**
- [ ] It works
"""

PLAN_DEPENDENCIES_NONE = """\
# Implementation Plan: Dep None

## Tasks

### Task 1: First task

**Description:**
First task description.

**Verification:**
- [ ] Check it

**Dependencies:** none
"""

PLAN_LENIENT_HEADINGS = """\
# Implementation Plan: Lenient

## Tasks

## Task 1: Two-hash heading

**Description:**
This task uses two hashes instead of three.

**Verification:**
- [ ] Parsed correctly

**Dependencies:** none
"""

PLAN_MIXED_HEADINGS = """\
# Implementation Plan: Mixed

## Tasks

## Task 1: Two-hash task

**Description:**
Uses two hashes.

**Verification:**
- [ ] Works

**Dependencies:** none

### Task 2: Three-hash task

**Description:**
Uses three hashes.

**Verification:**
- [ ] Also works

**Dependencies:** Task 1
"""

PLAN_NO_VERIFICATION = """\
# Implementation Plan: No Verification

## Tasks

### Task 1: Title only

**Description:**
Only has a title and description, no verification section.

**Dependencies:** none
"""

EMPTY_PLAN = """\
# Implementation Plan: Empty

## Approach
Nothing to do.

## Risks
- No tasks defined
"""

PLAN_EXTRA_CONTENT = """\
# Implementation Plan: Extra Content

## Tasks

### Task 1: First

**Description:**
First task.

**Verification:**
- [ ] Check 1

**Dependencies:** none

Some extra content that appears between tasks.
This should not be captured as part of any task.

### Task 2: Second

**Description:**
Second task.

**Verification:**
- [ ] Check 2

**Dependencies:** Task 1
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseWellFormedPlan:
    """Parse a well-formed plan with 3 tasks and verify all fields."""

    def test_returns_three_tasks(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        assert len(tasks) == 3

    def test_all_are_plan_task_instances(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        for task in tasks:
            assert isinstance(task, PlanTask)

    def test_task_1_fields(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        t1 = tasks[0]
        assert t1.id == 1
        assert t1.title == "Create data model"
        assert "Widget dataclass" in t1.description
        assert t1.verification_steps == [
            "Unit tests pass for Widget dataclass",
            "All fields have correct types",
        ]
        assert t1.dependencies == []

    def test_task_2_fields(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        t2 = tasks[1]
        assert t2.id == 2
        assert t2.title == "Build parser"
        assert t2.verification_steps == [
            "Parser handles valid YAML",
            "Parser raises on invalid input",
            "Edge cases covered",
        ]
        assert t2.dependencies == [1]

    def test_task_3_fields(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        t3 = tasks[2]
        assert t3.id == 3
        assert t3.title == "Integration layer"
        assert "public API" in t3.description
        assert t3.verification_steps == ["End-to-end test passes"]
        assert t3.dependencies == [1, 2]


class TestNoDependenciesLine:
    """Plan with no Dependencies line defaults to empty list."""

    def test_dependencies_default_empty(self):
        tasks = parse_plan(PLAN_NO_DEPENDENCIES_LINE)
        assert len(tasks) == 1
        assert tasks[0].dependencies == []

    def test_other_fields_still_parsed(self):
        tasks = parse_plan(PLAN_NO_DEPENDENCIES_LINE)
        assert tasks[0].id == 1
        assert tasks[0].title == "Only task"
        assert "Do the thing" in tasks[0].description
        assert tasks[0].verification_steps == ["It works"]


class TestDependenciesNone:
    """Plan with 'Dependencies: none' returns empty list."""

    def test_dependencies_none_returns_empty(self):
        tasks = parse_plan(PLAN_DEPENDENCIES_NONE)
        assert tasks[0].dependencies == []


class TestDependenciesMultiple:
    """Plan with 'Dependencies: Task 1, Task 2' returns [1, 2]."""

    def test_multiple_dependencies(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        t3 = tasks[2]
        assert t3.dependencies == [1, 2]


class TestLenientHeading:
    """## Task N: works in addition to ### Task N:."""

    def test_two_hash_heading_parsed(self):
        tasks = parse_plan(PLAN_LENIENT_HEADINGS)
        assert len(tasks) == 1
        assert tasks[0].id == 1
        assert tasks[0].title == "Two-hash heading"
        assert "two hashes" in tasks[0].description.lower()


class TestMultiLineDescription:
    """Multi-line descriptions are preserved correctly."""

    def test_multiline_description_preserved(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        t2 = tasks[1]
        # The description should contain multiple lines of content
        assert "parser that reads widget configuration" in t2.description
        assert "multi-line description" in t2.description


class TestVerificationStepsExtracted:
    """Verification steps extracted as strings without '- [ ]' prefix."""

    def test_no_checkbox_prefix(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        for task in tasks:
            for step in task.verification_steps:
                assert not step.startswith("- [ ]")
                assert not step.startswith("[")

    def test_steps_are_clean_strings(self):
        tasks = parse_plan(WELL_FORMED_PLAN)
        t1 = tasks[0]
        assert t1.verification_steps[0] == "Unit tests pass for Widget dataclass"


class TestEmptyPlanRaisesError:
    """Empty plan (no tasks) raises PlanParseError."""

    def test_raises_plan_parse_error(self):
        with pytest.raises(PlanParseError):
            parse_plan(EMPTY_PLAN)

    def test_error_message_mentions_tasks(self):
        with pytest.raises(PlanParseError, match="No tasks found"):
            parse_plan(EMPTY_PLAN)

    def test_completely_empty_string(self):
        with pytest.raises(PlanParseError):
            parse_plan("")


class TestNoVerificationSection:
    """Task with only title and description — verification_steps is empty."""

    def test_verification_steps_empty(self):
        tasks = parse_plan(PLAN_NO_VERIFICATION)
        assert tasks[0].verification_steps == []

    def test_description_still_parsed(self):
        tasks = parse_plan(PLAN_NO_VERIFICATION)
        assert "title and description" in tasks[0].description


class TestMixedHeadings:
    """Mix of ## Task and ### Task headings in same plan."""

    def test_both_heading_levels_parsed(self):
        tasks = parse_plan(PLAN_MIXED_HEADINGS)
        assert len(tasks) == 2

    def test_first_task_is_two_hash(self):
        tasks = parse_plan(PLAN_MIXED_HEADINGS)
        assert tasks[0].id == 1
        assert tasks[0].title == "Two-hash task"

    def test_second_task_is_three_hash(self):
        tasks = parse_plan(PLAN_MIXED_HEADINGS)
        assert tasks[1].id == 2
        assert tasks[1].title == "Three-hash task"
        assert tasks[1].dependencies == [1]


class TestExtraContentBetweenTasks:
    """Extra content between tasks is not captured in wrong places."""

    def test_extra_content_not_in_task_2_description(self):
        tasks = parse_plan(PLAN_EXTRA_CONTENT)
        assert len(tasks) == 2
        assert "extra content" not in tasks[1].description

    def test_task_fields_correct(self):
        tasks = parse_plan(PLAN_EXTRA_CONTENT)
        assert tasks[0].id == 1
        assert tasks[0].title == "First"
        assert tasks[1].id == 2
        assert tasks[1].title == "Second"
        assert tasks[1].dependencies == [1]
