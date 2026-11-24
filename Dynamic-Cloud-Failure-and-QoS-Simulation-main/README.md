# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

**Major Project Demonstration Prototype** — Phases 1–9 documented; presentation and viva materials included

> Inspired by the IEEE ICIMIA-2025 paper *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition.*

> **Research-scope note:** This project is a deterministic academic simulation. Cloud candidates, QoS measurements, and injected failures are synthetic. The prototype does not connect to live AWS, Azure, or Google Cloud services.

## 1. Project Overview

Modern cloud applications depend on distributed services and third-party APIs. Candidate services can experience latency spikes, reduced availability, transient reliability problems, or complete outages. Selecting a suitable replacement therefore requires more than ranking services by a single performance metric.

**Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** is a Python prototype that evaluates candidate services using multiple Quality of Service (QoS) attributes, enforces hard Service Level Agreement (SLA) constraints, reduces unnecessary switching through hysteresis and cooldown controls, monitors service health, supports validated manual overrides, and explains reselection decisions through an interactive Streamlit dashboard.

The application uses deterministic synthetic candidate registries. It provides decision explanations and chronological event/audit history. SQLite is used for the local persistence functionality described in Phase 9; transient simulation state and in-memory controls may still reset when the application process restarts, depending on which state is persisted by the implementation.

## 2. Documentation and Viva Preparation

The project documentation is organized under `docs/`.

### Core academic and engineering documentation

| Document | Description | Key contents |
| :--- | :--- | :--- |
| Final Project Report | Academic project report | Problem formulation, QoS model, SLA validation, hysteresis, monitoring, interface, benchmarks, literature review, and submission summary. |
| System Architecture | Architecture specification | Component interactions, data flows, state machines, and sequence diagrams. |
| Implementation Details | Technical specification | Formulas, data models, function interfaces, and algorithm workflows. |
| Experimental Results | Experimental evaluation | Controlled experiments, comparative baselines, stability analysis, and scalability profiling. |
| Testing Report | Test documentation | Test suites, persistence tests, UI automation, and coverage information. |
| Known Limitations | Scope and limitations | Synthetic-data boundaries, single-node execution, persistence boundaries, and future research directions. |
| Project Completion Audit | Milestone checklist | Requirement-level review of the project phases. |

### Phase 7 — final submission and audit materials

| Document | Description |
| :--- | :--- |
| Phase 7 Final Audit | Quality audit and submission-readiness assessment. |
| Submission Checklist | Pre-submission checks for code, tests, dashboard, experiments, report, and institutional requirements. |
| Implementation Verification | Traceability between implemented subsystems, source modules, tests, and execution evidence. |
| Report Validation | Formatting and content review of the academic report. |

### Phase 8 — demonstration, presentation, and viva materials

| Document | Description |
| :--- | :--- |
| Demonstration Guide | A guided live demonstration, including prerequisites, steps, expected outputs, and troubleshooting. |
| Project Presentation | Fifteen-slide presentation outline with suggested visuals and presenter notes. |
| Viva Questions | Technical viva questions and answers across the project's main subject areas. |
| Project Explanation | Short, medium, and detailed verbal project explanations. |
| Final Demonstration Audit | Demonstration-scenario verification matrix. |

These links describe the documentation files expected in the repository. Confirm that each file exists and that its contents match the current implementation before submission.

## 3. Implemented Capabilities

- **Multi-attribute QoS evaluation:** Weighted normalization of latency and invocation cost (lower is better), and availability and reliability (higher is better), using baseline reference bounds.
- **Hard SLA filtering:** Centralized SLAConfig applies maximum-latency, minimum-availability, and minimum-reliability constraints. A service that violates a hard constraint is excluded even if its aggregate QoS score is high.
- **Hysteresis and cooldown:** HysteresisConfig requires a candidate's QoS improvement to exceed the configured `min_qos_delta` before switching. Optional step-based and time-based cooldowns help reduce flapping. Outages and SLA violations can trigger emergency reselection without waiting for the normal cooldown.
- **Periodic monitoring:** MonitoringEngine reassesses candidate health at configured intervals and uses health states such as HEALTHY, DEGRADED, UNAVAILABLE, and RECOVERED. It records monitoring events and detects outages or SLA violations.
- **Validated manual override:** ManualOverrideManager supports AUTOMATIC and MANUAL_OVERRIDE modes. Manual selection validates candidate existence, category, availability, and SLA compliance. If the selected service becomes unavailable or violates an SLA, the override is terminated and emergency failover is attempted using eligible candidates.
- **Resilience testing and benchmarking:** Reliability and edge-case tests, controlled experiments, and performance measurements are included in the project materials.
- **Submission-readiness materials:** Technical documentation, report checks, dashboard guidance, and submission checklists are provided.
- **Demonstration and viva preparation:** Presentation materials, verbal explanation scripts, viva questions, and demonstration scenarios are provided.
- **SQLite local persistence:** The `src/database/` package provides SQLite storage functionality, including WAL-mode support, schema versioning, foreign keys, transaction handling, and repository/data-access methods, as described by the project documentation. Verify the exact records persisted by the current application before making claims about which runtime states survive a restart.

## 4. Repository Structure

The following is the documented repository layout. Update this tree if the actual checkout differs.

```
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py
├── benchmark_performance.py
├── benchmark_persistence.py
├── requirements.txt
├── README.md
├── data/
│   └── cloud_qos_simulation.db
├── docs/
│   ├── FINAL_PROJECT_REPORT.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── IMPLEMENTATION_DETAILS.md
│   ├── EXPERIMENTAL_RESULTS.md
│   ├── TESTING_REPORT.md
│   ├── KNOWN_LIMITATIONS.md
│   ├── PROJECT_COMPLETION_AUDIT.md
│   ├── PHASE_7_FINAL_AUDIT.md
│   ├── SUBMISSION_CHECKLIST.md
│   ├── IMPLEMENTATION_VERIFICATION.md
│   ├── REPORT_VALIDATION.md
│   ├── DEMONSTRATION_GUIDE.md
│   ├── PROJECT_PRESENTATION.md
│   ├── VIVA_QUESTIONS.md
│   ├── PROJECT_EXPLANATION.md
│   └── FINAL_DEMONSTRATION_AUDIT.md
├── src/
│   ├── __init__.py
│   ├── service_registry.py
│   ├── qos_evaluator.py
│   ├── sla_config.py
│   ├── hysteresis_config.py
│   ├── monitoring_config.py
│   ├── monitoring_engine.py
│   ├── override_manager.py
│   ├── failure_simulator.py
│   ├── recommendation_engine.py
│   ├── analytics.py
│   ├── explainability.py
│   └── database/
│       ├── __init__.py
│       ├── connection.py
│       ├── schema.py
│       ├── migrations.py
│       └── repositories.py
└── tests/
    ├── conftest.py
    ├── test_qos_evaluator.py
    ├── test_failure_simulator.py
    ├── test_recommendation_engine.py
    ├── test_sla_eligibility.py
    ├── test_hysteresis.py
    ├── test_monitoring.py
    ├── test_manual_override.py
    ├── test_persistence.py
    ├── test_explainability.py
    ├── test_analytics.py
    ├── test_ui_dashboard.py
    ├── test_e2e_integration_scenarios.py
    └── test_reliability_edge_cases.py
```

### Main source modules

| Module | Responsibility |
| :--- | :--- |
| `service_registry.py` | CloudService data model and synthetic baseline registries. |
| `qos_evaluator.py` | QoS normalization and weighted score calculation. |
| `sla_config.py` | Central SLA thresholds and eligibility validation. |
| `hysteresis_config.py` | Switching threshold and cooldown configuration. |
| `monitoring_config.py` | Monitoring configuration. |
| `monitoring_engine.py` | Periodic health reassessment and event logging. |
| `override_manager.py` | Operating-mode management and manual override validation. |
| `failure_simulator.py` | Latency, availability, and outage fault injection and restoration. |
| `recommendation_engine.py` | SLA, hysteresis, and override-aware recommendation pipeline. |
| `analytics.py` | Health classification, history tracking, and dashboard data builders. |
| `explainability.py` | Candidate comparisons, decision explanations, and audit information. |
| `database/` | SQLite connections, schema, migrations, and repository methods. |

## 5. Dashboard Guide

The Streamlit dashboard (`app.py`) is styled as a **Cloud Command Center** with a dark navy theme. It provides six navigable views for evaluating services, injecting faults, observing health, and testing manual overrides.

### Navigation views

| View | Description |
| :--- | :--- |
| **Dashboard** | System health banner (NOMINAL / DEGRADATION / OUTAGE), five visual cloud service cards with health badges, role indicators, and QoS progress bars. A connected-node SVG topology map shows service relationships and active routing. |
| **Cloud Service Map** | Interactive topology visualization of all cloud services with connecting lines and directional arrows showing service relationships. Failed services are highlighted in red; reselection transitions are animated. |
| **Performance Analytics** | Latency timeline, service health comparison, QoS ranking, availability visualization, and health distribution charts using Plotly. |
| **Failure Lab** | Interactive failure simulation with one-click examiner scenarios: inject latency spikes, simulate outages, reduce availability, restore services, and reset the simulation. Visual feedback shows the effect of each action. |
| **Decision History** | Chronological audit trail of recommendation decisions, switching explanations, override requests, and failover events. |
| **Configuration** | SLA thresholds, QoS weights, hysteresis settings, monitoring intervals, and operating-mode controls. |

### Automatic failover tracker

A 7-step visual workflow tracks the failover process in real time:

1. Active service identification
2. Failure or degradation detection
3. SLA eligibility checking
4. QoS comparison
5. Hysteresis decision
6. New service selection
7. Recovery confirmation

Each step displays a plain-language rationale derived from actual system decisions.

### Sidebar controls

- **Fault injection:** Select a target service and inject a latency spike, reduce availability, simulate an outage, or restore the service.
- **Monitoring:** Configure the monitoring interval, run a monitoring cycle, and enable or disable automatic monitoring.
- **Global reset:** Restore the simulation to its baseline state and automatic mode.

## 6. Technology Stack

- **Language:** Python 3.10+
- **Interactive application:** Streamlit
- **Data processing:** Pandas and NumPy
- **Visualization:** Plotly Graph Objects and Plotly Express
- **Testing:** Pytest and `streamlit.testing.v1.AppTest`
- **Profiling:** `time.perf_counter` and `tracemalloc`
- **Persistence:** SQLite

## 7. Installation and Setup

### Prerequisites

- Python version supported by the project's dependencies (the supplied documentation lists Python 3.10–3.14).
- PowerShell, Bash, or Command Prompt.

### Create and activate a virtual environment

```bash
# Navigate to the project directory
cd Dynamic-Cloud-Failure-and-QoS-Simulation

# Create a virtual environment
python -m venv .venv

# Activate it in PowerShell
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the activation method appropriate for your shell or adjust the local execution policy in accordance with your environment's security requirements.

## 8. Run the Application and Tests

### Start the dashboard

```bash
python -m streamlit run app.py
```

Open the local URL printed by Streamlit (normally http://localhost:8501).

### Run the automated test suite

```bash
python -m pytest tests -v
```

The project documentation reports **138 tests** across 13 test modules. The module-level counts add up to 138:

| Test module | Reported tests |
| :--- | :--- |
| `test_qos_evaluator.py` | 9 |
| `test_failure_simulator.py` | 6 |
| `test_recommendation_engine.py` | 6 |
| `test_sla_eligibility.py` | 14 |
| `test_hysteresis.py` | 15 |
| `test_monitoring.py` | 17 |
| `test_manual_override.py` | 15 |
| `test_persistence.py` | 15 |
| `test_explainability.py` | 5 |
| `test_analytics.py` | 4 |
| `test_ui_dashboard.py` | 12 |
| `test_e2e_integration_scenarios.py` | 7 |
| `test_reliability_edge_cases.py` | 13 |
| **Total** | **138** |

> **Verification note:** The figures above are the test results stated in the supplied project documentation, not a fresh test execution performed while editing this README. Run the command above in the target environment and update this section if the observed result differs. Avoid describing the suite as currently passing until that run has been completed.

### Run performance benchmarks

```bash
python benchmark_performance.py
python benchmark_persistence.py
```

## 9. Performance Benchmarks

The supplied project documentation reports measurements collected with `time.perf_counter()` and `tracemalloc` over repeated cycles on Python 3.14 (64-bit) and Windows 11. These are local prototype measurements, not cloud-provider service-level measurements.

### Reported component measurements

| Operation | Reported measurement |
| :--- | :--- |
| SLA eligibility filtering (10 services) | Mean 0.016 ms; minimum 0.008 ms |
| QoS score evaluation (10 services) | Mean 0.150 ms; minimum 0.082 ms |
| Isolated hysteresis decision | Mean 0.0015 ms |
| End-to-end recommendation pipeline (10 services) | Mean 0.186 ms; minimum 0.083 ms |
| Full periodic monitoring cycle (10 services) | Mean 0.380 ms; minimum 0.212 ms |
| Dashboard initial render via AppTest | Approximately 2.89 seconds |

### Reported scalability measurements

| Candidate services | Average latency | Reported throughput | Peak memory |
| :--- | :--- | :--- | :--- |
| 10 | 0.996 ms | Approximately 10,037 services/s | 6.26 KB |
| 100 | 6.226 ms | Approximately 16,061 services/s | 29.01 KB |
| 500 | 32.533 ms | Approximately 15,369 services/s | 137.21 KB |
| 1,000 | 66.613 ms | Approximately 15,012 services/s | 243.00 KB |

> **Interpretation caution:** The 10-service recommendation-pipeline measurement in the component table (0.186 ms) differs from the 10-service scalability measurement (0.996 ms). These may come from different benchmark procedures or measurement scopes. Keep both values only if the benchmark scripts and raw outputs support the distinction; otherwise rerun the benchmarks and reconcile the tables before academic submission.

## 10. Synthetic Data and Research Disclaimer

- **Synthetic simulation:** Candidate cloud services, example provider names, QoS measurements, and failure events are generated for academic simulation and evaluation.
- **No live cloud APIs:** The prototype does not connect to commercial AWS, Azure, or Google Cloud infrastructure, issue billing requests, or manage real virtual machines or containers.
- **Reference-paper context:** The IEEE ICIMIA-2025 paper provides theoretical motivation. This prototype demonstrates deterministic QoS scoring, SLA constraint enforcement, hysteresis-based switching control, periodic monitoring, and manual-override safety. It should not be described as implementing trained deep-reinforcement-learning or particle-swarm-optimization models unless such models are actually present in the source code.

## 11. Known Limitations

- **Synthetic inputs:** Results are based on simulated services and generated QoS conditions, not live provider telemetry.
- **Single-node execution:** Monitoring and recommendation workflows execute within the local application process; distributed coordination is outside the documented scope.
- **No user RBAC:** The supplied documentation states that manual overrides are not protected by multi-tenant role-based authentication.
- **Runtime-state persistence boundary:** SQLite persistence is included in the documented Phase 9 architecture. This does not automatically mean every transient simulation mutation, monitoring state, or override survives an application restart. Consult the persistence implementation and tests to identify exactly which records are stored and restored.
- **Environment dependence:** Benchmark timings and memory measurements depend on the machine, Python version, dependency versions, and benchmark procedure.

For further detail, see `docs/KNOWN_LIMITATIONS.md`.

## 12. Before Academic Submission

1. Run the complete test suite and record the actual output, including failures, skips, and duration.
2. Run both benchmark scripts and verify that the README tables match their raw outputs.
3. Confirm that every linked file under `docs/` exists in the submitted repository.
4. Verify that the architecture and module descriptions match the current source code.
5. Confirm the exact persistence behavior from implementation and tests.
6. Verify the full bibliographic details of the IEEE ICIMIA-2025 reference before citing it in the final report.
7. Check that screenshots, charts, and report conclusions are supported by the submitted application and experiment artifacts.

---

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Purpose:** Academic demonstration prototype for QoS-aware service selection, failure simulation, monitoring, and service reselection.
