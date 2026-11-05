"""Unit tests for src/analytics.py covering health classification, history tracking, and charts."""

import pytest
from src.service_registry import get_default_services, compute_reference_bounds
from src.qos_evaluator import QoSEvaluator
from src.failure_simulator import FailureSimulator
from src.analytics import (
    classify_service_health,
    HEALTH_HEALTHY,
    HEALTH_DEGRADED,
    HEALTH_UNAVAILABLE,
    HistoryTracker,
    build_qos_comparison_chart,
    build_qos_radar_chart,
    build_individual_metric_charts,
    build_health_donut_chart,
    build_before_after_chart,
    build_history_timeline_chart,
)


def test_classify_service_health():
    """Verify health status classification across various service conditions."""
    services = get_default_services()
    svc = services[0]

    # Baseline state -> HEALTHY
    assert classify_service_health(svc) == HEALTH_HEALTHY

    # Latency increase -> DEGRADED
    svc.latency += 50.0
    assert classify_service_health(svc) == HEALTH_DEGRADED
    svc.latency = svc.baseline["latency"]

    # Availability drop -> DEGRADED
    svc.availability -= 10.0
    assert classify_service_health(svc) == HEALTH_DEGRADED
    svc.availability = svc.baseline["availability"]

    # Reliability drop -> DEGRADED
    svc.reliability -= 5.0
    assert classify_service_health(svc) == HEALTH_DEGRADED
    svc.reliability = svc.baseline["reliability"]

    # Cost increase -> DEGRADED
    svc.cost += 0.05
    assert classify_service_health(svc) == HEALTH_DEGRADED
    svc.cost = svc.baseline["cost"]

    # Outage -> UNAVAILABLE
    svc.operational_status = "UNAVAILABLE"
    assert classify_service_health(svc) == HEALTH_UNAVAILABLE


def test_history_tracker():
    """Verify simulation snapshot recording, retrieval, and reset."""
    simulator = FailureSimulator()
    services = simulator.get_all_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    tracker = HistoryTracker()
    assert len(tracker.snapshots) == 0

    # Record initial baseline snapshot
    snap0 = tracker.record_snapshot(
        action="Initial Baseline",
        target_service_id="ALL",
        target_service_name="All Services",
        message="Initial state",
        services=services,
        evaluator=evaluator,
    )
    assert snap0.step == 0
    assert len(tracker.snapshots) == 1
    assert "SVC-C01" in snap0.services

    # Inject failure and record second snapshot
    simulator.inject_latency_spike("SVC-C01", 100.0)
    snap1 = tracker.record_snapshot(
        action="Latency Spike",
        target_service_id="SVC-C01",
        target_service_name="NovaCompute Standard",
        message="Latency +100ms",
        services=simulator.get_all_services(),
        evaluator=evaluator,
    )
    assert snap1.step == 1
    assert len(tracker.snapshots) == 2
    assert snap1.services["SVC-C01"].latency == snap0.services["SVC-C01"].latency + 100.0
    assert snap1.services["SVC-C01"].health_status == HEALTH_DEGRADED

    # Test history DataFrame extraction
    df = tracker.get_service_history_df("SVC-C01")
    assert len(df) == 2
    assert "latency" in df.columns
    assert df.iloc[0]["latency"] < df.iloc[1]["latency"]

    # Test reset
    tracker.reset()
    assert len(tracker.snapshots) == 0


def test_chart_builders():
    """Verify that all Plotly chart builders construct valid figures with proper data."""
    simulator = FailureSimulator()
    services = simulator.get_services_by_category("Compute")
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    # 1. QoS Comparison Bar Chart
    fig_bar = build_qos_comparison_chart(
        services=services,
        evaluator=evaluator,
        weights=None,
        recommended_id="SVC-C01",
        category="Compute",
    )
    assert fig_bar is not None
    assert len(fig_bar.data) > 0

    # 2. QoS Radar Chart
    fig_radar = build_qos_radar_chart(
        services=services,
        evaluator=evaluator,
        recommended_id="SVC-C01",
        selected_service_ids=["SVC-C01", "SVC-C02"],
    )
    assert fig_radar is not None
    assert len(fig_radar.data) == 2

    # 3. Individual Metric Charts
    metric_figs = build_individual_metric_charts(services)
    assert "latency" in metric_figs
    assert "cost" in metric_figs
    assert "availability" in metric_figs
    assert "reliability" in metric_figs

    # 4. Health Donut Chart
    fig_donut = build_health_donut_chart(services)
    assert fig_donut is not None
    assert len(fig_donut.data) == 1

    # 5. Before & After Chart
    fig_before_after = build_before_after_chart(
        target_service_id="SVC-C01",
        target_service_name="NovaCompute Standard",
        action="Latency Spike",
        before={"latency": 45.0, "availability": 99.9, "reliability": 99.5, "qos_score": 0.81},
        after={"latency": 195.0, "availability": 99.9, "reliability": 99.5, "qos_score": 0.52},
    )
    assert fig_before_after is not None
    assert len(fig_before_after.data) >= 2

    # 6. History Timeline Chart
    tracker = HistoryTracker()
    tracker.record_snapshot(
        action="Baseline",
        target_service_id="ALL",
        target_service_name="All",
        message="Initial",
        services=services,
        evaluator=evaluator,
    )
    simulator.inject_latency_spike("SVC-C01", 100.0)
    tracker.record_snapshot(
        action="Latency Spike",
        target_service_id="SVC-C01",
        target_service_name="NovaCompute Standard",
        message="Spike",
        services=simulator.get_all_services(),
        evaluator=evaluator,
    )
    df_hist = tracker.get_service_history_df("SVC-C01")
    fig_timeline = build_history_timeline_chart(df_hist, "SVC-C01", "NovaCompute Standard")
    assert fig_timeline is not None
    assert len(fig_timeline.data) == 4
