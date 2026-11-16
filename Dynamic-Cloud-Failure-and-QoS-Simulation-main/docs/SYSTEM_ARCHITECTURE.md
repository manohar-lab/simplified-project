# System Architecture & Technical Design

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Document Classification:** Architectural Specification & Component Interaction Guide  
**Release Target:** Release Candidate (RC-1.0.0)  

---

## 1. Architectural Overview & Design Principles

The **Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** system is designed as a modular, deterministic, and explainable software platform for evaluating cloud services, enforcing hard Service Level Agreement (SLA) constraints, suppressing service flapping, and automating emergency failover.

The architecture adheres to six core software engineering principles:
1. **Separation of Concerns:** Clear isolation between the candidate registry (`service_registry`), multi-criteria utility evaluation (`qos_evaluator`), SLA constraint filtering (`sla_config`), switching stability (`hysteresis_config`), background health surveillance (`monitoring_engine`), operator control (`override_manager`), and visualization (`app.py`, `analytics.py`).
2. **Immutable Baseline Reference Bounds:** Normalization bounds ($\min$ and $\max$ per category) are anchored to pre-computed baseline states. Degradation or failure in one candidate never warps or artificially inflates the normalized utility scores of competitor services.
3. **Multi-Stage Decision Pipeline:** Recommendation proceeds through a strict linear pipeline: `Category Filtering` $\to$ `Outage Disqualification` $\to$ `Hard SLA Validation` $\to$ `Multi-Attribute Utility Scoring` $\to$ `Deterministic Tie-Breaking` $\to$ `Hysteresis Switching Control` $\to$ `Manual Override Enforcement`.
4. **Hard Constraint Superiority:** SLA requirements represent non-negotiable boundaries evaluated *prior* to QoS scoring. High aggregate scores can never compensate for or bypass an SLA breach.
5. **Fail-Safe Emergency Bypass:** While normal performance-driven switching requires a significant improvement threshold ($\Delta Q \ge 0.05$) and respects cooldown timers, service outages and SLA breaches immediately trigger emergency reselection.
6. **Zero Memory Leaks & Linear Scalability:** All data structures use lightweight Python dataclasses, bounded history structures, and vectorized Pandas transformations, ensuring sub-20ms scalability to 1,000 services.

---

## 2. Overall System Architecture Diagram

```mermaid
flowchart TD
    subgraph UI_Layer["User Interface & Presentation Layer (Streamlit)"]
        UI_Dash["Streamlit Operations Console (app.py)"]
        UI_KPI["System Health & KPI Summary Cards"]
        UI_Sidebar["Fault Injection & Config Sidebar"]
        UI_Tabs["4-Tab Analytics: Overview, QoS Charts, Impact, Audit Trail"]
    end

    subgraph Control_Layer["Supervisory & Control Layer"]
        Sim["Failure Simulator (failure_simulator.py)"]
        Mon["Periodic Monitoring Engine (monitoring_engine.py)"]
        Ovr["Manual Override Manager (override_manager.py)"]
    end

    subgraph Decision_Pipeline["Unified Recommendation & Decision Pipeline (recommendation_engine.py)"]
        Filter_Cat["1. Category Filter"]
        Filter_Outage["2. Operational Availability Check"]
        Filter_SLA["3. Hard SLA Constraint Filter (sla_config.py)"]
        Scorer["4. Weighted QoS Utility Scorer (qos_evaluator.py)"]
        Ranker["5. Deterministic Tie-Breaker & Ranking"]
        Hyst["6. Hysteresis Switching Rules A-F (hysteresis_config.py)"]
        Ovr_Check["7. Manual Override Enforcement & Revocation"]
        Explainer["8. Decision Explanation & Audit (explainability.py)"]
    end

    subgraph Data_Layer["Registry & State Management Layer"]
        Reg["Cloud Service Registry (service_registry.py)"]
        RefBounds["Immutable Baseline Reference Bounds"]
        AuditHistory["Append-Only Reselection & History Trackers"]
    end

    UI_Sidebar -->|"Injects Faults (Latency/Outage/Drop)"| Sim
    UI_Sidebar -->|"Configures SLA & Hysteresis"| Decision_Pipeline
    UI_Sidebar -->|"Configures Polling Interval"| Mon
    UI_Tabs -->|"Requests Manual Selection"| Ovr

    Sim -->|"Mutates Runtime State"| Reg
    Mon -->|"Periodic Health Surveillance"| Reg
    Mon -->|"Triggers Reselection"| Decision_Pipeline
    Ovr -->|"Validates Manual Request"| Filter_SLA

    Reg -->|"Supplies Candidate Pool"| Filter_Cat
    RefBounds -.->|"Normalizes Metrics"| Scorer
    Decision_Pipeline -->|"Outputs Selected Winner"| UI_Dash
    Decision_Pipeline -->|"Logs Decisions"| AuditHistory
    AuditHistory -->|"Populates DataFrames & Plotly"| UI_Tabs
```

---

## 3. Workflow Diagrams

### 3.1 QoS Evaluation Workflow

The evaluation engine scales multi-attribute raw metrics with different physical units into comparable $[0.0, 1.0]$ utility scores using baseline-anchored bounds:

```mermaid
flowchart LR
    Raw["Raw Candidate Metrics: Latency (ms), Cost ($), Availability (%), Reliability (%)"]
    Bounds["Immutable Category Reference Bounds: Min/Max for each metric"]
    Weights["Configurable Priorities: W_lat (0.35), W_cost (0.20), W_avail (0.30), W_rel (0.15)"]

    subgraph Normalization["Bound Normalization Logic"]
        Norm_Lat["Latency (Lower is Better): (Max - Val) / (Max - Min)"]
        Norm_Cost["Cost (Lower is Better): (Max - Val) / (Max - Min)"]
        Norm_Avail["Availability (Higher is Better): (Val - Min) / (Max - Min)"]
        Norm_Rel["Reliability (Higher is Better): (Val - Min) / (Max - Min)"]
    end

    Clamping["Clamp to Range [0.0, 1.0]"]
    WeightedSum["Weighted Aggregate Sum: Total = Sum(W_i * Score_i)"]
    MetricScoresObj["MetricScores Object: LatencyScore, CostScore, AvailScore, RelScore, QoSScore"]

    Raw --> Normalization
    Bounds --> Normalization
    Normalization --> Clamping
    Clamping --> WeightedSum
    Weights --> WeightedSum
    WeightedSum --> MetricScoresObj
```

---

### 3.2 Failure Detection Workflow

Failures are detected dynamically through runtime mutation inspection or background surveillance:

```mermaid
flowchart TD
    Start["Fault Injection or Periodic Health Check"]
    Check_Status{"Is Operational Status == AVAILABLE?"}
    Mark_Outage["Flag as UNAVAILABLE (Outage)"]
    Check_Lat{"Is Latency <= Max Permitted Latency?"}
    Mark_Lat_Viol["Record Violation: Latency SLA Exceeded"]
    Check_Avail{"Is Availability >= Min Required Availability?"}
    Mark_Avail_Viol["Record Violation: Availability SLA Breached"]
    Check_Rel{"Is Reliability >= Min Required Reliability?"}
    Mark_Rel_Viol["Record Violation: Reliability SLA Breached"]
    Evaluate_Compliant{"Any Violations Recorded?"}
    Mark_Ineligible["Mark Service as INELIGIBLE (Hard SLA Disqualification)"]
    Mark_Eligible["Mark Service as ELIGIBLE for QoS Scoring"]

    Start --> Check_Status
    Check_Status -- "No (Outage)" --> Mark_Outage --> Mark_Ineligible
    Check_Status -- "Yes" --> Check_Lat
    Check_Lat -- "Violated" --> Mark_Lat_Viol --> Check_Avail
    Check_Lat -- "Satisfied" --> Check_Avail
    Check_Avail -- "Violated" --> Mark_Avail_Viol --> Check_Rel
    Check_Avail -- "Satisfied" --> Check_Rel
    Check_Rel -- "Violated" --> Mark_Rel_Viol --> Evaluate_Compliant
    Check_Rel -- "Satisfied" --> Evaluate_Compliant
    Evaluate_Compliant -- "Yes (>= 1 Violation)" --> Mark_Ineligible
    Evaluate_Compliant -- "No (0 Violations)" --> Mark_Eligible
```

---

### 3.3 Dynamic Service Reselection Workflow (Hysteresis Decision Engine)

The decision engine applies formal rules (Rules A through F) to decide whether to retain the currently selected service or execute a switch:

```mermaid
flowchart TD
    Trigger["Reselection Triggered (Health Change, SLA Breach, Timer, or User Action)"]
    Eval_Pool["Evaluate Eligible Candidates Pool (Status == AVAILABLE & 0 SLA Violations)"]
    Has_Eligible{"Eligible Candidates Pool > 0?"}
    No_Service["Return None (Status: NO_SLA_COMPLIANT_SERVICE)"]
    Has_Current{"Was a Service Previously Selected?"}
    Rule_A["Rule A (Initial Selection): Select Top-Scoring Eligible Candidate"]
    Check_Curr_Status{"Is Currently Selected Service UNAVAILABLE?"}
    Rule_C["Rule C (Emergency Outage): Bypass Cooldown/Hysteresis; Switch to Best Alternative"]
    Check_Curr_SLA{"Does Currently Selected Service Violate SLA?"}
    Rule_D["Rule D (Emergency SLA Violation): Bypass Cooldown/Hysteresis; Switch to Best Alternative"]
    Check_Best{"Is Currently Selected Service Already Ranked #1?"}
    Rule_B_Retain1["Rule B (Already Optimal): Retain Current Service"]
    Calc_Delta["Calculate QoS Improvement: Delta = Score(BestAlt) - Score(Current)"]
    Check_Cooldown{"Is Switching Cooldown Active?"}
    Rule_B_Cooldown["Rule B (Cooldown Active): Block Switch; Retain Current Service"]
    Check_Threshold{"Is Delta > Hysteresis Threshold (e.g. 0.05)?"}
    Rule_B_Switch["Rule B (Justified Improvement): Switch to Best Alternative"]
    Rule_B_Retain2["Rule B (Minor Fluctuation): Damped by Hysteresis; Retain Current Service"]

    Trigger --> Eval_Pool
    Eval_Pool --> Has_Eligible
    Has_Eligible -- "No" --> No_Service
    Has_Eligible -- "Yes" --> Has_Current
    Has_Current -- "No (Initial Run)" --> Rule_A
    Has_Current -- "Yes" --> Check_Curr_Status
    Check_Curr_Status -- "Yes (Outage)" --> Rule_C
    Check_Curr_Status -- "No" --> Check_Curr_SLA
    Check_Curr_SLA -- "Yes (Breached)" --> Rule_D
    Check_Curr_SLA -- "No (Healthy & Compliant)" --> Check_Best
    Check_Best -- "Yes" --> Rule_B_Retain1
    Check_Best -- "No" --> Calc_Delta
    Calc_Delta --> Check_Cooldown
    Check_Cooldown -- "Yes" --> Rule_B_Cooldown
    Check_Cooldown -- "No" --> Check_Threshold
    Check_Threshold -- "Yes (Delta >= 0.05)" --> Rule_B_Switch
    Check_Threshold -- "No (Delta < 0.05)" --> Rule_B_Retain2
```

---

### 3.4 Monitoring & Recovery Lifecycle Workflow

The background monitoring engine evaluates health transitions across the four-tier lifecycle:

```mermaid
stateDiagram-v2
    [*] --> HEALTHY: Service Initialized at Baseline

    HEALTHY --> DEGRADED: Latency increases (> 1.2x baseline) or Availability drops
    HEALTHY --> CRITICAL: Latency approaches SLA limit or Availability < 99.0%
    HEALTHY --> DOWN: Operational Status transitions to UNAVAILABLE
    
    DEGRADED --> HEALTHY: Metrics improve to baseline
    DEGRADED --> CRITICAL: Degradation worsens
    DEGRADED --> DOWN: Service suffers Outage

    CRITICAL --> DEGRADED: Partial Metric Recovery
    CRITICAL --> DOWN: Total Outage
    CRITICAL --> HEALTHY: Metrics fully restored

    DOWN --> HEALTHY: Service Restored (Single Restore or Global Reset)
    
    note right of DOWN
        Triggers Emergency Reselection
        Bypasses Hysteresis Cooldown
    end note
    
    note right of HEALTHY
        Reconsidered under Rule F
        Requires Delta > 0.05 to switch
    end note
```

---

### 3.5 Manual Override Operating Mode Workflow

Dual operating modes (`AUTOMATIC` and `MANUAL_OVERRIDE`) are governed with hard fail-safe protection:

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Dashboard Operator
    participant UI as Streamlit Console
    participant Mgr as ManualOverrideManager
    participant Eng as RecommendationEngine
    participant Reg as CloudService Registry

    Note over Operator,Eng: Mode: AUTOMATIC (Algorithmic Selection)
    Operator->>UI: Selects candidate SVC-C04 and provides audit reason
    Operator->>UI: Clicks "Activate Manual Override"
    UI->>Mgr: request_manual_override(services, "Compute", "SVC-C04", sla, reason)
    Mgr->>Mgr: Validate existence, category, status == AVAILABLE, SLA compliance
    alt Validation Rejection (e.g. SLA violated or Outage)
        Mgr-->>UI: is_valid = False, Rejection Reason
        UI-->>Operator: Displays red error banner; Mode remains AUTOMATIC
    else Validation Success
        Mgr->>Mgr: Transition Mode to MANUAL_OVERRIDE; lock requested_id = SVC-C04
        Mgr->>Mgr: Log MANUAL_OVERRIDE_ACTIVATED event
        Mgr-->>UI: is_valid = True
        UI-->>Operator: Displays amber warning banner: Active Manual Override
    end

    Note over Operator,Reg: Runtime Fault Injected on SVC-C04
    Reg->>Reg: Latency spikes to 180ms (SLA Breach) or Outage strikes
    UI->>Eng: recommend(services, mode=MANUAL, manual_id=SVC-C04)
    Eng->>Eng: Detects active manual service violates SLA or is UNAVAILABLE
    Eng->>Eng: Set override_terminated = True
    Eng->>Mgr: clear_override("Emergency SLA Violation Revocation")
    Mgr->>Mgr: Transition Mode to AUTOMATIC; clear lock
    Eng->>Eng: Fall back to best eligible automatic candidate (SVC-C01)
    Eng-->>UI: Output recommendation with failover notice
    UI-->>Operator: Alert: Manual Override Terminated due to SLA breach
```

---

## 4. Component Interaction Matrix

| Subsystem Component | Inputs | Outputs | Primary Interfacing Modules |
| :--- | :--- | :--- | :--- |
| **`CloudService`** | Hardware/network parameters | Standardized service representation | All modules |
| **`QoSEvaluator`** | Service metrics, Category reference bounds, Weights | `MetricScores` (individual + composite score) | `recommendation_engine`, `analytics` |
| **`SLAConfig`** | Max latency, Min availability, Min reliability | Boolean eligibility, Violation string list | `recommendation_engine`, `override_manager` |
| **`HysteresisConfig`**| Improvement threshold ($\Delta Q$), Cooldown duration | Boolean switching permission | `recommendation_engine` |
| **`MonitoringEngine`**| Polling interval, Service registry, SLA config | Cycle summaries, Deduplicated events, Health states | `recommendation_engine`, `app.py` |
| **`ManualOverrideManager`**| Operator requested service ID, Audit reason | Operating mode, Override locks, Transition events | `recommendation_engine`, `app.py` |
| **`RecommendationEngine`**| Services pool, Category, SLA, Hysteresis, Override | `RecommendationResult` (Winner, Scores, Rationale)| `app.py`, `monitoring_engine`, `analytics` |
| **`FailureSimulator`** | Target service ID, Fault magnitude | Mutated `CloudService` runtime attributes | `service_registry`, `app.py` |
| **`Explainability`** | Candidate scores, Historical decisions | Markdown breakdowns, Comparison DataFrames | `app.py` |
| **`Analytics`** | Snapshot history, Simulation events | Plotly visual figures (Bar, Radar, Timeline) | `app.py` |
