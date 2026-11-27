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