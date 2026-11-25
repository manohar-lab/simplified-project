"""
Failure Simulator Module
========================
Implements controlled fault injection, service restoration, and
global simulation reset.  Maintains an event history for auditing.
"""

import copy
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from service_registry import CloudService, get_baseline_services


@dataclass
class SimulationEvent:
    """A single recorded simulation event."""
    event_id: str
    timestamp: str
    service_id: str
    service_name: str
    event_type: str
    previous_state: Dict
    updated_state: Dict
    resulting_recommendation: Optional[str] = None


class FailureSimulator:
    """Manages fault injection, restoration, and event history."""

    # Deterministic injection deltas for reproducible demonstrations
    LATENCY_SPIKE_DELTA: float = 120.0   # ms added
    AVAILABILITY_DROP: float = 15.0      # percentage points removed

    def __init__(self) -> None:
        self.event_history: List[SimulationEvent] = []

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot(svc: CloudService) -> Dict:
        return {
            "latency": svc.latency,
            "cost": svc.cost,
            "availability": svc.availability,
            "reliability": svc.reliability,
            "status": svc.status,
        }

    def _record(self, svc: CloudService, event_type: str,
                prev: Dict, recommendation: Optional[str] = None) -> SimulationEvent:
        evt = SimulationEvent(
            event_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            service_id=svc.service_id,
            service_name=svc.name,
            event_type=event_type,
            previous_state=prev,
            updated_state=self._snapshot(svc),
            resulting_recommendation=recommendation,
        )
        self.event_history.append(evt)
        return evt

    # ------------------------------------------------------------------
    # Fault injection
    # ------------------------------------------------------------------

    def inject_latency_spike(self, service: CloudService,
                             delta: Optional[float] = None) -> SimulationEvent:
        """Add a latency spike to *service*."""
        if service.status == "UNAVAILABLE":
            raise ValueError(f"{service.name} is already unavailable; restore it first.")
        prev = self._snapshot(service)
        service.latency += delta if delta is not None else self.LATENCY_SPIKE_DELTA
        return self._record(service, "LATENCY_SPIKE", prev)

    def degrade_availability(self, service: CloudService,
                             drop: Optional[float] = None) -> SimulationEvent:
        """Reduce availability of *service*."""
        if service.status == "UNAVAILABLE":
            raise ValueError(f"{service.name} is already unavailable; restore it first.")
        prev = self._snapshot(service)
        service.availability = max(0.0, service.availability - (drop or self.AVAILABILITY_DROP))
        return self._record(service, "AVAILABILITY_DEGRADATION", prev)

    def simulate_outage(self, service: CloudService) -> SimulationEvent:
        """Mark *service* as UNAVAILABLE (total outage)."""
        if service.status == "UNAVAILABLE":
            raise ValueError(f"{service.name} is already unavailable.")
        prev = self._snapshot(service)
        service.status = "UNAVAILABLE"
        return self._record(service, "SERVICE_OUTAGE", prev)

    # ------------------------------------------------------------------
    # Restoration
    # ------------------------------------------------------------------

    def restore_service(self, service: CloudService,
                        baselines: List[CloudService]) -> SimulationEvent:
        """Restore *service* to its baseline values."""
        baseline = next((b for b in baselines if b.service_id == service.service_id), None)
        if baseline is None:
            raise ValueError(f"No baseline found for {service.service_id}.")
        prev = self._snapshot(service)
        service.latency = baseline.latency
        service.cost = baseline.cost
        service.availability = baseline.availability
        service.reliability = baseline.reliability
        service.status = "AVAILABLE"
        return self._record(service, "SERVICE_RESTORED", prev)

    def reset_simulation(self, services: List[CloudService],
                         category: str) -> List[SimulationEvent]:
        """Restore ALL services to baseline and clear event history."""
        baselines = get_baseline_services(category)
        events: List[SimulationEvent] = []
        for svc in services:
            baseline = next((b for b in baselines if b.service_id == svc.service_id), None)
            if baseline is None:
                continue
            prev = self._snapshot(svc)
            svc.latency = baseline.latency
            svc.cost = baseline.cost
            svc.availability = baseline.availability
            svc.reliability = baseline.reliability
            svc.status = "AVAILABLE"
            events.append(self._record(svc, "SIMULATION_RESET", prev))
        return events

    def get_history(self) -> List[SimulationEvent]:
        """Return full event history (chronological)."""
        return list(self.event_history)

    def clear_history(self) -> None:
        """Clear event history."""
        self.event_history.clear()
