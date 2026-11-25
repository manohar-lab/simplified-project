# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

A simulation-based cloud failure detection and QoS-aware service reselection platform developed as an academic capstone project.

> **Research Paper:** *Dynamic Cloud Failure Detection and QoS-Aware Service Reselection: A Simulation-Based Framework*

> **Academic Reference:** Inspired by IEEE ICIMIA-2025 — *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*

> **Important:** This is a **deterministic academic simulation**. It does not connect to live AWS, Azure, or Google Cloud infrastructure. All cloud services, QoS measurements, and failure events are synthetically generated.

---

## 1. Problem Statement

Modern cloud applications rely on distributed services and third-party APIs that can experience latency spikes, reduced availability, and complete outages. Traditional static service selection cannot react to dynamic runtime degradation, leading to SLA violations and cascading failures.

**Key challenges addressed:**
- Static SLA contracts fail under dynamic conditions
- Unconstrained QoS scoring ignores hard safety constraints
- Naive reactive systems cause service flapping
- Black-box optimization lacks transparency
- Fully autonomous systems prevent operator intervention

## 2. Objectives

1. **Multi-Attribute QoS Evaluation** — Score services using latency, cost, availability, and reliability with configurable weights
2. **Automatic Service Reselection** — Exclude unavailable services and select the best alternative
3. **Failure Simulation** — Inject latency spikes, availability degradation, and total outages
4. **Explainability** — Provide human-readable explanations for every recommendation decision
5. **Interactive Dashboard** — Professional Cloud Command Center for live demonstration

## 3. System Architecture

```mermaid
graph TD
    A[Streamlit Dashboard<br>app.py] --> B[Recommendation Engine]
    A --> C[Failure Simulator]
    A --> D[Analytics & Charts]
    A --> E[Explainability]
    B --> F[QoS Evaluator]
    B --> G[Service Registry]
    C --> G
    F --> G
    D --> G
    E --> B
```

### Module Responsibilities

| Module | Responsibility |
| :--- | :--- |
| `service_registry.py` | CloudService data model, synthetic baselines, immutable reference bounds |
| `qos_evaluator.py` | Min-max normalization and weighted multi-criteria QoS scoring |
| `recommendation_engine.py` | Availability filtering, ranking, selection, and explanation generation |
| `failure_simulator.py` | Latency spike, availability degradation, outage, restoration, and reset |
| `analytics.py` | Plotly chart builders for QoS comparison and health distribution |
| `explainability.py` | Human-readable recommendation explanations and comparison tables |
| `app.py` | Streamlit Cloud Command Center dashboard |

## 4. Project Structure

```
DynamicCloudQoS/
├── app.py                    # Streamlit dashboard
├── service_registry.py       # Cloud service data model
├── qos_evaluator.py          # QoS normalization and scoring
├── recommendation_engine.py  # Service ranking and selection
├── failure_simulator.py      # Fault injection and restoration
├── analytics.py              # Plotly visualization builders
├── explainability.py         # Decision explanation generator
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── tests/
    ├── __init__.py
    └── test_qos.py           # Automated test suite
```

## 5. QoS Mathematical Formulas

### Min-Max Normalization

**Benefit-type metrics** (higher is better — Availability, Reliability):

$$U_{\text{benefit}}(x) = \frac{x - x_{\min}}{x_{\max} - x_{\min}}$$

**Cost-type metrics** (lower is better — Latency, Cost):

$$U_{\text{cost}}(x) = \frac{x_{\max} - x}{x_{\max} - x_{\min}}$$

### Weighted Aggregate Score

$$Q(s) = \sum_{i=1}^{n} w_i \times q_i(s)$$

**Default weights:** Latency = 0.35, Cost = 0.20, Availability = 0.30, Reliability = 0.15

### Baseline Reference Bounds

Normalization uses **immutable baseline bounds** (not live min/max), ensuring that fault injection on one service does not distort the scores of other services.

## 6. Research Paper Result Reproduction

The prototype reproduces the baseline experimental benchmark figures captured in the research paper:

| Parameter | Research Paper Benchmark | Prototype Output | Verification Status |
| :--- | :--- | :--- | :--- |
| **Initial Active Services** | 5 / 5 Healthy | 5 / 5 Healthy | Exact Match |
| **Selected Service** | NovaCompute Standard (`SVC-C01`) | NovaCompute Standard (`SVC-C01`) | Exact Match |
| **Aggregate QoS Score** | 0.8168 | 0.8168 | Exact Match |
| **Best Alternative (Runner-up)** | Aether Compute HighPerf (`SVC-C02`) | Aether Compute HighPerf (`SVC-C02`) | Exact Match |
| **Alternative QoS Score** | 0.7937 | 0.7937 | Exact Match |
| **Score Margin ($\Delta Q$)** | 0.0231 | 0.0231 | Exact Match |
| **Normalized Latency** | 0.79 | 0.79 (0.7851) | Exact Match |
| **Normalized Cost** | 0.64 | 0.64 (0.6429) | Exact Match |
| **Normalized Availability** | 0.96 | 0.96 (0.9615) | Exact Match |
| **Normalized Reliability** | 0.83 | 0.83 (0.8333) | Exact Match |

## 7. Failure Scenarios

| Scenario | Effect | Reversible |
| :--- | :--- | :--- |
| **Latency Spike** | Adds +120ms to service latency | Yes (restore) |
| **Availability Degradation** | Reduces availability by 15 percentage points | Yes (restore) |
| **Service Outage** | Marks service as UNAVAILABLE | Yes (restore) |
| **Service Restoration** | Returns service to baseline values | — |
| **Reset Simulation** | Restores all services to original state | — |

## 8. Technologies Used

- **Python 3.10+** — Core language
- **Streamlit** — Interactive web dashboard
- **Pandas** — Data processing and table generation
- **NumPy** — Numerical calculations
- **Plotly** — Interactive charts and visualizations
- **Pytest** — Automated testing framework

## 9. Installation

```bash
# Clone or navigate to the project directory
cd DynamicCloudQoS

# Create and activate a virtual environment
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## 10. Running the Application

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## 11. Running Tests

```bash
pytest tests -v
```

## 12. Demonstration Script

### Step-by-step for academic review:

1. **Launch** — `streamlit run app.py` → Dashboard shows 5 healthy Compute services
2. **Observe initial state** — SVC-C01 (NovaCompute Standard) selected with highest QoS score
3. **Show ranking** — Scroll to QoS Analytics section to see service ranking chart
4. **Inject latency spike** — Select NovaCompute Standard in sidebar → Click "⚡ Latency Spike"
5. **Observe degradation** — QoS score drops, service may be reclassified as "Degraded"
6. **Trigger outage** — Click "🔴 Outage" on the same service
7. **Observe reselection** — Service becomes UNAVAILABLE, system automatically recommends next-best service
8. **Read explanation** — Expand "Selection Explanation" to see human-readable reasoning
9. **Restore service** — Select the failed service → Click "🔧 Restore"
10. **Observe recovery** — Original service returns to pool, rankings recalculated
11. **Reset** — Click "🔄 Reset Entire Simulation" to return to baseline state

## 13. Limitations

- **Synthetic data only** — Does not connect to real cloud infrastructure
- **Single-node execution** — Runs locally, not in a distributed environment
- **No machine learning** — Uses deterministic mathematical scoring, not ML prediction
- **No authentication** — Single-operator console without RBAC
- **Simulation scope** — Fault injection uses deterministic deltas, not stochastic models

## 14. Future Enhancements

1. Live cloud API connectors (AWS CloudWatch, Azure Monitor, Google Cloud Monitoring)
2. SLA constraint enforcement with hard-threshold filtering
3. Hysteresis anti-flapping to reduce unnecessary switching
4. Periodic background monitoring with health state classification
5. Multi-service DAG workflow composition
6. Role-based access control and authentication

---

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
**Purpose:** Academic demonstration prototype for QoS-aware service selection, failure simulation, and automatic reselection
