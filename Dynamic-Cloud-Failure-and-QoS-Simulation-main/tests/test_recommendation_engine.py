"""Unit tests for the Recommendation Engine."""

import pytest
from src.service_registry import CloudService, get_default_services, compute_reference_bounds
from src.qos_evaluator import QoSEvaluator
from src.failure_simulator import FailureSimulator
from src.recommendation_engine import RecommendationEngine


def setup_engine():
    """Helper to initialize simulator and recommendation engine."""
    sim = FailureSimulator()
    bounds = compute_reference_bounds(sim.get_all_services())
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)
    return sim, evaluator, engine


def test_deterministic_recommendation():
    """Verify recommendation is deterministic under identical state and weights."""
    sim, evaluator, engine = setup_engine()
    weights = {"latency": 0.35, "cost": 0.25, "availability": 0.25, "reliability": 0.15}

    res1 = engine.recommend(sim.get_all_services(), category="Compute", weights=weights)
    res2 = engine.recommend(sim.get_all_services(), category="Compute", weights=weights)

    assert res1.has_eligible_service is True
    assert res2.has_eligible_service is True
    assert res1.selected_service.service_id == res2.selected_service.service_id
    assert res1.selected_scores.qos_score == res2.selected_scores.qos_score


def test_exclusion_of_unavailable_services():
    """Verify an unavailable service is excluded even if it had the highest QoS score."""
    sim, evaluator, engine = setup_engine()
    weights = {"latency": 0.5, "cost": 0.0, "availability": 0.5, "reliability": 0.0}

    # Under this weight, SVC-C02 has latency=25ms, availability=99.95% (highest score)
    res_initial = engine.recommend(sim.get_all_services(), category="Compute", weights=weights)
    assert res_initial.selected_service.service_id == "SVC-C02"

    # Simulate outage on SVC-C02
    sim.simulate_outage("SVC-C02")

    res_after = engine.recommend(
        sim.get_all_services(),
        category="Compute",
        weights=weights,
        previously_selected_id="SVC-C02",
    )

    # SVC-C02 must be excluded from selected_service
    assert res_after.selected_service.service_id != "SVC-C02"
    assert any(s.service_id == "SVC-C02" for s, reason in res_after.excluded_services)
    assert "UNAVAILABLE" in res_after.selection_reason


def test_latency_spike_triggers_reselection():
    """Verify that a severe latency spike on the top candidate leads to alternative selection."""
    sim, evaluator, engine = setup_engine()
    # Heavily weight latency
    weights = {"latency": 0.8, "cost": 0.0, "availability": 0.1, "reliability": 0.1}

    initial_rec = engine.recommend(sim.get_all_services(), category="Compute", weights=weights)
    winner_id = initial_rec.selected_service.service_id

    # Inject large latency spike on top candidate (e.g., +400ms)
    sim.inject_latency_spike(winner_id, spike_ms=400.0)

    new_rec = engine.recommend(
        sim.get_all_services(),
        category="Compute",
        weights=weights,
        previously_selected_id=winner_id,
    )

    assert new_rec.selected_service.service_id != winner_id
    assert new_rec.has_eligible_service is True
    assert "Reselection trigger" in new_rec.selection_reason


def test_category_filtering():
    """Verify recommendation only evaluates services from the requested category."""
    sim, evaluator, engine = setup_engine()
    res = engine.recommend(sim.get_all_services(), category="Storage")
    assert res.has_eligible_service is True
    assert res.selected_service.category == "Storage"
    assert all(s.category == "Storage" for s, _ in res.ranked_eligible)


def test_equal_metric_values_recommendation():
    """Verify recommendation handles candidate pool where services have identical metrics."""
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

    res = engine.recommend([svc_a, svc_b], category="TestCat")
    assert res.has_eligible_service is True
    # In equal score situation, tiebreaker selects SVC-T01 deterministically
    assert res.selected_service.service_id == "SVC-T01"
    assert res.selected_scores.qos_score == 1.0


def test_no_eligible_service_behavior():
    """Verify graceful handling when all services in category are unavailable."""
    sim, evaluator, engine = setup_engine()
    compute_services = [s for s in sim.get_all_services() if s.category == "Compute"]

    # Mark every compute service unavailable
    for s in compute_services:
        sim.simulate_outage(s.service_id)

    res = engine.recommend(sim.get_all_services(), category="Compute")
    assert res.has_eligible_service is False
    assert res.selected_service is None
    assert res.selected_scores is None
    assert "All" in res.status_message
    assert "UNAVAILABLE" in res.status_message
    assert len(res.excluded_services) == len(compute_services)

