"""Dynamic Cloud Failure Detection and QoS-Aware Service Reselection.

Phase 2: SLA Constraint Enforcement, Strict Eligibility, and Anti-Flapping Hysteresis.

This package contains the core modules for the project:
  - service_registry : Defines synthetic cloud services and their baseline QoS metrics.
  - qos_evaluator    : Normalizes QoS metrics and calculates weighted scores.
  - sla_config       : Configurable SLA constraint thresholds and compliance validation.
  - hysteresis_config: Configurable hysteresis margin and anti-flapping switching rules.
  - failure_simulator: Injects failures (latency spikes, outages, availability drops)
                       and restores services to baseline.
  - recommendation_engine: Selects the best eligible service based on SLA compliance,
                           hysteresis anti-flapping, and QoS scores, explaining decisions.
"""

from src.sla_config import (
    SLAConfig,
    DEFAULT_SLA_CONFIGS,
    DEFAULT_GLOBAL_SLA_CONFIG,
    get_default_sla_config,
    validate_service_sla,
)

from src.hysteresis_config import (
    HysteresisConfig,
    DEFAULT_HYSTERESIS_CONFIG,
    check_cooldown_active,
)

__version__ = "1.2.0"
