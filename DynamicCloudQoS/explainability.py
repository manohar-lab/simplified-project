"""
Explainability Module
=====================
Generates human-readable explanations and comparison tables
for the recommendation engine output.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
from service_registry import CloudService


def generate_explanation(
    selected: Optional[CloudService],
    score: float,
    normalized: Dict[str, float],
    runner_up: Optional[CloudService],
    runner_up_score: float,
    margin: float,
    excluded: List[CloudService],
) -> str:
    """Build a multi-paragraph explanation of the current recommendation."""
    if selected is None:
        return (
            "⚠️ **No eligible service is currently available.**\n\n"
            "All registered services in this category are either unavailable "
            "or have been excluded.  Restore at least one service to resume "
            "automatic recommendation."
        )

    lines = [
        f"### ✅ Selected: {selected.name}",
        "",
        f"**{selected.name}** (ID: `{selected.service_id}`) was selected because "
        f"it achieved the **highest aggregate QoS score** of **{score:.4f}** "
        f"among all eligible services.",
        "",
    ]

    # Normalized breakdown
    lines.append("| Metric | Normalized Score |")
    lines.append("| :--- | :--- |")
    for metric in ("latency", "cost", "availability", "reliability"):
        label = metric.capitalize()
        val = normalized.get(metric, 0.0)
        lines.append(f"| {label} | {val:.4f} |")
    lines.append("")

    # Runner-up
    if runner_up:
        lines.append(
            f"**Best alternative:** {runner_up.name} "
            f"(score: {runner_up_score:.4f}, margin: {margin:.4f})."
        )
        lines.append("")

    # Excluded
    if excluded:
        names = ", ".join(f"*{s.name}*" for s in excluded)
        lines.append(
            f"**Excluded:** {names} — these services are currently "
            f"unavailable and cannot be recommended."
        )

    return "\n".join(lines)


def build_comparison_table(
    ranked: List[Tuple[CloudService, float, Dict[str, float]]],
) -> pd.DataFrame:
    """Build a DataFrame comparing all ranked services."""
    rows = []
    for svc, score, norms in ranked:
        rows.append({
            "Rank": len(rows) + 1,
            "Service": svc.name,
            "ID": svc.service_id,
            "Latency (ms)": f"{svc.latency:.1f}",
            "Cost ($)": f"{svc.cost:.3f}",
            "Availability (%)": f"{svc.availability:.1f}",
            "Reliability (%)": f"{svc.reliability:.1f}",
            "Status": svc.status,
            "QoS Score": f"{score:.4f}",
        })
    return pd.DataFrame(rows)


def build_event_history_table(events: list) -> pd.DataFrame:
    """Convert simulation event history into a display DataFrame."""
    if not events:
        return pd.DataFrame(columns=[
            "Timestamp", "Event", "Service", "Previous State", "Updated State",
        ])
    rows = []
    for evt in events:
        prev_status = evt.previous_state.get("status", "")
        new_status = evt.updated_state.get("status", "")
        prev_summary = (
            f"Lat: {evt.previous_state.get('latency', '?'):.1f}ms, "
            f"Avail: {evt.previous_state.get('availability', '?'):.1f}%, "
            f"Status: {prev_status}"
        )
        new_summary = (
            f"Lat: {evt.updated_state.get('latency', '?'):.1f}ms, "
            f"Avail: {evt.updated_state.get('availability', '?'):.1f}%, "
            f"Status: {new_status}"
        )
        rows.append({
            "Timestamp": evt.timestamp,
            "Event": evt.event_type.replace("_", " ").title(),
            "Service": evt.service_name,
            "Previous State": prev_summary,
            "Updated State": new_summary,
        })
    return pd.DataFrame(rows)
