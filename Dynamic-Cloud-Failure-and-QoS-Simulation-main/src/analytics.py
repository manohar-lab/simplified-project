"""Visual analytics, health classification, and snapshot tracking helpers.

This module provides data models, health status classification, simulation
history snapshot tracking, and Plotly visualization builders for the
Dynamic Cloud Failure and QoS Reselection dashboard.

All calculations strictly reuse the existing service registry and QoS evaluator
without modifying any underlying scoring formulas, weights, or simulation rules.
"""

from __future__ import annotations
import copy
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.service_registry import CloudService
from src.qos_evaluator import MetricScores, QoSEvaluator, METRICS
from src.sla_config import validate_service_sla


# =========================================================================
# Status & Theme Constants
# =========================================================================
HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_UNAVAILABLE = "UNAVAILABLE"
HEALTH_RECOVERED = "RECOVERED"

STATUS_COLORS = {
    "Recommended": "#2563EB",          # Royal Blue
    "Healthy": "#10B981",              # Emerald Green
    "Recovered": "#06B6D4",            # Cyan / Restored Healthy
    "Degraded": "#F59E0B",             # Amber / Orange
    "Unavailable": "#EF4444",          # Crimson Red
}


def _metrics_are_valid(service: CloudService) -> bool:
    """Safely check that all service QoS metrics are finite and within physically valid bounds."""
    lat = getattr(service, "latency", None)
    cost = getattr(service, "cost", None)
    avail = getattr(service, "availability", None)
    rel = getattr(service, "reliability", None)

    for val in (lat, cost, avail, rel):
        if val is None or isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
            return False

    if lat < 0.0 or cost < 0.0:
        return False
    if not (0.0 <= avail <= 100.0) or not (0.0 <= rel <= 100.0):
        return False
    return True


def classify_service_health(
    service: CloudService,
    sla_config: Optional[Any] = None,
    previous_health: Optional[str] = None,
) -> str:
    """Determine the health status of a candidate service.

    Canonical health classification shared across analytics and periodic monitoring.

    Classification rules:
    - UNAVAILABLE: operational_status is "UNAVAILABLE" (or non-"AVAILABLE").
    - DEGRADED: operational_status is "AVAILABLE" AND any of:
        1. Any QoS metric is invalid, missing, non-finite, or out of valid bounds.
        2. sla_config is provided and the service violates one or more SLA constraints.
        3. One or more metrics are degraded relative to the service's baseline
           (higher latency, lower availability, lower reliability, or higher cost).
    - RECOVERED: Service is healthy and SLA-compliant after previously being in
      DEGRADED or UNAVAILABLE state.
    - HEALTHY: operational_status is "AVAILABLE", metrics are valid and SLA-compliant,
      and all metrics are at or better than baseline values.

    Args:
        service: The CloudService instance to evaluate.
        sla_config: Optional active SLAConfig to ensure classification aligns with SLA eligibility.
        previous_health: Optional prior health status to detect recovery transitions.

    Returns:
        One of "HEALTHY", "DEGRADED", "UNAVAILABLE", or "RECOVERED".
    """
    status = getattr(service, "operational_status", "UNAVAILABLE")
    if status == "UNAVAILABLE" or status != "AVAILABLE":
        return HEALTH_UNAVAILABLE

    if not _metrics_are_valid(service):
        return HEALTH_DEGRADED

    # Check hard SLA constraints if provided
    if sla_config is not None:
        violations = validate_service_sla(service, sla_config)
        if violations:
            return HEALTH_DEGRADED

    b = getattr(service, "baseline", {}) or {}
    # Compare current metrics against immutable baseline values
    is_degraded = (
        service.latency > b.get("latency", service.latency)
        or service.availability < b.get("availability", service.availability)
        or service.reliability < b.get("reliability", service.reliability)
        or service.cost > b.get("cost", service.cost)
    )
    if is_degraded:
        return HEALTH_DEGRADED

    if previous_health in (HEALTH_DEGRADED, HEALTH_UNAVAILABLE):
        return HEALTH_RECOVERED

    return HEALTH_HEALTHY


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
            is_outage = (s.operational_status == "UNAVAILABLE")
            service_records[s.service_id] = ServiceStateRecord(
                service_id=s.service_id,
                name=s.name,
                category=s.category,
                latency=s.latency,
                cost=s.cost,
                availability=0.0 if is_outage else s.availability,
                reliability=0.0 if is_outage else s.reliability,
                operational_status=s.operational_status,
                health_status=health,
                qos_score=0.0 if is_outage else scores.qos_score,
                latency_score=scores.latency_score,
                cost_score=scores.cost_score,
                availability_score=0.0 if is_outage else scores.availability_score,
                reliability_score=0.0 if is_outage else scores.reliability_score,
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
    sla_config: Optional[Any] = None,
    operating_mode: Optional[str] = None,
) -> go.Figure:
    """Build the QoS Comparison Bar Chart distinguishing recommended, healthy, degraded, and unavailable services."""
    rows = []
    # Sort services by service_id to guarantee a stable, predictable x-axis order
    ordered_services = sorted(services, key=lambda s: s.service_id)

    for s in ordered_services:
        scores = evaluator.evaluate_service(s, weights)
        is_rec = (s.service_id == recommended_id)
        is_outage = (s.operational_status == "UNAVAILABLE")
        is_sla_violated = bool(sla_config and validate_service_sla(s, sla_config))
        health = classify_service_health(s, sla_config=sla_config)

        if is_rec:
            status_role = "Recommended"
        elif is_outage:
            status_role = "Unavailable"
        elif is_sla_violated:
            status_role = "SLA Breach"
        elif health == HEALTH_DEGRADED:
            status_role = "Degraded"
        else:
            status_role = "Healthy"

        if is_rec:
            badge = "🎯 [OVERRIDE]" if operating_mode == "MANUAL_OVERRIDE" else "⭐ [WINNER]"
        elif is_outage:
            badge = "🔴 [OUTAGE]"
        elif is_sla_violated:
            badge = "⚠️ [SLA BREACH]"
        elif health == HEALTH_DEGRADED:
            badge = "⚠️ [DEGRADED]"
        else:
            badge = "🟢 [HEALTHY]"

        disp_prefix = "⭐ " if is_rec else "🔴 " if is_outage else "⚠️ " if (is_sla_violated or health == HEALTH_DEGRADED) else ""
        display_name = f"{disp_prefix}<b>{s.service_id}</b><br>{s.name}"

        # An unavailable service is excluded by the engine (effective QoS for selection = 0)
        plot_score = 0.0 if is_outage else scores.qos_score

        if is_rec:
            bar_text = f"⭐ {scores.qos_score:.3f}"
        elif is_outage:
            bar_text = "❌ 0.000 [OUTAGE]"
        elif is_sla_violated:
            bar_text = f"⚠️ {scores.qos_score:.3f} [SLA]"
        else:
            bar_text = f"{scores.qos_score:.3f}"

        rows.append({
            "service_id": s.service_id,
            "name": s.name,
            "display_name": display_name,
            "qos_score": plot_score,
            "raw_qos_score": scores.qos_score,
            "status_role": status_role,
            "badge": badge,
            "is_rec": is_rec,
            "is_outage": is_outage,
            "is_sla_violated": is_sla_violated,
            "latency": s.latency,
            "cost": s.cost,
            "availability": s.availability,
            "reliability": s.reliability,
            "latency_score": scores.latency_score,
            "cost_score": scores.cost_score,
            "availability_score": scores.availability_score,
            "reliability_score": scores.reliability_score,
            "bar_text": bar_text,
        })

    df = pd.DataFrame(rows)
    fig = go.Figure()

    status_color_map = {
        "Recommended": STATUS_COLORS["Recommended"],
        "Healthy": STATUS_COLORS["Healthy"],
        "Degraded": STATUS_COLORS["Degraded"],
        "SLA Breach": "#DC2626",
        "Unavailable": STATUS_COLORS["Unavailable"],
    }

    order_groups = ["Recommended", "Healthy", "Degraded", "SLA Breach", "Unavailable"]
    all_categories = df["display_name"].tolist()

    for grp in order_groups:
        sub = df[df["status_role"] == grp]
        if sub.empty:
            continue

        hover_text = []
        for _, r in sub.iterrows():
            elig_str = (
                "❌ INELIGIBLE — Disqualified due to active Outage"
                if r["is_outage"]
                else (
                    "❌ INELIGIBLE — Violates configured SLA thresholds"
                    if r["is_sla_violated"]
                    else "✅ ELIGIBLE — Candidate compliant"
                )
            )
            role_str = (
                "🎯 Active Selected Service (Manual Override)"
                if (r["is_rec"] and operating_mode == "MANUAL_OVERRIDE")
                else (
                    "⭐ Active Selected Service (Automatic #1)"
                    if r["is_rec"]
                    else ("🔴 Outage / Disqualified" if r["is_outage"] else "Candidate Alternative")
                )
            )
            hover_text.append(
                f"<b>{r['name']}</b> ({r['service_id']})<br>"
                f"Status: <b>{r['badge']}</b><br>"
                f"Role: <b>{role_str}</b><br>"
                f"Eligibility: <b>{elig_str}</b><br>"
                f"Aggregate QoS Score: <b>{r['raw_qos_score']:.4f}</b><br>"
                f"----------------------------------------<br>"
                f"• Latency: {r['latency']:.1f} ms (Score: {r['latency_score']:.2f})<br>"
                f"• Cost: ${r['cost']:.3f} (Score: {r['cost_score']:.2f})<br>"
                f"• Availability: {r['availability']:.2f}% (Score: {r['availability_score']:.2f})<br>"
                f"• Reliability: {r['reliability']:.2f}% (Score: {r['reliability_score']:.2f})"
            )

        fig.add_trace(go.Bar(
            x=sub["display_name"],
            y=sub["qos_score"],
            name=grp,
            marker=dict(
                color=status_color_map.get(grp, "#64748B"),
                line=dict(
                    color="#1E3A8A" if grp == "Recommended" else "#7F1D1D" if grp == "Unavailable" else "#334155",
                    width=2.5 if grp == "Recommended" else 1.2 if grp == "Unavailable" else 0.5,
                ),
            ),
            text=sub["bar_text"],
            textposition="outside",
            hovertext=hover_text,
            hoverinfo="text",
            width=0.55,
        ))

    fig.update_layout(
        title=dict(
            text=f"QoS Comparative Evaluation — Category: {category} (Dynamic Reselection & Health)",
            font=dict(size=16, family="Inter, sans-serif"),
        ),
        xaxis=dict(
            title="Candidate Cloud Services",
            tickfont=dict(size=11),
            categoryorder="array",
            categoryarray=all_categories,
        ),
        yaxis=dict(
            title="Aggregate Weighted QoS Score (0.0 – 1.0)",
            range=[0.0, 1.15],
            gridcolor="#F1F5F9",
        ),
        legend=dict(
            title="Service Status / Role",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        barmode="overlay",
        margin=dict(l=40, r=40, t=60, b=40),
        template="plotly_white",
    )
    return fig


def build_qos_radar_chart(
    services: List[CloudService],
    evaluator: QoSEvaluator,
    recommended_id: Optional[str],
    selected_service_ids: Optional[List[str]] = None,
    sla_config: Optional[Any] = None,
    operating_mode: Optional[str] = None,
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
        is_outage = (s.operational_status == "UNAVAILABLE")

        # In an outage, operational availability and reliability are 0.0
        avail_score = 0.0 if is_outage else scores.availability_score
        rel_score = 0.0 if is_outage else scores.reliability_score

        # Dimension values (normalized 0.0 - 1.0, where 1.0 is best)
        vals = [
            scores.latency_score,
            scores.cost_score,
            avail_score,
            rel_score,
        ]
        vals_closed = vals + [vals[0]]

        if is_rec:
            color = "#1D4ED8"
            name_label = f"🎯 {s.service_id} ({s.name}) [OVERRIDE]" if operating_mode == "MANUAL_OVERRIDE" else f"⭐ {s.service_id} ({s.name}) [SELECTED]"
        elif is_outage:
            color = "#EF4444"
            name_label = f"🔴 {s.service_id} ({s.name}) [OUTAGE]"
        else:
            color = palette[idx % len(palette)]
            name_label = f"{s.service_id} ({s.name})"

        hover_text = [
            f"Latency: {s.latency:.1f}ms (Norm: {scores.latency_score:.2f})",
            f"Cost: ${s.cost:.3f} (Norm: {scores.cost_score:.2f})",
            f"Availability: {'0.0% [OUTAGE]' if is_outage else f'{s.availability:.2f}%'} (Norm: {avail_score:.2f})",
            f"Reliability: {'0.0% [OUTAGE]' if is_outage else f'{s.reliability:.2f}%'} (Norm: {rel_score:.2f})",
            f"Latency: {s.latency:.1f}ms (Norm: {scores.latency_score:.2f})",
        ]

        fig.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=categories_closed,
            name=name_label,
            fill="toself" if is_rec else "none",
            fillcolor="rgba(37, 99, 235, 0.18)" if is_rec else None,
            line=dict(
                color=color,
                width=3.5 if is_rec else 2.2 if is_outage else 1.8,
                dash="solid" if is_rec else "dot" if is_outage else "solid",
            ),
            marker=dict(size=8 if is_rec else 6),
            hovertext=hover_text,
            hoverinfo="text+name",
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0.0, 1.05],
                tickvals=[0.2, 0.4, 0.6, 0.8, 1.0],
                ticktext=["0.2 (Poor)", "0.4", "0.6", "0.8", "1.0 (Optimal)"],
                gridcolor="#E2E8F0",
            ),
            angularaxis=dict(gridcolor="#E2E8F0"),
        ),
        showlegend=True,
        title=dict(
            text="Multi-Dimensional QoS Radar Profile (Normalized 0.0–1.0, Outward is Better)",
            font=dict(size=16, family="Inter, sans-serif"),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=50, b=60),
        template="plotly_white",
    )
    return fig


def build_individual_metric_charts(
    services: List[CloudService],
    recommended_id: Optional[str] = None,
    sla_config: Optional[Any] = None,
    operating_mode: Optional[str] = None,
) -> Dict[str, go.Figure]:
    """Build individual interactive charts for Latency, Cost, Availability, and Reliability.

    Enhanced with dynamic failure response, SLA threshold reference lines,
    prominent highlighting of the currently selected / reselected service,
    and clear visual indicators for outages and SLA violations.

    Returns:
        Dict mapping metric key ('latency', 'cost', 'availability', 'reliability') to go.Figure.
    """
    charts = {}
    ordered_services = sorted(services, key=lambda s: s.service_id)

    # Common labels
    service_names = []
    for s in ordered_services:
        is_rec = (s.service_id == recommended_id)
        is_outage = (s.operational_status == "UNAVAILABLE")
        prefix = "⭐ " if is_rec else "🔴 " if is_outage else ""
        service_names.append(f"{prefix}<b>{s.service_id}</b><br>{s.name}")

    # Outline colors and widths
    borders = []
    border_widths = []
    for s in ordered_services:
        if s.service_id == recommended_id:
            borders.append("#1D4ED8")
            border_widths.append(3.0)
        elif s.operational_status == "UNAVAILABLE":
            borders.append("#B91C1C")
            border_widths.append(2.0)
        else:
            borders.append("#334155")
            border_widths.append(0.5)

    # -------------------------------------------------------------
    # 1. Latency (ms) - lower is better
    # -------------------------------------------------------------
    lat_vals = []
    lat_texts = []
    lat_colors = []
    lat_hovers = []

    for s in ordered_services:
        is_rec = (s.service_id == recommended_id)
        is_outage = (s.operational_status == "UNAVAILABLE")
        b_lat = s.baseline.get("latency", s.latency)
        d_lat = s.latency - b_lat
        sla_lat = getattr(sla_config, "max_latency", None) if sla_config else None
        is_sla_violated = (sla_lat is not None and s.latency > sla_lat)

        role = (
            "🎯 Active Selection (Manual Override)"
            if (is_rec and operating_mode == "MANUAL_OVERRIDE")
            else ("⭐ Active Selection (Automatic #1)" if is_rec else "Candidate Alternative")
        )

        if is_outage:
            lat_vals.append(s.latency)
            lat_texts.append("🔴 OFFLINE")
            lat_colors.append(STATUS_COLORS["Unavailable"])
            status_desc = "🔴 UNAVAILABLE (Outage Active)"
            elig = "❌ INELIGIBLE — Disqualified (Outage)"
        else:
            lat_vals.append(s.latency)
            if is_rec:
                lat_texts.append(f"⭐ {s.latency:.1f} ms")
                lat_colors.append(STATUS_COLORS["Recommended"])
            elif is_sla_violated:
                lat_texts.append(f"⚠️ {s.latency:.1f} ms [SLA]")
                lat_colors.append("#DC2626")
            elif d_lat > 0:
                lat_texts.append(f"{s.latency:.1f} ms (+{d_lat:.0f})")
                lat_colors.append(STATUS_COLORS["Degraded"])
            else:
                lat_texts.append(f"{s.latency:.1f} ms")
                lat_colors.append(STATUS_COLORS["Healthy"])

            status_desc = "⚠️ SLA BREACH" if is_sla_violated else ("⚠️ DEGRADED" if d_lat > 0 else "🟢 HEALTHY")
            elig = "❌ INELIGIBLE (SLA)" if is_sla_violated else "✅ ELIGIBLE"

        sla_info = f"Max SLA: {sla_lat:.1f} ms ({'❌ BREACHED' if is_sla_violated else '✅ OK'})" if sla_lat else "No SLA constraint"
        lat_hovers.append(
            f"<b>{s.name}</b> ({s.service_id})<br>"
            f"Role: <b>{role}</b><br>"
            f"Status: <b>{status_desc}</b> ({elig})<br>"
            f"Latency: <b>{s.latency:.1f} ms</b> (Baseline: {b_lat:.1f} ms, Δ: {d_lat:+.1f} ms)<br>"
            f"SLA Check: {sla_info}"
        )

    fig_lat = go.Figure()
    fig_lat.add_trace(go.Bar(
        x=service_names,
        y=lat_vals,
        marker=dict(
            color=lat_colors,
            line=dict(color=borders, width=border_widths),
        ),
        text=lat_texts,
        textposition="outside",
        hovertext=lat_hovers,
        hoverinfo="text",
        width=0.55,
    ))
    if sla_config and hasattr(sla_config, "max_latency") and sla_config.max_latency:
        fig_lat.add_hline(
            y=float(sla_config.max_latency),
            line_dash="dash",
            line_color="#DC2626",
            line_width=1.8,
            annotation_text=f"Max SLA ({sla_config.max_latency:.0f} ms)",
            annotation_position="top right",
            annotation_font=dict(color="#DC2626", size=10),
        )
    max_lat = max(lat_vals) if lat_vals else 100.0
    upper_lat = max(max_lat * 1.25, (float(sla_config.max_latency) * 1.15) if (sla_config and hasattr(sla_config, "max_latency")) else 100.0)
    fig_lat.update_layout(
        title=dict(text="Response Time / Latency Comparison (Lower is Better)", font=dict(size=14, family="Inter, sans-serif")),
        xaxis=dict(title="Candidate Services", tickfont=dict(size=10)),
        yaxis=dict(title="Response Time (ms)", range=[0, upper_lat], gridcolor="#F1F5F9"),
        template="plotly_white",
        margin=dict(l=35, r=35, t=45, b=35),
    )
    charts["latency"] = fig_lat

    # -------------------------------------------------------------
    # 2. Cost ($) - lower is better
    # -------------------------------------------------------------
    cost_vals = []
    cost_texts = []
    cost_colors = []
    cost_hovers = []

    for s in ordered_services:
        is_rec = (s.service_id == recommended_id)
        is_outage = (s.operational_status == "UNAVAILABLE")
        b_cost = s.baseline.get("cost", s.cost)
        d_cost = s.cost - b_cost

        cost_vals.append(s.cost)
        if is_outage:
            cost_texts.append(f"${s.cost:.3f}")
            cost_colors.append(STATUS_COLORS["Unavailable"])
            status_desc = "🔴 UNAVAILABLE (Outage Active)"
        elif is_rec:
            cost_texts.append(f"⭐ ${s.cost:.3f}")
            cost_colors.append(STATUS_COLORS["Recommended"])
            status_desc = "⭐ ACTIVE SELECTION"
        elif d_cost > 0:
            cost_texts.append(f"${s.cost:.3f}")
            cost_colors.append(STATUS_COLORS["Degraded"])
            status_desc = "⚠️ DEGRADED"
        else:
            cost_texts.append(f"${s.cost:.3f}")
            cost_colors.append("#0D9488")
            status_desc = "🟢 HEALTHY"

        cost_hovers.append(
            f"<b>{s.name}</b> ({s.service_id})<br>"
            f"Status: <b>{status_desc}</b><br>"
            f"Cost per Invocation: <b>${s.cost:.3f}</b> (Baseline: ${b_cost:.3f}, Δ: ${d_cost:+.3f})"
        )

    fig_cost = go.Figure()
    fig_cost.add_trace(go.Bar(
        x=service_names,
        y=cost_vals,
        marker=dict(
            color=cost_colors,
            line=dict(color=borders, width=border_widths),
        ),
        text=cost_texts,
        textposition="outside",
        hovertext=cost_hovers,
        hoverinfo="text",
        width=0.55,
    ))
    max_c = max(cost_vals) if cost_vals else 0.1
    fig_cost.update_layout(
        title=dict(text="Cost per Invocation Comparison (Lower is Better)", font=dict(size=14, family="Inter, sans-serif")),
        xaxis=dict(title="Candidate Services", tickfont=dict(size=10)),
        yaxis=dict(title="Cost ($ per invocation)", range=[0, max_c * 1.25], gridcolor="#F1F5F9"),
        template="plotly_white",
        margin=dict(l=35, r=35, t=45, b=35),
    )
    charts["cost"] = fig_cost

    # -------------------------------------------------------------
    # 3. Availability (%) - higher is better
    # -------------------------------------------------------------
    avail_vals = []
    avail_texts = []
    avail_colors = []
    avail_hovers = []
    has_any_outage = any(s.operational_status == "UNAVAILABLE" for s in ordered_services)

    for s in ordered_services:
        is_rec = (s.service_id == recommended_id)
        is_outage = (s.operational_status == "UNAVAILABLE")
        b_avail = s.baseline.get("availability", s.availability)
        sla_avail = getattr(sla_config, "min_availability", None) if sla_config else None
        eff_avail = 0.0 if is_outage else s.availability
        d_avail = eff_avail - b_avail
        is_sla_violated = (sla_avail is not None and not is_outage and s.availability < sla_avail)

        avail_vals.append(eff_avail)
        if is_outage:
            avail_texts.append("🔴 0.0% [OUTAGE]")
            avail_colors.append(STATUS_COLORS["Unavailable"])
            status_desc = "🔴 UNAVAILABLE (Total Outage — Disqualified)"
        elif is_rec:
            avail_texts.append(f"⭐ {s.availability:.2f}%")
            avail_colors.append(STATUS_COLORS["Recommended"])
            status_desc = "⭐ ACTIVE SELECTION"
        elif is_sla_violated:
            avail_texts.append(f"⚠️ {s.availability:.2f}% [SLA]")
            avail_colors.append("#DC2626")
            status_desc = "⚠️ SLA BREACH (Ineligible)"
        elif d_avail < 0:
            avail_texts.append(f"{s.availability:.2f}% ({d_avail:.1f}%)")
            avail_colors.append(STATUS_COLORS["Degraded"])
            status_desc = "⚠️ DEGRADED"
        else:
            avail_texts.append(f"{s.availability:.2f}%")
            avail_colors.append(STATUS_COLORS["Healthy"])
            status_desc = "🟢 HEALTHY"

        sla_info = f"Min SLA: {sla_avail:.1f}% ({'❌ BREACHED' if is_sla_violated else '✅ OK'})" if sla_avail else "No SLA constraint"
        avail_hovers.append(
            f"<b>{s.name}</b> ({s.service_id})<br>"
            f"Status: <b>{status_desc}</b><br>"
            f"Operational Availability: <b>{eff_avail:.2f}%</b> (Baseline: {b_avail:.2f}%, Δ: {d_avail:+.2f}%)<br>"
            f"SLA Check: {sla_info}"
        )

    fig_avail = go.Figure()
    fig_avail.add_trace(go.Bar(
        x=service_names,
        y=avail_vals,
        marker=dict(
            color=avail_colors,
            line=dict(color=borders, width=border_widths),
        ),
        text=avail_texts,
        textposition="outside",
        hovertext=avail_hovers,
        hoverinfo="text",
        width=0.55,
    ))
    if sla_config and hasattr(sla_config, "min_availability") and sla_config.min_availability:
        fig_avail.add_hline(
            y=float(sla_config.min_availability),
            line_dash="dash",
            line_color="#DC2626",
            line_width=1.8,
            annotation_text=f"Min SLA ({sla_config.min_availability:.1f}%)",
            annotation_position="bottom right",
            annotation_font=dict(color="#DC2626", size=10),
        )
    # Dynamic zoom for readability if no outage
    if has_any_outage:
        avail_range = [0, 112]
    else:
        min_a = min(avail_vals) if avail_vals else 90.0
        floor_a = max(0.0, min_a - 3.0)
        if sla_config and hasattr(sla_config, "min_availability"):
            floor_a = min(floor_a, float(sla_config.min_availability) - 3.0)
        avail_range = [max(0.0, floor_a), 105]

    fig_avail.update_layout(
        title=dict(text="Availability Percentage Comparison (Higher is Better)", font=dict(size=14, family="Inter, sans-serif")),
        xaxis=dict(title="Candidate Services", tickfont=dict(size=10)),
        yaxis=dict(title="Availability (%)", range=avail_range, gridcolor="#F1F5F9"),
        template="plotly_white",
        margin=dict(l=35, r=35, t=45, b=35),
    )
    charts["availability"] = fig_avail

    # -------------------------------------------------------------
    # 4. Reliability (%) - higher is better
    # -------------------------------------------------------------
    rel_vals = []
    rel_texts = []
    rel_colors = []
    rel_hovers = []

    for s in ordered_services:
        is_rec = (s.service_id == recommended_id)
        is_outage = (s.operational_status == "UNAVAILABLE")
        b_rel = s.baseline.get("reliability", s.reliability)
        sla_rel = getattr(sla_config, "min_reliability", None) if sla_config else None
        eff_rel = 0.0 if is_outage else s.reliability
        d_rel = eff_rel - b_rel
        is_sla_violated = (sla_rel is not None and not is_outage and s.reliability < sla_rel)

        rel_vals.append(eff_rel)
        if is_outage:
            rel_texts.append("🔴 0.0% [OUTAGE]")
            rel_colors.append(STATUS_COLORS["Unavailable"])
            status_desc = "🔴 UNAVAILABLE (Total Outage — Disqualified)"
        elif is_rec:
            rel_texts.append(f"⭐ {s.reliability:.2f}%")
            rel_colors.append(STATUS_COLORS["Recommended"])
            status_desc = "⭐ ACTIVE SELECTION"
        elif is_sla_violated:
            rel_texts.append(f"⚠️ {s.reliability:.2f}% [SLA]")
            rel_colors.append("#DC2626")
            status_desc = "⚠️ SLA BREACH (Ineligible)"
        elif d_rel < 0:
            rel_texts.append(f"{s.reliability:.2f}% ({d_rel:.1f}%)")
            rel_colors.append(STATUS_COLORS["Degraded"])
            status_desc = "⚠️ DEGRADED"
        else:
            rel_texts.append(f"{s.reliability:.2f}%")
            rel_colors.append("#8B5CF6")
            status_desc = "🟢 HEALTHY"

        sla_info = f"Min SLA: {sla_rel:.1f}% ({'❌ BREACHED' if is_sla_violated else '✅ OK'})" if sla_rel else "No SLA constraint"
        rel_hovers.append(
            f"<b>{s.name}</b> ({s.service_id})<br>"
            f"Status: <b>{status_desc}</b><br>"
            f"Operational Reliability: <b>{eff_rel:.2f}%</b> (Baseline: {b_rel:.2f}%, Δ: {d_rel:+.2f}%)<br>"
            f"SLA Check: {sla_info}"
        )

    fig_rel = go.Figure()
    fig_rel.add_trace(go.Bar(
        x=service_names,
        y=rel_vals,
        marker=dict(
            color=rel_colors,
            line=dict(color=borders, width=border_widths),
        ),
        text=rel_texts,
        textposition="outside",
        hovertext=rel_hovers,
        hoverinfo="text",
        width=0.55,
    ))
    if sla_config and hasattr(sla_config, "min_reliability") and sla_config.min_reliability:
        fig_rel.add_hline(
            y=float(sla_config.min_reliability),
            line_dash="dash",
            line_color="#DC2626",
            line_width=1.8,
            annotation_text=f"Min SLA ({sla_config.min_reliability:.1f}%)",
            annotation_position="bottom right",
            annotation_font=dict(color="#DC2626", size=10),
        )
    if has_any_outage:
        rel_range = [0, 112]
    else:
        min_r = min(rel_vals) if rel_vals else 90.0
        floor_r = max(0.0, min_r - 3.0)
        if sla_config and hasattr(sla_config, "min_reliability"):
            floor_r = min(floor_r, float(sla_config.min_reliability) - 3.0)
        rel_range = [max(0.0, floor_r), 105]

    fig_rel.update_layout(
        title=dict(text="Reliability Percentage Comparison (Higher is Better)", font=dict(size=14, family="Inter, sans-serif")),
        xaxis=dict(title="Candidate Services", tickfont=dict(size=10)),
        yaxis=dict(title="Reliability (%)", range=rel_range, gridcolor="#F1F5F9"),
        template="plotly_white",
        margin=dict(l=35, r=35, t=45, b=35),
    )
    charts["reliability"] = fig_rel

    return charts


def build_health_donut_chart(
    services: List[CloudService],
    sla_config: Optional[Any] = None,
) -> go.Figure:
    """Build a donut chart showing the health distribution (Healthy, Degraded, Unavailable)."""
    counts = {
        "Healthy": 0,
        "Degraded": 0,
        "Unavailable": 0,
    }
    svc_names_by_group = {
        "Healthy": [],
        "Degraded": [],
        "Unavailable": [],
    }

    for s in services:
        h = classify_service_health(s, sla_config=sla_config)
        if h == HEALTH_UNAVAILABLE:
            counts["Unavailable"] += 1
            svc_names_by_group["Unavailable"].append(f"{s.service_id} ({s.name})")
        elif h == HEALTH_DEGRADED:
            counts["Degraded"] += 1
            svc_names_by_group["Degraded"].append(f"{s.service_id} ({s.name})")
        else:
            counts["Healthy"] += 1
            svc_names_by_group["Healthy"].append(f"{s.service_id} ({s.name})")

    labels = ["Healthy", "Degraded", "Unavailable"]
    values = [counts[l] for l in labels]
    colors = [STATUS_COLORS["Healthy"], STATUS_COLORS["Degraded"], STATUS_COLORS["Unavailable"]]

    hover_texts = []
    total = sum(values)
    for l in labels:
        cnt = counts[l]
        pct = (cnt / total * 100) if total > 0 else 0
        names = "<br>• " + "<br>• ".join(svc_names_by_group[l]) if svc_names_by_group[l] else " None"
        hover_texts.append(f"<b>{l}</b>: {cnt} services ({pct:.1f}%)<br>Services:{names}")

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="label+value",
        hovertext=hover_texts,
        hoverinfo="text",
    )])

    avail_count = sum(1 for s in services if s.operational_status == "AVAILABLE")
    fig.update_layout(
        title=dict(text="Service Health & Availability Distribution", font=dict(size=15, family="Inter, sans-serif")),
        annotations=[dict(text=f"<b>{avail_count}/{total}</b><br>Available", x=0.5, y=0.5, font_size=15, showarrow=False)],
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
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
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Latency Impact (Response Time ms)", "Percentage QoS Metrics (Avail, Rel, QoS Score x100)"),
        horizontal_spacing=0.15,
    )

    is_outage = (after.get("operational_status") == "UNAVAILABLE" or "Outage" in action)
    is_restored = ("Restore" in action or action == "Restore Baseline")

    # Subplot 1: Latency
    before_lat = float(before.get("latency", 0))
    after_lat = float(after.get("latency", 0))
    after_lat_text = "🔴 TIMEOUT / OFFLINE" if is_outage else f"{after_lat:.1f}ms"
    after_lat_color = STATUS_COLORS["Unavailable"] if is_outage else (STATUS_COLORS["Healthy"] if is_restored else STATUS_COLORS["Degraded"])

    fig.add_trace(
        go.Bar(
            name="Before Action",
            x=["Latency (ms)"],
            y=[before_lat],
            marker_color="#94A3B8",
            text=[f"{before_lat:.1f}ms"],
            textposition="outside",
            showlegend=True,
            width=0.45,
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Bar(
            name="After Action",
            x=["Latency (ms)"],
            y=[before_lat if is_outage else after_lat],
            marker_color=after_lat_color,
            text=[after_lat_text],
            textposition="outside",
            showlegend=True,
            width=0.45,
        ),
        row=1, col=1,
    )

    # Subplot 2: Availability, Reliability, QoS Score (scaled 0-100)
    metrics_pct = ["Availability (%)", "Reliability (%)", "QoS Score (x100)"]
    before_vals = [
        float(before.get("availability", 0)),
        float(before.get("reliability", 0)),
        float(before.get("qos_score", 0)) * 100,
    ]

    if is_outage:
        after_vals = [0.0, 0.0, 0.0]
        after_texts = ["🔴 0.0% [OUTAGE]", "🔴 0.0% [OUTAGE]", "🔴 0.0 [DISQUALIFIED]"]
        after_pct_color = STATUS_COLORS["Unavailable"]
    else:
        after_vals = [
            float(after.get("availability", 0)),
            float(after.get("reliability", 0)),
            float(after.get("qos_score", 0)) * 100,
        ]
        after_texts = [f"{v:.1f}" for v in after_vals]
        after_pct_color = STATUS_COLORS["Healthy"] if is_restored else STATUS_COLORS["Degraded"]

    fig.add_trace(
        go.Bar(
            name="Before Action",
            x=metrics_pct,
            y=before_vals,
            marker_color="#94A3B8",
            text=[f"{v:.1f}" for v in before_vals],
            textposition="outside",
            showlegend=False,
            width=0.45,
        ),
        row=1, col=2,
    )
    fig.add_trace(
        go.Bar(
            name="After Action",
            x=metrics_pct,
            y=after_vals,
            marker_color=after_pct_color,
            text=after_texts,
            textposition="outside",
            showlegend=False,
            width=0.45,
        ),
        row=1, col=2,
    )

    status_badge = "🔴 TOTAL OUTAGE" if is_outage else ("🟢 RESTORED TO BASELINE" if is_restored else "⚠️ PERFORMANCE DEGRADED")
    fig.update_layout(
        title=f"Failure Impact / Recovery Analysis: {target_service_id} ({target_service_name}) — [{action}] — {status_badge}",
        barmode="group",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        margin=dict(l=30, r=30, t=65, b=30),
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
