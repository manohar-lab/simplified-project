"""Choose the best available service using its weighted QoS score.

This module implements the final decision-making step of the project. Given a set
of candidate services (possibly degraded by the failure simulator), it:
    1. Filters services by the requested category (e.g. "Compute").
    2. Separates UNAVAILABLE services (excluded) from eligible ones.
    3. Evaluates each eligible service's QoS score using the QoSEvaluator.
    4. Ranks eligible services by descending QoS score (ties broken by service_id).
    5. Selects the top-ranked service as the recommendation.
    6. Generates a human-readable explanation of why it was chosen,
       including reselection triggers when the previously recommended service
       has been degraded or taken offline.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.qos_evaluator import MetricScores, QoSEvaluator
from src.service_registry import CloudService


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
                           excluded because they are UNAVAILABLE.
        selection_reason: A human-readable string explaining why the service was chosen,
                         including any reselection triggers.
        has_eligible_service: True if at least one AVAILABLE service exists in the category.
        status_message: A summary message for the dashboard (e.g. "Successfully recommended...").
    """
    category: str
    selected_service: Optional[CloudService]
    selected_scores: Optional[MetricScores]
    ranked_eligible: List[Tuple[CloudService, MetricScores]]
    excluded_services: List[Tuple[CloudService, str]]
    selection_reason: str
    has_eligible_service: bool
    status_message: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert the recommendation result to a summary dictionary.

        This is useful for serialization or programmatic inspection of the result.

        Returns:
            Dictionary with key fields including the selected service's ID, name,
            QoS score, selection reason, and counts of eligible/excluded services.
        """
        service, scores = self.selected_service, self.selected_scores
        return {
            "category": self.category,
            "selected_service_id": service.service_id if service else None,
            "selected_service_name": service.name if service else None,
            "qos_score": scores.qos_score if scores else None,
            "selection_reason": self.selection_reason,
            "has_eligible_service": self.has_eligible_service,
            "status_message": self.status_message,
            "num_eligible": len(self.ranked_eligible),
            "num_excluded": len(self.excluded_services),
        }


class RecommendationEngine:
    """Rank category-matched services and explain the selection.

    This engine ties together the QoS evaluator and the filtering/ranking logic.
    It does NOT use machine learning, deep reinforcement learning, or any
    optimization algorithm — it performs a straightforward weighted score
    comparison and selects the service with the highest aggregate QoS score.
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
    ) -> RecommendationResult:
        """Select the best available service in the given category and explain the decision.

        This is the main entry point for the recommendation logic. The method
        proceeds through several stages:

        Stage 1 — Category filtering:
            Only services matching the requested category are considered.

        Stage 2 — Availability filtering:
            Services with operational_status == "UNAVAILABLE" are moved to the
            excluded list. They cannot be recommended regardless of their QoS score.

        Stage 3 — QoS evaluation and ranking:
            Each eligible service is scored by the QoSEvaluator. Services are
            sorted by descending qos_score. If two services have identical scores,
            the one with the lexicographically smaller service_id is chosen first
            (deterministic tie-breaking).

        Stage 4 — Reselection explanation:
            If a previously_selected_id was provided and the new winner differs,
            the reason string explains whether the prior choice went down (outage)
            or was overtaken on QoS score (e.g. after a latency spike).

        Args:
            services: Full list of CloudService instances (all categories).
            category: The category to evaluate, e.g. "Compute" or "Storage".
            weights: Optional custom weights for QoS scoring.
            previously_selected_id: The service_id that was recommended in the
                                    previous run. Used to detect and explain
                                    reselection events.

        Returns:
            A RecommendationResult containing the selected service, scores,
            full ranking, excluded services, and explanation text.
        """
        # --- Stage 1: Filter to only services in the requested category ---
        candidates = [s for s in services if s.category == category]
        if not candidates:
            # No services registered for this category at all
            return RecommendationResult(
                category, None, None, [], [],
                f"No services found registered under category '{category}'.", False,
                f"Category '{category}' has no candidate services registered.",
            )

        # --- Stage 2: Separate unavailable (excluded) from eligible services ---
        # Unavailable services are excluded with a reason string for the UI
        excluded = [(s, "Service is marked UNAVAILABLE (simulated outage/down).")
                    for s in candidates if s.operational_status == "UNAVAILABLE"]
        eligible = [s for s in candidates if s.operational_status != "UNAVAILABLE"]
        if not eligible:
            # Every service in the category is down — no recommendation possible
            return RecommendationResult(
                category, None, None, [], excluded,
                "No eligible candidate service available. Every candidate is in an outage/unavailable state.",
                False,
                f"All {len(candidates)} service(s) in category '{category}' are currently UNAVAILABLE.",
            )

        # --- Stage 3: Evaluate and rank eligible services by QoS score ---
        # Each eligible service gets its normalized weighted QoS score
        ranked = [(s, self.evaluator.evaluate_service(s, weights)) for s in eligible]
        # Sort by descending QoS score; ties are broken by ascending service_id
        # for deterministic, reproducible results
        ranked.sort(key=lambda pair: (-pair[1].qos_score, pair[0].service_id))
        # The first entry after sorting is the best (highest score, lowest ID on tie)
        best, score = ranked[0]

        # Build the explanation string for why this service was chosen
        reasons = [
            f"Selected as optimal service with highest aggregate QoS score of {score.qos_score:.4f}.",
            f"Latency: {best.latency:.1f}ms (score: {score.latency_score:.2f}) | "
            f"Cost: ${best.cost:.3f} (score: {score.cost_score:.2f}) | "
            f"Availability: {best.availability:.2f}% (score: {score.availability_score:.2f}) | "
            f"Reliability: {best.reliability:.2f}% (score: {score.reliability_score:.2f}).",
        ]

        # --- Stage 4: Explain reselection if the recommendation changed ---
        if previously_selected_id and previously_selected_id != best.service_id:
            # The recommendation changed — find the previous service to explain why
            previous = next((s for s in candidates if s.service_id == previously_selected_id), None)
            if previous:
                if previous.operational_status == "UNAVAILABLE":
                    # The previous choice went down entirely
                    reasons.append(
                        f"Reselection trigger: Prior choice '{previous.name}' ({previous.service_id}) is currently UNAVAILABLE."
                    )
                else:
                    # The previous choice is still available but another service now scores higher
                    old_score = self.evaluator.evaluate_service(previous, weights)
                    reasons.append(
                        f"Reselection trigger: Prior choice '{previous.name}' ({previous.service_id}) QoS score "
                        f"({old_score.qos_score:.4f}) dropped below '{best.name}' ({score.qos_score:.4f})."
                    )

        return RecommendationResult(
            category, best, score, ranked, excluded, " ".join(reasons), True,
            f"Successfully recommended '{best.name}' ({best.service_id}) out of {len(eligible)} eligible services.",
        )
