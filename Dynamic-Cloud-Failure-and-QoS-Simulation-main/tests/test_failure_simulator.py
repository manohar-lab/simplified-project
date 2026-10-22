"""Unit tests for the Dynamic Failure Simulator.

These tests verify that each failure injection method (latency spike, outage,
availability reduction) correctly modifies the target service, that restoration
returns services to their exact baseline values, and that repeated operations
do not cause cumulative drift or corruption of service state.
"""

import pytest
from src.failure_simulator import FailureSimulator
from src.service_registry import get_default_services


def test_latency_spike():
    """Verify latency injection increases latency and remains positive.

    Test strategy:
        - Start with a fresh simulator and record SVC-C01's initial latency.
        - Inject a +150ms spike and confirm the new latency equals initial + 150.
        - Confirm the latency is still positive (sanity check).
        - Confirm exactly one event was logged with the correct action and service_id.
    """
    sim = FailureSimulator()
    target_id = "SVC-C01"
    svc = sim.get_service(target_id)
    initial_latency = svc.latency

    # Inject a 150ms latency spike on SVC-C01
    success, msg = sim.inject_latency_spike(target_id, spike_ms=150.0)
    assert success is True
    # The new latency should be exactly the old value plus the spike amount
    assert svc.latency == initial_latency + 150.0
    # Latency must always be a positive value
    assert svc.latency > 0

    # Verify that the event was logged correctly
    logs = sim.get_event_logs()
    assert len(logs) == 1
    assert logs[0]["action"] == "LATENCY_SPIKE"
    assert logs[0]["service_id"] == target_id


def test_simulate_outage():
    """Verify simulating outage marks service UNAVAILABLE.

    Test strategy:
        - Confirm SVC-C02 starts as AVAILABLE.
        - Simulate an outage and confirm its status becomes UNAVAILABLE.
        - Confirm a SERVICE_OUTAGE event was logged for SVC-C02.
    """
    sim = FailureSimulator()
    target_id = "SVC-C02"
    svc = sim.get_service(target_id)
    # Pre-condition: service starts in AVAILABLE state
    assert svc.operational_status == "AVAILABLE"

    # Simulate a complete outage on SVC-C02
    success, msg = sim.simulate_outage(target_id)
    assert success is True
    # Post-condition: service is now UNAVAILABLE
    assert svc.operational_status == "UNAVAILABLE"

    # Verify the outage event appears in the audit log
    logs = sim.get_event_logs()
    assert any(log["action"] == "SERVICE_OUTAGE" and log["service_id"] == target_id for log in logs)


def test_reduce_availability_and_bounds():
    """Verify availability reduction is clamped to [0.0, 100.0].

    Test strategy:
        - Reduce SVC-C03's availability by 20% and confirm the exact result.
        - Then reduce by 150% (more than what remains) and confirm clamping to 0.0.
        This ensures the code never produces negative availability values.
    """
    sim = FailureSimulator()
    target_id = "SVC-C03"
    svc = sim.get_service(target_id)
    initial_avail = svc.availability

    # Step 1: Normal reduction — subtract 20 percentage points
    success, _ = sim.reduce_availability(target_id, reduction_percentage=20.0)
    assert success is True
    assert pytest.approx(svc.availability) == initial_avail - 20.0

    # Step 2: Severe reduction that exceeds remaining availability.
    # After Step 1, availability is ~78.8%. Reducing by 150% should clamp to 0.0.
    success, _ = sim.reduce_availability(target_id, reduction_percentage=150.0)
    assert success is True
    assert svc.availability == 0.0  # Clamped to 0.0


def test_restore_service_idempotence():
    """Verify restoring a modified service returns it to baseline QoS (idempotent).

    Test strategy:
        - Degrade SVC-C01 with a latency spike AND an outage.
        - Restore it and confirm all metrics match the baseline.
        - Restore it AGAIN (already at baseline) and confirm nothing changes.
        This proves the restore operation is safe to call repeatedly (idempotent).
    """
    sim = FailureSimulator()
    target_id = "SVC-C01"
    svc = sim.get_service(target_id)
    baseline_latency = svc.baseline["latency"]
    baseline_status = svc.baseline["operational_status"]

    # Degrade the service: add latency spike and simulate outage
    sim.inject_latency_spike(target_id, 200.0)
    sim.simulate_outage(target_id)
    # Confirm the service is now degraded
    assert svc.latency != baseline_latency
    assert svc.operational_status == "UNAVAILABLE"

    # First restore — should return to baseline
    success1, _ = sim.restore_service(target_id)
    assert success1 is True
    assert svc.latency == baseline_latency
    assert svc.operational_status == baseline_status

    # Second restore (idempotent) — should still be at baseline
    success2, _ = sim.restore_service(target_id)
    assert success2 is True
    assert svc.latency == baseline_latency
    assert svc.operational_status == baseline_status


def test_reset_simulation_idempotence():
    """Verify resetting restores all services to pristine state (idempotent).

    Test strategy:
        - Modify multiple services with different failure types.
        - Reset the simulation and confirm every service is back to baseline.
        - Reset again (idempotent) and confirm values are still at baseline.
    """
    sim = FailureSimulator()
    # Modify multiple services with different failure types
    sim.simulate_outage("SVC-C01")
    sim.inject_latency_spike("SVC-C02", 300.0)
    sim.reduce_availability("SVC-C03", 50.0)

    # First reset — all services should return to their original baseline values
    sim.reset_simulation()
    for s in sim.get_all_services():
        assert s.operational_status == "AVAILABLE"
        assert s.latency == s.baseline["latency"]
        assert s.availability == s.baseline["availability"]

    # Second reset (idempotent) — values should remain unchanged
    sim.reset_simulation()
    for s in sim.get_all_services():
        assert s.operational_status == "AVAILABLE"
        assert s.latency == s.baseline["latency"]


def test_repeated_actions_do_not_accumulate_drift():
    """Verify that repeatedly restoring and resetting maintains pristine values without drift.

    Test strategy:
        - Run a cycle of (degrade → restore → check baseline) 5 times on one service.
        - Then run 3 full simulation resets and verify every service each time.
        This catches subtle bugs like floating-point accumulation or stale references
        that might cause values to drift slightly after many operations.
    """
    sim = FailureSimulator()
    target_id = "SVC-C01"

    # Repeatedly modify, restore, and verify the service stays at baseline
    for _ in range(5):
        sim.inject_latency_spike(target_id, 50.0)
        sim.reduce_availability(target_id, 10.0)
        sim.restore_service(target_id)
        svc = sim.get_service(target_id)
        # After each restore, ALL metrics must exactly match the baseline
        assert svc.latency == svc.baseline["latency"]
        assert svc.availability == svc.baseline["availability"]
        assert svc.operational_status == svc.baseline["operational_status"]

    # Repeated full resets — verify every service, every metric
    for _ in range(3):
        sim.reset_simulation()
        for s in sim.get_all_services():
            assert s.latency == s.baseline["latency"]
            assert s.cost == s.baseline["cost"]
            assert s.availability == s.baseline["availability"]
            assert s.reliability == s.baseline["reliability"]
            assert s.operational_status == s.baseline["operational_status"]
