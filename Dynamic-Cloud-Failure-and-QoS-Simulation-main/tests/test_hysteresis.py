"""Automated tests for Phase 2: Hysteresis and Anti-Flapping Mechanism.

Covers the complete 15-test verification suite:
    1. Initial selection chooses highest-scoring eligible service (previously_selected_id is None).
    2. Current service is retained when score improvement is below threshold.
    3. Switching occurs when score improvement exceeds threshold.
    4. Equal QoS scores (delta == 0.0) do not cause unnecessary switching.
    5. Small score fluctuations do not cause repeated switching (flapping prevention).
    6. Current service outage (UNAVAILABLE) triggers immediate emergency reselection.
    7. Current service SLA violation triggers immediate emergency reselection.
    8. Cooldown blocks normal performance-driven switching when active.
    9. Cooldown never blocks emergency reselection (outage or SLA violation).
    10. No eligible candidate returns correct NO_ELIGIBLE_SERVICE state.
    11. Recovered services are reconsidered correctly in candidate pool.
    12. Recovery does not cause automatic bounce-back without satisfying switching threshold.
    13. Repeated evaluations with unchanged state do not generate duplicate switching events.
    14. Existing Phase 1 SLA constraints continue to enforce strict eligibility without regression.
    15. Existing QoS ranking and deterministic tie-breaking remain unchanged.
"""

from __future__ import annotations
import copy
import pytest

from src.service_registry import CloudService, get_default_services, compute_reference_bounds
from src.qos_evaluator import QoSEvaluator
from src.failure_simulator import FailureSimulator
from src.recommendation_engine import RecommendationEngine, RecommendationResult
from src.sla_config import SLAConfig, get_default_sla_config
from src.hysteresis_config import HysteresisConfig, DEFAULT_HYSTERESIS_CONFIG, check_cooldown_active


def setup_test_environment():
    """Helper to initialize fresh simulator, evaluator, and recommendation engine."""
    sim = FailureSimulator()
    bounds = compute_reference_bounds(sim.get_all_services())
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)
    return sim, evaluator, engine


def make_dummy_service(
    service_id: str,
    name: str,
    category: str = "Compute",
    latency: float = 30.0,
    cost: float = 0.05,
    availability: float = 99.9,
    reliability: float = 99.9,
    operational_status: str = "AVAILABLE",
) -> CloudService:
    """Helper to construct a fully formed CloudService dataclass instance."""
    baseline = {
        "latency": latency,
        "cost": cost,
        "availability": availability,
        "reliability": reliability,
        "operational_status": operational_status,
    }
    return CloudService(
        service_id=service_id,
        name=name,
        category=category,
        latency=latency,
        cost=cost,
        availability=availability,
        reliability=reliability,
        operational_status=operational_status,
        baseline=baseline,
    )


# =========================================================================
# 1. Initial Selection Rule
# =========================================================================
def test_initial_selection_chooses_highest_scoring_service():
    """Verify that with no prior selection (previously_selected_id=None), Rule A selects the highest-scoring candidate."""
    sim, evaluator, engine = setup_test_environment()
    services = sim.get_services_by_category("Compute")

    # Baseline Compute services: SVC-C01 has highest score (~0.8168)
    res = engine.recommend(services, category="Compute", previously_selected_id=None)

    assert res.has_eligible_service is True
    assert res.selected_service is not None
    assert res.selected_service.service_id == "SVC-C01"
    assert res.decision_type in ("INITIAL", "INITIAL_SELECTION")
    assert "initial selection" in res.decision_reason.lower()
    assert res.qos_improvement > 0.0
    assert res.cooldown_active is False


# =========================================================================
# 2. Hysteresis Retention: Insufficient Improvement
# =========================================================================
def test_current_service_retained_when_improvement_below_threshold():
    """Verify Rule B: Current service is retained when alternative improvement is below min_qos_delta."""
    sim, evaluator, engine = setup_test_environment()
    services = sim.get_services_by_category("Compute")

    # In Compute baseline: SVC-C01 score = 0.8168, SVC-C02 score = 0.7937
    # Slightly increase latency of SVC-C01 by 15ms so its score drops slightly below SVC-C02
    sim.inject_latency_spike("SVC-C01", 15.0)
    updated_services = sim.get_services_by_category("Compute")

    scores_c01 = evaluator.evaluate_service(sim.get_service("SVC-C01"))
    scores_c02 = evaluator.evaluate_service(sim.get_service("SVC-C02"))
    delta = scores_c02.qos_score - scores_c01.qos_score
    assert 0.0 < delta < 0.05

    # Threshold = 0.05, delta is small (< 0.05)
    hyst_cfg = HysteresisConfig(min_qos_delta=0.05)
    res = engine.recommend(
        updated_services,
        category="Compute",
        previously_selected_id="SVC-C01",
        hysteresis_config=hyst_cfg,
    )

    # Current service SVC-C01 must be retained
    assert res.selected_service.service_id == "SVC-C01"
    assert res.decision_type == "RETAINED"
    assert "below the hysteresis threshold" in res.decision_reason.lower()
    assert res.best_alternative is not None
    assert res.best_alternative.service_id == "SVC-C02"
    assert res.qos_improvement == round(delta, 4)


# =========================================================================
# 3. Switching Exceeds Threshold
# =========================================================================
def test_switching_occurs_when_improvement_exceeds_threshold():
    """Verify Rule B: Service switches when alternative improvement strictly exceeds min_qos_delta without SLA violation."""
    sim, evaluator, engine = setup_test_environment()

    # Latency spike of +50ms on SVC-C01: 45 + 50 = 95ms (within default 150ms SLA)
    sim.inject_latency_spike("SVC-C01", 50.0)
    services = sim.get_services_by_category("Compute")

    scores_c01 = evaluator.evaluate_service(sim.get_service("SVC-C01"))
    scores_c02 = evaluator.evaluate_service(sim.get_service("SVC-C02"))
    delta = scores_c02.qos_score - scores_c01.qos_score
    assert delta > 0.05

    hyst_cfg = HysteresisConfig(min_qos_delta=0.05)
    res = engine.recommend(
        services,
        category="Compute",
        previously_selected_id="SVC-C01",
        hysteresis_config=hyst_cfg,
    )

    # Switched to SVC-C02 via normal performance switching
    assert res.selected_service.service_id == "SVC-C02"
    assert res.decision_type == "SWITCHED"
    assert "exceeds the configured threshold" in res.decision_reason
    assert res.qos_improvement > 0.05


# =========================================================================
# 4. Equal QoS Scores Do Not Cause Switching
# =========================================================================
def test_equal_qos_scores_do_not_cause_unnecessary_switching():
    """Verify that when alternative candidate has identical QoS score (delta == 0.0), current service is retained."""
    sim, evaluator, engine = setup_test_environment()

    # Create two services with identical QoS metrics
    svc1 = make_dummy_service("SVC-X01", "Service Alpha", "Compute", 30.0, 0.05, 99.9, 99.9)
    svc2 = make_dummy_service("SVC-X02", "Service Beta", "Compute", 30.0, 0.05, 99.9, 99.9)
    custom_services = [svc1, svc2]

    # SVC-X02 was previously selected. Even though SVC-X01 is alphabetically earlier, delta is 0.0 <= min_qos_delta
    res = engine.recommend(
        custom_services,
        category="Compute",
        previously_selected_id="SVC-X02",
        hysteresis_config=HysteresisConfig(min_qos_delta=0.05),
    )

    assert res.selected_service.service_id == "SVC-X02"
    assert res.decision_type == "RETAINED"
    assert res.qos_improvement == 0.0


# =========================================================================
# 5. Flapping Prevention Under Fluctuations
# =========================================================================
def test_flapping_prevention_under_small_score_fluctuations():
    """Verify that minor back-and-forth oscillations do not cause rapid service reselection (anti-flapping)."""
    sim, evaluator, engine = setup_test_environment()
    hyst_cfg = HysteresisConfig(min_qos_delta=0.05)

    # Start with baseline: SVC-C01 selected
    res1 = engine.recommend(sim.get_services_by_category("Compute"), "Compute")
    selected_id = res1.selected_service.service_id
    assert selected_id == "SVC-C01"

    # Simulate minor fluctuations across 6 simulation cycles
    fluctuations = [10.0, -10.0, 15.0, -15.0, 8.0, -8.0]
    switch_count = 0

    for fluc in fluctuations:
        if fluc > 0:
            sim.inject_latency_spike("SVC-C01", fluc)
        else:
            sim.restore_service("SVC-C01")

        res = engine.recommend(
            sim.get_services_by_category("Compute"),
            category="Compute",
            previously_selected_id=selected_id,
            hysteresis_config=hyst_cfg,
        )
        if res.selected_service.service_id != selected_id:
            switch_count += 1
            selected_id = res.selected_service.service_id

    # Under hysteresis, zero flapping switches should occur
    assert switch_count == 0
    assert selected_id == "SVC-C01"


# =========================================================================
# 6. Current Service Outage Triggers Immediate Emergency Reselection
# =========================================================================
def test_current_service_outage_triggers_immediate_emergency_reselection():
    """Verify Rule C: When current service becomes UNAVAILABLE, emergency reselection immediately fires, bypassing hysteresis and cooldown."""
    sim, evaluator, engine = setup_test_environment()

    # Outage on SVC-C01
    sim.simulate_outage("SVC-C01")
    services = sim.get_services_by_category("Compute")

    # Cooldown condition would normally be active (last_switch=0, current_step=1, cooldown_steps=10)
    hyst_cfg = HysteresisConfig(min_qos_delta=0.50, cooldown_steps=10)
    is_cd_active, _ = check_cooldown_active(hyst_cfg, current_step=1, last_switch_step=0)
    assert is_cd_active is True

    # Even with high hysteresis and active cooldown, emergency failover must occur immediately
    res = engine.recommend(
        services,
        category="Compute",
        previously_selected_id="SVC-C01",
        hysteresis_config=hyst_cfg,
        current_step=1,
        last_switch_step=0,
    )

    assert res.selected_service.service_id == "SVC-C02"
    assert res.decision_type == "EMERGENCY_OUTAGE"
    assert "Emergency reselection" in res.decision_reason
    assert "UNAVAILABLE" in res.decision_reason


# =========================================================================
# 7. Current Service SLA Violation Triggers Immediate Emergency Reselection
# =========================================================================
def test_current_service_sla_violation_triggers_immediate_emergency_reselection():
    """Verify Rule D: When current service violates a hard SLA constraint, emergency reselection fires immediately, bypassing hysteresis and cooldown."""
    sim, evaluator, engine = setup_test_environment()

    # Latency spike that pushes SVC-C01 to 145ms (violating max_latency=80ms)
    sim.inject_latency_spike("SVC-C01", 100.0)  # 45 + 100 = 145ms
    services = sim.get_services_by_category("Compute")
    sla = SLAConfig(max_latency=80.0, min_availability=90.0, min_reliability=90.0)

    hyst_cfg = HysteresisConfig(min_qos_delta=0.40, cooldown_steps=10)
    res = engine.recommend(
        services,
        category="Compute",
        previously_selected_id="SVC-C01",
        sla_config=sla,
        hysteresis_config=hyst_cfg,
        current_step=2,
        last_switch_step=1,  # Cooldown active!
    )

    assert res.selected_service.service_id == "SVC-C02"
    assert res.decision_type == "EMERGENCY_SLA_VIOLATION"
    assert "Emergency reselection" in res.decision_reason
    assert "SLA" in res.decision_reason


# =========================================================================
# 8. Cooldown Blocks Normal Performance Switching
# =========================================================================
def test_cooldown_blocks_normal_performance_switching_when_active():
    """Verify Rule B cooldown check: When cooldown is active, normal performance improvement cannot trigger a switch."""
    sim, evaluator, engine = setup_test_environment()

    # Moderate spike on SVC-C01 that makes SVC-C02 improve by > 0.02
    sim.inject_latency_spike("SVC-C01", 40.0)
    services = sim.get_services_by_category("Compute")

    scores_c01 = evaluator.evaluate_service(sim.get_service("SVC-C01"))
    scores_c02 = evaluator.evaluate_service(sim.get_service("SVC-C02"))
    delta = scores_c02.qos_score - scores_c01.qos_score
    assert delta > 0.02

    # Configure small delta threshold (0.01) but active cooldown of 5 steps
    hyst_cfg = HysteresisConfig(min_qos_delta=0.01, cooldown_steps=5)

    # Last switch occurred at step 10, current step is 12 (cooldown remaining = 3 steps)
    res = engine.recommend(
        services,
        category="Compute",
        previously_selected_id="SVC-C01",
        hysteresis_config=hyst_cfg,
        current_step=12,
        last_switch_step=10,
    )

    # Switch blocked due to cooldown
    assert res.selected_service.service_id == "SVC-C01"
    assert res.decision_type == "RETAINED"
    assert res.cooldown_active is True
    assert "cooldown active" in res.decision_reason.lower()


# =========================================================================
# 9. Cooldown Never Blocks Emergency Reselection
# =========================================================================
def test_cooldown_never_blocks_emergency_reselection():
    """Verify that cooldown locking is strictly ignored when an outage or hard SLA violation occurs on current service."""
    sim, evaluator, engine = setup_test_environment()

    # Drop availability to 50% (violating default 95% SLA)
    sim.reduce_availability("SVC-C01", 49.0)
    services = sim.get_services_by_category("Compute")
    sla = SLAConfig(max_latency=200.0, min_availability=95.0, min_reliability=90.0)

    hyst_cfg = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=100)
    res = engine.recommend(
        services,
        category="Compute",
        previously_selected_id="SVC-C01",
        sla_config=sla,
        hysteresis_config=hyst_cfg,
        current_step=5,
        last_switch_step=4,  # Active cooldown of 99 steps remaining
    )

    # Must switch despite cooldown
    assert res.selected_service.service_id != "SVC-C01"
    assert res.decision_type == "EMERGENCY_SLA_VIOLATION"


# =========================================================================
# 10. No Eligible Service Behavior
# =========================================================================
def test_no_eligible_candidate_returns_correct_no_service_state():
    """Verify Rule E: When no candidate is eligible, returns selected_service=None and NO_ELIGIBLE_SERVICE."""
    sim, evaluator, engine = setup_test_environment()
    services = sim.get_services_by_category("Compute")

    # Mark all Compute services UNAVAILABLE
    for s in services:
        sim.simulate_outage(s.service_id)

    res = engine.recommend(
        sim.get_services_by_category("Compute"),
        category="Compute",
        previously_selected_id="SVC-C01",
    )

    assert res.has_eligible_service is False
    assert res.selected_service is None
    assert res.selected_scores is None
    assert res.decision_type == "NO_ELIGIBLE_SERVICE"
    assert "constraints" in res.decision_reason.lower()


# =========================================================================
# 11. Recovered Services Reconsidered Correctly
# =========================================================================
def test_recovered_services_reconsidered_correctly():
    """Verify Rule F: Recovered services re-enter the candidate pool and are evaluated normally."""
    sim, evaluator, engine = setup_test_environment()

    # Outage on SVC-C01 -> C02 becomes selected
    sim.simulate_outage("SVC-C01")
    rec_after_outage = engine.recommend(
        sim.get_services_by_category("Compute"),
        category="Compute",
        previously_selected_id="SVC-C01",
    )
    assert rec_after_outage.selected_service.service_id == "SVC-C02"

    # Restore SVC-C01 to baseline
    sim.restore_service("SVC-C01")
    services_restored = sim.get_services_by_category("Compute")

    rec_restored = engine.recommend(
        services_restored,
        category="Compute",
        previously_selected_id="SVC-C02",
        hysteresis_config=HysteresisConfig(min_qos_delta=0.01),  # Low threshold
    )

    # SVC-C01 is back in eligible candidates
    eligible_ids = [s.service_id for s, _ in rec_restored.ranked_eligible]
    assert "SVC-C01" in eligible_ids
    # With min_qos_delta=0.01, C01 leads C02 by > 0.01, so it is reselected
    assert rec_restored.selected_service.service_id == "SVC-C01"
    assert rec_restored.decision_type == "SWITCHED"


# =========================================================================
# 12. Recovery Does Not Cause Automatic Bounce-Back Without Satisfying Threshold
# =========================================================================
def test_recovery_does_not_cause_automatic_bounceback_without_satisfying_threshold():
    """Verify that service recovery does NOT automatically bounce back to previously preferred service unless normal hysteresis threshold is satisfied."""
    sim, evaluator, engine = setup_test_environment()

    # Outage on C01 -> switch to C02
    sim.simulate_outage("SVC-C01")
    engine.recommend(sim.get_services_by_category("Compute"), "Compute", previously_selected_id="SVC-C01")

    # Restore C01
    sim.restore_service("SVC-C01")
    services_restored = sim.get_services_by_category("Compute")

    # Baseline: C01 leads C02 by ~0.0273
    # Set min_qos_delta = 0.05. Since 0.0273 < 0.05, C02 must be RETAINED!
    hyst_cfg = HysteresisConfig(min_qos_delta=0.05)
    rec_eval = engine.recommend(
        services_restored,
        category="Compute",
        previously_selected_id="SVC-C02",
        hysteresis_config=hyst_cfg,
    )

    # C02 is retained! No bounce-back flapping!
    assert rec_eval.selected_service.service_id == "SVC-C02"
    assert rec_eval.decision_type == "RETAINED"
    assert rec_eval.best_alternative.service_id == "SVC-C01"
    assert 0.0 < rec_eval.qos_improvement < 0.05


# =========================================================================
# 13. Repeated Evaluations With Unchanged State Do Not Generate Switching
# =========================================================================
def test_repeated_evaluations_with_unchanged_state_do_not_generate_duplicate_switching():
    """Verify that multiple successive evaluations with unchanged state consistently retain the selected service."""
    sim, evaluator, engine = setup_test_environment()
    services = sim.get_services_by_category("Compute")

    # Initial recommendation
    rec_initial = engine.recommend(services, "Compute")
    current_id = rec_initial.selected_service.service_id
    assert rec_initial.decision_type in ("INITIAL", "INITIAL_SELECTION")

    # Repeat 5 times
    for step in range(1, 6):
        rec_next = engine.recommend(
            services,
            category="Compute",
            previously_selected_id=current_id,
            current_step=step,
        )
        assert rec_next.selected_service.service_id == current_id
        assert rec_next.decision_type == "RETAINED"


# =========================================================================
# 14. Phase 1 SLA Strict Enforcement Regression Test
# =========================================================================
def test_existing_phase1_sla_tests_continue_to_pass_with_hysteresis():
    """Verify that hard SLA constraints always eliminate violating candidates before hysteresis is evaluated."""
    sim, evaluator, engine = setup_test_environment()
    services = sim.get_services_by_category("Compute")

    # Tight latency SLA of 30ms (only C02 at 25ms is compliant, C01 at 45ms is excluded)
    sla = SLAConfig(max_latency=30.0, min_availability=90.0, min_reliability=90.0)

    # Even if C01 was previously selected, it cannot be retained because it violates SLA!
    rec = engine.recommend(
        services,
        category="Compute",
        previously_selected_id="SVC-C01",
        sla_config=sla,
        hysteresis_config=HysteresisConfig(min_qos_delta=0.50),
    )

    assert rec.selected_service.service_id == "SVC-C02"
    assert rec.decision_type == "EMERGENCY_SLA_VIOLATION"
    excluded_ids = [s.service_id for s, _ in rec.excluded_services]
    assert "SVC-C01" in excluded_ids


# =========================================================================
# 15. Candidate Ranking and Deterministic Tie-Breaking Preserved
# =========================================================================
def test_candidate_ranking_and_deterministic_tie_breaking_remain_unchanged():
    """Verify that ranked_eligible candidate order is strictly by descending QoS score and ascending service_id."""
    sim, evaluator, engine = setup_test_environment()

    # Three identical services with full CloudService fields
    svc1 = make_dummy_service("SVC-Z03", "Service Zeta", "Storage", 20.0, 0.02, 99.9, 99.9)
    svc2 = make_dummy_service("SVC-Z01", "Service Alpha", "Storage", 20.0, 0.02, 99.9, 99.9)
    svc3 = make_dummy_service("SVC-Z02", "Service Beta", "Storage", 20.0, 0.02, 99.9, 99.9)
    custom = [svc1, svc2, svc3]

    res = engine.recommend(custom, category="Storage")

    # Tie-breaking by service_id: Z01, Z02, Z03
    ranked_ids = [s.service_id for s, _ in res.ranked_eligible]
    assert ranked_ids == ["SVC-Z01", "SVC-Z02", "SVC-Z03"]
    assert res.selected_service.service_id == "SVC-Z01"
