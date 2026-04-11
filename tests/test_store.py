"""Tests for the SQLite store."""

import sqlite3

import pytest

from dev_workflow.store import Store


class TestStoreInit:
    def test_creates_database_file(self, tmp_base_dir):
        db_path = tmp_base_dir / "store.db"
        store = Store(db_path)
        assert db_path.exists()
        store.close()

    def test_creates_parent_directories(self, tmp_path):
        db_path = tmp_path / "deep" / "nested" / "store.db"
        store = Store(db_path)
        assert db_path.exists()
        store.close()

    def test_creates_all_tables(self, store):
        conn = sqlite3.connect(store._db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        # Filter out sqlite_sequence (auto-created by AUTOINCREMENT)
        tables = sorted(
            row[0] for row in cursor.fetchall() if row[0] != "sqlite_sequence"
        )
        conn.close()
        assert tables == [
            "artifacts",
            "checkpoints",
            "decisions",
            "schema_version",
            "spaces",
            "tasks",
            "verifications",
        ]

    def test_schema_version_set(self, store):
        conn = sqlite3.connect(store._db_path)
        cursor = conn.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()[0]
        conn.close()
        assert version == 1

    def test_wal_mode_enabled(self, store):
        conn = sqlite3.connect(store._db_path)
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_reopen_existing_db(self, tmp_base_dir):
        db_path = tmp_base_dir / "store.db"
        store1 = Store(db_path)
        store1.close()
        store2 = Store(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()[0]
        conn.close()
        store2.close()
        assert version == 1
