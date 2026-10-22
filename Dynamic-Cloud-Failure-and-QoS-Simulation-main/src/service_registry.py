"""Service registry defining synthetic candidate cloud services and their baseline QoS.

This module provides deterministic synthetic services with baseline QoS metrics,
allowing reproducible testing and demonstration of failure scenarios.

Key Concepts:
    - Each service has four QoS metrics: latency, cost, availability, reliability.
    - Each service stores a 'baseline' snapshot of its original metric values so that
      the failure simulator can restore it to the original state after a failure.
    - 'Reference bounds' (min/max for each metric per category) are computed from
      baseline values and used later by the QoS evaluator for normalization.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, asdict
from typing import Dict, List, Any


@dataclass
class CloudService:
    """Represents a cloud service candidate with QoS metrics and operational status.

    This is the central data model of the project. Every candidate service that can
    be evaluated, degraded, or recommended is an instance of this class.

    Fields:
        service_id: Unique identifier string, e.g. "SVC-C01".
        name: Human-readable display name, e.g. "NovaCompute Standard".
        category: Service category used for filtering, e.g. "Compute" or "Storage".
        latency: Response time in milliseconds. Lower is better for QoS scoring.
        cost: Price in illustrative currency units per invocation. Lower is better.
        availability: Uptime percentage (0–100). Higher is better.
        reliability: Success-rate percentage (0–100). Higher is better.
        operational_status: Either "AVAILABLE" or "UNAVAILABLE". Only AVAILABLE
                           services are eligible for recommendation.
        baseline: A dictionary snapshot of the original metric values. Used by the
                  failure simulator to restore the service to its pre-failure state.
    """
    service_id: str
    name: str
    category: str
    latency: float       # In milliseconds (lower is better)
    cost: float          # In illustrative currency units per invocation (lower is better)
    availability: float  # Percentage 0-100 (higher is better)
    reliability: float   # Percentage 0-100 (higher is better)
    operational_status: str  # "AVAILABLE" or "UNAVAILABLE"
    baseline: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert this service instance to a plain dictionary.

        Uses Python's dataclasses.asdict() to recursively convert all fields.
        This is useful for serialization, display in DataFrames, and creating
        independent copies of a service via from_dict().

        Returns:
            A dictionary with all field names as keys and their current values.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CloudService:
        """Create a new CloudService instance from a dictionary.

        A deep copy of the input dictionary is made first, so that modifying
        the returned CloudService does not accidentally alter the original dict.

        Args:
            data: Dictionary whose keys match the CloudService field names.

        Returns:
            A new CloudService instance populated from the dictionary values.
        """
        data_copy = copy.deepcopy(data)
        return cls(**data_copy)


# ---------------------------------------------------------------------------
# Deterministic synthetic candidate service definitions
# ---------------------------------------------------------------------------
# These are hard-coded, synthetic services used for demonstration purposes.
# They are NOT real cloud services. Each entry defines a service with its
# QoS metrics and a 'baseline' snapshot that records the original values.
# The baseline is essential because after failure injection (e.g., a latency
# spike), we need the original value to restore the service.
_INITIAL_SERVICES_DATA: List[Dict[str, Any]] = [
    {
        "service_id": "SVC-C01",
        "name": "NovaCompute Standard",
        "category": "Compute",
        "latency": 45.0,
        "cost": 0.040,
        "availability": 99.90,
        "reliability": 99.50,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 45.0,
            "cost": 0.040,
            "availability": 99.90,
            "reliability": 99.50,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C02",
        "name": "AetherCompute HighPerf",
        "category": "Compute",
        "latency": 25.0,
        "cost": 0.085,
        "availability": 99.95,
        "reliability": 99.80,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 25.0,
            "cost": 0.085,
            "availability": 99.95,
            "reliability": 99.80,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C03",
        "name": "EcoCompute Budget",
        "category": "Compute",
        "latency": 120.0,
        "cost": 0.015,
        "availability": 98.80,
        "reliability": 97.50,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 120.0,
            "cost": 0.015,
            "availability": 98.80,
            "reliability": 97.50,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C04",
        "name": "TitanCompute Enterprise",
        "category": "Compute",
        "latency": 55.0,
        "cost": 0.050,
        "availability": 99.85,
        "reliability": 99.90,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 55.0,
            "cost": 0.050,
            "availability": 99.85,
            "reliability": 99.90,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C05",
        "name": "ZenithCompute Flex",
        "category": "Compute",
        "latency": 75.0,
        "cost": 0.028,
        "availability": 99.20,
        "reliability": 98.40,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 75.0,
            "cost": 0.028,
            "availability": 99.20,
            "reliability": 98.40,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-S01",
        "name": "PulseStore Standard",
        "category": "Storage",
        "latency": 35.0,
        "cost": 0.020,
        "availability": 99.90,
        "reliability": 99.60,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 35.0,
            "cost": 0.020,
            "availability": 99.90,
            "reliability": 99.60,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-S02",
        "name": "GlacierStore Archive",
        "category": "Storage",
        "latency": 160.0,
        "cost": 0.005,
        "availability": 99.10,
        "reliability": 99.90,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 160.0,
            "cost": 0.005,
            "availability": 99.10,
            "reliability": 99.90,
            "operational_status": "AVAILABLE",
        },
    },
]


def get_default_services() -> List[CloudService]:
    """Return a fresh list of candidate cloud services with baseline values.

    Each call creates new CloudService objects from the static definitions above,
    so that callers get independent copies they can modify without affecting the
    original definitions. This is important because the failure simulator mutates
    service objects in place (e.g., changing latency or operational_status).

    Returns:
        A list of CloudService instances, one for each entry in _INITIAL_SERVICES_DATA.
    """
    return [CloudService.from_dict(s) for s in _INITIAL_SERVICES_DATA]


def compute_reference_bounds(services: List[CloudService]) -> Dict[str, Dict[str, float]]:
    """Compute baseline reference min/max bounds for each category.

    Using the original candidate baseline values ensures that normalized scores
    remain stable and directly comparable before and after failure injection.

    Why this matters:
        When we normalize a metric (e.g., latency) to a 0–1 scale, we need a
        fixed min and max range. If we used *current* values (which change during
        failure injection), the scale would shift every time a failure is injected,
        making scores incomparable across runs. By using the *baseline* values,
        the normalization range stays constant.

    Args:
        services: The list of all candidate CloudService instances.

    Returns:
        A dictionary keyed by category name (e.g. "Compute"), where each value is
        another dictionary with keys like "min_latency", "max_latency", "min_cost",
        "max_cost", "min_availability", "max_availability", "min_reliability",
        "max_reliability".
    """
    bounds: Dict[str, Dict[str, float]] = {}
    # Collect unique categories (e.g., "Compute", "Storage")
    categories = set(s.category for s in services)

    for cat in categories:
        # Filter services belonging to this category
        cat_services = [s for s in services if s.category == cat]
        if not cat_services:
            continue

        # Extract baseline metric values for all services in this category
        latencies = [s.baseline["latency"] for s in cat_services]
        costs = [s.baseline["cost"] for s in cat_services]
        availabilities = [s.baseline["availability"] for s in cat_services]
        reliabilities = [s.baseline["reliability"] for s in cat_services]

        # Store the min and max for each metric; these become the normalization range
        bounds[cat] = {
            "min_latency": min(latencies),
            "max_latency": max(latencies),
            "min_cost": min(costs),
            "max_cost": max(costs),
            "min_availability": min(availabilities),
            "max_availability": max(availabilities),
            "min_reliability": min(reliabilities),
            "max_reliability": max(reliabilities),
        }

    return bounds
