"""
Recommendation Engine Module
=============================
Evaluates all services, excludes unavailable ones, ranks by QoS score,
selects the best eligible service, and provides a selection explanation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from service_registry import CloudService
from qos_evaluator import evaluate_all, DEFAULT_WEIGHTS


@dataclass
class RecommendationResult:
    """Encapsulates a recommendation decision."""
    selected_service: Optional[CloudService] = None
    selected_score: float = 0.0
    selected_normalized: Dict[str, float] = field(default_factory=dict)
    runner_up: Optional[CloudService] = None
    runner_up_score: float = 0.0
    score_margin: float = 0.0
    ranking: List[tuple] = field(default_factory=list)
    excluded_services: List[CloudService] = field(default_factory=list)
    reason: str = ""
    all_unavailable: bool = False


def recommend(
    services: List[CloudService],
    category: str = "Compute",
    weights: Optional[Dict[str, float]] = None,
) -> RecommendationResult:
    """Run the full recommendation pipeline.

    1. Filter by category.
    2. Separate available vs unavailable.
    3. Evaluate & rank available services.
    4. Select the highest-scoring service.
    5. Identify runner-up and score margin.
    6. Generate explanation.
    """
    result = RecommendationResult()
    w = weights or DEFAULT_WEIGHTS

    # --- Category filter ---
    category_services = [s for s in services if s.category == category]
    if not category_services:
        result.reason = f"No services registered in the '{category}' category."
        result.all_unavailable = True
        return result

    # --- Availability filter ---
    available = [s for s in category_services if s.status == "AVAILABLE"]
    result.excluded_services = [s for s in category_services if s.status != "AVAILABLE"]

    if not available:
        result.reason = (
            "All services in this category are currently unavailable. "
            "No eligible service can be recommended."
        )
        result.all_unavailable = True
        return result

    # --- Evaluate & rank ---
    ranked = evaluate_all(available, w)
    result.ranking = ranked

    # --- Select best ---
    best_svc, best_score, best_norms = ranked[0]
    result.selected_service = best_svc
    result.selected_score = best_score
    result.selected_normalized = best_norms

    # --- Runner-up ---
    if len(ranked) > 1:
        ru_svc, ru_score, _ = ranked[1]
        result.runner_up = ru_svc
        result.runner_up_score = ru_score
        result.score_margin = round(best_score - ru_score, 4)

    # --- Explanation ---
    result.reason = _build_reason(result)
    return result


def _build_reason(result: RecommendationResult) -> str:
    """Generate a human-readable explanation of the recommendation."""
    svc = result.selected_service
    if svc is None:
        return "No eligible service available."

    parts = [
        f"{svc.name} (ID: {svc.service_id}) was selected because it achieved "
        f"the highest aggregate QoS score of {result.selected_score:.4f} "
        f"among all eligible services."
    ]

    if result.runner_up:
        parts.append(
            f"The next best alternative is {result.runner_up.name} "
            f"with a score of {result.runner_up_score:.4f} "
            f"(margin: {result.score_margin:.4f})."
        )

    if result.excluded_services:
        names = ", ".join(s.name for s in result.excluded_services)
        parts.append(
            f"Excluded from consideration: {names} "
            f"(status: UNAVAILABLE)."
        )

    return " ".join(parts)
