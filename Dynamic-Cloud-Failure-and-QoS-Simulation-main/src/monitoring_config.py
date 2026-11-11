"""Centralized periodic monitoring configuration and validation logic.

Defines configurable monitoring parameters (polling interval, active state,
optional history retention limits) used by the Periodic Monitoring Engine.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional


# Sensible default interval for interactive dashboard simulation (seconds)
DEFAULT_MONITORING_INTERVAL_SECONDS: float = 5.0


@dataclass
class MonitoringConfig:
    """Configurable parameters for periodic automatic service monitoring.

    Attributes:
        interval_seconds: Periodic reassessment interval in seconds.
                          Must be a finite positive float (> 0.0). Default is 5.0s.
        enabled: Whether automatic periodic monitoring starts in ACTIVE mode.
                 Must be a boolean. Default is True.
        max_history_events: Optional maximum cap on stored monitoring events.
                            None preserves append-only unbounded history.
                            If provided, must be an integer >= 1.
    """
    interval_seconds: float = DEFAULT_MONITORING_INTERVAL_SECONDS
    enabled: bool = True
    max_history_events: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate configuration parameters and reject invalid values."""
        # 1. Validate interval_seconds
        if isinstance(self.interval_seconds, bool) or not isinstance(self.interval_seconds, (int, float)):
            raise TypeError(
                f"interval_seconds must be numeric, got {type(self.interval_seconds).__name__}."
            )
        if not math.isfinite(self.interval_seconds):
            raise ValueError(f"interval_seconds must be finite, got {self.interval_seconds}.")
        if self.interval_seconds <= 0.0:
            raise ValueError(
                f"interval_seconds must be strictly positive (> 0.0s), got {self.interval_seconds}."
            )

        # Normalize to float
        self.interval_seconds = float(self.interval_seconds)

        # 2. Validate enabled
        if not isinstance(self.enabled, bool):
            raise TypeError(f"enabled must be a boolean, got {type(self.enabled).__name__}.")

        # 3. Validate max_history_events
        if self.max_history_events is not None:
            if isinstance(self.max_history_events, bool) or not isinstance(self.max_history_events, int):
                raise TypeError(
                    f"max_history_events must be an integer or None, got {type(self.max_history_events).__name__}."
                )
            if self.max_history_events < 1:
                raise ValueError(
                    f"max_history_events must be >= 1 when specified, got {self.max_history_events}."
                )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize monitoring configuration to a dictionary."""
        return {
            "interval_seconds": float(self.interval_seconds),
            "enabled": bool(self.enabled),
            "max_history_events": self.max_history_events,
        }


DEFAULT_MONITORING_CONFIG = MonitoringConfig(
    interval_seconds=DEFAULT_MONITORING_INTERVAL_SECONDS,
    enabled=True,
    max_history_events=None,
)

