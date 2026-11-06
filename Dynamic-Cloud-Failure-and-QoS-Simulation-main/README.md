Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
Major Project Demonstration Prototype

Inspired by the IEEE ICIMIA-2025 paper, A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition.
1. Project Overview
Modern cloud applications depend on interconnected services and distributed APIs. A service that performs well under normal conditions may experience latency spikes, reduced availability, reliability problems, or a complete outage.

Dynamic Cloud Failure Detection and QoS-Aware Service Reselection is a Python-based simulation prototype that evaluates cloud services using Quality of Service (QoS) metrics, simulates service failures, and automatically recommends an alternative when the current recommendation is no longer the best eligible option.

The Streamlit dashboard makes the process observable through service comparisons, interactive failure simulation, analytics visualizations, decision explanations, and an event audit trail.

The current implementation uses deterministic QoS scoring and ranking. It is not a trained deep reinforcement learning (DRL) or particle swarm optimization (PSO) implementation.
2. Problem Statement and Proposed Approach
Problem Statement
Static service selection can become unsuitable when a cloud service experiences an outage or performance degradation. Without a mechanism to reassess service health and compare alternatives, an application may continue relying on a service that is no longer suitable.
Proposed Approach
The prototype addresses this problem through:
- QoS-based evaluation: Evaluates services using latency, cost, availability, and reliability.
- Baseline-anchored normalization: Uses fixed reference bounds so that a change in one service does not distort the normalized scores of unaffected services.
- Deterministic ranking: Ranks eligible candidates using a weighted QoS score, with deterministic tie-breaking.
- Failure simulation: Supports simulated latency spikes, availability reductions, and total outages.
- Automatic reselection: Re-evaluates candidates after simulated changes and recommends the highest-ranked eligible alternative.
- Decision explainability: Shows why a service was selected, how its score compares with alternatives, and why unavailable services were excluded.
- Analytics and audit history: Provides charts, simulation snapshots, and a chronological record of events.
Current eligibility behavior
Unavailable services are excluded from recommendations. The current implementation does not yet enforce configurable hard SLA thresholds for maximum latency, minimum availability, or minimum reliability. A degraded service may remain eligible if it is still ranked highest under the current QoS scoring rules.

Strict SLA filtering is a planned implementation phase and must not be described as completed until it has been implemented and tested.
3. Synthetic Data and Research Disclaimer
Important: The cloud services, QoS measurements, and failure events used by this prototype are synthetic.

This project does not connect to real cloud providers, provision cloud infrastructure, or execute production workloads. It does not claim to reproduce the experimental benchmarks or train the DRL/PSO models described in the reference paper.

The project is intended for academic demonstration and experimentation with QoS-aware service reselection concepts.
4. System Architecture
The application is organized into a Streamlit interface, service and QoS logic, failure simulation, recommendation and explanation components, and automated tests.
Dynamic-Cloud-Failure-and-QoS-Simulation/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── service_registry.py
│   ├── qos_evaluator.py
│   ├── recommendation_engine.py
│   ├── failure_simulator.py
│   ├── analytics.py
│   └── explainability.py
└── tests/
    ├── __init__.py
    └── ...
Module Responsibilities
Module	Responsibility
app.py	Streamlit dashboard, KPI cards, interactive controls, service tables, and Plotly visualizations.
src/service_registry.py	Defines and manages the synthetic cloud-service registry and baseline QoS values.
src/qos_evaluator.py	Normalizes QoS metrics, validates weights, and calculates the weighted aggregate score.
src/recommendation_engine.py	Filters unavailable candidates, ranks eligible services, and produces recommendation results.
src/failure_simulator.py	Simulates latency spikes, availability reductions, outages, restoration, and reset operations; maintains simulation events.
src/analytics.py	Provides service-health classification, analytics data, history tracking, and simulation snapshots.
src/explainability.py	Produces human-readable selection and exclusion explanations and supports the decision audit trail.
tests/	Contains automated tests for core service, QoS, simulation, recommendation, analytics, and explanation logic.


This tree summarizes the main modules. Use the actual repository tree as the source of truth if files have been added, renamed, or reorganized.

5. Technology Stack
- Language: Python
- Dashboard: Streamlit
- Data processing: Pandas and NumPy
- Visualization: Plotly Express and Plotly Graph Objects
- Testing: Pytest
6. Installation and Setup
Prerequisites
- Python 3.10 or later
- Git (if cloning the repository)
- Windows PowerShell for the example commands below
Open a terminal in the project root directory.
Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
If PowerShell blocks activation, invoke the environment executables directly.
Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Without activating the virtual environment:
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Ensure requirements.txt contains the dependencies used by the current project, including Streamlit, Pandas, NumPy, Plotly, and Pytest.
7. Running the Application
From the project root:
python -m streamlit run app.py
Or, on Windows with the virtual environment:
.\.venv\Scripts\streamlit.exe run app.py
Open the local URL printed in the terminal. The default address is http://localhost:8501.
8. Running Automated Tests
Run the complete test suite from the project root:
python -m pytest -v
Or use the virtual environment directly:
.\.venv\Scripts\pytest.exe -v
Latest documented test status
The latest project audit reported 29 backend unit tests passing (29/29):
- QoS evaluator: 9 tests
- Recommendation engine: 6 tests
- Failure simulator: 6 tests
- Explainability: 5 tests
- Analytics: 3 tests
These are the results documented by the audit, not a guarantee that the current local checkout still produces the same result. Run the test command above to verify the current code.

The audit also identified areas not covered by the reported tests, including Streamlit UI/session-state behavior and some invalid or boundary input cases.
9. Dashboard and Demonstration Scenarios
The dashboard includes service KPIs, candidate comparisons, QoS visualizations, failure simulations, recommendation explanations, and simulation history. The documented analytics include QoS comparison charts, metric-specific charts, before/after failure comparisons, service-health distribution, history timelines, and simulation snapshots.
Scenario 1: Inspect the baseline state
1. Launch the dashboard.
2. Select a service category, such as Compute.
3. Inspect the registered services and their QoS metrics.
4. Review the recommendation and its explanation.
5. Identify the highest-ranked eligible service.
The exact service selected depends on the current registry, QoS weights, and metric values. Do not assume a fixed result without checking the running application.
Scenario 2: Inject a latency spike
1. Select the currently recommended service.
2. Enter a latency increase in the simulation control.
3. Trigger the latency-spike action.
4. Observe the updated latency and QoS score.
5. Review whether another eligible service becomes the top-ranked candidate.
6. Inspect the explanation and history/audit information.
Reselection occurs when the updated ranking changes the top eligible candidate. A latency-degraded service is not necessarily excluded under the current implementation unless it becomes unavailable or another candidate outranks it.
Scenario 3: Simulate a service outage
1. Select the currently recommended service.
2. Trigger the outage simulation.
3. Verify that its operational status changes to UNAVAILABLE.
4. Confirm that it is excluded from recommendation candidates.
5. Review the replacement recommendation and exclusion explanation.
Scenario 4: Simulate complete category failure
1. Simulate outages for all services in the selected category.
2. Observe the recommendation after each change.
3. Confirm that unavailable services are not recommended.
4. Verify that the application handles the no-available-service state without crashing.
Scenario 5: Restore services and reset the simulation
1. Restore an individual service.
2. Confirm that its operational status returns to normal.
3. Use the global reset control.
4. Verify that services return to their baseline state.
5. Inspect the event history.
Restoration and reset should not accumulate unintended changes to baseline QoS values.
10. Current Limitations and Planned Improvements
The latest audit identified the following gaps:
- Hard SLA enforcement: Configurable maximum-latency, minimum-availability, and minimum-reliability constraints are not yet enforced by the recommendation engine.
- Continuous monitoring: Monitoring is reactive to Streamlit reruns and user interactions rather than a continuous autonomous monitoring loop.
- Anti-flapping protection: Hysteresis or a cooldown mechanism to prevent rapid switching between services is not yet implemented.
- Manual override: A user-controlled service pin/override is not yet implemented.
- UI automation tests: The reported test suite does not cover the Streamlit interface and session-state behavior comprehensively.
- Synthetic environment: Services and failures are simulated; there is no live cloud-provider integration.
Planned implementation order
1. Add configurable SLA thresholds and strict eligibility filtering.
2. Add hysteresis to prevent unnecessary repeated reselection.
3. Add periodic monitoring appropriate to the Streamlit application.
4. Consider manual override and additional UI-level tests.
Implement and verify each phase before marking it complete. Do not describe planned capabilities as existing functionality.
11. Future Research Directions
The following are possible research extensions beyond the current demonstration scope:
- Multi-cloud service composition across providers.
- Dependency-aware workflow modeling using directed acyclic graphs (DAGs).
- Network jitter and correlated failure simulation.
- SLA violation prediction and proactive reselection.
- Reinforcement learning for adaptive decision-making.
- Particle swarm optimization for candidate or workflow optimization.
- Repeatable performance evaluation using documented datasets and experimental procedures.
These are research directions, not claims about the current implementation.
12. Project Summary
Dynamic Cloud Failure Detection and QoS-Aware Service Reselection is an academic simulation prototype for demonstrating how service recommendations can respond to changing QoS conditions and simulated failures.

It combines baseline-anchored QoS evaluation, deterministic candidate ranking, failure simulation, automatic recommendation updates, decision explanations, analytics visualizations, and event history in an interactive Streamlit dashboard.

The implementation is intentionally presented as a simulation prototype. Its current behavior and limitations are documented separately from planned enhancements so that project demonstrations and academic reports accurately reflect what has been implemented.
Project Type: Academic Major Project Demonstration Prototype
Implementation: Python, Streamlit, Pandas, NumPy, Plotly, Pytest
Data: Synthetic
Reference: IEEE ICIMIA-2025 paper on hybrid deep reinforcement learning and swarm optimization for intelligent cloud service composition
