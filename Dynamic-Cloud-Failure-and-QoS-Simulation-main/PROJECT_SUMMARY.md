# Project Summary

## 1. Project Title

**Dynamic Cloud Failure and QoS-Aware Service Reselection**

_Major Project Demonstration Prototype — Inspired by IEEE ICIMIA-2025_

## 2. Problem Statement

Distributed cloud workflows and microservices depend on external cloud services that may experience latency spikes, availability drops, reliability degradation, and unexpected outages. Traditional service selection frameworks often rely on static Service Level Agreement (SLA) specifications and cannot adequately respond to changing runtime conditions.

These limitations can lead to SLA violations, delayed execution, and cascading workflow failures.

This project addresses the problem through a deterministic, lightweight, and explainable simulation platform that monitors cloud service quality, detects simulated failures, and automatically recommends the best eligible replacement.

## 3. Objectives

The primary objectives are to:

1. Simulate real-time cloud service QoS degradation and operational outages.
2. Evaluate candidate services using configurable multi-criteria QoS utility functions.
3. Automatically exclude unavailable services and reselect the optimal eligible candidate.
4. Explain service selection and reselection decisions using mathematical score breakdowns.
5. Develop a **modern, visually appealing, interactive cloud monitoring dashboard**.
6. Introduce advanced graphs for QoS comparison, service health, failure impact, and performance trends.
7. Provide an audit trail of fault injection, service recovery, and reselection events.
8. Maintain deterministic behavior, reproducible experiments, and automated test coverage.

## 4. Proposed Improvements Over the Reference Framework

The reference paper, _A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition_ (IEEE ICIMIA-2025), explores service composition optimization using Deep Reinforcement Learning (DRL) and Particle Swarm Optimization (PSO).

This prototype focuses on an accessible and transparent service reselection subsystem with the following improvements.

### 4.1 Baseline-Anchored Normalization

QoS metrics are normalized against immutable baseline reference bounds. A degradation in one service therefore does not artificially change the normalized scores of unaffected competitors.

### 4.2 Fail-Safe Service Ineligibility

Services marked `UNAVAILABLE` are immediately excluded from recommendations, regardless of their historical QoS score.

### 4.3 Explainable Decision Engine

Each recommendation includes the overall score, individual metric contributions, eligible alternatives, and the reason for selecting or rejecting a candidate.

### 4.4 Modern Cloud Operations Dashboard

The Streamlit interface will be enhanced with a professional monitoring layout, consistent typography, visual hierarchy, service status indicators, interactive controls, and responsive data visualizations.

### 4.5 Advanced QoS Visualization

Interactive graphs will help users understand service performance before, during, and after failure events, making the project easier to demonstrate and evaluate academically.

## 5. Architecture and Modules

```text
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py
├── requirements.txt
├── README.md
├── DEMO_GUIDE.md
├── PROJECT_SUMMARY.md
├── src/
│   ├── __init__.py
│   ├── service_registry.py
│   ├── qos_evaluator.py
│   ├── failure_simulator.py
│   └── recommendation_engine.py
└── tests/
    ├── __init__.py
    ├── test_failure_simulator.py
    ├── test_qos_evaluator.py
    └── test_recommendation_engine.py
```

### Module Responsibilities

- **`src/service_registry.py`** — Defines the `CloudService` data model and registers seven synthetic services across Compute and Storage categories.
- **`src/qos_evaluator.py`** — Normalizes latency, cost, availability, and reliability; validates QoS weights; and calculates weighted service scores.
- **`src/failure_simulator.py`** — Implements latency spikes, service outages, availability degradation, recovery, global reset, and event logging.
- **`src/recommendation_engine.py`** — Filters candidates by category, excludes unavailable services, ranks eligible candidates deterministically, and explains decisions.
- **`app.py`** — Provides the interactive Streamlit dashboard, KPI cards, fault injection controls, Plotly visualizations, service comparison, and event audit trail.

## 6. New Feature: Professional Dashboard Design

The dashboard should resemble a modern cloud operations console rather than a basic collection of Streamlit widgets.

### 6.1 Dashboard Layout

The interface will be organized into the following sections:

**A. Header and System Status**

- Project title and short description.
- Simulation status indicator.
- Current simulation state.
- Reset simulation control.
- Clear visual separation between navigation, monitoring, and analysis sections.

**B. Key Performance Indicator Cards**

Display important information at the top of the dashboard:

- Total registered services.
- Currently available services.
- Unavailable or failed services.
- Current recommended service.
- Best eligible QoS score.
- Number of reselection events.

The KPI cards should update when a fault is injected, a service is restored, or the simulation is reset.

**C. Service Health Overview**

Show each candidate service as a compact card or table row containing:

- Service ID and name.
- Functional category.
- Current operational status.
- Latency.
- Availability percentage.
- Reliability.
- Cost.
- Current normalized QoS score.

Use consistent status colors: green for healthy, amber for degraded, and red for unavailable. Include text labels so status is not communicated by color alone.

**D. Fault Injection Control Panel**

Provide clear interactive controls for:

- Selecting a target service.
- Injecting a latency spike.
- Simulating an outage.
- Degrading availability.
- Restoring an individual service.
- Resetting all services to baseline.

Display the effect of each operation and the resulting recommendation directly in the dashboard.

**E. Recommendation and Decision Explanation**

Highlight the currently recommended eligible service and show:

- Overall QoS score.
- Metric-by-metric contribution.
- Previous recommendation, when available.
- Reason for reselection.
- Ranked eligible alternatives.
- Excluded candidates and their exclusion reasons.

## 7. New Feature: Advanced Interactive Graphs

The following graphs should be implemented using Plotly, with interactive tooltips, legends, readable labels, and consistent formatting.

### 7.1 QoS Score Comparison — Interactive Bar Chart

**Purpose:** Compare the normalized QoS scores of all candidate services.

Features:

- Display service names and scores.
- Visually distinguish the current recommendation.
- Identify unavailable candidates separately.
- Update when QoS weights or service conditions change.
- Support hover details for individual QoS metrics.

### 7.2 QoS Metric Comparison — Grouped Bar Chart

**Purpose:** Compare latency, cost, availability, and reliability across eligible services.

Features:

- Support comparisons across multiple candidates.
- Display normalized metric values on a common 0–1 scale.
- Make metric differences easy to interpret.
- Allow users to inspect individual services through interactive tooltips.

Raw metrics should also remain accessible because normalized values alone do not communicate actual units such as milliseconds or cost units.

### 7.3 Service Health — Status Distribution Chart

**Purpose:** Show the number of healthy, degraded, and unavailable services.

Features:

- Summarize current service health.
- Update after fault injection and recovery.
- Clearly distinguish temporary degradation from total outages.

The degraded state should be assigned according to an explicit rule rather than inferred solely from a visualization.

### 7.4 Latency and Availability Analysis

**Purpose:** Examine the impact of simulated failures on service performance.

Features:

- Compare baseline and current latency.
- Show availability changes.
- Highlight the service affected by the most recent fault.
- Display the difference between baseline and current values.

### 7.5 QoS Weight Distribution — Donut Chart

**Purpose:** Visualize how much each metric contributes to the recommendation.

Default weights:

- Latency: 35%.
- Cost: 20%.
- Availability: 30%.
- Reliability: 15%.

The chart must update when the user changes the weights and should reflect the normalized weights used by the evaluation engine.

### 7.6 Failure Impact and Recovery Timeline

**Purpose:** Visualize the sequence of simulation events.

Features:

- Record fault injection, outage, restoration, and reset events.
- Display event time, service ID, event type, and resulting service state.
- Show the recommendation before and after reselection where recorded.
- Allow users to inspect individual events through tooltips.

This graph should use the existing audit log and recorded snapshots. Historical values must be captured at event time instead of reconstructed from the current service state.

### 7.7 Recommendation Score Breakdown

**Purpose:** Explain why one service outranks another.

Features:

- Display the weighted contribution of latency, cost, availability, and reliability.
- Compare the selected service with the previous selection or its strongest eligible competitor.
- Show the total score and the difference between candidates.
- Explain when a service is excluded because of an outage.

## 8. Technologies Used

- **Programming language:** Python 3.10+.
- **Dashboard:** Streamlit.
- **Data processing:** Pandas.
- **Interactive visualization:** Plotly Express and Plotly Graph Objects.
- **Automated testing:** Pytest.
- **Core implementation:** Python dataclasses, deterministic ranking, and weighted QoS evaluation.

The dashboard improvements should reuse the existing stack wherever possible to keep installation and execution simple.

## 9. Simulation Workflow

1. **Registry Initialization:** Load seven synthetic candidate services and calculate immutable baseline reference bounds.
2. **QoS Evaluation:** Score services using the default normalized weights.
3. **Initial Recommendation:** Recommend the highest-scoring eligible Compute or Storage service in the selected category.
4. **Fault Injection:** Simulate a latency spike, availability reduction, or complete outage.
5. **Dynamic Reselection:** Recalculate scores and recommend the highest-scoring eligible replacement.
6. **Visualization Update:** Refresh KPI cards, service health, score comparisons, and decision explanations.
7. **Recovery:** Restore a service or reset the simulation to its original baseline.
8. **Audit Logging:** Record the action, timestamp, affected service, and recommendation changes.
9. **Demonstration and Validation:** Run the automated tests and verify that the dashboard remains functional through normal, degraded, and all-unavailable states.

## 10. Testing and Validation

The existing verified test suite contains **21 passing tests**, with zero failures, errors, or skipped tests.

The reported verification also includes successful module imports and a Streamlit startup check returning HTTP 200.

Existing tests cover:

- Normalization bounds and zero-division protection.
- QoS weight validation and normalization.
- Weighted scoring and metric sensitivity.
- Latency spikes and availability degradation.
- Outage simulation and candidate exclusion.
- Restoration and reset idempotency.
- Deterministic ranking and tie-breaking.
- Functional category filtering.
- All-unavailable scenarios.
- Protection against baseline drift.

### Additional Tests for the Dashboard Improvements

Before claiming the upgraded dashboard is complete, add or extend tests for:

- Correct KPI calculations after fault injection.
- Graph data consistency with the recommendation engine.
- Correct score contribution calculations.
- Historical event snapshot integrity.
- Correct updates after restoration and reset.
- Empty-state behavior when no eligible candidate exists.
- Dashboard startup and rendering of essential sections.

The 21 existing tests are the verified baseline; the additional dashboard tests must be executed before reporting any updated test count.

## 11. Synthetic Data Disclaimer

All candidate cloud services, QoS values, and failure events are synthetic. The application does not connect to AWS, Microsoft Azure, Google Cloud, or other commercial cloud infrastructure.

The prototype does not provision physical resources and does not implement or benchmark the reference paper's DRL and PSO neural optimization models.

The reselection engine is a deterministic, weighted multi-criteria scoring system designed for transparency and demonstration.

## 12. Limitations and Future Work

- **Single-service reselection:** The current implementation chooses individual atomic services rather than orchestrating complete multi-service DAG workflows.
- **Static candidate registry:** Candidate services are pre-registered rather than dynamically discovered.
- **Synthetic failure conditions:** Faults are simulated rather than collected from production telemetry.
- **Historical data limitations:** Meaningful time-series analysis requires recording service metrics and recommendations throughout the simulation.
- **Future enhancements:** Multi-service DAG execution, network jitter simulation, predictive SLA degradation detection, reinforcement learning, and integration with real cloud monitoring APIs.

## 13. Expected Outcome

The improved project will provide a professional, interactive cloud service monitoring and reselection demonstration. Users will be able to inject failures, observe changes in QoS metrics, compare candidate services through interactive graphs, understand the mathematical basis of each recommendation, and inspect the event history.

The primary contribution is a **transparent, reproducible, and visually explainable QoS-aware service reselection prototype**, with a modern dashboard designed to communicate the behavior clearly during a major project demonstration.
