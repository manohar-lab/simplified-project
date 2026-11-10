"""Hysteresis and anti-flapping configuration and validation logic.

Defines configurable hysteresis parameters (minimum QoS delta, cooldown)
to prevent high-frequency flapping and unnecessary service switching.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple


@dataclass
class HysteresisConfig:
    """Configurable hysteresis constraints to prevent service flapping.

    Attributes:
        min_qos_delta: Minimum aggregate QoS score improvement (0.0 to 1.0 scale)
                       required to switch from the currently selected service to an
                       alternative candidate. Must be in [0.0, 1.0].
                       Default is 0.05 (5% composite QoS score advantage).
        cooldown_steps: Minimum number of simulation / recommendation steps that must
                        elapse after a service switch before another performance-driven
                        switch is permitted. Must be an integer >= 0. Default is 0.
        cooldown_seconds: Minimum wall-clock seconds that must elapse after a switch
                          before another performance-driven switch is permitted.
                          Must be a finite float >= 0.0. Default is 0.0.
    """
    min_qos_delta: float = 0.05
    cooldown_steps: int = 0
    cooldown_seconds: float = 0.0

    def __post_init__(self) -> None:
        """Validate threshold values and reject invalid or non-finite configurations."""
        # 1. Validate min_qos_delta
        if not isinstance(self.min_qos_delta, (int, float)):
            raise TypeError(f"min_qos_delta must be numeric, got {type(self.min_qos_delta).__name__}.")
        if not math.isfinite(self.min_qos_delta):
            raise ValueError(f"min_qos_delta must be a finite number, got {self.min_qos_delta}.")
        if not (0.0 <= self.min_qos_delta <= 1.0):
            raise ValueError(f"min_qos_delta must be in [0.0, 1.0], got {self.min_qos_delta}.")

        # 2. Validate cooldown_steps
        if not isinstance(self.cooldown_steps, int) or isinstance(self.cooldown_steps, bool):
            raise TypeError(f"cooldown_steps must be an integer, got {type(self.cooldown_steps).__name__}.")
        if self.cooldown_steps < 0:
            raise ValueError(f"cooldown_steps must be >= 0, got {self.cooldown_steps}.")

        # 3. Validate cooldown_seconds
        if not isinstance(self.cooldown_seconds, (int, float)):
            raise TypeError(f"cooldown_seconds must be numeric, got {type(self.cooldown_seconds).__name__}.")
        if not math.isfinite(self.cooldown_seconds):
            raise ValueError(f"cooldown_seconds must be a finite number, got {self.cooldown_seconds}.")
        if self.cooldown_seconds < 0.0:
            raise ValueError(f"cooldown_seconds must be >= 0.0, got {self.cooldown_seconds}.")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "min_qos_delta": float(self.min_qos_delta),
            "cooldown_steps": int(self.cooldown_steps),
            "cooldown_seconds": float(self.cooldown_seconds),
        }


DEFAULT_HYSTERESIS_CONFIG = HysteresisConfig(
    min_qos_delta=0.05,
    cooldown_steps=0,
    cooldown_seconds=0.0,
)


def check_cooldown_active(
    config: HysteresisConfig,
    current_step: Optional[int] = None,
    last_switch_step: Optional[int] = None,
    current_time: Optional[float] = None,
    last_switch_time: Optional[float] = None,
) -> Tuple[bool, str]:
    """Check if switching cooldown is currently active.

    Args:
        config: HysteresisConfig instance.
        current_step: Current simulation step counter.
        last_switch_step: Step counter when the last switch occurred.
        current_time: Current epoch timestamp (seconds).
        last_switch_time: Epoch timestamp when the last switch occurred.

    Returns:
        Tuple of (is_active: bool, description: str).
    """
    if config.cooldown_steps > 0 and current_step is not None and last_switch_step is not None:
        elapsed_steps = current_step - last_switch_step
        if elapsed_steps < config.cooldown_steps:
            remaining = config.cooldown_steps - elapsed_steps
            return True, f"step cooldown active ({remaining} step(s) remaining)"

    if config.cooldown_seconds > 0.0 and current_time is not None and last_switch_time is not None:
        elapsed_seconds = current_time - last_switch_time
        if elapsed_seconds < config.cooldown_seconds:
            remaining = config.cooldown_seconds - elapsed_seconds
            return True, f"time cooldown active ({remaining:.1f}s remaining)"

    return False, "cooldown satisfied or inactive"

