"""Visual analytics, health classification, and snapshot tracking helpers.

This module provides data models, health status classification, simulation
history snapshot tracking, and Plotly visualization builders for the
Dynamic Cloud Failure and QoS Reselection dashboard.

All calculations strictly reuse the existing service registry and QoS evaluator
without modifying any underlying scoring formulas, weights, or simulation rules.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.service_registry import CloudService
from src.qos_evaluator import MetricScores, QoSEvaluator, METRICS


# =========================================================================
# Status & Theme Constants
# =========================================================================
HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_UNAVAILABLE = "UNAVAILABLE"

STATUS_COLORS = {
    "Recommended": "#2563EB",          # Royal Blue
    "Healthy": "#10B981",              # Emerald Green
    "Degraded": "#F59E0B",             # Amber / Orange
    "Unavailable": "#EF4444",          # Crimson Red
}


def classify_service_health(service: CloudService) -> str:
    """Determine the health status of a candidate service.

    Classification rules:
    - UNAVAILABLE: operational_status is "UNAVAILABLE" (outage).
    - DEGRADED: operational_status is "AVAILABLE" but one or more metrics
      are degraded relative to the service's baseline (higher latency,
      lower availability, lower reliability, or higher cost).
    - HEALTHY: operational_status is "AVAILABLE" and all metrics are at or
      better than baseline values.

    Args:
        service: The CloudService instance to evaluate.

    Returns:
        One of "HEALTHY", "DEGRADED", or "UNAVAILABLE".
    """
    if service.operational_status == "UNAVAILABLE":
        return HEALTH_UNAVAILABLE

    b = service.baseline
    # Compare current metrics against immutable baseline values
    is_degraded = (
        service.latency > b.get("latency", service.latency)
        or service.availability < b.get("availability", service.availability)
        or service.reliability < b.get("reliability", service.reliability)
        or service.cost > b.get("cost", service.cost)
    )
    return HEALTH_DEGRADED if is_degraded else HEALTH_HEALTHY


# =========================================================================
# Simulation Snapshot & History Tracking
# =========================================================================

@dataclass
class ServiceStateRecord:
    """Immutable record of a single service's state at a point in time."""
    service_id: str
    name: str
    category: str
    latency: float
    cost: float
    availability: float
    reliability: float
    operational_status: str
    health_status: str
    qos_score: float
    latency_score: float
    cost_score: float
    availability_score: float
    reliability_score: float


@dataclass
class SimulationSnapshot:
    """Snapshot of the entire candidate registry at a specific simulation step."""
    step: int
    timestamp: str
    action: str
    target_service_id: str
    target_service_name: str
    message: str
    services: Dict[str, ServiceStateRecord] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization."""
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "action": self.action,
            "target_service_id": self.target_service_id,
            "target_service_name": self.target_service_name,
            "message": self.message,
            "services": {sid: asdict(rec) for sid, rec in self.services.items()},
        }


class HistoryTracker:
    """Tracks simulation snapshots over time to enable historical analysis."""

    def __init__(self):
        self.snapshots: List[SimulationSnapshot] = []

    def record_snapshot(
        self,
        action: str,
        target_service_id: str,
        target_service_name: str,
        message: str,
        services: List[CloudService],
        evaluator: QoSEvaluator,
        weights: Optional[Dict[str, float]] = None,
        timestamp: Optional[str] = None,
    ) -> SimulationSnapshot:
        """Capture a snapshot of all services following a state change."""
        step = len(self.snapshots)
        ts = timestamp or datetime.now().strftime("%H:%M:%S")

        service_records: Dict[str, ServiceStateRecord] = {}
        for s in services:
            scores = evaluator.evaluate_service(s, weights)
            health = classify_service_health(s)
            service_records[s.service_id] = ServiceStateRecord(
                service_id=s.service_id,
                name=s.name,
                category=s.category,
                latency=s.latency,
                cost=s.cost,
                availability=s.availability,
                reliability=s.reliability,
                operational_status=s.operational_status,
                health_status=health,
                qos_score=scores.qos_score,
                latency_score=scores.latency_score,
                cost_score=scores.cost_score,
                availability_score=scores.availability_score,
                reliability_score=scores.reliability_score,
            )

        snap = SimulationSnapshot(
            step=step,
            timestamp=ts,
            action=action,
            target_service_id=target_service_id,
            target_service_name=target_service_name,
            message=message,
            services=service_records,
        )
        self.snapshots.append(snap)
        return snap

    def reset(self) -> None:
        """Clear all historical snapshots."""
        self.snapshots.clear()

    def get_service_history_df(self, service_id: str) -> pd.DataFrame:
        """Extract a chronological DataFrame for a single service across all snapshots."""
        rows = []
        for snap in self.snapshots:
            if service_id in snap.services:
                rec = snap.services[service_id]
                rows.append({
                    "step": snap.step,
                    "timestamp": snap.timestamp,
                    "action": snap.action,
                    "label": f"Step {snap.step}: {snap.action}",
                    "service_id": rec.service_id,
                    "name": rec.name,
                    "latency": rec.latency,
                    "cost": rec.cost,
                    "availability": rec.availability,
                    "reliability": rec.reliability,
                    "health_status": rec.health_status,
                    "operational_status": rec.operational_status,
                    "qos_score": rec.qos_score,
                })
        return pd.DataFrame(rows)


# =========================================================================
# Plotly Visualization Builders
# =========================================================================

def build_qos_comparison_chart(
    services: List[CloudService],
    evaluator: QoSEvaluator,
    weights: Optional[Dict[str, float]],
    recommended_id: Optional[str],
    category: str,
) -> go.Figure:
    """Build the QoS Comparison Bar Chart distinguishing recommended, healthy, degraded, and unavailable services."""
    rows = []
    for s in services:
        scores = evaluator.evaluate_service(s, weights)
        is_rec = (s.service_id == recommended_id)
        health = classify_service_health(s)

        if is_rec:
            status_role = "Recommended"
        elif health == HEALTH_UNAVAILABLE:
            status_role = "Unavailable"
        elif health == HEALTH_DEGRADED:
            status_role = "Degraded"
        else:
            status_role = "Healthy"

        rows.append({
            "service_id": s.service_id,
            "name": s.name,
            "display_name": f"{s.service_id}<br>{s.name}",
            "qos_score": scores.qos_score,
            "status_role": status_role,
            "latency": s.latency,
            "cost": s.cost,
            "availability": s.availability,
            "reliability": s.reliability,
            "latency_score": scores.latency_score,
            "cost_score": scores.cost_score,
            "availability_score": scores.availability_score,
            "reliability_score": scores.reliability_score,
        })

    df = pd.DataFrame(rows)

    fig = go.Figure()

    # Add traces by status category to preserve legend groups and distinct colors
    order_groups = ["Recommended", "Healthy", "Degraded", "Unavailable"]
    for grp in order_groups:
        sub = df[df["status_role"] == grp]
        if sub.empty:
            continue

        hover_text = [
            f"<b>{r.name}</b> ({r.service_id})<br>"
            f"Role: <b>{r.status_role}</b><br>"
            f"Aggregate QoS Score: <b>{r.qos_score:.4f}</b><br>"
            f"------------------------------<br>"
            f"Latency: {r.latency:.1f} ms (Score: {r.latency_score:.2f})<br>"
            f"Cost: ${r.cost:.3f} (Score: {r.cost_score:.2f})<br>"
            f"Availability: {r.availability:.2f}% (Score: {r.availability_score:.2f})<br>"
            f"Reliability: {r.reliability:.2f}% (Score: {r.reliability_score:.2f})"
            for _, r in sub.iterrows()
        ]

        fig.add_trace(go.Bar(
            x=sub["display_name"],
            y=sub["qos_score"],
            name=grp,
            marker=dict(
                color=STATUS_COLORS[grp],
                line=dict(
                    color="#1E3A8A" if grp == "Recommended" else "#334155",
                    width=2 if grp == "Recommended" else 0.5,
                )
            ),
            text=[f"{val:.3f}" for val in sub["qos_score"]],
            textposition="outside",
            hovertext=hover_text,
            hoverinfo="text",
        ))

    fig.update_layout(
        title=dict(
            text=f"QoS Comparative Evaluation — Category: {category}",
            font=dict(size=16, family="Inter, sans-serif"),
        ),
        xaxis=dict(title="Candidate Cloud Services", tickfont=dict(size=11)),
        yaxis=dict(title="Aggregate Weighted QoS Score (0.0 – 1.0)", range=[0.0, 1.12]),
        legend=dict(title="Service Status / Role", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        barmode="group",
        margin=dict(l=40, r=40, t=60, b=40),
        template="plotly_white",
    )
    return fig


def build_qos_radar_chart(
    services: List[CloudService],
    evaluator: QoSEvaluator,
    recommended_id: Optional[str],
    selected_service_ids: Optional[List[str]] = None,
) -> go.Figure:
    """Build the QoS Radar Chart comparing the four dimensions (Latency, Cost, Availability, Reliability).

    All 4 dimensions are plotted using the normalized scores where higher = better (1.0 is optimal).
    """
    categories = ["Latency", "Cost", "Availability", "Reliability"]
    categories_closed = categories + [categories[0]]

    fig = go.Figure()

    # Filter to selected services or default to all services
    active_services = [s for s in services if selected_service_ids is None or s.service_id in selected_service_ids]

    palette = ["#2563EB", "#10B981", "#8B5CF6", "#F59E0B", "#06B6D4", "#EC4899", "#64748B"]

    for idx, s in enumerate(active_services):
        scores = evaluator.evaluate_service(s)
        is_rec = (s.service_id == recommended_id)

        # Dimension values (normalized 0.0 - 1.0, where 1.0 is best)
        vals = [
            scores.latency_score,
            scores.cost_score,
            scores.availability_score,
            scores.reliability_score,
        ]
        vals_closed = vals + [vals[0]]

        color = STATUS_COLORS["Recommended"] if is_rec else palette[idx % len(palette)]
        name_prefix = "⭐ " if is_rec else ""

        hover_text = [
            f"Latency: {s.latency:.1f}ms (Norm: {scores.latency_score:.2f})",
            f"Cost: ${s.cost:.3f} (Norm: {scores.cost_score:.2f})",
            f"Availability: {s.availability:.2f}% (Norm: {scores.availability_score:.2f})",
            f"Reliability: {s.reliability:.2f}% (Norm: {scores.reliability_score:.2f})",
            f"Latency: {s.latency:.1f}ms (Norm: {scores.latency_score:.2f})",
        ]

        fig.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=categories_closed,
            name=f"{name_prefix}{s.service_id} ({s.name})",
            fill="toself" if is_rec else "none",
            fillcolor="rgba(37, 99, 235, 0.15)" if is_rec else None,
            line=dict(
                color=color,
                width=3.5 if is_rec else 1.8,
                dash="solid" if is_rec else "dot" if s.operational_status == "UNAVAILABLE" else "solid",
            ),
            marker=dict(size=7 if is_rec else 5),
            hovertext=hover_text,
            hoverinfo="text+name",
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0.0, 1.0],
                tickvals=[0.2, 0.4, 0.6, 0.8, 1.0],
                ticktext=["0.2 (Poor)", "0.4", "0.6", "0.8", "1.0 (Optimal)"],
            )
        ),
        showlegend=True,
        title=dict(
            text="QoS Dimension Radar Comparison (Normalized 0–1, Outward is Better)",
            font=dict(size=16, family="Inter, sans-serif"),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=50, b=60),
        template="plotly_white",
    )
    return fig


def build_individual_metric_charts(services: List[CloudService]) -> Dict[str, go.Figure]:
    """Build individual interactive charts for Latency, Cost, Availability, and Reliability.

    Returns:
        Dict mapping metric key ('latency', 'cost', 'availability', 'reliability') to go.Figure.
    """
    charts = {}

    service_names = [f"{s.service_id}<br>{s.name}" for s in services]
    health_statuses = [classify_service_health(s) for s in services]

    # Helper to assign colors based on health
    def get_colors(for_metric: str) -> List[str]:
        cols = []
        for s, h in zip(services, health_statuses):
            if h == HEALTH_UNAVAILABLE:
                cols.append(STATUS_COLORS["Unavailable"])
            elif h == HEALTH_DEGRADED:
                # Highlight if this specific metric is degraded from baseline
                b = s.baseline
                if (for_metric == "latency" and s.latency > b["latency"]) or \
                   (for_metric == "cost" and s.cost > b["cost"]) or \
                   (for_metric == "availability" and s.availability < b["availability"]) or \
                   (for_metric == "reliability" and s.reliability < b["reliability"]):
                    cols.append(STATUS_COLORS["Degraded"])
                else:
                    cols.append("#94A3B8")  # Neutral slate
            else:
                cols.append(STATUS_COLORS["Healthy"])
        return cols

    # 1. Latency (ms) - lower is better
    lat_vals = [s.latency for s in services]
    lat_colors = get_colors("latency")
    fig_lat = go.Figure()
    fig_lat.add_trace(go.Bar(
        x=service_names,
        y=lat_vals,
        marker_color=lat_colors,
        text=[f"{v:.1f} ms" for v in lat_vals],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Latency: %{y:.1f} ms<extra></extra>",
    ))
    fig_lat.update_layout(
        title="Latency Comparison (Lower is Better)",
        xaxis_title="Candidate Services",
        yaxis_title="Response Time (ms)",
        template="plotly_white",
        margin=dict(l=30, r=30, t=40, b=30),
    )
    charts["latency"] = fig_lat

    # 2. Cost ($) - lower is better
    cost_vals = [s.cost for s in services]
    cost_colors = get_colors("cost")
    fig_cost = go.Figure()
    fig_cost.add_trace(go.Bar(
        x=service_names,
        y=cost_vals,
        marker_color=cost_colors,
        text=[f"${v:.3f}" for v in cost_vals],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Cost: $%{y:.3f}<extra></extra>",
    ))
    fig_cost.update_layout(
        title="Cost Comparison (Lower is Better)",
        xaxis_title="Candidate Services",
        yaxis_title="Cost ($ per invocation)",
        template="plotly_white",
        margin=dict(l=30, r=30, t=40, b=30),
    )
    charts["cost"] = fig_cost

    # 3. Availability (%) - higher is better
    avail_vals = [s.availability for s in services]
    avail_colors = get_colors("availability")
    fig_avail = go.Figure()
    fig_avail.add_trace(go.Bar(
        x=service_names,
        y=avail_vals,
        marker_color=avail_colors,
        text=[f"{v:.2f}%" for v in avail_vals],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Availability: %{y:.2f}%<extra></extra>",
    ))
    fig_avail.update_layout(
        title="Availability Comparison (Higher is Better)",
        xaxis_title="Candidate Services",
        yaxis_title="Availability (%)",
        yaxis_range=[0, 105],
        template="plotly_white",
        margin=dict(l=30, r=30, t=40, b=30),
    )
    charts["availability"] = fig_avail

    # 4. Reliability (%) - higher is better
    rel_vals = [s.reliability for s in services]
    rel_colors = get_colors("reliability")
    fig_rel = go.Figure()
    fig_rel.add_trace(go.Bar(
        x=service_names,
        y=rel_vals,
        marker_color=rel_colors,
        text=[f"{v:.2f}%" for v in rel_vals],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Reliability: %{y:.2f}%<extra></extra>",
    ))
    fig_rel.update_layout(
        title="Reliability Comparison (Higher is Better)",
        xaxis_title="Candidate Services",
        yaxis_title="Reliability (%)",
        yaxis_range=[0, 105],
        template="plotly_white",
        margin=dict(l=30, r=30, t=40, b=30),
    )
    charts["reliability"] = fig_rel

    return charts


def build_health_donut_chart(services: List[CloudService]) -> go.Figure:
    """Build a donut chart showing the health distribution (Healthy, Degraded, Unavailable)."""
    counts = {
        "Healthy": 0,
        "Degraded": 0,
        "Unavailable": 0,
    }

    for s in services:
        h = classify_service_health(s)
        if h == HEALTH_UNAVAILABLE:
            counts["Unavailable"] += 1
        elif h == HEALTH_DEGRADED:
            counts["Degraded"] += 1
        else:
            counts["Healthy"] += 1

    labels = ["Healthy", "Degraded", "Unavailable"]
    values = [counts[l] for l in labels]
    colors = [STATUS_COLORS["Healthy"], STATUS_COLORS["Degraded"], STATUS_COLORS["Unavailable"]]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="label+value",
        hovertemplate="<b>%{label}</b>: %{value} services (%{percent})<extra></extra>",
    )])

    total = sum(values)
    fig.update_layout(
        title=dict(text="Service Health Distribution", font=dict(size=15, family="Inter, sans-serif")),
        annotations=[dict(text=f"<b>{total}</b><br>Total", x=0.5, y=0.5, font_size=16, showarrow=False)],
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        margin=dict(l=20, r=20, t=40, b=30),
        template="plotly_white",
    )
    return fig


def build_before_after_chart(
    target_service_id: str,
    target_service_name: str,
    action: str,
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> go.Figure:
    """Build a grouped comparison chart displaying before vs after metric changes."""
    # Create subplots for Latency (ms) and Percentage Metrics (Availability %, Reliability %, QoS Score %)
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Latency Impact (Response Time ms)", "Percentage Metrics (Avail, Rel, QoS Score)"),
        horizontal_spacing=0.15,
    )

    # Subplot 1: Latency
    fig.add_trace(
        go.Bar(
            name="Before Action",
            x=["Latency (ms)"],
            y=[before.get("latency", 0)],
            marker_color="#94A3B8",
            text=[f"{before.get('latency', 0):.1f}ms"],
            textposition="outside",
            showlegend=True,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(
            name="After Action",
            x=["Latency (ms)"],
            y=[after.get("latency", 0)],
            marker_color=STATUS_COLORS["Recommended"] if action == "Restore Baseline" else STATUS_COLORS["Degraded"],
            text=[f"{after.get('latency', 0):.1f}ms"],
            textposition="outside",
            showlegend=True,
        ),
        row=1, col=1,
    )

    # Subplot 2: Availability, Reliability, QoS Score (scaled 0-100)
    metrics_pct = ["Availability (%)", "Reliability (%)", "QoS Score (x100)"]
    before_vals = [
        before.get("availability", 0),
        before.get("reliability", 0),
        before.get("qos_score", 0) * 100,
    ]
    after_vals = [
        after.get("availability", 0),
        after.get("reliability", 0),
        after.get("qos_score", 0) * 100,
    ]

    fig.add_trace(
        go.Bar(
            name="Before Action",
            x=metrics_pct,
            y=before_vals,
            marker_color="#94A3B8",
            text=[f"{v:.1f}" for v in before_vals],
            textposition="outside",
            showlegend=False,
        ),
        row=1, col=2,
    )
    fig.add_trace(
        go.Bar(
            name="After Action",
            x=metrics_pct,
            y=after_vals,
            marker_color=STATUS_COLORS["Recommended"] if action == "Restore Baseline" else STATUS_COLORS["Degraded"],
            text=[f"{v:.1f}" for v in after_vals],
            textposition="outside",
            showlegend=False,
        ),
        row=1, col=2,
    )

    fig.update_layout(
        title=f"Failure Impact / Recovery Analysis: {target_service_id} ({target_service_name}) — [{action}]",
        barmode="group",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        margin=dict(l=30, r=30, t=60, b=30),
    )
    return fig


def build_history_timeline_chart(
    history_df: pd.DataFrame,
    service_id: str,
    service_name: str,
) -> go.Figure:
    """Build multi-line chart tracking historical QoS metrics across simulation sequence steps."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=("Aggregate QoS Score & Latency (ms)", "Availability & Reliability (%)"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
    )

    steps = history_df["step"].tolist()
    step_labels = [f"Step {s}: {act}" for s, act in zip(steps, history_df["action"])]

    # Top plot: QoS Score (left) & Latency (right secondary y)
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=history_df["qos_score"],
            name="Aggregate QoS Score",
            mode="lines+markers",
            line=dict(color="#2563EB", width=3),
            marker=dict(size=8),
            hovertext=[f"{lbl}<br>QoS Score: {val:.4f}" for lbl, val in zip(step_labels, history_df["qos_score"])],
            hoverinfo="text",
        ),
        row=1, col=1, secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=steps,
            y=history_df["latency"],
            name="Latency (ms)",
            mode="lines+markers",
            line=dict(color="#DC2626", width=2, dash="dash"),
            marker=dict(size=7),
            hovertext=[f"{lbl}<br>Latency: {val:.1f}ms" for lbl, val in zip(step_labels, history_df["latency"])],
            hoverinfo="text",
        ),
        row=1, col=1, secondary_y=True,
    )

    # Bottom plot: Availability & Reliability
    fig.add_trace(
        go.Scatter(
            x=steps,
            y=history_df["availability"],
            name="Availability (%)",
            mode="lines+markers",
            line=dict(color="#10B981", width=2.5),
            marker=dict(size=7),
            hovertext=[f"{lbl}<br>Availability: {val:.2f}%" for lbl, val in zip(step_labels, history_df["availability"])],
            hoverinfo="text",
        ),
        row=2, col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=steps,
            y=history_df["reliability"],
            name="Reliability (%)",
            mode="lines+markers",
            line=dict(color="#8B5CF6", width=2.5),
            marker=dict(size=7),
            hovertext=[f"{lbl}<br>Reliability: {val:.2f}%" for lbl, val in zip(step_labels, history_df["reliability"])],
            hoverinfo="text",
        ),
        row=2, col=1,
    )

    fig.update_xaxes(
        title_text="Simulation Step Sequence",
        tickmode="array",
        tickvals=steps,
        ticktext=[f"Step {s}" for s in steps],
        row=2, col=1,
    )
    fig.update_yaxes(title_text="QoS Score (0–1)", range=[0, 1.05], row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Latency (ms)", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Percentage (%)", range=[0, 105], row=2, col=1)

    fig.update_layout(
        title=f"Historical Performance Trend — {service_id} ({service_name})",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1),
        margin=dict(l=30, r=30, t=60, b=30),
        height=550,
    )
    return fig
