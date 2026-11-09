"""Automated tests for SLA Constraint Enforcement and Strict Service Eligibility.

Covers:
    1. Latency above maximum threshold excludes a service.
    2. Availability below minimum threshold excludes a service.
    3. Reliability below minimum threshold excludes a service.
    4. Multiple simultaneous SLA violations are all reported.
    5. A highest-scoring but SLA-violating service is never selected.
    6. The highest-scoring SLA-compliant service is selected.
    7. All services violating SLA returns no selected service.
    8. All services unavailable returns the correct no-service state.
    9. Restoring metrics makes a previously excluded service eligible again.
    10. Existing category filtering remains correct.
    11. Existing deterministic tie-breaking remains unchanged.
    12. Existing QoS weights and normalization remain unchanged.
    13. Invalid SLA configuration is rejected safely.
    14. Missing, NaN, infinite, and out-of-range metric values are handled safely.
"""

import math
import pytest

from src.service_registry import CloudService, get_default_services, compute_reference_bounds
from src.qos_evaluator import QoSEvaluator
from src.failure_simulator import FailureSimulator
from src.recommendation_engine import RecommendationEngine, RecommendationResult
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla


def setup_engine():
    """Helper to initialize fresh simulator, bounds, evaluator, and recommendation engine."""
    sim = FailureSimulator()
    bounds = compute_reference_bounds(sim.get_all_services())
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)
    return sim, evaluator, engine


# =========================================================================
# 1. Latency SLA Exclusion
# =========================================================================
def test_latency_above_max_threshold_excludes_service():
    """Verify that any service exceeding the maximum allowed latency is marked ineligible."""
    sim, evaluator, engine = setup_engine()
    # Baseline Compute services latencies: C01=45ms, C02=25ms, C04=55ms, C05=75ms, C03=120ms
    # Setting max_latency=50.0 should exclude C04, C05, and C03
    sla = SLAConfig(max_latency=50.0, min_availability=90.0, min_reliability=90.0)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res.has_eligible_service is True
    eligible_ids = [s.service_id for s, _ in res.ranked_eligible]
    excluded_ids = [s.service_id for s, _ in res.excluded_services]

    # C01 (45ms) and C02 (25ms) are eligible
    assert "SVC-C01" in eligible_ids
    assert "SVC-C02" in eligible_ids

    # C04 (55ms), C05 (75ms), C03 (120ms) must be excluded
    assert "SVC-C04" in excluded_ids
    assert "SVC-C05" in excluded_ids
    assert "SVC-C03" in excluded_ids

    # Check violation message for C04
    c04_reason = next(reason for s, reason in res.excluded_services if s.service_id == "SVC-C04")
    assert "Latency SLA violated:" in c04_reason
    assert "exceeds maximum 50.0 ms" in c04_reason


# =========================================================================
# 2. Availability SLA Exclusion
# =========================================================================
def test_availability_below_min_threshold_excludes_service():
    """Verify that any service with availability below the minimum required threshold is excluded."""
    sim, evaluator, engine = setup_engine()
    # Baseline Compute availabilities: C01=99.90%, C02=99.95%, C04=99.85%, C05=99.20%, C03=98.80%
    # Setting min_availability=99.50% should exclude C05 (99.20%) and C03 (98.80%)
    sla = SLAConfig(max_latency=200.0, min_availability=99.50, min_reliability=90.0)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res.has_eligible_service is True
    excluded_ids = [s.service_id for s, _ in res.excluded_services]

    assert "SVC-C05" in excluded_ids
    assert "SVC-C03" in excluded_ids

    c03_reason = next(reason for s, reason in res.excluded_services if s.service_id == "SVC-C03")
    assert "Availability SLA violated:" in c03_reason
    assert "is below minimum 99.50%" in c03_reason


# =========================================================================
# 3. Reliability SLA Exclusion
# =========================================================================
def test_reliability_below_min_threshold_excludes_service():
    """Verify that any service with reliability below the minimum required threshold is excluded."""
    sim, evaluator, engine = setup_engine()
    # Baseline Compute reliabilities: C01=99.50%, C02=99.80%, C04=99.90%, C05=98.40%, C03=97.50%
    # Setting min_reliability=99.00% should exclude C05 (98.40%) and C03 (97.50%)
    sla = SLAConfig(max_latency=200.0, min_availability=90.0, min_reliability=99.00)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res.has_eligible_service is True
    excluded_ids = [s.service_id for s, _ in res.excluded_services]

    assert "SVC-C05" in excluded_ids
    assert "SVC-C03" in excluded_ids

    c05_reason = next(reason for s, reason in res.excluded_services if s.service_id == "SVC-C05")
    assert "Reliability SLA violated:" in c05_reason
    assert "is below minimum 99.00%" in c05_reason


# =========================================================================
# 4. Multiple Simultaneous SLA Violations
# =========================================================================
def test_multiple_simultaneous_sla_violations_all_reported():
    """Verify that when a service violates multiple SLA constraints, all violations are reported."""
    sim, evaluator, engine = setup_engine()
    # EcoCompute Budget (SVC-C03): lat=120ms, avail=98.80%, rel=97.50%
    # Setting max_latency=100.0, min_availability=99.0, min_reliability=99.0 triggers all 3 violations
    sla = SLAConfig(max_latency=100.0, min_availability=99.0, min_reliability=99.0)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    c03_reason = next(reason for s, reason in res.excluded_services if s.service_id == "SVC-C03")

    assert "Latency SLA violated: 120.0 ms exceeds maximum 100.0 ms." in c03_reason
    assert "Availability SLA violated: 98.80% is below minimum 99.00%." in c03_reason
    assert "Reliability SLA violated: 97.50% is below minimum 99.00%." in c03_reason


# =========================================================================
# 5. Highest-Scoring but SLA-Violating Service is Never Selected
# =========================================================================
def test_highest_scoring_service_excluded_when_violating_sla():
    """Verify that a candidate with the highest QoS score is NEVER selected if it violates an SLA."""
    sim, evaluator, engine = setup_engine()
    # Under default weights, NovaCompute (SVC-C01) has the highest baseline QoS score (0.8168)
    # SVC-C01 latency is 45.0 ms. If we set max_latency=40.0 ms, SVC-C01 violates SLA.
    # AetherCompute (SVC-C02) has latency 25.0 ms and satisfies max_latency=40.0 ms.
    sla = SLAConfig(max_latency=40.0, min_availability=98.0, min_reliability=97.0)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)

    # Acceptance criterion: SVC-C01 must never be selected!
    assert res.selected_service is not None
    assert res.selected_service.service_id != "SVC-C01"
    assert res.selected_service.service_id == "SVC-C02"

    # Confirm SVC-C01 is in excluded_services
    c01_excluded = any(s.service_id == "SVC-C01" for s, _ in res.excluded_services)
    assert c01_excluded is True


# =========================================================================
# 6. Highest-Scoring Eligible Service is Selected
# =========================================================================
def test_highest_scoring_eligible_service_selected():
    """Verify that among the compliant candidate pool, the service with the highest QoS score is chosen."""
    sim, evaluator, engine = setup_engine()
    sla = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res.has_eligible_service is True
    assert res.selected_service is not None

    top_eligible_service, top_eligible_score = res.ranked_eligible[0]
    assert res.selected_service.service_id == top_eligible_service.service_id
    assert res.selected_scores.qos_score == top_eligible_score.qos_score


# =========================================================================
# 7. All Services Violating SLA Returns No Recommendation
# =========================================================================
def test_all_services_violating_sla_returns_no_recommendation():
    """Verify that if all candidate services violate SLA constraints, no service is selected."""
    sim, evaluator, engine = setup_engine()
    # No service has latency <= 10.0 ms (min baseline latency is 25.0 ms)
    sla = SLAConfig(max_latency=10.0, min_availability=98.0, min_reliability=97.0)

    res = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)

    assert res.has_eligible_service is False
    assert res.selected_service is None
    assert res.selected_scores is None
    assert res.status_code == "NO_SLA_COMPLIANT_SERVICE"
    assert "No SLA-Compliant Service Available" in res.status_message
    assert "No SLA-Compliant Service Available" in res.selection_reason
    assert len(res.ranked_eligible) == 0
    assert len(res.excluded_services) == 5


# =========================================================================
# 8. All Services Unavailable Returns Correct State
# =========================================================================
def test_all_services_unavailable_returns_correct_state():
    """Verify that when all candidate services are in an outage, appropriate state is returned."""
    sim, evaluator, engine = setup_engine()
    for s in sim.get_services_by_category("Compute"):
        sim.simulate_outage(s.service_id)

    res = engine.recommend(sim.get_all_services(), category="Compute")

    assert res.has_eligible_service is False
    assert res.selected_service is None
    assert res.selected_scores is None
    assert res.status_code == "NO_SLA_COMPLIANT_SERVICE"
    assert "No SLA-Compliant Service Available" in res.status_message
    assert "UNAVAILABLE" in res.status_message
    assert all("UNAVAILABLE" in reason for _, reason in res.excluded_services)


# =========================================================================
# 9. Restoring Metrics Makes Excluded Service Eligible Again
# =========================================================================
def test_restoring_metrics_makes_previously_excluded_service_eligible_again():
    """Verify that restoring degraded metrics restores SLA compliance and eligibility."""
    sim, evaluator, engine = setup_engine()
    sla = SLAConfig(max_latency=100.0, min_availability=98.0, min_reliability=97.0)

    # NovaCompute (SVC-C01) baseline latency is 45.0 ms (compliant, initially selected)
    res_initial = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res_initial.selected_service.service_id == "SVC-C01"

    # Inject severe latency spike (+100.0 ms) -> latency becomes 145.0 ms (> 100.0 ms)
    sim.inject_latency_spike("SVC-C01", 100.0)
    res_degraded = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res_degraded.selected_service.service_id != "SVC-C01"
    assert any(s.service_id == "SVC-C01" for s, _ in res_degraded.excluded_services)

    # Restore SVC-C01 back to baseline (latency = 45.0 ms <= 100.0 ms)
    sim.restore_service("SVC-C01")
    res_restored = engine.recommend(sim.get_all_services(), category="Compute", sla_config=sla)
    assert res_restored.selected_service.service_id == "SVC-C01"
    assert any(s.service_id == "SVC-C01" for s, _ in res_restored.ranked_eligible)


# =========================================================================
# 10. Existing Category Filtering Remains Correct
# =========================================================================
def test_existing_category_filtering_remains_correct():
    """Verify that category filtering continues to strictly isolate target categories."""
    sim, evaluator, engine = setup_engine()
    res = engine.recommend(sim.get_all_services(), category="Storage")

    assert res.has_eligible_service is True
    assert res.selected_service.category == "Storage"
    assert all(s.category == "Storage" for s, _ in res.ranked_eligible)
    assert all(s.category == "Storage" for s, _ in res.excluded_services)


# =========================================================================
# 11. Existing Deterministic Tie-Breaking Remains Unchanged
# =========================================================================
def test_existing_deterministic_tie_breaking_remains_unchanged():
    """Verify that two SLA-compliant services with equal scores break ties deterministically by ID."""
    svc_a = CloudService(
        service_id="SVC-T01",
        name="Test Service A",
        category="TestCat",
        latency=50.0,
        cost=0.05,
        availability=99.0,
        reliability=99.0,
        operational_status="AVAILABLE",
        baseline={"latency": 50.0, "cost": 0.05, "availability": 99.0, "reliability": 99.0, "operational_status": "AVAILABLE"},
    )
    svc_b = CloudService(
        service_id="SVC-T02",
        name="Test Service B",
        category="TestCat",
        latency=50.0,
        cost=0.05,
        availability=99.0,
        reliability=99.0,
        operational_status="AVAILABLE",
        baseline={"latency": 50.0, "cost": 0.05, "availability": 99.0, "reliability": 99.0, "operational_status": "AVAILABLE"},
    )
    bounds = compute_reference_bounds([svc_a, svc_b])
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)
    sla = SLAConfig(max_latency=100.0, min_availability=95.0, min_reliability=95.0)

    res = engine.recommend([svc_a, svc_b], category="TestCat", sla_config=sla)
    assert res.has_eligible_service is True
    # SVC-T01 must win tie-break over SVC-T02
    assert res.selected_service.service_id == "SVC-T01"


# =========================================================================
# 12. Existing QoS Weights and Normalization Remain Unchanged
# =========================================================================
def test_existing_qos_weights_and_normalization_remain_unchanged():
    """Verify that SLA eligibility filtering does not alter underlying QoS scoring math."""
    sim, evaluator, engine = setup_engine()
    weights = {"latency": 0.5, "cost": 0.0, "availability": 0.5, "reliability": 0.0}
    sla = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)

    # In Compute, SVC-C02 is best on latency (25ms -> 1.0) and availability (99.95% -> 1.0)
    res = engine.recommend(sim.get_all_services(), category="Compute", weights=weights, sla_config=sla)

    assert res.selected_service.service_id == "SVC-C02"
    assert res.selected_scores.latency_score == 1.0
    assert res.selected_scores.availability_score == 1.0
    assert res.selected_scores.qos_score == 1.0


# =========================================================================
# 13. Invalid SLA Configuration is Rejected Safely
# =========================================================================
def test_invalid_sla_configuration_rejected_safely():
    """Verify that invalid, negative, non-finite, or impossible SLA configs raise ValueError or TypeError."""
    # Negative max_latency
    with pytest.raises(ValueError, match="max_latency must be strictly positive"):
        SLAConfig(max_latency=-10.0)

    # Zero max_latency
    with pytest.raises(ValueError, match="max_latency must be strictly positive"):
        SLAConfig(max_latency=0.0)

    # NaN max_latency
    with pytest.raises(ValueError, match="max_latency must be a finite number"):
        SLAConfig(max_latency=float("nan"))

    # Infinite max_latency
    with pytest.raises(ValueError, match="max_latency must be a finite number"):
        SLAConfig(max_latency=float("inf"))

    # Availability > 100%
    with pytest.raises(ValueError, match=r"min_availability must be in \[0.0, 100.0\]%"):
        SLAConfig(min_availability=105.0)

    # Availability < 0%
    with pytest.raises(ValueError, match=r"min_availability must be in \[0.0, 100.0\]%"):
        SLAConfig(min_availability=-1.0)

    # Reliability > 100%
    with pytest.raises(ValueError, match=r"min_reliability must be in \[0.0, 100.0\]%"):
        SLAConfig(min_reliability=100.1)

    # Non-numeric input
    with pytest.raises(TypeError, match="max_latency must be numeric"):
        SLAConfig(max_latency="invalid")


# =========================================================================
# 14. Missing, NaN, Infinite, and Out-of-Range Metric Values Handled Safely
# =========================================================================
def test_missing_nan_infinite_and_out_of_range_metrics_handled_safely():
    """Verify that corrupt, NaN, infinite, or out-of-range metrics are safely excluded."""
    sim, evaluator, engine = setup_engine()
    sla = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)

    # Service with NaN latency
    bad_service_nan = CloudService(
        service_id="SVC-BAD1",
        name="Corrupted NaN Service",
        category="Compute",
        latency=float("nan"),
        cost=0.01,
        availability=99.9,
        reliability=99.9,
        operational_status="AVAILABLE",
        baseline={"latency": 50.0, "cost": 0.01, "availability": 99.9, "reliability": 99.9, "operational_status": "AVAILABLE"},
    )

    # Service with Infinite latency
    bad_service_inf = CloudService(
        service_id="SVC-BAD2",
        name="Infinite Latency Service",
        category="Compute",
        latency=float("inf"),
        cost=0.01,
        availability=99.9,
        reliability=99.9,
        operational_status="AVAILABLE",
        baseline={"latency": 50.0, "cost": 0.01, "availability": 99.9, "reliability": 99.9, "operational_status": "AVAILABLE"},
    )

    # Service with out-of-range availability (>100%)
    bad_service_avail = CloudService(
        service_id="SVC-BAD3",
        name="Over 100 Avail Service",
        category="Compute",
        latency=50.0,
        cost=0.01,
        availability=150.0,
        reliability=99.9,
        operational_status="AVAILABLE",
        baseline={"latency": 50.0, "cost": 0.01, "availability": 99.9, "reliability": 99.9, "operational_status": "AVAILABLE"},
    )

    # Direct validation check
    violations_nan = validate_service_sla(bad_service_nan, sla)
    assert any("non-finite" in v for v in violations_nan)

    violations_inf = validate_service_sla(bad_service_inf, sla)
    assert any("non-finite" in v for v in violations_inf)

    violations_avail = validate_service_sla(bad_service_avail, sla)
    assert any("out of range" in v for v in violations_avail)

    # Full recommendation pipeline with corrupted services injected into candidate pool
    pool = sim.get_all_services() + [bad_service_nan, bad_service_inf, bad_service_avail]
    res = engine.recommend(pool, category="Compute", sla_config=sla)

    # The corrupted services must never be selected
    assert res.selected_service is not None
    assert res.selected_service.service_id not in ("SVC-BAD1", "SVC-BAD2", "SVC-BAD3")

    excluded_ids = [s.service_id for s, _ in res.excluded_services]
    assert "SVC-BAD1" in excluded_ids
    assert "SVC-BAD2" in excluded_ids
    assert "SVC-BAD3" in excluded_ids

