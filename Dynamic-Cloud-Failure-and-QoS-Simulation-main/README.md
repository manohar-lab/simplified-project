# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

**Major Project Demonstration Prototype**

Inspired by the IEEE ICIMIA-2025 paper: _A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition_

---

## 1. Project Overview

Modern cloud architectures rely on interconnected services, distributed APIs, and dynamic service orchestration. Although traditional Quality of Service (QoS) models evaluate cloud services using advertised Service Level Agreements (SLAs), real-world environments can experience latency spikes, service degradation, and unexpected outages.

**Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** is a standalone simulation prototype that models cloud service failures, evaluates multiple QoS metrics, and dynamically recommends the best eligible replacement when a service becomes degraded or unavailable.

The system provides an interactive dashboard for simulating failures, comparing service performance, understanding reselection decisions, and inspecting an event audit log.

## 2. Problem Statement and Proposed Improvement

### Problem Statement

Existing cloud service composition approaches may rely on static service registries or offline optimization. When an active service experiences an outage or significant QoS degradation, the orchestration process can encounter execution failures, SLA violations, or service interruptions without an appropriate reselection mechanism.

### Proposed Improvement

Inspired by the framework presented in the reference paper, this project implements a transparent, QoS-aware service reselection mechanism with three key improvements.

- **Baseline-Anchored Normalization:** QoS scores are calculated using fixed baseline reference bounds so that degrading one service does not distort the scores of unaffected services.
- **Fail-Safe Eligibility Rules:** Completely unavailable services are immediately excluded from recommendations, regardless of their previous QoS scores.
- **Decision Explainability:** Human-readable explanations describe why a candidate was selected, why a previous recommendation changed, and why unavailable services were excluded.

These improvements are implemented in a deterministic simulation prototype rather than a trained deep reinforcement learning or particle swarm optimization system.

## 3. Synthetic Data Disclaimer

> **Important:** All cloud services, QoS metrics, and failure events in this project are synthetic.

This prototype does not connect to real cloud providers, provision cloud infrastructure, or execute production cloud workloads. It does not claim to reproduce the experimental benchmarks or train the DRL/PSO models described in the reference IEEE paper.

The project is intended for academic demonstration, experimentation, and evaluation of QoS-aware service reselection concepts.

## 4. System Architecture

```text
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── service_registry.py
│   ├── qos_evaluator.py
│   ├── failure_simulator.py
│   └── recommendation_engine.py
└── tests/
    ├── __init__.py
    ├── test_service_registry.py
    ├── test_qos_evaluator.py
    ├── test_failure_simulator.py
    └── test_recommendation_engine.py
```

### Module Responsibilities

| Module                         | Responsibility                                                                                                                                          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`                       | Streamlit dashboard, KPI cards, interactive controls, candidate tables, and Plotly charts.                                                              |
| `src/service_registry.py`      | Defines the `CloudService` model, registers seven synthetic services across Compute and Storage categories, and retains baseline QoS values.            |
| `src/qos_evaluator.py`         | Implements metric normalization, weighted QoS scoring, weight validation, clamping, and division-by-zero safeguards.                                    |
| `src/failure_simulator.py`     | Simulates latency spikes, outages, availability reductions, service restoration, and global reset operations. Maintains an append-only event audit log. |
| `src/recommendation_engine.py` | Filters candidates by category and operational status, ranks eligible services, and generates decision explanations.                                    |
| `tests/`                       | Contains automated tests for registry behavior, QoS evaluation, failure simulation, and recommendation logic.                                           |

## 5. Technology Stack

- **Programming Language:** Python 3.10+
- **Dashboard:** Streamlit
- **Data Manipulation:** Pandas
- **Visualization:** Plotly Express and Plotly Graph Objects
- **Testing:** Pytest

## 6. Installation and Setup

### Prerequisites

- Python 3.10 or later
- Windows PowerShell (for the commands below)
- Git, if cloning the repository

Open PowerShell in the project directory.

### Option A: Use the project virtual environment

```powershell
cd "C:\Users\Mahendra\OneDrive\Desktop\Dynamic-Cloud-Failure-and-QoS-Simulation"

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Install or update dependencies
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, use the direct invocation commands in Option B or Option C.

### Option B: Use the virtual environment executables directly

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Option C: Use Anaconda Python

```powershell
& "$env:USERPROFILE\anaconda3\python.exe" -m pip install -r requirements.txt
```

Ensure that `requirements.txt` includes the project's required dependencies, including Streamlit, Pandas, Plotly, and Pytest.

## 7. Running the Application

From the project root, launch the dashboard using one of the following commands.

### With the activated virtual environment

```powershell
streamlit run app.py
```

### Without activating the virtual environment

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

### Using Anaconda

```powershell
& "$env:USERPROFILE\anaconda3\python.exe" -m streamlit run app.py
```

Once the server starts, open the local URL displayed in the terminal. The default address is:

**http://localhost:8501**

## 8. Running the Automated Tests

Execute the test suite from the project root.

```powershell
python -m pytest -v
```

Alternatively, use the virtual environment directly:

```powershell
.\.venv\Scripts\pytest.exe -v
```

Or use Anaconda:

```powershell
& "$env:USERPROFILE\anaconda3\python.exe" -m pytest -v
```

### Test Coverage

The documented test suite contains 21 unit tests covering the following areas:

- Lower-is-better normalization for latency and cost.
- Higher-is-better normalization for availability and reliability.
- Metric sensitivity and score direction.
- Equal minimum/maximum bounds and division-by-zero protection.
- Non-negative weight validation and sum-to-one normalization.
- Weighted aggregate QoS scoring.
- Latency spike injection and metric bounds.
- Outage simulation and immediate candidate exclusion.
- Availability reductions and percentage clamping.
- Idempotent service restoration and global reset.
- Baseline consistency across repeated restoration cycles.
- Category filtering and deterministic candidate ranking.
- Tie-breaking behavior.
- Handling categories in which every service is unavailable.

**Note:** The count of 21 tests should be updated if the actual test suite changes. Run the test command and report the observed result rather than assuming every test passes.

## 9. Demonstration Scenarios

The following sequence can be used during a project presentation.

### Scenario 1: Inspect the Baseline State

1. Launch the dashboard.
2. Select the `Compute` category.
3. Inspect the candidate services and their baseline QoS scores.
4. Review the total-service, healthy-service, and unavailable-service KPIs.
5. Identify the highest-ranked eligible service.

The expected baseline is five Compute services, five healthy services, and zero unavailable services, assuming the registry matches the documented configuration.

### Scenario 2: Latency Spike and Dynamic Reselection

1. Select `SVC-C01` or the currently recommended Compute service.
2. Enter `150` in the latency spike field.
3. Click **Inject Latency Spike**.
4. Observe the updated latency and QoS score.
5. Inspect the newly recommended eligible service.
6. Review the explanation panel and comparative chart.

For the documented example, increasing latency from 45 ms by 150 ms produces a simulated latency of 195 ms.

The recommendation should change if the degraded service no longer ranks first and another eligible candidate scores higher.

### Scenario 3: Total Service Outage

1. Select the currently recommended service.
2. Click **Simulate Outage**.
3. Verify that its operational status becomes `UNAVAILABLE`.
4. Confirm that it is excluded from the recommendation candidates.
5. Inspect the replacement recommendation and exclusion explanation.

The replacement depends on the current QoS weights, service metrics, and eligibility rules. Verify the exact selected service during the demonstration.

### Scenario 4: Complete Category Failure

1. Simulate outages for all remaining Compute services.
2. Observe the recommendation engine after each outage.
3. Confirm that no unavailable service is recommended.
4. Verify that the dashboard displays a clear no-eligible-service warning when every Compute service is unavailable.

The application should handle this edge case without crashing.

### Scenario 5: Restoration and Global Reset

1. Restore an individual service.
2. Confirm that its operational state returns to normal.
3. Click **Reset All Services**.
4. Verify that all services return to their baseline state.
5. Inspect the event audit log to review the chronological sequence of simulated events.

The restoration and reset operations should be repeatable without accumulating unintended changes to baseline QoS values.

## 10. Limitations

The current prototype has the following limitations:

- **Simulation Only:** All services and failure events are synthetic.
- **Single-Service Reselection:** The system selects an alternative service within a functional category rather than executing a complete multi-service workflow.
- **Deterministic Recommendation:** Candidate selection uses weighted QoS evaluation and ranking rather than a trained DRL policy.
- **No Production Integration:** The prototype does not invoke real cloud APIs or provision cloud resources.
- **No Benchmark Reproduction Claim:** Results from this dashboard should not be presented as reproduced experimental results from the reference paper.

## 11. Future Work

Potential extensions for a future version include:

- Multi-cloud service composition across multiple providers.
- Dependency-aware workflow modeling using directed acyclic graphs (DAGs).
- Network jitter and correlated failure simulation.
- SLA violation prediction and proactive service reselection.
- Integration of reinforcement learning for adaptive decision-making.
- Integration of particle swarm optimization for candidate or workflow optimization.
- Performance evaluation using repeatable experiments and documented datasets.

These extensions are outside the scope of the current demonstration prototype.

## 12. Project Summary

Dynamic Cloud Failure Detection and QoS-Aware Service Reselection demonstrates how a cloud service orchestration system can respond to simulated failures through baseline-anchored QoS evaluation, fail-safe eligibility filtering, deterministic candidate ranking, and transparent decision explanations.

The Streamlit dashboard makes these mechanisms observable and testable through interactive failure injection, service restoration, comparative visualizations, and event logging.

The result is a modular academic prototype for demonstrating the principles of resilient, QoS-aware cloud service reselection.

---

**Project Type:** Academic Major Project Demonstration Prototype  
**Implementation:** Python, Streamlit, Pandas, Plotly, Pytest  
**Data:** Fully synthetic  
**Reference:** IEEE ICIMIA-2025 paper on hybrid deep reinforcement learning and swarm optimization for intelligent cloud service composition
