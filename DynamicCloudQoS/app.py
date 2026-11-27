"""
Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
=================================================================
Interactive Streamlit Cloud Command Center dashboard.
"""

import time
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from service_registry import CloudService, get_baseline_services, get_all_categories, get_baseline_bounds
from qos_evaluator import evaluate_all, evaluate_service, DEFAULT_WEIGHTS, validate_weights
from recommendation_engine import recommend, RecommendationResult
from failure_simulator import FailureSimulator
from analytics import (
    classify_health, health_summary,
    qos_ranking_chart, latency_chart, availability_chart,
    reliability_chart, health_distribution_chart, cost_chart,
    normalized_scores_radar,
)
from explainability import (
    generate_explanation, build_comparison_table, build_event_history_table,
)

# ════════════════════════════════════════════════════════════════════
# Page configuration
# ════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Cloud Command Center",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════
# Custom CSS — dark navy theme
# ════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
/* ---- Global ---- */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0B1120 0%, #0F172A 100%);
    color: #E2E8F0;
}
[data-testid="stSidebar"] {
    background: #0F172A;
    border-right: 1px solid #1E293B;
}
[data-testid="stHeader"] { background: transparent; }

/* ---- Cards ---- */
.metric-card {
    background: linear-gradient(135deg, #1E293B 0%, #162032 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 10px;
    text-align: center;
    min-height: 130px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    transition: transform 0.2s, border-color 0.2s;
}
.metric-card:hover { transform: translateY(-2px); border-color: #22D3EE80; }
.metric-card h3 { color: #94A3B8; font-size: 0.78rem; margin: 0 0 6px 0; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.metric-card .value { color: #F1F5F9; font-size: 1.7rem; font-weight: 700; margin: 2px 0; line-height: 1.1; }
.metric-card .service-title { color: #22D3EE; font-size: 0.95rem; font-weight: 700; margin: 4px 0; line-height: 1.25; word-break: break-word; text-align: center; max-width: 100%; }
.metric-card .sub { color: #64748B; font-size: 0.72rem; margin-top: 4px; }

/* ---- Sidebar button styles ---- */
[data-testid="stSidebar"] [data-testid="stButton"] button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 8px 12px;
    transition: all 0.2s ease;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {
    border-color: #22D3EE;
    color: #22D3EE;
}

/* ---- Recommendation card ---- */
.rec-card {
    background: linear-gradient(135deg, #0F2A1B 0%, #132A18 100%);
    border: 1px solid #22C55E40;
    border-radius: 14px;
    padding: 24px;
    margin: 10px 0;
}
.rec-card h2 { color: #22D3EE; margin: 0 0 8px; }
.rec-card .score { color: #10B981; font-size: 2rem; font-weight: 800; }

/* ---- Warning card ---- */
.warn-card {
    background: linear-gradient(135deg, #2A1A0F 0%, #2A1810 100%);
    border: 1px solid #EF444460;
    border-radius: 14px;
    padding: 24px;
    margin: 10px 0;
}
.warn-card h2 { color: #EF4444; }

/* ---- Status badges ---- */
.badge-healthy { background: #10B981; color: #fff; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; }
.badge-degraded { background: #F59E0B; color: #000; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; }
.badge-unavailable { background: #EF4444; color: #fff; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; }

/* ---- Section headers ---- */
.section-header {
    color: #E2E8F0;
    font-size: 1.3rem;
    font-weight: 600;
    margin: 30px 0 15px;
    padding-bottom: 8px;
    border-bottom: 2px solid #22D3EE30;
}

/* ---- Table text colour fix ---- */
[data-testid="stDataFrame"] { color: #E2E8F0; }

/* ---- Workflow Flow Cards ---- */
.workflow-box {
    background: #0F172A;
    border: 1px solid #1E293B;
    border-radius: 14px;
    padding: 20px;
    margin: 15px 0 25px 0;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
.flow-col {
    border-radius: 10px;
    padding: 16px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.flow-col-before {
    border: 1px solid #38BDF860;
    background: linear-gradient(180deg, rgba(14, 165, 233, 0.08) 0%, rgba(30, 41, 59, 0.9) 100%);
}
.flow-col-failure {
    border: 1px solid #EF444480;
    background: linear-gradient(180deg, rgba(239, 68, 68, 0.14) 0%, rgba(30, 41, 59, 0.9) 100%);
}
.flow-col-after {
    border: 1px solid #10B98180;
    background: linear-gradient(180deg, rgba(16, 185, 129, 0.14) 0%, rgba(30, 41, 59, 0.9) 100%);
}
.flow-stage-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.flow-svc-name {
    font-size: 1.15rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 2px 0 4px;
}
.flow-msg {
    font-size: 0.8rem;
    padding: 8px 10px;
    border-radius: 6px;
    margin-top: 10px;
    line-height: 1.35;
}

/* Hide Streamlit branding */
#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# Session-state initialisation
# ════════════════════════════════════════════════════════════════════

def _init_state():
    if "category" not in st.session_state:
        st.session_state.category = "Compute"
    if "services" not in st.session_state:
        st.session_state.services = get_baseline_services(st.session_state.category)
    if "baselines" not in st.session_state:
        st.session_state.baselines = get_baseline_services(st.session_state.category)
    if "simulator" not in st.session_state:
        st.session_state.simulator = FailureSimulator()
    if "raw_weights" not in st.session_state:
        st.session_state.raw_weights = dict(DEFAULT_WEIGHTS)
    if "weights" not in st.session_state:
        st.session_state.weights = dict(DEFAULT_WEIGHTS)
    if "last_failover_event" not in st.session_state:
        st.session_state.last_failover_event = None

_init_state()


def _switch_category(cat: str):
    st.session_state.category = cat
    st.session_state.services = get_baseline_services(cat)
    st.session_state.baselines = get_baseline_services(cat)
    st.session_state.simulator = FailureSimulator()
    st.session_state.last_failover_event = None
    if "sim_target" in st.session_state:
        del st.session_state["sim_target"]


def trigger_active_service_failure():
    """Simulate an immediate failure of the currently active/recommended cloud service."""
    curr_rec = recommend(st.session_state.services, st.session_state.category, st.session_state.weights)
    if not curr_rec.selected_service:
        st.warning("⚠️ No active healthy cloud service available to fail.")
        return

    target = curr_rec.selected_service
    prev_name = target.name
    prev_id = target.service_id
    prev_score = curr_rec.selected_score

    # Visual loading transition for reselection demonstration
    with st.spinner(f"🚨 Cloud service failure detected on {prev_name} ({prev_id})! Searching for an alternative..."):
        time.sleep(0.35)

    # Trigger outage on active service
    evt = st.session_state.simulator.fail_active_service(target)

    # Immediately recalculate QoS scores and reselect
    new_rec = recommend(st.session_state.services, st.session_state.category, st.session_state.weights)
    if new_rec.selected_service:
        new_name = new_rec.selected_service.name
        new_id = new_rec.selected_service.service_id
        new_score = new_rec.selected_score
        has_alt = True
        msg = "Automatic service reselection completed successfully."
        rec_summary = f"{new_name} (QoS: {new_score:.4f})"
    else:
        new_name = "None Available"
        new_id = "N/A"
        new_score = 0.0
        has_alt = False
        msg = "All candidate services in this category are offline. No alternative available."
        rec_summary = "No Eligible Service"

    evt.resulting_recommendation = rec_summary

    st.session_state.last_failover_event = {
        "previous_service": prev_name,
        "previous_id": prev_id,
        "previous_score": prev_score,
        "failed_service": prev_name,
        "failed_id": prev_id,
        "new_service": new_name,
        "new_id": new_id,
        "new_score": new_score,
        "message": msg,
        "timestamp": evt.timestamp,
        "has_alternative": has_alt,
    }
    st.toast(f"🔴 Failure simulated on {prev_name}. Auto-reselected {new_name}!", icon="⚡")
    st.rerun()


def trigger_restore_failed_service():
    """Restore the most recently failed service to healthy status."""
    failed = [s for s in st.session_state.services if s.status == "UNAVAILABLE"]
    if not failed:
        st.info("No failed services to restore.")
        return

    target = failed[-1]
    evt = st.session_state.simulator.restore_service(target, st.session_state.baselines)
    rec_after = recommend(st.session_state.services, st.session_state.category, st.session_state.weights)
    rec_summary = f"{rec_after.selected_service.name} (QoS: {rec_after.selected_score:.4f})" if rec_after.selected_service else "No Eligible Service"
    evt.resulting_recommendation = rec_summary

    remaining_failed = [s for s in st.session_state.services if s.status == "UNAVAILABLE"]
    if not remaining_failed:
        st.session_state.last_failover_event = None

    st.toast(f"🔧 Restored {target.name} to Healthy status", icon="🔧")
    st.rerun()


def trigger_reset_simulation():
    """Restore all services to baseline state and clear failure state."""
    st.session_state.simulator.reset_simulation(
        st.session_state.services, st.session_state.category,
        recommendation="NovaCompute Standard (0.8168)" if st.session_state.category == "Compute" else "NovaStore Premium"
    )
    st.session_state.last_failover_event = None
    st.toast("🔄 Simulation reset to initial baseline", icon="🔄")
    st.rerun()


# ════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ☁️ Cloud Command Center")
    st.caption("Dynamic Cloud Failure Detection & QoS-Aware Service Reselection")
    st.markdown("---")

    # ---- Category selector ----
    cat = st.selectbox("Service Category", get_all_categories(),
                       index=get_all_categories().index(st.session_state.category),
                       key="cat_select")
    if cat != st.session_state.category:
        _switch_category(cat)
        st.rerun()

    st.markdown("---")

    # ---- QoS Weight Configuration ----
    st.markdown("### ⚙️ QoS Weights Configuration")
    st.caption("Adjust multi-attribute evaluation criteria (Benchmark sum: 1.00)")

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        w_lat = st.slider("Latency (Cost)", 0.0, 1.0, float(st.session_state.raw_weights["latency"]), 0.05, key="slider_lat")
        w_cost = st.slider("Cost (Cost)", 0.0, 1.0, float(st.session_state.raw_weights["cost"]), 0.05, key="slider_cost")
    with col_w2:
        w_avail = st.slider("Avail (Benefit)", 0.0, 1.0, float(st.session_state.raw_weights["availability"]), 0.05, key="slider_avail")
        w_rel = st.slider("Reliab (Benefit)", 0.0, 1.0, float(st.session_state.raw_weights["reliability"]), 0.05, key="slider_rel")

    st.session_state.raw_weights = {
        "latency": w_lat, "cost": w_cost,
        "availability": w_avail, "reliability": w_rel,
    }
    w_total = sum(st.session_state.raw_weights.values())

    if w_total > 0:
        st.session_state.weights = validate_weights(st.session_state.raw_weights)
    else:
        st.session_state.weights = dict(DEFAULT_WEIGHTS)
        w_total = 1.0

    eff = st.session_state.weights
    if abs(w_total - 1.0) < 0.001:
        st.markdown(
            "<div style='font-size:0.8rem; color:#10B981; background:#064E3B40; border:1px solid #10B98150; padding:6px 10px; border-radius:6px; margin:4px 0 8px; text-align:center;'>"
            "✅ <b>Weights Sum = 1.00 (Balanced Benchmark)</b></div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='font-size:0.78rem; color:#F59E0B; background:#78350F30; border:1px solid #F59E0B50; padding:8px 10px; border-radius:6px; margin:4px 0 8px;'>"
            f"⚠️ <b>Raw Sum = {w_total:.2f}</b> (Auto-Normalized for Scoring):<br>"
            f"Lat: <b>{eff['latency']:.1%}</b> | Cost: <b>{eff['cost']:.1%}</b> | "
            f"Avail: <b>{eff['availability']:.1%}</b> | Rel: <b>{eff['reliability']:.1%}</b>"
            f"</div>",
            unsafe_allow_html=True
        )

    if st.button("↺ Reset Weights to Benchmark (1.00)", use_container_width=True, key="btn_reset_weights"):
        st.session_state.raw_weights = dict(DEFAULT_WEIGHTS)
        st.session_state.weights = dict(DEFAULT_WEIGHTS)
        st.session_state.slider_lat = DEFAULT_WEIGHTS["latency"]
        st.session_state.slider_cost = DEFAULT_WEIGHTS["cost"]
        st.session_state.slider_avail = DEFAULT_WEIGHTS["availability"]
        st.session_state.slider_rel = DEFAULT_WEIGHTS["reliability"]
        st.rerun()

    st.markdown("---")

    # ---- Simulation Controls (One-Click Autonomous Failover) ----
    st.markdown("### ⚡ Failure Simulation Lab")
    st.caption("One-click active cloud failure and autonomous reselection")

    failed_svcs_sidebar = [s for s in st.session_state.services if s.status == "UNAVAILABLE"]

    if st.button("⚡ Simulate Cloud Failure", use_container_width=True, type="primary", key="sb_btn_fail",
                 help="Automatically fails the active service and triggers QoS reselection"):
        trigger_active_service_failure()

    if failed_svcs_sidebar:
        last_failed_name = failed_svcs_sidebar[-1].name
        if st.button("🔧 Restore Failed Service", use_container_width=True, key="sb_btn_restore",
                     help=f"Restore {last_failed_name} to Healthy status"):
            trigger_restore_failed_service()
    else:
        st.button("🔧 Restore Failed Service", use_container_width=True, disabled=True, key="sb_btn_restore_dis",
                  help="No failed services to restore")

    if st.button("🔄 Reset Entire Simulation", use_container_width=True, key="sb_btn_reset",
                 help="Restore all services to baseline state"):
        trigger_reset_simulation()


# ════════════════════════════════════════════════════════════════════
# MAIN DASHBOARD
# ════════════════════════════════════════════════════════════════════

services = st.session_state.services
baselines = st.session_state.baselines
weights = st.session_state.weights
simulator: FailureSimulator = st.session_state.simulator

# ---- Compute recommendation ----
rec: RecommendationResult = recommend(services, st.session_state.category, weights)

# ---- Health summary ----
h_summary = health_summary(services, baselines)

# ═══════════════════════════════════════════════════════════════════
# SECTION A: Overview KPI Cards
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">📊 System Overview</div>', unsafe_allow_html=True)

kpi_cols = st.columns(5)

with kpi_cols[0]:
    st.markdown(f"""
    <div class="metric-card">
        <h3>Total Services</h3>
        <div class="value">{len(services)}</div>
        <div class="sub">{st.session_state.category} category</div>
    </div>""", unsafe_allow_html=True)

with kpi_cols[1]:
    st.markdown(f"""
    <div class="metric-card">
        <h3>🟢 Healthy</h3>
        <div class="value" style="color:#10B981">{h_summary['Healthy']}</div>
        <div class="sub">Fully operational</div>
    </div>""", unsafe_allow_html=True)

with kpi_cols[2]:
    st.markdown(f"""
    <div class="metric-card">
        <h3>🟡 Degraded</h3>
        <div class="value" style="color:#F59E0B">{h_summary['Degraded']}</div>
        <div class="sub">Performance reduced</div>
    </div>""", unsafe_allow_html=True)

with kpi_cols[3]:
    st.markdown(f"""
    <div class="metric-card">
        <h3>🔴 Unavailable</h3>
        <div class="value" style="color:#EF4444">{h_summary['Unavailable']}</div>
        <div class="sub">Total outage</div>
    </div>""", unsafe_allow_html=True)

with kpi_cols[4]:
    if rec.selected_service:
        s_title = rec.selected_service.name
        s_sub = f"ID: {rec.selected_service.service_id} | QoS: {rec.selected_score:.4f}"
        s_color = "#22D3EE"
    else:
        s_title = "None Eligible"
        s_sub = "All candidates offline"
        s_color = "#EF4444"
    st.markdown(f"""
    <div class="metric-card">
        <h3>✅ Selected Service</h3>
        <div class="service-title" style="color:{s_color}">{s_title}</div>
        <div class="sub">{s_sub}</div>
    </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION B: One-Click Cloud Failure & Automatic Reselection
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">⚡ Dynamic Cloud Failure & Reselection Console</div>', unsafe_allow_html=True)

# Prominent Action Bar in Main View
failed_svcs_main = [s for s in services if s.status == "UNAVAILABLE"]
action_col1, action_col2, action_col3 = st.columns([1.6, 1.2, 1.0])

with action_col1:
    if st.button("⚡ Simulate Cloud Failure", use_container_width=True, type="primary", key="main_btn_fail",
                 help="Instantly simulate failure on the active cloud service and trigger real-time reselection"):
        trigger_active_service_failure()

with action_col2:
    if failed_svcs_main:
        last_failed_name = failed_svcs_main[-1].name
        if st.button("🔧 Restore Failed Service", use_container_width=True, key="main_btn_restore",
                     help=f"Restore {last_failed_name} to Healthy status"):
            trigger_restore_failed_service()
    else:
        st.button("🔧 Restore Failed Service", use_container_width=True, disabled=True, key="main_btn_restore_dis",
                  help="No failed services to restore")

with action_col3:
    if st.button("🔄 Reset Entire Simulation", use_container_width=True, key="main_btn_reset",
                 help="Restore all services to original baseline values"):
        trigger_reset_simulation()

# Before-and-After Visual Workflow Display
event = st.session_state.get("last_failover_event")

if event:
    st.markdown(f"""
    <div class="workflow-box">
        <div style="font-size:0.85rem; color:#94A3B8; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
            <span><strong>REAL-TIME FAILOVER & RESELECTION LIFECYCLE</strong></span>
            <span style="color:#64748B;">Audit Timestamp: {event['timestamp']}</span>
        </div>
    """, unsafe_allow_html=True)

    c_prev, c_arr1, c_fail, c_arr2, c_new = st.columns([2.8, 0.4, 3.2, 0.4, 3.2])

    with c_prev:
        st.markdown(f"""
        <div class="flow-col flow-col-before">
            <div>
                <div class="flow-stage-title" style="color:#38BDF8;">1. BEFORE FAILURE</div>
                <div class="flow-svc-name">{event['previous_service']}</div>
                <div style="color:#94A3B8; font-size:0.8rem; margin-bottom:6px;">ID: <code>{event['previous_id']}</code></div>
            </div>
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                    <span style="color:#CBD5E1; font-size:0.85rem;">QoS Score:</span>
                    <span style="color:#38BDF8; font-size:1.15rem; font-weight:700;">{event['previous_score']:.4f}</span>
                </div>
                <div style="margin-top:6px;">
                    <span class="badge-healthy">🟢 Healthy</span>
                </div>
                <div class="flow-msg" style="background:#0369A120; color:#BAE6FD; border:1px solid #0284C740;">
                    Active cloud service handling workload prior to failure.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c_arr1:
        st.markdown('<div style="text-align:center; padding-top:60px; font-size:1.8rem; color:#EF4444;">➜</div>', unsafe_allow_html=True)

    with c_fail:
        st.markdown(f"""
        <div class="flow-col flow-col-failure">
            <div>
                <div class="flow-stage-title" style="color:#F87171;">2. FAILURE DETECTED</div>
                <div class="flow-svc-name">{event['failed_service']}</div>
                <div style="color:#94A3B8; font-size:0.8rem; margin-bottom:6px;">ID: <code>{event['failed_id']}</code></div>
            </div>
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                    <span style="color:#CBD5E1; font-size:0.85rem;">Status:</span>
                    <span style="color:#EF4444; font-size:1.15rem; font-weight:700;">FAILED</span>
                </div>
                <div style="margin-top:6px;">
                    <span class="badge-unavailable">🔴 Failed</span>
                </div>
                <div class="flow-msg" style="background:#991B1B25; color:#FECACA; border:1px solid #DC262650;">
                    ⚠️ Cloud service failure detected. Searching for an alternative...
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c_arr2:
        st.markdown('<div style="text-align:center; padding-top:60px; font-size:1.8rem; color:#10B981;">➜</div>', unsafe_allow_html=True)

    with c_new:
        if event['has_alternative']:
            badge_html = '<span class="badge-healthy">🟢 Healthy</span>'
            score_html = f"<span style='color:#10B981; font-size:1.15rem; font-weight:700;'>{event['new_score']:.4f}</span>"
            msg_style = "background:#065F4625; color:#A7F3D0; border:1px solid #05966950;"
            msg_text = "✅ Automatic service reselection completed successfully."
        else:
            badge_html = '<span class="badge-unavailable">🔴 Failed / No Alternative</span>'
            score_html = "<span style='color:#EF4444; font-size:1.15rem; font-weight:700;'>0.0000</span>"
            msg_style = "background:#991B1B25; color:#FECACA; border:1px solid #DC262650;"
            msg_text = "⚠️ All candidate services offline. No alternative available."

        st.markdown(f"""
        <div class="flow-col flow-col-after">
            <div>
                <div class="flow-stage-title" style="color:#34D399;">3. AFTER AUTOMATIC RESELECTION</div>
                <div class="flow-svc-name">{event['new_service']}</div>
                <div style="color:#94A3B8; font-size:0.8rem; margin-bottom:6px;">ID: <code>{event['new_id']}</code></div>
            </div>
            <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                    <span style="color:#CBD5E1; font-size:0.85rem;">QoS Score:</span>
                    {score_html}
                </div>
                <div style="margin-top:6px;">
                    {badge_html}
                </div>
                <div class="flow-msg" style="{msg_style}">
                    {msg_text}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
else:
    active_name = rec.selected_service.name if rec.selected_service else "None"
    active_id = rec.selected_service.service_id if rec.selected_service else "N/A"
    st.markdown(f"""
    <div style="background:linear-gradient(135deg, #0F172A 0%, #1E293B 100%); border:1px solid #334155; border-radius:12px; padding:16px 20px; margin:10px 0 20px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-size:0.85rem; color:#38BDF8; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:4px;">
                    Ready for Autonomous Failure & Reselection Demonstration
                </div>
                <div style="color:#94A3B8; font-size:0.88rem;">
                    Currently Active Service: <strong style="color:#F1F5F9;">{active_name}</strong> (<code>{active_id}</code> | QoS: <strong>{rec.selected_score:.4f}</strong> | <span class="badge-healthy">🟢 Healthy</span>).
                    Click <strong>'Simulate Cloud Failure'</strong> above or in the sidebar to simulate an immediate outage on the active service and observe autonomous reselection in real-time.
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION C: Recommendation Card
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">🎯 Current Service Recommendation</div>', unsafe_allow_html=True)

if rec.selected_service:
    svc = rec.selected_service
    r_col1, r_col2 = st.columns([2, 1])
    with r_col1:
        st.markdown(f"""
        <div class="rec-card">
            <h2>✅ {svc.name}</h2>
            <p style="color:#94A3B8; margin:4px 0;">Service ID: <strong>{svc.service_id}</strong></p>
            <div class="score">{rec.selected_score:.4f}</div>
            <p style="color:#94A3B8; margin:4px 0;">Aggregate QoS Score</p>
            <p style="color:#CBD5E1; margin:12px 0 0;">
                Best Alternative: <strong>{rec.runner_up.name if rec.runner_up else 'N/A'}</strong>
                {'(Score: ' + f'{rec.runner_up_score:.4f}' + ', Margin: ' + f'{rec.score_margin:.4f}' + ')' if rec.runner_up else ''}
            </p>
        </div>""", unsafe_allow_html=True)
        if st.session_state.category == "Compute" and rec.selected_service.service_id == "SVC-C01":
            st.markdown(
                "<div style='font-size:0.8rem; color:#38BDF8; background:#0C4A6E30; border:1px solid #0284C750; padding:6px 12px; border-radius:6px; margin-top:8px;'>"
                "🔬 <b>Research Paper Benchmark:</b> NovaCompute Standard (SVC-C01: <b>0.8168</b>) | "
                "Aether Compute HighPerf (SVC-C02: <b>0.7937</b>) | Margin $\\Delta Q = 0.0231$</div>",
                unsafe_allow_html=True
            )
    with r_col2:
        fig_radar = normalized_scores_radar(svc, rec.selected_normalized)
        st.plotly_chart(fig_radar, use_container_width=True)
else:
    st.markdown("""
    <div class="warn-card">
        <h2>⚠️ No Eligible Service</h2>
        <p style="color:#F87171;">All services in this category are currently unavailable.
        Restore at least one service to resume recommendations.</p>
    </div>""", unsafe_allow_html=True)

# Explanation
with st.expander("📝 Selection Explanation", expanded=True):
    explanation = generate_explanation(
        rec.selected_service, rec.selected_score, rec.selected_normalized,
        rec.runner_up, rec.runner_up_score, rec.score_margin,
        rec.excluded_services,
    )
    st.markdown(explanation)


# ═══════════════════════════════════════════════════════════════════
# SECTION D: Service Registry Table
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">📋 Service Registry</div>', unsafe_allow_html=True)

baseline_map = {b.service_id: b for b in baselines}
table_rows = []
for svc in services:
    bl = baseline_map.get(svc.service_id, svc)
    health = classify_health(svc, bl.latency, bl.availability)
    score, norms = evaluate_service(svc, weights)
    table_rows.append({
        "Service": svc.name,
        "ID": svc.service_id,
        "Latency (ms)": f"{svc.latency:.1f}",
        "Cost ($)": f"${svc.cost:.3f}",
        "Availability (%)": f"{svc.availability:.1f}",
        "Reliability (%)": f"{svc.reliability:.1f}",
        "Health": health,
        "Status": svc.status,
        "QoS Score": f"{score:.4f}",
    })

df_registry = pd.DataFrame(table_rows)
st.dataframe(df_registry, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION E: QoS Analytics
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">📈 QoS Analytics</div>', unsafe_allow_html=True)

available_svcs = [s for s in services if s.status == "AVAILABLE"]
ranked = evaluate_all(available_svcs, weights) if available_svcs else []
selected_id = rec.selected_service.service_id if rec.selected_service else None

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    if ranked:
        st.plotly_chart(qos_ranking_chart(ranked, selected_id), use_container_width=True)
    else:
        st.info("No available services to rank.")

with chart_col2:
    st.plotly_chart(health_distribution_chart(h_summary), use_container_width=True)

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.plotly_chart(latency_chart(services), use_container_width=True)

with chart_col4:
    st.plotly_chart(availability_chart(services), use_container_width=True)

chart_col5, chart_col6 = st.columns(2)

with chart_col5:
    st.plotly_chart(reliability_chart(services), use_container_width=True)

with chart_col6:
    st.plotly_chart(cost_chart(services), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION F: Candidate Ranking
# ═══════════════════════════════════════════════════════════════════

if ranked:
    st.markdown('<div class="section-header">🏆 Candidate Ranking</div>', unsafe_allow_html=True)
    df_comparison = build_comparison_table(ranked)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION G: Simulation Event History
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">📜 Simulation Event History</div>', unsafe_allow_html=True)

events = simulator.get_history()
if events:
    df_events = build_event_history_table(events)
    st.dataframe(df_events, use_container_width=True, hide_index=True)
else:
    st.info("No simulation events recorded yet. Use the sidebar controls to inject faults.")
