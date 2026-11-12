"""Periodic Automatic Service Monitoring and Health Reassessment Engine.

Provides automated, periodic reassessment of registered cloud services, integrating:
    - Canonical health classification (HEALTHY, DEGRADED, UNAVAILABLE, RECOVERED)
    - Phase 1 strict SLA validation (via validate_service_sla)
    - Phase 2 hysteresis & anti-flapping reselection (via RecommendationEngine)
    - Overlap-safe, exception-resilient execution
    - Deduplicated append-only monitoring event history

Does NOT duplicate QoS evaluation, SLA logic, or hysteresis logic, and does NOT
modify baseline service metrics or inject random failures.
"""

from __future__ import annotations
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pandas as pd

from src.service_registry import CloudService
from src.qos_evaluator import QoSEvaluator
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla
from src.hysteresis_config import HysteresisConfig, DEFAULT_HYSTERESIS_CONFIG
from src.recommendation_engine import RecommendationEngine, RecommendationResult
from src.override_manager import (
    MODE_AUTOMATIC,
    MODE_MANUAL,
    ManualOverrideManager,
    OVERRIDE_EVENT_EMERGENCY_TERMINATED,
)
from src.analytics import (
    classify_service_health,
    HEALTH_HEALTHY,
    HEALTH_DEGRADED,
    HEALTH_UNAVAILABLE,
    HEALTH_RECOVERED,
)
from src.monitoring_config import MonitoringConfig, DEFAULT_MONITORING_CONFIG

logger = logging.getLogger(__name__)


# =========================================================================
# Canonical Monitoring Event Type Constants
# =========================================================================
EVENT_MONITORING_STARTED = "MONITORING_STARTED"
EVENT_MONITORING_PAUSED = "MONITORING_PAUSED"
EVENT_MONITORING_RESUMED = "MONITORING_RESUMED"
EVENT_CYCLE_STARTED = "MONITORING_CYCLE_STARTED"
EVENT_CYCLE_COMPLETED = "MONITORING_CYCLE_COMPLETED"
EVENT_SERVICE_HEALTH_CHANGED = "SERVICE_HEALTH_CHANGED"
EVENT_SLA_VIOLATION_DETECTED = "SLA_VIOLATION_DETECTED"
EVENT_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
EVENT_SERVICE_RECOVERED = "SERVICE_RECOVERED"
EVENT_AUTOMATIC_RESELECTION = "AUTOMATIC_RESELECTION"
EVENT_MANUAL_OVERRIDE_TERMINATED = OVERRIDE_EVENT_EMERGENCY_TERMINATED
EVENT_NO_ELIGIBLE_SERVICE = "NO_ELIGIBLE_SERVICE"
EVENT_MONITORING_ERROR = "MONITORING_ERROR"

STATUS_ACTIVE = "ACTIVE"
STATUS_PAUSED = "PAUSED"


def _format_epoch(epoch: Optional[float]) -> Optional[str]:
    """Format an epoch timestamp safely across platforms including small test epochs."""
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(epoch).strftime("%H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%H:%M:%S")


def _steady_health_state(health_state: str) -> str:
    """Normalize RECOVERED -> HEALTHY for cycle-to-cycle change deduplication."""
    return HEALTH_HEALTHY if health_state == HEALTH_RECOVERED else health_state


@dataclass
class MonitoringEvent:
    """Represents a meaningful event recorded during periodic service monitoring."""
    sequence_number: int
    event_type: str
    service_id: str
    service_name: str
    timestamp: str
    epoch_time: float
    previous_health_state: Optional[str]
    new_health_state: Optional[str]
    reason: str
    category: str = ""
    cycle_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize monitoring event to a dictionary."""
        return asdict(self)


@dataclass
class ServiceHealthSnapshot:
    """Observed health and SLA compliance state of a single service in a monitoring cycle."""
    service_id: str
    name: str
    category: str
    operational_status: str
    health_state: str
    sla_compliant: bool
    sla_violations: List[str]
    qos_score: float
    latency: Any
    cost: Any
    availability: Any
    reliability: Any
    is_eligible: bool


@dataclass
class MonitoringCycleResult:
    """Structured summary produced by a single monitoring cycle execution."""
    cycle_number: int
    timestamp: str
    epoch_time: float
    status: str  # "ACTIVE", "PAUSED", "SKIPPED_OVERLAP", "SKIPPED_INTERVAL", "ERROR"
    category: str
    total_services: int
    healthy_count: int
    degraded_count: int
    unavailable_count: int
    sla_violating_count: int
    eligible_count: int
    selected_service_id: Optional[str]
    selected_service_name: Optional[str]
    recommendation_result: Optional[RecommendationResult]
    reselection_triggered: bool
    changes_detected: bool
    service_snapshots: Dict[str, ServiceHealthSnapshot] = field(default_factory=dict)
    events_emitted: List[MonitoringEvent] = field(default_factory=list)
    error_message: Optional[str] = None


class MonitoringEngine:
    """Manages periodic automatic assessment of registered cloud services."""

    def __init__(
        self,
        evaluator: QoSEvaluator,
        recommendation_engine: RecommendationEngine,
        config: Optional[MonitoringConfig] = None,
        time_fn: Optional[Callable[[], float]] = None,
        override_manager: Optional[ManualOverrideManager] = None,
    ):
        """Initialize the periodic monitoring engine.

        Args:
            evaluator: Existing QoSEvaluator used to score candidates.
            recommendation_engine: Existing RecommendationEngine (Phase 1 SLA + Phase 2 Hysteresis).
            config: MonitoringConfig instance. Defaults to DEFAULT_MONITORING_CONFIG.
            time_fn: Injectable clock returning epoch seconds (defaults to time.time).
            override_manager: Optional ManualOverrideManager for operating mode integration.
        """
        self.evaluator = evaluator
        self.recommendation_engine = recommendation_engine
        self.config: MonitoringConfig = config if config is not None else DEFAULT_MONITORING_CONFIG
        self.time_fn: Callable[[], float] = time_fn if time_fn is not None else time.time
        self.override_manager: Optional[ManualOverrideManager] = override_manager

        self.is_active: bool = self.config.enabled
        self.cycle_count: int = 0
        self.last_run_epoch: Optional[float] = None
        self.last_run_timestamp: Optional[str] = None
        self.next_expected_epoch: Optional[float] = (
            float(self.time_fn()) + self.config.interval_seconds if self.is_active else None
        )
        self.next_expected_timestamp: Optional[str] = _format_epoch(self.next_expected_epoch)
        self.last_cycle_result: Optional[MonitoringCycleResult] = None

        self.event_history: List[MonitoringEvent] = []
        self._cycle_lock = threading.Lock()

        # Internal state maps for change detection and duplicate prevention
        self._last_service_states: Dict[str, Dict[str, Any]] = {}
        self._initialized_categories: Set[str] = set()
        self._category_selected_id: Dict[str, Optional[str]] = {}
        self._category_last_switch_step: Dict[str, Optional[int]] = {}
        self._category_last_switch_time: Dict[str, Optional[float]] = {}
        self._category_no_eligible_reported: Dict[str, bool] = {}

        now = float(self.time_fn())
        if self.is_active:
            self._append_event(
                event_type=EVENT_MONITORING_STARTED,
                service_id="SYSTEM",
                service_name="Periodic Monitor",
                epoch_time=now,
                previous_health_state=None,
                new_health_state=STATUS_ACTIVE,
                reason=f"Periodic monitoring initialized (interval: {self.config.interval_seconds:.1f}s).",
            )
        else:
            self._append_event(
                event_type=EVENT_MONITORING_PAUSED,
                service_id="SYSTEM",
                service_name="Periodic Monitor",
                epoch_time=now,
                previous_health_state=None,
                new_health_state=STATUS_PAUSED,
                reason="Periodic monitoring initialized in PAUSED state.",
            )

    @property
    def status_label(self) -> str:
        """Return 'ACTIVE' or 'PAUSED'."""
        return STATUS_ACTIVE if self.is_active else STATUS_PAUSED

    def _append_event(
        self,
        event_type: str,
        service_id: str,
        service_name: str,
        epoch_time: float,
        previous_health_state: Optional[str],
        new_health_state: Optional[str],
        reason: str,
        category: str = "",
        cycle_number: int = 0,
    ) -> MonitoringEvent:
        """Append a single MonitoringEvent to the append-only audit history."""
        seq = len(self.event_history) + 1
        evt = MonitoringEvent(
            sequence_number=seq,
            event_type=event_type,
            service_id=service_id,
            service_name=service_name,
            timestamp=_format_epoch(epoch_time) or "00:00:00",
            epoch_time=epoch_time,
            previous_health_state=previous_health_state,
            new_health_state=new_health_state,
            reason=reason,
            category=category,
            cycle_number=cycle_number,
        )
        self.event_history.append(evt)
        if (
            self.config.max_history_events is not None
            and len(self.event_history) > self.config.max_history_events
        ):
            self.event_history = self.event_history[-self.config.max_history_events:]
        return evt

    def start(self) -> None:
        """Start or resume periodic monitoring (idempotent if already active)."""
        self.resume()

    def resume(self) -> None:
        """Resume periodic monitoring if currently paused (idempotent)."""
        if self.is_active:
            return
        now = float(self.time_fn())
        self.is_active = True
        self.next_expected_epoch = now + self.config.interval_seconds
        self.next_expected_timestamp = _format_epoch(self.next_expected_epoch)
        self._append_event(
            event_type=EVENT_MONITORING_RESUMED,
            service_id="SYSTEM",
            service_name="Periodic Monitor",
            epoch_time=now,
            previous_health_state=STATUS_PAUSED,
            new_health_state=STATUS_ACTIVE,
            reason=f"Periodic monitoring resumed (interval: {self.config.interval_seconds:.1f}s).",
            cycle_number=self.cycle_count,
        )

    def pause(self) -> None:
        """Pause automatic periodic monitoring safely (idempotent)."""
        if not self.is_active:
            return
        now = float(self.time_fn())
        self.is_active = False
        self.next_expected_epoch = None
        self.next_expected_timestamp = None
        self._append_event(
            event_type=EVENT_MONITORING_PAUSED,
            service_id="SYSTEM",
            service_name="Periodic Monitor",
            epoch_time=now,
            previous_health_state=STATUS_ACTIVE,
            new_health_state=STATUS_PAUSED,
            reason="Periodic monitoring paused by configuration or user action.",
            cycle_number=self.cycle_count,
        )

    def stop(self) -> None:
        """Alias for pause()."""
        self.pause()

    def update_config(self, new_config: MonitoringConfig) -> None:
        """Update monitoring configuration safely."""
        if not isinstance(new_config, MonitoringConfig):
            raise TypeError(f"Expected MonitoringConfig, got {type(new_config).__name__}.")
        self.config = new_config
        if self.is_active:
            base_epoch = self.last_run_epoch if self.last_run_epoch is not None else float(self.time_fn())
            self.next_expected_epoch = base_epoch + self.config.interval_seconds
            self.next_expected_timestamp = _format_epoch(self.next_expected_epoch)

    def sync_external_selection(
        self,
        category: str,
        selected_id: Optional[str],
        switch_step: Optional[int] = None,
        switch_time: Optional[float] = None,
    ) -> None:
        """Synchronize externally updated selection (e.g. sidebar actions) to prevent duplicate reselections."""
        self._category_selected_id[category] = selected_id
        if switch_step is not None:
            self._category_last_switch_step[category] = switch_step
        if switch_time is not None:
            self._category_last_switch_time[category] = switch_time
        self._category_no_eligible_reported[category] = (selected_id is None and category in self._initialized_categories)

    def clear_events(self) -> None:
        """Clear monitoring event log."""
        self.event_history.clear()

    def reset(self, clear_events: bool = False) -> None:
        """Reset tracked state (cycles, observed service healths, category selections)."""
        self.cycle_count = 0
        self.last_run_epoch = None
        self.last_run_timestamp = None
        self.last_cycle_result = None
        self._last_service_states.clear()
        self._initialized_categories.clear()
        self._category_selected_id.clear()
        self._category_last_switch_step.clear()
        self._category_last_switch_time.clear()
        self._category_no_eligible_reported.clear()
        if clear_events:
            self.event_history.clear()
        now = float(self.time_fn())
        if self.is_active:
            self.next_expected_epoch = now + self.config.interval_seconds
            self.next_expected_timestamp = _format_epoch(self.next_expected_epoch)
        else:
            self.next_expected_epoch = None
            self.next_expected_timestamp = None

    def run_cycle(
        self,
        services: List[CloudService],
        category: str,
        weights: Optional[Dict[str, float]] = None,
        sla_config: Optional[SLAConfig] = None,
        hysteresis_config: Optional[HysteresisConfig] = None,
        previously_selected_id: Optional[str] = None,
        current_step: Optional[int] = None,
        last_switch_step: Optional[int] = None,
        last_switch_time: Optional[float] = None,
        force: bool = False,
        respect_interval: bool = False,
        override_manager: Optional[ManualOverrideManager] = None,
    ) -> MonitoringCycleResult:
        """Execute one deterministic service monitoring and reassessment cycle.

        Args:
            services: List of registered CloudService objects.
            category: Target service category to evaluate.
            weights: Optional normalized QoS weights.
            sla_config: Active Phase 1 SLAConfig. Defaults to category default.
            hysteresis_config: Active Phase 2 HysteresisConfig. Defaults to DEFAULT_HYSTERESIS_CONFIG.
            previously_selected_id: Optional external active selection ID. If None, uses tracked ID.
            current_step: Optional simulation step counter for cooldown checks.
            last_switch_step: Optional simulation step of last switch.
            last_switch_time: Optional epoch timestamp of last switch.
            force: If True, runs even when monitoring is PAUSED or interval not elapsed.
            respect_interval: If True, skips execution unless interval_seconds has elapsed
                              since last_run_epoch (unless force=True or first cycle).

        Returns:
            MonitoringCycleResult summarizing health states, counts, events, and reselection status.
        """
        now_epoch = float(self.time_fn())
        now_str = _format_epoch(now_epoch) or "00:00:00"

        # 1. Respect PAUSED state unless explicitly forced
        if not self.is_active and not force:
            prev_res = self.last_cycle_result
            return MonitoringCycleResult(
                cycle_number=self.cycle_count,
                timestamp=now_str,
                epoch_time=now_epoch,
                status=STATUS_PAUSED,
                category=category,
                total_services=prev_res.total_services if prev_res else 0,
                healthy_count=prev_res.healthy_count if prev_res else 0,
                degraded_count=prev_res.degraded_count if prev_res else 0,
                unavailable_count=prev_res.unavailable_count if prev_res else 0,
                sla_violating_count=prev_res.sla_violating_count if prev_res else 0,
                eligible_count=prev_res.eligible_count if prev_res else 0,
                selected_service_id=self._category_selected_id.get(category, previously_selected_id),
                selected_service_name=prev_res.selected_service_name if prev_res else None,
                recommendation_result=prev_res.recommendation_result if prev_res else None,
                reselection_triggered=False,
                changes_detected=False,
                service_snapshots=prev_res.service_snapshots if prev_res else {},
                events_emitted=[],
            )

        # 2. Prevent overlapping cycles
        if not self._cycle_lock.acquire(blocking=False):
            prev_res = self.last_cycle_result
            return MonitoringCycleResult(
                cycle_number=self.cycle_count,
                timestamp=now_str,
                epoch_time=now_epoch,
                status="SKIPPED_OVERLAP",
                category=category,
                total_services=prev_res.total_services if prev_res else 0,
                healthy_count=prev_res.healthy_count if prev_res else 0,
                degraded_count=prev_res.degraded_count if prev_res else 0,
                unavailable_count=prev_res.unavailable_count if prev_res else 0,
                sla_violating_count=prev_res.sla_violating_count if prev_res else 0,
                eligible_count=prev_res.eligible_count if prev_res else 0,
                selected_service_id=self._category_selected_id.get(category, previously_selected_id),
                selected_service_name=prev_res.selected_service_name if prev_res else None,
                recommendation_result=prev_res.recommendation_result if prev_res else None,
                reselection_triggered=False,
                changes_detected=False,
                service_snapshots=prev_res.service_snapshots if prev_res else {},
                events_emitted=[],
            )

        try:
            # 3. Respect configured monitoring interval when requested
            if (
                respect_interval
                and not force
                and self.last_run_epoch is not None
                and (now_epoch - self.last_run_epoch) < self.config.interval_seconds
            ):
                prev_res = self.last_cycle_result
                return MonitoringCycleResult(
                    cycle_number=self.cycle_count,
                    timestamp=now_str,
                    epoch_time=now_epoch,
                    status="SKIPPED_INTERVAL",
                    category=category,
                    total_services=prev_res.total_services if prev_res else 0,
                    healthy_count=prev_res.healthy_count if prev_res else 0,
                    degraded_count=prev_res.degraded_count if prev_res else 0,
                    unavailable_count=prev_res.unavailable_count if prev_res else 0,
                    sla_violating_count=prev_res.sla_violating_count if prev_res else 0,
                    eligible_count=prev_res.eligible_count if prev_res else 0,
                    selected_service_id=self._category_selected_id.get(category, previously_selected_id),
                    selected_service_name=prev_res.selected_service_name if prev_res else None,
                    recommendation_result=prev_res.recommendation_result if prev_res else None,
                    reselection_triggered=False,
                    changes_detected=False,
                    service_snapshots=prev_res.service_snapshots if prev_res else {},
                    events_emitted=[],
                )

            self.cycle_count += 1
            cycle_num = self.cycle_count
            is_first_cat_cycle = category not in self._initialized_categories
            self._initialized_categories.add(category)

            effective_sla = sla_config if sla_config is not None else get_default_sla_config(category)
            effective_hyst = hysteresis_config if hysteresis_config is not None else DEFAULT_HYSTERESIS_CONFIG

            # Determine active selection for comparison
            if previously_selected_id is not None:
                effective_prev_id: Optional[str] = previously_selected_id
            else:
                effective_prev_id = self._category_selected_id.get(category)

            effective_step = current_step if current_step is not None else cycle_num
            effective_last_switch_step = (
                last_switch_step if last_switch_step is not None else self._category_last_switch_step.get(category)
            )
            effective_last_switch_time = (
                last_switch_time if last_switch_time is not None else self._category_last_switch_time.get(category)
            )

            # Collect registered services for target category safely
            cat_services = [s for s in services if getattr(s, "category", None) == category]
            total_services = len(cat_services)

            service_snapshots: Dict[str, ServiceHealthSnapshot] = {}
            pending_events: List[Dict[str, Any]] = []

            healthy_count = 0
            degraded_count = 0
            unavailable_count = 0
            sla_violating_count = 0
            eligible_count = 0

            # 4. Evaluate health and SLA status for each service in category
            for s in cat_services:
                prev_state = self._last_service_states.get(s.service_id)
                prev_health = prev_state["health_state"] if prev_state else None
                prev_steady = prev_state["steady_health"] if prev_state else None
                prev_violations = prev_state["sla_violations"] if prev_state else ()

                try:
                    sla_violations = tuple(validate_service_sla(s, effective_sla))
                    current_health = classify_service_health(
                        s,
                        sla_config=effective_sla,
                        previous_health=prev_health,
                    )
                except Exception as svc_exc:
                    logger.exception("Error validating service %s during monitoring cycle", getattr(s, "service_id", "?"))
                    sla_violations = (f"Metric evaluation error: {svc_exc}",)
                    current_health = HEALTH_DEGRADED

                steady_health = _steady_health_state(current_health)
                is_sla_compliant = (len(sla_violations) == 0)
                is_available = (getattr(s, "operational_status", "UNAVAILABLE") == "AVAILABLE")
                is_eligible = is_available and is_sla_compliant

                try:
                    score_val = float(self.evaluator.evaluate_service(s, weights).qos_score)
                    if not (score_val == score_val):  # NaN guard
                        score_val = 0.0
                except Exception:
                    score_val = 0.0

                service_snapshots[s.service_id] = ServiceHealthSnapshot(
                    service_id=s.service_id,
                    name=s.name,
                    category=s.category,
                    operational_status=getattr(s, "operational_status", "UNAVAILABLE"),
                    health_state=current_health,
                    sla_compliant=is_sla_compliant,
                    sla_violations=list(sla_violations),
                    qos_score=score_val,
                    latency=getattr(s, "latency", None),
                    cost=getattr(s, "cost", None),
                    availability=getattr(s, "availability", None),
                    reliability=getattr(s, "reliability", None),
                    is_eligible=is_eligible,
                )

                if current_health in (HEALTH_HEALTHY, HEALTH_RECOVERED):
                    healthy_count += 1
                elif current_health == HEALTH_DEGRADED:
                    degraded_count += 1
                elif current_health == HEALTH_UNAVAILABLE:
                    unavailable_count += 1

                if not is_sla_compliant:
                    sla_violating_count += 1
                if is_eligible:
                    eligible_count += 1

                # Detect meaningful transitions and emit deduplicated events
                if prev_state is None:
                    # Initial observation for this service
                    if current_health == HEALTH_UNAVAILABLE:
                        pending_events.append({
                            "event_type": EVENT_SERVICE_UNAVAILABLE,
                            "service_id": s.service_id,
                            "service_name": s.name,
                            "prev": None,
                            "new": HEALTH_UNAVAILABLE,
                            "reason": f"Service '{s.name}' observed in UNAVAILABLE state during initial monitoring cycle.",
                        })
                    elif sla_violations:
                        pending_events.append({
                            "event_type": EVENT_SLA_VIOLATION_DETECTED,
                            "service_id": s.service_id,
                            "service_name": s.name,
                            "prev": None,
                            "new": current_health,
                            "reason": "; ".join(sla_violations),
                        })
                else:
                    if prev_steady != steady_health:
                        if current_health == HEALTH_RECOVERED:
                            pending_events.append({
                                "event_type": EVENT_SERVICE_RECOVERED,
                                "service_id": s.service_id,
                                "service_name": s.name,
                                "prev": prev_health,
                                "new": HEALTH_RECOVERED,
                                "reason": f"Service '{s.name}' recovered from {prev_health} to healthy SLA-compliant baseline state.",
                            })
                        elif current_health == HEALTH_UNAVAILABLE:
                            pending_events.append({
                                "event_type": EVENT_SERVICE_UNAVAILABLE,
                                "service_id": s.service_id,
                                "service_name": s.name,
                                "prev": prev_health,
                                "new": HEALTH_UNAVAILABLE,
                                "reason": f"Service '{s.name}' became UNAVAILABLE (was {prev_health}).",
                            })
                        else:
                            pending_events.append({
                                "event_type": EVENT_SERVICE_HEALTH_CHANGED,
                                "service_id": s.service_id,
                                "service_name": s.name,
                                "prev": prev_health,
                                "new": current_health,
                                "reason": (
                                    f"Service '{s.name}' health transitioned from {prev_health} to {current_health}"
                                    + (f" ({'; '.join(sla_violations)})" if sla_violations else ".")
                                ),
                            })

                    if sla_violations and sla_violations != prev_violations:
                        pending_events.append({
                            "event_type": EVENT_SLA_VIOLATION_DETECTED,
                            "service_id": s.service_id,
                            "service_name": s.name,
                            "prev": prev_health,
                            "new": current_health,
                            "reason": "; ".join(sla_violations),
                        })

                self._last_service_states[s.service_id] = {
                    "health_state": current_health,
                    "steady_health": steady_health,
                    "operational_status": getattr(s, "operational_status", "UNAVAILABLE"),
                    "sla_violations": sla_violations,
                }

            # 5. Invoke existing Recommendation Engine (Phase 1 SLA + Phase 2 Hysteresis + Phase 4 Operating Mode)
            eff_override_mgr = override_manager if override_manager is not None else self.override_manager
            if (
                eff_override_mgr is not None
                and eff_override_mgr.is_manual_active
                and eff_override_mgr.category == category
            ):
                run_mode = MODE_MANUAL
                manual_id = eff_override_mgr.requested_service_id
                manual_reason = eff_override_mgr.reason
            else:
                run_mode = MODE_AUTOMATIC
                manual_id = None
                manual_reason = ""

            rec = self.recommendation_engine.recommend(
                services=cat_services,
                category=category,
                weights=weights,
                previously_selected_id=effective_prev_id,
                sla_config=effective_sla,
                hysteresis_config=effective_hyst,
                current_step=effective_step,
                last_switch_step=effective_last_switch_step,
                current_time=now_epoch,
                last_switch_time=effective_last_switch_time,
                operating_mode=run_mode,
                manual_service_id=manual_id,
                manual_override_reason=manual_reason,
            )

            reselection_triggered = False
            selected_id: Optional[str] = None
            selected_name: Optional[str] = None

            if rec.override_terminated and manual_id is not None:
                replacement_id = rec.selected_service.service_id if rec.selected_service else None
                terminated_logged = True
                if eff_override_mgr is not None:
                    terminated_logged = eff_override_mgr.handle_emergency_termination(
                        failed_service_id=manual_id,
                        replacement_service_id=replacement_id,
                        reason=rec.override_termination_reason,
                        category=category,
                    )
                if terminated_logged:
                    failed_snap = service_snapshots.get(manual_id)
                    pending_events.append({
                        "event_type": EVENT_MANUAL_OVERRIDE_TERMINATED,
                        "service_id": manual_id,
                        "service_name": failed_snap.name if failed_snap else manual_id,
                        "prev": MODE_MANUAL,
                        "new": MODE_AUTOMATIC,
                        "reason": rec.override_termination_reason,
                    })
                    reselection_triggered = True

            if not rec.has_eligible_service or rec.selected_service is None:
                selected_id = None
                selected_name = None
                if not self._category_no_eligible_reported.get(category, False):
                    pending_events.append({
                        "event_type": EVENT_NO_ELIGIBLE_SERVICE,
                        "service_id": "ALL",
                        "service_name": f"Category: {category}",
                        "prev": effective_prev_id or "None",
                        "new": "NONE",
                        "reason": rec.status_message,
                    })
                    self._category_no_eligible_reported[category] = True
                    if effective_prev_id is not None:
                        reselection_triggered = True
                self._category_selected_id[category] = None
            else:
                was_no_eligible = self._category_no_eligible_reported.get(category, False)
                self._category_no_eligible_reported[category] = False
                selected_id = rec.selected_service.service_id
                selected_name = rec.selected_service.name

                is_actual_switch = (
                    rec.decision_type in ("SWITCHED", "EMERGENCY_OUTAGE", "EMERGENCY_SLA_VIOLATION")
                    or (rec.decision_type == "MANUAL_OVERRIDE" and effective_prev_id is not None and selected_id != effective_prev_id)
                    or (was_no_eligible and selected_id != effective_prev_id)
                )

                if is_actual_switch:
                    reselection_triggered = True
                    self._category_last_switch_step[category] = effective_step
                    self._category_last_switch_time[category] = now_epoch
                    pending_events.append({
                        "event_type": EVENT_AUTOMATIC_RESELECTION,
                        "service_id": selected_id,
                        "service_name": selected_name,
                        "prev": effective_prev_id or "None",
                        "new": service_snapshots[selected_id].health_state if selected_id in service_snapshots else HEALTH_HEALTHY,
                        "reason": f"[{rec.decision_type}] {rec.decision_reason}",
                    })

                self._category_selected_id[category] = selected_id

            # 6. Deduplicated Audit Event Logging: only emit cycle logs if first run or state changed
            changes_detected = len(pending_events) > 0
            emitted_events: List[MonitoringEvent] = []

            if changes_detected or is_first_cat_cycle:
                emitted_events.append(
                    self._append_event(
                        event_type=EVENT_CYCLE_STARTED,
                        service_id="SYSTEM",
                        service_name=f"Monitor ({category})",
                        epoch_time=now_epoch,
                        previous_health_state=None,
                        new_health_state=self.status_label,
                        reason=f"Monitoring cycle #{cycle_num} started across {total_services} service(s) in '{category}'.",
                        category=category,
                        cycle_number=cycle_num,
                    )
                )
                for ev in pending_events:
                    emitted_events.append(
                        self._append_event(
                            event_type=ev["event_type"],
                            service_id=ev["service_id"],
                            service_name=ev["service_name"],
                            epoch_time=now_epoch,
                            previous_health_state=ev["prev"],
                            new_health_state=ev["new"],
                            reason=ev["reason"],
                            category=category,
                            cycle_number=cycle_num,
                        )
                    )
                emitted_events.append(
                    self._append_event(
                        event_type=EVENT_CYCLE_COMPLETED,
                        service_id="SYSTEM",
                        service_name=f"Monitor ({category})",
                        epoch_time=now_epoch,
                        previous_health_state=None,
                        new_health_state=self.status_label,
                        reason=(
                            f"Monitoring cycle #{cycle_num} completed: "
                            f"Healthy={healthy_count}, Degraded={degraded_count}, "
                            f"Unavailable={unavailable_count}, SLA Violations={sla_violating_count}."
                        ),
                        category=category,
                        cycle_number=cycle_num,
                    )
                )

            # 7. Update scheduling metadata
            self.last_run_epoch = now_epoch
            self.last_run_timestamp = now_str
            if self.is_active:
                self.next_expected_epoch = now_epoch + self.config.interval_seconds
                self.next_expected_timestamp = _format_epoch(self.next_expected_epoch)
            else:
                self.next_expected_epoch = None
                self.next_expected_timestamp = None

            result = MonitoringCycleResult(
                cycle_number=cycle_num,
                timestamp=now_str,
                epoch_time=now_epoch,
                status=self.status_label,
                category=category,
                total_services=total_services,
                healthy_count=healthy_count,
                degraded_count=degraded_count,
                unavailable_count=unavailable_count,
                sla_violating_count=sla_violating_count,
                eligible_count=eligible_count,
                selected_service_id=selected_id,
                selected_service_name=selected_name,
                recommendation_result=rec,
                reselection_triggered=reselection_triggered,
                changes_detected=changes_detected,
                service_snapshots=service_snapshots,
                events_emitted=emitted_events,
            )
            self.last_cycle_result = result
            return result

        except Exception as exc:
            logger.exception("Periodic monitoring cycle #%s failed: %s", self.cycle_count, exc)
            err_evt = self._append_event(
                event_type=EVENT_MONITORING_ERROR,
                service_id="SYSTEM",
                service_name="Periodic Monitor",
                epoch_time=now_epoch,
                previous_health_state=None,
                new_health_state="ERROR",
                reason=f"Monitoring cycle failed safely: {exc}",
                category=category,
                cycle_number=self.cycle_count,
            )
            self.last_run_epoch = now_epoch
            self.last_run_timestamp = now_str
            if self.is_active:
                self.next_expected_epoch = now_epoch + self.config.interval_seconds
                self.next_expected_timestamp = _format_epoch(self.next_expected_epoch)

            err_result = MonitoringCycleResult(
                cycle_number=self.cycle_count,
                timestamp=now_str,
                epoch_time=now_epoch,
                status="ERROR",
                category=category,
                total_services=0,
                healthy_count=0,
                degraded_count=0,
                unavailable_count=0,
                sla_violating_count=0,
                eligible_count=0,
                selected_service_id=self._category_selected_id.get(category, previously_selected_id),
                selected_service_name=None,
                recommendation_result=None,
                reselection_triggered=False,
                changes_detected=False,
                service_snapshots={},
                events_emitted=[err_evt],
                error_message=str(exc),
            )
            self.last_cycle_result = err_result
            return err_result

        finally:
            self._cycle_lock.release()

    def get_events_dataframe(self) -> pd.DataFrame:
        """Convert append-only monitoring event history to a Pandas DataFrame for UI display."""
        if not self.event_history:
            return pd.DataFrame()
        rows = [e.to_dict() for e in self.event_history]
        df = pd.DataFrame(rows)
        df.rename(
            columns={
                "sequence_number": "Seq #",
                "timestamp": "Timestamp",
                "event_type": "Event Type",
                "category": "Category",
                "service_id": "Service ID",
                "service_name": "Service Name",
                "previous_health_state": "Previous State",
                "new_health_state": "New State",
                "cycle_number": "Cycle #",
                "reason": "Monitoring Details / Reason",
            },
            inplace=True,
        )
        display_cols = [
            "Seq #",
            "Timestamp",
            "Cycle #",
            "Event Type",
            "Service ID",
            "Service Name",
            "Previous State",
            "New State",
            "Monitoring Details / Reason",
        ]
        existing_cols = [c for c in display_cols if c in df.columns]
        return df[existing_cols]

    def get_status_summary(self) -> Dict[str, Any]:
        """Return compact dictionary describing current monitoring status and timing."""
        res = self.last_cycle_result
        return {
            "status": self.status_label,
            "interval_seconds": self.config.interval_seconds,
            "cycle_count": self.cycle_count,
            "last_run_timestamp": self.last_run_timestamp or "Not yet run",
            "next_expected_timestamp": self.next_expected_timestamp or ("Paused" if not self.is_active else "Pending"),
            "total_services": res.total_services if res else 0,
            "healthy_count": res.healthy_count if res else 0,
            "degraded_count": res.degraded_count if res else 0,
            "unavailable_count": res.unavailable_count if res else 0,
            "sla_violating_count": res.sla_violating_count if res else 0,
            "selected_service_id": res.selected_service_id if res else None,
            "latest_event": self.event_history[-1].to_dict() if self.event_history else None,
        }
