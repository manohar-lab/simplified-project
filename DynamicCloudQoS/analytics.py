"""
Analytics Module
================
Plotly-based visualization builders for QoS comparison, service health,
latency analysis, and event history.
"""

from typing import Dict, List, Tuple, Optional
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from service_registry import CloudService


# ── Colour palette ──────────────────────────────────────────────────
STATUS_COLORS = {
    "Healthy":     "#10B981",  # emerald
    "Degraded":    "#F59E0B",  # amber
    "Unavailable": "#EF4444",  # red
}

METRIC_COLORS = ["#3B82F6", "#6366F1", "#10B981", "#F59E0B", "#EF4444"]


# ── Health classification ───────────────────────────────────────────

def classify_health(service: CloudService,
                    baseline_latency: float,
                    baseline_availability: float) -> str:
    """Classify a service as Healthy / Degraded / Unavailable."""
    if service.status == "UNAVAILABLE":
        return "Unavailable"
    if service.latency > baseline_latency * 1.5 or service.availability < baseline_availability * 0.95:
        return "Degraded"
    return "Healthy"


def health_summary(services: List[CloudService],
                   baselines: List[CloudService]) -> Dict[str, int]:
    """Count services per health classification."""
    baseline_map = {b.service_id: b for b in baselines}
    counts = {"Healthy": 0, "Degraded": 0, "Unavailable": 0}
    for svc in services:
        bl = baseline_map.get(svc.service_id, svc)
        h = classify_health(svc, bl.latency, bl.availability)
        counts[h] = counts.get(h, 0) + 1
    return counts


# ── Chart builders ──────────────────────────────────────────────────

def _dark_layout(fig: go.Figure, title: str, height: int = 350) -> go.Figure:
    """Apply a consistent dark theme to Plotly figures."""
    fig.update_layout(
        title=dict(text=title, font=dict(color="#E2E8F0", size=16)),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#1E293B",
        font=dict(color="#94A3B8", size=12),
        height=height,
        margin=dict(l=50, r=30, t=50, b=40),
        legend=dict(font=dict(color="#CBD5E1")),
    )
    fig.update_xaxes(gridcolor="#334155", zerolinecolor="#334155")
    fig.update_yaxes(gridcolor="#334155", zerolinecolor="#334155")
    return fig


def qos_ranking_chart(
    ranked: List[Tuple[CloudService, float, Dict[str, float]]],
    selected_id: Optional[str] = None,
) -> go.Figure:
    """Horizontal bar chart of QoS scores (highest first)."""
    names = [r[0].name for r in ranked]
    scores = [r[1] for r in ranked]
    colors = ["#22D3EE" if r[0].service_id == selected_id else "#3B82F6" for r in ranked]

    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker_color=colors,
        text=[f"{s:.4f}" for s in scores],
        textposition="outside",
    ))
    return _dark_layout(fig, "Service QoS Ranking")


def latency_chart(services: List[CloudService]) -> go.Figure:
    """Bar chart comparing latency across services."""
    fig = go.Figure(go.Bar(
        x=[s.name for s in services],
        y=[s.latency for s in services],
        marker_color=METRIC_COLORS[:len(services)],
        text=[f"{s.latency:.1f} ms" for s in services],
        textposition="outside",
    ))
    return _dark_layout(fig, "Latency Comparison (ms)")


def availability_chart(services: List[CloudService]) -> go.Figure:
    """Bar chart comparing availability."""
    fig = go.Figure(go.Bar(
        x=[s.name for s in services],
        y=[s.availability for s in services],
        marker_color=METRIC_COLORS[:len(services)],
        text=[f"{s.availability:.1f}%" for s in services],
        textposition="outside",
    ))
    fig.update_yaxes(range=[90, 100])
    return _dark_layout(fig, "Availability Comparison (%)")


def reliability_chart(services: List[CloudService]) -> go.Figure:
    """Bar chart comparing reliability."""
    fig = go.Figure(go.Bar(
        x=[s.name for s in services],
        y=[s.reliability for s in services],
        marker_color=METRIC_COLORS[:len(services)],
        text=[f"{s.reliability:.1f}%" for s in services],
        textposition="outside",
    ))
    fig.update_yaxes(range=[90, 100])
    return _dark_layout(fig, "Reliability Comparison (%)")


def health_distribution_chart(summary: Dict[str, int]) -> go.Figure:
    """Pie/donut chart of service health distribution."""
    labels = list(summary.keys())
    values = list(summary.values())
    colors = [STATUS_COLORS.get(l, "#64748B") for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker=dict(colors=colors),
        hole=0.45,
        textinfo="label+value",
        textfont=dict(color="#E2E8F0"),
    ))
    return _dark_layout(fig, "Service Health Distribution", height=300)


def cost_chart(services: List[CloudService]) -> go.Figure:
    """Bar chart comparing invocation cost."""
    fig = go.Figure(go.Bar(
        x=[s.name for s in services],
        y=[s.cost for s in services],
        marker_color=METRIC_COLORS[:len(services)],
        text=[f"${s.cost:.3f}" for s in services],
        textposition="outside",
    ))
    return _dark_layout(fig, "Cost per Invocation ($)")


def normalized_scores_radar(
    service: CloudService,
    normalized: Dict[str, float],
) -> go.Figure:
    """Radar chart showing normalized metric breakdown for a service."""
    metrics = ["Latency", "Cost", "Availability", "Reliability"]
    values = [normalized.get(m.lower(), 0) for m in metrics]
    values.append(values[0])  # close the polygon
    metrics.append(metrics[0])

    fig = go.Figure(go.Scatterpolar(
        r=values, theta=metrics, fill="toself",
        fillcolor="rgba(34,211,238,0.2)",
        line=dict(color="#22D3EE", width=2),
        name=service.name,
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="#1E293B",
            radialaxis=dict(range=[0, 1], gridcolor="#334155", tickfont=dict(color="#94A3B8")),
            angularaxis=dict(gridcolor="#334155", tickfont=dict(color="#CBD5E1")),
        ),
    )
    return _dark_layout(fig, f"{service.name} — Normalized Metrics", height=350)
