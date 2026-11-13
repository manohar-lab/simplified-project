"""Phase 5 Reliability and Edge-Case Validation Suite.

Validates the 13 required edge cases:
    1. Missing QoS values (None attributes).
    2. NaN and infinite values in raw metrics.
    3. Invalid SLA configurations (negative latency, out-of-range percentages).
    4. Equal QoS scores and deterministic tie-breaking.
    5. Empty service categories.
    6. All services unavailable.
    7. All services SLA-ineligible.
    8. Repeated monitoring cycles with zero state drift.
    9. Duplicate audit events prevention across monitoring and override managers.
    10. Rapid metric fluctuations without crashing or corrupted rankings.
    11. Repeated service restoration idempotence.
    12. Session-state consistency and rerun safety.
    13. Monitoring exceptions handled safely without crashing.
"""

import math
import pytest
from src.service_registry import get_default_services, CloudService
from src.failure_simulator import FailureSimulator
from src.qos_evaluator import QoSEvaluator, DEFAULT_WEIGHTS
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla
from src.hysteresis_config import HysteresisConfig
from src.monitoring_config import MonitoringConfig
from src.monitoring_engine import MonitoringEngine, MonitoringCycleResult
from src.recommendation_engine import RecommendationEngine
from src.override_manager import ManualOverrideManager, MODE_AUTOMATIC, MODE_MANUAL


def _setup_stack():
    sim = FailureSimulator(get_default_services())
    evaluator = QoSEvaluator()
    engine = RecommendationEngine(evaluator)
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    ovr = ManualOverrideManager()
    mon = MonitoringEngine(evaluator=evaluator, recommendation_engine=engine, override_manager=ovr)
    return sim, evaluator, engine, sla, hyst, ovr, mon


def test_edge_01_missing_qos_values():
    """1. Missing QoS values (None attributes) are caught safely as SLA violations."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    broken_svc = CloudService(
        service_id="SVC-BROKEN",
        name="Broken Service",
        category="Compute",
        latency=None,  # Missing!
        cost=0.05,
        availability=None,  # Missing!
        reliability=99.0,
        operational_status="AVAILABLE",
        baseline={},
    )
    violations = validate_service_sla(broken_svc, sla)
    assert len(violations) >= 2
    assert any("latency" in v.lower() for v in violations)
    assert any("availability" in v.lower() for v in violations)


def test_edge_02_nan_and_infinite_values():
    """2. NaN and infinite metric values do not cause uncaught math errors or false eligibility."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    nan_svc = CloudService("SVC-NAN", "NaN Service", "Compute", float("nan"), 0.05, 99.0, 99.0, "AVAILABLE", {})
    inf_svc = CloudService("SVC-INF", "Inf Service", "Compute", 45.0, 0.05, float("inf"), 99.0, "AVAILABLE", {})

    v_nan = validate_service_sla(nan_svc, sla)
    v_inf = validate_service_sla(inf_svc, sla)

    assert len(v_nan) > 0
    assert any("non-finite" in v.lower() or "invalid" in v.lower() for v in v_nan)
    assert len(v_inf) > 0
    assert any("non-finite" in v.lower() or "invalid" in v.lower() for v in v_inf)


def test_edge_03_invalid_sla_configurations():
    """3. Invalid SLA configurations (impossible thresholds, negative values) raise explicit ValueError."""
    with pytest.raises((ValueError, TypeError)):
        SLAConfig(max_latency=-10.0)

    with pytest.raises((ValueError, TypeError)):
        SLAConfig(min_availability=105.0)

    with pytest.raises((ValueError, TypeError)):
        SLAConfig(min_reliability=-5.0)


def test_edge_04_equal_qos_scores_deterministic_tie_breaking():
    """4. Equal QoS scores resolve deterministically by service ID order without crashes or flapping."""
    eval_obj = QoSEvaluator()
    engine = RecommendationEngine(eval_obj)
    sla = SLAConfig(max_latency=150.0, min_availability=90.0, min_reliability=90.0)

    svc_b = CloudService("SVC-B", "Service B", "Compute", 50.0, 0.05, 99.0, 99.0, "AVAILABLE", {})
    svc_a = CloudService("SVC-A", "Service A", "Compute", 50.0, 0.05, 99.0, 99.0, "AVAILABLE", {})

    res1 = engine.recommend([svc_b, svc_a], "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    res2 = engine.recommend([svc_a, svc_b], "Compute", DEFAULT_WEIGHTS, sla_config=sla)

    assert res1.selected_service.service_id == "SVC-A"
    assert res2.selected_service.service_id == "SVC-A"


def test_edge_05_empty_service_categories():
    """5. Querying a non-existent or empty category returns safe NO_ELIGIBLE_SERVICE state."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    res = engine.recommend(sim.get_all_services(), category="QuantumComputing")

    assert res.has_eligible_service is False
    assert res.selected_service is None
    assert res.decision_type == "NO_ELIGIBLE_SERVICE"
    assert len(res.ranked_eligible) == 0


def test_edge_06_all_services_unavailable():
    """6. All services in category marked UNAVAILABLE handled safely without fallback."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    for s in sim.get_services_by_category("Compute"):
        s.operational_status = "UNAVAILABLE"

    res = engine.recommend(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=sla)
    assert res.has_eligible_service is False
    assert res.selected_service is None
    assert res.decision_type == "NO_ELIGIBLE_SERVICE"


def test_edge_07_all_services_sla_ineligible():
    """7. All services violating SLA handled safely with full audit exclusion reasons."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    tight_sla = SLAConfig(max_latency=5.0)  # All services exceed 5ms

    res = engine.recommend(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla_config=tight_sla)
    assert res.has_eligible_service is False
    assert len(res.excluded_services) == 5
    assert all("Latency SLA violated" in r for s, r in res.excluded_services)


def test_edge_08_repeated_monitoring_cycles_zero_drift():
    """8. 50 repeated monitoring cycles on steady state produce zero drift and zero spam."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    for i in range(50):
        cycle = mon.run_cycle(
            sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst,
            previously_selected_id="SVC-C01", current_step=i, force=True, respect_interval=False
        )
        assert cycle.selected_service_id == "SVC-C01"
        assert cycle.reselection_triggered is False


def test_edge_09_duplicate_audit_events_prevention():
    """9. Redundant status mutations or identical cycles do not flood audit logs."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst, "SVC-C01", force=True, respect_interval=False)
    count1 = len(mon.event_history)
    mon.run_cycle(sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst, "SVC-C01", force=True, respect_interval=False)
    count2 = len(mon.event_history)
    assert count1 == count2


def test_edge_10_rapid_metric_fluctuations():
    """10. Rapid alternating latency spikes simulate high volatility without system crash."""
    sim, eval_obj, engine, sla, hyst, ovr, mon = _setup_stack()
    for step in range(10):
        # Alternate latency between SVC-C01 and SVC-C02
        if step % 2 == 0:
            sim.get_service("SVC-C01").latency = 120.0
            sim.get_service("SVC-C02").latency = 25.0
        else:
            sim.get_service("SVC-C01").latency = 45.0
            sim.get_service("SVC-C02").latency = 130.0

        cycle = mon.run_cycle(
            sim.get_all_services(), "Compute", DEFAULT_WEIGHTS, sla, hyst,
            previously_selected_id="SVC-C01", current_step=step, force=True, respect_interval=False
        )
        assert cycle.selected_service_id is not None


def test_edge_11_repeated_service_restoration_idempotence():
    """11. Restoring already healthy service is a safe no-op that preserves exact baseline."""
    sim = FailureSimulator(get_default_services())
    svc = sim.get_service("SVC-C01")
    orig_latency = svc.latency

    ok1, msg1 = sim.restore_service("SVC-C01")
    ok2, msg2 = sim.restore_service("SVC-C01")

    assert ok1 is True
    assert ok2 is True
    assert svc.latency == orig_latency
    assert svc.operational_status == "AVAILABLE"


def test_edge_12_session_state_consistency_and_rerun_safety():
    """12. Manual override manager reset and mode changes remain strictly consistent."""
    mgr = ManualOverrideManager()
    assert mgr.mode == MODE_AUTOMATIC
    mgr.reset()
    assert mgr.mode == MODE_AUTOMATIC
    assert mgr.requested_service_id is None
    assert len(mgr.event_history) == 0


def test_edge_13_monitoring_exceptions_handled_safely():
    """13. Unhandled engine errors during monitoring do not crash engine and log ERROR cycle."""
    class CrashingEngine:
        def recommend(self, *args, **kwargs):
            raise RuntimeError("Simulated recommendation engine crash")

    mon = MonitoringEngine(evaluator=QoSEvaluator(), recommendation_engine=CrashingEngine())

    cycle = mon.run_cycle(
        get_default_services(), "Compute", DEFAULT_WEIGHTS,
        SLAConfig(), HysteresisConfig(), "SVC-C01", force=True, respect_interval=False
    )

    assert cycle.status == "ERROR"
    assert "Simulated recommendation engine crash" in cycle.error_message

