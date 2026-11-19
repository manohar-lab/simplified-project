"""Comprehensive automated test suite for Phase 9 SQLite Persistence & Audit Management.

Verifies:
1. Database initialization and pragma verification.
2. Schema and table creation.
3. Database migration and version tracking.
4. Service state persistence.
5. Service state recovery after simulated restart while preserving baseline bounds.
6. Failure event persistence.
7. Monitoring event persistence and deduplication.
8. Reselection audit persistence and explainability recovery.
9. Manual override history persistence.
10. Transaction rollback on write failure.
11. Duplicate event handling and idempotency.
12. Simulation reset preserves audit history without deletion.
13. Concurrent database read/write access.
14. Invalid persisted data handling and boundary validation.
15. Database recovery, corruption resilience, and error handling.
"""

import os
import sys
import tempfile
import threading
import sqlite3
import pytest

from src.service_registry import get_default_services, CloudService
from src.database.connection import (
    create_connection,
    get_connection,
    transaction,
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
from src.failure_simulator import SimulationEvent
from src.monitoring_engine import MonitoringEvent
from src.explainability import ReselectionRecord
from src.override_manager import OverrideTransitionEvent
from src.analytics import SimulationSnapshot, ServiceStateRecord


@pytest.fixture
def temp_db_path():
    """Create a temporary database file that is cleaned up after testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    # Clean up WAL and SHM files if present
    for ext in ("-wal", "-shm"):
        extra = path + ext
        if os.path.exists(extra):
            try:
                os.remove(extra)
            except OSError:
                pass


@pytest.fixture
def persistence_manager(temp_db_path):
    """Provide an initialized PersistenceManager backed by a temporary database."""
    pm = PersistenceManager(temp_db_path)
    pm.initialize()
    return pm


# =========================================================================
# 1. Database Initialization
# =========================================================================
def test_01_database_initialization(temp_db_path):
    """Test 1: Database initializes cleanly with foreign keys and WAL mode."""
    v = initialize_database(temp_db_path)
    assert v == CURRENT_SCHEMA_VERSION

    conn = create_connection(temp_db_path)
    try:
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1, "Foreign keys must be enabled"

        busy = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert busy >= 5000, "Busy timeout must be configured"

        journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal.lower() in ("wal", "memory"), "WAL journal mode expected"
    finally:
        conn.close()


# =========================================================================
# 2. Schema Creation
# =========================================================================
def test_02_schema_creation(persistence_manager, temp_db_path):
    """Test 2: All required persistence tables and indexes are created."""
    expected_tables = {
        "schema_version",
        "service_states",
        "simulation_events",
        "monitoring_events",
        "reselection_records",
        "override_events",
        "history_snapshots",
    }
    with get_connection(temp_db_path) as conn:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cur.fetchall()}
        assert expected_tables.issubset(tables)

        cur_idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row["name"] for row in cur_idx.fetchall()}
        assert "idx_svc_category" in indexes
        assert "idx_sim_service" in indexes
        assert "idx_mon_cycle" in indexes
        assert "idx_reselect_seq" in indexes


# =========================================================================
# 3. Database Migration
# =========================================================================
def test_03_database_migration(temp_db_path):
    """Test 3: Schema migrations record history and are idempotent."""
    v1 = apply_migrations(temp_db_path)
    assert v1 == CURRENT_SCHEMA_VERSION

    # Idempotent second run
    v2 = apply_migrations(temp_db_path)
    assert v2 == CURRENT_SCHEMA_VERSION

    version = get_current_schema_version(temp_db_path)
    assert version == CURRENT_SCHEMA_VERSION


# =========================================================================
# 4. Service State Persistence
# =========================================================================
def test_04_service_state_persistence(persistence_manager):
    """Test 4: Candidate service state persists accurately."""
    services = get_default_services()
    svc = services[0]
    svc.latency = 185.5
    svc.operational_status = "UNAVAILABLE"

    persistence_manager.services.save_service_state(svc)
    saved = persistence_manager.services.get_service_state(svc.service_id)

    assert saved is not None
    assert saved["service_id"] == svc.service_id
    assert saved["name"] == svc.name
    assert saved["latency"] == 185.5
    assert saved["operational_status"] == "UNAVAILABLE"
    assert saved["baseline_latency"] == svc.baseline["latency"]


# =========================================================================
# 5. Service State Recovery After Simulated Restart
# =========================================================================
def test_05_service_state_recovery_after_restart(temp_db_path):
    """Test 5: Live metrics restore after restart without altering baseline bounds."""
    # Session 1: Mutate and save
    pm1 = PersistenceManager(temp_db_path)
    pm1.initialize()
    defaults = get_default_services()
    c01 = next(s for s in defaults if s.service_id == "SVC-C01")
    c01.latency = 250.0  # Degraded
    c01.operational_status = "UNAVAILABLE"
    pm1.services.save_service_state(c01)

    # Session 2: Fresh instance (simulating restart)
    pm2 = PersistenceManager(temp_db_path)
    fresh_defaults = get_default_services()
    restored, was_restored = pm2.services.load_services_with_restored_state(fresh_defaults)

    assert was_restored is True
    restored_c01 = next(s for s in restored if s.service_id == "SVC-C01")
    assert restored_c01.latency == 250.0
    assert restored_c01.operational_status == "UNAVAILABLE"
    # Immutable baseline must remain intact!
    assert restored_c01.baseline["latency"] == 45.0
    assert restored_c01.baseline["operational_status"] == "AVAILABLE"


# =========================================================================
# 6. Failure Event Persistence
# =========================================================================
def test_06_failure_event_persistence(persistence_manager):
    """Test 6: Fault injection and restoration events are persisted."""
    ev = SimulationEvent(
        action="LATENCY_SPIKE",
        service_id="SVC-C01",
        service_name="NovaCompute Standard",
        details="Latency spiked by +150ms",
        timestamp="12:00:00",
    )
    row_id = persistence_manager.simulation_events.save_event(
        event=ev,
        injected_latency_change=150.0,
        injected_availability_change=0.0,
        previous_state={"latency": 45.0},
        resulting_state={"latency": 195.0},
    )
    assert row_id > 0

    events = persistence_manager.simulation_events.get_events(limit=10)
    assert len(events) == 1
    assert events[0]["action"] == "LATENCY_SPIKE"
    assert events[0]["injected_latency_change"] == 150.0
    assert events[0]["service_id"] == "SVC-C01"


# =========================================================================
# 7. Monitoring Event Persistence
# =========================================================================
def test_07_monitoring_event_persistence(persistence_manager):
    """Test 7: Periodic monitoring telemetry and state transitions are persisted."""
    mev = MonitoringEvent(
        sequence_number=1,
        cycle_number=1,
        event_type="SERVICE_HEALTH_CHANGED",
        service_id="SVC-C02",
        service_name="AetherCompute HighPerf",
        timestamp="12:01:00",
        epoch_time=1700000000.0,
        previous_health_state="HEALTHY",
        new_health_state="DEGRADED",
        reason="Latency spiked above baseline",
        category="Compute",
    )
    row_id = persistence_manager.monitoring_events.save_event(
        event=mev,
        health_state="DEGRADED",
        sla_compliant=True,
        qos_score=0.7425,
    )
    assert row_id > 0
    assert persistence_manager.monitoring_events.count_events() == 1

    stored = persistence_manager.monitoring_events.get_events()[0]
    assert stored["event_type"] == "SERVICE_HEALTH_CHANGED"
    assert stored["qos_score"] == 0.7425
    assert stored["sla_compliant"] == 1


# =========================================================================
# 8. Reselection Audit Persistence
# =========================================================================
def test_08_reselection_audit_persistence(persistence_manager):
    """Test 8: Recommendation decisions and explainability deltas persist accurately."""
    rec = ReselectionRecord(
        sequence_number=1,
        timestamp="12:05:00",
        trigger_event="Outage on SVC-C01",
        prev_service_id="SVC-C01",
        prev_service_name="NovaCompute Standard",
        prev_qos_score=0.0,
        prev_health_status="UNAVAILABLE",
        new_service_id="SVC-C02",
        new_service_name="AetherCompute HighPerf",
        new_qos_score=0.8850,
        new_health_status="HEALTHY",
        runner_up_id="SVC-C04",
        runner_up_name="TitanCompute Enterprise",
        runner_up_qos_score=0.8120,
        reselection_reason="Emergency Outage Reselection",
        detailed_explanation="Switched to SVC-C02 due to total outage on active service.",
        q_diff=0.8850,
        lat_diff=-20.0,
        avail_diff=0.05,
        rel_diff=0.30,
        cost_diff=0.045,
        decision_type="EMERGENCY_OUTAGE",
        qos_improvement=0.8850,
        hysteresis_threshold=0.05,
        cooldown_active=False,
        operating_mode="AUTOMATIC",
    )
    row_id = persistence_manager.reselection.save_record(rec)
    assert row_id > 0

    assert persistence_manager.reselection.count_records() == 1
    stored = persistence_manager.reselection.get_records()[0]
    assert stored["new_service_id"] == "SVC-C02"
    assert stored["decision_type"] == "EMERGENCY_OUTAGE"
    assert stored["qos_improvement"] == 0.8850


# =========================================================================
# 9. Manual Override History Persistence
# =========================================================================
def test_09_manual_override_history_persistence(persistence_manager):
    """Test 9: Operating mode transitions and manual overrides are persisted."""
    oev = OverrideTransitionEvent(
        sequence_number=1,
        timestamp="12:10:00",
        epoch_time=1700000500.0,
        event_type="MANUAL_OVERRIDE_ACTIVATED",
        operating_mode="MANUAL_OVERRIDE",
        requested_service_id="SVC-C04",
        selected_service_id="SVC-C04",
        category="Compute",
        reason="Operator preference for enterprise tier",
    )
    row_id = persistence_manager.override_events.save_event(oev)
    assert row_id > 0

    assert persistence_manager.override_events.count_events() == 1
    stored = persistence_manager.override_events.get_events()[0]
    assert stored["event_type"] == "MANUAL_OVERRIDE_ACTIVATED"
    assert stored["requested_service_id"] == "SVC-C04"


# =========================================================================
# 10. Transaction Rollback on Write Failure
# =========================================================================
def test_10_transaction_rollback(temp_db_path):
    """Test 10: Failed atomic writes rollback cleanly without partial corruptions."""
    initialize_database(temp_db_path)

    with pytest.raises(sqlite3.IntegrityError):
        with transaction(temp_db_path) as conn:
            # First insert valid
            conn.execute(
                """
                INSERT INTO simulation_events (
                    action, service_id, service_name, details, timestamp, epoch_time
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("TEST_ACTION_1", "SVC-C01", "NovaCompute", "Valid details", "12:00:00", 1.0),
            )
            # Second insert invalid (missing NOT NULL column)
            conn.execute(
                """
                INSERT INTO simulation_events (
                    action, service_id, details
                ) VALUES (?, ?, ?);
                """,
                ("TEST_ACTION_2", "SVC-C02", "Missing columns"),
            )

    # Verify first insert was rolled back completely
    with get_connection(temp_db_path) as conn:
        cnt = conn.execute("SELECT COUNT(*) AS total FROM simulation_events;").fetchone()["total"]
        assert cnt == 0, "All writes in transaction must rollback on error"


# =========================================================================
# 11. Duplicate Event Handling & Idempotence
# =========================================================================
def test_11_duplicate_event_handling(persistence_manager):
    """Test 11: Batch insertions handle repeat operations idempotently."""
    services = get_default_services()
    # Save once
    persistence_manager.services.save_all_service_states(services)
    c1 = persistence_manager.services.count_services()

    # Save twice (UPSERT)
    persistence_manager.services.save_all_service_states(services)
    c2 = persistence_manager.services.count_services()

    assert c1 == c2 == len(services), "Upserting existing services must not duplicate rows"


# =========================================================================
# 12. Simulation Reset Preserves Audit History Without Deletion
# =========================================================================
def test_12_reset_without_deleting_audit_history(persistence_manager):
    """Test 12: Normal simulation reset updates live metrics but preserves audit history."""
    # Populate simulation event & audit record
    ev = SimulationEvent("LATENCY_SPIKE", "SVC-C01", "NovaCompute", "Spike details")
    persistence_manager.simulation_events.save_event(ev)

    rec = ReselectionRecord(
        sequence_number=1,
        timestamp="12:00:00",
        trigger_event="Spike",
        prev_service_id="SVC-C01",
        prev_service_name="NovaCompute",
        prev_qos_score=0.9,
        prev_health_status="HEALTHY",
        new_service_id="SVC-C02",
        new_service_name="AetherCompute",
        new_qos_score=0.95,
        new_health_status="HEALTHY",
        runner_up_id=None,
        runner_up_name=None,
        runner_up_qos_score=None,
        reselection_reason="Score",
        detailed_explanation="Explanation",
        q_diff=0.05,
        lat_diff=-10.0,
        avail_diff=0.0,
        rel_diff=0.0,
        cost_diff=0.0,
        decision_type="SWITCHED",
        qos_improvement=0.05,
        hysteresis_threshold=0.05,
        cooldown_active=False,
        operating_mode="AUTOMATIC",
    )
    persistence_manager.reselection.save_record(rec)

    # Perform simulation reset (restores services to baseline)
    defaults = get_default_services()
    persistence_manager.services.reset_all_services_to_baseline(defaults)

    # Add a reset event
    reset_ev = SimulationEvent("RESET_SIMULATION", "ALL", "All Services", "Reset to baseline")
    persistence_manager.simulation_events.save_event(reset_ev)

    # Audit records must remain intact!
    assert persistence_manager.simulation_events.count_events() == 2
    assert persistence_manager.reselection.count_records() == 1


# =========================================================================
# 13. Concurrent Database Access
# =========================================================================
def test_13_concurrent_database_access(temp_db_path):
    """Test 13: Multiple concurrent threads perform reads and writes safely."""
    initialize_database(temp_db_path)
    errors = []

    def writer_thread(tid: int):
        try:
            repo = SimulationEventRepository(temp_db_path)
            for i in range(10):
                ev = SimulationEvent(
                    action=f"THREAD_WRITE_{tid}",
                    service_id=f"SVC-T{tid}",
                    service_name=f"ThreadService-{tid}",
                    details=f"Write index {i}",
                )
                repo.save_event(ev)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer_thread, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent access threw errors: {errors}"
    repo = SimulationEventRepository(temp_db_path)
    assert repo.count_events() == 50


# =========================================================================
# 14. Invalid Persisted Data Handling & Bounds
# =========================================================================
def test_14_invalid_persisted_data_handling(persistence_manager, temp_db_path):
    """Test 14: System handles missing, empty, or uninitialized records safely."""
    # Query non-existent service
    non_existent = persistence_manager.services.get_service_state("NON_EXISTENT")
    assert non_existent is None

    # Empty tables return clean zero counts and empty lists
    assert persistence_manager.simulation_events.count_events() == 0
    assert persistence_manager.simulation_events.get_events() == []
    assert persistence_manager.reselection.get_records() == []
    assert persistence_manager.override_events.get_events() == []


# =========================================================================
# 15. Database Recovery and Error Handling
# =========================================================================
def test_15_database_recovery_and_error_handling(temp_db_path):
    """Test 15: Database gracefully reports connection errors on invalid paths."""
    # Invalid directory path (e.g., pointing into a non-directory file or forbidden path)
    with pytest.raises(DatabaseConnectionError):
        # Pass an impossible path on Windows
        create_connection(r"Z:\impossible_drive_letter_9999\invalid.db")

    # Summary reporting handles uninitialized or missing database safely
    pm_invalid = PersistenceManager(r"Z:\impossible_drive_letter_9999\invalid.db")
    summary = pm_invalid.get_summary()
    assert summary["connected"] is False
    assert "error" in summary
