# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
## Major Project Demonstration Prototype (Phases 1–5 Complete)

Inspired by the IEEE ICIMIA-2025 paper, *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*.

---

## 1. Project Overview
Modern cloud applications depend on distributed services and third-party APIs. In real-world environments, candidate services experience latency spikes, reduced availability, transient unreliability, or total outages. 

**Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** is an end-to-end Python prototype designed to evaluate candidate cloud services using multi-attribute Quality of Service (QoS) parameters, enforce strict hard Service Level Agreement (SLA) constraints, mitigate service flapping via hysteresis and cooldown thresholds, autonomously monitor service health, support authorized manual service overrides with failover safety, and present explainable reselection decisions in an interactive Streamlit dashboard.

The application runs deterministically on synthetic cloud candidate registries with complete decision explainability and chronological audit logs.

---

## 2. Implemented Capabilities and System Architecture

### Implemented Core Capabilities
1. **Multi-Attribute QoS Evaluation:** Weighted normalization across latency (ms, lower-is-better), invocation cost (currency, lower-is-better), availability (%, higher-is-better), and reliability (%, higher-is-better) with baseline reference bounds.
2. **Phase 1 — Strict Hard SLA Filtering:** Centralized SLA configuration (`SLAConfig`) enforcing maximum latency, minimum availability, and minimum reliability thresholds. Services violating any threshold are disqualified regardless of aggregate score.
3. **Phase 2 — Anti-Flapping Hysteresis & Cooldown:** Centralized hysteresis configuration (`HysteresisConfig`) requiring candidate QoS improvement to exceed a configurable delta (`min_qos_delta`) before switching, with optional step-based and temporal cooldown periods. Outages and SLA violations immediately trigger emergency reselection, bypassing cooldown.
4. **Phase 3 — Periodic Automatic Monitoring Engine:** Background-capable, non-blocking monitoring engine (`MonitoringEngine`) that reassesses candidate services at configurable intervals, classifies health states (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `RECOVERED`), detects outages/SLA violations, and emits deduplicated event logs.
5. **Phase 4 — Validated Manual Service Override:** Two distinct operating modes (`AUTOMATIC` vs. `MANUAL_OVERRIDE`) managed by `ManualOverrideManager`. Manual selection strictly validates candidate existence, category match, availability, and SLA compliance. In the event of an outage or SLA violation on a manually overridden service, the system immediately terminates the override and performs emergency failover to the best eligible automatic service.
6. **Decision Explainability & Audit Trail:** Full mathematical breakdown of selection reasons, multi-candidate comparison tables, runner-up score margins, and low-level audit trail dataframes.

### Repository Architecture
```text
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py                     # Streamlit interactive dashboard with operating mode & monitoring panels
├── benchmark_performance.py   # Performance profiling and scalability benchmark script
├── requirements.txt           # Core runtime dependencies
├── README.md                  # System documentation and audit report
├── src/
│   ├── __init__.py            # Package root exporting core modules (v1.4.0)
│   ├── service_registry.py    # CloudService dataclass and synthetic baseline registries
│   ├── qos_evaluator.py       # Bound normalization and weighted QoS score calculation
│   ├── sla_config.py          # Centralized SLA thresholds and constraint validation (Phase 1)
│   ├── hysteresis_config.py   # Hysteresis switching threshold and cooldown logic (Phase 2)
│   ├── monitoring_config.py   # Periodic monitoring configuration (Phase 3)
│   ├── monitoring_engine.py   # Periodic health reassessment & event logging engine (Phase 3)
│   ├── override_manager.py    # Operating mode management & override validation (Phase 4)
│   ├── failure_simulator.py   # Fault injection (latency, availability, outage) and baseline restore
│   ├── recommendation_engine.py # Multi-stage SLA, hysteresis, and override recommendation pipeline
│   ├── analytics.py           # Health classification, history tracking, and snapshot builders
│   └── explainability.py      # Candidate comparison tables, explanations, and audit trail
└── tests/
    ├── test_qos_evaluator.py          # QoS normalization and scoring unit tests (9 tests)
    ├── test_failure_simulator.py      # Fault injection and restoration unit tests (6 tests)
    ├── test_recommendation_engine.py  # Basic recommendation engine unit tests (6 tests)
    ├── test_sla_eligibility.py        # Strict SLA filtering & edge-case unit tests (14 tests)
    ├── test_hysteresis.py             # Hysteresis delta & cooldown unit tests (15 tests)
    ├── test_monitoring.py             # Monitoring lifecycle & cycle execution tests (17 tests)
    ├── test_manual_override.py        # Manual override validation & failover tests (15 tests)
    ├── test_explainability.py         # Explainability and comparison table tests (5 tests)
    ├── test_analytics.py              # Health analytics & history tracker tests (3 tests)
    ├── test_ui_dashboard.py           # Streamlit AppTest dashboard automation tests (12 tests)
    ├── test_e2e_integration_scenarios.py # End-to-end integration scenarios A–G (7 tests)
    └── test_reliability_edge_cases.py    # Reliability and boundary edge-case tests (13 tests)
```

---

## 3. Technology Stack
- **Language:** Python (3.10+)
- **Interactive UI:** Streamlit
- **Data Structures & Processing:** Pandas, NumPy
- **Interactive Visualizations:** Plotly Graph Objects & Plotly Express
- **Test Automation:** Pytest, `streamlit.testing.v1.AppTest`
- **Memory Profiling & Timing:** `tracemalloc`, Python `time.perf_counter`

---

## 4. Installation and Setup

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- PowerShell, Bash, or Command Prompt

### Virtual Environment Setup
```powershell
# Navigate to the project directory
cd Dynamic-Cloud-Failure-and-QoS-Simulation-main

# Create virtual environment
python -m venv .venv

# Activate virtual environment (PowerShell)
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 5. Running the Application & Test Suite

### Running the Streamlit Dashboard
```powershell
python -m streamlit run app.py
```
Open the local URL in a web browser (default: `http://localhost:8501`).

### Running the Complete Automated Test Suite
```powershell
python -m pytest tests -v
```
All **122 tests** run deterministically in approximately 15–25 seconds without external server dependencies.

### Running Performance Benchmarks
```powershell
python benchmark_performance.py
```

---

## 6. Documented Test Status (Phase 5 Verification)
The automated test suite contains **122 tests** across 12 test modules, all passing:
- `tests/test_qos_evaluator.py`: 9 passed
- `tests/test_failure_simulator.py`: 6 passed
- `tests/test_recommendation_engine.py`: 6 passed
- `tests/test_sla_eligibility.py`: 14 passed
- `tests/test_hysteresis.py`: 15 passed
- `tests/test_monitoring.py`: 17 passed
- `tests/test_manual_override.py`: 15 passed
- `tests/test_explainability.py`: 5 passed
- `tests/test_analytics.py`: 3 passed
- `tests/test_ui_dashboard.py`: 12 passed
- `tests/test_e2e_integration_scenarios.py`: 7 passed
- `tests/test_reliability_edge_cases.py`: 13 passed
**Result:** **122 passed, 0 failed, 0 skipped**.

---

## 7. Performance Benchmarks
Measured via `time.perf_counter()` and `tracemalloc` across 100 repeated cycles (Python 3.14 64-bit on Windows 11):
- **SLA Eligibility Filtering Latency (10 services):** Mean: `0.016 ms` | Min: `0.008 ms`
- **QoS Score Evaluation Latency (10 services):** Mean: `0.150 ms` | Min: `0.082 ms`
- **Hysteresis Decision Evaluation (isolated):** Mean: `0.0015 ms`
- **End-to-End Recommendation Pipeline (10 services):** Mean: `0.186 ms` | Min: `0.083 ms`
- **Periodic Monitoring Full Cycle (10 services):** Mean: `0.380 ms` | Min: `0.212 ms`
- **Dashboard Initial Render (via AppTest):** `~2.89 seconds`
- **Scalability Throughput:**
  - 10 services: `0.996 ms` avg latency | ~10,037 services/sec throughput | Peak RAM: `6.26 KB`
  - 100 services: `6.226 ms` avg latency | ~16,061 services/sec throughput | Peak RAM: `29.01 KB`
  - 500 services: `32.533 ms` avg latency | ~15,369 services/sec throughput | Peak RAM: `137.21 KB`
  - 1,000 services: `66.613 ms` avg latency | ~15,012 services/sec throughput | Peak RAM: `243.00 KB`

---

## 8. Synthetic Data & Research Disclaimer
1. **Synthetic Simulation:** All registered cloud services (e.g., NovaCompute Standard, AetherCompute HighPerf, TitanCompute Enterprise), QoS measurements, and failure events are synthetically generated for academic simulation and evaluation.
2. **No Live Cloud APIs:** This prototype does not connect to live commercial cloud infrastructure (AWS, Azure, GCP), issue billing requests, or manage real virtual machines/containers.
3. **Reference Paper Context:** The paper *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition* (IEEE ICIMIA-2025) provides theoretical motivation. This prototype demonstrates deterministic, observable QoS scoring, SLA constraint enforcement, anti-flapping hysteresis, periodic monitoring, and override safety without training neural networks or swarm heuristics.

---

## 9. Known Limitations
- **In-Memory Volatility:** Simulation mutations and override state are held in memory during the execution session and reset upon application restart.
- **Single-Node Execution:** Monitoring and recommendation pipelines execute in-process on the local host machine.
- **No User Role-Based Access Control (RBAC):** Manual overrides are accessible to any user interacting with the dashboard session without multi-tenant authentication.
