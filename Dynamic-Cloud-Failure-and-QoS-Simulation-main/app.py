"""Dynamic Cloud Failure and QoS-Aware Service Reselection.

Streamlit Dashboard for demonstrating cloud service failure detection,
QoS degradation, and transparent reselection of eligible alternative services.

This is the main entry point of the application. It builds an interactive web
dashboard using Streamlit and Plotly where users can:
    1. View candidate cloud services, real-time health states, and baseline bounds.
    2. Inject failures (latency spikes, outages, availability drops) or restore services.
    3. Watch the recommendation engine automatically re-evaluate candidates and reselect.
    4. Explore QoS analytics (bar chart, radar chart, individual metric charts).
    5. Analyze failure impact with before-and-after comparisons.
    6. Inspect transparent, data-driven explainability and decision comparisons.
    7. Track simulation history and view the reselection audit trail.

Run this file with:  streamlit run app.py
"""

from __future__ import annotations
import copy
import html
import time
from typing import Dict, Any, List

# --- Third-party imports ---
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Project module imports ---
from src.service_registry import get_default_services, compute_reference_bounds, CloudService
from src.qos_evaluator import QoSEvaluator, validate_and_normalize_weights
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla
from src.hysteresis_config import HysteresisConfig, DEFAULT_HYSTERESIS_CONFIG
from src.monitoring_config import MonitoringConfig, DEFAULT_MONITORING_CONFIG
from src.monitoring_engine import MonitoringEngine, STATUS_ACTIVE
from src.override_manager import (
    MODE_AUTOMATIC,
    MODE_MANUAL,
    ManualOverrideManager,
)
from src.failure_simulator import FailureSimulator
from src.recommendation_engine import RecommendationEngine
from src.analytics import (
    classify_service_health,
    HistoryTracker,
    HEALTH_HEALTHY,
    HEALTH_DEGRADED,
    HEALTH_UNAVAILABLE,
    HEALTH_RECOVERED,
    build_qos_comparison_chart,
    build_qos_radar_chart,
    build_individual_metric_charts,
    build_health_donut_chart,
    build_before_after_chart,
    build_history_timeline_chart,
)
from src.explainability import (
    generate_detailed_reselection_explanation,
    build_three_way_comparison_dataframe,
    build_candidate_comparison_table,
    ReselectionAuditTrail,
)


# =========================================================================
# Page Configuration & Custom CSS Styling
# =========================================================================
st.set_page_config(
    page_title="Dynamic Cloud Failure & QoS Reselection",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #475569;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 16px;
    }
    .badge-available {
        background-color: #DCFCE7;
        color: #15803D;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-degraded {
        background-color: #FEF3C7;
        color: #B45309;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-unavailable {
        background-color: #FEE2E2;
        color: #B91C1C;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-recommended {
        background-color: #DBEAFE;
        color: #1D4ED8;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .explain-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #2563EB;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .section-desc {
        color: #64748B;
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================================
# Session State Initialization
# =========================================================================
if "simulator" not in st.session_state:
    st.session_state.simulator = FailureSimulator()

if "prev_recommended_id" not in st.session_state:
    st.session_state.prev_recommended_id = None

if "last_switch_step" not in st.session_state:
    st.session_state.last_switch_step = None

if "last_action_summary" not in st.session_state:
    st.session_state.last_action_summary = None

if "last_action_detail" not in st.session_state:
    st.session_state.last_action_detail = None

if "history_tracker" not in st.session_state:
    st.session_state.history_tracker = HistoryTracker()

if "reselection_audit_trail" not in st.session_state:
    st.session_state.reselection_audit_trail = ReselectionAuditTrail()

if "override_manager" not in st.session_state:
    st.session_state.override_manager = ManualOverrideManager()

if "override_feedback" not in st.session_state:
    st.session_state.override_feedback = None

simulator: FailureSimulator = st.session_state.simulator
history_tracker: HistoryTracker = st.session_state.history_tracker
reselection_audit_trail: ReselectionAuditTrail = st.session_state.reselection_audit_trail
override_manager: ManualOverrideManager = st.session_state.override_manager

all_services = simulator.get_all_services()
reference_bounds = compute_reference_bounds(all_services)
evaluator = QoSEvaluator(reference_bounds)
engine = RecommendationEngine(evaluator)

if "monitoring_engine" not in st.session_state:
    st.session_state.monitoring_engine = MonitoringEngine(
        evaluator=evaluator,
        recommendation_engine=engine,
        config=DEFAULT_MONITORING_CONFIG,
        override_manager=override_manager,
    )

monitoring_engine: MonitoringEngine = st.session_state.monitoring_engine
monitoring_engine.override_manager = override_manager
st.session_state["_is_full_app_render"] = True


# Helper to snapshot state for failure analysis before/after comparison
def extract_service_state(svc: CloudService, weights: Dict[str, float]) -> Dict[str, Any]:
    """Capture a dictionary snapshot of a service's raw and scored state."""
    scores = evaluator.evaluate_service(svc, weights)
    return {
        "service_id": svc.service_id,
        "name": svc.name,
        "category": svc.category,
        "latency": svc.latency,
        "cost": svc.cost,
        "availability": svc.availability,
        "reliability": svc.reliability,
        "operational_status": svc.operational_status,
        "qos_score": scores.qos_score,
        "health_status": classify_service_health(svc),
    }


# =========================================================================
# Sidebar: Simulation Controls & QoS Priority Sliders
# =========================================================================
with st.sidebar:
    st.header("⚙️ Simulation Controls")

    # --- Category Selection ---
    available_categories = sorted(list(set(s.category for s in all_services)))
    selected_category = st.selectbox(
        "Service Category",
        options=available_categories,
        index=0,
        help="Select the cloud service category to inspect and evaluate.",
    )

    st.markdown("---")

    # --- SLA Constraint Configuration ---
    st.subheader("🛡️ SLA Eligibility Constraints")
    st.caption("Hard constraints: services violating any threshold are disqualified.")

    cat_default_sla = get_default_sla_config(selected_category)
    sla_max_lat = st.number_input(
        "Max Allowed Latency (ms)",
        min_value=10.0,
        max_value=1000.0,
        value=float(cat_default_sla.max_latency),
        step=10.0,
        help="Maximum acceptable response time in milliseconds.",
    )
    sla_min_avail = st.number_input(
        "Min Required Availability (%)",
        min_value=50.0,
        max_value=100.0,
        value=float(cat_default_sla.min_availability),
        step=0.5,
        help="Minimum acceptable availability percentage.",
    )
    sla_min_rel = st.number_input(
        "Min Required Reliability (%)",
        min_value=50.0,
        max_value=100.0,
        value=float(cat_default_sla.min_reliability),
        step=0.5,
        help="Minimum acceptable reliability percentage.",
    )

    active_sla = SLAConfig(
        max_latency=float(sla_max_lat),
        min_availability=float(sla_min_avail),
        min_reliability=float(sla_min_rel),
    )

    st.markdown("---")

    # --- Hysteresis & Anti-Flapping Configuration ---
    st.subheader("⚖️ Hysteresis & Anti-Flapping")
    st.caption("Prevent flapping by requiring a significant score improvement to switch services.")

    h_min_delta = st.slider(
        "Min QoS Improvement (ΔQoS)",
        min_value=0.00,
        max_value=0.50,
        value=float(DEFAULT_HYSTERESIS_CONFIG.min_qos_delta),
        step=0.01,
        help="Minimum score improvement (0.0 to 1.0) required to switch from the currently selected service.",
    )
    h_cooldown_steps = st.number_input(
        "Switching Cooldown (Steps)",
        min_value=0,
        max_value=10,
        value=int(DEFAULT_HYSTERESIS_CONFIG.cooldown_steps),
        step=1,
        help="Number of simulation steps that must elapse before another performance-driven switch is allowed.",
    )
    active_hysteresis = HysteresisConfig(
        min_qos_delta=float(h_min_delta),
        cooldown_steps=int(h_cooldown_steps),
    )

    st.markdown("---")

    # --- Periodic Automatic Monitoring Configuration ---
    st.subheader("📡 Periodic Automatic Monitoring")
    st.caption("Automatically reassess service health, SLA compliance, and failover status.")

    m_enabled = st.toggle(
        "Enable Automatic Monitoring",
        value=bool(monitoring_engine.is_active),
        help="Toggle periodic automatic health reassessment (ACTIVE / PAUSED).",
    )
    m_interval = st.slider(
        "Monitoring Interval (seconds)",
        min_value=2.0,
        max_value=60.0,
        value=float(monitoring_engine.config.interval_seconds),
        step=1.0,
        help="Frequency at which registered services are automatically reassessed.",
    )

    if m_enabled and not monitoring_engine.is_active:
        monitoring_engine.resume()
    elif not m_enabled and monitoring_engine.is_active:
        monitoring_engine.pause()

    active_monitoring_config = MonitoringConfig(
        interval_seconds=float(m_interval),
        enabled=bool(m_enabled),
    )
    if (
        active_monitoring_config.interval_seconds != monitoring_engine.config.interval_seconds
        or active_monitoring_config.enabled != monitoring_engine.config.enabled
    ):
        monitoring_engine.update_config(active_monitoring_config)

    st.markdown("---")

    # --- QoS Metric Weight Sliders ---
    st.subheader("🎯 QoS Metric Priorities")
    st.caption("Adjust importance weights (normalized automatically):")

    w_lat = st.slider("Latency Weight (lower is better)", 0.0, 1.0, 0.35, 0.05)
    w_cost = st.slider("Cost Weight (lower is better)", 0.0, 1.0, 0.20, 0.05)
    w_avail = st.slider("Availability Weight (higher is better)", 0.0, 1.0, 0.30, 0.05)
    w_rel = st.slider("Reliability Weight (higher is better)", 0.0, 1.0, 0.15, 0.05)

    user_weights = {
        "latency": w_lat,
        "cost": w_cost,
        "availability": w_avail,
        "reliability": w_rel,
    }
    normalized_weights = validate_and_normalize_weights(user_weights)

    st.caption(
        f"**Effective Weights:** Lat: `{normalized_weights['latency']:.2f}`, "
        f"Cost: `{normalized_weights['cost']:.2f}`, "
        f"Avail: `{normalized_weights['availability']:.2f}`, "
        f"Rel: `{normalized_weights['reliability']:.2f}`"
    )

    st.markdown("---")

    # Baseline tracking initialization
    if len(history_tracker.snapshots) == 0:
        history_tracker.record_snapshot(
            action="Baseline Initialized",
            target_service_id="ALL",
            target_service_name="All Services",
            message="System initialized with baseline QoS values.",
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )

    # --- Failure Injection Target Selection ---
    st.subheader("⚡ Failure Injection Target")

    category_services = [s for s in all_services if s.category == selected_category]
    service_options = {s.service_id: f"{s.service_id} - {s.name}" for s in category_services}

    target_service_id = st.selectbox(
        "Target Service",
        options=list(service_options.keys()),
        format_func=lambda x: service_options[x],
        help="Choose a candidate service to inject faults or restore.",
    )

    col_act1, col_act2 = st.columns(2)
    with col_act1:
        spike_val = st.number_input("Spike (ms)", min_value=10, max_value=1000, value=150, step=25)
    with col_act2:
        drop_val = st.number_input("Avail Drop (%)", min_value=1, max_value=100, value=25, step=5)

    target_svc = simulator.get_service(target_service_id)
    before_state = extract_service_state(target_svc, normalized_weights) if target_svc else {}

    btn_spike = st.button("⚡ Inject Latency Spike", use_container_width=True)
    btn_outage = st.button("🔴 Simulate Outage", use_container_width=True)
    btn_drop = st.button("📉 Reduce Availability", use_container_width=True)
    btn_restore = st.button("🟢 Restore Service", use_container_width=True)
    st.markdown("---")
    btn_reset = st.button("🔄 Reset All Services", use_container_width=True, type="secondary")

    def _finalize_sidebar_action(prev_choice_id: str | None, trigger_label: str) -> None:
        """Re-evaluate recommendation after a sidebar fault/recovery action, respecting operating mode safety."""
        current_step_idx = len(history_tracker.snapshots)
        is_manual_for_cat = (
            override_manager.is_manual_active
            and override_manager.category == selected_category
        )
        new_rec = engine.recommend(
            simulator.get_all_services(),
            selected_category,
            normalized_weights,
            prev_choice_id,
            sla_config=active_sla,
            hysteresis_config=active_hysteresis,
            current_step=current_step_idx,
            last_switch_step=st.session_state.last_switch_step,
            operating_mode=override_manager.mode if is_manual_for_cat else MODE_AUTOMATIC,
            manual_service_id=override_manager.requested_service_id if is_manual_for_cat else None,
            manual_override_reason=override_manager.reason,
        )
        if new_rec.override_terminated and is_manual_for_cat:
            failed_id = override_manager.requested_service_id
            replacement_id = new_rec.selected_service.service_id if new_rec.selected_service else None
            override_manager.handle_emergency_termination(
                failed_service_id=failed_id,
                replacement_service_id=replacement_id,
                reason=new_rec.override_termination_reason,
                category=selected_category,
            )
            st.session_state.override_feedback = ("error", new_rec.override_termination_reason)
            st.session_state["_recent_override_terminated"] = True
            trigger_label = f"{trigger_label} -> Emergency Override Termination"

        if new_rec.decision_type in ("SWITCHED", "EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION"):
            st.session_state.last_switch_step = current_step_idx

        reselection_audit_trail.record_decision(
            trigger_event=trigger_label,
            recommendation=new_rec,
            evaluator=evaluator,
            weights=normalized_weights,
            prev_service_id=prev_choice_id,
            all_category_services=simulator.get_services_by_category(selected_category),
        )
        st.session_state["_recent_button_action"] = True
        st.rerun()

    # --- Button Event Handlers ---
    if btn_spike and target_service_id:
        prev_choice_id = st.session_state.prev_recommended_id
        ok, msg = simulator.inject_latency_spike(target_service_id, float(spike_val))
        after_state = extract_service_state(target_svc, normalized_weights)
        st.session_state.last_action_summary = {
            "action": "Latency Spike",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": f"{before_state['latency']:.1f}ms",
            "after": f"{after_state['latency']:.1f}ms",
            "message": msg,
        }
        st.session_state.last_action_detail = {
            "action": "Latency Spike",
            "target_service_id": target_service_id,
            "target_service_name": target_svc.name,
            "before": before_state,
            "after": after_state,
            "recovered": False,
        }
        history_tracker.record_snapshot(
            action=f"Latency Spike (+{spike_val}ms)",
            target_service_id=target_service_id,
            target_service_name=target_svc.name,
            message=msg,
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        _finalize_sidebar_action(prev_choice_id, f"Latency Spike (+{spike_val}ms) on {target_service_id}")

    if btn_outage and target_service_id:
        prev_choice_id = st.session_state.prev_recommended_id
        ok, msg = simulator.simulate_outage(target_service_id)
        after_state = extract_service_state(target_svc, normalized_weights)
        st.session_state.last_action_summary = {
            "action": "Simulate Outage",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": before_state["operational_status"],
            "after": "UNAVAILABLE",
            "message": msg,
        }
        st.session_state.last_action_detail = {
            "action": "Simulate Outage",
            "target_service_id": target_service_id,
            "target_service_name": target_svc.name,
            "before": before_state,
            "after": after_state,
            "recovered": False,
        }
        history_tracker.record_snapshot(
            action="Service Outage",
            target_service_id=target_service_id,
            target_service_name=target_svc.name,
            message=msg,
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        _finalize_sidebar_action(prev_choice_id, f"Outage Triggered on {target_service_id}")

    if btn_drop and target_service_id:
        prev_choice_id = st.session_state.prev_recommended_id
        ok, msg = simulator.reduce_availability(target_service_id, float(drop_val))
        after_state = extract_service_state(target_svc, normalized_weights)
        st.session_state.last_action_summary = {
            "action": "Reduce Availability",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": f"{before_state['availability']:.2f}%",
            "after": f"{after_state['availability']:.2f}%",
            "message": msg,
        }
        st.session_state.last_action_detail = {
            "action": "Reduce Availability",
            "target_service_id": target_service_id,
            "target_service_name": target_svc.name,
            "before": before_state,
            "after": after_state,
            "recovered": False,
        }
        history_tracker.record_snapshot(
            action=f"Availability Drop (-{drop_val}%)",
            target_service_id=target_service_id,
            target_service_name=target_svc.name,
            message=msg,
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        _finalize_sidebar_action(prev_choice_id, f"Availability Drop (-{drop_val}%) on {target_service_id}")

    if btn_restore and target_service_id:
        prev_choice_id = st.session_state.prev_recommended_id
        ok, msg = simulator.restore_service(target_service_id)
        after_state = extract_service_state(target_svc, normalized_weights)
        st.session_state.last_action_summary = {
            "action": "Restore Baseline",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": f"Degraded ({before_state['health_status']})",
            "after": "Restored (HEALTHY)",
            "message": msg,
        }
        st.session_state.last_action_detail = {
            "action": "Restore Baseline",
            "target_service_id": target_service_id,
            "target_service_name": target_svc.name,
            "before": before_state,
            "after": after_state,
            "recovered": True,
        }
        history_tracker.record_snapshot(
            action="Service Restored",
            target_service_id=target_service_id,
            target_service_name=target_svc.name,
            message=msg,
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        _finalize_sidebar_action(prev_choice_id, f"Service Restored on {target_service_id}")

    if btn_reset:
        simulator.reset_simulation()
        monitoring_engine.reset(clear_events=False)
        override_manager.reset(clear_events=False)
        st.session_state.override_feedback = None
        st.session_state.prev_recommended_id = None
        st.session_state.last_switch_step = None
        st.session_state.last_action_summary = {
            "action": "Reset All",
            "service_id": "ALL",
            "service_name": "All Candidate Services",
            "before": "Various Modified States",
            "after": "Pristine Baseline States",
            "message": "All services reset to baseline QoS specifications.",
        }
        st.session_state.last_action_detail = None
        history_tracker.record_snapshot(
            action="Reset Simulation",
            target_service_id="ALL",
            target_service_name="All Services",
            message="All candidate services reset to baseline.",
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        reset_rec = engine.recommend(
            simulator.get_all_services(),
            selected_category,
            normalized_weights,
            None,
            sla_config=active_sla,
            hysteresis_config=active_hysteresis,
            current_step=0,
            last_switch_step=None,
        )
        reselection_audit_trail.record_decision(
            trigger_event="Reset All Services to Baseline",
            recommendation=reset_rec,
            evaluator=evaluator,
            weights=normalized_weights,
            prev_service_id=None,
            all_category_services=simulator.get_services_by_category(selected_category),
        )
        st.session_state["_recent_button_action"] = True
        st.rerun()


# =========================================================================
# Main Panel: Header & Project Context
# =========================================================================
st.markdown('<div class="main-title">☁️ Dynamic Cloud Failure & QoS-Aware Service Reselection</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    'Autonomous cloud service health monitoring, failure detection, multi-criteria QoS evaluation, '
    'and explainable service reselection prototype (inspired by IEEE ICIMIA-2025).'
    '</div>',
    unsafe_allow_html=True,
)

# Handle category transitions explicitly if a manual override belonged to another category
if override_manager.is_manual_active and override_manager.category != selected_category:
    prev_cat = override_manager.category
    override_manager.clear_override(
        reason=f"Category changed from '{prev_cat}' to '{selected_category}'; automatic mode restored."
    )
    st.session_state.prev_recommended_id = None
    st.session_state.override_feedback = (
        "info",
        f"Category changed to '{selected_category}'. Manual override from '{prev_cat}' was cleared and Automatic Mode restored.",
    )

# Run recommendation engine on current state & operating mode
current_step_idx = len(history_tracker.snapshots)
raw_prev_id = st.session_state.prev_recommended_id
category_service_ids = {s.service_id for s in category_services}
old_prev_id = raw_prev_id if (raw_prev_id is not None and raw_prev_id in category_service_ids) else None

is_manual_active_for_cat = (
    override_manager.is_manual_active
    and override_manager.category == selected_category
)

recommendation = engine.recommend(
    services=all_services,
    category=selected_category,
    weights=normalized_weights,
    previously_selected_id=old_prev_id,
    sla_config=active_sla,
    hysteresis_config=active_hysteresis,
    current_step=current_step_idx,
    last_switch_step=st.session_state.last_switch_step,
    operating_mode=override_manager.mode if is_manual_active_for_cat else MODE_AUTOMATIC,
    manual_service_id=override_manager.requested_service_id if is_manual_active_for_cat else None,
    manual_override_reason=override_manager.reason,
)

was_button_action = bool(st.session_state.pop("_recent_button_action", False))
recent_override_terminated = bool(st.session_state.pop("_recent_override_terminated", False))

if recommendation.override_terminated and is_manual_active_for_cat:
    failed_manual_id = override_manager.requested_service_id
    replacement_id = recommendation.selected_service.service_id if recommendation.selected_service else None
    terminated_now = override_manager.handle_emergency_termination(
        failed_service_id=failed_manual_id,
        replacement_service_id=replacement_id,
        reason=recommendation.override_termination_reason,
        category=selected_category,
    )
    st.session_state.override_feedback = ("error", recommendation.override_termination_reason)
    if terminated_now and not was_button_action:
        reselection_audit_trail.record_decision(
            trigger_event="Policy / SLA Change -> Emergency Override Termination",
            recommendation=recommendation,
            evaluator=evaluator,
            weights=normalized_weights,
            prev_service_id=failed_manual_id,
            all_category_services=category_services,
        )
    recent_override_terminated = True

# Generate intelligent explainability breakdown
explanation_data = generate_detailed_reselection_explanation(
    recommendation=recommendation,
    evaluator=evaluator,
    weights=normalized_weights,
    prev_service_id=old_prev_id,
    all_category_services=category_services,
    last_action=st.session_state.last_action_detail,
)
if recent_override_terminated:
    explanation_data["override_terminated"] = True
    if "Emergency Override Termination" not in explanation_data.get("reselection_trigger", ""):
        explanation_data["reselection_trigger"] = f"Emergency Override Termination ({explanation_data.get('reselection_trigger', 'Failover')})"

# Initialize baseline decision in audit trail if empty
if len(reselection_audit_trail.records) == 0 and recommendation.has_eligible_service:
    reselection_audit_trail.record_decision(
        trigger_event="Baseline Initialization",
        recommendation=recommendation,
        evaluator=evaluator,
        weights=normalized_weights,
        prev_service_id=None,
        all_category_services=category_services,
    )

recommended_id = recommendation.selected_service.service_id if recommendation.selected_service else None
if recommended_id is not None:
    if old_prev_id != recommended_id:
        st.session_state.last_switch_step = current_step_idx
        if (
            not was_button_action
            and not recent_override_terminated
            and len(reselection_audit_trail.records) > 0
            and old_prev_id is not None
        ):
            reselection_audit_trail.record_decision(
                trigger_event="Configuration / Policy Re-evaluation",
                recommendation=recommendation,
                evaluator=evaluator,
                weights=normalized_weights,
                prev_service_id=old_prev_id,
                all_category_services=category_services,
            )
    st.session_state.prev_recommended_id = recommended_id
else:
    st.session_state.prev_recommended_id = None

# Keep monitoring engine synchronized with current parameters, operating mode & active choice
monitoring_engine.evaluator = evaluator
monitoring_engine.recommendation_engine = engine
monitoring_engine.override_manager = override_manager
monitoring_engine.sync_external_selection(
    category=selected_category,
    selected_id=recommended_id,
    switch_step=st.session_state.last_switch_step,
)

st.session_state["active_category"] = selected_category
st.session_state["active_sla"] = active_sla
st.session_state["active_hysteresis"] = active_hysteresis
st.session_state["active_weights"] = normalized_weights


# Action banner if recent action occurred
if st.session_state.last_action_summary:
    summary = st.session_state.last_action_summary
    st.info(
        f"🔔 **Latest Simulation Action [{summary['action']}]:** {summary['message']} "
        f"*(Target: `{summary['service_id']} - {summary['service_name']}` | "
        f"Before: `{summary['before']}` ➜ After: `{summary['after']}`)*"
    )


# =========================================================================
# Operating Mode & Manual Service Override Control (Phase 4)
# =========================================================================
st.markdown("### 🎛️ Operating Mode & Service Selection Control")

eligible_pairs = recommendation.ranked_eligible
eligible_service_ids = [s.service_id for s, _ in eligible_pairs]
eligible_labels = {
    s.service_id: f"{s.service_id} - {s.name} (QoS: {sc.qos_score:.4f} | Lat: {s.latency:.1f}ms)"
    for s, sc in eligible_pairs
}

active_mode = MODE_MANUAL if recommendation.manual_override_active else MODE_AUTOMATIC
mode_bg = "#F3E8FF" if active_mode == MODE_MANUAL else "#DBEAFE"
mode_fg = "#6B21A8" if active_mode == MODE_MANUAL else "#1E40AF"
mode_icon = "🎯" if active_mode == MODE_MANUAL else "🤖"

if not recommendation.has_eligible_service or recommendation.selected_service is None:
    sel_summary_txt = "None (No SLA-Compliant Service Available)"
    sel_kind_txt = "Unavailable / All Ineligible"
elif recommendation.decision_type == "MANUAL_OVERRIDE":
    sel_summary_txt = f"{recommendation.selected_service.service_id} - {recommendation.selected_service.name}"
    sel_kind_txt = "Manually Overridden Service"
elif recommendation.decision_type in ("EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION") or recent_override_terminated:
    sel_summary_txt = f"{recommendation.selected_service.service_id} - {recommendation.selected_service.name}"
    sel_kind_txt = "Emergency Replacement Service"
else:
    sel_summary_txt = f"{recommendation.selected_service.service_id} - {recommendation.selected_service.name}"
    sel_kind_txt = "Automatically Selected Service"

auto_best = recommendation.automatic_best_service
auto_best_score = recommendation.automatic_best_score
auto_ref_txt = (
    f"{auto_best.service_id} - {auto_best.name} (QoS: {auto_best_score.qos_score:.4f})"
    if auto_best is not None and auto_best_score is not None
    else "None Available"
)
sla_status_txt = (
    f"Compliant ({len(eligible_pairs)}/{len(category_services)} eligible)"
    if len(eligible_pairs) > 0
    else f"No Compliant Service (0/{len(category_services)} eligible)"
)

st.markdown(
    f"""
    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; display: flex; flex-wrap: wrap; gap: 18px; align-items: center;">
        <span style="background-color: {mode_bg}; color: {mode_fg}; font-weight: 700; padding: 3px 10px; border-radius: 999px; font-size: 0.85rem;">
            {mode_icon} Mode: {html.escape(active_mode)}
        </span>
        <span style="color: #1E293B; font-size: 0.9rem;">Active Selection: <b>{html.escape(sel_summary_txt)}</b> <i>({html.escape(sel_kind_txt)})</i></span>
        <span style="color: #475569; font-size: 0.9rem;">Automatic Rank #1: <b>{html.escape(auto_ref_txt)}</b></span>
        <span style="color: #475569; font-size: 0.9rem;">SLA Compliance: <b>{html.escape(sla_status_txt)}</b></span>
        <span style="color: #475569; font-size: 0.9rem;">Manual Override: <b>{"ACTIVE" if override_manager.is_manual_active else "INACTIVE"}</b></span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(f"**Selection Reason:** {recommendation.decision_reason}")

feedback = st.session_state.pop("override_feedback", None)
if feedback is not None:
    fb_level, fb_msg = feedback
    if fb_level == "error":
        st.error(f"🛑 {fb_msg}")
    elif fb_level == "success":
        st.success(f"✅ {fb_msg}")
    else:
        st.info(f"ℹ️ {fb_msg}")

ov_col1, ov_col2, ov_col3, ov_col4 = st.columns([0.36, 0.28, 0.18, 0.18])
with ov_col1:
    if eligible_service_ids:
        default_ov_idx = 0
        if override_manager.is_manual_active and override_manager.requested_service_id in eligible_service_ids:
            default_ov_idx = eligible_service_ids.index(override_manager.requested_service_id)
        chosen_manual_id = st.selectbox(
            "Eligible Services for Manual Selection",
            options=eligible_service_ids,
            index=default_ov_idx,
            format_func=lambda sid: eligible_labels.get(sid, sid),
            key="manual_override_target_select",
            help="Only operationally AVAILABLE and SLA-compliant candidates in the active category are selectable.",
        )
    else:
        st.selectbox(
            "Eligible Services for Manual Selection",
            options=["NONE_ELIGIBLE"],
            index=0,
            format_func=lambda _: "No eligible SLA-compliant services available",
            disabled=True,
            key="manual_override_target_select",
        )
        chosen_manual_id = None

with ov_col2:
    manual_reason_text = st.text_input(
        "Override Reason (Optional)",
        value=override_manager.reason if override_manager.is_manual_active else "",
        placeholder="e.g., Operator preference / maintenance check",
        key="manual_override_reason_input",
    )

with ov_col3:
    st.markdown("<div style='margin-top: 26px;'></div>", unsafe_allow_html=True)
    btn_activate_override = st.button(
        "🎯 Activate Manual Override",
        key="btn_activate_manual_override",
        use_container_width=True,
        disabled=(len(eligible_service_ids) == 0),
    )

with ov_col4:
    st.markdown("<div style='margin-top: 26px;'></div>", unsafe_allow_html=True)
    btn_clear_override = st.button(
        "🔄 Return to Automatic",
        key="btn_clear_manual_override",
        use_container_width=True,
        disabled=(not override_manager.is_manual_active),
    )

if btn_activate_override:
    prior_active_id = recommended_id
    ok_ov, msg_ov, _ = override_manager.request_manual_override(
        services=all_services,
        category=selected_category,
        requested_service_id=chosen_manual_id,
        sla_config=active_sla,
        reason=manual_reason_text,
    )
    if ok_ov and chosen_manual_id is not None:
        man_rec = engine.recommend(
            services=all_services,
            category=selected_category,
            weights=normalized_weights,
            previously_selected_id=prior_active_id,
            sla_config=active_sla,
            hysteresis_config=active_hysteresis,
            current_step=len(history_tracker.snapshots),
            last_switch_step=st.session_state.last_switch_step,
            operating_mode=MODE_MANUAL,
            manual_service_id=chosen_manual_id,
            manual_override_reason=override_manager.reason,
        )
        history_tracker.record_snapshot(
            action="Manual Override Activated",
            target_service_id=chosen_manual_id,
            target_service_name=man_rec.selected_service.name if man_rec.selected_service else chosen_manual_id,
            message=msg_ov,
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        reselection_audit_trail.record_decision(
            trigger_event=f"Manual Override Activated -> {chosen_manual_id}",
            recommendation=man_rec,
            evaluator=evaluator,
            weights=normalized_weights,
            prev_service_id=prior_active_id,
            all_category_services=category_services,
        )
        st.session_state.last_switch_step = len(history_tracker.snapshots)
        st.session_state.prev_recommended_id = chosen_manual_id
        monitoring_engine.sync_external_selection(
            category=selected_category,
            selected_id=chosen_manual_id,
            switch_step=st.session_state.last_switch_step,
        )
        st.session_state.last_action_summary = {
            "action": "Manual Override Activated",
            "service_id": chosen_manual_id,
            "service_name": man_rec.selected_service.name if man_rec.selected_service else chosen_manual_id,
            "before": prior_active_id or "None",
            "after": chosen_manual_id,
            "message": msg_ov,
        }
        st.session_state.override_feedback = ("success", msg_ov)
        st.session_state["_recent_button_action"] = True
        st.rerun()
    else:
        st.session_state.override_feedback = ("error", msg_ov)
        st.rerun()

if btn_clear_override:
    prior_manual_id = override_manager.requested_service_id or recommended_id
    cleared_ok = override_manager.clear_override(
        reason=f"Operator cleared manual override on '{prior_manual_id}' and restored Automatic Mode."
    )
    if cleared_ok:
        auto_rec = engine.recommend(
            services=all_services,
            category=selected_category,
            weights=normalized_weights,
            previously_selected_id=None,
            sla_config=active_sla,
            hysteresis_config=active_hysteresis,
            current_step=len(history_tracker.snapshots),
            last_switch_step=st.session_state.last_switch_step,
            operating_mode=MODE_AUTOMATIC,
        )
        auto_winner_id = auto_rec.selected_service.service_id if auto_rec.selected_service else None
        auto_winner_name = auto_rec.selected_service.name if auto_rec.selected_service else "None"
        history_tracker.record_snapshot(
            action="Manual Override Cleared",
            target_service_id=auto_winner_id or "NONE",
            target_service_name=auto_winner_name,
            message=f"Returned to Automatic Mode (selected: {auto_winner_id}).",
            services=simulator.get_all_services(),
            evaluator=evaluator,
            weights=normalized_weights,
        )
        if auto_rec.has_eligible_service:
            reselection_audit_trail.record_decision(
                trigger_event=f"Manual Override Cleared -> Automatic Mode ({auto_winner_id})",
                recommendation=auto_rec,
                evaluator=evaluator,
                weights=normalized_weights,
                prev_service_id=prior_manual_id,
                all_category_services=category_services,
            )
        st.session_state.last_switch_step = len(history_tracker.snapshots)
        st.session_state.prev_recommended_id = auto_winner_id
        monitoring_engine.sync_external_selection(
            category=selected_category,
            selected_id=auto_winner_id,
            switch_step=st.session_state.last_switch_step,
        )
        st.session_state.last_action_summary = {
            "action": "Manual Override Cleared",
            "service_id": auto_winner_id or "NONE",
            "service_name": auto_winner_name,
            "before": prior_manual_id or "None",
            "after": auto_winner_id or "NONE",
            "message": f"Manual override cleared; control returned to Automatic Mode ({auto_winner_id}).",
        }
        st.session_state.override_feedback = (
            "info",
            f"Manual override cleared. Control returned to Automatic Mode ({auto_winner_id or 'None Available'}).",
        )
        st.session_state["_recent_button_action"] = True
        st.rerun()


# =========================================================================
# Periodic Automatic Service Monitoring Fragment (Phase 3)
# =========================================================================
def _periodic_monitoring_body() -> None:
    """Execute one periodic health reassessment cycle and render live monitoring telemetry."""
    mon: MonitoringEngine = st.session_state.monitoring_engine
    sim: FailureSimulator = st.session_state.simulator
    hist: HistoryTracker = st.session_state.history_tracker
    audit: ReselectionAuditTrail = st.session_state.reselection_audit_trail
    eval_obj: QoSEvaluator = mon.evaluator

    cat = st.session_state.get("active_category")
    sla = st.session_state.get("active_sla")
    hyst = st.session_state.get("active_hysteresis")
    wts = st.session_state.get("active_weights")
    was_full_app_render = bool(st.session_state.pop("_is_full_app_render", False))

    st.markdown("### 📡 Periodic Service Monitoring Dashboard")
    hdr_col1, hdr_col2 = st.columns([0.80, 0.20])
    with hdr_col2:
        manual_check = st.button(
            "🔍 Inspect Now",
            key="btn_monitoring_inspect_now",
            use_container_width=True,
            help="Immediately run one monitoring assessment cycle without waiting for the next timer tick.",
        )

    override_mgr: ManualOverrideManager = st.session_state.override_manager

    if manual_check or mon.is_active:
        cycle_res = mon.run_cycle(
            services=sim.get_all_services(),
            category=cat,
            weights=wts,
            sla_config=sla,
            hysteresis_config=hyst,
            previously_selected_id=st.session_state.prev_recommended_id,
            current_step=len(hist.snapshots),
            last_switch_step=st.session_state.last_switch_step,
            force=bool(manual_check),
            respect_interval=False,
            override_manager=override_mgr,
        )
    else:
        cycle_res = mon.last_cycle_result

    # Trigger full dashboard rerun when background tick or manual inspect detects changes
    if (
        not was_full_app_render
        and cycle_res is not None
        and cycle_res.status not in ("SKIPPED_OVERLAP", "SKIPPED_INTERVAL")
        and (cycle_res.reselection_triggered or cycle_res.changes_detected)
    ):
        if cycle_res.reselection_triggered and cycle_res.recommendation_result is not None:
            prev_id = st.session_state.prev_recommended_id
            new_id = cycle_res.selected_service_id
            cat_svcs = sim.get_services_by_category(cat)
            rec_res = cycle_res.recommendation_result

            if rec_res.override_terminated:
                st.session_state.override_feedback = (
                    "error",
                    rec_res.override_termination_reason
                    or f"Emergency termination of manual override: switched to {new_id or 'NONE'}.",
                )
                st.session_state["_recent_override_terminated"] = True

            if new_id is not None:
                st.session_state.last_switch_step = len(hist.snapshots)
            st.session_state.prev_recommended_id = new_id

            hist.record_snapshot(
                action=(
                    "Emergency Override Reselection"
                    if rec_res.override_terminated
                    else "Periodic Monitor Reselection"
                ),
                target_service_id=new_id or "NONE",
                target_service_name=cycle_res.selected_service_name or "None",
                message=rec_res.decision_reason,
                services=sim.get_all_services(),
                evaluator=eval_obj,
                weights=wts,
            )
            audit.record_decision(
                trigger_event=(
                    f"Emergency Override Failover (Cycle #{cycle_res.cycle_number})"
                    if rec_res.override_terminated
                    else f"Periodic Monitoring Cycle #{cycle_res.cycle_number}"
                ),
                recommendation=rec_res,
                evaluator=eval_obj,
                weights=wts,
                prev_service_id=prev_id,
                all_category_services=cat_svcs,
            )
            st.session_state.last_action_summary = {
                "action": (
                    "Emergency Manual Override Termination"
                    if rec_res.override_terminated
                    else "Automatic Periodic Reselection"
                ),
                "service_id": new_id or "NONE",
                "service_name": cycle_res.selected_service_name or "No Eligible Service",
                "before": prev_id or "None",
                "after": new_id or "NONE",
                "message": rec_res.decision_reason,
            }
        st.rerun()

    mon_summary = mon.get_status_summary()
    is_active_now = (mon_summary["status"] == STATUS_ACTIVE)
    badge_bg = "#DCFCE7" if is_active_now else "#FEF3C7"
    badge_fg = "#166534" if is_active_now else "#92400E"
    badge_icon = "🟢" if is_active_now else "⏸️"
    mode_label = "🎯 MANUAL_OVERRIDE" if override_mgr.is_manual_active else "🤖 AUTOMATIC"

    with hdr_col1:
        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 14px; display: flex; flex-wrap: wrap; gap: 18px; align-items: center;">
                <span style="background-color: {badge_bg}; color: {badge_fg}; font-weight: 700; padding: 3px 10px; border-radius: 999px; font-size: 0.85rem;">
                    {badge_icon} {html.escape(mon_summary['status'])}
                </span>
                <span style="color: #475569; font-size: 0.9rem;">Mode: <b>{mode_label}</b></span>
                <span style="color: #475569; font-size: 0.9rem;">Category: <b>{html.escape(str(cat))}</b></span>
                <span style="color: #475569; font-size: 0.9rem;">Interval: <b>{mon_summary['interval_seconds']:.0f}s</b></span>
                <span style="color: #475569; font-size: 0.9rem;">Cycles Executed: <b>#{mon_summary['cycle_count']}</b></span>
                <span style="color: #475569; font-size: 0.9rem;">Last Checked: <b>{html.escape(str(mon_summary['last_run_timestamp']))}</b></span>
                <span style="color: #475569; font-size: 0.9rem;">Next Expected Check: <b>{html.escape(str(mon_summary['next_expected_timestamp']))}</b></span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)
    mcol1.metric("Monitored Services", mon_summary["total_services"])
    mcol2.metric("Healthy Services", mon_summary["healthy_count"])
    mcol3.metric("Degraded Services", mon_summary["degraded_count"])
    mcol4.metric("Unavailable Services", mon_summary["unavailable_count"])
    mcol5.metric("SLA Violations", mon_summary["sla_violating_count"])

    active_svc_display = mon_summary["selected_service_id"] or "NONE"
    if cycle_res is not None and cycle_res.selected_service_name:
        active_svc_help = f"Active Service: {cycle_res.selected_service_id} - {cycle_res.selected_service_name}"
    else:
        active_svc_help = "Currently selected service in monitored category"
    mcol6.metric("Active Selected", active_svc_display, help=active_svc_help)

    recovered_ids = (
        [
            sid for sid, snap in cycle_res.service_snapshots.items()
            if snap.health_state == HEALTH_RECOVERED
        ]
        if cycle_res is not None
        else []
    )

    info_col1, info_col2 = st.columns(2)
    with info_col1:
        if cycle_res is not None and cycle_res.selected_service_id is None:
            st.error("🚫 **Automatic Reselection Status:** No eligible SLA-compliant service currently available.")
        elif cycle_res is not None and cycle_res.reselection_triggered:
            st.warning(
                f"🔄 **Automatic Reselection Triggered:** Switched active service to "
                f"`{cycle_res.selected_service_id} - {cycle_res.selected_service_name}`."
            )
        elif recovered_ids:
            st.info(
                f"💚 **Recovery Observed:** {', '.join(f'`{rid}`' for rid in recovered_ids)} restored to SLA compliance. "
                f"Active selection: `{active_svc_display}`."
            )
        else:
            st.success(
                f"✅ **Automatic Reselection Status:** Stable on `{active_svc_display}` (no unscheduled switch required)."
            )

    with info_col2:
        latest_evt = mon_summary.get("latest_event")
        if latest_evt:
            st.info(
                f"🧾 **Latest Event (`{latest_evt['event_type']}` @ {latest_evt['timestamp']}):** "
                f"{latest_evt['reason']}"
            )
        else:
            st.info("🧾 **Latest Event:** No monitoring events recorded yet.")


st.fragment(
    _periodic_monitoring_body,
    run_every=active_monitoring_config.interval_seconds if monitoring_engine.is_active else None,
    key="periodic_monitor_panel",
)()


# =========================================================================
# Dashboard Tabs Layout
# =========================================================================
tab_overview, tab_analytics, tab_failure, tab_history = st.tabs([
    "📌 Overview & Explainability",
    "📊 QoS Analytics",
    "⚡ Failure Analysis",
    "📜 Simulation & Decision History",
])


# =========================================================================
# Tab 1: Overview & Intelligent Recommendation Explainability
# =========================================================================
with tab_overview:
    # --- Configured SLA Thresholds & Hysteresis Banner ---
    st.markdown(
        f"""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-left: 4px solid #2563EB; border-radius: 6px; padding: 10px 16px; margin-bottom: 14px; display: flex; flex-wrap: wrap; gap: 24px; align-items: center;">
            <span style="font-weight: 700; color: #1E293B;">🛡️ Configured SLA Thresholds ({selected_category}):</span>
            <span style="color: #475569;">Max Latency: <b>&le; {active_sla.max_latency:.1f} ms</b></span>
            <span style="color: #475569;">Min Availability: <b>&ge; {active_sla.min_availability:.2f}%</b></span>
            <span style="color: #475569;">Min Reliability: <b>&ge; {active_sla.min_reliability:.2f}%</b></span>
            <span style="font-weight: 700; color: #1E293B; margin-left: 8px;">⚖️ Hysteresis:</span>
            <span style="color: #475569;">Min ΔQoS: <b>&ge; {active_hysteresis.min_qos_delta:.2f}</b></span>
            <span style="color: #475569;">Cooldown: <b>{active_hysteresis.cooldown_steps} step(s)</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- KPI Cards Row ---
    total_in_cat = len(category_services)
    eligible_in_cat = len(recommendation.ranked_eligible)
    excluded_in_cat = len(recommendation.excluded_services)
    unavailable_in_cat = len([s for s in category_services if s.operational_status == "UNAVAILABLE"])
    rec_name = recommendation.selected_service.name if recommendation.selected_service else "None (No SLA-Compliant Service)"
    rec_score = f"{recommendation.selected_scores.qos_score:.4f}" if recommendation.selected_scores else "N/A"

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    with kpi1:
        st.metric("Total Evaluated", total_in_cat)
    with kpi2:
        st.metric(
            "SLA Eligible",
            eligible_in_cat,
            delta="Compliant" if eligible_in_cat > 0 else "0 Compliant",
            delta_color="normal" if eligible_in_cat > 0 else "inverse",
        )
    with kpi3:
        st.metric(
            "Excluded / Ineligible",
            excluded_in_cat,
            delta=f"{excluded_in_cat} Ineligible" if excluded_in_cat > 0 else "0 Ineligible",
            delta_color="inverse" if excluded_in_cat > 0 else "normal",
        )
    with kpi4:
        st.metric(
            "Unavailable / Down",
            unavailable_in_cat,
            delta=f"+{unavailable_in_cat} down" if unavailable_in_cat > 0 else "0 down",
            delta_color="inverse" if unavailable_in_cat > 0 else "normal",
        )
    with kpi5:
        if recommendation.manual_override_active and recommendation.selected_scores:
            kpi5_delta = f"🎯 Manual Override | QoS: {rec_score}"
        elif recommendation.override_terminated and recommendation.selected_scores:
            kpi5_delta = f"🚨 Emergency Replacement | QoS: {rec_score}"
        elif recommendation.selected_scores:
            kpi5_delta = f"🤖 Automatic | QoS: {rec_score}"
        else:
            kpi5_delta = "No Selection"
        st.metric(
            "Selected Service",
            rec_name,
            delta=kpi5_delta,
        )

    st.markdown("---")

    # --- Recommendation Decision Breakdown ---
    st.subheader("💡 Recommendation Decision Breakdown")
    st.caption("Inspect the active recommendation, reselection trigger, prior choice status, and decision explanation.")

    col_dec1, col_dec2, col_dec3 = st.columns(3)

    # Card 1: Prior Service State
    with col_dec1:
        prev_s = explanation_data.get("prev_service")
        prev_sc = explanation_data.get("prev_score")
        prev_h = explanation_data.get("prev_health", "N/A")
        if prev_s:
            p_status_badge = (
                "🔴 UNAVAILABLE (Outage)" if prev_s.operational_status == "UNAVAILABLE"
                else ("🟠 DEGRADED" if prev_h == HEALTH_DEGRADED else "🟢 HEALTHY")
            )
            st.markdown(
                f"""
                <div class="metric-card">
                    <div style="font-size:0.82rem; color:#64748B; font-weight:600; text-transform:uppercase;">Prior Selected Choice</div>
                    <div style="font-size:1.15rem; font-weight:700; color:#1E293B; margin:4px 0;">{prev_s.name} ({prev_s.service_id})</div>
                    <div>Status: <b>{p_status_badge}</b></div>
                    <div style="margin-top:4px; font-size:0.88rem; color:#475569;">
                        Prior QoS Score: <b>{prev_sc.qos_score:.4f}</b> | Latency: <b>{prev_s.latency:.1f}ms</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="metric-card">
                    <div style="font-size:0.82rem; color:#64748B; font-weight:600; text-transform:uppercase;">Prior Selected Choice</div>
                    <div style="font-size:1.15rem; font-weight:700; color:#1E293B; margin:4px 0;">None (Initial Baseline)</div>
                    <div>Status: <b>🟢 Initializing</b></div>
                    <div style="margin-top:4px; font-size:0.88rem; color:#475569;">First evaluation cycle of the simulation.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Card 2: Decision Trigger & Reason
    with col_dec2:
        reselect_trig = explanation_data.get("reselection_trigger", "Optimal Score Selection")
        reselect_type = explanation_data.get("reselection_type", "INITIAL")
        is_manual_dec = bool(recommendation.manual_override_active)
        is_emerg_dec = bool(recommendation.override_terminated) or reselect_type in (
            "EMERGENCY_OUTAGE",
            "EMERGENCY_SLA_VIOLATION",
            "OUTAGE",
            "SLA_VIOLATION",
        )
        type_icon = (
            "🚨" if is_emerg_dec
            else ("🎯" if is_manual_dec
                  else ("🛡️" if reselect_type == "RETAINED"
                        else ("🔄" if reselect_type == "SWITCHED"
                              else ("⚠️" if reselect_type == "DEGRADATION" else "🤖"))))
        )
        action_text = (
            "Emergency Override Termination & Failover"
            if recommendation.override_terminated
            else (
                "Manual Service Override Active"
                if is_manual_dec
                else (
                    "Service Retained (Anti-Flapping)"
                    if reselect_type == "RETAINED"
                    else ("Service Reselection" if explanation_data.get("is_reselection") else "Automatic Rank #1 Selection")
                )
            )
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size:0.82rem; color:#64748B; font-weight:600; text-transform:uppercase;">Decision Trigger</div>
                <div style="font-size:1.15rem; font-weight:700; color:#1E293B; margin:4px 0;">{type_icon} {html.escape(str(reselect_trig))}</div>
                <div>Action: <b>{action_text}</b> | Mode: <b>{html.escape(recommendation.operating_mode)}</b></div>
                <div style="margin-top:4px; font-size:0.88rem; color:#475569;">
                    Evaluated across {len(category_services)} services with active SLA &amp; Hysteresis thresholds.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Card 3: Newly Selected Winner
    with col_dec3:
        if recommendation.has_eligible_service and recommendation.selected_service:
            win = recommendation.selected_service
            win_sc = recommendation.selected_scores
            win_h = explanation_data.get("winner_health", "HEALTHY")
            w_badge = "🟢 HEALTHY" if win_h == HEALTH_HEALTHY else "🟠 DEGRADED"
            if recommendation.manual_override_active:
                role_badge = "🎯 MANUALLY OVERRIDDEN"
                card_title = "Manually Selected Service"
                card_accent = "#D97706"
            elif recommendation.override_terminated or recommendation.decision_type in (
                "EMERGENCY_OUTAGE",
                "EMERGENCY_SLA_VIOLATION",
            ):
                role_badge = "🚨 EMERGENCY REPLACEMENT"
                card_title = "Emergency Replacement Service"
                card_accent = "#DC2626"
            elif recommendation.decision_type == "RETAINED":
                role_badge = "🛡️ AUTOMATICALLY RETAINED"
                card_title = "Automatically Selected Service"
                card_accent = "#2563EB"
            else:
                role_badge = "🤖 AUTOMATICALLY SELECTED"
                card_title = "Automatically Selected Service"
                card_accent = "#2563EB"
            st.markdown(
                f"""
                <div class="metric-card" style="border-left: 4px solid {card_accent};">
                    <div style="font-size:0.82rem; color:{card_accent}; font-weight:600; text-transform:uppercase;">{card_title}</div>
                    <div style="font-size:1.15rem; font-weight:700; color:#1E293B; margin:4px 0;">{html.escape(win.name)} ({html.escape(win.service_id)})</div>
                    <div>Status: <b>{w_badge}</b> | Role: <span class="badge-recommended">{role_badge}</span></div>
                    <div style="margin-top:4px; font-size:0.88rem; color:#1D4ED8; font-weight:600;">
                        Aggregate QoS Score: {win_sc.qos_score:.4f} / 1.0000
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="metric-card" style="border-left: 4px solid #EF4444;">
                    <div style="font-size:0.82rem; color:#EF4444; font-weight:600; text-transform:uppercase;">Newly Recommended Winner</div>
                    <div style="font-size:1.15rem; font-weight:700; color:#EF4444; margin:4px 0;">No SLA-Compliant Service Available</div>
                    <div>Status: <b>🔴 ALL CANDIDATES INELIGIBLE</b></div>
                    <div style="margin-top:4px; font-size:0.88rem; color:#B91C1C;">Every candidate is either unavailable or violates configured SLA thresholds.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Phase 2: Hysteresis & Anti-Flapping Status ---
    st.subheader("⚖️ Hysteresis & Anti-Flapping Status")
    st.caption("Real-time monitoring of flapping protection, score improvement threshold, and switching cooldown.")

    col_h1, col_h2, col_h3, col_h4 = st.columns(4)
    with col_h1:
        st.metric(
            "Current Selection",
            recommendation.selected_service.name if recommendation.selected_service else "None",
            delta=f"QoS: {recommendation.selected_scores.qos_score:.4f}" if recommendation.selected_scores else "N/A",
        )
    with col_h2:
        alt_name = recommendation.best_alternative.name if recommendation.best_alternative else "None"
        alt_sc = f"QoS: {recommendation.best_alternative_score.qos_score:.4f}" if recommendation.best_alternative_score else "N/A"
        st.metric("Best Alternative", alt_name, delta=alt_sc)
    with col_h3:
        delta_val = recommendation.qos_improvement
        thresh_val = active_hysteresis.min_qos_delta
        st.metric(
            "QoS Margin (ΔQoS)",
            f"{delta_val:+.4f}",
            delta=f"Required: ≥ {thresh_val:.4f}",
            delta_color="normal" if delta_val >= thresh_val else "off",
        )
    with col_h4:
        cd_active = recommendation.cooldown_active
        cd_status = "🔒 Active (Locked)" if cd_active else "🟢 Inactive (Unlocked)"
        st.metric(
            "Cooldown Window",
            cd_status,
            delta=f"{active_hysteresis.cooldown_steps} step(s)" if active_hysteresis.cooldown_steps > 0 else "Disabled",
        )

    # Decision Banner Callout
    dec_type = recommendation.decision_type
    if dec_type == "RETAINED":
        if recommendation.cooldown_active:
            st.warning(
                f"🛡️ **Service Retained (Cooldown Active):** Candidate `{alt_name}` offered higher QoS, "
                f"but switching is locked by cooldown to prevent rapid switching. ({recommendation.decision_reason})"
            )
        else:
            st.info(
                f"🛡️ **Service Retained (Anti-Flapping Active):** Current service `{recommendation.selected_service.name}` "
                f"remains compliant. Challenger `{alt_name}` improved QoS by `{recommendation.qos_improvement:+.4f}`, "
                f"which does not exceed the required hysteresis margin `ΔQoS ≥ {active_hysteresis.min_qos_delta:.4f}`. "
                f"Flapping has been prevented."
            )
    elif dec_type == "SWITCHED":
        st.success(
            f"🔄 **Service Reselected (Hysteresis Satisfied):** Switched to `{recommendation.selected_service.name}`. "
            f"Improvement (`+{recommendation.qos_improvement:.4f}`) exceeded threshold (`≥ {active_hysteresis.min_qos_delta:.4f}`)."
        )
    elif dec_type in ("EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION"):
        emergency_cause = "Outage (UNAVAILABLE)" if dec_type == "EMERGENCY_OUTAGE" else "Hard SLA Constraint Violation"
        st.error(
            f"🚨 **Emergency Reselection (Bypassed Hysteresis & Cooldown):** Active service was disqualified due to "
            f"**{emergency_cause}**. Emergency failover selected `{recommendation.selected_service.name}` immediately."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Phase 3: Explain Why a Service Was Selected ---
    col_ov_left, col_ov_right = st.columns([1.2, 0.8])

    with col_ov_left:
        st.markdown("#### 🔍 Explain Why This Service Was Selected")
        if not recommendation.has_eligible_service:
            st.error(
                f"🚨 **No SLA-Compliant Service Available**\n\n"
                f"{recommendation.status_message}\n\n"
                f"**Root Cause:** All candidates in category '{selected_category}' are currently in an outage state or violate active SLA constraint thresholds."
            )
        else:
            winner = recommendation.selected_service
            scores = recommendation.selected_scores

            # Narrative bullet points supported by actual engine calculations
            for detail_point in explanation_data.get("details", []):
                st.markdown(f"- {detail_point}")

            with st.expander("📊 View Winner Normalized Metric Scores Breakdown (0.0 to 1.0)", expanded=True):
                col_b1, col_b2, col_b3, col_b4 = st.columns(4)
                col_b1.progress(scores.latency_score, text=f"Latency Score: {scores.latency_score:.2f}")
                col_b2.progress(scores.cost_score, text=f"Cost Score: {scores.cost_score:.2f}")
                col_b3.progress(scores.availability_score, text=f"Avail Score: {scores.availability_score:.2f}")
                col_b4.progress(scores.reliability_score, text=f"Rel Score: {scores.reliability_score:.2f}")

        # List ineligible services and rejection reasons
        if recommendation.excluded_services:
            with st.expander(f"⚠️ Ineligible Excluded Candidates ({len(recommendation.excluded_services)})", expanded=not recommendation.has_eligible_service):
                for s, reason in recommendation.excluded_services:
                    icon = "🔴" if s.operational_status == "UNAVAILABLE" else "⚠️"
                    st.markdown(f"- {icon} **{s.name} (`{s.service_id}`)**: *{reason}*")

    with col_ov_right:
        # Service Health Donut Chart
        donut_fig = build_health_donut_chart(category_services)
        st.plotly_chart(donut_fig, use_container_width=True)

    st.markdown("---")

    # --- Phase 4: Decision Comparison (3-Way Comparison) ---
    st.subheader("⚔️ Decision Comparison: Prior Choice vs Newly Selected vs Best Alternative")
    st.caption("Compares QoS values and reveals whether metrics improved or degraded during the reselection decision.")

    if explanation_data.get("has_recommendation"):
        df_3way = build_three_way_comparison_dataframe(explanation_data)
        st.dataframe(df_3way, use_container_width=True, hide_index=True)
    else:
        st.info("Comparison unavailable because no SLA-compliant service is currently available in this category.")

    st.markdown("---")

    # --- Phase 5: Candidate Service Comparison & Engine Ranking ---
    st.subheader(f"📋 Candidate Services Comparison & Official Ranking ({selected_category})")
    st.caption("Ranked according to the existing recommendation engine's weighted evaluation. Differentiates selected, eligible, and ineligible candidates.")

    df_candidates = build_candidate_comparison_table(recommendation, evaluator, normalized_weights, category_services)
    st.dataframe(
        df_candidates.style.highlight_max(subset=["Aggregate QoS Score"], color="#DBEAFE"),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================================
# Tab 2: QoS Analytics
# =========================================================================
with tab_analytics:
    st.markdown("### 📊 QoS Comparative Analytics")
    st.markdown(
        '<div class="section-desc">'
        'Compare aggregate QoS scores and multi-dimensional performance profiles across candidate services.'
        '</div>',
        unsafe_allow_html=True,
    )

    # 1. QoS Comparison Bar Chart
    fig_bar = build_qos_comparison_chart(
        services=category_services,
        evaluator=evaluator,
        weights=normalized_weights,
        recommended_id=recommended_id,
        category=selected_category,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # 2. QoS Radar Chart
    st.markdown("### 🕸️ Multi-Dimensional QoS Radar Chart")
    st.caption("Visualizes Latency, Cost, Availability, and Reliability normalized onto a common 0.0–1.0 scale (outwards is better).")

    all_cat_ids = [s.service_id for s in category_services]
    radar_col1, radar_col2 = st.columns([0.3, 0.7])
    with radar_col1:
        default_selected = all_cat_ids[:4] if len(all_cat_ids) > 4 else all_cat_ids
        if recommended_id and recommended_id not in default_selected:
            default_selected.append(recommended_id)

        selected_radar_ids = st.multiselect(
            "Select Services to Compare on Radar:",
            options=all_cat_ids,
            default=default_selected,
            format_func=lambda sid: f"{sid} ({service_options.get(sid, sid).split(' - ')[-1]})",
        )
        st.info("💡 **Tip:** The recommended service is highlighted with a shaded blue area and prominent border.")

    with radar_col2:
        if selected_radar_ids:
            fig_radar = build_qos_radar_chart(
                services=category_services,
                evaluator=evaluator,
                recommended_id=recommended_id,
                selected_service_ids=selected_radar_ids,
            )
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.warning("Please select at least one service to display the radar chart.")

    st.markdown("---")

    # 3. Individual Metric Charts
    st.markdown("### 📈 Individual QoS Metric Breakdowns")
    st.caption("Inspect raw values for each metric with actual operational units. Degraded and unavailable services are highlighted.")

    metric_mode = st.radio(
        "Display Layout:",
        options=["2x2 Grid View", "Single Metric Focus"],
        horizontal=True,
    )

    metric_charts = build_individual_metric_charts(category_services)

    if metric_mode == "2x2 Grid View":
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            st.plotly_chart(metric_charts["latency"], use_container_width=True)
            st.plotly_chart(metric_charts["availability"], use_container_width=True)
        with g_col2:
            st.plotly_chart(metric_charts["cost"], use_container_width=True)
            st.plotly_chart(metric_charts["reliability"], use_container_width=True)
    else:
        focused_metric = st.selectbox(
            "Select Metric to Inspect:",
            options=["latency", "cost", "availability", "reliability"],
            format_func=lambda m: {
                "latency": "Latency (ms) — Lower is Better",
                "cost": "Cost ($ per invocation) — Lower is Better",
                "availability": "Availability (%) — Higher is Better",
                "reliability": "Reliability (%) — Higher is Better",
            }[m],
        )
        st.plotly_chart(metric_charts[focused_metric], use_container_width=True)


# =========================================================================
# Tab 3: Failure Analysis
# =========================================================================
with tab_failure:
    st.markdown("### ⚡ Failure Impact & Recovery Analysis")
    st.markdown(
        '<div class="section-desc">'
        'Inspect the before-and-after impact of simulated faults (latency spikes, availability drops, outages) '
        'and verify whether service restoration returns the node to baseline QoS.'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.last_action_detail:
        detail = st.session_state.last_action_detail
        before = detail["before"]
        after = detail["after"]

        d_lat = after["latency"] - before["latency"]
        d_avail = after["availability"] - before["availability"]
        d_rel = after["reliability"] - before["reliability"]
        d_score = after["qos_score"] - before["qos_score"]

        status_callout = (
            "✅ Fully Restored to Baseline" if detail["recovered"]
            else ("🚨 Service Outage Triggered" if after["operational_status"] == "UNAVAILABLE"
                  else "⚠️ Service Performance Degraded")
        )

        st.subheader(f"Action: {detail['action']} on {detail['target_service_id']} ({detail['target_service_name']})")
        st.caption(f"Status Outcome: **{status_callout}**")

        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            st.metric(
                "Latency Change",
                f"{after['latency']:.1f} ms",
                delta=f"{d_lat:+.1f} ms",
                delta_color="inverse",
            )
        with f_col2:
            st.metric(
                "Availability Change",
                f"{after['availability']:.2f}%",
                delta=f"{d_avail:+.2f}%",
            )
        with f_col3:
            st.metric(
                "Reliability Change",
                f"{after['reliability']:.2f}%",
                delta=f"{d_rel:+.2f}%",
            )
        with f_col4:
            st.metric(
                "QoS Score Impact",
                f"{after['qos_score']:.4f}",
                delta=f"{d_score:+.4f}",
            )

        fig_ba = build_before_after_chart(
            target_service_id=detail["target_service_id"],
            target_service_name=detail["target_service_name"],
            action=detail["action"],
            before=before,
            after=after,
        )
        st.plotly_chart(fig_ba, use_container_width=True)

        target_obj = simulator.get_service(detail["target_service_id"])
        if target_obj:
            with st.expander("🔍 Compare Baseline vs Current Values for Target Service"):
                b = target_obj.baseline
                comp_data = [
                    {"Metric": "Latency", "Baseline": f"{b['latency']:.1f} ms", "Current": f"{target_obj.latency:.1f} ms", "Difference": f"{target_obj.latency - b['latency']:+.1f} ms"},
                    {"Metric": "Cost", "Baseline": f"${b['cost']:.3f}", "Current": f"${target_obj.cost:.3f}", "Difference": f"${target_obj.cost - b['cost']:+.3f}"},
                    {"Metric": "Availability", "Baseline": f"{b['availability']:.2f}%", "Current": f"{target_obj.availability:.2f}%", "Difference": f"{target_obj.availability - b['availability']:+.2f}%"},
                    {"Metric": "Reliability", "Baseline": f"{b['reliability']:.2f}%", "Current": f"{target_obj.reliability:.2f}%", "Difference": f"{target_obj.reliability - b['reliability']:+.2f}%"},
                    {"Metric": "Operational Status", "Baseline": b["operational_status"], "Current": target_obj.operational_status, "Difference": "Status Changed" if b["operational_status"] != target_obj.operational_status else "Unchanged"},
                ]
                st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

    else:
        st.info(
            "ℹ️ **No recent failure or restoration action captured.**\n\n"
            "Use the sidebar on the left to inject a **Latency Spike**, **Outage**, or **Availability Drop**, "
            "or click **Restore Service** to view the interactive Before-and-After impact analysis."
        )


# =========================================================================
# Tab 4: Simulation & Decision History
# =========================================================================
with tab_history:
    st.markdown("### 📜 Simulation Performance History & Reselection Decision Audit Trail")
    st.markdown(
        '<div class="section-desc">'
        'Inspect the historical performance trajectory across simulation steps, followed by the complete '
        'chronological decision history and reselection explanations.'
        '</div>',
        unsafe_allow_html=True,
    )

    # --- Recommendation Reselection Audit Trail ---
    st.subheader("🛡️ Reselection Decision Audit Trail")
    st.caption("Maintains a permanent chronological record of every recommendation and reselection event.")

    trail_col1, trail_col2 = st.columns([0.75, 0.25])
    with trail_col1:
        st.caption(f"Recorded Reselection Decisions: **{len(reselection_audit_trail.records)}** event(s)")
    with trail_col2:
        if st.button("🗑️ Clear Decision History", use_container_width=True):
            reselection_audit_trail.reset()
            # Log current baseline
            reselection_audit_trail.record_decision(
                trigger_event="History Cleared -> Baseline State",
                recommendation=recommendation,
                evaluator=evaluator,
                weights=normalized_weights,
                prev_service_id=None,
                all_category_services=category_services,
            )
            st.rerun()

    df_trail = reselection_audit_trail.to_dataframe()
    if not df_trail.empty:
        # Display newest reselection at the top
        st.dataframe(
            df_trail.iloc[::-1].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No reselection decisions recorded yet.")

    st.markdown("---")

    # --- Simulation Performance History ---
    st.subheader("📈 Performance Trajectory Across Sequence Steps")
    hist_col1, hist_col2 = st.columns([0.75, 0.25])
    with hist_col1:
        st.caption(f"Recorded Simulation Metric Snapshots: **{len(history_tracker.snapshots)}** step(s)")
    with hist_col2:
        if st.button("🗑️ Reset Snapshot History", use_container_width=True):
            history_tracker.reset()
            history_tracker.record_snapshot(
                action="Baseline Initialized",
                target_service_id="ALL",
                target_service_name="All Services",
                message="History reset to baseline.",
                services=simulator.get_all_services(),
                evaluator=evaluator,
                weights=normalized_weights,
            )
            st.rerun()

    if len(history_tracker.snapshots) <= 1:
        st.warning(
            "⏳ **Only baseline snapshot recorded so far.**\n\n"
            "Inject failure events (e.g., Latency Spike, Outage) or restore services in the sidebar to populate "
            "historical performance trend graphs over simulation sequence steps."
        )

    all_service_ids = [s.service_id for s in all_services]
    hist_service_id = st.selectbox(
        "Select Service to Inspect History Timeline:",
        options=all_service_ids,
        index=0 if target_service_id not in all_service_ids else all_service_ids.index(target_service_id),
        format_func=lambda sid: f"{sid} ({service_options.get(sid, sid)})",
    )

    df_hist = history_tracker.get_service_history_df(hist_service_id)
    if not df_hist.empty:
        target_name = df_hist.iloc[0]["name"]
        fig_trend = build_history_timeline_chart(df_hist, hist_service_id, target_name)
        st.plotly_chart(fig_trend, use_container_width=True)

    st.markdown("---")

    # Periodic Monitoring Event History (Phase 3)
    st.subheader("📡 Periodic Monitoring Event History")
    st.caption(
        "Append-only deduplicated log of monitoring lifecycle events, health transitions, SLA detections, "
        "outages, recoveries, and automatic reselections."
    )
    mon_evt_col1, mon_evt_col2 = st.columns([0.75, 0.25])
    with mon_evt_col1:
        st.caption(
            f"Recorded Monitoring Events: **{len(monitoring_engine.event_history)}** event(s) | "
            f"Engine Status: **{monitoring_engine.status_label}**"
        )
    with mon_evt_col2:
        if st.button("🗑️ Clear Monitoring Events", key="btn_clear_monitoring_events", use_container_width=True):
            monitoring_engine.clear_events()
            st.rerun()

    df_mon_events = monitoring_engine.get_events_dataframe()
    if not df_mon_events.empty:
        st.dataframe(
            df_mon_events.iloc[::-1].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No monitoring events recorded yet.")

    st.markdown("---")

    # Operating Mode & Manual Override Event Audit Log
    ovr_hdr_col, ovr_btn_col = st.columns([0.82, 0.18])
    with ovr_hdr_col:
        st.subheader("🎛️ Operating Mode & Manual Override Event Log")
    with ovr_btn_col:
        if st.button("🧹 Clear Override Log", key="btn_clear_override_events", use_container_width=True):
            override_manager.clear_events()
            st.rerun()

    df_ovr_events = override_manager.get_events_dataframe()
    if not df_ovr_events.empty:
        st.dataframe(
            df_ovr_events.iloc[::-1].reset_index(drop=True),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.write("No operating mode transitions or manual override events recorded yet.")

    st.markdown("---")

    # Simulation Event Audit Log
    st.subheader("📋 Low-Level Simulation Mutation Log")
    events = simulator.get_event_logs()
    if events:
        df_events = pd.DataFrame(events)
        df_events = df_events.iloc[::-1].reset_index(drop=True)
        df_events.rename(
            columns={
                "timestamp": "Timestamp",
                "action": "Action",
                "service_id": "Service ID",
                "service_name": "Service Name",
                "details": "Simulation Details & Outcome",
            },
            inplace=True,
        )
        st.dataframe(df_events, use_container_width=True, hide_index=True)
    else:
        st.write("No simulation events logged yet.")
