"""Database migration and schema versioning management.

Ensures the SQLite database is automatically initialized on first launch and
applies incremental versioned migrations safely within atomic transactions.
"""

from __future__ import annotations
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Callable

from src.database.connection import transaction, get_connection
from src.database.schema import (
    CURRENT_SCHEMA_VERSION,
    CREATE_SCHEMA_VERSION_TABLE,
    ALL_TABLE_CREATION_STATEMENTS,
    CREATE_INDEXES,
)

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Raised when a schema migration fails."""
    pass


def get_current_schema_version(db_path: Optional[str] = None) -> int:
    """Retrieve the current applied schema version from the database.

    Returns:
        Integer version (0 if the database is uninitialized).
    """
    with get_connection(db_path) as conn:
        try:
            # Check if schema_version table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
            )
            if cursor.fetchone() is None:
                return 0

            cur = conn.execute("SELECT MAX(version) AS max_v FROM schema_version;")
            row = cur.fetchone()
            if row and row["max_v"] is not None:
                return int(row["max_v"])
            return 0
        except sqlite3.Error as exc:
            logger.error(f"Failed to query schema version: {exc}")
            return 0


def _migration_v1_initial_schema(conn: sqlite3.Connection) -> None:
    """Migration 1: Create all initial tables and indexes."""
    for stmt in ALL_TABLE_CREATION_STATEMENTS:
        conn.execute(stmt)
    for idx_stmt in CREATE_INDEXES:
        conn.execute(idx_stmt)


# Ordered list of migrations: (version, description, migration_callable)
MIGRATIONS: List[Tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
    (1, "Initial schema: service_states, simulation_events, monitoring_events, reselection_records, override_events, history_snapshots", _migration_v1_initial_schema),
]


def apply_migrations(db_path: Optional[str] = None) -> int:
    """Execute all pending schema migrations up to CURRENT_SCHEMA_VERSION.

    Args:
        db_path: Optional database path.

    Returns:
        The updated schema version after migrations.

    Raises:
        MigrationError: If executing any migration fails.
    """
    with transaction(db_path) as conn:
        try:
            # 1. Ensure schema_version table itself exists
            conn.execute(CREATE_SCHEMA_VERSION_TABLE)

            # 2. Determine current applied version
            cur = conn.execute("SELECT MAX(version) AS max_v FROM schema_version;")
            row = cur.fetchone()
            current_v = int(row["max_v"]) if row and row["max_v"] is not None else 0

            # 3. Apply pending migrations
            for version, description, fn in MIGRATIONS:
                if version > current_v:
                    logger.info(f"Applying database migration v{version}: {description}")
                    fn(conn)
                    conn.execute(
                        """
                        INSERT INTO schema_version (version, applied_at, description)
                        VALUES (?, ?, ?);
                        """,
                        (version, datetime.now().isoformat(), description),
                    )
                    current_v = version

            return current_v
        except Exception as exc:
            logger.error(f"Migration failed: {exc}")
            raise MigrationError(f"Database migration failed: {exc}") from exc


def initialize_database(db_path: Optional[str] = None) -> int:
    """Initialize database and ensure all schema migrations are applied.

    Convenience wrapper for application startup.
    """
    return apply_migrations(db_path)
