"""Shared test fixtures."""

import pytest


@pytest.fixture
def tmp_base_dir(tmp_path):
    """Isolated base directory. No test touches real ~/.dev-workflow."""
    base = tmp_path / "dev-workflow"
    base.mkdir()
    return base


@pytest.fixture
def store(tmp_base_dir):
    """Fresh Store with auto-created schema."""
    from dev_workflow.store import Store

    db_path = tmp_base_dir / "store.db"
    s = Store(db_path)
    yield s
    s.close()
