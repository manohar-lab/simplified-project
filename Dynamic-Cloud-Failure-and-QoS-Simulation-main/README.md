# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

> **Major Project Demonstration Prototype**  
> Inspired by: IEEE ICIMIA-2025 paper — *"A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition"*

---

## 1. Project Overview

Modern cloud architectures depend heavily on multi-service workflows and distributed cloud APIs. While static QoS (Quality of Service) models evaluate candidate services based on advertised Service Level Agreements (SLAs), real-world cloud environments suffer from dynamic latency spikes, transient degradation, and total service outages.

This project delivers a functional, standalone simulation prototype that models dynamic cloud service failures, evaluates multi-criteria QoS metrics in real time, and dynamically recommends an optimal eligible replacement candidate when failures occur.

---

## 2. Problem Statement & Proposed Improvement

### The Problem
Existing cloud composition approaches often assume static service registries or rely on offline optimization. When an active cloud service experiences an outage or severe QoS degradation, composition pipelines experience execution stalls, SLA violations, or unhandled exceptions unless resilient reselection is built into the orchestration layer.

### Proposed Improvement over the Paper's Framework
The IEEE ICIMIA-2025 paper outlines a cloud service repository, an environment simulator, a QoS evaluator, and a composition engine. Our improvement concretizes this framework into a **transparent, real-time reselection engine**:
- **Baseline-Anchored Normalization:** Metric normalization is calculated against baseline reference bounds, ensuring that a failure in one service decreases its own score without warping the scores of untouched services.
- **Fail-Safe Ineligibility Rules:** Total outages immediately disqualify a service from recommendation regardless of its prior QoS score.
- **Decision Explainability:** The system provides explicit, human-readable explanations detailing why a specific candidate was chosen and why previous choices were superseded or excluded.

---

## 3. Synthetic Data Disclaimer

> **Important Disclaimer:**  
> All candidate cloud services, metrics (latency, cost, availability, reliability), and simulated failure events are **100% synthetic**. This prototype does not connect to real cloud providers, does not provision cloud infrastructure, and does not claim to reproduce the experimental benchmarks or train the DRL/PSO models described in the original IEEE paper.

---

## 4. Architecture & Module Responsibilities

The codebase follows a modular design with separation of concerns:

```
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py                     # Streamlit web dashboard & interactive visualization
├── requirements.txt           # Project dependencies
├── README.md                  # System documentation & demo guide
├── .gitignore                 # Standard Python exclusions
├── src/
│   ├── __init__.py            # Package entry
│   ├── service_registry.py    # Synthetic candidate services & baseline QoS data
│   ├── qos_evaluator.py       # Multi-criteria normalization and weighted scoring
│   ├── failure_simulator.py   # Deterministic fault injection & state management
│   └── recommendation_engine.py # Transparent candidate ranking & explanation
└── tests/
    ├── __init__.py
    ├── test_service_registry.py (integrated into test suite)
    ├── test_qos_evaluator.py
    ├── test_failure_simulator.py
    └── test_recommendation_engine.py
```

### Module Breakdown
- `src/service_registry.py`: Defines the `CloudService` data model and registers 7 synthetic cloud services across two functional categories (`Compute` and `Storage`). Retains immutable baseline QoS values.
- `src/qos_evaluator.py`: Implements lower-is-better (Latency, Cost) and higher-is-better (Availability, Reliability) normalization formulas, weight validation and normalization (sum-to-1), zero-division safeguards, and metric clamping.
- `src/failure_simulator.py`: Manages runtime operational state, supports latency spikes, outage triggers, availability reductions, single-service restoration, and global simulation reset. Maintained with an append-only event audit log.
- `src/recommendation_engine.py`: Filters by service category, excludes unavailable/failed services, sorts by aggregate QoS score, and produces transparent decision logs and reselection explanations.
- `app.py`: Provides a responsive Streamlit UI featuring KPI summary cards, candidate tables, Plotly comparative bar charts, and simulation control panels.

---

## 5. Technology Stack

- **Language:** Python 3.10+
- **Web UI & Dashboard:** Streamlit
- **Data Manipulation:** Pandas
- **Interactive Visualizations:** Plotly Express & Plotly Graph Objects
- **Testing Framework:** Pytest

---

## 6. Installation Instructions (Windows PowerShell)

Ensure Python 3.10+ is installed on your Windows machine.

### Option A: Using the Project Virtual Environment (.venv)
Open Windows PowerShell in the project directory:

```powershell
cd "c:\Users\Mahendra\OneDrive\Desktop\Dynamic-Cloud-Failure-and-QoS-Simulation"

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# (Dependencies are already installed, or update with):
pip install -r requirements.txt
```

### Option B: Using System Anaconda Directly
```powershell
# Direct invocation with Anaconda Python
& "$env:USERPROFILE\anaconda3\python.exe" -m pip install -r requirements.txt
```

---

## 7. Running the Application

To launch the interactive dashboard locally:

```powershell
# Option 1: Using activated .venv:
streamlit run app.py

# Option 2: Direct one-liner via .venv:
.\.venv\Scripts\streamlit.exe run app.py

# Option 3: Direct one-liner via Anaconda:
& "$env:USERPROFILE\anaconda3\python.exe" -m streamlit run app.py
```

The application will start and open automatically in your default browser at:
`http://localhost:8501`

---

## 8. Executing the Test Suite

Run the complete automated unit test suite with verbose output:

```powershell
# Option 1: Using activated .venv:
pytest -v

# Option 2: Direct one-liner via .venv:
.\.venv\Scripts\pytest.exe -v

# Option 3: Direct one-liner via Anaconda:
& "$env:USERPROFILE\anaconda3\python.exe" -m pytest -v
```

All 21 unit tests cover:
- Lower-is-better normalization and clamping (Latency & Cost)
- Higher-is-better normalization and clamping (Availability & Reliability)
- Sensitivity verification: lower latency/cost increases score, higher availability/reliability increases score
- Equal minimum/maximum edge cases without division by zero
- Non-negative weight validation and sum-to-1 normalization
- Weighted QoS aggregate scoring
- Latency spike injection and bounds verification
- Outage marking and immediate candidate exclusion
- Availability reductions and bounded clamping [0, 100]%
- Service restoration idempotency
- Global simulation reset idempotency
- Zero drift across repeated restore and reset iterations
- Category filtering
- Deterministic candidate ranking and tie-breaking
- All-unavailable edge case handling without crashes

---

## 9. Demonstration Sequence for Project Presentations

Follow this 5-step sequence during a project demonstration:

1. **Baseline State Inspection:**
   - Launch the dashboard and view the `Compute` category.
   - Observe that `NovaCompute Standard` (`SVC-C01`) or `AetherCompute HighPerf` (`SVC-C02`) is selected with the highest QoS score.
   - Review the summary KPI cards: `5 Total`, `5 Healthy`, `0 Unavailable`.

2. **Scenario 1: Latency Spike & Dynamic Reselection:**
   - In the sidebar, select target service `SVC-C01` (or the top recommended service).
   - Enter `150` in the "Spike (ms)" field and click **⚡ Inject Latency Spike**.
   - **Observe:** The latency of the target service spikes from 45.0ms to 195.0ms. Its QoS score drops immediately, and the recommendation engine automatically reselects the next best available alternative (e.g., `SVC-C02`).
   - The explanation panel highlights the reselection trigger and metric comparison.
   - The Plotly bar chart visually displays the score degradation.

3. **Scenario 2: Total Outage Simulation:**
   - Select the newly recommended service (`SVC-C02`).
   - Click **🔴 Simulate Outage**.
   - **Observe:** The operational status changes to `UNAVAILABLE` (marked with a red badge).
   - The service is immediately disqualified from candidate consideration, and the engine seamlessly reselects an eligible alternative (`SVC-C04` / `TitanCompute Enterprise`).
   - The Excluded Services panel explains why `SVC-C02` was removed.

4. **Scenario 3: Complete Category Failure (Edge Case):**
   - Click **🔴 Simulate Outage** on each remaining Compute service until all are marked `UNAVAILABLE`.
   - **Observe:** The system does not crash. It displays an alert: `🚨 NO ELIGIBLE SERVICE AVAILABLE! All 5 service(s) in category 'Compute' are currently UNAVAILABLE.`

5. **Scenario 4: Service Restoration & Global Reset:**
   - Click **🟢 Restore Service** on any service to demonstrate single-service recovery back to baseline.
   - Click **🔄 Reset All Services** to demonstrate idempotent global restoration of all services, clearing degradation and returning the registry to pristine baseline state.
   - Check the **Simulation Event Audit Log** to see the full chronological history of events.

---

## 10. Limitations & Future Work

- **Phase 1 Prototype Scope:** Focuses on deterministic single-service reselection within a single category rather than end-to-end multi-service composition workflow graph execution.
- **Future Work (Phase 2):** Integration of multi-cloud service composition pipelines, dependency DAG evaluation, network jitter simulation, and adaptive reinforcement learning policies.
