"""Intelligent recommendation explainability and decision audit trail engine.

This module provides transparent, data-driven explanations of cloud service
reselection decisions following simulated failures, outages, and restorations.

All comparisons, delta metrics, rankings, and explanations are derived strictly
from the actual CloudService values and QoSEvaluator output without altering
any recommendation logic, scoring formulas, or weights.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd

from src.service_registry import CloudService
from src.qos_evaluator import MetricScores, QoSEvaluator
from src.recommendation_engine import RecommendationResult
from src.sla_config import SLAConfig, validate_service_sla
from src.analytics import classify_service_health, HEALTH_HEALTHY, HEALTH_DEGRADED, HEALTH_UNAVAILABLE


@dataclass
class MetricDiff:
    """Represents a comparative difference between two services for a single metric."""
    metric_name: str
    unit: str
    val_selected: float
    val_compared: float
    delta: float
    improved: bool
    summary: str


@dataclass
class ReselectionRecord:
    """Record of a recommendation / reselection decision for the audit trail."""
    sequence_number: int
    timestamp: str
    trigger_event: str
    prev_service_id: Optional[str]
    prev_service_name: Optional[str]
    prev_qos_score: Optional[float]
    prev_health_status: Optional[str]
    new_service_id: str
    new_service_name: str
    new_qos_score: float
    new_health_status: str
    runner_up_id: Optional[str]
    runner_up_name: Optional[str]
    runner_up_qos_score: Optional[float]
    reselection_reason: str
    detailed_explanation: str
    q_diff: Optional[float]
    lat_diff: Optional[float]
    avail_diff: Optional[float]
    rel_diff: Optional[float]
    cost_diff: Optional[float]
    # Phase 2 hysteresis tracking fields
    decision_type: str = "INITIAL"
    qos_improvement: float = 0.0
    hysteresis_threshold: float = 0.0
    cooldown_active: bool = False
    # Phase 4 operating mode tracking field
    operating_mode: str = "AUTOMATIC"

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for table display or serialization."""
        return asdict(self)


def compare_service_metrics(
    svc_selected: CloudService,
    score_selected: MetricScores,
    svc_compared: CloudService,
    score_compared: MetricScores,
) -> Dict[str, MetricDiff]:
    """Compare two services across all QoS metrics and aggregate score.

    Identifies whether each metric improved or worsened from svc_compared to svc_selected.
    For lower-is-better (Latency, Cost): negative delta means improvement.
    For higher-is-better (Availability, Reliability, QoS Score): positive delta means improvement.
    """
    # 1. QoS Score (higher is better)
    d_qos = score_selected.qos_score - score_compared.qos_score
    qos_improved = d_qos >= 0
    diff_qos = MetricDiff(
        metric_name="QoS Score",
        unit="",
        val_selected=score_selected.qos_score,
        val_compared=score_compared.qos_score,
        delta=round(d_qos, 4),
        improved=qos_improved,
        summary=f"{'+' if d_qos >= 0 else ''}{d_qos:.4f} score ({'Superior' if qos_improved else 'Lower'})",
    )

    # 2. Latency (lower is better)
    d_lat = svc_selected.latency - svc_compared.latency
    lat_improved = d_lat <= 0
    diff_lat = MetricDiff(
        metric_name="Latency",
        unit="ms",
        val_selected=svc_selected.latency,
        val_compared=svc_compared.latency,
        delta=round(d_lat, 1),
        improved=lat_improved,
        summary=f"{'+' if d_lat > 0 else ''}{d_lat:.1f} ms ({'Faster' if lat_improved else 'Slower'})",
    )

    # 3. Cost (lower is better)
    d_cost = svc_selected.cost - svc_compared.cost
    cost_improved = d_cost <= 0
    diff_cost = MetricDiff(
        metric_name="Cost",
        unit="$",
        val_selected=svc_selected.cost,
        val_compared=svc_compared.cost,
        delta=round(d_cost, 4),
        improved=cost_improved,
        summary=f"{'+' if d_cost > 0 else ''}${d_cost:.3f} ({'Cheaper' if cost_improved else 'More Expensive'})",
    )

    # 4. Availability (higher is better)
    d_avail = svc_selected.availability - svc_compared.availability
    avail_improved = d_avail >= 0
    diff_avail = MetricDiff(
        metric_name="Availability",
        unit="%",
        val_selected=svc_selected.availability,
        val_compared=svc_compared.availability,
        delta=round(d_avail, 2),
        improved=avail_improved,
        summary=f"{'+' if d_avail >= 0 else ''}{d_avail:.2f}% ({'Higher Uptime' if avail_improved else 'Lower Uptime'})",
    )

    # 5. Reliability (higher is better)
    d_rel = svc_selected.reliability - svc_compared.reliability
    rel_improved = d_rel >= 0
    diff_rel = MetricDiff(
        metric_name="Reliability",
        unit="%",
        val_selected=svc_selected.reliability,
        val_compared=svc_compared.reliability,
        delta=round(d_rel, 2),
        improved=rel_improved,
        summary=f"{'+' if d_rel >= 0 else ''}{d_rel:.2f}% ({'Higher Success Rate' if rel_improved else 'Lower Success Rate'})",
    )

    return {
        "qos_score": diff_qos,
        "latency": diff_lat,
        "cost": diff_cost,
        "availability": diff_avail,
        "reliability": diff_rel,
    }


def generate_detailed_reselection_explanation(
    recommendation: RecommendationResult,
    evaluator: QoSEvaluator,
    weights: Optional[Dict[str, float]],
    prev_service_id: Optional[str],
    all_category_services: List[CloudService],
    last_action: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate comprehensive, transparent explanations for the current recommendation decision.

    Analyzes:
    1. Winner vs previous choice (why it was replaced, outage vs degradation vs hysteresis).
    2. Winner vs runner-up (why the runner-up was beaten or prevented from switching).
    3. Excluded candidate reasons (outage disqualifications, SLA violations).
    """
    if not recommendation.has_eligible_service or not recommendation.selected_service:
        return {
            "has_recommendation": False,
            "headline": "No Eligible Service Available (No SLA-Compliant Service Available)",
            "summary": "Every candidate service in this category is currently unavailable or violates configured SLA thresholds.",
            "reselection_trigger": "Universal Ineligibility (Outage / SLA Violation)",
            "details": ["All services failed operational availability or SLA compliance constraints."],
            "comparison_prev": None,
            "comparison_runner_up": None,
            "runner_up": None,
            "excluded_reasons": [(s.service_id, s.name, reason) for s, reason in recommendation.excluded_services],
            "decision_type": recommendation.decision_type or "NO_ELIGIBLE_SERVICE",
            "decision_reason": recommendation.decision_reason or "All candidates ineligible.",
            "qos_improvement": 0.0,
            "hysteresis_threshold": recommendation.hysteresis_config.min_qos_delta if recommendation.hysteresis_config else 0.0,
            "cooldown_active": False,
            "operating_mode": recommendation.operating_mode,
            "manual_override_active": False,
            "override_terminated": recommendation.override_terminated,
            "override_termination_reason": recommendation.override_termination_reason,
            "automatic_best_service": None,
        }

    winner = recommendation.selected_service
    winner_score = recommendation.selected_scores
    winner_health = classify_service_health(winner)

    # Identify runner-up / best alternative candidate
    if recommendation.best_alternative and recommendation.best_alternative_score:
        runner_up = recommendation.best_alternative
        runner_up_score = recommendation.best_alternative_score
    else:
        runner_up_pair = recommendation.ranked_eligible[1] if len(recommendation.ranked_eligible) > 1 else None
        runner_up = runner_up_pair[0] if runner_up_pair else None
        runner_up_score = runner_up_pair[1] if runner_up_pair else None

    # Identify previous service if known
    prev_svc = next((s for s in all_category_services if s.service_id == prev_service_id), None)
    prev_score = evaluator.evaluate_service(prev_svc, weights) if prev_svc else None
    prev_health = classify_service_health(prev_svc) if prev_svc else None

    # Reselection trigger detection
    is_reselection = (prev_service_id is not None and prev_service_id != winner.service_id)
    reselection_trigger = "Baseline Optimization"
    reselection_type = recommendation.decision_type or ("RESELECTION" if is_reselection else "INITIAL")

    details = []

    if recommendation.decision_type == "MANUAL_OVERRIDE":
        reselection_type = "MANUAL_OVERRIDE"
        reselection_trigger = "Manual Operator Service Override"
        details.append(
            f"🎯 **Manual Override Active:** Operator explicitly selected eligible service "
            f"`{winner.name}` ({winner.service_id}) in `{winner.category}` "
            f"(QoS score: `{winner_score.qos_score:.4f}`). Hard SLA checks and periodic monitoring remain enforced."
        )
        if recommendation.manual_override_reason:
            details.append(f"📝 **Override Reason:** {recommendation.manual_override_reason}")
        if (
            recommendation.automatic_best_service is not None
            and recommendation.automatic_best_service.service_id != winner.service_id
            and recommendation.automatic_best_score is not None
        ):
            auto_svc = recommendation.automatic_best_service
            auto_sc = recommendation.automatic_best_score
            details.append(
                f"🤖 **Automatic Rank #1 Reference:** Automatic engine would select `{auto_svc.name}` "
                f"({auto_svc.service_id}, QoS: `{auto_sc.qos_score:.4f}`); manual choice overrides "
                f"performance-based switching thresholds while SLA-compliant."
            )
    elif recommendation.decision_type == "RETAINED":
        reselection_type = "RETAINED"
        reselection_trigger = recommendation.decision_reason or "Anti-Flapping Protection Active (Hysteresis)"
        details.append(
            f"🛡️ **Anti-Flapping Protection Active:** Currently selected service `{winner.name}` ({winner.service_id}) "
            f"was retained. {recommendation.decision_reason}"
        )
    elif is_reselection and prev_svc:
        if prev_svc.operational_status == "UNAVAILABLE" or recommendation.decision_type == "EMERGENCY_OUTAGE":
            reselection_trigger = (
                "Emergency Override Termination (Outage)"
                if recommendation.override_terminated else "Previous Service Outage"
            )
            reselection_type = "OUTAGE"
            prefix = "🛑 **Manual Override Emergency Terminated** — " if recommendation.override_terminated else "🚨 **Disqualification of Prior Choice:** "
            details.append(
                f"{prefix}Prior selected service `{prev_svc.name}` ({prev_svc.service_id}) "
                f"entered an **UNAVAILABLE** state. Under fail-safe eligibility rules, emergency reselection immediately selected `{winner.name}` "
                f"(bypassing hysteresis and cooldown)."
            )
        elif (recommendation.sla_config and validate_service_sla(prev_svc, recommendation.sla_config)) or recommendation.decision_type == "EMERGENCY_SLA_VIOLATION":
            reselection_trigger = (
                "Emergency Override Termination (SLA Violation)"
                if recommendation.override_terminated else "Prior Service SLA Violation"
            )
            reselection_type = "SLA_VIOLATION"
            prev_violations = validate_service_sla(prev_svc, recommendation.sla_config) if recommendation.sla_config else []
            violations_text = "; ".join(prev_violations) if prev_violations else "SLA threshold violation"
            prefix = "🛑 **Manual Override Emergency Terminated** — " if recommendation.override_terminated else "🚨 **SLA Violation Disqualification:** "
            details.append(
                f"{prefix}Prior selected service `{prev_svc.name}` ({prev_svc.service_id}) "
                f"violated configured SLA constraints ({violations_text}). Emergency reselection immediately selected `{winner.name}` "
                f"(bypassing hysteresis and cooldown)."
            )
        elif recommendation.decision_type == "SWITCHED":
            reselection_trigger = "QoS Improvement Exceeded Hysteresis Threshold"
            reselection_type = "SWITCHED"
            details.append(
                f"🔄 **Hysteresis Threshold Exceeded:** Switched from `{prev_svc.name}` ({prev_svc.service_id}) "
                f"to `{winner.name}` ({winner.service_id}). {recommendation.decision_reason}"
            )
        elif prev_health == HEALTH_DEGRADED:
            reselection_trigger = "Prior Service QoS Degradation"
            reselection_type = "DEGRADATION"
            details.append(
                f"⚠️ **Prior Choice Degradation:** Prior recommended service `{prev_svc.name}` ({prev_svc.service_id}) "
                f"experienced performance degradation (QoS score dropped to `{prev_score.qos_score:.4f}`). "
                f"`{winner.name}` surpassed it with an aggregate score of `{winner_score.qos_score:.4f}`."
            )
        else:
            reselection_trigger = "QoS Weight Rebalancing or System Recovery"
            reselection_type = "RECOVERY"
            details.append(
                f"🔄 **Reselection Trigger:** `{winner.name}` ({winner.service_id}) now leads the category with a higher "
                f"composite score of `{winner_score.qos_score:.4f}` compared to `{prev_svc.name}` ({prev_score.qos_score:.4f})."
            )
    else:
        details.append(
            f"🏆 **Optimal Candidate:** `{winner.name}` ({winner.service_id}) is currently ranked #1 with the highest "
            f"aggregate QoS score of `{winner_score.qos_score:.4f}` / 1.0000 across all eligible candidates."
        )

    # Comparison against runner-up
    comparison_runner_up = None
    if runner_up and runner_up_score:
        comparison_runner_up = compare_service_metrics(winner, winner_score, runner_up, runner_up_score)
        d_score = winner_score.qos_score - runner_up_score.qos_score

        # Identify key winning factors
        strengths = []
        if winner.latency < runner_up.latency:
            strengths.append(f"{runner_up.latency - winner.latency:.1f}ms lower latency")
        if winner.availability > runner_up.availability:
            strengths.append(f"{winner.availability - runner_up.availability:.2f}% higher availability")
        if winner.reliability > runner_up.reliability:
            strengths.append(f"{winner.reliability - runner_up.reliability:.2f}% higher reliability")
        if winner.cost < runner_up.cost:
            strengths.append(f"${runner_up.cost - winner.cost:.3f} lower cost")

        factor_str = ", ".join(strengths) if strengths else "balanced normalized weighted score"
        if recommendation.decision_type == "RETAINED" and d_score < 0:
            details.append(
                f"⚖️ **Anti-Flapping Margin:** Best alternative candidate `{runner_up.name}` ({runner_up.service_id}) "
                f"leads by `{abs(d_score):.4f}` score, but switch was prevented by hysteresis threshold "
                f"(`ΔQoS required >= {recommendation.hysteresis_config.min_qos_delta if recommendation.hysteresis_config else 0.05:.4f}`)."
            )
        else:
            details.append(
                f"⚔️ **Margin over Best Alternative:** Aggregate QoS score difference is `+{d_score:.4f}` vs "
                f"`{runner_up.name}` ({runner_up.service_id}). Key differentiators: {factor_str}."
            )

    # Comparison against previous service
    comparison_prev = None
    if prev_svc and prev_score:
        comparison_prev = compare_service_metrics(winner, winner_score, prev_svc, prev_score)

    # Excluded services
    excluded_reasons = []
    for s, reason in recommendation.excluded_services:
        excluded_reasons.append({
            "service_id": s.service_id,
            "name": s.name,
            "health_status": classify_service_health(s),
            "reason": reason,
        })

    if recommendation.decision_type == "MANUAL_OVERRIDE":
        headline = f"Manual Override Active: {winner.name} ({winner.service_id})"
    elif recommendation.override_terminated:
        headline = f"Emergency Override Termination: {reselection_trigger}"
    elif recommendation.decision_type == "RETAINED":
        headline = f"Service Retained: {winner.name} (Anti-Flapping Active)"
    elif is_reselection:
        headline = f"Reselection Triggered: {reselection_trigger}"
    else:
        headline = f"Optimal Service: {winner.name} ({winner.service_id})"

    summary_text = (
        f"Manually selected '{winner.name}' ({winner.service_id}) with aggregate QoS score of {winner_score.qos_score:.4f}."
        if recommendation.decision_type == "MANUAL_OVERRIDE"
        else f"Recommended '{winner.name}' ({winner.service_id}) with aggregate QoS score of {winner_score.qos_score:.4f}."
    )

    return {
        "has_recommendation": True,
        "headline": headline,
        "summary": summary_text,
        "reselection_trigger": reselection_trigger,
        "reselection_type": reselection_type,
        "is_reselection": is_reselection,
        "decision_type": recommendation.decision_type,
        "decision_reason": recommendation.decision_reason,
        "qos_improvement": recommendation.qos_improvement,
        "hysteresis_threshold": recommendation.hysteresis_config.min_qos_delta if recommendation.hysteresis_config else 0.0,
        "cooldown_active": recommendation.cooldown_active,
        "operating_mode": recommendation.operating_mode,
        "manual_override_active": recommendation.manual_override_active,
        "override_terminated": recommendation.override_terminated,
        "override_termination_reason": recommendation.override_termination_reason,
        "automatic_best_service": recommendation.automatic_best_service,
        "winner": winner,
        "winner_score": winner_score,
        "winner_health": winner_health,
        "prev_service": prev_svc,
        "prev_score": prev_score,
        "prev_health": prev_health,
        "runner_up": runner_up,
        "runner_up_score": runner_up_score,
        "comparison_prev": comparison_prev,
        "comparison_runner_up": comparison_runner_up,
        "details": details,
        "excluded_services": excluded_reasons,
    }


def build_three_way_comparison_dataframe(
    explanation_data: Dict[str, Any]
) -> pd.DataFrame:
    """Build a 3-way comparative DataFrame comparing Prior Service, Selected Winner, and Best Alternative (Runner-Up)."""
    if not explanation_data.get("has_recommendation"):
        return pd.DataFrame()

    winner = explanation_data["winner"]
    winner_score = explanation_data["winner_score"]
    winner_health = explanation_data["winner_health"]

    prev = explanation_data.get("prev_service")
    prev_score = explanation_data.get("prev_score")
    prev_health = explanation_data.get("prev_health", "N/A")

    runner_up = explanation_data.get("runner_up")
    runner_up_score = explanation_data.get("runner_up_score")
    runner_up_health = classify_service_health(runner_up) if runner_up else "N/A"

    comp_prev = explanation_data.get("comparison_prev")
    comp_runner = explanation_data.get("comparison_runner_up")

    decision_type = explanation_data.get("decision_type", "")
    if decision_type == "RETAINED":
        winner_vs_prior = "Retained via Anti-Flapping Hysteresis"
        winner_vs_runner = f"Challenger ΔQoS: {explanation_data.get('qos_improvement', 0.0):+.4f} (Below Threshold)"
    else:
        winner_vs_prior = (
            ("Retained" if prev and prev.service_id == winner.service_id else ("Prior is UNAVAILABLE" if prev and prev.operational_status == "UNAVAILABLE" else "Operational Change"))
            if prev else "Baseline"
        )
        winner_vs_runner = "Both Eligible" if runner_up else "N/A"

    rows = [
        {
            "QoS Metric": "Health & Status",
            "Prior Service": f"{prev_health} ({prev.operational_status})" if prev else "N/A",
            "Newly Selected Winner": f"{winner_health} ({winner.operational_status})",
            "Best Alternative (Runner-Up)": f"{runner_up_health} ({runner_up.operational_status})" if runner_up else "N/A",
            "Winner vs Prior Choice": winner_vs_prior,
            "Winner vs Runner-Up": winner_vs_runner,
        },
        {
            "QoS Metric": "Aggregate QoS Score",
            "Prior Service": f"{prev_score.qos_score:.4f}" if prev_score else "N/A",
            "Newly Selected Winner": f"{winner_score.qos_score:.4f}",
            "Best Alternative (Runner-Up)": f"{runner_up_score.qos_score:.4f}" if runner_up_score else "N/A",
            "Winner vs Prior Choice": comp_prev["qos_score"].summary if comp_prev else "Baseline Winner",
            "Winner vs Runner-Up": comp_runner["qos_score"].summary if comp_runner else "N/A",
        },
        {
            "QoS Metric": "Latency (ms)",
            "Prior Service": f"{prev.latency:.1f} ms" if prev else "N/A",
            "Newly Selected Winner": f"{winner.latency:.1f} ms",
            "Best Alternative (Runner-Up)": f"{runner_up.latency:.1f} ms" if runner_up else "N/A",
            "Winner vs Prior Choice": comp_prev["latency"].summary if comp_prev else "Baseline",
            "Winner vs Runner-Up": comp_runner["latency"].summary if comp_runner else "N/A",
        },
        {
            "QoS Metric": "Availability (%)",
            "Prior Service": f"{prev.availability:.2f}%" if prev else "N/A",
            "Newly Selected Winner": f"{winner.availability:.2f}%",
            "Best Alternative (Runner-Up)": f"{runner_up.availability:.2f}%" if runner_up else "N/A",
            "Winner vs Prior Choice": comp_prev["availability"].summary if comp_prev else "Baseline",
            "Winner vs Runner-Up": comp_runner["availability"].summary if comp_runner else "N/A",
        },
        {
            "QoS Metric": "Reliability (%)",
            "Prior Service": f"{prev.reliability:.2f}%" if prev else "N/A",
            "Newly Selected Winner": f"{winner.reliability:.2f}%",
            "Best Alternative (Runner-Up)": f"{runner_up.reliability:.2f}%" if runner_up else "N/A",
            "Winner vs Prior Choice": comp_prev["reliability"].summary if comp_prev else "Baseline",
            "Winner vs Runner-Up": comp_runner["reliability"].summary if comp_runner else "N/A",
        },
        {
            "QoS Metric": "Cost ($ per call)",
            "Prior Service": f"${prev.cost:.3f}" if prev else "N/A",
            "Newly Selected Winner": f"${winner.cost:.3f}",
            "Best Alternative (Runner-Up)": f"${runner_up.cost:.3f}" if runner_up else "N/A",
            "Winner vs Prior Choice": comp_prev["cost"].summary if comp_prev else "Baseline",
            "Winner vs Runner-Up": comp_runner["cost"].summary if comp_runner else "N/A",
        },
    ]

    return pd.DataFrame(rows)


def build_candidate_comparison_table(
    recommendation: RecommendationResult,
    evaluator: QoSEvaluator,
    weights: Optional[Dict[str, float]],
    all_category_services: List[CloudService],
) -> pd.DataFrame:
    """Build a comprehensive comparison DataFrame for all category candidate services.

    Includes Rank, Eligibility, Health Status, Aggregate QoS Score, and raw metrics.
    Preserves exact engine ranking.
    """
    rows = []
    rec_id = recommendation.selected_service.service_id if recommendation.selected_service else None

    # First add ranked eligible candidates in engine order
    for rank_idx, (s, scores) in enumerate(recommendation.ranked_eligible, start=1):
        is_selected = (s.service_id == rec_id)
        is_best_alt = (recommendation.best_alternative and s.service_id == recommendation.best_alternative.service_id) or (not recommendation.best_alternative and rank_idx == 2)
        if is_selected:
            if recommendation.decision_type == "MANUAL_OVERRIDE":
                role = "🎯 Selected Service (Manual Override)"
            elif recommendation.decision_type in ("EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION"):
                role = "🚨 Selected Service (Emergency Replacement)"
            else:
                role = "⭐ Selected Service (Automatic)"
        elif is_best_alt:
            role = "🤖 Automatic #1 (Overridden)" if recommendation.decision_type == "MANUAL_OVERRIDE" else "🥈 Best Alternative"
        else:
            role = "Eligible Alternative"
        health = classify_service_health(s)

        if is_selected:
            if recommendation.decision_type == "MANUAL_OVERRIDE":
                notes = f"Selected via Manual Override ({recommendation.manual_override_reason or 'Operator Choice'})"
            elif recommendation.decision_type == "RETAINED":
                notes = "Selected (Retained via Hysteresis)"
            elif recommendation.decision_type in ("SWITCHED", "EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION"):
                notes = f"Selected ({recommendation.decision_type})"
                if recommendation.override_terminated:
                    notes += " [Manual Override Terminated]"
            else:
                notes = "Highest eligible score"
        elif is_best_alt:
            if recommendation.decision_type == "RETAINED":
                notes = f"Leading candidate (ΔQoS +{recommendation.qos_improvement:.4f} below threshold)"
            else:
                notes = "Best alternative candidate"
        else:
            notes = f"Rank #{rank_idx} candidate"

        rows.append({
            "Rank": f"#{rank_idx}",
            "Service ID": s.service_id,
            "Service Name": s.name,
            "Eligibility": "✅ Eligible",
            "Role": role,
            "Health Status": health,
            "Aggregate QoS Score": scores.qos_score,
            "Latency (ms)": f"{s.latency:.1f}",
            "Cost ($)": f"${s.cost:.3f}",
            "Availability (%)": f"{s.availability:.2f}%",
            "Reliability (%)": f"{s.reliability:.2f}%",
            "Decision Notes": notes,
        })

    # Next append excluded services
    for s, reason in recommendation.excluded_services:
        scores = evaluator.evaluate_service(s, weights)
        is_outage = (s.operational_status == "UNAVAILABLE")
        role = "Excluded / Down" if is_outage else "Excluded / SLA Violation"
        health = classify_service_health(s)
        rows.append({
            "Rank": "Excluded",
            "Service ID": s.service_id,
            "Service Name": s.name,
            "Eligibility": "❌ Ineligible",
            "Role": role,
            "Health Status": health,
            "Aggregate QoS Score": scores.qos_score,
            "Latency (ms)": f"{s.latency:.1f}",
            "Cost ($)": f"${s.cost:.3f}",
            "Availability (%)": f"{s.availability:.2f}%",
            "Reliability (%)": f"{s.reliability:.2f}%",
            "Decision Notes": f"Disqualified: {reason}",
        })

    return pd.DataFrame(rows)


class ReselectionAuditTrail:
    """Manages an audit trail of recommendation and reselection decisions."""

    def __init__(self):
        self.records: List[ReselectionRecord] = []

    def record_decision(
        self,
        trigger_event: str,
        recommendation: RecommendationResult,
        evaluator: QoSEvaluator,
        weights: Optional[Dict[str, float]],
        prev_service_id: Optional[str],
        all_category_services: List[CloudService],
        timestamp: Optional[str] = None,
    ) -> Optional[ReselectionRecord]:
        """Record a reselection event into the audit trail."""
        if not recommendation.selected_service or not recommendation.selected_scores:
            return None

        winner = recommendation.selected_service
        winner_score = recommendation.selected_scores
        winner_health = classify_service_health(winner)

        prev_svc = next((s for s in all_category_services if s.service_id == prev_service_id), None)
        prev_score = evaluator.evaluate_service(prev_svc, weights) if prev_svc else None
        prev_health = classify_service_health(prev_svc) if prev_svc else None

        runner_up_pair = recommendation.ranked_eligible[1] if len(recommendation.ranked_eligible) > 1 else None
        runner_up = runner_up_pair[0] if runner_up_pair else None
        runner_up_score = runner_up_pair[1] if runner_up_pair else None

        # Calculate metric deltas if previous service exists
        q_diff = round(winner_score.qos_score - prev_score.qos_score, 4) if prev_score else None
        lat_diff = round(winner.latency - prev_svc.latency, 1) if prev_svc else None
        cost_diff = round(winner.cost - prev_svc.cost, 4) if prev_svc else None
        avail_diff = round(winner.availability - prev_svc.availability, 2) if prev_svc else None
        rel_diff = round(winner.reliability - prev_svc.reliability, 2) if prev_svc else None

        explanation_data = generate_detailed_reselection_explanation(
            recommendation=recommendation,
            evaluator=evaluator,
            weights=weights,
            prev_service_id=prev_service_id,
            all_category_services=all_category_services,
        )

        hysteresis_thresh = (
            recommendation.hysteresis_config.min_qos_delta
            if recommendation.hysteresis_config
            else 0.0
        )

        rec = ReselectionRecord(
            sequence_number=len(self.records) + 1,
            timestamp=timestamp or datetime.now().strftime("%H:%M:%S"),
            trigger_event=trigger_event,
            prev_service_id=prev_svc.service_id if prev_svc else "None (Initial)",
            prev_service_name=prev_svc.name if prev_svc else "None",
            prev_qos_score=prev_score.qos_score if prev_score else None,
            prev_health_status=prev_health or "N/A",
            new_service_id=winner.service_id,
            new_service_name=winner.name,
            new_qos_score=winner_score.qos_score,
            new_health_status=winner_health,
            runner_up_id=runner_up.service_id if runner_up else None,
            runner_up_name=runner_up.name if runner_up else None,
            runner_up_qos_score=runner_up_score.qos_score if runner_up_score else None,
            reselection_reason=explanation_data.get("reselection_trigger", "Optimal Score"),
            detailed_explanation=" ".join(explanation_data.get("details", [])),
            q_diff=q_diff,
            lat_diff=lat_diff,
            avail_diff=avail_diff,
            rel_diff=rel_diff,
            cost_diff=cost_diff,
            decision_type=recommendation.decision_type or "INITIAL",
            qos_improvement=recommendation.qos_improvement,
            hysteresis_threshold=hysteresis_thresh,
            cooldown_active=recommendation.cooldown_active,
            operating_mode=recommendation.operating_mode,
        )
        self.records.append(rec)
        return rec

    def reset(self) -> None:
        """Clear all audit records."""
        self.records.clear()

    def to_dataframe(self) -> pd.DataFrame:
        """Convert all records to a clean DataFrame for UI display."""
        if not self.records:
            return pd.DataFrame()
        rows = [r.to_dict() for r in self.records]
        df = pd.DataFrame(rows)
        # Rename columns to user-friendly names
        df.rename(
            columns={
                "sequence_number": "Seq #",
                "timestamp": "Timestamp",
                "trigger_event": "Trigger Event",
                "operating_mode": "Operating Mode",
                "decision_type": "Decision Type",
                "prev_service_id": "Previous Service",
                "new_service_id": "Selected Service",
                "new_qos_score": "QoS Score",
                "new_health_status": "Health Status",
                "runner_up_id": "Runner-Up",
                "qos_improvement": "Δ QoS",
                "hysteresis_threshold": "Threshold",
                "cooldown_active": "Cooldown Active",
                "reselection_reason": "Decision Trigger",
                "detailed_explanation": "Decision Explanation",
            },
            inplace=True,
        )
        return df
