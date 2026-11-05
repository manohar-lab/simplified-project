"""Unit tests for src/explainability.py covering reselection decision explainability, comparisons, and audit trail."""

import pytest
from src.service_registry import get_default_services, compute_reference_bounds
from src.qos_evaluator import QoSEvaluator
from src.failure_simulator import FailureSimulator
from src.recommendation_engine import RecommendationEngine
from src.explainability import (
    compare_service_metrics,
    generate_detailed_reselection_explanation,
    build_three_way_comparison_dataframe,
    build_candidate_comparison_table,
    ReselectionAuditTrail,
)


def test_compare_service_metrics():
    """Verify metric comparison and improvement directionality."""
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    svc_a = services[0]  # NovaCompute: lat=45.0, cost=0.040, avail=99.90, rel=99.50
    svc_b = services[1]  # AetherCompute: lat=25.0, cost=0.085, avail=99.95, rel=99.80

    score_a = evaluator.evaluate_service(svc_a)
    score_b = evaluator.evaluate_service(svc_b)

    diffs = compare_service_metrics(svc_a, score_a, svc_b, score_b)

    assert "latency" in diffs
    assert "cost" in diffs
    assert "availability" in diffs
    assert "reliability" in diffs
    assert "qos_score" in diffs

    # svc_a (45ms) has higher latency than svc_b (25ms), so latency is not improved for svc_a
    assert diffs["latency"].delta == 20.0
    assert diffs["latency"].improved is False

    # svc_a ($0.040) has lower cost than svc_b ($0.085), so cost is improved for svc_a
    assert diffs["cost"].delta == -0.045
    assert diffs["cost"].improved is True


def test_generate_detailed_reselection_explanation():
    """Verify dynamic explanation generation for initial baseline, failure, and outage."""
    simulator = FailureSimulator()
    services = simulator.get_services_by_category("Compute")
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)

    # 1. Baseline Explanation
    rec1 = engine.recommend(services, "Compute")
    exp1 = generate_detailed_reselection_explanation(
        recommendation=rec1,
        evaluator=evaluator,
        weights=None,
        prev_service_id=None,
        all_category_services=services,
    )
    assert exp1["has_recommendation"] is True
    assert exp1["is_reselection"] is False
    assert exp1["winner"].service_id == "SVC-C01"
    assert exp1["runner_up"] is not None

    # 2. Outage on SVC-C01 -> Reselection of SVC-C02
    simulator.simulate_outage("SVC-C01")
    services_after_outage = simulator.get_services_by_category("Compute")
    rec2 = engine.recommend(services_after_outage, "Compute", previously_selected_id="SVC-C01")
    exp2 = generate_detailed_reselection_explanation(
        recommendation=rec2,
        evaluator=evaluator,
        weights=None,
        prev_service_id="SVC-C01",
        all_category_services=services_after_outage,
    )
    assert exp2["has_recommendation"] is True
    assert exp2["is_reselection"] is True
    assert exp2["reselection_type"] == "OUTAGE"
    assert "UNAVAILABLE" in exp2["details"][0]
    assert exp2["prev_service"].service_id == "SVC-C01"

    # 3. Universal outage
    for s in services_after_outage:
        simulator.simulate_outage(s.service_id)
    all_down = simulator.get_services_by_category("Compute")
    rec3 = engine.recommend(all_down, "Compute")
    exp3 = generate_detailed_reselection_explanation(
        recommendation=rec3,
        evaluator=evaluator,
        weights=None,
        prev_service_id="SVC-C02",
        all_category_services=all_down,
    )
    assert exp3["has_recommendation"] is False
    assert "No Eligible Service" in exp3["headline"]


def test_candidate_comparison_table():
    """Verify candidate table respects actual engine ranking and separates excluded services."""
    simulator = FailureSimulator()
    simulator.simulate_outage("SVC-C01")
    services = simulator.get_services_by_category("Compute")
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)

    rec = engine.recommend(services, "Compute")
    df = build_candidate_comparison_table(rec, evaluator, None, services)

    assert len(df) == len(services)
    # The first row must be the selected service (#1)
    assert df.iloc[0]["Rank"] == "#1"
    assert df.iloc[0]["Service ID"] == rec.selected_service.service_id
    assert "Selected Service" in df.iloc[0]["Role"]

    # Excluded service must be flagged as Ineligible
    excluded_rows = df[df["Eligibility"] == "❌ Ineligible"]
    assert len(excluded_rows) == 1
    assert excluded_rows.iloc[0]["Service ID"] == "SVC-C01"


def test_build_three_way_comparison_dataframe():
    """Verify 3-way comparative matrix construction and metric difference rows."""
    simulator = FailureSimulator()
    services = simulator.get_services_by_category("Compute")
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)

    rec = engine.recommend(services, "Compute")
    exp = generate_detailed_reselection_explanation(
        recommendation=rec,
        evaluator=evaluator,
        weights=None,
        prev_service_id="SVC-C02",
        all_category_services=services,
    )
    df_3way = build_three_way_comparison_dataframe(exp)
    assert not df_3way.empty
    assert "QoS Metric" in df_3way.columns
    assert "Newly Selected Winner" in df_3way.columns
    assert "Best Alternative (Runner-Up)" in df_3way.columns
    assert len(df_3way) == 6



def test_reselection_audit_trail():
    """Verify audit trail record capture, history preservation, and reset."""
    simulator = FailureSimulator()
    services = simulator.get_services_by_category("Compute")
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)
    engine = RecommendationEngine(evaluator)

    trail = ReselectionAuditTrail()
    assert len(trail.records) == 0

    # Initial decision record
    rec1 = engine.recommend(services, "Compute")
    r1 = trail.record_decision(
        trigger_event="Baseline Initialization",
        recommendation=rec1,
        evaluator=evaluator,
        weights=None,
        prev_service_id=None,
        all_category_services=services,
    )
    assert r1.sequence_number == 1
    assert r1.new_service_id == "SVC-C01"
    assert len(trail.records) == 1

    # Simulate spike and reselection
    simulator.inject_latency_spike("SVC-C01", 150.0)
    services2 = simulator.get_services_by_category("Compute")
    rec2 = engine.recommend(services2, "Compute", previously_selected_id="SVC-C01")

    r2 = trail.record_decision(
        trigger_event="Latency Spike (+150ms)",
        recommendation=rec2,
        evaluator=evaluator,
        weights=None,
        prev_service_id="SVC-C01",
        all_category_services=services2,
    )
    assert r2.sequence_number == 2
    assert r2.prev_service_id == "SVC-C01"
    assert len(trail.records) == 2

    # Check DataFrame representation
    df = trail.to_dataframe()
    assert len(df) == 2
    assert "Trigger Event" in df.columns

    # Reset
    trail.reset()
    assert len(trail.records) == 0
