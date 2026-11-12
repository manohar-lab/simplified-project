"""Dynamic Cloud Failure Detection and QoS-Aware Service Reselection.

Phase 4: SLA Constraint Enforcement, Anti-Flapping Hysteresis, Periodic Monitoring,
and Validated Manual Service Override.

This package contains the core modules for the project:
  - service_registry   : Defines synthetic cloud services and their baseline QoS metrics.
  - qos_evaluator      : Normalizes QoS metrics and calculates weighted scores.
  - sla_config         : Configurable SLA constraint thresholds and compliance validation.
  - hysteresis_config  : Configurable hysteresis margin and anti-flapping switching rules.
  - monitoring_config  : Configurable periodic monitoring interval and retention settings.
  - monitoring_engine  : Automated periodic health reassessment and event logging engine.
  - override_manager   : Operating mode management and strict manual override validation.
  - failure_simulator  : Injects failures (latency spikes, outages, availability drops)
                         and restores services to baseline.
  - recommendation_engine: Selects the best eligible service based on SLA compliance,
                           hysteresis anti-flapping, operating mode, and QoS scores.
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

from src.monitoring_config import (
    MonitoringConfig,
    DEFAULT_MONITORING_CONFIG,
    DEFAULT_MONITORING_INTERVAL_SECONDS,
)

from src.monitoring_engine import (
    MonitoringEngine,
    MonitoringEvent,
    MonitoringCycleResult,
    ServiceHealthSnapshot,
)

from src.override_manager import (
    MODE_AUTOMATIC,
    MODE_MANUAL,
    OVERRIDE_EVENT_ACTIVATED,
    OVERRIDE_EVENT_CLEARED,
    OVERRIDE_EVENT_REJECTED,
    OVERRIDE_EVENT_EMERGENCY_TERMINATED,
    OVERRIDE_EVENT_AUTO_RESTORED,
    ManualOverrideManager,
    OverrideValidationResult,
    OverrideTransitionEvent,
    validate_manual_override_request,
)

__version__ = "1.4.0"
