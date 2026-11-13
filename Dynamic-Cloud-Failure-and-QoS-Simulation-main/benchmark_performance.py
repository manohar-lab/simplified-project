"""Phase 5 Performance Audit and Benchmark Script.

Measures:
    1. Initial application startup / import time.
    2. QoS evaluation time (single & batch).
    3. SLA eligibility filtering time.
    4. Hysteresis decision time.
    5. Recommendation generation time (end-to-end).
    6. Monitoring cycle execution time.
    7. Memory consumption (peak tracemalloc allocation).
    8. Scalability benchmarks across synthetic registry sizes (10, 100, 500, 1,000 services).
"""

import time
import tracemalloc
import random
import statistics
import json
from typing import List, Dict, Any

from src.service_registry import CloudService, get_default_services, compute_reference_bounds
from src.qos_evaluator import QoSEvaluator, DEFAULT_WEIGHTS
from src.sla_config import SLAConfig, get_default_sla_config, validate_service_sla
from src.hysteresis_config import HysteresisConfig
from src.monitoring_config import MonitoringConfig
from src.monitoring_engine import MonitoringEngine
from src.recommendation_engine import RecommendationEngine
from src.override_manager import ManualOverrideManager


def _generate_synthetic_services(count: int, category: str = "Compute") -> List[CloudService]:
    """Generate deterministic synthetic services for scalability benchmarking."""
    random.seed(42)
    services = []
    for i in range(count):
        sid = f"SVC-BENCH-{i:05d}"
        sname = f"Benchmark Cloud Node {i}"
        lat = round(random.uniform(15.0, 180.0), 2)
        cost = round(random.uniform(0.01, 0.15), 4)
        avail = round(random.uniform(97.0, 99.99), 2)
        rel = round(random.uniform(96.0, 99.95), 2)
        base_dict = {
            "latency": lat,
            "cost": cost,
            "availability": avail,
            "reliability": rel,
            "operational_status": "AVAILABLE",
        }
        services.append(
            CloudService(
                service_id=sid,
                name=sname,
                category=category,
                latency=lat,
                cost=cost,
                availability=avail,
                reliability=rel,
                operational_status="AVAILABLE",
                baseline=base_dict,
            )
        )
    return services


def run_performance_benchmarks():
    results: Dict[str, Any] = {}

    evaluator = QoSEvaluator()
    engine = RecommendationEngine(evaluator)
    sla = get_default_sla_config("Compute")
    hyst = HysteresisConfig(min_qos_delta=0.05, cooldown_steps=0)
    default_svcs = get_default_services()

    # 0. Startup & Dashboard Responsiveness Time
    import subprocess
    import sys

    # Measure raw module import startup
    t_start0 = time.perf_counter()
    subprocess.run([sys.executable, "-c", "import src; import app"], capture_output=True)
    t_start1 = time.perf_counter()
    results["module_import_startup_seconds"] = round(t_start1 - t_start0, 3)

    # Measure Streamlit AppTest launch & initial render latency
    from streamlit.testing.v1 import AppTest
    t_app0 = time.perf_counter()
    at = AppTest.from_file("app.py", default_timeout=20)
    at.run()
    t_app1 = time.perf_counter()
    results["dashboard_initial_render_latency_seconds"] = round(t_app1 - t_app0, 3)

    # 1. SLA Eligibility Filtering Time (100 iterations)
    sla_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        for s in default_svcs:
            validate_service_sla(s, sla)
        t1 = time.perf_counter()
        sla_times.append((t1 - t0) * 1000)  # ms

    results["sla_filtering_10_services_ms"] = {
        "mean": round(statistics.mean(sla_times), 4),
        "min": round(min(sla_times), 4),
        "max": round(max(sla_times), 4),
        "stdev": round(statistics.stdev(sla_times), 4),
    }

    # 2. QoS Evaluation Time (100 iterations)
    qos_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        evaluator.evaluate_all(default_svcs, DEFAULT_WEIGHTS)
        t1 = time.perf_counter()
        qos_times.append((t1 - t0) * 1000)

    results["qos_evaluation_10_services_ms"] = {
        "mean": round(statistics.mean(qos_times), 4),
        "min": round(min(qos_times), 4),
        "max": round(max(qos_times), 4),
        "stdev": round(statistics.stdev(qos_times), 4),
    }

    # 3. Recommendation Generation Time (End-to-End, 100 iterations)
    rec_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        engine.recommend(
            default_svcs,
            category="Compute",
            weights=DEFAULT_WEIGHTS,
            sla_config=sla,
            hysteresis_config=hyst,
            previously_selected_id="SVC-C01",
        )
        t1 = time.perf_counter()
        rec_times.append((t1 - t0) * 1000)

    results["recommendation_e2e_10_services_ms"] = {
        "mean": round(statistics.mean(rec_times), 4),
        "min": round(min(rec_times), 4),
        "max": round(max(rec_times), 4),
        "stdev": round(statistics.stdev(rec_times), 4),
    }

    # 3b. Hysteresis Decision Logic in isolation (1000 iterations)
    from src.hysteresis_config import check_cooldown_active
    hyst_times = []
    for _ in range(1000):
        t0 = time.perf_counter()
        is_cd, _ = check_cooldown_active(hyst, current_step=5, last_switch_step=2)
        diff = round(0.8500 - 0.8100, 4)
        decision = "SWITCHED" if diff > hyst.min_qos_delta and not is_cd else "RETAINED"
        t1 = time.perf_counter()
        hyst_times.append((t1 - t0) * 1000)

    results["hysteresis_decision_isolated_ms"] = {
        "mean": round(statistics.mean(hyst_times), 5),
        "min": round(min(hyst_times), 5),
        "max": round(max(hyst_times), 5),
        "stdev": round(statistics.stdev(hyst_times), 5),
    }

    # 4. Monitoring Cycle Execution Time (100 iterations)
    mon = MonitoringEngine(evaluator=evaluator, recommendation_engine=engine)
    mon_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        mon.run_cycle(
            default_svcs,
            category="Compute",
            weights=DEFAULT_WEIGHTS,
            sla_config=sla,
            hysteresis_config=hyst,
            previously_selected_id="SVC-C01",
            force=True,
            respect_interval=False,
        )
        t1 = time.perf_counter()
        mon_times.append((t1 - t0) * 1000)

    results["monitoring_cycle_10_services_ms"] = {
        "mean": round(statistics.mean(mon_times), 4),
        "min": round(min(mon_times), 4),
        "max": round(max(mon_times), 4),
        "stdev": round(statistics.stdev(mon_times), 4),
    }

    # 5. Scalability Benchmarks (10, 100, 500, 1000 services)
    scalability_results = {}
    for size in (10, 100, 500, 1000):
        svcs = _generate_synthetic_services(size)
        tracemalloc.start()
        t0 = time.perf_counter()

        # Run 20 recommendation passes
        for _ in range(20):
            engine.recommend(
                svcs,
                category="Compute",
                weights=DEFAULT_WEIGHTS,
                sla_config=sla,
                hysteresis_config=hyst,
                previously_selected_id=svcs[0].service_id,
            )

        t1 = time.perf_counter()
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        avg_ms = ((t1 - t0) / 20) * 1000
        throughput = size / ((t1 - t0) / 20)
        scalability_results[f"registry_size_{size}"] = {
            "services_count": size,
            "avg_recommendation_latency_ms": round(avg_ms, 3),
            "throughput_services_per_second": round(throughput, 1),
            "peak_memory_kb": round(peak_mem / 1024, 2),
        }

    results["scalability_benchmarks"] = scalability_results

    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run_performance_benchmarks()
