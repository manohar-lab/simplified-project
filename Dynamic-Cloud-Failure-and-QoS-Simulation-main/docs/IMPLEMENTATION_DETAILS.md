# Implementation Details & Module Specification

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Document Classification:** Codebase Engineering Reference & Algorithm Specification  
**Language & Runtime:** Python 3.10+ (Verified on Python 3.14.3 64-bit)  

---

## 1. Codebase Structure Overview

The source code is structured as a modular Python package located in `src/`, accompanied by the Streamlit application console in `app.py`, automated tests in `tests/`, and benchmarks in `experiments/`:

```text
Dynamic-Cloud-Failure-and-QoS-Simulation-main/
├── app.py                          # Streamlit UI Dashboard & Operating Console
├── benchmark_performance.py        # Independent Latency & Scalability Profiler
├── requirements.txt                # Runtime Dependencies
├── src/
│   ├── __init__.py                 # Package Exports & Version Metadata (v1.4.0)
│   ├── service_registry.py         # CloudService Dataclass & Synthetic Datasets
│   ├── qos_evaluator.py            # Bound Normalization & Weighted Utility Scoring
│   ├── sla_config.py               # SLA Threshold Configuration & Validation (Phase 1)
│   ├── hysteresis_config.py        # Hysteresis Thresholds & Cooldown Engine (Phase 2)
│   ├── monitoring_config.py        # Monitoring Configuration Dataclass (Phase 3)
│   ├── monitoring_engine.py        # Periodic Surveillance & Health State Machine (Phase 3)
│   ├── override_manager.py         # Dual Operating Modes & Override Safety (Phase 4)
│   ├── failure_simulator.py        # Fault Injection, Recovery & Global Reset
│   ├── recommendation_engine.py    # Multi-Stage Unified Decision Pipeline
│   ├── explainability.py           # Mathematical Score Breakdowns & Comparison Tables
│   └── analytics.py                # Health Classification & Plotly Chart Builders
```

---

## 2. Module-by-Module Technical Specification

### 2.1 Service Registry (`src/service_registry.py`)

#### Purpose
Defines the canonical data model for cloud services, calculates immutable reference bounds for normalization, and instantiates the synthetic baseline registry.

#### Key Data Structures
```python
@dataclass
class CloudService:
    service_id: str
    name: str
    category: str
    latency: float
    cost: float
    availability: float
    reliability: float
    operational_status: str = "AVAILABLE"
    baseline: Dict[str, Any] = field(default_factory=dict)
```

#### Key Functions
- `compute_reference_bounds(services: List[CloudService]) -> Dict[str, Dict[str, float]]`:  
  Iterates over candidate services grouped by category. Extracts `min_latency`, `max_latency`, `min_cost`, `max_cost`, `min_availability`, `max_availability`, `min_reliability`, `max_reliability`.
- `get_default_services() -> List[CloudService]`:  
  Returns fresh copies of the 7 synthetic candidates across `Compute` and `Storage` categories.

#### Immutability Guarantee
When `get_default_services()` runs, each service stores an immutable `baseline` dictionary. Even when simulation faults alter `service.latency` or `service.operational_status`, `service.baseline` remains untouched, preventing reference bound drift.

---

### 2.2 QoS Evaluation Engine (`src/qos_evaluator.py`)

#### Purpose
Transforms raw multi-criteria metrics with different physical units into comparable $[0.0, 1.0]$ utility scores, and computes weighted aggregate scores.

#### Mathematical Normalization Formulas
For lower-is-better metrics (Latency in ms, Invocation Cost in $):
$$U_{\text{lower}}(v) = \max\left(0.0, \min\left(1.0, \frac{\max_{\text{bound}} - v}{\max_{\text{bound}} - \min_{\text{bound}}}\right)\right)$$

For higher-is-better metrics (Availability in %, Reliability in %):
$$U_{\text{higher}}(v) = \max\left(0.0, \min\left(1.0, \frac{v - \min_{\text{bound}}}{\max_{\text{bound}} - \min_{\text{bound}}}\right)\right)$$

Zero-division protection: If $\max_{\text{bound}} \le \min_{\text{bound}}$, returns $1.0$.

#### Weighted Aggregate QoS Score
$$Q(s) = \sum_{m \in \{\text{lat}, \text{cost}, \text{avail}, \text{rel}\}} w_m \cdot U_m(s_m)$$
where $\sum w_m = 1.0$ and $w_m \ge 0$.

#### Key Classes
- `QoSEvaluator(reference_bounds: Optional[Dict[str, Dict[str, float]]])`:
  - `evaluate_service(service: CloudService, weights: Optional[Dict[str, float]]) -> MetricScores`: Evaluates a single service.
  - `evaluate_all(services: List[CloudService], weights: Optional[Dict[str, float]]) -> Dict[str, MetricScores]`: Batch scoring.
  - `validate_and_normalize_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]`: Normalizes weights to sum to 1.0; falls back to equal weights ($0.25$) if all are zero.

---

### 2.3 SLA Constraint Enforcement (`src/sla_config.py` — Phase 1)

#### Purpose
Enforces hard SLA constraints as non-negotiable boundaries. Any candidate violating an SLA constraint is excluded from ranking prior to QoS utility scoring.

#### Constraints Enforced
1. $\text{Latency} \le \text{Max Latency Threshold}$
2. $\text{Availability} \ge \text{Min Required Availability}$
3. $\text{Reliability} \ge \text{Min Required Reliability}$

#### Key Classes & Functions
```python
@dataclass
class SLAConfig:
    max_latency: float = 150.0
    min_availability: float = 98.0
    min_reliability: float = 97.0
```
- `__post_init__()`: Validates that thresholds are finite numbers, positive, and percentages reside within $[0.0, 100.0]$.
- `validate_service_sla(service: CloudService, sla_config: SLAConfig) -> List[str]`:  
  Returns an empty list `[]` if the service satisfies all SLAs. Otherwise, returns a list of human-readable violation descriptions. Handles `None`, `NaN`, and `Inf` safely.

---

### 2.4 Hysteresis & Anti-Flapping Mechanism (`src/hysteresis_config.py` — Phase 2)

#### Purpose
Prevents service flapping, migration overhead, and score oscillation when competing candidates experience minor performance fluctuations.

#### Switching Rules
Let $S_{\text{current}}$ be the currently selected provider, and $S_{\text{best}}$ be the highest-scoring eligible candidate:
- **Rule A (Initial Selection):** If no provider was previously selected, select $S_{\text{best}}$.
- **Rule B (Eligible Current Provider):** If $S_{\text{current}}$ is operational and SLA-compliant:
  - If $S_{\text{best}} == S_{\text{current}}$, retain $S_{\text{current}}$.
  - If $\Delta Q = Q(S_{\text{best}}) - Q(S_{\text{current}}) > \Delta_{\text{threshold}}$ AND cooldown elapsed, switch to $S_{\text{best}}$.
  - Otherwise, retain $S_{\text{current}}$.
- **Rule C (Emergency Outage):** If $S_{\text{current}}$ is `UNAVAILABLE`, immediately fail over to $S_{\text{best}}$ (bypasses threshold and cooldown).
- **Rule D (Emergency SLA Breach):** If $S_{\text{current}}$ violates SLA, immediately fail over to $S_{\text{best}}$ (bypasses threshold and cooldown).
- **Rule E (Empty Candidate State):** If no candidate is eligible, output `None` with `NO_SLA_COMPLIANT_SERVICE`.
- **Rule F (Recovery Consideration):** Recovered candidates are considered under Rule B; no bounce-back occurs unless improvement exceeds $\Delta_{\text{threshold}}$.

---

### 2.5 Periodic Monitoring Engine (`src/monitoring_config.py`, `src/monitoring_engine.py` — Phase 3)

#### Purpose
Executes autonomous background surveillance of registered services, classifies health states, maintains cycle statistics, and triggers reselection upon service degradation.

#### Health Classification Rules
- **`HEALTHY`:** Status is `AVAILABLE`, 0 SLA violations, and Latency $\le 1.2 \times \text{Baseline Latency}$.
- **`DEGRADED`:** Status is `AVAILABLE`, 0 SLA violations, but Latency $> 1.2 \times \text{Baseline Latency}$ or Availability $< 99.5\%$.
- **`CRITICAL`:** Status is `AVAILABLE`, but candidate is violating one or more SLA thresholds.
- **`DOWN`:** Operational status is `UNAVAILABLE` (outage).

#### Key Classes & Methods
- `MonitoringConfig`: Parameters for interval (seconds), enabled flag, and max history cap.
- `MonitoringEngine`:
  - `run_cycle(services: List[CloudService], category: str) -> MonitoringCycleResult`: Executes an evaluation cycle. Thread-safe using `threading.Lock`.
  - `start()`, `pause()`, `resume()`, `reset()`: Lifecycle control methods.
  - Event deduplication: Only records `SERVICE_HEALTH_CHANGED` events when a service's health state actually transitions.

---

### 2.6 Manual Service Override (`src/override_manager.py` — Phase 4)

#### Purpose
Enables authorized operators to lock the active service to an eligible candidate while strictly enforcing safety checks and automatic failover revocation.

#### Request Validation Pipeline
```python
def validate_manual_override_request(
    services: List[CloudService],
    category: str,
    requested_service_id: Optional[str],
    sla_config: Optional[SLAConfig] = None,
) -> OverrideValidationResult
```
Enforces four sequential guard conditions:
1. Candidate Existence Check: Target ID must exist in `services`.
2. Category Compatibility Check: Target service category must match active category.
3. Operational Status Check: Target service must not be `UNAVAILABLE`.
4. Hard SLA Constraint Check: Target service must have 0 SLA violations under `sla_config`.

#### Emergency Revocation
During execution in `RecommendationEngine.recommend()`:
If the manually overridden service experiences an outage or breaches SLA, `override_terminated` is set to `True`, operating mode reverts to `MODE_AUTOMATIC`, and emergency reselection chooses the highest-scoring eligible replacement.

---

### 2.7 Failure Simulation (`src/failure_simulator.py`)

#### Purpose
Simulates realistic cloud degradation and fault scenarios in a controlled, idempotent manner.

#### Fault Mutation Operations
- `inject_latency_spike(service_id: str, spike_ms: float)`: Adds `spike_ms` to current latency.
- `simulate_outage(service_id: str)`: Sets `operational_status = "UNAVAILABLE"`.
- `reduce_availability(service_id: str, drop_percent: float)`: Subtracts `drop_percent`, clamping at $0.0\%$.
- `restore_service(service_id: str)`: Resets single target service to its exact immutable baseline.
- `reset_simulation()`: Restores all services across all categories to baseline. Idempotent across multiple invocations.

---

### 2.8 Unified Recommendation Pipeline (`src/recommendation_engine.py`)

#### Purpose
Serves as the decision-making coordinator integrating SLA filtering, QoS utility scoring, hysteresis switching rules, and manual override management.

#### Output Dataclass
```python
@dataclass
class RecommendationResult:
    category: str
    selected_service: Optional[CloudService]
    selected_scores: Optional[MetricScores]
    ranked_eligible: List[Tuple[CloudService, MetricScores]]
    excluded_services: List[Tuple[CloudService, str]]
    selection_reason: str
    has_eligible_service: bool
    status_message: str
    status_code: str
    decision_type: str
    decision_reason: str
    best_alternative: Optional[CloudService]
    best_alternative_score: Optional[MetricScores]
    qos_improvement: float
    cooldown_active: bool
    operating_mode: str
    manual_override_active: bool
    override_terminated: bool
    override_termination_reason: str
```

---

### 2.9 Operations Dashboard (`app.py`)

#### Layout & Forward Compatibility
Built using Streamlit with four dedicated tabs:
1. **Tab 1: Overview & Recommendations:** KPI metric cards, active recommendation banner, candidate comparison table, and manual override control panel.
2. **Tab 2: QoS Comparative Analytics:** Normalized bar charts, multi-dimensional radar profiles, individual metric comparative bar charts, and weight donut chart.
3. **Tab 3: Failure Impact Analysis:** Before-and-After comparative delta cards, Plotly grouped impact chart, and baseline vs current metric differential table.
4. **Tab 4: Simulation & Decision History:** Four chronological audit tables:
   - Reselection Decision Audit Trail
   - Historical Metric Sequence Trajectory
   - Periodic Monitoring Event History
   - Operating Mode & Manual Override Event Log

#### Version-Aware Rendering Adapter
```python
def _render_full_width_kwargs() -> dict:
    # Passes width='stretch' on Streamlit >= 1.35; use_container_width=True on legacy
```
Ensures 100% clean console logs without Streamlit deprecation warnings.
