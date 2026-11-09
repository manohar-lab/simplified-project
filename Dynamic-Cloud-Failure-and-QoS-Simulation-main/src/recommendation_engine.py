"""Choose the best available service using its weighted QoS score and strict SLA constraints.

This module implements the final decision-making step of the project. Given a set
of candidate services (possibly degraded by the failure simulator), it:
    1. Filters services by the requested category (e.g. "Compute").
    2. Separates UNAVAILABLE services (outages) from eligible candidates.
    3. Evaluates available candidates against configured SLA thresholds (latency,
       availability, reliability). Candidates violating any SLA are strictly excluded.
    4. Evaluates each eligible service's QoS score using the QoSEvaluator.
    5. Ranks eligible services by descending QoS score (ties broken by service_id).
    6. Selects the top-ranked eligible service as the recommendation.
    7. Generates a human-readable explanation of why it was chosen,
       including reselection triggers and exact exclusion reasons.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.qos_evaluator import MetricScores, QoSEvaluator
from src.service_registry import CloudService
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla


@dataclass
class RecommendationResult:
    """Encapsulates the full output of a recommendation decision.

    This dataclass carries everything the dashboard needs to display:
    the selected service, its scores, the full ranked list, excluded services,
    and an explanation of why this particular service was chosen.

    Fields:
        category: The service category that was evaluated (e.g. "Compute").
        selected_service: The top-ranked CloudService, or None if no eligible service exists.
        selected_scores: The MetricScores of the selected service, or None.
        ranked_eligible: List of (CloudService, MetricScores) tuples for all eligible
                         services, sorted by descending QoS score then ascending service_id.
        excluded_services: List of (CloudService, reason_string) for services that were
                           excluded because they are UNAVAILABLE or violate SLA constraints.
        selection_reason: A human-readable string explaining why the service was chosen,
                         including any reselection triggers.
        has_eligible_service: True if at least one compliant service exists in the category.
        status_message: A summary message for the dashboard.
        sla_config: The SLAConfig applied during eligibility evaluation.
    """
    category: str
    selected_service: Optional[CloudService]
    selected_scores: Optional[MetricScores]
    ranked_eligible: List[Tuple[CloudService, MetricScores]]
    excluded_services: List[Tuple[CloudService, str]]
    selection_reason: str
    has_eligible_service: bool
    status_message: str
    sla_config: Optional[SLAConfig] = None
    status_code: str = "RECOMMENDED"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the recommendation result to a summary dictionary.

        This is useful for serialization or programmatic inspection of the result.

        Returns:
            Dictionary with key fields including the selected service's ID, name,
            QoS score, selection reason, status code, and counts of eligible/excluded services.
        """
        service, scores = self.selected_service, self.selected_scores
        return {
            "category": self.category,
            "status_code": self.status_code,
            "selected_service_id": service.service_id if service else None,
            "selected_service_name": service.name if service else None,
            "qos_score": scores.qos_score if scores else None,
            "selection_reason": self.selection_reason,
            "has_eligible_service": self.has_eligible_service,
            "status_message": self.status_message,
            "num_eligible": len(self.ranked_eligible),
            "num_excluded": len(self.excluded_services),
            "sla_config": self.sla_config.to_dict() if self.sla_config else None,
        }


class RecommendationEngine:
    """Rank category-matched services and explain the selection.

    This engine ties together SLA constraint filtering, QoS evaluation, and ranking logic:
        1. Filters services by requested category.
        2. Strictly excludes unavailable services.
        3. Strictly validates each remaining candidate against active SLA thresholds.
        4. Ranks only eligible, SLA-compliant candidates using weighted QoS scoring.
        5. Selects the top-ranked eligible candidate (deterministic tie-breaking).
    """

    def __init__(self, evaluator: QoSEvaluator):
        """Initialize the engine with a configured QoS evaluator.

        Args:
            evaluator: A QoSEvaluator instance (already loaded with reference bounds)
                       used to compute normalized scores for each service.
        """
        self.evaluator = evaluator

    def recommend(
        self,
        services: List[CloudService],
        category: str,
        weights: Optional[Dict[str, float]] = None,
        previously_selected_id: Optional[str] = None,
        sla_config: Optional[SLAConfig] = None,
    ) -> RecommendationResult:
        """Select the best available SLA-compliant service and explain the decision.

        Stages performed:
            Stage 1 — Category filtering:
                Only services matching the requested category are evaluated.

            Stage 2 — Availability & SLA Eligibility filtering:
                - Services marked UNAVAILABLE are immediately excluded.
                - Services violating any SLA threshold (latency, availability, reliability)
                  are strictly marked ineligible, regardless of their QoS scores.
                - All violations are recorded in the exclusion reason.

            Stage 3 — QoS evaluation and ranking (Eligible candidates only):
                Each eligible candidate is scored by QoSEvaluator. Candidates are
                sorted by descending qos_score with ascending service_id tie-breaking.

            Stage 4 — Reselection explanation:
                If previously_selected_id was provided and differs from the winner,
                explains whether the prior choice failed (outage), breached an SLA,
                or was overtaken on composite score.

        Args:
            services: Full list of CloudService instances.
            category: The category to evaluate (e.g. "Compute", "Storage").
            weights: Optional custom weights for QoS scoring.
            previously_selected_id: Previous winner ID to detect and explain reselection.
            sla_config: Optional active SLA constraint thresholds. If None, default
                        thresholds for the category are used.

        Returns:
            A RecommendationResult with selected service, scores, rankings, exclusions,
            and data-driven explanations.
        """
        effective_sla = sla_config if sla_config is not None else get_default_sla_config(category)

        # --- Stage 1: Category filtering ---
        candidates = [s for s in services if s.category == category]
        if not candidates:
            return RecommendationResult(
                category=category,
                selected_service=None,
                selected_scores=None,
                ranked_eligible=[],
                excluded_services=[],
                selection_reason=f"No services found registered under category '{category}'.",
                has_eligible_service=False,
                status_message=f"Category '{category}' has no candidate services registered.",
                sla_config=effective_sla,
                status_code="NO_CANDIDATES",
            )

        # --- Stage 2: Separate unavailable and SLA-violating services ---
        excluded: List[Tuple[CloudService, str]] = []
        available_candidates: List[CloudService] = []

        # 2a. Operational status filtering (fail-safe outage exclusion)
        for s in candidates:
            if s.operational_status == "UNAVAILABLE":
                excluded.append((s, "Service is marked UNAVAILABLE (simulated outage/down)."))
            else:
                available_candidates.append(s)

        # 2b. Strict SLA constraint evaluation on available candidates
        eligible: List[CloudService] = []
        for s in available_candidates:
            violations = validate_service_sla(s, effective_sla)
            if violations:
                excluded.append((s, f"Excluded: {'; '.join(violations)}"))
            else:
                eligible.append(s)

        # --- Stage 3: No eligible service handling ---
        if not eligible:
            if not available_candidates:
                status_msg = f"No SLA-Compliant Service Available. All {len(candidates)} service(s) in category '{category}' are currently UNAVAILABLE."
                reason = "No eligible candidate service available. Every candidate is in an outage/unavailable state."
            else:
                status_msg = f"No SLA-Compliant Service Available. All {len(candidates)} candidate service(s) in category '{category}' are unavailable or violate SLA constraints."
                reason = f"No SLA-Compliant Service Available. All {len(available_candidates)} available candidate(s) violate configured SLA thresholds."

            return RecommendationResult(
                category=category,
                selected_service=None,
                selected_scores=None,
                ranked_eligible=[],
                excluded_services=excluded,
                selection_reason=reason,
                has_eligible_service=False,
                status_message=status_msg,
                sla_config=effective_sla,
                status_code="NO_SLA_COMPLIANT_SERVICE",
            )

        # --- Stage 4: Evaluate and rank ELIGIBLE services only ---
        ranked = [(s, self.evaluator.evaluate_service(s, weights)) for s in eligible]
        # Sort by descending QoS score; ties broken by ascending service_id
        ranked.sort(key=lambda pair: (-pair[1].qos_score, pair[0].service_id))
        best, score = ranked[0]

        # Build human-readable explanation
        reasons = [
            f"Selected as optimal SLA-compliant service with highest aggregate QoS score of {score.qos_score:.4f}.",
            f"Latency: {best.latency:.1f}ms (score: {score.latency_score:.2f}) | "
            f"Cost: ${best.cost:.3f} (score: {score.cost_score:.2f}) | "
            f"Availability: {best.availability:.2f}% (score: {score.availability_score:.2f}) | "
            f"Reliability: {best.reliability:.2f}% (score: {score.reliability_score:.2f}).",
        ]

        # --- Stage 5: Explain reselection if recommendation changed ---
        if previously_selected_id and previously_selected_id != best.service_id:
            previous = next((s for s in candidates if s.service_id == previously_selected_id), None)
            if previous:
                if previous.operational_status == "UNAVAILABLE":
                    reasons.append(
                        f"Reselection trigger: Prior choice '{previous.name}' ({previous.service_id}) is currently UNAVAILABLE."
                    )
                else:
                    prev_violations = validate_service_sla(previous, effective_sla)
                    if prev_violations:
                        reasons.append(
                            f"Reselection trigger: Prior choice '{previous.name}' ({previous.service_id}) violated SLA constraints: {'; '.join(prev_violations)}."
                        )
                    else:
                        old_score = self.evaluator.evaluate_service(previous, weights)
                        reasons.append(
                            f"Reselection trigger: Prior choice '{previous.name}' ({previous.service_id}) QoS score "
                            f"({old_score.qos_score:.4f}) dropped below '{best.name}' ({score.qos_score:.4f})."
                        )

        return RecommendationResult(
            category=category,
            selected_service=best,
            selected_scores=score,
            ranked_eligible=ranked,
            excluded_services=excluded,
            selection_reason=" ".join(reasons),
            has_eligible_service=True,
            status_message=f"Successfully recommended '{best.name}' ({best.service_id}) out of {len(eligible)} eligible services.",
            sla_config=effective_sla,
        )
