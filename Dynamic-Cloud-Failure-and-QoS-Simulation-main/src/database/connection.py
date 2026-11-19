"""Database connection management and transaction lifecycle handling for SQLite.

Provides safe, thread-isolated SQLite connections configured with foreign keys,
write-ahead logging (WAL), busy timeout handling, and atomic transactions.
"""

from __future__ import annotations
import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Generator, Optional, Any

logger = logging.getLogger(__name__)

# Default database directory and file location
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_DEFAULT_DB_FILE = os.path.join(_DEFAULT_DATA_DIR, "cloud_qos_simulation.db")


def get_default_database_path() -> str:
    """Return the active database file path, honoring environment overrides if set."""
    return os.environ.get("CLOUD_QOS_DB_PATH", _DEFAULT_DB_FILE)


def ensure_database_directory(db_path: str) -> None:
    """Ensure the parent directory for the database file exists."""
    if db_path != ":memory:":
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)


class DatabaseConnectionError(Exception):
    """Raised when establishing or operating a database connection fails."""
    pass


def create_connection(db_path: Optional[str] = None, timeout_seconds: float = 10.0) -> sqlite3.Connection:
    """Create and configure a fresh SQLite connection.

    Configures:
        - timeout: 10.0s for acquiring busy locks
        - PRAGMA foreign_keys = ON
        - PRAGMA journal_mode = WAL (file-based databases only)
        - PRAGMA busy_timeout = 5000 (ms)
        - row_factory = sqlite3.Row for dictionary-like column access

    Args:
        db_path: Optional path to the SQLite database file. Defaults to get_default_database_path().
        timeout_seconds: Busy timeout in seconds.

    Returns:
        Configured sqlite3.Connection instance.

    Raises:
        DatabaseConnectionError: If connection or pragma initialization fails.
    """
    path = db_path if db_path is not None else get_default_database_path()
    try:
        ensure_database_directory(path)
        conn = sqlite3.connect(path, timeout=timeout_seconds, check_same_thread=True)
        conn.row_factory = sqlite3.Row

        # Enforce foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")

        # Enable Write-Ahead Logging for file-backed databases to optimize concurrent read/write
        if path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")

        return conn
    except (sqlite3.Error, OSError) as exc:
        logger.error(f"Failed to connect to database at '{path}': {exc}")
        raise DatabaseConnectionError(f"Database connection failed for '{path}': {exc}") from exc


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager providing a database connection that closes automatically on exit.

    Yields:
        sqlite3.Connection
    """
    conn = create_connection(db_path)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except sqlite3.Error as exc:
            logger.warning(f"Error while closing database connection: {exc}")


@contextmanager
def transaction(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager executing a block within an atomic database transaction.

    Automatically commits on normal completion or rolls back if an exception is raised.

    Yields:
        sqlite3.Connection inside an active transaction.
    """
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
            logger.debug(f"Transaction rolled back due to: {exc}")
        except sqlite3.Error as rb_exc:
            logger.error(f"Rollback failed: {rb_exc}")
        raise
    finally:
        try:
            conn.close()
        except sqlite3.Error as exc:
            logger.warning(f"Error while closing transaction connection: {exc}")
