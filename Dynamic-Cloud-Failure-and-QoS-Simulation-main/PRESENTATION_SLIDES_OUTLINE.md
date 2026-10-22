# Dynamic Cloud Failure and QoS-Aware Service Reselection

## PowerPoint Presentation Outline — Engineering Major Project

**Presentation format:** Formal college engineering project review  
**Suggested duration:** 10–12 minutes  
**Project implementation:** Python, Streamlit, Pandas, Plotly  
**Reference basis:** `PROJECT_IMPLEMENTATION_AUDIT_FOR_CHATGPT.md`  

---

## Slide 1 — Title Slide

**DYNAMIC CLOUD FAILURE AND QOS-AWARE SERVICE RESELECTION**

*An Explainable Simulation Prototype for Runtime Service Selection and Failover*

- Major Project Presentation
- Submitted by: **[Student Name / USN]**
- Department of **[Department Name]**
- **[College Name]**
- Under the guidance of **[Guide Name]**
- Academic Year: **[Academic Year]**

*Visual suggestion:* A simple diagram showing candidate cloud services, a failure event, and selection of a replacement.

---

## Slide 2 — Introduction

- Cloud applications depend on services that may experience changing performance or availability.
- Quality of Service (QoS) metrics help compare alternative services.
- Static service selection may not respond appropriately when a selected service becomes degraded or unavailable.
- This project demonstrates runtime fault simulation, QoS-based ranking, and replacement-service recommendation.
- The prototype emphasizes deterministic decisions and human-readable explanations.

**Key point:** The project demonstrates the service-reselection concept in a controlled simulation rather than operating a real cloud infrastructure.

---

## Slide 3 — Problem Statement

Traditional service selection based on fixed or baseline QoS values may not adequately respond to simulated runtime degradation or outages.

The project addresses the following problem:
- A selected service experiences a latency spike or availability reduction.
- A service becomes unavailable.
- The system must exclude unavailable candidates.
- Remaining eligible candidates must be evaluated and ranked.
- The replacement decision should be explainable.

**Problem statement:** To implement a lightweight simulation prototype that evaluates service QoS, handles simulated faults, and recommends an eligible replacement using deterministic weighted ranking.

---

## Slide 4 — Objectives

1. Maintain a registry of candidate services and their QoS metrics.
2. Evaluate latency, cost, availability, and reliability using normalized scores.
3. Allow configurable QoS weights.
4. Simulate latency spikes, availability reduction, and service outages.
5. Exclude unavailable services from replacement recommendations.
6. Rank eligible services deterministically.
7. Explain recommendation decisions through an interactive dashboard.
8. Support restoration, simulation reset, and event logging.

---

## Slide 5 — Research Context and Scope

**Research context**

The project is inspired by the IEEE ICIMIA-2025 paper titled *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*.

**Distinction between the paper and this implementation**

| Full research approach               | Implemented project                          |
| ------------------------------------ | -------------------------------------------- |
| DRL and PSO-based research framework | Deterministic weighted QoS ranking           |
| AI-based optimization approach       | Explicit scoring and sorting rules           |
| Multi-service composition research   | Single-service reselection within a category |
| Model-based learning/optimization    | No DRL or PSO training implemented           |

**Important:** This project is a focused, explainable prototype inspired by the research topic. It is **not a complete reproduction or implementation of the paper's DRL–PSO algorithm**.

---

## Slide 6 — Proposed System and Architecture

**Main modules**

1. **Service Registry — `src/service_registry.py`**
   - Defines service records and synthetic baseline QoS metrics.
   - Maintains reference bounds for normalization.

2. **QoS Evaluator — `src/qos_evaluator.py`**
   - Normalizes metrics.
   - Validates weights and computes aggregate scores.

3. **Failure Simulator — `src/failure_simulator.py`**
   - Injects simulated faults.
   - Restores services and records events.

4. **Recommendation Engine — `src/recommendation_engine.py`**
   - Filters unavailable candidates.
   - Scores and ranks eligible services.
   - Produces decision explanations.

5. **Dashboard — `app.py`**
   - Provides controls, metrics, comparison charts, and event history.

*Visual suggestion:* Architecture flow:
`Service Registry → QoS Evaluator → Recommendation Engine → Recommended Service`  
with `Failure Simulator` feeding state changes, and `Streamlit Dashboard` interfacing with all modules.

---

## Slide 7 — Technology Stack and Project Structure

**Technology stack**
- Python 3.10+ (Tested on 3.13.9) — application logic
- Streamlit (1.66.0 / 1.51.0) — interactive web interface
- Pandas (3.0.6 / 2.3.3) — tabular data handling
- Plotly (7.1.0 / 6.3.0) — comparative visualizations
- Pytest (9.1.1 / 8.4.2) — automated tests

**Core project files**
- `app.py` — dashboard
- `src/service_registry.py` — service definitions and reference bounds
- `src/qos_evaluator.py` — normalization and scoring
- `src/failure_simulator.py` — fault injection and recovery
- `src/recommendation_engine.py` — candidate ranking and explanations
- `tests/` — automated test suite (21 passing tests)
- `requirements.txt` — dependencies
- `README.md` and `DEMO_GUIDE.md` — setup and demonstration documentation

---

## Slide 8 — Synthetic Service Registry

The prototype uses **seven synthetic services** divided into two categories.

| Category  | Service IDs        | Number of services |
| --------- | ------------------ | -----------------: |
| Compute   | SVC-C01 to SVC-C05 |                  5 |
| Storage   | SVC-S01 to SVC-S02 |                  2 |
| **Total** |                    |              **7** |

Each service includes QoS attributes such as:
- Latency (ms) — Minimized
- Cost ($/inv) — Minimized
- Availability (%) — Maximized
- Reliability (%) — Maximized

The service registry maintains baseline values used by the scoring system.

**Dataset limitation:** The audit describes the service data as synthetic and deterministic. No live AWS, Azure, GCP, or other real-cloud service integration is implemented.

---

## Slide 9 — QoS Evaluation and Mathematical Model

The system evaluates four QoS dimensions:
- Latency — lower is better
- Cost — lower is better
- Availability — higher is better
- Reliability — higher is better

Each metric is normalized into the range $[0, 1]$ using fixed reference bounds. The normalization direction depends on whether a lower or higher value is preferred.

Let:
- $s_i$ be the aggregate score of service $i$
- $w_j$ be the normalized weight for metric $j$
- $q_{ij}$ be the normalized score of service $i$ for metric $j$

The weighted scoring model is:
$$s_i = \sum_{j=1}^{4} w_j q_{ij}$$

Subject to:
$$w_j \ge 0, \qquad \sum_{j=1}^{4} w_j = 1$$

**Implementation details**
- User-configurable weights are normalized to sum to 1.
- Normalized metric values are clamped to $[0, 1]$.
- Fixed baseline reference bounds prevent a runtime fault in one service from altering the normalization scale for healthy competing services.
- The highest-scoring eligible candidate is recommended.

---

## Slide 10 — Failure Simulation and Recovery

The failure simulator supports the following operations:

1. **Latency spike**
   - Increases a selected service's latency.
   - Allows the effect on its score and ranking to be observed.

2. **Availability reduction**
   - Reduces the selected service's availability value within the defined bounds.

3. **Service outage**
   - Marks a service as unavailable.
   - The unavailable service is excluded from recommendations.

4. **Service restoration**
   - Restores the selected service to its baseline metrics and status.

5. **Global reset**
   - Reinitializes the simulation to its baseline state without state drift.

**Scope clarification:** Faults are explicitly triggered by the user. The prototype does not implement stochastic background failures or automatic real-world fault detection.

---

## Slide 11 — Recommendation and Reselection Algorithm

**Decision flow**
1. Receive the selected service category and current service state.
2. Filter the registry to the selected category.
3. Exclude candidates marked unavailable.
4. Normalize the QoS metrics using the configured reference bounds.
5. Compute weighted aggregate scores.
6. Sort candidates by descending score.
7. Use service ID as the secondary tie-breaker.
8. Recommend the highest-ranked eligible candidate.
9. Display the score and human-readable decision explanation.

**Algorithm characteristics**
- Deterministic
- Rule-based
- Explainable
- No neural-network inference
- No DRL or PSO optimization

If no eligible candidates remain, the system gracefully handles the total category outage without unhandled exceptions.

---

## Slide 12 — Dashboard and Demonstration

**Dashboard components**
- Category selection
- QoS weight controls
- Fault target and simulation controls
- KPI cards
- Candidate service table
- QoS comparison bar chart
- Recommendation explanation
- Fault and recovery event log

**Suggested live demonstration**
1. Display the baseline Compute candidate ranking (`SVC-C01` top pick with `0.8168`).
2. Inject a latency spike into a service (`+150ms`).
3. Show the updated scores and recommendation (`SVC-C02` top pick with `0.7937`).
4. Simulate an outage and demonstrate exclusion of the unavailable service (`SVC-C04` selected).
5. Restore a service.
6. Reset the simulation and show the baseline state.

---

## Slide 13 — Testing and Reported Results

**Automated testing**
The implementation audit reports:
- **21 automated tests**
- **21 passed**
- **0 failed**
- **0 skipped**
- Test execution time: **< 0.20s**
- Test coverage across failure simulator, QoS evaluator, and recommendation engine.

**What the tests validate**
- Fault injection and recovery behavior
- Metric normalization and weight handling
- Aggregate QoS scoring
- Candidate filtering and deterministic ranking

**Interpretation**
The tests confirm correct, bug-free implementation of the prototype's logic. These tests do not establish performance superiority over DRL–PSO or production-scale cloud workloads.

---

## Slide 14 — Limitations and Future Enhancements

**Current limitations**
- Synthetic service data only.
- No real cloud API connections or infrastructure orchestration.
- Single-service reselection within a category; no multi-service workflow DAG composition.
- Deterministic, user-triggered fault simulation rather than stochastic background failures.
- In-memory simulation state and event history; state is lost on refresh or server restart.
- No DRL, PSO, or neural-network training.

**Potential future enhancements (Not implemented)**
- Multi-service workflow DAG composition.
- Persistent event logging (e.g., PostgreSQL / SQLite).
- Stochastic fault and network-jitter simulation.
- Predictive detection of QoS degradation.
- Integration with real cloud service APIs (AWS CloudWatch / Azure Monitor).
- Comparative evaluation against DRL–PSO or other baselines.

---

## Slide 15 — Conclusion and Q&A

**Conclusion**
- Developed a modular prototype for dynamic cloud failure simulation and QoS-aware service reselection.
- Implemented weighted scoring over latency, cost, availability, and reliability.
- Demonstrated how simulated degradation and outages affect candidate eligibility and ranking.
- Added deterministic recommendation, decision explanations, restoration, reset, and event logging.
- Provided an interactive dashboard for observing the selection process.

**Final clarification**
The contribution is an explainable, deterministic QoS-based reselection prototype. It is inspired by the research problem but does not implement the full DRL–PSO research framework.

**Thank you**  
*Questions and Discussion*

---

## Presentation Preparation Checklist

- [ ] Replace all title-slide placeholders with your actual academic details.
- [ ] Add a screenshot of the running dashboard.
- [ ] Add a clean architecture diagram.
- [ ] Add a screenshot of the candidate ranking before and after a fault.
- [ ] Run `pytest -v` and verify the 21 passed tests.
- [ ] Demonstrate an outage and recovery using the live application.
- [ ] Do not describe the prototype as a DRL–PSO implementation.
- [ ] Do not claim real-cloud deployment, real-world experiments, or comparative performance gains unless separately demonstrated and documented.
