"""
Service Registry Module
=======================
Defines the CloudService data model and synthetic baseline registries
for Compute and Storage categories.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import copy


@dataclass
class CloudService:
    """Represents a single cloud service with QoS attributes."""
    service_id: str
    name: str
    category: str  # "Compute" or "Storage"
    latency: float  # milliseconds
    cost: float  # cost per invocation
    availability: float  # percentage (0-100)
    reliability: float  # percentage (0-100)
    status: str = "AVAILABLE"  # "AVAILABLE" or "UNAVAILABLE"


# ---------------------------------------------------------------------------
# Baseline reference bounds per category — used for normalization anchoring.
# These are IMMUTABLE and never change during simulation, ensuring that
# fault injection on one service does not distort the scores of others.
# ---------------------------------------------------------------------------

BASELINE_BOUNDS: Dict[str, Dict[str, Dict[str, float]]] = {
    "Compute": {
        "latency":      {"min": 28.0,  "max": 102.0},
        "cost":         {"min": 0.025, "max": 0.067},
        "availability": {"min": 97.0,  "max": 99.6},
        "reliability":  {"min": 95.0,  "max": 98.6},
    },
    "Storage": {
        "latency":      {"min": 10.0,  "max": 85.0},
        "cost":         {"min": 0.010, "max": 0.050},
        "availability": {"min": 97.5,  "max": 99.9},
        "reliability":  {"min": 96.0,  "max": 99.5},
    },
}


def _build_compute_services() -> List[CloudService]:
    """Five synthetic Compute-category cloud services calibrated to match research paper benchmarks."""
    return [
        CloudService(
            service_id="SVC-C01",
            name="NovaCompute Standard",
            category="Compute",
            latency=43.9,
            cost=0.040,
            availability=99.5,
            reliability=98.0,
        ),
        CloudService(
            service_id="SVC-C02",
            name="Aether Compute HighPerf",
            category="Compute",
            latency=32.0,
            cost=0.04503,
            availability=99.2,
            reliability=97.5,
        ),
        CloudService(
            service_id="SVC-C03",
            name="Quantum Cloud Elite",
            category="Compute",
            latency=55.0,
            cost=0.035,
            availability=99.6,
            reliability=97.0,
        ),
        CloudService(
            service_id="SVC-C04",
            name="NebulaSys Compute",
            category="Compute",
            latency=68.0,
            cost=0.042,
            availability=98.8,
            reliability=98.5,
        ),
        CloudService(
            service_id="SVC-C05",
            name="HyperScale Dynamic",
            category="Compute",
            latency=82.0,
            cost=0.050,
            availability=99.0,
            reliability=97.8,
        ),
    ]


def _build_storage_services() -> List[CloudService]:
    """Two synthetic Storage-category cloud services."""
    return [
        CloudService(
            service_id="SVC-S01",
            name="NovaStore Premium",
            category="Storage",
            latency=18.0,
            cost=0.015,
            availability=99.8,
            reliability=99.2,
        ),
        CloudService(
            service_id="SVC-S02",
            name="AetherVault Secure",
            category="Storage",
            latency=25.0,
            cost=0.022,
            availability=99.5,
            reliability=98.8,
        ),
    ]


# ----- Immutable baselines (deep copies stored once at import time) --------

_COMPUTE_BASELINE: List[CloudService] = _build_compute_services()
_STORAGE_BASELINE: List[CloudService] = _build_storage_services()


def get_baseline_services(category: str) -> List[CloudService]:
    """Return a deep copy of the original baseline services for *category*."""
    if category == "Compute":
        return copy.deepcopy(_COMPUTE_BASELINE)
    elif category == "Storage":
        return copy.deepcopy(_STORAGE_BASELINE)
    raise ValueError(f"Unknown category: {category}")


def get_baseline_bounds(category: str) -> Dict[str, Dict[str, float]]:
    """Return immutable normalization bounds for *category*."""
    if category not in BASELINE_BOUNDS:
        raise ValueError(f"Unknown category: {category}")
    return BASELINE_BOUNDS[category]


def get_all_categories() -> List[str]:
    """Return available service categories."""
    return ["Compute", "Storage"]
