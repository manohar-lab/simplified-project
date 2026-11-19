"""Global pytest fixtures and test environment configuration.

Ensures every test runs with an isolated, temporary SQLite database to prevent
cross-test state contamination and preserve deterministic test assertions.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path, monkeypatch):
    """Provide a clean, isolated SQLite test database path for every test invocation."""
    test_db = str(tmp_path / "test_cloud_qos.db")
    monkeypatch.setenv("CLOUD_QOS_DB_PATH", test_db)
    yield test_db
