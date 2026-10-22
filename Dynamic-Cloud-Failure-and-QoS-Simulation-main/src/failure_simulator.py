"""Dynamic Failure Simulator for injecting QoS degradation and outages.

This module lets the user inject controlled failures into the synthetic cloud
services to observe how the recommendation engine responds. All failures are
deterministic (not random), so results are reproducible.

Supports deterministic failure events:
- Injecting latency spikes
- Simulating service outages
- Reducing availability
- Restoring individual services to baseline
- Resetting the entire simulation state to baseline

Key Concepts:
    - Failure injection modifies a service's live QoS metrics in place.
    - The service's 'baseline' dictionary is never modified; it serves as the
      restore point so we can undo any failure.
    - Every action is recorded in an event log for audit/display on the dashboard.
"""

from __future__ import annotations
import copy
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from src.service_registry import CloudService, get_default_services


class SimulationEvent:
    """Represents a single logged simulation action and its outcome.

    Every time the user injects a failure, restores a service, or resets the
    simulation, a SimulationEvent is created and appended to the event log.
    The dashboard displays these events in an audit trail table.

    Attributes:
        action: Type of event, e.g. "LATENCY_SPIKE", "SERVICE_OUTAGE",
                "REDUCE_AVAILABILITY", "RESTORE_SERVICE", "RESET_SIMULATION".
        service_id: ID of the service affected, or "ALL" for a full reset.
        service_name: Human-readable name of the affected service.
        details: A descriptive message about what happened (e.g., the old and
                 new latency values).
        timestamp: Time string (HH:MM:SS) when the event occurred.
    """

    def __init__(
        self,
        action: str,
        service_id: str,
        service_name: str,
        details: str,
        timestamp: Optional[str] = None,
    ):
        self.action = action
        self.service_id = service_id
        self.service_name = service_name
        self.details = details
        # Record the current time; allows the dashboard to show when each event happened
        self.timestamp = timestamp or datetime.now().strftime("%H:%M:%S")

    def to_dict(self) -> Dict[str, str]:
        """Convert this event to a dictionary for display in a Pandas DataFrame.

        Returns:
            Dictionary with keys: timestamp, action, service_id, service_name, details.
        """
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "details": self.details,
        }


class FailureSimulator:
    """Manages service states and executes failure simulation actions.

    This class holds the mutable state of all candidate services. It provides
    methods to:
        - Inject a latency spike (increase latency by a specified amount).
        - Simulate a full outage (mark the service as UNAVAILABLE).
        - Reduce availability by a percentage.
        - Restore a single service to its baseline.
        - Reset ALL services back to their original baseline values.

    Each mutation is logged as a SimulationEvent for the audit trail.
    """

    def __init__(self, services: Optional[List[CloudService]] = None):
        """Initialize the simulator with candidate services or fresh defaults.

        Args:
            services: Optional list of CloudService objects to manage. If None,
                      a fresh set of default services is loaded from the registry.

        Side effects:
            Deep-copies each service so that the simulator owns its own instances
            and mutations don't leak back to the caller's list.
        """
        # Dictionary mapping service_id → CloudService for fast lookup
        self.services: Dict[str, CloudService] = {}
        target_services = services if services is not None else get_default_services()
        for s in target_services:
            # Deep copy ensures each service is independently mutable
            self.services[s.service_id] = copy.deepcopy(s)
        # Chronological list of all simulation events (the audit trail)
        self.event_log: List[SimulationEvent] = []

    def get_service(self, service_id: str) -> Optional[CloudService]:
        """Retrieve a service by its unique ID.

        Args:
            service_id: The identifier string (e.g. "SVC-C01").

        Returns:
            The CloudService instance if found, or None if the ID is unknown.
        """
        return self.services.get(service_id)

    def get_all_services(self) -> List[CloudService]:
        """Return a list of all current services managed by the simulator.

        Returns:
            List of CloudService instances (references, not copies).
        """
        return list(self.services.values())

    def get_services_by_category(self, category: str) -> List[CloudService]:
        """Return services belonging to the specified category.

        Args:
            category: Category string to filter by, e.g. "Compute" or "Storage".

        Returns:
            List of CloudService instances matching the given category.
        """
        return [s for s in self.services.values() if s.category == category]

    def inject_latency_spike(
        self,
        service_id: str,
        spike_ms: float = 100.0,
    ) -> Tuple[bool, str]:
        """Increase the latency of a service by a specified number of milliseconds.

        This simulates a network or processing slowdown. The spike is added to
        the service's current latency, so multiple spikes accumulate.

        Ensures latency remains a valid positive number (minimum spike of 1.0ms).

        Args:
            service_id: ID of the service to degrade.
            spike_ms: Additional latency in milliseconds (default 100.0, minimum 1.0).

        Returns:
            Tuple of (success: bool, message: str describing what happened).

        Side effects:
            Modifies the service's latency in place and logs a LATENCY_SPIKE event.
        """
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        old_latency = service.latency
        # Ensure the spike is at least 1.0ms to prevent zero or negative spikes
        spike = max(1.0, float(spike_ms))
        new_latency = round(old_latency + spike, 2)
        # Apply the degraded latency to the live service object
        service.latency = new_latency

        msg = f"Latency spiked by +{spike:.1f}ms (from {old_latency:.1f}ms to {new_latency:.1f}ms)."
        # Record this action in the event log for the audit trail
        self.event_log.append(
            SimulationEvent("LATENCY_SPIKE", service.service_id, service.name, msg)
        )
        return True, msg

    def simulate_outage(self, service_id: str) -> Tuple[bool, str]:
        """Mark a service as UNAVAILABLE, simulating a complete service outage.

        An UNAVAILABLE service is excluded from recommendation even if its
        calculated QoS score would otherwise be the highest. This is the most
        severe failure type in the simulation.

        Args:
            service_id: ID of the service to take offline.

        Returns:
            Tuple of (success: bool, message: str describing the status change).

        Side effects:
            Sets the service's operational_status to "UNAVAILABLE" and logs
            a SERVICE_OUTAGE event.
        """
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        old_status = service.operational_status
        # Mark the service as down — the recommendation engine will skip it
        service.operational_status = "UNAVAILABLE"

        msg = f"Outage triggered. Status changed from {old_status} to UNAVAILABLE."
        self.event_log.append(
            SimulationEvent("SERVICE_OUTAGE", service.service_id, service.name, msg)
        )
        return True, msg

    def reduce_availability(
        self,
        service_id: str,
        reduction_percentage: float = 20.0,
    ) -> Tuple[bool, str]:
        """Lower the availability percentage of a service, clamped to [0.0, 100.0].

        Unlike an outage, reducing availability degrades the service's QoS score
        without making it completely unavailable. The service remains eligible for
        recommendation, but its availability_score will decrease.

        Args:
            service_id: ID of the service to degrade.
            reduction_percentage: How many percentage points to subtract (default 20.0,
                                  minimum 0.1 to prevent no-op reductions).

        Returns:
            Tuple of (success: bool, message: str describing the change).

        Side effects:
            Modifies the service's availability in place and logs a REDUCE_AVAILABILITY event.
        """
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        old_avail = service.availability
        # Ensure the drop is at least 0.1% to prevent meaningless reductions
        drop = max(0.1, float(reduction_percentage))
        # Clamp the result to [0.0, 100.0] — availability cannot go below 0% or above 100%
        new_avail = max(0.0, min(100.0, round(old_avail - drop, 2)))
        service.availability = new_avail

        msg = f"Availability reduced by -{drop:.1f}% (from {old_avail:.2f}% to {new_avail:.2f}%)."
        self.event_log.append(
            SimulationEvent("REDUCE_AVAILABILITY", service.service_id, service.name, msg)
        )
        return True, msg

    def restore_service(self, service_id: str) -> Tuple[bool, str]:
        """Restore a single service back to its baseline QoS and status (idempotent).

        This undoes all failures applied to the service by copying every metric
        and the operational status from its stored baseline dictionary. Calling
        this multiple times in a row has no additional effect (idempotent).

        Args:
            service_id: ID of the service to restore.

        Returns:
            Tuple of (success: bool, message: str confirming the restoration).

        Side effects:
            Resets latency, cost, availability, reliability, and operational_status
            to their baseline values. Logs a RESTORE_SERVICE event.
        """
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        # Copy each metric from the immutable baseline back into the live service
        baseline = service.baseline
        service.latency = baseline["latency"]
        service.cost = baseline["cost"]
        service.availability = baseline["availability"]
        service.reliability = baseline["reliability"]
        service.operational_status = baseline["operational_status"]

        msg = f"Service restored to baseline QoS (Latency: {service.latency}ms, Status: {service.operational_status})."
        self.event_log.append(
            SimulationEvent("RESTORE_SERVICE", service.service_id, service.name, msg)
        )
        return True, msg

    def reset_simulation(self) -> Tuple[bool, str]:
        """Restore all services to baseline state and clear event history (idempotent).

        This is the "nuclear option" — it replaces every service with a fresh copy
        from the registry defaults and clears the event log (replacing it with a
        single RESET_SIMULATION entry). Useful for starting a new demonstration
        from a clean state.

        Returns:
            Tuple of (success: bool, message: str confirming the reset).

        Side effects:
            Replaces self.services with fresh defaults and replaces self.event_log
            with a single reset event.
        """
        # Load a completely new set of services from the static definitions
        default_services = get_default_services()
        self.services = {s.service_id: s for s in default_services}
        # Clear the old event log and record the reset itself
        self.event_log = [
            SimulationEvent(
                "RESET_SIMULATION",
                "ALL",
                "All Services",
                "All candidate services restored to baseline QoS configurations.",
            )
        ]
        return True, "Simulation successfully reset to baseline state."

    def get_event_logs(self) -> List[Dict[str, str]]:
        """Return all logged events as a list of dictionaries.

        The dashboard converts this list into a Pandas DataFrame for display
        in the Simulation Event Audit Log table.

        Returns:
            List of dictionaries, one per event, each with keys: timestamp,
            action, service_id, service_name, details.
        """
        return [e.to_dict() for e in self.event_log]
