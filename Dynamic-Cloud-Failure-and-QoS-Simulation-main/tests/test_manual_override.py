"""Comprehensive Phase 4 backend tests for Operating Mode & Manual Service Override.

Verifies:
    1.  Automatic mode selects best eligible service.
    2.  Manual mode selects requested eligible service.
    3.  Unknown service IDs are rejected cleanly.
    4.  Services from another category are rejected cleanly.
    5.  Unavailable services cannot be manually selected.
    6.  SLA-violating services cannot be manually selected.
    7.  Clearing override restores automatic mode cleanly.
    8.  Manual override never bypasses hard SLA or availability checks.
    9.  Emergency outage overrides and terminates manual selection immediately.
    10. Emergency SLA violation overrides and terminates manual selection immediately.
    11. Periodic monitoring continues in manual mode.
    12. Recovered services do not cause unwanted switching out of valid manual override.
    13. Hysteresis still works in automatic mode.
    14. Duplicate events are prevented.
    15. End-to-end integration with Phase 1 SLA, Phase 2 Hysteresis, Phase 3 Monitoring,
        Explainability Audit Trail, and Failure Simulator.
"""

from src.service_registry import get_default_services
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
    OVERRIDE_EVENT_ACTIVATED,
    OVERRIDE_EVENT_CLEARED,
    OVERRIDE_EVENT_REJECTED,
    OVERRIDE_EVENT_EMERGENCY_TERMINATED,
    OVERRIDE_EVENT_AUTO_RESTORED,
    ManualOverrideManager,
    validate_manual_override_request,
)


def _make_engine():
    return RecommendationEngine(QoSEvaluator())


def test_01_automatic_mode_selects_best_eligible_service():
    """Test 1: Automatic mode independently picks highest-scoring eligible service."""
    sim = FailureSimulator(get_default_services())
    engine = _make_engine()
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)

    res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        operating_mode=MODE_AUTOMATIC,
    )

    assert res.operating_mode == MODE_AUTOMATIC
    assert res.manual_override_active is False
    assert res.selected_service is not None
    assert res.selected_service.service_id == "SVC-C01"
    assert res.decision_type == "INITIAL_SELECTION"
    assert res.automatic_best_service is not None
    assert res.automatic_best_service.service_id == "SVC-C01"


def test_02_manual_mode_selects_requested_eligible_service():
    """Test 2: Manual override forces an eligible lower-ranked service cleanly."""
    sim = FailureSimulator(get_default_services())
    engine = _make_engine()
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.15, cooldown_steps=5)
    mgr = ManualOverrideManager()

    accepted, msg, validation = mgr.request_manual_override(
        services=sim.get_all_services(),
        category="Compute",
        requested_service_id="SVC-C02",
        sla_config=sla,
        reason="Operator pinning AetherCompute",
    )
    assert accepted is True
    assert validation.is_valid is True
    assert mgr.mode == MODE_MANUAL
    assert mgr.requested_service_id == "SVC-C02"

    # Even with strict hysteresis/cooldown from SVC-C01, manual override selects SVC-C02
    res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C01",
        current_step=1,
        last_switch_step=1,
        operating_mode=mgr.mode,
        manual_service_id=mgr.requested_service_id,
        manual_override_reason=mgr.reason,
    )

    assert res.operating_mode == MODE_MANUAL
    assert res.manual_override_active is True
    assert res.override_terminated is False
    assert res.decision_type == "MANUAL_OVERRIDE"
    assert res.selected_service is not None
    assert res.selected_service.service_id == "SVC-C02"
    assert res.automatic_best_service.service_id == "SVC-C01"


def test_03_unknown_service_id_is_rejected():
    """Test 3: Unknown service IDs are rejected explicitly without changing mode."""
    sim = FailureSimulator(get_default_services())
    sla = get_default_sla_config("Compute")
    mgr = ManualOverrideManager()

    accepted, msg, val = mgr.request_manual_override(
        services=sim.get_all_services(),
        category="Compute",
        requested_service_id="SVC-DOES-NOT-EXIST",
        sla_config=sla,
    )

    assert accepted is False
    assert val.is_valid is False
    assert "does not exist" in msg.lower()
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.requested_service_id is None
    assert len(mgr.event_history) == 1
    assert mgr.event_history[0].event_type == OVERRIDE_EVENT_REJECTED


def test_04_cross_category_service_is_rejected():
    """Test 4: Requesting a Storage service while Compute is active is rejected."""
    sim = FailureSimulator(get_default_services())
    sla = get_default_sla_config("Compute")
    mgr = ManualOverrideManager()

    accepted, msg, val = mgr.request_manual_override(
        services=sim.get_all_services(),
        category="Compute",
        requested_service_id="SVC-S01",
        sla_config=sla,
    )

    assert accepted is False
    assert val.is_valid is False
    assert "category" in msg.lower()
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.event_history[-1].event_type == OVERRIDE_EVENT_REJECTED


def test_05_unavailable_service_cannot_be_manually_selected():
    """Test 5: Outage-marked (UNAVAILABLE) services are rejected from manual override."""
    sim = FailureSimulator(get_default_services())
    sim.simulate_outage("SVC-C02")
    sla = get_default_sla_config("Compute")
    mgr = ManualOverrideManager()

    accepted, msg, val = mgr.request_manual_override(
        services=sim.get_all_services(),
        category="Compute",
        requested_service_id="SVC-C02",
        sla_config=sla,
    )

    assert accepted is False
    assert val.is_valid is False
    assert "unavailable" in msg.lower()
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.event_history[-1].event_type == OVERRIDE_EVENT_REJECTED


def test_06_sla_violating_service_cannot_be_manually_selected():
    """Test 6: Services violating latency, availability, or reliability SLA are rejected."""
    sla = SLAConfig(max_latency=100.0, min_availability=99.0, min_reliability=99.0)

    # Latency SLA violation
    sim_lat = FailureSimulator(get_default_services())
    sim_lat.inject_latency_spike("SVC-C02", spike_ms=200.0)
    mgr_lat = ManualOverrideManager()
    ok_lat, msg_lat, val_lat = mgr_lat.request_manual_override(
        sim_lat.get_all_services(), "Compute", "SVC-C02", sla
    )
    assert ok_lat is False
    assert val_lat.sla_violations
    assert "sla" in msg_lat.lower()

    # Availability SLA violation
    sim_avail = FailureSimulator(get_default_services())
    sim_avail.reduce_availability("SVC-C02", reduction_percentage=10.0)
    mgr_avail = ManualOverrideManager()
    ok_avail, _, val_avail = mgr_avail.request_manual_override(
        sim_avail.get_all_services(), "Compute", "SVC-C02", sla
    )
    assert ok_avail is False
    assert val_avail.sla_violations

    # Reliability SLA violation (direct service mutation in simulator copy)
    sim_rel = FailureSimulator(get_default_services())
    sim_rel.get_service("SVC-C02").reliability = 95.0
    mgr_rel = ManualOverrideManager()
    ok_rel, _, val_rel = mgr_rel.request_manual_override(
        sim_rel.get_all_services(), "Compute", "SVC-C02", sla
    )
    assert ok_rel is False
    assert val_rel.sla_violations


def test_07_clearing_override_restores_automatic_mode_cleanly():
    """Test 7: Clearing manual override returns to AUTOMATIC and restores #1 choice."""
    sim = FailureSimulator(get_default_services())
    engine = _make_engine()
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.20, cooldown_steps=0)
    mgr = ManualOverrideManager()

    ok, _, _ = mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla)
    assert ok is True

    manual_res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        operating_mode=mgr.mode,
        manual_service_id=mgr.requested_service_id,
    )
    assert manual_res.selected_service.service_id == "SVC-C02"

    cleared = mgr.clear_override(reason="User returned to automatic management")
    assert cleared is True
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.requested_service_id is None
    assert any(e.event_type == OVERRIDE_EVENT_CLEARED for e in mgr.event_history)
    assert any(e.event_type == OVERRIDE_EVENT_AUTO_RESTORED for e in mgr.event_history)

    # Fresh automatic recommendation with previously_selected_id=None restores #1 service
    auto_res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id=None,
        operating_mode=mgr.mode,
    )
    assert auto_res.operating_mode == MODE_AUTOMATIC
    assert auto_res.manual_override_active is False
    assert auto_res.selected_service.service_id == "SVC-C01"


def test_08_manual_override_never_bypasses_sla_constraints_even_directly():
    """Test 8: RecommendationEngine itself rejects manual selection violating SLA."""
    sim = FailureSimulator(get_default_services())
    sim.inject_latency_spike("SVC-C03", spike_ms=400.0)
    engine = _make_engine()
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)

    # Bypass ManualOverrideManager and call RecommendationEngine directly with invalid service
    res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C03",
        operating_mode=MODE_MANUAL,
        manual_service_id="SVC-C03",
    )

    assert res.selected_service is None or res.selected_service.service_id != "SVC-C03"
    assert res.override_terminated is True
    assert res.operating_mode == MODE_AUTOMATIC
    assert res.manual_override_active is False
    assert res.selected_service.service_id == "SVC-C01"


def test_09_emergency_outage_immediately_terminates_manual_override():
    """Test 9: Outage on manually selected service triggers immediate emergency takeover."""
    sim = FailureSimulator(get_default_services())
    engine = _make_engine()
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    mgr = ManualOverrideManager()

    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla)[0]

    # Inject outage on overridden service
    sim.simulate_outage("SVC-C02")

    res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C02",
        operating_mode=mgr.mode,
        manual_service_id=mgr.requested_service_id,
    )

    assert res.override_terminated is True
    assert res.decision_type == "EMERGENCY_OUTAGE"
    assert res.operating_mode == MODE_AUTOMATIC
    assert res.manual_override_active is False
    assert res.selected_service is not None
    assert res.selected_service.service_id == "SVC-C01"

    recorded = mgr.handle_emergency_termination(
        failed_service_id="SVC-C02",
        replacement_service_id=res.selected_service.service_id,
        reason=res.override_termination_reason,
        category="Compute",
    )
    assert recorded is True
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.requested_service_id is None
    types = [e.event_type for e in mgr.event_history]
    assert OVERRIDE_EVENT_EMERGENCY_TERMINATED in types
    assert OVERRIDE_EVENT_AUTO_RESTORED in types


def test_10_emergency_sla_violation_immediately_terminates_manual_override():
    """Test 10: SLA breach on manually selected service immediately terminates override."""
    sim = FailureSimulator(get_default_services())
    sla = SLAConfig(max_latency=100.0, min_availability=99.0, min_reliability=99.0)
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    mgr = ManualOverrideManager()
    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla)[0]

    # Inject severe latency breach on SVC-C02 (25ms + 250ms = 275ms > 100ms)
    sim.inject_latency_spike("SVC-C02", spike_ms=250.0)

    mon = MonitoringEngine(
        evaluator=QoSEvaluator(),
        recommendation_engine=_make_engine(),
        config=MonitoringConfig(interval_seconds=2.0),
        override_manager=mgr,
    )
    cycle = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C02",
        current_step=1,
        last_switch_step=0,
        force=True,
        respect_interval=False,
    )

    assert cycle.reselection_triggered is True
    assert cycle.selected_service_id == "SVC-C01"
    assert cycle.recommendation_result.decision_type == "EMERGENCY_SLA_VIOLATION"
    assert cycle.recommendation_result.override_terminated is True
    assert mgr.mode == MODE_AUTOMATIC
    assert any(e.event_type == EVENT_MANUAL_OVERRIDE_TERMINATED for e in mon.event_history)
    assert any(e.event_type == EVENT_AUTOMATIC_RESELECTION for e in mon.event_history)


def test_11_periodic_monitoring_continues_in_manual_mode():
    """Test 11: Monitoring keeps tracking health snapshots & violations during manual mode."""
    sim = FailureSimulator(get_default_services())
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    mgr = ManualOverrideManager()
    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla)[0]

    mon = MonitoringEngine(
        evaluator=QoSEvaluator(),
        recommendation_engine=_make_engine(),
        config=MonitoringConfig(interval_seconds=2.0),
        override_manager=mgr,
    )

    c1 = mon.run_cycle(
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
    assert c1.selected_service_id == "SVC-C02"
    assert c1.total_services == 5
    assert mgr.mode == MODE_MANUAL

    # Fail a DIFFERENT service (SVC-C04); monitoring detects it while keeping SVC-C02 active
    sim.simulate_outage("SVC-C04")
    c2 = mon.run_cycle(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C02",
        current_step=2,
        last_switch_step=1,
        force=True,
        respect_interval=False,
    )
    assert c2.unavailable_count == 1
    assert c2.changes_detected is True
    assert c2.selected_service_id == "SVC-C02"
    assert mgr.mode == MODE_MANUAL


def test_12_recovered_service_does_not_displace_valid_manual_override():
    """Test 12: Restoring a higher-scoring service does NOT switch away from valid manual override."""
    sim = FailureSimulator(get_default_services())
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.01, cooldown_steps=0)

    # Put SVC-C01 into outage first, activate manual override on SVC-C02
    sim.simulate_outage("SVC-C01")
    mgr = ManualOverrideManager()
    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla)[0]

    mon = MonitoringEngine(
        evaluator=QoSEvaluator(),
        recommendation_engine=_make_engine(),
        config=MonitoringConfig(interval_seconds=2.0),
        override_manager=mgr,
    )
    mon.run_cycle(
        sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst,
        previously_selected_id="SVC-C02", force=True, respect_interval=False
    )

    # Restore higher-scoring SVC-C01 -> recovery logged, but SVC-C02 remains selected!
    sim.restore_service("SVC-C01")
    c2 = mon.run_cycle(
        sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst,
        previously_selected_id="SVC-C02", force=True, respect_interval=False
    )

    assert any(e.event_type == EVENT_SERVICE_RECOVERED and e.service_id == "SVC-C01" for e in mon.event_history)
    assert c2.selected_service_id == "SVC-C02"
    assert mgr.mode == MODE_MANUAL


def test_13_hysteresis_still_works_in_automatic_mode():
    """Test 13: Phase 2 hysteresis remains intact in AUTOMATIC mode."""
    sim = FailureSimulator(get_default_services())
    engine = _make_engine()
    sla = get_default_sla_config("Compute")
    # Large hysteresis margin so SVC-C02 cannot trivially displace SVC-C01 even if slightly degraded
    hyst = HysteresisConfig(min_qos_delta=0.25, cooldown_steps=0)

    # Slightly degrade SVC-C01 (+35ms -> 80ms, still within 150ms SLA) so SVC-C02 takes rank #1 marginally
    sim.inject_latency_spike("SVC-C01", spike_ms=35.0)
    res = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C01",
        operating_mode=MODE_AUTOMATIC,
    )

    assert res.operating_mode == MODE_AUTOMATIC
    assert res.decision_type == "RETAINED"
    assert res.selected_service.service_id == "SVC-C01"


def test_14_duplicate_override_and_monitoring_events_prevented():
    """Test 14: Repeated idempotent operations do not flood transition/monitoring logs."""
    sim = FailureSimulator(get_default_services())
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    mgr = ManualOverrideManager()

    # Duplicate identical manual override activation logs only 1 activation
    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla, "pin")[0]
    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla, "pin")[0]
    activated_count = sum(1 for e in mgr.event_history if e.event_type == OVERRIDE_EVENT_ACTIVATED)
    assert activated_count == 1

    # Clearing when already in AUTOMATIC returns False and adds no events
    assert mgr.clear_override() is True
    before_len = len(mgr.event_history)
    assert mgr.clear_override() is False
    assert len(mgr.event_history) == before_len

    # Emergency termination when already AUTOMATIC returns False and adds no duplicate event
    assert mgr.handle_emergency_termination("SVC-C02", "SVC-C01", "Already auto", "Compute") is False
    assert len(mgr.event_history) == before_len

    # Steady-state monitoring produces no duplicate change events
    mon = MonitoringEngine(
        evaluator=QoSEvaluator(),
        recommendation_engine=_make_engine(),
        override_manager=mgr,
    )
    mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst, "SVC-C01", force=True, respect_interval=False)
    steady_evt_count = len(mon.event_history)
    mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst, "SVC-C01", force=True, respect_interval=False)
    assert len(mon.event_history) == steady_evt_count


def test_15_full_integration_explainability_sla_hysteresis_monitoring_and_reset():
    """Test 15: Full lifecycle integration across audit trail, comparison table, and simulator reset."""
    sim = FailureSimulator(get_default_services())
    eval_obj = QoSEvaluator()
    engine = RecommendationEngine(eval_obj)
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    mgr = ManualOverrideManager()
    audit = ReselectionAuditTrail()

    # Step 1: Activate valid manual override on SVC-C02
    assert mgr.request_manual_override(sim.get_all_services(), "Compute", "SVC-C02", sla, "Planned DR test")[0]
    cat_svcs = sim.get_services_by_category("Compute")
    rec_manual = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C01",
        operating_mode=mgr.mode,
        manual_service_id=mgr.requested_service_id,
        manual_override_reason=mgr.reason,
    )
    audit.record_decision("Manual Override Activated", rec_manual, eval_obj, DEFAULT_WEIGHTS, "SVC-C01", cat_svcs)
    tbl_manual = build_candidate_comparison_table(rec_manual, eval_obj, DEFAULT_WEIGHTS, cat_svcs)
    assert any("Manual Override" in r for r in tbl_manual["Role"].tolist())
    assert any("Selected Service" in r for r in tbl_manual["Role"].tolist())

    exp_manual = generate_detailed_reselection_explanation(rec_manual, eval_obj, DEFAULT_WEIGHTS, "SVC-C01", cat_svcs)
    assert "Manual" in exp_manual["reselection_trigger"]
    assert "Override" in exp_manual["reselection_trigger"]

    # Step 2: Inject outage on SVC-C02 -> emergency replacement & audit trail captures AUTOMATIC failover
    sim.simulate_outage("SVC-C02")
    rec_emerg = engine.recommend(
        services=sim.get_all_services(),
        category="Compute",
        weights=DEFAULT_WEIGHTS,
        sla_config=sla,
        hysteresis_config=hyst,
        previously_selected_id="SVC-C02",
        operating_mode=mgr.mode,
        manual_service_id=mgr.requested_service_id,
    )
    assert rec_emerg.override_terminated is True
    assert rec_emerg.selected_service.service_id == "SVC-C01"
    mgr.handle_emergency_termination("SVC-C02", "SVC-C01", rec_emerg.override_termination_reason, "Compute")
    audit.record_decision("Emergency Override Termination", rec_emerg, eval_obj, DEFAULT_WEIGHTS, "SVC-C02", cat_svcs)
    tbl_emerg = build_candidate_comparison_table(rec_emerg, eval_obj, DEFAULT_WEIGHTS, cat_svcs)
    assert any("Emergency Replacement" in r for r in tbl_emerg["Role"].tolist())

    # Step 3: Validate audit dataframe includes Operating Mode & validation helper reports clean state after reset
    df_audit = audit.to_dataframe()
    assert "Operating Mode" in df_audit.columns
    assert set(df_audit["Operating Mode"].tolist()) == {MODE_MANUAL, MODE_AUTOMATIC}

    sim.reset_simulation()
    mgr.reset()
    val_after_reset = validate_manual_override_request(sim.get_all_services(), "Compute", "SVC-C02", sla)
    assert val_after_reset.is_valid is True
    assert mgr.mode == MODE_AUTOMATIC
