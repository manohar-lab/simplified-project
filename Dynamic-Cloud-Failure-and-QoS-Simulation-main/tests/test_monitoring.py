"""Automated deterministic test suite for Phase 3 Periodic Automatic Monitoring Engine."""

from __future__ import annotations

import copy
import math
from typing import Dict, List

import pytest

from src.analytics import (
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_RECOVERED,
    HEALTH_UNAVAILABLE,
    classify_service_health,
)
from src.failure_simulator import FailureSimulator
from src.hysteresis_config import DEFAULT_HYSTERESIS_CONFIG, HysteresisConfig
from src.monitoring_config import (
    DEFAULT_MONITORING_CONFIG,
    DEFAULT_MONITORING_INTERVAL_SECONDS,
    MonitoringConfig,
)
from src.monitoring_engine import (
    EVENT_AUTOMATIC_RESELECTION,
    EVENT_CYCLE_COMPLETED,
    EVENT_CYCLE_STARTED,
    EVENT_MONITORING_ERROR,
    EVENT_MONITORING_PAUSED,
    EVENT_MONITORING_RESUMED,
    EVENT_MONITORING_STARTED,
    EVENT_NO_ELIGIBLE_SERVICE,
    EVENT_SERVICE_HEALTH_CHANGED,
    EVENT_SERVICE_RECOVERED,
    EVENT_SERVICE_UNAVAILABLE,
    EVENT_SLA_VIOLATION_DETECTED,
    STATUS_ACTIVE,
    STATUS_PAUSED,
    MonitoringEngine,
)
from src.qos_evaluator import DEFAULT_WEIGHTS, QoSEvaluator
from src.recommendation_engine import RecommendationEngine
from src.service_registry import CloudService, compute_reference_bounds, get_default_services
from src.sla_config import SLAConfig


class FakeClock:
    """Deterministic injectable epoch clock for interval and cooldown testing."""

    def __init__(self, initial: float = 1_700_000_000.0):
        self.now = float(initial)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += float(seconds)
        return self.now


def _make_service(
    service_id: str,
    name: str,
    category: str = "Compute",
    latency: float = 100.0,
    cost: float = 0.20,
    availability: float = 99.5,
    reliability: float = 99.0,
    operational_status: str = "AVAILABLE",
) -> CloudService:
    """Create an isolated CloudService instance with matching baseline."""
    return CloudService(
        service_id=service_id,
        name=name,
        category=category,
        latency=latency,
        cost=cost,
        availability=availability,
        reliability=reliability,
        operational_status=operational_status,
        baseline={
            "latency": latency,
            "cost": cost,
            "availability": availability,
            "reliability": reliability,
            "operational_status": operational_status,
        },
    )


def _build_engine_and_services(
    services: List[CloudService] | None = None,
    config: MonitoringConfig | None = None,
    clock: FakeClock | None = None,
):
    svcs = services if services is not None else get_default_services()
    bounds = compute_reference_bounds(svcs)
    evaluator = QoSEvaluator(bounds)
    rec_engine = RecommendationEngine(evaluator)
    clk = clock or FakeClock()
    mon = MonitoringEngine(
        evaluator=evaluator,
        recommendation_engine=rec_engine,
        config=config,
        time_fn=clk,
    )
    return mon, svcs, clk, evaluator, rec_engine


# =========================================================================
# 1. Monitoring Engine Initialization
# =========================================================================
def test_monitoring_engine_initialization():
    """Verify MonitoringEngine initializes with defaults, timestamps, and start event."""
    clock = FakeClock(1_700_000_100.0)
    mon, svcs, _, _, _ = _build_engine_and_services(clock=clock)

    assert mon.is_active is True
    assert mon.status_label == STATUS_ACTIVE
    assert mon.cycle_count == 0
    assert mon.last_run_epoch is None
    assert mon.last_run_timestamp is None
    assert mon.next_expected_epoch == pytest.approx(1_700_000_100.0 + DEFAULT_MONITORING_INTERVAL_SECONDS)
    assert mon.config.interval_seconds == DEFAULT_MONITORING_INTERVAL_SECONDS
    assert len(mon.event_history) == 1
    assert mon.event_history[0].event_type == EVENT_MONITORING_STARTED
    assert mon.event_history[0].new_health_state == STATUS_ACTIVE


def test_monitoring_engine_initialized_paused():
    """Verify MonitoringEngine respects enabled=False on initialization."""
    clock = FakeClock(1_700_000_100.0)
    cfg = MonitoringConfig(interval_seconds=10.0, enabled=False)
    mon, _, _, _, _ = _build_engine_and_services(config=cfg, clock=clock)

    assert mon.is_active is False
    assert mon.status_label == STATUS_PAUSED
    assert mon.next_expected_epoch is None
    assert len(mon.event_history) == 1
    assert mon.event_history[0].event_type == EVENT_MONITORING_PAUSED


# =========================================================================
# 2. Monitoring Configuration Validation
# =========================================================================
def test_monitoring_configuration_validation():
    """Verify centralized MonitoringConfig validation rejects invalid inputs."""
    assert DEFAULT_MONITORING_CONFIG.interval_seconds == 5.0
    assert DEFAULT_MONITORING_CONFIG.enabled is True
    assert DEFAULT_MONITORING_CONFIG.max_history_events is None

    valid = MonitoringConfig(interval_seconds=3, enabled=False, max_history_events=100)
    assert isinstance(valid.interval_seconds, float)
    assert valid.to_dict() == {
        "interval_seconds": 3.0,
        "enabled": False,
        "max_history_events": 100,
    }

    with pytest.raises(ValueError):
        MonitoringConfig(interval_seconds=0.0)
    with pytest.raises(ValueError):
        MonitoringConfig(interval_seconds=-2.5)
    with pytest.raises(ValueError):
        MonitoringConfig(interval_seconds=math.nan)
    with pytest.raises(ValueError):
        MonitoringConfig(interval_seconds=math.inf)
    with pytest.raises(TypeError):
        MonitoringConfig(interval_seconds="5")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MonitoringConfig(interval_seconds=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MonitoringConfig(enabled="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        MonitoringConfig(max_history_events=0)
    with pytest.raises(TypeError):
        MonitoringConfig(max_history_events=True)  # type: ignore[arg-type]


# =========================================================================
# 3. Periodic Monitoring Execution with Deterministic Clock
# =========================================================================
def test_periodic_monitoring_execution_respects_interval():
    """Verify cycles execute only when interval has elapsed under respect_interval=True."""
    clock = FakeClock(1_700_000_000.0)
    cfg = MonitoringConfig(interval_seconds=5.0, enabled=True)
    mon, svcs, _, _, _ = _build_engine_and_services(config=cfg, clock=clock)

    res1 = mon.run_cycle(svcs, "Compute", respect_interval=True)
    assert res1.cycle_number == 1
    assert res1.status == STATUS_ACTIVE
    assert mon.last_run_epoch == 1_700_000_000.0
    assert mon.next_expected_epoch == 1_700_000_005.0

    # Advancing less than interval skips execution safely
    clock.advance(2.5)
    skipped = mon.run_cycle(svcs, "Compute", respect_interval=True)
    assert skipped.status == "SKIPPED_INTERVAL"
    assert mon.cycle_count == 1

    # Advancing past interval executes cycle #2
    clock.advance(2.5)
    res2 = mon.run_cycle(svcs, "Compute", respect_interval=True)
    assert res2.cycle_number == 2
    assert res2.status == STATUS_ACTIVE
    assert mon.last_run_epoch == 1_700_000_005.0
    assert mon.next_expected_epoch == 1_700_000_010.0


# =========================================================================
# 4. Correct Service Health Classification
# =========================================================================
def test_service_health_classification_states():
    """Verify canonical HEALTHY, DEGRADED, UNAVAILABLE, RECOVERED, and SLA consistency."""
    svc = _make_service("T1", "Test Compute", latency=100.0, cost=0.10, availability=99.5, reliability=99.0)
    strict_sla = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)

    assert classify_service_health(svc, sla_config=strict_sla) == HEALTH_HEALTHY

    # Exceeding baseline degrades service
    svc.latency = 130.0
    assert classify_service_health(svc, sla_config=strict_sla) == HEALTH_DEGRADED

    # Recovery from DEGRADED back to healthy baseline -> RECOVERED
    svc.latency = 100.0
    assert classify_service_health(svc, sla_config=strict_sla, previous_health=HEALTH_DEGRADED) == HEALTH_RECOVERED

    # Operational outage overrides metrics -> UNAVAILABLE
    svc.operational_status = "UNAVAILABLE"
    assert classify_service_health(svc, sla_config=strict_sla, previous_health=HEALTH_HEALTHY) == HEALTH_UNAVAILABLE

    # Recovery from UNAVAILABLE -> RECOVERED
    svc.operational_status = "AVAILABLE"
    assert classify_service_health(svc, sla_config=strict_sla, previous_health=HEALTH_UNAVAILABLE) == HEALTH_RECOVERED

    # Stricter SLA config marks otherwise-baseline metrics as DEGRADED (no conflicting definition)
    stricter_sla = SLAConfig(max_latency=80.0, min_availability=98.0, min_reliability=97.0)
    assert classify_service_health(svc, sla_config=stricter_sla) == HEALTH_DEGRADED

    # Corrupted / NaN metrics -> DEGRADED
    svc.latency = math.nan
    assert classify_service_health(svc, sla_config=strict_sla) == HEALTH_DEGRADED


# =========================================================================
# 5. Detection of SLA Violations
# =========================================================================
def test_detection_of_sla_violations():
    """Verify monitoring detects SLA violations accurately and emits SLA_VIOLATION_DETECTED."""
    s1 = _make_service("A1", "Fast Leader", latency=60.0, cost=0.05, availability=99.9, reliability=99.5)
    s2 = _make_service("A2", "Backup Node", latency=140.0, cost=0.15, availability=99.0, reliability=98.5)
    sla = SLAConfig(max_latency=200.0, min_availability=98.0, min_reliability=97.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    r1 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r1.selected_service_id == "A1"
    assert r1.sla_violating_count == 0

    # Inject latency spike violating SLA (latency 250 > 200) on A1
    clock.advance(5.0)
    s1.latency = 250.0
    r2 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)

    assert r2.sla_violating_count == 1
    assert r2.service_snapshots["A1"].health_state == HEALTH_DEGRADED
    assert r2.service_snapshots["A1"].sla_compliant is False
    assert r2.service_snapshots["A1"].is_eligible is False
    assert any("latency" in v.lower() for v in r2.service_snapshots["A1"].sla_violations)

    evt_types = [e.event_type for e in r2.events_emitted]
    assert EVENT_SLA_VIOLATION_DETECTED in evt_types
    assert EVENT_SERVICE_HEALTH_CHANGED in evt_types


# =========================================================================
# 6. Detection of Unavailable Services
# =========================================================================
def test_detection_of_unavailable_services():
    """Verify monitoring detects operational outages and logs SERVICE_UNAVAILABLE."""
    s1 = _make_service("A1", "Primary", latency=60.0)
    s2 = _make_service("A2", "Secondary", latency=120.0)
    sla = SLAConfig(max_latency=200.0, min_availability=95.0, min_reliability=95.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)

    clock.advance(5.0)
    s2.operational_status = "UNAVAILABLE"
    r2 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)

    assert r2.unavailable_count == 1
    assert r2.service_snapshots["A2"].health_state == HEALTH_UNAVAILABLE
    assert r2.service_snapshots["A2"].is_eligible is False
    assert r2.selected_service_id == "A1"
    assert r2.reselection_triggered is False  # Active A1 remained healthy

    unavail_events = [e for e in r2.events_emitted if e.event_type == EVENT_SERVICE_UNAVAILABLE]
    assert len(unavail_events) == 1
    assert unavail_events[0].service_id == "A2"
    assert unavail_events[0].new_health_state == HEALTH_UNAVAILABLE


# =========================================================================
# 7. Detection of Service Recovery
# =========================================================================
def test_detection_of_service_recovery():
    """Verify degraded/unavailable -> baseline healthy transitions emit SERVICE_RECOVERED."""
    s1 = _make_service("A1", "Primary", latency=70.0)
    s2 = _make_service("A2", "Secondary", latency=110.0)
    sla = SLAConfig(max_latency=200.0, min_availability=95.0, min_reliability=95.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)

    # Cause A2 outage
    clock.advance(5.0)
    s2.operational_status = "UNAVAILABLE"
    r_fail = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r_fail.service_snapshots["A2"].health_state == HEALTH_UNAVAILABLE

    # Restore A2 back to baseline
    clock.advance(5.0)
    s2.operational_status = "AVAILABLE"
    r_rec = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r_rec.service_snapshots["A2"].health_state == HEALTH_RECOVERED
    assert r_rec.healthy_count == 2
    assert r_rec.unavailable_count == 0
    rec_events = [e for e in r_rec.events_emitted if e.event_type == EVENT_SERVICE_RECOVERED]
    assert len(rec_events) == 1
    assert rec_events[0].service_id == "A2"

    # Subsequent unchanged cycle settles to HEALTHY with zero extra events
    clock.advance(5.0)
    r_steady = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r_steady.service_snapshots["A2"].health_state == HEALTH_HEALTHY
    assert r_steady.changes_detected is False
    assert r_steady.events_emitted == []


# =========================================================================
# 8. Automatic Reselection After Emergency Failure
# =========================================================================
def test_automatic_reselection_after_emergency_failure():
    """Verify outages and SLA breaches trigger immediate automatic reselection."""
    s1 = _make_service("A1", "Primary", latency=60.0, cost=0.10, availability=99.9, reliability=99.5)
    s2 = _make_service("A2", "Backup", latency=110.0, cost=0.15, availability=99.0, reliability=98.5)
    s3 = _make_service("A3", "Tertiary", latency=130.0, cost=0.18, availability=98.5, reliability=98.0)
    sla = SLAConfig(max_latency=180.0, min_availability=98.0, min_reliability=97.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2, s3])
    r1 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r1.selected_service_id == "A1"

    # Emergency 1: Active A1 suffers operational outage -> switches to A2
    clock.advance(5.0)
    s1.operational_status = "UNAVAILABLE"
    r2 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r2.reselection_triggered is True
    assert r2.selected_service_id == "A2"
    assert r2.recommendation_result.decision_type == "EMERGENCY_OUTAGE"
    assert any(e.event_type == EVENT_AUTOMATIC_RESELECTION and e.service_id == "A2" for e in r2.events_emitted)

    # Emergency 2: Active A2 suffers availability SLA breach -> switches to A3
    clock.advance(5.0)
    s2.availability = 94.0
    r3 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r3.reselection_triggered is True
    assert r3.selected_service_id == "A3"
    assert r3.recommendation_result.decision_type == "EMERGENCY_SLA_VIOLATION"
    assert any(e.event_type == EVENT_AUTOMATIC_RESELECTION and e.service_id == "A3" for e in r3.events_emitted)


# =========================================================================
# 9. No Eligible Service State & Later Recovery
# =========================================================================
def test_no_eligible_service_state_and_recovery():
    """Verify monitoring handles all services becoming ineligible cleanly and recovers later."""
    s1 = _make_service("A1", "Node 1", latency=70.0)
    s2 = _make_service("A2", "Node 2", latency=100.0)
    sla = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    r1 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r1.selected_service_id == "A1"

    # Both services breach SLA / fail
    clock.advance(5.0)
    s1.operational_status = "UNAVAILABLE"
    s2.latency = 300.0
    r2 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r2.selected_service_id is None
    assert r2.eligible_count == 0
    assert r2.reselection_triggered is True
    assert any(e.event_type == EVENT_NO_ELIGIBLE_SERVICE for e in r2.events_emitted)

    # Next cycle still empty -> no duplicate NO_ELIGIBLE_SERVICE event
    clock.advance(5.0)
    r3 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r3.selected_service_id is None
    assert r3.reselection_triggered is False
    assert r3.events_emitted == []

    # Recover s2 back into compliance -> automatic selection resumes cleanly
    clock.advance(5.0)
    s2.latency = 100.0
    r4 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r4.selected_service_id == "A2"
    assert r4.reselection_triggered is True
    assert any(e.event_type == EVENT_SERVICE_RECOVERED and e.service_id == "A2" for e in r4.events_emitted)
    assert any(e.event_type == EVENT_AUTOMATIC_RESELECTION and e.service_id == "A2" for e in r4.events_emitted)


# =========================================================================
# 10. Hysteresis Integration (Preventing Flapping)
# =========================================================================
def test_hysteresis_integration_prevents_minor_flapping():
    """Verify MonitoringEngine honors min_qos_delta and blocks marginal switching."""
    s1 = _make_service("A1", "Primary", latency=80.0, cost=0.10, availability=99.5, reliability=99.0)
    s2 = _make_service("A2", "RunnerUp", latency=85.0, cost=0.10, availability=99.5, reliability=99.0)
    sla = SLAConfig(max_latency=200.0, min_availability=95.0, min_reliability=95.0)
    hyst = HysteresisConfig(min_qos_delta=0.15, cooldown_steps=0, cooldown_seconds=0.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    r1 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r1.selected_service_id == "A1"

    # Slightly degrade A1 within SLA so A2 scores marginally better (< 0.15 gap)
    clock.advance(5.0)
    s1.latency = 95.0
    r2 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r2.selected_service_id == "A1"
    assert r2.reselection_triggered is False
    assert r2.recommendation_result.decision_type == "RETAINED"
    assert r2.recommendation_result.cooldown_active is False

    # Clear significant improvement >= min_qos_delta triggers controlled SWITCHED
    d1 = _make_service("D1", "Service One", latency=50.0, cost=0.10, availability=99.5, reliability=99.0)
    d2 = _make_service("D2", "Service Two", latency=150.0, cost=0.10, availability=99.5, reliability=99.0)
    mon2, svcs2, clock2, _, _ = _build_engine_and_services([d1, d2])
    init_res = mon2.run_cycle(svcs2, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert init_res.selected_service_id == "D1"

    clock2.advance(5.0)
    d1.latency = 170.0
    d2.latency = 20.0
    r_switch = mon2.run_cycle(svcs2, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r_switch.reselection_triggered is True
    assert r_switch.selected_service_id == "D2"
    assert r_switch.recommendation_result.decision_type == "SWITCHED"


# =========================================================================
# 11. Cooldown Does Not Block Emergency Reselection
# =========================================================================
def test_cooldown_does_not_block_emergency_reselection():
    """Verify cooldown periods suppress normal switching but NEVER delay outage/SLA reselection."""
    s1 = _make_service("A1", "Node1", latency=20.0, cost=0.10, availability=99.5, reliability=99.0)
    s2 = _make_service("A2", "Node2", latency=150.0, cost=0.10, availability=99.5, reliability=99.0)
    sla = SLAConfig(max_latency=200.0, min_availability=98.0, min_reliability=97.0)
    hyst = HysteresisConfig(min_qos_delta=0.01, cooldown_steps=5, cooldown_seconds=300.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    r1 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r1.selected_service_id == "A1"

    # Trigger an initial switch A1 -> A2 so MonitoringEngine records switch_step and switch_time
    clock.advance(5.0)
    s1.latency = 180.0
    s2.latency = 20.0
    r_first_switch = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r_first_switch.selected_service_id == "A2"
    assert r_first_switch.reselection_triggered is True

    # 5 seconds later (deep inside 300s / 5-step cooldown), A1 recovers strongly -> blocked by cooldown
    clock.advance(5.0)
    s1.latency = 10.0
    s2.latency = 180.0
    r_cooldown = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r_cooldown.selected_service_id == "A2"
    assert r_cooldown.recommendation_result.decision_type == "RETAINED"
    assert r_cooldown.recommendation_result.cooldown_active is True
    assert r_cooldown.reselection_triggered is False

    # 5 seconds later (still deep inside cooldown!), active A2 violates SLA -> immediate emergency switch!
    clock.advance(5.0)
    s2.latency = 260.0
    r_emergency = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r_emergency.selected_service_id == "A1"
    assert r_emergency.reselection_triggered is True
    assert r_emergency.recommendation_result.decision_type == "EMERGENCY_SLA_VIOLATION"


# =========================================================================
# 12 & 13. Duplicate Prevention & Unchanged Cycles Stay Silent
# =========================================================================
def test_duplicate_events_prevented_and_unchanged_cycles_silent():
    """Verify unchanged consecutive cycles produce zero events and overlap lock skips concurrent calls."""
    s1 = _make_service("A1", "Primary", latency=60.0)
    s2 = _make_service("A2", "Backup", latency=120.0)
    sla = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)

    mon, svcs, clock, _, _ = _build_engine_and_services([s1, s2])
    r1 = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert len(r1.events_emitted) == 2  # First cycle emits CYCLE_STARTED & CYCLE_COMPLETED
    hist_len_after_1 = len(mon.event_history)

    # Steady healthy cycles -> zero new events
    for _ in range(4):
        clock.advance(5.0)
        rk = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
        assert rk.changes_detected is False
        assert rk.events_emitted == []
    assert len(mon.event_history) == hist_len_after_1

    # Persistent outage on A2 emits UNAVAILABLE + SLA checks only on the transition cycle
    clock.advance(5.0)
    s2.operational_status = "UNAVAILABLE"
    r_outage = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert any(e.event_type == EVENT_SERVICE_UNAVAILABLE for e in r_outage.events_emitted)
    hist_len_after_outage = len(mon.event_history)

    clock.advance(5.0)
    r_still_down = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert r_still_down.events_emitted == []
    assert r_still_down.changes_detected is False
    assert len(mon.event_history) == hist_len_after_outage

    # Overlap guard prevents concurrent execution when lock is held
    acquired = mon._cycle_lock.acquire(blocking=False)
    assert acquired is True
    try:
        overlap_res = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla)
        assert overlap_res.status == "SKIPPED_OVERLAP"
        assert overlap_res.events_emitted == []
    finally:
        mon._cycle_lock.release()


# =========================================================================
# 14. Exception Handling Safety
# =========================================================================
def test_monitoring_exceptions_handled_safely(monkeypatch):
    """Verify MonitoringEngine catches internal failures gracefully, logs MONITORING_ERROR, and recovers."""
    s1 = _make_service("A1", "Primary", latency=60.0)
    mon, svcs, clock, _, rec_engine = _build_engine_and_services([s1])

    original_recommend = rec_engine.recommend

    def broken_recommend(*args, **kwargs):
        raise RuntimeError("Simulated monitoring reassessment crash")

    monkeypatch.setattr(rec_engine, "recommend", broken_recommend)

    r_err = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS)
    assert r_err.status == "ERROR"
    assert "Simulated monitoring reassessment crash" in (r_err.error_message or "")
    assert len(r_err.events_emitted) == 1
    assert r_err.events_emitted[0].event_type == EVENT_MONITORING_ERROR

    # Lock must have been released by finally block; restoring recommend allows clean recovery
    monkeypatch.setattr(rec_engine, "recommend", original_recommend)
    clock.advance(5.0)
    r_ok = mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS)
    assert r_ok.status == STATUS_ACTIVE
    assert r_ok.selected_service_id == "A1"


# =========================================================================
# 15. Monitoring Pause and Resume Behavior
# =========================================================================
def test_monitoring_pause_and_resume_behavior():
    """Verify pause stops scheduled cycles, force still works, and resume restores active schedule."""
    clock = FakeClock(1_700_000_000.0)
    mon, svcs, _, _, _ = _build_engine_and_services(clock=clock)

    mon.run_cycle(svcs, "Compute")
    assert mon.cycle_count == 1

    clock.advance(5.0)
    mon.pause()
    assert mon.is_active is False
    assert mon.status_label == STATUS_PAUSED
    assert mon.next_expected_epoch is None
    assert mon.event_history[-1].event_type == EVENT_MONITORING_PAUSED

    # Idempotent pause should not emit duplicate paused event
    event_len_paused = len(mon.event_history)
    mon.pause()
    assert len(mon.event_history) == event_len_paused

    # Scheduled call while paused does not increment cycle_count
    clock.advance(5.0)
    r_paused = mon.run_cycle(svcs, "Compute")
    assert r_paused.status == STATUS_PAUSED
    assert mon.cycle_count == 1

    # Forced inspect still works while paused
    r_forced = mon.run_cycle(svcs, "Compute", force=True)
    assert r_forced.cycle_number == 2
    assert mon.cycle_count == 2
    assert mon.next_expected_epoch is None

    # Resume restarts schedule cleanly
    clock.advance(5.0)
    mon.resume()
    assert mon.is_active is True
    assert mon.status_label == STATUS_ACTIVE
    assert mon.next_expected_epoch == pytest.approx(clock() + mon.config.interval_seconds)
    assert mon.event_history[-1].event_type == EVENT_MONITORING_RESUMED

    clock.advance(5.0)
    r_resumed = mon.run_cycle(svcs, "Compute")
    assert r_resumed.status == STATUS_ACTIVE
    assert r_resumed.cycle_number == 3


# =========================================================================
# 16. State Persistence Across Simulated Streamlit Reruns
# =========================================================================
def test_state_persistence_across_simulated_reruns():
    """Verify MonitoringEngine state, dataframe export, summary, and sync survive Streamlit reruns."""
    session_store: Dict[str, object] = {}
    clock = FakeClock(1_700_000_000.0)
    mon, svcs, _, _, _ = _build_engine_and_services(clock=clock)
    session_store["monitoring_engine"] = mon

    # Rerun 1: Baseline selection externally synced before inline monitoring
    sim_mon: MonitoringEngine = session_store["monitoring_engine"]  # type: ignore[assignment]
    r1 = sim_mon.run_cycle(svcs, "Compute", DEFAULT_WEIGHTS)
    initial_selected = r1.selected_service_id
    assert initial_selected is not None
    sim_mon.sync_external_selection("Compute", initial_selected, switch_step=0)

    # Rerun 2: Persistent instance remembers cycle_count, history, and status summary
    clock.advance(5.0)
    r2 = session_store["monitoring_engine"].run_cycle(svcs, "Compute", DEFAULT_WEIGHTS)  # type: ignore[attr-defined]
    assert r2.cycle_number == 2
    assert r2.changes_detected is False

    summary = sim_mon.get_status_summary()
    assert summary["status"] == STATUS_ACTIVE
    assert summary["cycle_count"] == 2
    assert summary["selected_service_id"] == initial_selected

    df_events = sim_mon.get_events_dataframe()
    assert not df_events.empty
    assert "Event Type" in df_events.columns
    assert "Monitoring Details / Reason" in df_events.columns


# =========================================================================
# 17 & 18 & 19. Integrated Phase 1, Phase 2, and FailureSimulator End-to-End
# =========================================================================
def test_end_to_end_failure_simulator_sla_hysteresis_and_restoration():
    """Verify Phase 1 SLA + Phase 2 Hysteresis + FailureSimulator work seamlessly with MonitoringEngine."""
    sim = FailureSimulator()
    all_svcs = sim.get_all_services()
    clock = FakeClock(1_700_000_000.0)
    mon, svcs, _, _, _ = _build_engine_and_services(services=all_svcs, clock=clock)

    compute_svcs = sim.get_services_by_category("Compute")
    sla = SLAConfig(max_latency=180.0, min_availability=98.0, min_reliability=97.0)
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=1, cooldown_seconds=0.0)

    # Cycle 1: Initial automatic SLA-compliant selection
    r1 = mon.run_cycle(all_svcs, "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    first_id = r1.selected_service_id
    assert first_id is not None
    assert r1.sla_violating_count == 0 or r1.service_snapshots[first_id].sla_compliant is True
    baseline_latency_snapshot = sim.get_service(first_id).baseline["latency"]  # type: ignore[union-attr]

    # Inject small latency spike that stays within SLA -> baseline stays immutable
    clock.advance(5.0)
    sim.inject_latency_spike(first_id, 20.0)
    r2 = mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    # Monitoring never modifies immutable baseline
    assert sim.get_service(first_id).baseline["latency"] == baseline_latency_snapshot  # type: ignore[union-attr]

    # Inject severe outage on current active service -> immediate emergency reselection
    active_before_outage = r2.selected_service_id
    assert active_before_outage is not None
    clock.advance(5.0)
    sim.simulate_outage(active_before_outage)
    r3 = mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r3.reselection_triggered is True
    assert r3.selected_service_id is not None
    assert r3.selected_service_id != active_before_outage

    # Restore failed service -> detected as RECOVERED, does not fail or reset baseline
    clock.advance(5.0)
    sim.restore_service(active_before_outage)
    r4 = mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r4.service_snapshots[active_before_outage].health_state == HEALTH_RECOVERED
    assert sim.get_service(active_before_outage).baseline["latency"] == sim.get_service(active_before_outage).latency  # type: ignore[union-attr]

    # Verify reset returns everything cleanly without crashing
    sim.reset_simulation()
    mon.reset(clear_events=False)
    assert mon.cycle_count == 0
    r5 = mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst)
    assert r5.healthy_count == len(compute_svcs)
