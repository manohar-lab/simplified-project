"""Performance benchmark script for Phase 9 SQLite Persistence Layer.

Measures:
1. Database initialization and migration time.
2. Service state persistence and retrieval latency.
3. Audit record insertion latency (single and batch).
4. Historical record retrieval latency across 10, 100, and 1,000 records.
5. Query latency with indexing under 1,000+ historical records.
"""

import os
import sys
import tempfile
import time
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.service_registry import get_default_services
from src.database.connection import create_connection
from src.database.migrations import initialize_database
from src.database.repositories import (
    PersistenceManager,
    SimulationEventRepository,
    MonitoringEventRepository,
    ReselectionAuditRepository,
)
from src.failure_simulator import SimulationEvent
from src.monitoring_engine import MonitoringEvent
from src.explainability import ReselectionRecord


def run_persistence_benchmarks() -> Dict[str, Any]:
    """Execute all persistence performance benchmarks and collect exact metrics."""
    results = {}
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        pm = PersistenceManager(db_path)

        # 1. Database Initialization Time
        t0 = time.perf_counter()
        v = pm.initialize()
        t1 = time.perf_counter()
        init_ms = (t1 - t0) * 1000.0
        results["initialization_ms"] = init_ms
        results["schema_version"] = v

        # 2. Service State Write & Retrieval Latency (7 services)
        services = get_default_services()
        t0 = time.perf_counter()
        pm.services.save_all_service_states(services)
        t1 = time.perf_counter()
        save_services_ms = (t1 - t0) * 1000.0
        results["save_services_ms"] = save_services_ms

        t0 = time.perf_counter()
        loaded_states = pm.services.get_all_service_states()
        t1 = time.perf_counter()
        retrieve_services_ms = (t1 - t0) * 1000.0
        results["retrieve_services_ms"] = retrieve_services_ms
        results["total_services_loaded"] = len(loaded_states)

        # 3. Single Record Insertion Latency (100 repetitions)
        single_times = []
        for i in range(100):
            ev = SimulationEvent(
                action="LATENCY_SPIKE",
                service_id="SVC-C01",
                service_name="NovaCompute Standard",
                details=f"Benchmark latency spike iteration {i}",
            )
            t0 = time.perf_counter()
            pm.simulation_events.save_event(ev, injected_latency_change=10.0)
            t1 = time.perf_counter()
            single_times.append((t1 - t0) * 1000.0)
        avg_single_insert_ms = sum(single_times) / len(single_times)
        min_single_insert_ms = min(single_times)
        max_single_insert_ms = max(single_times)
        results["avg_single_insert_ms"] = avg_single_insert_ms
        results["min_single_insert_ms"] = min_single_insert_ms
        results["max_single_insert_ms"] = max_single_insert_ms

        # 4. Scale up to 1,000+ records in batch
        target_count = 1000
        existing = pm.simulation_events.count_events()
        needed = max(0, target_count - existing)

        t0 = time.perf_counter()
        from src.database.connection import transaction
        with transaction(db_path) as conn:
            rows = [
                (
                    "PERF_PROBE",
                    f"SVC-C0{(i % 5) + 1}",
                    f"ComputeService-{(i % 5) + 1}",
                    float(i % 50),
                    0.0,
                    None,
                    None,
                    f"Stress probe {i}",
                    "12:00:00",
                    time.time() + i,
                )
                for i in range(needed)
            ]
            conn.executemany(
                """
                INSERT INTO simulation_events (
                    action, service_id, service_name, injected_latency_change,
                    injected_availability_change, previous_state, resulting_state,
                    details, timestamp, epoch_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
        t1 = time.perf_counter()
        batch_insert_1000_ms = (t1 - t0) * 1000.0
        results["batch_insert_1000_ms"] = batch_insert_1000_ms
        results["total_records_in_db"] = pm.simulation_events.count_events()

        # 5. Retrieval Latency Under 1,000 Records
        # A. Bounded retrieval (limit 10)
        t0 = time.perf_counter()
        recs_10 = pm.simulation_events.get_events(limit=10)
        t1 = time.perf_counter()
        retrieve_10_ms = (t1 - t0) * 1000.0
        results["retrieve_10_under_1000_ms"] = retrieve_10_ms

        # B. Bounded retrieval (limit 100)
        t0 = time.perf_counter()
        recs_100 = pm.simulation_events.get_events(limit=100)
        t1 = time.perf_counter()
        retrieve_100_ms = (t1 - t0) * 1000.0
        results["retrieve_100_under_1000_ms"] = retrieve_100_ms

        # C. Full retrieval (all 1,000 records)
        t0 = time.perf_counter()
        recs_all = pm.simulation_events.get_events(limit=None)
        t1 = time.perf_counter()
        retrieve_all_1000_ms = (t1 - t0) * 1000.0
        results["retrieve_all_1000_ms"] = retrieve_all_1000_ms

        # 6. Reselection Audit Records Insertion (1,000 records)
        with transaction(db_path) as conn:
            rec_rows = [
                (
                    i + 1,
                    "12:00:00",
                    f"Reselection Event {i}",
                    "SVC-C01",
                    "NovaCompute Standard",
                    0.85,
                    "HEALTHY",
                    "SVC-C02",
                    "AetherCompute HighPerf",
                    0.92,
                    "HEALTHY",
                    "SVC-C04",
                    "TitanCompute Enterprise",
                    0.88,
                    "Higher aggregate QoS score",
                    "Candidate outperformed active provider",
                    0.07,
                    -15.0,
                    0.05,
                    0.10,
                    0.02,
                    "SWITCHED",
                    0.07,
                    0.05,
                    0,
                    "AUTOMATIC",
                )
                for i in range(1000)
            ]
            conn.executemany(
                """
                INSERT INTO reselection_records (
                    sequence_number, timestamp, trigger_event, prev_service_id, prev_service_name,
                    prev_qos_score, prev_health_status, new_service_id, new_service_name,
                    new_qos_score, new_health_status, runner_up_id, runner_up_name,
                    runner_up_qos_score, reselection_reason, detailed_explanation,
                    q_diff, lat_diff, avail_diff, rel_diff, cost_diff, decision_type,
                    qos_improvement, hysteresis_threshold, cooldown_active, operating_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rec_rows,
            )

        t0 = time.perf_counter()
        indexed_query = pm.reselection.get_records(limit=100)
        t1 = time.perf_counter()
        reselection_query_100_ms = (t1 - t0) * 1000.0
        results["reselection_query_100_ms"] = reselection_query_100_ms
        results["total_reselection_records"] = pm.reselection.count_records()

    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass
        for ext in ("-wal", "-shm"):
            extra = db_path + ext
            if os.path.exists(extra):
                try:
                    os.remove(extra)
                except OSError:
                    pass

    return results


if __name__ == "__main__":
    print("=" * 70)
    print("DYNAMIC CLOUD FAILURE & QOS RESELECTION — PERSISTENCE BENCHMARK")
    print("=" * 70)
    res = run_persistence_benchmarks()
    print(f"Database Initialization (Schema v{res['schema_version']}): {res['initialization_ms']:.3f} ms")
    print(f"Service States Save (7 services):          {res['save_services_ms']:.3f} ms")
    print(f"Service States Retrieve (7 services):      {res['retrieve_services_ms']:.3f} ms")
    print(f"Single Record Insert (avg over 100):      {res['avg_single_insert_ms']:.3f} ms (min: {res['min_single_insert_ms']:.3f} ms, max: {res['max_single_insert_ms']:.3f} ms)")
    print(f"Batch Insert 1,000 Records:               {res['batch_insert_1000_ms']:.3f} ms (~{1000.0 / (res['batch_insert_1000_ms'] / 1000.0):,.0f} records/sec)")
    print(f"Query 10 Records (from 1,000 total):      {res['retrieve_10_under_1000_ms']:.3f} ms")
    print(f"Query 100 Records (from 1,000 total):     {res['retrieve_100_under_1000_ms']:.3f} ms")
    print(f"Query All 1,000 Records:                  {res['retrieve_all_1000_ms']:.3f} ms")
    print(f"Reselection Records Query (100 of 1,000): {res['reselection_query_100_ms']:.3f} ms")
    print("=" * 70)
