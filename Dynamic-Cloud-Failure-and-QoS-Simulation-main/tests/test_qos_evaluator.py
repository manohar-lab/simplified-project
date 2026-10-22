"""Unit tests for the QoS Evaluation Engine.

These tests verify the mathematical correctness of QoS normalization and weighted
scoring. They cover:
    - Lower-is-better normalization (used for latency and cost).
    - Higher-is-better normalization (used for availability and reliability).
    - Edge cases like equal min/max (no range) and out-of-range clamping.
    - Weight validation: normalization to sum-to-1, negative weight clamping,
      and the all-zero fallback to equal weights.
    - End-to-end weighted score calculation on actual synthetic services.
    - Sensitivity: improving a metric must strictly increase its score and the
      aggregate QoS score.
"""

import pytest
from src.service_registry import CloudService, get_default_services, compute_reference_bounds
from src.qos_evaluator import (
    QoSEvaluator,
    normalize_lower_is_better,
    normalize_higher_is_better,
    validate_and_normalize_weights,
)


def test_normalize_lower_is_better():
    """Verify lower-is-better normalization formula: (max - val) / (max - min).

    For latency and cost, a LOWER raw value means a BETTER score.

    Test cases with reference range [20, 100]:
        - Mid-range (val=60): (100-60)/80 = 0.5
        - Best case (val=20, equals min): score = 1.0
        - Worst case (val=100, equals max): score = 0.0
        - Below min (val=10): clamped to 1.0 (better than the best baseline)
        - Above max (val=150): clamped to 0.0 (worse than the worst baseline)
    """
    # Mid-range: min=20, max=100, val=60 -> (100 - 60) / 80 = 40/80 = 0.5
    assert normalize_lower_is_better(60.0, 20.0, 100.0) == 0.5
    # Best case: val == min -> (100 - 20) / 80 = 1.0
    assert normalize_lower_is_better(20.0, 20.0, 100.0) == 1.0
    # Worst case: val == max -> (100 - 100) / 80 = 0.0
    assert normalize_lower_is_better(100.0, 20.0, 100.0) == 0.0
    # Clamping: val > max -> should clamp to 0.0
    assert normalize_lower_is_better(150.0, 20.0, 100.0) == 0.0
    # Clamping: val < min -> should clamp to 1.0
    assert normalize_lower_is_better(10.0, 20.0, 100.0) == 1.0


def test_normalize_lower_is_better_equal_min_max():
    """Verify handling when max == min without division by zero.

    When all services have the same value for a metric, the range is zero.
    The function should return 1.0 (treat everyone as equally good) rather
    than causing a division-by-zero error.
    """
    assert normalize_lower_is_better(50.0, 50.0, 50.0) == 1.0
    assert normalize_lower_is_better(60.0, 50.0, 50.0) == 1.0


def test_normalize_higher_is_better():
    """Verify higher-is-better normalization formula: (val - min) / (max - min).

    For availability and reliability, a HIGHER raw value means a BETTER score.

    Test cases with reference range [90, 100]:
        - Mid-range (val=95): (95-90)/10 = 0.5
        - Best case (val=100, equals max): score = 1.0
        - Worst case (val=90, equals min): score = 0.0
        - Above max (val=105): clamped to 1.0
        - Below min (val=80): clamped to 0.0
    """
    # Mid-range: min=90, max=100, val=95 -> (95 - 90) / 10 = 0.5
    assert normalize_higher_is_better(95.0, 90.0, 100.0) == 0.5
    # Best case: val == max -> 1.0
    assert normalize_higher_is_better(100.0, 90.0, 100.0) == 1.0
    # Worst case: val == min -> 0.0
    assert normalize_higher_is_better(90.0, 90.0, 100.0) == 0.0
    # Clamping: val > max -> clamp to 1.0
    assert normalize_higher_is_better(105.0, 90.0, 100.0) == 1.0
    # Clamping: val < min -> clamp to 0.0
    assert normalize_higher_is_better(80.0, 90.0, 100.0) == 0.0


def test_normalize_higher_is_better_equal_min_max():
    """Verify higher-is-better handling when max == min without division by zero.

    Same edge case as for lower-is-better: zero range should return 1.0.
    """
    assert normalize_higher_is_better(99.0, 99.0, 99.0) == 1.0
    assert normalize_higher_is_better(85.0, 99.0, 99.0) == 1.0


def test_weight_validation_and_normalization():
    """Verify weight validation and sum-to-1 normalization.

    The weight validation function must handle four cases:
        1. Equal positive weights → each becomes 0.25 after normalization.
        2. Unequal weights → proportional normalization preserving ratios.
        3. Negative weights → clamped to 0.0 before normalization.
        4. All-zero weights → fallback to equal weights (0.25 each).
    """
    # Case 1: Equal weights (2, 2, 2, 2) → each normalizes to 0.25
    weights = {"latency": 2.0, "cost": 2.0, "availability": 2.0, "reliability": 2.0}
    normalized = validate_and_normalize_weights(weights)
    assert pytest.approx(sum(normalized.values())) == 1.0
    assert pytest.approx(normalized["latency"]) == 0.25

    # Case 2: Unequal weights (4, 1, 3, 2) → total=10, latency=0.40, cost=0.10
    weights2 = {"latency": 4.0, "cost": 1.0, "availability": 3.0, "reliability": 2.0}
    normalized2 = validate_and_normalize_weights(weights2)
    assert pytest.approx(sum(normalized2.values())) == 1.0
    assert pytest.approx(normalized2["latency"]) == 0.40
    assert pytest.approx(normalized2["cost"]) == 0.10

    # Case 3: Negative weight for latency → clamped to 0.0; remaining (1, 1, 0) → 0.5, 0.5, 0.0
    weights3 = {"latency": -5.0, "cost": 1.0, "availability": 1.0, "reliability": 0.0}
    normalized3 = validate_and_normalize_weights(weights3)
    assert normalized3["latency"] == 0.0
    assert pytest.approx(normalized3["cost"]) == 0.5
    assert pytest.approx(normalized3["availability"]) == 0.5

    # Case 4: All zero weights → fallback to equal weights (0.25 each)
    weights_zero = {"latency": 0.0, "cost": 0.0, "availability": 0.0, "reliability": 0.0}
    normalized_zero = validate_and_normalize_weights(weights_zero)
    assert pytest.approx(sum(normalized_zero.values())) == 1.0
    for v in normalized_zero.values():
        assert pytest.approx(v) == 0.25


def test_weighted_score_calculation():
    """Verify total weighted QoS score calculation on a candidate service.

    Test strategy:
        - Use SVC-C02 (AetherCompute HighPerf) which has the lowest latency (25ms)
          and highest availability (99.95%) among Compute services.
        - Set weights to only consider latency (0.5) and availability (0.5), ignoring
          cost and reliability by setting their weights to 0.0.
        - Since SVC-C02 is the best on both weighted metrics, it should score 1.0.

    This test confirms the end-to-end pipeline: reference bounds → normalization → weighting.
    """
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    # SVC-C02 has latency=25ms (min among Compute) and availability=99.95% (max among Compute)
    svc = next(s for s in services if s.service_id == "SVC-C02")
    scores = evaluator.evaluate_service(
        svc,
        weights={"latency": 0.5, "cost": 0.0, "availability": 0.5, "reliability": 0.0},
    )

    # With only latency and availability weighted, and SVC-C02 being the best on both,
    # each score should be 1.0, so the aggregate should also be 1.0
    assert scores.latency_score == 1.0
    assert scores.availability_score == 1.0
    assert scores.qos_score == 1.0
    # Sanity check: score is always in the valid range
    assert 0.0 <= scores.qos_score <= 1.0


def test_evaluate_all_services():
    """Verify evaluate_all returns scores for every registered service.

    Test strategy:
        - Call evaluate_all() on the full default service list.
        - Confirm the result dictionary has one entry per service.
        - Confirm every score is within the valid [0.0, 1.0] range.
    """
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    results = evaluator.evaluate_all(services)
    # There should be exactly as many results as there are services
    assert len(results) == len(services)
    for s in services:
        assert s.service_id in results
        # Every QoS score must fall within the valid normalized range
        assert 0.0 <= results[s.service_id].qos_score <= 1.0


def test_latency_and_cost_lower_is_better_sensitivity():
    """Verify that reducing latency or cost strictly increases the QoS score.

    This is a sensitivity test: it confirms that the scoring system correctly
    rewards improvements in lower-is-better metrics. If we decrease latency
    (or cost) from its original value, the score must go up.
    """
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    svc = next(s for s in services if s.service_id == "SVC-C01")
    # Score with only latency and cost weighted
    initial_score = evaluator.evaluate_service(svc, weights={"latency": 0.5, "cost": 0.5, "availability": 0.0, "reliability": 0.0})

    # Improving latency (decreasing it) should increase both the latency score and the aggregate
    svc_improved_lat = CloudService.from_dict(svc.to_dict())
    svc_improved_lat.latency = max(25.0, svc.latency - 15.0)
    improved_lat_score = evaluator.evaluate_service(svc_improved_lat, weights={"latency": 0.5, "cost": 0.5, "availability": 0.0, "reliability": 0.0})
    assert improved_lat_score.latency_score > initial_score.latency_score
    assert improved_lat_score.qos_score > initial_score.qos_score

    # Improving cost (decreasing it) should increase both the cost score and the aggregate
    svc_improved_cost = CloudService.from_dict(svc.to_dict())
    svc_improved_cost.cost = max(0.015, svc.cost - 0.010)
    improved_cost_score = evaluator.evaluate_service(svc_improved_cost, weights={"latency": 0.5, "cost": 0.5, "availability": 0.0, "reliability": 0.0})
    assert improved_cost_score.cost_score > initial_score.cost_score
    assert improved_cost_score.qos_score > initial_score.qos_score


def test_availability_and_reliability_higher_is_better_sensitivity():
    """Verify that increasing availability or reliability strictly increases the QoS score.

    This is the counterpart to the latency/cost test above: it confirms that the
    scoring system correctly rewards improvements in higher-is-better metrics.
    """
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    # SVC-C03 (EcoCompute Budget) has the lowest availability and reliability among
    # Compute services, so there is room for improvement
    svc = next(s for s in services if s.service_id == "SVC-C03")
    initial_score = evaluator.evaluate_service(svc, weights={"latency": 0.0, "cost": 0.0, "availability": 0.5, "reliability": 0.5})

    # Increasing availability should improve the availability score and the aggregate
    svc_improved_avail = CloudService.from_dict(svc.to_dict())
    svc_improved_avail.availability = min(99.95, svc.availability + 0.5)
    improved_avail_score = evaluator.evaluate_service(svc_improved_avail, weights={"latency": 0.0, "cost": 0.0, "availability": 0.5, "reliability": 0.5})
    assert improved_avail_score.availability_score > initial_score.availability_score
    assert improved_avail_score.qos_score > initial_score.qos_score

    # Increasing reliability should improve the reliability score and the aggregate
    svc_improved_rel = CloudService.from_dict(svc.to_dict())
    svc_improved_rel.reliability = min(99.90, svc.reliability + 1.0)
    improved_rel_score = evaluator.evaluate_service(svc_improved_rel, weights={"latency": 0.0, "cost": 0.0, "availability": 0.5, "reliability": 0.5})
    assert improved_rel_score.reliability_score > initial_score.reliability_score
    assert improved_rel_score.qos_score > initial_score.qos_score
