"""End-to-End Integration Scenario Tests for Phase 5 System Integration Audit.

Explicitly verifies Scenarios A through G as defined in Phase 5 specifications:
    Scenario A: Normal Operation (load registry, QoS evaluation, SLA filtering, select #1, verify explanation).
    Scenario B: Performance Degradation (minor latency spike, monitoring cycle, QoS recalc, hysteresis retains service).
    Scenario C: SLA Violation (hard SLA breached, immediate disqualification, emergency reselection, cooldown bypassed).
    Scenario D: Complete Outage (active service UNAVAILABLE, immediate failure detection, select best remaining, audit event logged).
    Scenario E: No Eligible Service (all services UNAVAILABLE or SLA-ineligible, returns None, safe state without fallback).
    Scenario F: Service Recovery (restore failed service, health restored, eligible again, hysteresis prevents unwanted bounceback).
    Scenario G: Manual Override (select eligible manually, reject SLA-violating, outage triggers emergency reselection, clear restores automatic).
"""

import pytest
from src.service_registry import get_default_services, CloudService
from src.failure_simulator import FailureSimulator
from src.qos_evaluator import QoSEvaluator, DEFAULT_WEIGHTS
from src.sla_config import SLAConfig, get_default_sla_config
from src.hysteresis_config import HysteresisConfig
from src.monitoring_config import MonitoringConfig
from src.monitoring_engine import (
    MonitoringEngine,
    EVENT_AUTOMATIC_RESELECTION,
    EVENT_SERVICE_RECOVERED,
    EVENT_MANUAL_OVERRIDE_TERMINATED,
    HEALTH_HEALTHY,
    HEALTH_DEGRADED,
    HEALTH_UNAVAILABLE,
    HEALTH_RECOVERED,
)
from src.recommendation_engine import RecommendationEngine
from src.explainability import (
    ReselectionAuditTrail,
    build_candidate_comparison_table,
    generate_detailed_reselection_explanation,
)
from src.override_manager import (
    MODE_AUTOMATIC,
    MODE_MANUAL,
    ManualOverrideManager,
    OVERRIDE_EVENT_ACTIVATED,
    OVERRIDE_EVENT_CLEARED,
    OVERRIDE_EVENT_REJECTED,
    OVERRIDE_EVENT_EMERGENCY_TERMINATED,
)


def _setup_system():
    sim = FailureSimulator(get_default_services())
    evaluator = QoSEvaluator()
    engine = RecommendationEngine(evaluator)
    sla = get_default_sla_config("Compute")
    hysteresis = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=2)
    override_mgr = ManualOverrideManager()
    monitoring = MonitoringEngine(
        evaluator=evaluator,
        recommendation_engine=engine,
        config=MonitoringConfig(interval_seconds=2.0, enabled=True),
        override_manager=override_mgr,
    )
    audit_trail = ReselectionAuditTrail()
    return sim, evaluator, engine, sla, hysteresis, override_mgr, monitoring, audit_trail


def test_scenario_a_normal_operation():
    """Scenario A: Normal Operation.
    - Load all registered services.
    - Evaluate QoS metrics.
    - Apply SLA filtering.
    - Select the highest-ranked eligible service.
    - Verify the explanation.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()
    services = sim.get_all_services()
    assert len(services) == 7

    rec = engine.recommend(
        services=services,
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        operating_mode=MODE_AUTOMATIC,
    )

    assert rec.has_eligible_service is True
    assert rec.selected_service is not None
    assert rec.selected_service.service_id == "SVC-C01"
    assert rec.decision_type == "INITIAL_SELECTION"
    assert len(rec.ranked_eligible) == 5
    assert len(rec.excluded_services) == 0

    explanation = generate_detailed_reselection_explanation(
        rec, eval_obj, DEFAULT_WEIGHTS, None, sim.get_services_by_category("Compute")
    )
    assert explanation["winner"].service_id == "SVC-C01"
    assert "Optimal" in explanation["reselection_trigger"] or "Baseline" in explanation["reselection_trigger"]
    assert rec.selected_scores.qos_score > 0.0


def test_scenario_b_performance_degradation():
    """Scenario B: Performance Degradation.
    - Select active service (SVC-C01).
    - Degrade active service slightly within SLA bounds.
    - Trigger monitoring.
    - Recalculate QoS scores.
    - Apply hysteresis: alternative does not exceed min_qos_delta -> retain current.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()

    # Initial selection
    rec0 = engine.recommend(
        sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=sla, hysteresis_config=hyst
    )
    active_id = rec0.selected_service.service_id
    assert active_id == "SVC-C01"

    # Degrade SVC-C01 latency by +15ms (45ms -> 60ms <= 150ms SLA)
    sim.inject_latency_spike(active_id, spike_ms=15.0)

    # Run monitoring cycle
    cycle = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id=active_id,
        current_step=1,
        last_switch_step=0,
        force=True,
        respect_interval=False,
    )

    # Hysteresis prevents unnecessary switching
    assert cycle.selected_service_id == "SVC-C01"
    assert cycle.reselection_triggered is False
    assert cycle.recommendation_result.decision_type == "RETAINED"


def test_scenario_c_sla_violation():
    """Scenario C: SLA Violation.
    - Active service violates hard SLA (latency spike > max_latency).
    - Immediate disqualification from candidate pool.
    - Immediate emergency reselection.
    - Cooldown does not block emergency reselection.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()
    active_id = "SVC-C01"

    # Inject severe latency spike exceeding 150ms SLA (45ms + 150ms = 195ms > 150ms)
    sim.inject_latency_spike(active_id, spike_ms=150.0)

    # Active cooldown from previous step
    cycle = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id=active_id,
        current_step=1,
        last_switch_step=1,  # Cooldown active!
        force=True,
        respect_interval=False,
    )

    assert cycle.reselection_triggered is True
    assert cycle.selected_service_id != active_id
    assert cycle.selected_service_id == "SVC-C02"
    assert cycle.recommendation_result.decision_type == "EMERGENCY_SLA_VIOLATION"
    assert any(s.service_id == active_id for s, r in cycle.recommendation_result.excluded_services)
    # Cooldown was active but overridden for emergency
    assert cycle.recommendation_result.cooldown_active is False or cycle.recommendation_result.is_emergency is True


def test_scenario_d_complete_outage():
    """Scenario D: Complete Outage.
    - Simulate outage of active service.
    - Immediate failure detection and exclusion.
    - Select best remaining eligible candidate.
    - Verify event history and audit logging.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()
    active_id = "SVC-C01"

    sim.simulate_outage(active_id)

    cycle = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id=active_id,
        current_step=1,
        last_switch_step=0,
        force=True,
        respect_interval=False,
    )

    assert cycle.reselection_triggered is True
    assert cycle.selected_service_id == "SVC-C02"
    assert cycle.recommendation_result.decision_type == "EMERGENCY_OUTAGE"
    assert cycle.unavailable_count >= 1

    events = mon.get_events_dataframe()
    assert not events.empty
    event_types = events["Event Type"].tolist()
    assert "SERVICE_UNAVAILABLE" in event_types
    assert "AUTOMATIC_RESELECTION" in event_types


def test_scenario_e_no_eligible_service():
    """Scenario E: No Eligible Service.
    - Make all services unavailable or SLA-ineligible.
    - Recommendation selection becomes None.
    - Correct status returned without unsafe fallback.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()

    # Take down all compute services
    for s in sim.get_services_by_category("Compute"):
        sim.simulate_outage(s.service_id)

    cycle = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C01",
        current_step=1,
        last_switch_step=0,
        force=True,
        respect_interval=False,
    )

    assert cycle.selected_service_id is None
    assert cycle.selected_service_name is None
    assert cycle.recommendation_result.has_eligible_service is False
    assert cycle.recommendation_result.selected_service is None
    assert cycle.recommendation_result.decision_type == "NO_ELIGIBLE_SERVICE"
    assert len(cycle.recommendation_result.ranked_eligible) == 0


def test_scenario_f_service_recovery():
    """Scenario F: Service Recovery.
    - Active service was switched to SVC-C02 due to outage on SVC-C01.
    - Restore SVC-C01 to baseline.
    - Verify health recovery is detected.
    - Hysteresis prevents unnecessary bounceback when improvement < min_qos_delta.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()

    # Step 1: SVC-C01 outage
    sim.simulate_outage("SVC-C01")
    mon.run_cycle(
        sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst,
        previously_selected_id="SVC-C01", force=True, respect_interval=False
    )

    # Step 2: Restore SVC-C01
    sim.restore_service("SVC-C01")

    # High hysteresis requirement (e.g. 10% delta) so SVC-C01 (~0.81) vs SVC-C02 (~0.79) does not bounce back
    strict_hyst = HysteresisConfig(min_qos_delta=0.10, cooldown_steps=0)
    cycle = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=strict_hyst,
        previously_selected_id="SVC-C02",
        current_step=2,
        last_switch_step=1,
        force=True,
        respect_interval=False,
    )

    # Recovery was observed in snapshots and logged
    recovered_snap = cycle.service_snapshots["SVC-C01"]
    assert recovered_snap.health_state == HEALTH_RECOVERED
    assert recovered_snap.sla_compliant is True

    # But active selection remains SVC-C02 to avoid flapping!
    assert cycle.selected_service_id == "SVC-C02"
    assert cycle.recommendation_result.decision_type == "RETAINED"


def test_scenario_g_manual_override_lifecycle():
    """Scenario G: Manual Override Lifecycle.
    - Select eligible service manually (SVC-C02).
    - Attempt to select an SLA-violating service (SVC-C03 with spike) -> rejected.
    - Simulate outage of manually selected service -> emergency reselection & termination.
    - Clear manual override -> automatic mode restored cleanly.
    """
    sim, eval_obj, engine, sla, hyst, ovr, mon, audit = _setup_system()

    # 1. Manual selection of eligible service
    ok, msg, val = ovr.request_manual_override(
        sim.get_all_services(), "Compute", "SVC-C02", sla, reason="Maintenance route"
    )
    assert ok is True
    assert ovr.mode == MODE_MANUAL

    rec1 = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        operating_mode=ovr.mode,
        manual_service_id=ovr.requested_service_id,
    )
    assert rec1.selected_service.service_id == "SVC-C02"
    assert rec1.decision_type == "MANUAL_OVERRIDE"

    # 2. Attempt to select an SLA-violating service
    sim.inject_latency_spike("SVC-C03", spike_ms=300.0)
    ok_bad, msg_bad, _ = ovr.request_manual_override(
        sim.get_all_services(), "Compute", "SVC-C03", sla
    )
    assert ok_bad is False
    assert "sla" in msg_bad.lower()
    # Mode remains pinned to previous manual service
    assert ovr.mode == MODE_MANUAL
    assert ovr.requested_service_id == "SVC-C02"

    # 3. Simulate outage on active manual service (SVC-C02)
    sim.simulate_outage("SVC-C02")
    cycle = mon.run_cycle(
        sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst,
        previously_selected_id="SVC-C02", force=True, respect_interval=False,
    )

    assert cycle.reselection_triggered is True
    assert cycle.selected_service_id == "SVC-C01"
    assert cycle.recommendation_result.override_terminated is True
    assert ovr.mode == MODE_AUTOMATIC
    assert ovr.requested_service_id is None

    # 4. Clear manual override when already in automatic is idempotent
    assert ovr.clear_override() is False
    assert ovr.mode == MODE_AUTOMATIC

