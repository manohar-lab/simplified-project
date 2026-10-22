# Project Summary

## 1. Project Title
**Dynamic Cloud Failure and QoS-Aware Service Reselection**  
*Major Project Demonstration Prototype (Inspired by IEEE ICIMIA-2025)*

---

## 2. Problem Statement
Distributed cloud workflows and microservices rely on external cloud candidate services. Traditional service selection frameworks evaluate candidates using static Service Level Agreement (SLA) specifications. In production cloud environments, however, services frequently experience runtime degradation, such as sudden latency spikes, availability drops, and unexpected total outages. Static selection models cannot detect or adapt to these dynamic QoS fluctuations, leading to SLA penalties, composition pipeline stalls, and cascading workflow failures.

---

## 3. Objective
To construct a deterministic, lightweight, and explainable prototype that:
1. Simulates real-time cloud service QoS degradation and operational outages.
2. Dynamically evaluates candidate services using multi-criteria QoS utility functions.
3. Automatically excludes failed candidates and reselects the optimal available replacement candidate.
4. Explains the exact mathematical rationale behind every selection and reselection event through an interactive dashboard.

---

## 4. Proposed Improvement over Paper's Framework
The reference paper (*"A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition"*, IEEE ICIMIA-2025) discusses multi-service composition optimization using DRL and PSO. This major project implements an accessible, verified, and transparent reselection subsystem featuring three core improvements:
1. **Baseline-Anchored Normalization:** Metric normalization is calculated against immutable baseline reference bounds established by the candidate service registry. This guarantees that degrading one service's metrics reduces its own score without artificially warping the scores of untouched competitor services.
2. **Fail-Safe Ineligibility Rules:** Total outages (`UNAVAILABLE` state) immediately disqualify a candidate from recommendation regardless of how high its historical or baseline score was.
3. **Transparent Decision Explainability:** Rather than operating as an uninterpretable black box, the recommendation engine generates detailed explanations comparing the chosen service against prior selections, breaking down individual sub-scores (latency, cost, availability, reliability).

---

## 5. Architecture & Modules

The system follows a clean modular architecture:

```
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py                     # Streamlit interactive UI & Plotly visualization dashboard
├── requirements.txt           # Minimal dependencies (streamlit, pandas, plotly, pytest)
├── README.md                  # Complete architectural and execution guide
├── DEMO_GUIDE.md              # Verified step-by-step demonstration walkthrough
├── PROJECT_SUMMARY.md         # Academic and technical project summary
├── src/
│   ├── __init__.py
│   ├── service_registry.py    # CloudService dataclass, 7 synthetic services, reference bounds
│   ├── qos_evaluator.py       # Multi-criteria normalization and weighted QoS scoring
│   ├── failure_simulator.py   # Fault injection, status management, and audit logging
│   └── recommendation_engine.py # Deterministic ranking, exclusion logic, and explainability
└── tests/
    ├── __init__.py
    ├── test_failure_simulator.py      # Tests for fault injection and restoration
    ├── test_qos_evaluator.py          # Tests for normalization, weighting, and sensitivity
    └── test_recommendation_engine.py  # Tests for ranking, exclusion, and edge cases
```

### Module Roles:
- **`src/service_registry.py`**: Defines the `CloudService` data model with baseline QoS attributes. Registers 7 synthetic candidates (5 `Compute`, 2 `Storage`).
- **`src/qos_evaluator.py`**: Applies lower-is-better formulas for Latency and Cost, higher-is-better formulas for Availability and Reliability, clamps normalized values to `[0.0, 1.0]`, and normalizes weights so they sum to `1.0`.
- **`src/failure_simulator.py`**: Injects latency spikes, marks service outages, lowers availability percentages, supports single-service recovery, and enables global reset with an append-only event log.
- **`src/recommendation_engine.py`**: Filters candidates by functional category, excludes unavailable candidates, ranks eligible services deterministically by QoS score, and produces human-readable decision logs.
- **`app.py`**: Presents a responsive Streamlit dashboard with summary KPI cards, dynamic sliders for QoS priorities, fault injection controls, candidate comparison tables, interactive Plotly bar charts, and an audit trail.

---

## 6. Technologies Used
- **Programming Language:** Python 3.10+ (Verified on Python 3.13.9 / Anaconda3)
- **Web Dashboard:** Streamlit (1.51.0)
- **Data Structuring:** Pandas (2.3.3)
- **Interactive Visualizations:** Plotly Express & Plotly Graph Objects (6.3.0)
- **Automated Testing:** Pytest (8.4.2)

---

## 7. Simulation Workflow
1. **Registry Initialization:** Candidate services are loaded with deterministic baseline QoS parameters. Fixed baseline reference bounds are computed.
2. **QoS Evaluation:** Candidates are scored using normalized multi-criteria weighting (default: Latency `35%`, Cost `20%`, Availability `30%`, Reliability `15%`).
3. **Initial Recommendation:** The candidate with the highest QoS score is designated as the recommended service (`SVC-C01` / `NovaCompute Standard`, QoS: `0.8168`).
4. **Fault Injection:**
   - *Latency Spike:* Injects delay (+150ms). Score drops to `0.5405`. Engine detects competitor (`SVC-C02` / `AetherCompute HighPerf`, QoS: `0.7937`) has a higher score and triggers reselection.
   - *Service Outage:* Marks `SVC-C02` as `UNAVAILABLE`. Engine immediately disqualifies it and reselects `SVC-C04` (`TitanCompute Enterprise`, QoS: `0.7634`).
   - *Total Outage:* When all candidates are down, engine gracefully flags `has_eligible_service = False` without application crash.
5. **Restoration & Recovery:** Restores individual services or resets the full registry back to baseline state without drift.
6. **Audit Trail:** Every fault injection, restoration, and reset action is timestamped and recorded in the audit log.

---

## 8. Testing Performed & Actual Results
The complete automated unit test suite was executed via pytest:
- **Commands:** `pytest -v` (under `.venv`) or `& "$env:USERPROFILE\anaconda3\python.exe" -m pytest -v`
- **Result:** **`21 passed in 0.08s`** (0 failures, 0 errors, 0 skipped).
- **Test Categories:**
  - Normalization bounds & zero-division guards (4 tests).
  - Weight validation & sum-to-1 normalization (1 test).
  - Multi-criteria weighted QoS scoring & sensitivity (4 tests).
  - Latency spike injection & availability reduction (2 tests).
  - Outage simulation & candidate exclusion (2 tests).
  - Restoration and simulation reset idempotency (2 tests).
  - Deterministic ranking & tie-breaking (2 tests).
  - Category filtering & all-unavailable edge cases (2 tests).
  - Drift prevention across repeated actions (2 tests).
- **Application Startup Verification:**
  - All module imports verified via Python.
  - Streamlit dashboard booted in headless mode and verified responding with HTTP status `200`.

---

## 9. Synthetic Data Disclaimer
All candidate cloud services, QoS metrics (latency, cost, availability, reliability), and simulated failure events are **100% synthetic**. This prototype does not connect to commercial cloud providers (AWS, Azure, GCP), does not provision physical infrastructure, and does not implement or benchmark the complex DRL/PSO neural network models referenced in the IEEE research paper.

---

## 10. Limitations & Future Work
- **Single-Service Reselection Scope:** The current prototype evaluates and reselects individual atomic cloud services within a category rather than orchestrating end-to-end multi-service composite DAG workflows.
- **Static Candidate Pool:** Uses a pre-registered candidate pool rather than dynamic service discovery via external service brokers.
- **Future Work:**
  - Multi-service workflow composition DAG execution.
  - Integration of stochastic network jitter and intermittent packet loss.
  - Adaptive reinforcement learning policies for long-term predictive SLA degradation forecasting.
