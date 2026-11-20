# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
## Major Project Demonstration Prototype (Phases 1–8 Complete — Presentation & Viva Ready)

Inspired by the IEEE ICIMIA-2025 paper, *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*.

---

## 1. Project Overview
Modern cloud applications depend on distributed multi-cloud services and third-party APIs. In real-world environments, candidate services experience latency spikes, reduced availability, transient unreliability, or total outages. 

**Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** is an end-to-end Python prototype designed to evaluate candidate cloud services using multi-attribute Quality of Service (QoS) parameters, enforce strict hard Service Level Agreement (SLA) constraints, mitigate service flapping via hysteresis and cooldown thresholds, autonomously monitor service health, support authorized manual service overrides with failover safety, and present explainable reselection decisions in an interactive Streamlit dashboard.

The application runs deterministically on synthetic cloud candidate registries with complete decision explainability and chronological audit logs.

---

## 2. Comprehensive Documentation & Viva Preparation Suite

The complete academic, engineering, and presentation documentation suite is available in the [`docs/`](docs/) directory:

### Core Academic & Engineering Documentation
| Document | Description | Key Contents |
| :--- | :--- | :--- |
| [**Final Project Report**](docs/FINAL_PROJECT_REPORT.md) | Comprehensive 25-chapter academic report | Problem formulation, QoS model, SLA validation, hysteresis, monitoring, UI, benchmarks, literature review, and academic submission summary. |
| [**System Architecture**](docs/SYSTEM_ARCHITECTURE.md) | Architectural specification & 6 Mermaid diagrams | Complete component interaction matrix, data-flow pipelines, state machines, and sequence diagrams. |
| [**Implementation Details**](docs/IMPLEMENTATION_DETAILS.md) | Module-by-module technical specification | Mathematical formulas, dataclass definitions, function signatures, and algorithmic workflows. |
| [**Experimental Results**](docs/EXPERIMENTAL_RESULTS.md) | Empirical evaluation & benchmark report | 8 empirical experiments, 100-step comparative baseline study, stability analysis, and scalability profiling. |
| [**Testing Report**](docs/TESTING_REPORT.md) | Verification and test execution report | Detailed audit of all 138 automated test cases across 13 test suites, persistence tests, AppTest UI automation, and coverage analysis. |
| [**Known Limitations**](docs/KNOWN_LIMITATIONS.md) | Academic scope boundaries | Explicit documentation of synthetic data boundaries, single-node execution, resolved persistence status, and future research directions. |
| [**Project Completion Audit**](docs/PROJECT_COMPLETION_AUDIT.md) | Milestone verification matrix | Line-by-line audit verifying 100% completion of scoped requirements across Phases 1 through 9. |

### Phase 7 Final Submission & Audit Suite
| Document | Description | Key Contents |
| :--- | :--- | :--- |
| [**Phase 7 Final Audit**](docs/PHASE_7_FINAL_AUDIT.md) | Final Quality Audit & Submission Readiness | Formal evaluation table across all 8 project areas, completion formula, discovered issues, and clearance verdict. |
| [**Submission Checklist**](docs/SUBMISSION_CHECKLIST.md) | Comprehensive Submission Checklist | Pre-submission verification checklist covering code, tests, dashboard, experiments, report, and institutional tasks. |
| [**Implementation Verification**](docs/IMPLEMENTATION_VERIFICATION.md) | Architectural Traceability Matrix | Deep subsystem verification tracing modules, algorithms, and models to test suites and runtimes. |
| [**Report Validation**](docs/REPORT_VALIDATION.md) | Academic Report Formatting Audit | Formatting verification of `F_report.docx` (Times New Roman, 12/14pt, headers, footers, tables, figures, natural appendix flow). |

### Phase 8 Demonstration, Presentation & Viva Deliverables
| Document | Description | Key Contents |
| :--- | :--- | :--- |
| [**Demonstration Guide**](docs/DEMONSTRATION_GUIDE.md) | Step-by-step 12-minute live demo walkthrough | Prerequisites, dashboard visual layout, step-by-step demonstration sequence (Phases A–G), expected outputs, and troubleshooting. |
| [**Project Presentation**](docs/PROJECT_PRESENTATION.md) | 15-slide defense presentation outline | Complete slides with titles, bullet points, suggested diagrams/charts, and word-for-word presenter delivery notes. |
| [**Viva Voce Questions & Answers**](docs/VIVA_QUESTIONS.md) | 55 comprehensive examination Q&As | In-depth answers across 15 technical domains including QoS modeling, SLA filtering, anti-flapping, failover, and architecture. |
| [**Project Explanations**](docs/PROJECT_EXPLANATION.md) | Faculty verbal delivery scripts | Tailored delivery scripts: 1-minute elevator pitch, 3-minute committee overview, 5-minute technical review, and novel contributions. |
| [**Final Demonstration Audit**](docs/FINAL_DEMONSTRATION_AUDIT.md) | 14-scenario verification matrix | Detailed audit verifying all 14 demonstration scenarios against actual code execution and AppTest UI tests. |

---

## 3. Implemented Capabilities and System Architecture

### Core Capabilities
1. **Multi-Attribute QoS Evaluation:** Weighted normalization across latency (ms, lower-is-better), invocation cost (currency, lower-is-better), availability (%, higher-is-better), and reliability (%, higher-is-better) with baseline reference bounds.
2. **Phase 1 — Strict Hard SLA Filtering:** Centralized SLA configuration (`SLAConfig`) enforcing maximum latency, minimum availability, and minimum reliability thresholds. Services violating any threshold are disqualified regardless of aggregate score.
3. **Phase 2 — Anti-Flapping Hysteresis & Cooldown:** Centralized hysteresis configuration (`HysteresisConfig`) requiring candidate QoS improvement to exceed a configurable delta (`min_qos_delta`) before switching, with optional step-based and temporal cooldown periods. Outages and SLA violations immediately trigger emergency reselection, bypassing cooldown.
4. **Phase 3 — Periodic Automatic Monitoring Engine:** Background-capable, non-blocking monitoring engine (`MonitoringEngine`) that reassesses candidate services at configurable intervals, classifies health states (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `RECOVERED`), detects outages/SLA violations, and emits deduplicated event logs.
5. **Phase 4 — Validated Manual Service Override:** Two distinct operating modes (`AUTOMATIC` vs. `MANUAL_OVERRIDE`) managed by `ManualOverrideManager`. Manual selection strictly validates candidate existence, category match, availability, and SLA compliance. In the event of an outage or SLA violation on a manually overridden service, the system immediately terminates the override and performs emergency failover to the best eligible automatic service.
6. **Phase 5 & 6 — Resilience Validation & Benchmarking:** Rigorous reliability hardening, edge-case remediation, and empirical benchmarking across 8 controlled experimental conditions.
7. **Phase 7 — Academic Submission Readiness:** Complete documentation suite, cross-document audit verification, visual dashboard navigation guides, and 100% verified test suite.
8. **Phase 8 — Final Demonstration & Viva Preparation:** Comprehensive 15-slide defense deck, 55 viva voce examination Q&As, verbal delivery scripts, and verified 14-scenario demonstration audit.
9. **Phase 9 — SQLite Local Persistence & Audit History:** ACID-compliant SQLite persistence layer (`src/database/`) with WAL journaling, schema versioning, foreign keys, transaction rollback, and full history retention across restarts.

### Repository Architecture
```text
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py                             # Streamlit interactive dashboard with operating mode & monitoring panels
├── benchmark_performance.py           # Performance profiling and scalability benchmark script
├── benchmark_persistence.py           # SQLite database persistence profiling benchmark script
├── requirements.txt                   # Core runtime dependencies
├── README.md                          # Project overview and submission documentation
├── data/                              # Persistent storage directory
│   └── cloud_qos_simulation.db        # SQLite database (auto-initialized, WAL mode)
├── docs/                              # Academic, technical & presentation documentation suite
│   ├── FINAL_PROJECT_REPORT.md        # 25-chapter academic capstone report
│   ├── SYSTEM_ARCHITECTURE.md         # Component diagrams and data flows
│   ├── IMPLEMENTATION_DETAILS.md      # Method-level engineering specifications
│   ├── EXPERIMENTAL_RESULTS.md        # Benchmark data and comparative baseline evaluation
│   ├── TESTING_REPORT.md              # 138-test automated verification report
│   ├── KNOWN_LIMITATIONS.md           # Scope boundaries and assumptions
│   ├── PROJECT_COMPLETION_AUDIT.md    # 52-item milestone audit matrix
│   ├── DEMONSTRATION_GUIDE.md         # 12-minute live demonstration script
│   ├── PROJECT_PRESENTATION.md        # 15-slide academic defense presentation outline
│   ├── VIVA_QUESTIONS.md              # 55 comprehensive viva voce examination Q&As
│   ├── PROJECT_EXPLANATION.md         # 1-min, 3-min, and 5-min faculty delivery scripts
│   └── FINAL_DEMONSTRATION_AUDIT.md   # 14-scenario demonstration audit report
├── src/
│   ├── __init__.py                    # Package root exporting core modules (v1.5.0)
│   ├── service_registry.py            # CloudService dataclass and synthetic baseline registries
│   ├── qos_evaluator.py               # Bound normalization and weighted QoS score calculation
│   ├── sla_config.py                  # Centralized SLA thresholds and constraint validation (Phase 1)
│   ├── hysteresis_config.py           # Hysteresis switching threshold and cooldown logic (Phase 2)
│   ├── monitoring_config.py           # Periodic monitoring configuration (Phase 3)
│   ├── monitoring_engine.py           # Periodic health reassessment & event logging engine (Phase 3)
│   ├── override_manager.py            # Operating mode management & override validation (Phase 4)
│   ├── failure_simulator.py           # Fault injection (latency, availability, outage) and baseline restore
│   ├── recommendation_engine.py       # Multi-stage SLA, hysteresis, and override recommendation pipeline
│   ├── analytics.py                   # Health classification, history tracking, and snapshot builders
│   ├── explainability.py              # Candidate comparison tables, explanations, and audit trail
│   └── database/                      # Persistent storage and audit management (Phase 9)
│       ├── __init__.py                # Database package entrypoint
│       ├── connection.py              # Thread-isolated SQLite connections and transactions
│       ├── schema.py                  # Table definitions, version tracking, and indexes
│       ├── migrations.py              # Automatic idempotent migration runner
│       └── repositories.py            # Parameterized SQL data access objects
└── tests/
    ├── conftest.py                    # Isolated test database fixtures
    ├── test_qos_evaluator.py          # QoS normalization and scoring unit tests (9 tests)
    ├── test_failure_simulator.py      # Fault injection and restoration unit tests (6 tests)
    ├── test_recommendation_engine.py  # Basic recommendation engine unit tests (6 tests)
    ├── test_sla_eligibility.py        # SLA constraint filtering and edge-case unit tests (14 tests)
    ├── test_hysteresis.py             # Hysteresis threshold and cooldown unit tests (15 tests)
    ├── test_monitoring.py             # Periodic monitoring and state transition tests (17 tests)
    ├── test_manual_override.py        # Manual override, validation, and failover tests (15 tests)
    ├── test_persistence.py            # SQLite persistence, migrations, and ACID tests (15 tests)
    ├── test_explainability.py         # Decision explainability and audit trail tests (5 tests)
    ├── test_analytics.py              # Health classification and chart builder tests (4 tests)
    ├── test_ui_dashboard.py           # Streamlit AppTest dashboard automation tests (12 tests)
    ├── test_e2e_integration_scenarios.py # End-to-end integration scenarios A–G (7 tests)
    └── test_reliability_edge_cases.py    # Reliability and boundary edge-case tests (13 tests)
```

---

## 4. Dashboard Navigation and Visual Layout Guide

The Streamlit dashboard (`app.py`) provides an interactive interface for evaluating cloud services, observing autonomous failover, and testing manual overrides.

### Top Summary KPI Cards
- **Active Selected Service:** Displays the currently active service ID and name (e.g., `SVC-C01 (NovaCompute Standard)`).
- **QoS Score:** Real-time composite score between 0.0000 and 1.0000.
- **Operating Mode:** Status badge indicating `AUTOMATIC` (green) or `MANUAL_OVERRIDE` (amber).
- **Service Health:** Badge indicating `HEALTHY` (green), `DEGRADED` (yellow), or `UNAVAILABLE` (red).

### Sidebar Controls
1. **Operating Mode & Manual Override:**
   - Radio buttons to toggle between **Automatic Optimization** and **Manual Service Override**.
   - Service dropdown listing available candidates with compliance status indicators.
   - Text input for audit override reason and a "Confirm Override" button.
   - "Release Override" button to safely transition back to automatic mode.
2. **Dynamic Fault Injection:**
   - Target candidate selector.
   - Fault injection buttons: *Inject Latency Spike* (+150 ms), *Reduce Availability* (-20%), *Simulate Complete Outage* (0% availability/reliability), and *Restore Service*.
3. **SLA Configuration:**
   - Sliders for Maximum Latency (ms), Minimum Availability (%), and Minimum Reliability (%).
4. **Hysteresis & Anti-Flapping Settings:**
   - Slider for Minimum QoS Delta ($\Delta H$, default 0.05).
   - Cooldown period configuration (steps / seconds).
5. **Periodic Monitoring Controls:**
   - Interval slider (seconds), Run Monitoring Cycle button, and auto-run toggle.
6. **Global Reset Button:**
   - Instantly clears all mutations, resets candidate states to default baseline, and restores automatic mode.

### Main View Tabs
- **Tab 1: Live Service Evaluation & Recommendation:** Displays the ranked candidate table, normalized attribute breakdowns, hard SLA eligibility badges, disqualification reasons, and runner-up delta margins.
- **Tab 2: Service Health & Monitoring Telemetry:** Visual indicators of all registered services, health status distribution, recent state transition alerts, and background monitoring logs.
- **Tab 3: Comparative QoS Radar & Multi-Attribute Analysis:** Interactive Plotly radar charts and bar charts comparing latency, cost, availability, and reliability trade-offs across candidates.
- **Tab 4: Audit Logs & Explainability Engine:** Chronological audit trail of all recommendation decisions, switching justifications, override requests, and failover events.

---

## 5. Technology Stack
- **Language:** Python (3.10+)
- **Interactive UI:** Streamlit
- **Data Structures & Processing:** Pandas, NumPy
- **Interactive Visualizations:** Plotly Graph Objects & Plotly Express
- **Test Automation:** Pytest, `streamlit.testing.v1.AppTest`
- **Memory Profiling & Timing:** `tracemalloc`, Python `time.perf_counter`

---

## 6. Installation and Setup

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

## 7. Running the Application & Test Suite

### Running the Streamlit Dashboard
```powershell
python -m streamlit run app.py
```
Open the local URL in a web browser (default: `http://localhost:8501`).

### Running the Complete Automated Test Suite
```powershell
python -m pytest tests -v
```
All **138 tests** run deterministically in approximately 15–20 seconds without external server dependencies.

### Running Performance Benchmarks
```powershell
python benchmark_performance.py
python benchmark_persistence.py
```

---

## 8. Documented Test Status (Authoritative Test Verification)
The automated test suite contains **138 tests** across 13 test modules, all passing:
- `tests/test_qos_evaluator.py`: 9 passed
- `tests/test_failure_simulator.py`: 6 passed
- `tests/test_recommendation_engine.py`: 6 passed
- `tests/test_sla_eligibility.py`: 14 passed
- `tests/test_hysteresis.py`: 15 passed
- `tests/test_monitoring.py`: 17 passed
- `tests/test_manual_override.py`: 15 passed
- `tests/test_persistence.py`: 15 passed
- `tests/test_explainability.py`: 5 passed
- `tests/test_analytics.py`: 4 passed
- `tests/test_ui_dashboard.py`: 12 passed
- `tests/test_e2e_integration_scenarios.py`: 7 passed
- `tests/test_reliability_edge_cases.py`: 13 passed
**Result:** **138 passed, 0 failed, 0 skipped (100% pass rate in ~20.07s)**.

---

## 9. Performance Benchmarks
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

## 10. Synthetic Data & Research Disclaimer
1. **Synthetic Simulation:** All registered cloud services (e.g., NovaCompute Standard, AetherCompute HighPerf, TitanCompute Enterprise), QoS measurements, and failure events are synthetically generated for academic simulation and evaluation.
2. **No Live Cloud APIs:** This prototype does not connect to live commercial cloud infrastructure (AWS, Azure, GCP), issue billing requests, or manage real virtual machines/containers.
3. **Reference Paper Context:** The paper *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition* (IEEE ICIMIA-2025) provides theoretical motivation. This prototype demonstrates deterministic, observable QoS scoring, SLA constraint enforcement, anti-flapping hysteresis, periodic monitoring, and override safety without training neural networks or swarm heuristics.

---

## 11. Known Limitations
- **In-Memory Volatility:** Simulation mutations and override state are held in memory during the execution session and reset upon application restart.
- **Single-Node Execution:** Monitoring and recommendation pipelines execute in-process on the local host machine.
- **No User Role-Based Access Control (RBAC):** Manual overrides are accessible to any user interacting with the dashboard session without multi-tenant authentication.
- For a comprehensive analysis of academic boundaries, see [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md).
