"""Dynamic Cloud Failure Detection and QoS-Aware Service Reselection.

Phase 1 standalone prototype.

This package contains the core modules for the project:
  - service_registry : Defines synthetic cloud services and their baseline QoS metrics.
  - qos_evaluator    : Normalizes QoS metrics and calculates weighted scores.
  - sla_config       : Configurable SLA constraint thresholds and compliance validation.
  - failure_simulator: Injects failures (latency spikes, outages, availability drops)
                       and restores services to baseline.
  - recommendation_engine: Selects the best eligible service based on SLA compliance
                           and QoS scores, explaining decisions.
"""

from src.sla_config import (
    SLAConfig,
    DEFAULT_SLA_CONFIGS,
    DEFAULT_GLOBAL_SLA_CONFIG,
    get_default_sla_config,
    validate_service_sla,
)

__version__ = "1.1.0"
