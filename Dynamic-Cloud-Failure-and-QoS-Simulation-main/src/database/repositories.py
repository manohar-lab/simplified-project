"""Repository pattern implementations for Phase 9 SQLite persistence.

Encapsulates all SQL queries using parameterized statements, type validation,
and atomic transaction safety for service states, simulation events, monitoring
telemetry, reselection records, and manual override audit trails.
"""

from __future__ import annotations
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from src.service_registry import CloudService
from src.database.connection import get_connection, transaction
from src.failure_simulator import SimulationEvent
from src.monitoring_engine import MonitoringEvent
from src.explainability import ReselectionRecord
from src.override_manager import OverrideTransitionEvent
from src.analytics import SimulationSnapshot, ServiceStateRecord

logger = logging.getLogger(__name__)


# =========================================================================
# Service State Repository
# =========================================================================

class ServiceStateRepository:
    """Manages persistence and state recovery for candidate cloud services."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_service_state(self, service: CloudService) -> None:
        """Persist or update the live state of a single service."""
        b = service.baseline or {}
        now_ts = datetime.now().isoformat()
        sql = """
        INSERT INTO service_states (
            service_id, name, category, latency, cost, availability, reliability,
            operational_status, baseline_latency, baseline_cost, baseline_availability,
            baseline_reliability, baseline_operational_status, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(service_id) DO UPDATE SET
            name = excluded.name,
            category = excluded.category,
            latency = excluded.latency,
            cost = excluded.cost,
            availability = excluded.availability,
            reliability = excluded.reliability,
            operational_status = excluded.operational_status,
            last_updated = excluded.last_updated;
        """
        with transaction(self.db_path) as conn:
            conn.execute(
                sql,
                (
                    service.service_id,
                    service.name,
                    service.category,
                    float(service.latency),
                    float(service.cost),
                    float(service.availability),
                    float(service.reliability),
                    str(service.operational_status),
                    float(b.get("latency", service.latency)),
                    float(b.get("cost", service.cost)),
                    float(b.get("availability", service.availability)),
                    float(b.get("reliability", service.reliability)),
                    str(b.get("operational_status", service.operational_status)),
                    now_ts,
                ),
            )

    def save_all_service_states(self, services: List[CloudService]) -> None:
        """Persist or update a collection of services within a single atomic transaction."""
        now_ts = datetime.now().isoformat()
        sql = """
        INSERT INTO service_states (
            service_id, name, category, latency, cost, availability, reliability,
            operational_status, baseline_latency, baseline_cost, baseline_availability,
            baseline_reliability, baseline_operational_status, last_updated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(service_id) DO UPDATE SET
            name = excluded.name,
            category = excluded.category,
            latency = excluded.latency,
            cost = excluded.cost,
            availability = excluded.availability,
            reliability = excluded.reliability,
            operational_status = excluded.operational_status,
            last_updated = excluded.last_updated;
        """
        rows = []
        for s in services:
            b = s.baseline or {}
            rows.append((
                s.service_id,
                s.name,
                s.category,
                float(s.latency),
                float(s.cost),
                float(s.availability),
                float(s.reliability),
                str(s.operational_status),
                float(b.get("latency", s.latency)),
                float(b.get("cost", s.cost)),
                float(b.get("availability", s.availability)),
                float(b.get("reliability", s.reliability)),
                str(b.get("operational_status", s.operational_status)),
                now_ts,
            ))
        with transaction(self.db_path) as conn:
            conn.executemany(sql, rows)

    def get_service_state(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the persisted state of a single service by ID."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM service_states WHERE service_id = ?;",
                (service_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_all_service_states(self) -> List[Dict[str, Any]]:
        """Retrieve all persisted service states."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM service_states ORDER BY service_id ASC;")
            return [dict(r) for r in cur.fetchall()]

    def count_services(self) -> int:
        """Count the number of persisted service records."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) AS total FROM service_states;")
            return int(cur.fetchone()["total"])

    def load_services_with_restored_state(
        self, default_services: List[CloudService]
    ) -> Tuple[List[CloudService], bool]:
        """Hydrate default services with persisted runtime states while preserving baseline bounds.

        If persisted records exist in the database, the live metrics (latency, cost,
        availability, reliability, operational_status) of the default services are
        updated from the database. The immutable 'baseline' dictionary of each service
        is strictly preserved to ensure normalization bounds and restore operations
        remain anchored to the baseline.

        Returns:
            Tuple of (hydrated_services_list, was_restored_bool).
        """
        persisted = self.get_all_service_states()
        if not persisted:
            # First launch: save default baseline services into the database
            self.save_all_service_states(default_services)
            return default_services, False

        state_by_id = {row["service_id"]: row for row in persisted}
        restored_services: List[CloudService] = []
        any_mutations_restored = False

        for svc in default_services:
            if svc.service_id in state_by_id:
                rec = state_by_id[svc.service_id]
                # Update runtime state
                svc.latency = float(rec["latency"])
                svc.cost = float(rec["cost"])
                svc.availability = float(rec["availability"])
                svc.reliability = float(rec["reliability"])
                svc.operational_status = str(rec["operational_status"])

                # Check if current state differs from immutable baseline
                b = svc.baseline
                if (
                    svc.latency != b["latency"]
                    or svc.cost != b["cost"]
                    or svc.availability != b["availability"]
                    or svc.reliability != b["reliability"]
                    or svc.operational_status != b["operational_status"]
                ):
                    any_mutations_restored = True

            restored_services.append(svc)

        return restored_services, any_mutations_restored

    def reset_service_to_baseline(self, service_id: str, baseline_service: CloudService) -> None:
        """Reset a single service in the database back to its baseline metrics."""
        self.save_service_state(baseline_service)

    def reset_all_services_to_baseline(self, default_services: List[CloudService]) -> None:
        """Reset all services in the database back to their original baseline metrics."""
        self.save_all_service_states(default_services)


# =========================================================================
# Simulation Event Repository
# =========================================================================

class SimulationEventRepository:
    """Manages append-only persistence of fault injection and restoration events."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_event(
        self,
        event: SimulationEvent,
        injected_latency_change: float = 0.0,
        injected_availability_change: float = 0.0,
        previous_state: Optional[Dict[str, Any]] = None,
        resulting_state: Optional[Dict[str, Any]] = None,
        epoch_time: Optional[float] = None,
    ) -> int:
        """Insert a simulation mutation or restoration event."""
        now_epoch = epoch_time if epoch_time is not None else datetime.now().timestamp()
        prev_json = json.dumps(previous_state) if previous_state else None
        res_json = json.dumps(resulting_state) if resulting_state else None
        sql = """
        INSERT INTO simulation_events (
            action, service_id, service_name, injected_latency_change,
            injected_availability_change, previous_state, resulting_state,
            details, timestamp, epoch_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                sql,
                (
                    event.action,
                    event.service_id,
                    event.service_name,
                    float(injected_latency_change),
                    float(injected_availability_change),
                    prev_json,
                    res_json,
                    event.details,
                    event.timestamp,
                    now_epoch,
                ),
            )
            return cursor.lastrowid

    def get_events(self, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Retrieve recent simulation events in reverse chronological order."""
        with get_connection(self.db_path) as conn:
            sql = "SELECT * FROM simulation_events ORDER BY id DESC"
            if limit is not None and limit > 0:
                sql += f" LIMIT {int(limit)}"
            sql += ";"
            cur = conn.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def get_all_events_chronological(self) -> List[SimulationEvent]:
        """Retrieve all events in forward chronological order as SimulationEvent instances."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM simulation_events ORDER BY id ASC;")
            events = []
            for r in cur.fetchall():
                ev = SimulationEvent(
                    action=r["action"],
                    service_id=r["service_id"],
                    service_name=r["service_name"],
                    details=r["details"],
                    timestamp=r["timestamp"],
                )
                events.append(ev)
            return events

    def count_events(self) -> int:
        """Count the total number of simulation events recorded."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) AS total FROM simulation_events;")
            return int(cur.fetchone()["total"])

    def clear_events(self, confirmed: bool = False) -> bool:
        """Destructive history purge requiring explicit confirmation."""
        if not confirmed:
            logger.warning("Simulation event deletion rejected: explicit confirmation missing.")
            return False
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM simulation_events;")
        return True


# =========================================================================
# Monitoring Event Repository
# =========================================================================

class MonitoringEventRepository:
    """Manages append-only persistence of periodic surveillance events."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_event(
        self,
        event: MonitoringEvent,
        health_state: Optional[str] = None,
        sla_compliant: Optional[bool] = None,
        qos_score: Optional[float] = None,
    ) -> int:
        """Persist a single monitoring event."""
        sla_int = 1 if sla_compliant is True else (0 if sla_compliant is False else None)
        sql = """
        INSERT INTO monitoring_events (
            sequence_number, cycle_number, event_type, service_id, service_name,
            category, previous_health_state, new_health_state, health_state,
            sla_compliant, qos_score, reason, timestamp, epoch_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                sql,
                (
                    int(event.sequence_number),
                    int(event.cycle_number),
                    event.event_type,
                    event.service_id,
                    event.service_name,
                    event.category,
                    event.previous_health_state,
                    event.new_health_state,
                    health_state or event.new_health_state,
                    sla_int,
                    qos_score,
                    event.reason,
                    event.timestamp,
                    float(event.epoch_time),
                ),
            )
            return cursor.lastrowid

    def save_events_batch(self, events: List[MonitoringEvent]) -> None:
        """Persist a batch of monitoring events in a single transaction."""
        if not events:
            return
        sql = """
        INSERT INTO monitoring_events (
            sequence_number, cycle_number, event_type, service_id, service_name,
            category, previous_health_state, new_health_state, health_state,
            sla_compliant, qos_score, reason, timestamp, epoch_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        rows = [
            (
                int(e.sequence_number),
                int(e.cycle_number),
                e.event_type,
                e.service_id,
                e.service_name,
                e.category,
                e.previous_health_state,
                e.new_health_state,
                e.new_health_state,
                None,
                None,
                e.reason,
                e.timestamp,
                float(e.epoch_time),
            )
            for e in events
        ]
        with transaction(self.db_path) as conn:
            conn.executemany(sql, rows)

    def get_events(self, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Retrieve recent monitoring events in reverse chronological order."""
        with get_connection(self.db_path) as conn:
            sql = "SELECT * FROM monitoring_events ORDER BY id DESC"
            if limit is not None and limit > 0:
                sql += f" LIMIT {int(limit)}"
            sql += ";"
            cur = conn.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def get_all_events_chronological(self) -> List[MonitoringEvent]:
        """Retrieve all monitoring events in forward chronological order."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM monitoring_events ORDER BY id ASC;")
            result = []
            for r in cur.fetchall():
                evt = MonitoringEvent(
                    sequence_number=r["sequence_number"],
                    event_type=r["event_type"],
                    service_id=r["service_id"],
                    service_name=r["service_name"],
                    timestamp=r["timestamp"],
                    epoch_time=r["epoch_time"],
                    previous_health_state=r["previous_health_state"],
                    new_health_state=r["new_health_state"],
                    reason=r["reason"],
                    category=r["category"],
                    cycle_number=r["cycle_number"],
                )
                result.append(evt)
            return result

    def count_events(self) -> int:
        """Count the total number of monitoring events recorded."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) AS total FROM monitoring_events;")
            return int(cur.fetchone()["total"])

    def clear_events(self, confirmed: bool = False) -> bool:
        """Destructive monitoring history purge requiring explicit confirmation."""
        if not confirmed:
            logger.warning("Monitoring event deletion rejected: explicit confirmation missing.")
            return False
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM monitoring_events;")
        return True


# =========================================================================
# Reselection Audit Repository
# =========================================================================

class ReselectionAuditRepository:
    """Manages persistence of reselection decisions and explainability logs."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_record(self, record: ReselectionRecord) -> int:
        """Persist a single reselection audit record."""
        sql = """
        INSERT INTO reselection_records (
            sequence_number, timestamp, trigger_event, prev_service_id, prev_service_name,
            prev_qos_score, prev_health_status, new_service_id, new_service_name,
            new_qos_score, new_health_status, runner_up_id, runner_up_name,
            runner_up_qos_score, reselection_reason, detailed_explanation,
            q_diff, lat_diff, avail_diff, rel_diff, cost_diff, decision_type,
            qos_improvement, hysteresis_threshold, cooldown_active, operating_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with transaction(self.db_path) as conn:
            cur = conn.execute(
                sql,
                (
                    int(record.sequence_number),
                    record.timestamp,
                    record.trigger_event,
                    record.prev_service_id,
                    record.prev_service_name,
                    record.prev_qos_score,
                    record.prev_health_status,
                    record.new_service_id,
                    record.new_service_name,
                    float(record.new_qos_score),
                    record.new_health_status,
                    record.runner_up_id,
                    record.runner_up_name,
                    record.runner_up_qos_score,
                    record.reselection_reason,
                    record.detailed_explanation,
                    record.q_diff,
                    record.lat_diff,
                    record.avail_diff,
                    record.rel_diff,
                    record.cost_diff,
                    record.decision_type,
                    float(record.qos_improvement),
                    float(record.hysteresis_threshold),
                    1 if record.cooldown_active else 0,
                    record.operating_mode,
                ),
            )
            return cur.lastrowid

    def get_records(self, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Retrieve recent reselection audit records in reverse chronological order."""
        with get_connection(self.db_path) as conn:
            sql = "SELECT * FROM reselection_records ORDER BY id DESC"
            if limit is not None and limit > 0:
                sql += f" LIMIT {int(limit)}"
            sql += ";"
            cur = conn.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def get_all_records_chronological(self) -> List[ReselectionRecord]:
        """Retrieve all reselection records in forward chronological order."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM reselection_records ORDER BY id ASC;")
            records = []
            for r in cur.fetchall():
                rec = ReselectionRecord(
                    sequence_number=r["sequence_number"],
                    timestamp=r["timestamp"],
                    trigger_event=r["trigger_event"],
                    prev_service_id=r["prev_service_id"],
                    prev_service_name=r["prev_service_name"],
                    prev_qos_score=r["prev_qos_score"],
                    prev_health_status=r["prev_health_status"],
                    new_service_id=r["new_service_id"],
                    new_service_name=r["new_service_name"],
                    new_qos_score=r["new_qos_score"],
                    new_health_status=r["new_health_status"],
                    runner_up_id=r["runner_up_id"],
                    runner_up_name=r["runner_up_name"],
                    runner_up_qos_score=r["runner_up_qos_score"],
                    reselection_reason=r["reselection_reason"],
                    detailed_explanation=r["detailed_explanation"],
                    q_diff=r["q_diff"],
                    lat_diff=r["lat_diff"],
                    avail_diff=r["avail_diff"],
                    rel_diff=r["rel_diff"],
                    cost_diff=r["cost_diff"],
                    decision_type=r["decision_type"],
                    qos_improvement=r["qos_improvement"],
                    hysteresis_threshold=r["hysteresis_threshold"],
                    cooldown_active=bool(r["cooldown_active"]),
                    operating_mode=r["operating_mode"],
                )
                records.append(rec)
            return records

    def count_records(self) -> int:
        """Count the total number of reselection records persisted."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) AS total FROM reselection_records;")
            return int(cur.fetchone()["total"])

    def clear_records(self, confirmed: bool = False) -> bool:
        """Destructive reselection history purge requiring explicit confirmation."""
        if not confirmed:
            logger.warning("Reselection record deletion rejected: explicit confirmation missing.")
            return False
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM reselection_records;")
        return True


# =========================================================================
# Manual Override Event Repository
# =========================================================================

class OverrideEventRepository:
    """Manages append-only persistence of operator manual override events."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_event(self, event: OverrideTransitionEvent) -> int:
        """Persist a manual override transition event."""
        sql = """
        INSERT INTO override_events (
            sequence_number, timestamp, epoch_time, event_type,
            operating_mode, requested_service_id, selected_service_id,
            category, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with transaction(self.db_path) as conn:
            cur = conn.execute(
                sql,
                (
                    int(event.sequence_number),
                    event.timestamp,
                    float(event.epoch_time),
                    event.event_type,
                    event.operating_mode,
                    event.requested_service_id,
                    event.selected_service_id,
                    event.category,
                    event.reason,
                ),
            )
            return cur.lastrowid

    def get_events(self, limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Retrieve recent manual override events in reverse chronological order."""
        with get_connection(self.db_path) as conn:
            sql = "SELECT * FROM override_events ORDER BY id DESC"
            if limit is not None and limit > 0:
                sql += f" LIMIT {int(limit)}"
            sql += ";"
            cur = conn.execute(sql)
            return [dict(r) for r in cur.fetchall()]

    def get_all_events_chronological(self) -> List[OverrideTransitionEvent]:
        """Retrieve all manual override events in forward chronological order."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM override_events ORDER BY id ASC;")
            events = []
            for r in cur.fetchall():
                ev = OverrideTransitionEvent(
                    sequence_number=r["sequence_number"],
                    timestamp=r["timestamp"],
                    epoch_time=r["epoch_time"],
                    event_type=r["event_type"],
                    operating_mode=r["operating_mode"],
                    requested_service_id=r["requested_service_id"],
                    selected_service_id=r["selected_service_id"],
                    category=r["category"],
                    reason=r["reason"],
                )
                events.append(ev)
            return events

    def count_events(self) -> int:
        """Count the total number of manual override events recorded."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) AS total FROM override_events;")
            return int(cur.fetchone()["total"])

    def clear_events(self, confirmed: bool = False) -> bool:
        """Destructive override history purge requiring explicit confirmation."""
        if not confirmed:
            logger.warning("Override event deletion rejected: explicit confirmation missing.")
            return False
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM override_events;")
        return True


# =========================================================================
# History Snapshot Repository (HistoryTracker)
# =========================================================================

class HistorySnapshotRepository:
    """Manages persistence of multi-service simulation snapshots across evaluation steps."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def save_snapshot(self, snapshot: SimulationSnapshot) -> int:
        """Persist a single multi-service simulation snapshot."""
        services_dict = {sid: asdict(rec) for sid, rec in snapshot.services.items()}
        sql = """
        INSERT INTO history_snapshots (
            step, timestamp, action, target_service_id, target_service_name,
            message, services_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with transaction(self.db_path) as conn:
            cur = conn.execute(
                sql,
                (
                    int(snapshot.step),
                    snapshot.timestamp,
                    snapshot.action,
                    snapshot.target_service_id,
                    snapshot.target_service_name,
                    snapshot.message,
                    json.dumps(services_dict),
                ),
            )
            return cur.lastrowid

    def get_all_snapshots(self) -> List[SimulationSnapshot]:
        """Retrieve all persisted snapshots in forward step sequence."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM history_snapshots ORDER BY step ASC;")
            snapshots = []
            for r in cur.fetchall():
                srv_data = json.loads(r["services_json"])
                services_map = {
                    sid: ServiceStateRecord(**srec) for sid, srec in srv_data.items()
                }
                snap = SimulationSnapshot(
                    step=r["step"],
                    timestamp=r["timestamp"],
                    action=r["action"],
                    target_service_id=r["target_service_id"],
                    target_service_name=r["target_service_name"],
                    message=r["message"],
                    services=services_map,
                )
                snapshots.append(snap)
            return snapshots

    def count_snapshots(self) -> int:
        """Count total persisted snapshots."""
        with get_connection(self.db_path) as conn:
            cur = conn.execute("SELECT COUNT(*) AS total FROM history_snapshots;")
            return int(cur.fetchone()["total"])

    def clear_snapshots(self, confirmed: bool = False) -> bool:
        """Destructive snapshot purge requiring explicit confirmation."""
        if not confirmed:
            logger.warning("Snapshot deletion rejected: explicit confirmation missing.")
            return False
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM history_snapshots;")
        return True


# =========================================================================
# Unified Persistence Manager
# =========================================================================

class PersistenceManager:
    """Unified entry point orchestrating all database repositories and lifecycle operations."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.services = ServiceStateRepository(db_path)
        self.simulation_events = SimulationEventRepository(db_path)
        self.monitoring_events = MonitoringEventRepository(db_path)
        self.reselection = ReselectionAuditRepository(db_path)
        self.override_events = OverrideEventRepository(db_path)
        self.snapshots = HistorySnapshotRepository(db_path)

    def initialize(self) -> int:
        """Initialize database, apply schema migrations, and return active version."""
        from src.database.migrations import initialize_database
        return initialize_database(self.db_path)

    def get_summary(self) -> Dict[str, Any]:
        """Generate high-level persistence telemetry for dashboard and verification."""
        try:
            from src.database.migrations import get_current_schema_version
            v = get_current_schema_version(self.db_path)
            return {
                "connected": True,
                "db_path": self.db_path or "default",
                "schema_version": v,
                "total_services": self.services.count_services(),
                "total_simulation_events": self.simulation_events.count_events(),
                "total_monitoring_events": self.monitoring_events.count_events(),
                "total_reselection_records": self.reselection.count_records(),
                "total_override_events": self.override_events.count_events(),
                "total_snapshots": self.snapshots.count_snapshots(),
            }
        except Exception as exc:
            logger.error(f"Error fetching persistence summary: {exc}")
            return {
                "connected": False,
                "error": str(exc),
                "db_path": self.db_path or "default",
            }
