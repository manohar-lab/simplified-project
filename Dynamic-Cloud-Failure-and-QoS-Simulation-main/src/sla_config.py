"""SLA threshold configuration and service validation logic.

Defines configurable SLA thresholds (latency, availability, reliability)
and validation rules for strict service eligibility filtering.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.service_registry import CloudService


@dataclass
class SLAConfig:
    """Configurable SLA constraints for cloud service eligibility.

    A candidate service must satisfy ALL constraints to be eligible for selection:
        1. latency <= max_latency (ms)
        2. availability >= min_availability (%)
        3. reliability >= min_reliability (%)

    Attributes:
        max_latency: Maximum permitted response time in milliseconds.
                     Must be a finite positive number (> 0.0).
        min_availability: Minimum required availability percentage (0.0–100.0).
                          Must be a finite percentage in [0.0, 100.0].
        min_reliability: Minimum required reliability percentage (0.0–100.0).
                         Must be a finite percentage in [0.0, 100.0].
    """
    max_latency: float = 150.0
    min_availability: float = 98.0
    min_reliability: float = 97.0

    def __post_init__(self) -> None:
        """Validate threshold values and reject invalid or impossible configurations."""
        # 1. Validate max_latency
        if not isinstance(self.max_latency, (int, float)):
            raise TypeError(f"max_latency must be numeric, got {type(self.max_latency).__name__}.")
        if not math.isfinite(self.max_latency):
            raise ValueError(f"max_latency must be a finite number, got {self.max_latency}.")
        if self.max_latency <= 0.0:
            raise ValueError(f"max_latency must be strictly positive (> 0.0 ms), got {self.max_latency}.")

        # 2. Validate min_availability
        if not isinstance(self.min_availability, (int, float)):
            raise TypeError(f"min_availability must be numeric, got {type(self.min_availability).__name__}.")
        if not math.isfinite(self.min_availability):
            raise ValueError(f"min_availability must be a finite number, got {self.min_availability}.")
        if not (0.0 <= self.min_availability <= 100.0):
            raise ValueError(f"min_availability must be in [0.0, 100.0]%, got {self.min_availability}.")

        # 3. Validate min_reliability
        if not isinstance(self.min_reliability, (int, float)):
            raise TypeError(f"min_reliability must be numeric, got {type(self.min_reliability).__name__}.")
        if not math.isfinite(self.min_reliability):
            raise ValueError(f"min_reliability must be a finite number, got {self.min_reliability}.")
        if not (0.0 <= self.min_reliability <= 100.0):
            raise ValueError(f"min_reliability must be in [0.0, 100.0]%, got {self.min_reliability}.")

    def to_dict(self) -> Dict[str, float]:
        """Convert SLA configuration to dictionary for serialization or UI display."""
        return {
            "max_latency": float(self.max_latency),
            "min_availability": float(self.min_availability),
            "min_reliability": float(self.min_reliability),
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

    Safely handles missing (None), non-finite (NaN, inf), or out-of-range metrics.

    Args:
        service: The CloudService instance to evaluate.
        sla_config: The active SLAConfig containing constraint thresholds.

    Returns:
        List of human-readable violation strings. Empty list if the service satisfies all SLAs.
    """
    violations: List[str] = []

    # 1. Latency validation
    lat = getattr(service, "latency", None)
    if lat is None or not isinstance(lat, (int, float)) or not math.isfinite(lat) or lat < 0.0:
        violations.append(f"Latency SLA violated: metric value ({lat}) is invalid, missing, or non-finite.")
    elif lat > sla_config.max_latency:
        violations.append(f"Latency SLA violated: {lat:.1f} ms exceeds maximum {sla_config.max_latency:.1f} ms.")

    # 2. Availability validation
    avail = getattr(service, "availability", None)
    if avail is None or not isinstance(avail, (int, float)) or not math.isfinite(avail) or not (0.0 <= avail <= 100.0):
        violations.append(f"Availability SLA violated: metric value ({avail}) is invalid, missing, or out of range [0.0, 100.0].")
    elif avail < sla_config.min_availability:
        violations.append(f"Availability SLA violated: {avail:.2f}% is below minimum {sla_config.min_availability:.2f}%.")

    # 3. Reliability validation
    rel = getattr(service, "reliability", None)
    if rel is None or not isinstance(rel, (int, float)) or not math.isfinite(rel) or not (0.0 <= rel <= 100.0):
        violations.append(f"Reliability SLA violated: metric value ({rel}) is invalid, missing, or out of range [0.0, 100.0].")
    elif rel < sla_config.min_reliability:
        violations.append(f"Reliability SLA violated: {rel:.2f}% is below minimum {sla_config.min_reliability:.2f}%.")

    return violations
