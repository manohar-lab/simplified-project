"""
QoS Evaluator Module
====================
Implements min-max normalization and weighted multi-criteria QoS scoring.

Normalization formulas
----------------------
Benefit-type (higher is better — availability, reliability):
    normalized = (x − x_min) / (x_max − x_min)

Cost-type (lower is better — latency, cost):
    normalized = (x_max − x) / (x_max − x_min)

Aggregate score
---------------
    Q(s) = Σ  w_i × q_i(s)
"""

from typing import Dict, List, Optional, Tuple
from service_registry import CloudService, get_baseline_bounds

# Default QoS weights (must sum to 1.0)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "latency":      0.35,
    "cost":         0.20,
    "availability": 0.30,
    "reliability":  0.15,
}

# Classification of each metric
COST_TYPE_METRICS = {"latency", "cost"}        # lower is better
BENEFIT_TYPE_METRICS = {"availability", "reliability"}  # higher is better


def validate_weights(weights: Dict[str, float]) -> Dict[str, float]:
    """Validate and normalize weights so they sum to 1.0.

    Raises ValueError if any weight is negative or no metrics are provided.
    """
    if not weights:
        raise ValueError("Weights dictionary must not be empty.")
    for metric, w in weights.items():
        if w < 0:
            raise ValueError(f"Weight for '{metric}' must be non-negative, got {w}.")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Sum of weights must be positive.")
    if abs(total - 1.0) > 1e-6:
        weights = {k: v / total for k, v in weights.items()}
    return weights


def _safe_normalize(value: float, bound_min: float, bound_max: float,
                    is_cost_type: bool) -> float:
    """Normalize a single metric value using baseline bounds.

    Returns 0.0 for invalid / missing values and handles equal bounds.
    """
    if value is None or not isinstance(value, (int, float)):
        return 0.0
    import math
    if math.isnan(value) or math.isinf(value):
        return 0.0

    denom = bound_max - bound_min
    if abs(denom) < 1e-12:
        return 1.0  # All services identical on this metric

    if is_cost_type:
        raw = (bound_max - value) / denom
    else:
        raw = (value - bound_min) / denom

    return max(0.0, min(1.0, raw))


def evaluate_service(
    service: CloudService,
    weights: Optional[Dict[str, float]] = None,
    bounds: Optional[Dict[str, Dict[str, float]]] = None,
) -> Tuple[float, Dict[str, float]]:
    """Compute the aggregate QoS score for a single service.

    Returns (aggregate_score, {metric: normalized_score}).
    """
    w = validate_weights(weights or DEFAULT_WEIGHTS)
    b = bounds or get_baseline_bounds(service.category)

    normalized: Dict[str, float] = {}
    for metric in ("latency", "cost", "availability", "reliability"):
        raw_value = getattr(service, metric, None)
        bmin = b[metric]["min"]
        bmax = b[metric]["max"]
        is_cost = metric in COST_TYPE_METRICS
        normalized[metric] = _safe_normalize(raw_value, bmin, bmax, is_cost)

    aggregate = sum(w.get(m, 0.0) * normalized.get(m, 0.0) for m in normalized)
    aggregate = round(aggregate, 4)
    return aggregate, normalized


def evaluate_all(
    services: List[CloudService],
    weights: Optional[Dict[str, float]] = None,
) -> List[Tuple[CloudService, float, Dict[str, float]]]:
    """Evaluate and rank all services by descending QoS score.

    Returns list of (service, score, normalized_metrics) sorted best-first.
    Ties are broken alphabetically by service_id for determinism.
    """
    if not services:
        return []

    w = validate_weights(weights or DEFAULT_WEIGHTS)
    results = []
    for svc in services:
        score, norms = evaluate_service(svc, w)
        results.append((svc, score, norms))

    results.sort(key=lambda t: (-t[1], t[0].service_id))
    return results
