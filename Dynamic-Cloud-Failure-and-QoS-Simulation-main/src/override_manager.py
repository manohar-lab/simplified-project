"""Operating mode management and validated manual service override backend.

Supports two explicit operating modes:
    - AUTOMATIC: RecommendationEngine selects the best SLA-compliant service
      using QoS scoring, strict SLA eligibility, and Phase 2 hysteresis.
    - MANUAL_OVERRIDE: An operator explicitly selects an eligible service from
      the active category while monitoring and hard SLA/availability safety
      rules remain continuously enforced.

Manual selection NEVER bypasses operational status ("AVAILABLE") or configured
hard SLA constraints. Any unavailable or SLA-violating state triggers immediate
override termination and emergency automatic reselection.
"""

from __future__ import annotations
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from src.service_registry import CloudService
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla

logger = logging.getLogger(__name__)


# =========================================================================
# Operating Mode & Override Event Constants
# =========================================================================
MODE_AUTOMATIC = "AUTOMATIC"
MODE_MANUAL = "MANUAL_OVERRIDE"

OVERRIDE_EVENT_ACTIVATED = "MANUAL_OVERRIDE_ACTIVATED"
OVERRIDE_EVENT_CLEARED = "MANUAL_OVERRIDE_CLEARED"
OVERRIDE_EVENT_REJECTED = "MANUAL_OVERRIDE_REJECTED"
OVERRIDE_EVENT_EMERGENCY_TERMINATED = "MANUAL_OVERRIDE_EMERGENCY_TERMINATED"
OVERRIDE_EVENT_AUTO_RESTORED = "AUTOMATIC_MODE_RESTORED"


def _format_epoch(epoch: Optional[float]) -> str:
    """Format an epoch timestamp safely across platforms and small synthetic clocks."""
    if epoch is None:
        return datetime.now().strftime("%H:%M:%S")
    try:
        return datetime.fromtimestamp(epoch).strftime("%H:%M:%S")
    except (OSError, ValueError, OverflowError):
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%H:%M:%S")


@dataclass
class OverrideValidationResult:
    """Outcome of validating a manual service override request against backend safety rules."""
    is_valid: bool
    requested_service_id: str
    category: str
    service: Optional[CloudService]
    rejection_reason: str = ""
    sla_violations: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.sla_violations is None:
            self.sla_violations = []


@dataclass
class OverrideTransitionEvent:
    """Append-only audit record for operating mode & manual override lifecycle events."""
    sequence_number: int
    timestamp: str
    epoch_time: float
    event_type: str
    operating_mode: str
    requested_service_id: Optional[str]
    selected_service_id: Optional[str]
    category: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize transition event to a dictionary."""
        return asdict(self)


def validate_manual_override_request(
    services: List[CloudService],
    category: str,
    requested_service_id: Optional[str],
    sla_config: Optional[SLAConfig] = None,
) -> OverrideValidationResult:
    """Strictly validate a manual service override request in the backend.

    Enforces all Phase 4 manual override safety rules:
        1. Requested service ID must be non-empty and exist in the service registry.
        2. Requested service must belong to the currently selected category.
        3. Requested service must be operationally AVAILABLE (not UNAVAILABLE).
        4. Requested service must satisfy every configured hard SLA threshold.

    Args:
        services: Current registered services list.
        category: Currently active service category (e.g., "Compute").
        requested_service_id: Service ID requested by the user/caller.
        sla_config: Active SLAConfig. Defaults to category default SLA if omitted.

    Returns:
        OverrideValidationResult describing eligibility or exact rejection reason.
    """
    req_id = "" if requested_service_id is None else str(requested_service_id).strip()
    if not req_id:
        return OverrideValidationResult(
            is_valid=False,
            requested_service_id=req_id,
            category=category,
            service=None,
            rejection_reason="Rejected: requested service ID is empty or missing.",
        )

    service = next((s for s in services if s.service_id == req_id), None)
    if service is None:
        return OverrideValidationResult(
            is_valid=False,
            requested_service_id=req_id,
            category=category,
            service=None,
            rejection_reason=f"Rejected: service '{req_id}' does not exist in the service registry.",
        )

    if service.category != category:
        return OverrideValidationResult(
            is_valid=False,
            requested_service_id=req_id,
            category=category,
            service=service,
            rejection_reason=(
                f"Rejected: service '{service.name}' ({req_id}) belongs to category '{service.category}', "
                f"not the active category '{category}'."
            ),
        )

    if getattr(service, "operational_status", "UNAVAILABLE") != "AVAILABLE":
        return OverrideValidationResult(
            is_valid=False,
            requested_service_id=req_id,
            category=category,
            service=service,
            rejection_reason=(
                f"Rejected: service '{service.name}' ({req_id}) is currently UNAVAILABLE and cannot be manually selected."
            ),
        )

    effective_sla = sla_config if sla_config is not None else get_default_sla_config(category)
    violations = validate_service_sla(service, effective_sla)
    if violations:
        return OverrideValidationResult(
            is_valid=False,
            requested_service_id=req_id,
            category=category,
            service=service,
            rejection_reason=(
                f"Rejected: service '{service.name}' ({req_id}) violates hard SLA constraints: "
                f"{'; '.join(violations)}"
            ),
            sla_violations=list(violations),
        )

    return OverrideValidationResult(
        is_valid=True,
        requested_service_id=req_id,
        category=category,
        service=service,
        rejection_reason="",
        sla_violations=[],
    )


class ManualOverrideManager:
    """Manages operating mode state (Automatic vs Manual Override) and transition audit logs."""

    def __init__(self, time_fn: Optional[Callable[[], float]] = None):
        """Initialize operating mode manager in AUTOMATIC mode."""
        self.time_fn: Callable[[], float] = time_fn if time_fn is not None else time.time
        self.mode: str = MODE_AUTOMATIC
        self.requested_service_id: Optional[str] = None
        self.category: Optional[str] = None
        self.reason: str = ""
        self.activated_at: Optional[str] = None
        self.last_rejection_reason: Optional[str] = None
        self.last_termination_notice: Optional[str] = None
        self.event_history: List[OverrideTransitionEvent] = []

    @property
    def is_manual_active(self) -> bool:
        """Return True when Manual Override mode holds an active requested service."""
        return self.mode == MODE_MANUAL and self.requested_service_id is not None

    def _append_event(
        self,
        event_type: str,
        operating_mode: str,
        requested_service_id: Optional[str],
        selected_service_id: Optional[str],
        category: str,
        reason: str,
    ) -> OverrideTransitionEvent:
        now_epoch = float(self.time_fn())
        evt = OverrideTransitionEvent(
            sequence_number=len(self.event_history) + 1,
            timestamp=_format_epoch(now_epoch),
            epoch_time=now_epoch,
            event_type=event_type,
            operating_mode=operating_mode,
            requested_service_id=requested_service_id,
            selected_service_id=selected_service_id,
            category=category,
            reason=reason,
        )
        self.event_history.append(evt)
        return evt

    def request_manual_override(
        self,
        services: List[CloudService],
        category: str,
        requested_service_id: Optional[str],
        sla_config: Optional[SLAConfig] = None,
        reason: str = "",
    ) -> Tuple[bool, str, OverrideValidationResult]:
        """Validate and activate a manual service override request.

        If validation fails, operating mode and prior override selection remain
        unchanged (no silent mode switch), and a MANUAL_OVERRIDE_REJECTED event is logged.
        """
        validation = validate_manual_override_request(
            services=services,
            category=category,
            requested_service_id=requested_service_id,
            sla_config=sla_config,
        )
        clean_reason = reason.strip() if reason else "Explicit operator manual override"

        if not validation.is_valid:
            self.last_rejection_reason = validation.rejection_reason
            self._append_event(
                event_type=OVERRIDE_EVENT_REJECTED,
                operating_mode=self.mode,
                requested_service_id=validation.requested_service_id or None,
                selected_service_id=self.requested_service_id,
                category=category,
                reason=validation.rejection_reason,
            )
            return False, validation.rejection_reason, validation

        assert validation.service is not None
        svc = validation.service

        # Idempotent guard: avoid duplicate audit events if identical manual override is already active
        if (
            self.mode == MODE_MANUAL
            and self.requested_service_id == svc.service_id
            and self.category == category
            and self.reason == clean_reason
        ):
            self.last_rejection_reason = None
            return True, f"Manual override already active on '{svc.name}' ({svc.service_id}).", validation

        now_epoch = float(self.time_fn())
        self.mode = MODE_MANUAL
        self.requested_service_id = svc.service_id
        self.category = category
        self.reason = clean_reason
        self.activated_at = _format_epoch(now_epoch)
        self.last_rejection_reason = None
        self.last_termination_notice = None

        msg = (
            f"Manual override activated for '{svc.name}' ({svc.service_id}) in category '{category}'. "
            f"Reason: {clean_reason}"
        )
        self._append_event(
            event_type=OVERRIDE_EVENT_ACTIVATED,
            operating_mode=MODE_MANUAL,
            requested_service_id=svc.service_id,
            selected_service_id=svc.service_id,
            category=category,
            reason=msg,
        )
        return True, msg, validation

    def clear_override(
        self,
        reason: str = "Manual override cleared by operator; automatic mode restored.",
    ) -> bool:
        """Clear active manual override and return control to Automatic Mode cleanly (idempotent)."""
        if self.mode == MODE_AUTOMATIC and self.requested_service_id is None:
            return False

        prev_id = self.requested_service_id
        prev_cat = self.category or ""

        self._append_event(
            event_type=OVERRIDE_EVENT_CLEARED,
            operating_mode=MODE_AUTOMATIC,
            requested_service_id=prev_id,
            selected_service_id=None,
            category=prev_cat,
            reason=reason,
        )
        self._append_event(
            event_type=OVERRIDE_EVENT_AUTO_RESTORED,
            operating_mode=MODE_AUTOMATIC,
            requested_service_id=None,
            selected_service_id=None,
            category=prev_cat,
            reason=f"Operating mode returned to {MODE_AUTOMATIC} after clearing override on {prev_id}.",
        )

        self.mode = MODE_AUTOMATIC
        self.requested_service_id = None
        self.category = None
        self.reason = ""
        self.activated_at = None
        self.last_rejection_reason = None
        return True

    def handle_emergency_termination(
        self,
        failed_service_id: Optional[str],
        replacement_service_id: Optional[str],
        reason: str,
        category: str = "",
    ) -> bool:
        """Terminate an unsafe manual override immediately following outage or SLA violation."""
        if self.mode != MODE_MANUAL and self.requested_service_id is None:
            return False

        target_id = failed_service_id or self.requested_service_id
        eff_cat = category or self.category or ""

        self._append_event(
            event_type=OVERRIDE_EVENT_EMERGENCY_TERMINATED,
            operating_mode=MODE_AUTOMATIC,
            requested_service_id=target_id,
            selected_service_id=replacement_service_id,
            category=eff_cat,
            reason=reason,
        )
        self._append_event(
            event_type=OVERRIDE_EVENT_AUTO_RESTORED,
            operating_mode=MODE_AUTOMATIC,
            requested_service_id=target_id,
            selected_service_id=replacement_service_id,
            category=eff_cat,
            reason=(
                f"Automatic mode restored following emergency termination of '{target_id}'. "
                + (f"Replacement service selected: '{replacement_service_id}'." if replacement_service_id else "No eligible replacement service available.")
            ),
        )

        self.mode = MODE_AUTOMATIC
        self.requested_service_id = None
        self.category = None
        self.reason = ""
        self.activated_at = None
        self.last_rejection_reason = None
        self.last_termination_notice = reason
        return True

    def clear_events(self) -> None:
        """Clear manual override event history."""
        self.event_history.clear()

    def reset(self, clear_events: bool = False) -> None:
        """Reset operating mode state to AUTOMATIC."""
        self.mode = MODE_AUTOMATIC
        self.requested_service_id = None
        self.category = None
        self.reason = ""
        self.activated_at = None
        self.last_rejection_reason = None
        self.last_termination_notice = None
        if clear_events:
            self.event_history.clear()

    def get_events_dataframe(self) -> pd.DataFrame:
        """Convert override lifecycle history to a clean DataFrame for dashboard display."""
        if not self.event_history:
            return pd.DataFrame()
        df = pd.DataFrame([e.to_dict() for e in self.event_history])
        df.rename(
            columns={
                "sequence_number": "Seq #",
                "timestamp": "Timestamp",
                "event_type": "Event Type",
                "operating_mode": "Operating Mode",
                "category": "Category",
                "requested_service_id": "Requested Service",
                "selected_service_id": "Selected Service",
                "reason": "Transition Details / Reason",
            },
            inplace=True,
        )
        cols = [
            "Seq #",
            "Timestamp",
            "Event Type",
            "Operating Mode",
            "Category",
            "Requested Service",
            "Selected Service",
            "Transition Details / Reason",
        ]
        return df[[c for c in cols if c in df.columns]]

