"""Dynamic Cloud Failure Detection and QoS-Aware Service Reselection.

Phase 1 standalone prototype.

This package contains the core modules for the project:
  - service_registry : Defines synthetic cloud services and their baseline QoS metrics.
  - qos_evaluator    : Normalizes QoS metrics and calculates weighted scores.
  - failure_simulator: Injects failures (latency spikes, outages, availability drops)
                       and restores services to baseline.
  - recommendation_engine: Selects the best available service based on QoS scores
                           and explains why that service was chosen.
"""

__version__ = "1.0.0"
