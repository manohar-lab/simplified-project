"""
Automated Test Suite — test_qos.py
===================================
Covers QoS normalization, scoring, ranking, failure simulation,
restoration, and edge cases.
"""

import sys
import os
import math
import copy
import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from service_registry import CloudService, get_baseline_services, get_baseline_bounds, BASELINE_BOUNDS
from qos_evaluator import (
    evaluate_service, evaluate_all, validate_weights,
    DEFAULT_WEIGHTS, _safe_normalize,
)
from recommendation_engine import recommend, RecommendationResult
from failure_simulator import FailureSimulator
from explainability import generate_explanation, build_comparison_table, build_event_history_table


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def compute_services():
    return get_baseline_services("Compute")


@pytest.fixture
def storage_services():
    return get_baseline_services("Storage")


@pytest.fixture
def simulator():
    return FailureSimulator()


# ══════════════════════════════════════════════════════════════════
# 1. Benefit-type normalization
# ══════════════════════════════════════════════════════════════════

class TestBenefitNormalization:
    def test_availability_normalized_to_unit_interval(self):
        """Availability (higher is better) normalized ∈ [0, 1]."""
        # min=97.0, max=99.6 → SVC-C01 avail=99.5
        result = _safe_normalize(99.5, 97.0, 99.6, is_cost_type=False)
        assert 0.0 <= result <= 1.0
        assert abs(result - (99.5 - 97.0) / (99.6 - 97.0)) < 1e-6

    def test_reliability_normalized_correctly(self):
        result = _safe_normalize(98.0, 95.0, 98.6, is_cost_type=False)
        expected = (98.0 - 95.0) / (98.6 - 95.0)
        assert abs(result - expected) < 1e-6

    def test_at_minimum_gives_zero(self):
        assert _safe_normalize(97.0, 97.0, 99.6, is_cost_type=False) == pytest.approx(0.0)

    def test_at_maximum_gives_one(self):
        assert _safe_normalize(99.6, 97.0, 99.6, is_cost_type=False) == pytest.approx(1.0)


# ══════════════════════════════════════════════════════════════════
# 2. Cost-type normalization
# ══════════════════════════════════════════════════════════════════

class TestCostNormalization:
    def test_latency_normalized_lower_is_better(self):
        """Latency (lower is better) → low values get high normalized scores."""
        # min=28, max=102 → SVC-C01 lat=45
        result = _safe_normalize(45.0, 28.0, 102.0, is_cost_type=True)
        expected = (102.0 - 45.0) / (102.0 - 28.0)
        assert abs(result - expected) < 1e-6

    def test_cost_normalized_lower_is_better(self):
        result = _safe_normalize(0.040, 0.025, 0.067, is_cost_type=True)
        expected = (0.067 - 0.040) / (0.067 - 0.025)
        assert abs(result - expected) < 1e-6

    def test_at_minimum_gives_one(self):
        assert _safe_normalize(28.0, 28.0, 102.0, is_cost_type=True) == pytest.approx(1.0)

    def test_at_maximum_gives_zero(self):
        assert _safe_normalize(102.0, 28.0, 102.0, is_cost_type=True) == pytest.approx(0.0)


# ══════════════════════════════════════════════════════════════════
# 3. Aggregate QoS calculation
# ══════════════════════════════════════════════════════════════════

class TestAggregateQoS:
    def test_svc_c01_score_matches_research_paper(self, compute_services):
        """SVC-C01 aggregate QoS ≈ 0.8168 (research-paper target)."""
        svc = compute_services[0]
        assert svc.service_id == "SVC-C01"
        score, norms = evaluate_service(svc)
        # Verify individual normalized scores are in reasonable range
        assert 0.70 <= norms["latency"] <= 0.85
        assert 0.55 <= norms["cost"] <= 0.70
        assert 0.90 <= norms["availability"] <= 1.00
        assert 0.75 <= norms["reliability"] <= 0.90
        # Verify aggregate score
        assert 0.75 <= score <= 0.85

    def test_all_services_produce_valid_scores(self, compute_services):
        for svc in compute_services:
            score, norms = evaluate_service(svc)
            assert 0.0 <= score <= 1.0, f"{svc.name} score out of range: {score}"
            for m, v in norms.items():
                assert 0.0 <= v <= 1.0, f"{svc.name}.{m} normalized to {v}"

    def test_scores_are_deterministic(self, compute_services):
        scores1 = [evaluate_service(s)[0] for s in compute_services]
        scores2 = [evaluate_service(s)[0] for s in compute_services]
        assert scores1 == scores2


# ══════════════════════════════════════════════════════════════════
# 4. Weight validation
# ══════════════════════════════════════════════════════════════════

class TestWeightValidation:
    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            validate_weights({"latency": -0.1, "cost": 0.5})

    def test_empty_weights_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_weights({})

    def test_weights_auto_normalized(self):
        w = validate_weights({"latency": 2.0, "cost": 2.0, "availability": 2.0, "reliability": 2.0})
        assert abs(sum(w.values()) - 1.0) < 1e-6

    def test_zero_total_weight_raises(self):
        with pytest.raises(ValueError, match="positive"):
            validate_weights({"latency": 0.0, "cost": 0.0})


# ══════════════════════════════════════════════════════════════════
# 5. Ranking
# ══════════════════════════════════════════════════════════════════

class TestRanking:
    def test_services_ranked_descending(self, compute_services):
        ranked = evaluate_all(compute_services)
        scores = [r[1] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_svc_c01_is_top_ranked(self, compute_services):
        ranked = evaluate_all(compute_services)
        assert ranked[0][0].service_id == "SVC-C01"

    def test_deterministic_tie_breaking(self):
        """When scores are tied, services are sorted alphabetically by ID."""
        s1 = CloudService("B-SVC", "B", "Compute", 45, 0.04, 99.5, 98.0)
        s2 = CloudService("A-SVC", "A", "Compute", 45, 0.04, 99.5, 98.0)
        ranked = evaluate_all([s1, s2])
        assert ranked[0][0].service_id == "A-SVC"


# ══════════════════════════════════════════════════════════════════
# 6. Exclusion of unavailable services
# ══════════════════════════════════════════════════════════════════

class TestUnavailableExclusion:
    def test_unavailable_service_excluded_from_recommendation(self, compute_services):
        compute_services[0].status = "UNAVAILABLE"  # SVC-C01
        result = recommend(compute_services, "Compute")
        assert result.selected_service is not None
        assert result.selected_service.service_id != "SVC-C01"

    def test_excluded_list_populated(self, compute_services):
        compute_services[0].status = "UNAVAILABLE"
        result = recommend(compute_services, "Compute")
        ids = [s.service_id for s in result.excluded_services]
        assert "SVC-C01" in ids


# ══════════════════════════════════════════════════════════════════
# 7. Automatic reselection after failure
# ══════════════════════════════════════════════════════════════════

class TestReselectionAfterFailure:
    def test_outage_triggers_reselection(self, compute_services, simulator):
        # Initially SVC-C01 is best
        r1 = recommend(compute_services, "Compute")
        assert r1.selected_service.service_id == "SVC-C01"
        # Outage on SVC-C01
        simulator.simulate_outage(compute_services[0])
        r2 = recommend(compute_services, "Compute")
        assert r2.selected_service.service_id != "SVC-C01"

    def test_latency_spike_changes_ranking(self, compute_services, simulator):
        simulator.inject_latency_spike(compute_services[0], delta=200.0)
        result = recommend(compute_services, "Compute")
        # With massive latency spike, SVC-C01 should no longer be top
        assert result.selected_service.service_id != "SVC-C01"


# ══════════════════════════════════════════════════════════════════
# 8. Service restoration
# ══════════════════════════════════════════════════════════════════

class TestRestoration:
    def test_restore_returns_to_baseline(self, compute_services, simulator):
        baselines = get_baseline_services("Compute")
        svc = compute_services[0]
        original_latency = svc.latency
        simulator.inject_latency_spike(svc)
        assert svc.latency > original_latency
        simulator.restore_service(svc, baselines)
        assert svc.latency == original_latency
        assert svc.status == "AVAILABLE"

    def test_reset_restores_all_services(self, compute_services, simulator):
        simulator.simulate_outage(compute_services[0])
        simulator.inject_latency_spike(compute_services[1])
        simulator.reset_simulation(compute_services, "Compute")
        for svc in compute_services:
            assert svc.status == "AVAILABLE"
        baselines = get_baseline_services("Compute")
        for svc, bl in zip(compute_services, baselines):
            assert svc.latency == bl.latency
            assert svc.availability == bl.availability

    def test_repeated_restore_idempotent(self, compute_services, simulator):
        baselines = get_baseline_services("Compute")
        svc = compute_services[0]
        simulator.inject_latency_spike(svc)
        simulator.restore_service(svc, baselines)
        lat1 = svc.latency
        simulator.restore_service(svc, baselines)
        assert svc.latency == lat1


# ══════════════════════════════════════════════════════════════════
# 9. Empty service registry
# ══════════════════════════════════════════════════════════════════

class TestEmptyRegistry:
    def test_recommend_empty_list(self):
        result = recommend([], "Compute")
        assert result.selected_service is None
        assert result.all_unavailable is True

    def test_evaluate_all_empty(self):
        assert evaluate_all([]) == []


# ══════════════════════════════════════════════════════════════════
# 10. All services unavailable
# ══════════════════════════════════════════════════════════════════

class TestAllUnavailable:
    def test_no_eligible_service(self, compute_services):
        for svc in compute_services:
            svc.status = "UNAVAILABLE"
        result = recommend(compute_services, "Compute")
        assert result.selected_service is None
        assert result.all_unavailable is True
        assert "unavailable" in result.reason.lower()


# ══════════════════════════════════════════════════════════════════
# 11. Identical metric values
# ══════════════════════════════════════════════════════════════════

class TestIdenticalMetrics:
    def test_equal_bounds_gives_score_one(self):
        """When min == max, normalization returns 1.0."""
        assert _safe_normalize(50.0, 50.0, 50.0, is_cost_type=True) == 1.0
        assert _safe_normalize(50.0, 50.0, 50.0, is_cost_type=False) == 1.0

    def test_nan_returns_zero(self):
        assert _safe_normalize(float("nan"), 0, 100, is_cost_type=False) == 0.0

    def test_inf_returns_zero(self):
        assert _safe_normalize(float("inf"), 0, 100, is_cost_type=False) == 0.0

    def test_none_returns_zero(self):
        assert _safe_normalize(None, 0, 100, is_cost_type=False) == 0.0


# ══════════════════════════════════════════════════════════════════
# 12. Repeated failure operations
# ══════════════════════════════════════════════════════════════════

class TestRepeatedOperations:
    def test_double_outage_raises(self, compute_services, simulator):
        simulator.simulate_outage(compute_services[0])
        with pytest.raises(ValueError, match="already unavailable"):
            simulator.simulate_outage(compute_services[0])

    def test_spike_on_unavailable_raises(self, compute_services, simulator):
        simulator.simulate_outage(compute_services[0])
        with pytest.raises(ValueError, match="already unavailable"):
            simulator.inject_latency_spike(compute_services[0])

    def test_event_history_accumulates(self, compute_services, simulator):
        simulator.inject_latency_spike(compute_services[0])
        simulator.inject_latency_spike(compute_services[1])
        assert len(simulator.get_history()) == 2


# ══════════════════════════════════════════════════════════════════
# 13. Explainability
# ══════════════════════════════════════════════════════════════════

class TestExplainability:
    def test_explanation_contains_service_name(self, compute_services):
        result = recommend(compute_services, "Compute")
        explanation = generate_explanation(
            result.selected_service, result.selected_score,
            result.selected_normalized, result.runner_up,
            result.runner_up_score, result.score_margin,
            result.excluded_services,
        )
        assert result.selected_service.name in explanation

    def test_explanation_no_eligible(self):
        explanation = generate_explanation(None, 0, {}, None, 0, 0, [])
        assert "No eligible" in explanation

    def test_comparison_table_has_all_services(self, compute_services):
        ranked = evaluate_all(compute_services)
        df = build_comparison_table(ranked)
        assert len(df) == len(compute_services)

    def test_event_history_table_empty(self):
        df = build_event_history_table([])
        assert len(df) == 0


# ══════════════════════════════════════════════════════════════════
# 14. Category filtering
# ══════════════════════════════════════════════════════════════════

class TestCategoryFiltering:
    def test_compute_category_returns_compute_service(self, compute_services):
        result = recommend(compute_services, "Compute")
        assert result.selected_service.category == "Compute"

    def test_wrong_category_returns_no_service(self, compute_services):
        result = recommend(compute_services, "Storage")
        assert result.selected_service is None

    def test_storage_category_works(self, storage_services):
        result = recommend(storage_services, "Storage")
        assert result.selected_service is not None
        assert result.selected_service.category == "Storage"


# ══════════════════════════════════════════════════════════════════
# 15. Simulation event history
# ══════════════════════════════════════════════════════════════════

class TestEventHistory:
    def test_event_records_previous_and_new_state(self, compute_services, simulator):
        svc = compute_services[0]
        old_lat = svc.latency
        simulator.inject_latency_spike(svc)
        evt = simulator.get_history()[-1]
        assert evt.previous_state["latency"] == old_lat
        assert evt.updated_state["latency"] > old_lat

    def test_clear_history(self, simulator, compute_services):
        simulator.inject_latency_spike(compute_services[0])
        assert len(simulator.get_history()) > 0
        simulator.clear_history()
        assert len(simulator.get_history()) == 0
