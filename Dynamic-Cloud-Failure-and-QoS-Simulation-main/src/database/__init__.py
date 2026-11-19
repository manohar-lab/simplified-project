"""Persistent storage and audit history management package for Phase 9.

Provides SQLite-based persistence for service states, simulation events,
periodic monitoring telemetry, reselection audit records, and manual overrides.
"""

from __future__ import annotations

from src.database.connection import (
    create_connection,
    get_connection,
    transaction,
    get_default_database_path,
    DatabaseConnectionError,
)
from src.database.schema import CURRENT_SCHEMA_VERSION
from src.database.migrations import (
    initialize_database,
    apply_migrations,
    get_current_schema_version,
    MigrationError,
)
from src.database.repositories import (
    ServiceStateRepository,
    SimulationEventRepository,
    MonitoringEventRepository,
    ReselectionAuditRepository,
    OverrideEventRepository,
    HistorySnapshotRepository,
    PersistenceManager,
)

__all__ = [
    "create_connection",
    "get_connection",
    "transaction",
    "get_default_database_path",
    "DatabaseConnectionError",
    "CURRENT_SCHEMA_VERSION",
    "initialize_database",
    "apply_migrations",
    "get_current_schema_version",
    "MigrationError",
    "ServiceStateRepository",
    "SimulationEventRepository",
    "MonitoringEventRepository",
    "ReselectionAuditRepository",
    "OverrideEventRepository",
    "HistorySnapshotRepository",
    "PersistenceManager",
]
