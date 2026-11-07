"""SLA threshold configuration and service validation logic.

Defines configurable SLA thresholds (latency, availability, reliability)
and validation rules for strict service eligibility filtering.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.service_registry import CloudService


@dataclass
class SLAConfig:
    """Configurable SLA constraints for cloud service eligibility.

    A candidate service must satisfy ALL constraints to be eligible for selection:
        1. latency <= max_latency
        2. availability >= min_availability
        3. reliability >= min_reliability

    Attributes:
        max_latency: Maximum permitted response time in milliseconds.
                     Services with latency > max_latency violate the SLA.
        min_availability: Minimum required availability percentage (0–100).
                          Services with availability < min_availability violate the SLA.
        min_reliability: Minimum required reliability percentage (0–100).
                         Services with reliability < min_reliability violate the SLA.
    """
    max_latency: float = 150.0
    min_availability: float = 98.0
    min_reliability: float = 97.0

    def to_dict(self) -> Dict[str, float]:
        """Convert SLA configuration to dictionary for serialization or UI display."""
        return {
            "max_latency": self.max_latency,
            "min_availability": self.min_availability,
            "min_reliability": self.min_reliability,
        }


# Category-specific sensible default SLA thresholds based on baseline datasets
DEFAULT_SLA_CONFIGS: Dict[str, SLAConfig] = {
    "Compute": SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0),
    "Storage": SLAConfig(max_latency=200.0, min_availability=98.0, min_reliability=97.0),
}

# Global fallback default SLA config
DEFAULT_GLOBAL_SLA_CONFIG = SLAConfig(max_latency=150.0, min_availability=98.0, min_reliability=97.0)


def get_default_sla_config(category: Optional[str] = None) -> SLAConfig:
    """Retrieve the default SLA configuration for a given category or the global default.

    Args:
        category: Optional category name string (e.g. "Compute", "Storage").

    Returns:
        The matching SLAConfig instance.
    """
    if category and category in DEFAULT_SLA_CONFIGS:
        return DEFAULT_SLA_CONFIGS[category]
    return DEFAULT_GLOBAL_SLA_CONFIG


def validate_service_sla(service: CloudService, sla_config: SLAConfig) -> List[str]:
    """Validate a candidate service against all SLA thresholds and return all violations.

    Evaluates:
        - Latency (must not exceed max_latency)
        - Availability (must not fall below min_availability)
        - Reliability (must not fall below min_reliability)

    Args:
        service: The CloudService instance to evaluate.
        sla_config: The active SLAConfig containing constraint thresholds.

    Returns:
        List of human-readable violation strings. Empty list if the service satisfies all SLAs.
    """
    violations: List[str] = []

    if service.latency > sla_config.max_latency:
        violations.append(
            f"Latency ({service.latency:.1f}ms) exceeds maximum permitted threshold ({sla_config.max_latency:.1f}ms)"
        )

    if service.availability < sla_config.min_availability:
        violations.append(
            f"Availability ({service.availability:.2f}%) is below minimum requirement ({sla_config.min_availability:.2f}%)"
        )

    if service.reliability < sla_config.min_reliability:
        violations.append(
            f"Reliability ({service.reliability:.2f}%) is below minimum requirement ({sla_config.min_reliability:.2f}%)"
        )

    return violations
