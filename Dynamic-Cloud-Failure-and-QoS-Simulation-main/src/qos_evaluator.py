"""Calculate normalized QoS scores for cloud services.

This module is the mathematical core of the project. It takes raw QoS metric values
(latency in ms, cost in currency, availability in %, reliability in %) and converts
them into comparable 0–1 normalized scores. It then combines them into a single
weighted aggregate QoS score that the recommendation engine uses to rank services.

Key Concepts:
    - Normalization: Converts metrics with different units into a common 0–1 scale.
    - Lower-is-better metrics (latency, cost): A value equal to the minimum in the
      category gets a score of 1.0 (best); the maximum gets 0.0 (worst).
    - Higher-is-better metrics (availability, reliability): A value equal to the
      maximum gets 1.0 (best); the minimum gets 0.0 (worst).
    - Weighted scoring: Each metric's normalized score is multiplied by its weight,
      and the products are summed to produce the final QoS score.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.service_registry import CloudService


# ---------------------------------------------------------------------------
# Constants: metric names and default weight configuration
# ---------------------------------------------------------------------------

# The four QoS metrics evaluated by the system.
METRICS = ("latency", "cost", "availability", "reliability")

# Default weights used when the user does not customize them.
# These must sum to 1.0. Latency and availability are weighted higher by default,
# reflecting a common preference for fast, highly-available services.
DEFAULT_WEIGHTS = {
    "latency": 0.30,
    "cost": 0.20,
    "availability": 0.30,
    "reliability": 0.20,
}


@dataclass
class MetricScores:
    """Holds the individual normalized scores and the final weighted QoS score for a service.

    After a service is evaluated, this object stores:
        - The 0–1 normalized score for each of the four metrics.
        - The final aggregate qos_score (weighted combination of the four scores).

    Fields:
        service_id: Identifier of the service that was evaluated.
        latency_score: Normalized latency score (1.0 = best/lowest latency).
        cost_score: Normalized cost score (1.0 = best/lowest cost).
        availability_score: Normalized availability score (1.0 = best/highest availability).
        reliability_score: Normalized reliability score (1.0 = best/highest reliability).
        qos_score: Final weighted aggregate score in the range [0.0, 1.0].
    """
    service_id: str
    latency_score: float
    cost_score: float
    availability_score: float
    reliability_score: float
    qos_score: float


def _normalize(value: float, minimum: float, maximum: float, lower_is_better: bool) -> float:
    """Scale a single metric value to the 0–1 range, clamping values outside the reference range.

    This is the core normalization formula. It converts a raw metric value into a
    score where 1.0 means "best possible within the reference range" and 0.0 means
    "worst possible".

    For lower-is-better metrics (latency, cost):
        score = (max - value) / (max - min)
        → The lowest value maps to 1.0, the highest to 0.0.

    For higher-is-better metrics (availability, reliability):
        score = (value - min) / (max - min)
        → The highest value maps to 1.0, the lowest to 0.0.

    If max == min (all services have the same value), returns 1.0 to avoid
    division by zero and to treat a uniform metric as equally good for all.

    Values outside the [min, max] range are clamped to [0.0, 1.0].

    Args:
        value: The raw metric value to normalize.
        minimum: The lowest value in the reference range (from baseline bounds).
        maximum: The highest value in the reference range (from baseline bounds).
        lower_is_better: True for latency and cost; False for availability and reliability.

    Returns:
        A float in [0.0, 1.0] representing how good this value is.
    """
    if maximum <= minimum:
        return 1.0
    score = ((maximum - value) if lower_is_better else (value - minimum)) / (maximum - minimum)
    # Clamp to [0.0, 1.0] in case the current value exceeds the baseline range
    # (e.g., after a latency spike pushes latency above the original max)
    return max(0.0, min(1.0, float(score)))


def normalize_lower_is_better(value: float, min_val: float, max_val: float) -> float:
    """Convenience wrapper for normalizing metrics where lower values are better.

    Used for latency and cost. Delegates to _normalize with lower_is_better=True.

    Args:
        value: The raw metric value (e.g., latency in ms).
        min_val: Minimum value in the reference range.
        max_val: Maximum value in the reference range.

    Returns:
        Normalized score in [0.0, 1.0]. A value equal to min_val yields 1.0.
    """
    return _normalize(value, min_val, max_val, True)


def normalize_higher_is_better(value: float, min_val: float, max_val: float) -> float:
    """Convenience wrapper for normalizing metrics where higher values are better.

    Used for availability and reliability. Delegates to _normalize with lower_is_better=False.

    Args:
        value: The raw metric value (e.g., availability percentage).
        min_val: Minimum value in the reference range.
        max_val: Maximum value in the reference range.

    Returns:
        Normalized score in [0.0, 1.0]. A value equal to max_val yields 1.0.
    """
    return _normalize(value, min_val, max_val, False)


def validate_and_normalize_weights(weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Make non-negative weights add up to one; use equal weights if all are zero.

    The user can set arbitrary slider values for each metric's importance. This
    function ensures:
        1. Negative weights are clamped to 0.0 (no metric can have negative importance).
        2. The weights are divided by their sum so they add up to exactly 1.0.
        3. If every weight is zero (or all negative), equal weights of 0.25 are used.

    This guarantees that the weighted QoS score always stays in the [0.0, 1.0] range.

    Args:
        weights: Dictionary with keys "latency", "cost", "availability", "reliability"
                 and float values. If None, DEFAULT_WEIGHTS are used.

    Returns:
        A dictionary with the same four keys, values summing to 1.0.
    """
    # Use the provided weights, or fall back to the defaults defined above
    supplied = weights or DEFAULT_WEIGHTS
    # Clamp each weight to be non-negative
    clean = {name: max(0.0, float(supplied.get(name, 0.0))) for name in METRICS}
    total = sum(clean.values())
    # If all weights are zero, assign equal importance (0.25 each);
    # otherwise, divide each weight by the total so they sum to 1.0
    return ({name: 0.25 for name in METRICS} if total <= 0 else
            {name: value / total for name, value in clean.items()})


class QoSEvaluator:
    """Score services using fixed reference bounds and configurable weights.

    This class is responsible for evaluating each service's QoS metrics and
    producing a single aggregate score. It uses reference bounds (min/max per
    category) to normalize metrics, and user-configurable weights to control
    how much each metric influences the final score.

    Typical usage:
        1. Create an evaluator with reference bounds from compute_reference_bounds().
        2. Call evaluate_service() to score a single service.
        3. Call evaluate_all() to score every service at once.
    """

    def __init__(self, reference_bounds: Optional[Dict[str, Dict[str, float]]] = None):
        """Initialize the evaluator with reference bounds for metric normalization.

        Args:
            reference_bounds: Dictionary keyed by category (e.g. "Compute"), where
                              each value is a dict with keys like "min_latency",
                              "max_latency", etc. If None, an empty dict is used
                              and bounds must be set later via set_reference_bounds().
        """
        self.reference_bounds = reference_bounds or {}

    def set_reference_bounds(self, reference_bounds: Dict[str, Dict[str, float]]) -> None:
        """Replace the current reference bounds with new ones.

        Args:
            reference_bounds: New bounds dictionary, same structure as in __init__.
        """
        self.reference_bounds = reference_bounds

    def evaluate_service(
        self,
        service: CloudService,
        weights: Optional[Dict[str, float]] = None,
        custom_bounds: Optional[Dict[str, float]] = None,
    ) -> MetricScores:
        """Calculate the normalized QoS score for a single service.

        Steps performed:
            1. Look up the reference bounds for this service's category.
            2. Normalize each of the four metrics to a 0–1 score.
            3. Validate and normalize the user-specified weights.
            4. Compute the weighted sum: Σ(weight_i × score_i).
            5. Clamp the total to [0.0, 1.0] and round to 4 decimal places.

        Args:
            service: The CloudService instance to evaluate.
            weights: Optional custom weight dictionary. If None, DEFAULT_WEIGHTS are used.
            custom_bounds: Optional per-call bounds override. If None, the evaluator's
                           stored reference_bounds for the service's category are used.

        Returns:
            A MetricScores dataclass containing per-metric scores and the aggregate qos_score.
        """
        # Determine which bounds to use: custom override, or stored category bounds
        bounds = custom_bounds or self.reference_bounds.get(service.category, {})

        # Extract the four raw metric values from the service
        values = {
            "latency": service.latency,
            "cost": service.cost,
            "availability": service.availability,
            "reliability": service.reliability,
        }

        # Map metric names to MetricScores field names
        score_names = {"latency": "latency_score", "cost": "cost_score",
                       "availability": "availability_score", "reliability": "reliability_score"}

        # Normalize each metric using its reference bounds.
        # Latency and cost are "lower is better"; availability and reliability are "higher is better".
        scores = {}
        for metric, value in values.items():
            low = bounds.get(f"min_{metric}", value)
            high = bounds.get(f"max_{metric}", value)
            scores[metric] = _normalize(value, low, high, metric in ("latency", "cost"))

        # Ensure the weights add up to 1.0
        normalized_weights = validate_and_normalize_weights(weights)

        # Calculate the weighted aggregate QoS score:
        # total = w_latency * latency_score + w_cost * cost_score
        #       + w_availability * availability_score + w_reliability * reliability_score
        total = sum(normalized_weights[m] * scores[m] for m in METRICS)

        # Round individual scores to 4 decimal places for clean display
        rounded = {score_names[m]: round(scores[m], 4) for m in METRICS}

        return MetricScores(
            service_id=service.service_id,
            **rounded,
            # Clamp and round the aggregate score to stay within [0.0, 1.0]
            qos_score=max(0.0, min(1.0, round(total, 4))),
        )

    def evaluate_all(
        self,
        services: List[CloudService],
        weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, MetricScores]:
        """Evaluate every service and return a dictionary of their scores.

        This is a convenience method that calls evaluate_service() on each service.

        Args:
            services: List of all CloudService instances to evaluate.
            weights: Optional custom weights; applied uniformly to all services.

        Returns:
            Dictionary mapping service_id → MetricScores for each service.
        """
        return {service.service_id: self.evaluate_service(service, weights) for service in services}
