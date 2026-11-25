"""
Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
=================================================================
Interactive Streamlit Cloud Command Center dashboard.
"""

import streamlit as st
import pandas as pd
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
    padding: 20px;
    text-align: center;
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-2px); }
.metric-card h3 { color: #94A3B8; font-size: 0.85rem; margin: 0; }
.metric-card .value { color: #F1F5F9; font-size: 1.8rem; font-weight: 700; margin: 6px 0; }
.metric-card .sub   { color: #64748B; font-size: 0.75rem; }

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
    if "weights" not in st.session_state:
        st.session_state.weights = dict(DEFAULT_WEIGHTS)

_init_state()


def _switch_category(cat: str):
    st.session_state.category = cat
    st.session_state.services = get_baseline_services(cat)
    st.session_state.baselines = get_baseline_services(cat)
    st.session_state.simulator = FailureSimulator()


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
    st.markdown("### ⚙️ QoS Weights")
    w_lat = st.slider("Latency", 0.0, 1.0, st.session_state.weights["latency"], 0.05, key="w_lat")
    w_cost = st.slider("Cost", 0.0, 1.0, st.session_state.weights["cost"], 0.05, key="w_cost")
    w_avail = st.slider("Availability", 0.0, 1.0, st.session_state.weights["availability"], 0.05, key="w_avail")
    w_rel = st.slider("Reliability", 0.0, 1.0, st.session_state.weights["reliability"], 0.05, key="w_rel")
    w_total = w_lat + w_cost + w_avail + w_rel
    if w_total > 0:
        st.session_state.weights = validate_weights({
            "latency": w_lat, "cost": w_cost,
            "availability": w_avail, "reliability": w_rel,
        })
    st.caption(f"Weights sum: {w_total:.2f} → auto-normalized to 1.0")

    st.markdown("---")

    # ---- Simulation Controls ----
    st.markdown("### 🧪 Failure Simulation")
    svc_names = {s.name: s for s in st.session_state.services}
    target_name = st.selectbox("Target Service", list(svc_names.keys()), key="sim_target")
    target_svc = svc_names[target_name]

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        if st.button("⚡ Latency Spike", use_container_width=True, key="btn_lat"):
            try:
                st.session_state.simulator.inject_latency_spike(target_svc)
                st.toast(f"⚡ Latency spike injected on {target_svc.name}", icon="⚡")
            except ValueError as e:
                st.error(str(e))
        if st.button("🔴 Outage", use_container_width=True, key="btn_outage"):
            try:
                st.session_state.simulator.simulate_outage(target_svc)
                st.toast(f"🔴 Outage simulated on {target_svc.name}", icon="🔴")
            except ValueError as e:
                st.error(str(e))
    with sim_col2:
        if st.button("📉 Degrade Avail", use_container_width=True, key="btn_avail"):
            try:
                st.session_state.simulator.degrade_availability(target_svc)
                st.toast(f"📉 Availability degraded on {target_svc.name}", icon="📉")
            except ValueError as e:
                st.error(str(e))
        if st.button("🔧 Restore", use_container_width=True, key="btn_restore"):
            try:
                st.session_state.simulator.restore_service(target_svc, st.session_state.baselines)
                st.toast(f"🔧 {target_svc.name} restored", icon="🔧")
            except ValueError as e:
                st.error(str(e))

    if st.button("🔄 Reset Entire Simulation", use_container_width=True, type="primary", key="btn_reset"):
        st.session_state.simulator.reset_simulation(
            st.session_state.services, st.session_state.category
        )
        st.session_state.simulator.clear_history()
        st.toast("🔄 Simulation reset to baseline", icon="🔄")


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
    selected_name = rec.selected_service.name if rec.selected_service else "None"
    st.markdown(f"""
    <div class="metric-card">
        <h3>✅ Selected Service</h3>
        <div class="value" style="color:#22D3EE; font-size:1.1rem">{selected_name}</div>
        <div class="sub">Currently recommended</div>
    </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION B: Recommendation Card
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
# SECTION C: Service Registry Table
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
# SECTION D: QoS Analytics
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
# SECTION E: Comparison Table (ranked candidates)
# ═══════════════════════════════════════════════════════════════════

if ranked:
    st.markdown('<div class="section-header">🏆 Candidate Ranking</div>', unsafe_allow_html=True)
    df_comparison = build_comparison_table(ranked)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# SECTION F: Event History
# ═══════════════════════════════════════════════════════════════════

st.markdown('<div class="section-header">📜 Simulation Event History</div>', unsafe_allow_html=True)

events = simulator.get_history()
if events:
    df_events = build_event_history_table(events)
    st.dataframe(df_events, use_container_width=True, hide_index=True)
else:
    st.info("No simulation events recorded yet. Use the sidebar controls to inject faults.")
