# Project Presentation: Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

**Academic Project Defense & Final Review Presentation**  
**Presenter:** Project Developer / Candidate  
**Academic Inspiration:** IEEE ICIMIA-2025 (*A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*)  
**Technology Stack:** Python 3.10+, Streamlit, Pandas, NumPy, Plotly, Pytest  

---

## Slide 1: Title Slide

### Slide Title
**Dynamic Cloud Failure Detection and QoS-Aware Service Reselection**
*A Deterministic, SLA-Enforced, and Anti-Flapping Cloud Service Recommendation Framework*

### Main Bullet Points
- **Domain:** Cloud Computing, Service-Oriented Architecture (SOA), and Autonomic Computing.
- **Core Focus:** Multi-attribute QoS evaluation, strict SLA constraint filtering, and intelligent reselection.
- **Key Innovations:** Zero-tolerance SLA enforcement, hysteresis anti-flapping ($\Delta H$), periodic autonomous health monitoring, and validated manual operator override with failover safety.
- **Presentation Date:** Academic Year 2026–2027.

### Suggested Visual
- University or Department crest alongside a high-level conceptual diagram showing a Cloud Gateway dynamically routing requests between multiple cloud candidate services (Compute, Storage).

### Presenter Notes
> *"Good morning, respected external examiners, faculty members, and colleagues. Today I am presenting my major project: 'Dynamic Cloud Failure Detection and QoS-Aware Service Reselection'. In modern multi-cloud architectures, services continuously experience latency spikes, availability degradation, and transient outages. Our goal is to build an autonomic recommendation engine that selects optimal cloud services, guarantees strict SLA compliance, prevents service flapping, and maintains continuous application availability."*

---

## Slide 2: Introduction & Motivation

### Slide Title
**Introduction: The Modern Multi-Cloud Dilemma**

### Main Bullet Points
- **API and Microservice Proliferation:** Modern applications compose tens or hundreds of distributed third-party APIs and cloud microservices.
- **Dynamic Quality of Service (QoS):** Cloud service performance is non-stationary; shared virtualization, network congestion, and hardware faults cause performance drift.
- **High Business Cost of Outages:** Even minutes of service unreliability or latency degradation translate into direct financial loss, SLA breach penalties, and customer churn.
- **The Challenge:** How can cloud-native applications autonomously detect degradation and switch to superior alternatives without human delay or unstable service flapping?

### Suggested Visual
- Graph showing cloud telemetry variability: latency spikes fluctuating over time alongside an SLA threshold line, showing moments where the active service breaches acceptable performance boundaries.

### Presenter Notes
> *"Cloud environments are fundamentally dynamic. While cloud providers offer high baseline service level guarantees, real-world networks experience latency jitter, noisy neighbors, and total outages. Manually detecting and reconfiguring service bindings is too slow and error-prone. What cloud architectures require is an autonomic system that monitors QoS continuously, enforces hard contractual SLAs, and reselects healthy alternatives in sub-millisecond time."*

---

## Slide 3: Problem Statement

### Slide Title
**Problem Statement: Fragility of Static Service Composition**

### Main Bullet Points
- **Static Binding Inflexibility:** Conventional cloud applications statically bind to a single service endpoint at deployment, failing when that endpoint experiences an outage.
- **Single-Metric Tunnel Vision:** Naive systems evaluate services based solely on cost or solely on latency, neglecting multi-attribute trade-offs.
- **Unconstrained Switching (Service Flapping):** Switching endpoints immediately whenever an alternative becomes marginally faster causes thrashing, connection resets, and cache thrashing.
- **Ignoring Hard SLA Boundaries:** Many optimization algorithms allow an exceptional cost score to mask an unacceptable latency violation, selecting services that violate contractual SLAs.

### Suggested Visual
- Conceptual illustration comparing:
  1. *Static System:* Fails completely when active provider crashes.
  2. *Naive Greedy System:* Rapidly flaps back and forth between two services due to minor jitter.
  3. *Proposed System:* Stabilized execution with intelligent, fail-safe switching.

### Presenter Notes
> *"The problem can be summarized into three core failures of existing approaches: First, static binding causes single-point-of-failure vulnerability. Second, naive multi-criteria algorithms often trade off hard constraints, choosing an unacceptably slow service just because it is cheap. Third, greedy dynamic switching causes 'flapping'—rapid oscillation between services due to harmless micro-jitter, which degrades system throughput."*

---

## Slide 4: Project Objectives

### Slide Title
**Project Objectives & Scope**

### Main Bullet Points
1. **Multi-Attribute QoS Evaluation:** Model candidate cloud services across 4 core dimensions: Latency (ms), Cost (\$), Availability (%), and Reliability (%).
2. **Strict Hard SLA Filtering:** Enforce contractual SLA constraints as non-negotiable prerequisites before score ranking.
3. **Anti-Flapping Hysteresis Engine:** Implement a configurable hysteresis threshold ($\Delta H$) and cooldown timer to eliminate unnecessary switching under micro-jitter.
4. **Periodic Autonomous Monitoring:** Build a non-blocking background engine that continuously evaluates candidate health states.
5. **Validated Manual Override:** Provide an authorized operator override mechanism protected by automated SLA validation and emergency failover guards.
6. **Transparent Explainability:** Deliver clear mathematical justifications, runner-up comparisons, and lossless audit trails via an interactive dashboard.

### Suggested Visual
- A six-pillar milestone graphic illustrating the progression from QoS Modeling $\to$ SLA Filtering $\to$ Hysteresis $\to$ Monitoring $\to$ Override $\to$ Explainability.

### Presenter Notes
> *"To address these challenges, we defined six concrete engineering objectives. Notice that our focus is not merely selecting the highest score, but guaranteeing strict SLA compliance, ensuring switching stability via hysteresis, maintaining continuous background monitoring, and providing complete explainability so cloud operators understand exactly why a service was chosen."*

---

## Slide 5: Existing Systems vs. Proposed Architecture

### Slide Title
**Comparative Analysis: Existing Solutions vs. Proposed Prototype**

### Main Bullet Points
| Feature | Static Binding | Greedy Scoring | Black-Box AI / DRL | Proposed System |
| :--- | :---: | :---: | :---: | :---: |
| **Dynamic Reselection** | ❌ No | ✅ Yes | ✅ Yes | ✅ **Yes (Sub-millisecond)** |
| **Strict SLA Disqualification** | ❌ No | ❌ Soft penalty | ❌ Reward trade-off | ✅ **Strict Hard Exclusion** |
| **Flapping Mitigation** | ❌ N/A | ❌ Severe thrashing | ⚠️ Complex reward | ✅ **Configurable $\Delta H$ & Cooldown** |
| **Autonomous Monitoring** | ❌ No | ⚠️ External | ⚠️ Offline trained | ✅ **Periodic In-Engine Telemetry** |
| **Decision Explainability** | ❌ None | ⚠️ Opaque score | ❌ Black-box weights | ✅ **Lossless Mathematical Audit** |
| **Manual Override Safety** | ❌ Static | ❌ No validation | ❌ Disables model | ✅ **Guarded with Failover** |

### Suggested Visual
- Comparative matrix chart highlighting green checkmarks for the proposed architecture across deterministic execution, SLA safety, and explainability.

### Presenter Notes
> *"When comparing existing solutions, static binding lacks resilience, while greedy scoring suffers from severe service flapping. On the other hand, complex deep reinforcement learning or neural network models act as black boxes—they cannot provide the strict, verifiable SLA compliance guarantees required by enterprise legal contracts. Our proposed system combines deterministic multi-attribute scoring with hard SLA filters, hysteresis stabilization, and complete mathematical explainability."*

---

## Slide 6: Proposed System Overview

### Slide Title
**Proposed System: Autonomic Resilience Lifecycle**

### Main Bullet Points
- **Autonomic Feedback Loop (MAPE-K):** Monitors candidate metrics, Analyzes health states, Plans optimal reselection, and Executes failover against a shared Knowledge base.
- **Two-Tier Decision Pipeline:**
  - *Tier 1 (Hard Eligibility):* Disqualifies unavailable candidates and hard SLA violators.
  - *Tier 2 (Soft Optimization):* Evaluates normalized weighted scores across compliant candidates.
- **Failover Priority Engine:** Differentiates between normal QoS optimization (governed by hysteresis) and emergency outages (immediate bypass of cooldown).
- **Dual Operating Modes:** Supports fully autonomous operation alongside operator-directed manual override.

### Suggested Visual
- High-level block diagram: Service Registry $\to$ SLA Filter $\to$ QoS Evaluator $\to$ Hysteresis Controller $\to$ Active Service Binding $\to$ Audit Log.

### Presenter Notes
> *"The proposed system operates as an Autonomic MAPE-K feedback loop. It implements a two-tier decision pipeline: Tier 1 is a hard filter that immediately eliminates any service that is down or breaches an SLA threshold. Tier 2 is a soft optimization engine that evaluates multi-attribute QoS scores only among the survivors. This guarantees that an ineligible service can never be recommended."*

---

## Slide 7: Technology Stack & Implementation Architecture

### Slide Title
**Technology Stack & Software Engineering Rigor**

### Main Bullet Points
- **Core Programming Language:** Python 3.10+ (type hints, dataclasses, deterministic execution).
- **Telemetry & Data Structures:** Pandas DataFrames (audit tables), NumPy (vectorized math).
- **Interactive UI Dashboard:** Streamlit (component-based, reactive state management).
- **Data Visualization:** Plotly Express & Plotly Graph Objects (interactive 4-axis radar charts, donuts, timelines).
- **Quality Assurance & Verification:** Pytest (122 automated unit, integration, and AppTest UI tests).
- **Benchmarking & Profiling:** Python `time.perf_counter()` (sub-microsecond timing) and `tracemalloc` (memory profiling).

### Suggested Visual
- Tech stack badge layout displaying Python, Streamlit, Pandas, Plotly, and Pytest logos.

### Presenter Notes
> *"The prototype is engineered in Python 3 using a modular architecture. For the user interface, we selected Streamlit combined with Plotly to deliver rich, reactive visualizations without heavy frontend overhead. To guarantee production-grade reliability, the entire codebase is verified by 122 automated tests covering units, boundary conditions, and headless UI automation through Streamlit AppTest."*

---

## Slide 8: System Architecture & Component Interactions

### Slide Title
**System Architecture: End-to-End Component Flow**

### Main Bullet Points
- **Candidate Registry (`service_registry.py`):** Maintains candidate metadata, categories, and computes baseline reference bounds $[Q_{min}, Q_{max}]$.
- **SLA Validator (`sla_config.py`):** Validates services against latency, availability, and reliability limits.
- **QoS Engine (`qos_evaluator.py`):** Executes min-max normalization and weighted score summation.
- **Hysteresis Manager (`hysteresis_config.py`):** Evaluates candidate delta $\Delta = Q_{new} - Q_{prev}$ against $\Delta H$.
- **Monitoring Daemon (`monitoring_engine.py`):** Runs periodic health reassessment cycles.
- **Override Manager (`override_manager.py`):** Manages manual selection, validation, and emergency termination.

### Suggested Visual
- Complete Mermaid architecture flowchart showing the interaction between the UI Dashboard, Recommendation Engine, and Core Subsystems.

### Presenter Notes
> *"This architectural diagram illustrates our clean separation of concerns. The Recommendation Engine coordinates between the SLA Validator, the QoS Evaluator, the Hysteresis Manager, and the Override Manager. Notice that telemetry mutations originating from the Failure Simulator flow directly into the monitoring engine, which triggers the recommendation pipeline whenever state changes occur."*

---

## Slide 9: QoS Evaluation Methodology

### Slide Title
**Multi-Attribute QoS Normalization & Scoring Formula**

### Main Bullet Points
- **Cost Attributes (Lower-is-Better — Latency, Cost):**
  $$N(q) = \frac{Q_{max} - q}{Q_{max} - Q_{min}}$$
- **Benefit Attributes (Higher-is-Better — Availability, Reliability):**
  $$N(q) = \frac{q - Q_{min}}{Q_{max} - Q_{min}}$$
- **Aggregate Weighted QoS Score:**
  $$\text{Score}(s) = \sum_{i=1}^{m} w_i \cdot N(q_i) \quad \text{where} \quad \sum_{i=1}^{m} w_i = 1.0, \quad w_i \ge 0$$
- **Dynamic Reference Bounds:** Bounds are computed across the candidate pool, preventing score distortion and guaranteeing $N(q) \in [0.0, 1.0]$.

### Suggested Visual
- Dual curve visualization showing cost-attribute normalization sloping downward from 1 to 0 vs. benefit-attribute normalization sloping upward from 0 to 1.

### Presenter Notes
> *"Normalization is mandatory because QoS attributes have vastly different units and scales: latency is in milliseconds, cost is in fractions of a dollar, and availability is a percentage. Furthermore, latency and cost are 'cost-type' attributes where smaller values are better, whereas availability and reliability are 'benefit-type' attributes. Our formulas normalize every dimension into a uniform zero-to-one range before applying the user-defined importance weights."*

---

## Slide 10: Strict SLA Constraint Enforcement

### Slide Title
**Hard SLA Constraint Enforcement: The Non-Negotiable Gate**

### Main Bullet Points
- **The SLA Contract:** Configured via centralized `SLAConfig`:
  - $\text{Latency}(s) \le \text{MaxAllowedLatency}$
  - $\text{Availability}(s) \ge \text{MinRequiredAvailability}$
  - $\text{Reliability}(s) \ge \text{MinRequiredReliability}$
- **Pre-Filtering Pipeline:** Disqualification occurs *before* candidate ranking:
  $$\text{Eligible}(s) = \text{IsAvailable}(s) \land \forall c \in \text{SLA}, \, \text{Satisfies}(s, c)$$
- **Zero-Tolerance Principle:** Even if a service achieves an aggregate score of $0.9999$ due to negligible cost, a single $1\text{ ms}$ latency breach permanently excludes it.
- **Fail-Safe Behavior:** If all candidates violate SLA, the system returns `None` rather than routing traffic to a non-compliant service.

### Suggested Visual
- Flow diagram showing candidate services entering an SLA Filter gate: non-compliant services are routed to the Disqualification Table with violation reasons, while compliant services proceed to QoS ranking.

### Presenter Notes
> *"In commercial cloud contracts, an SLA violation triggers legal penalties and downtime. Therefore, SLA thresholds cannot be treated as soft mathematical penalties in an optimization function. In our system, SLA enforcement is a hard binary gate: if a candidate violates even one threshold, it is immediately disqualified with an explicit reason logged in the audit trail. If all services fail, the system reports 'No Eligible Service Available' rather than masking the violation."*

---

## Slide 11: Failure Detection & Dynamic Reselection

### Slide Title
**Failure Detection & Emergency Reselection**

### Main Bullet Points
- **Dynamic Fault Simulator (`failure_simulator.py`):**
  - *Latency Spike:* Injects network delays (+150 ms) to trigger SLA latency breaches.
  - *Availability Degradation:* Reduces uptime (-5%) to simulate intermittent packet drops.
  - *Total Outage:* Forces `UNAVAILABLE` status ($0.0\%$ uptime/reliability) to simulate crash faults.
- **Emergency Bypass of Hysteresis:**
  - Normal switching requires improvement $\ge \Delta H$ and cooldown expiry.
  - **Emergency Rule:** If the currently active service suffers an outage or SLA violation, hysteresis cooldown is **instantly bypassed**.
- **Reselection Performance:**
  - Outage Detection Latency: **$0.0009\text{ ms}$ ($0.9\text{ µs}$)**.
  - Emergency Reselection Latency: **$0.0386\text{ ms}$ ($38.6\text{ µs}$)**.

### Suggested Visual
- State transition diagram showing the transition from `HEALTHY` $\to$ `DEGRADED` / `UNAVAILABLE` $\to$ Emergency Reselection Trigger $\to$ `ACTIVE` alternative.

### Presenter Notes
> *"To rigorously evaluate reselection, we developed an integrated fault simulator supporting latency spikes, availability drops, and total outages. When the active service experiences an outage, our engine detects the fault in under one microsecond and completes emergency reselection in 38 microseconds. Most importantly, it immediately bypasses hysteresis and cooldown timers, because protecting system uptime supersedes anti-flapping concerns."*

---

## Slide 12: Hysteresis, Monitoring & Manual Override

### Slide Title
**Hysteresis Stabilization, Periodic Monitoring & Guarded Override**

### Main Bullet Points
- **Anti-Flapping Hysteresis:**
  $$\text{Switch Condition:} \quad \text{Score}(s_{new}) - \text{Score}(s_{curr}) \ge \Delta H \quad (\Delta H = 0.05)$$
  - Prevents ping-pong switching under minor telemetry noise; verified **100% flapping reduction**.
- **Autonomous Monitoring Engine:**
  - Non-blocking periodic daemon evaluating candidate health states (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `RECOVERED`).
  - Monitoring overhead: **$0.380\text{ ms}$ per cycle**, requiring only **$6.26\text{ KB}$** peak RAM.
- **Validated Manual Override:**
  - Authorized operators can lock selection to a preferred service.
  - **Guarded Safety:** Manual selection must satisfy hard SLAs; if an overridden service crashes, the system revokes the override and fails over automatically.

### Suggested Visual
- Diagram showing dual operating tracks:
  1. Autonomous Track (governed by Hysteresis and Periodic Monitoring).
  2. Manual Override Track (governed by Operator Input with Safety Revocation Guard).

### Presenter Notes
> *"Slide 12 highlights our three primary reliability mechanisms. First, the hysteresis threshold delta H prevents service flapping when candidate rankings fluctuate marginally. Second, the periodic monitoring engine runs in the background with negligible overhead, tracking health transitions. Third, our manual override mode gives human operators full authority to choose an eligible service, while guaranteeing that if that service fails, the system automatically revokes the override and triggers failover."*

---

## Slide 13: Dashboard Walkthrough & Live Demonstration

### Slide Title
**Streamlit Interactive Dashboard & Demonstration Flow**

### Main Bullet Points
- **Top KPI Cards:** Instant visibility into Active Service, QoS Score, Operating Mode, and Health State.
- **Tab 1 — Live Recommendation:** Ranked candidate table, eligibility badges, and runner-up delta margins.
- **Tab 2 — Health Telemetry:** Health distribution donut chart, active failure alerts, and monitoring event logs.
- **Tab 3 — Comparative Analytics:** 4-axis interactive Plotly radar chart displaying trade-off surfaces.
- **Tab 4 — Audit Trail & Explainability:** Lossless chronological log of all switching decisions and justifications.
- **Live Demo Flow:** Normal Baseline $\to$ Latency Spike $\to$ SLA Disqualification $\to$ Outage Failover $\to$ Manual Override $\to$ Safety Revocation.

### Suggested Visual
- Split-screen annotated UI screenshot showing the Sidebar controls, Top KPI metric cards, and Tab 1 Candidate Comparison Table.

### Presenter Notes
> *"The Streamlit dashboard serves as our evaluation and operational console. It is structured into top-level KPI summary cards, a persistent control sidebar for fault injection and configuration, and four analytical tabs. During our live demonstration, we walked through the complete lifecycle: normal baseline scoring, injecting a latency spike that triggered an SLA disqualification, simulating a total outage with instantaneous failover, and validating manual override with safety revocation."*

---

## Slide 14: Experimental Results & Comparative Evaluation

### Slide Title
**Empirical Benchmarks & Comparative Evaluation**

### Main Bullet Points
- **100-Step Comparative Baseline Simulation:**
  | Metric | Random Selection | Greedy Scoring | SLA-Aware (No Hysteresis) | **Proposed System** |
  | :--- | :---: | :---: | :---: | :---: |
  | **SLA Compliance Rate** | 62.0% | 74.0% | 100.0% | **100.0%** |
  | **Service Outage Exposure** | 18.0% | 12.0% | 0.0% | **0.0%** |
  | **Total Switching Events** | 46 switches | 68 switches | 17 switches | **1 switch (94.1% reduction)** |
- **Algorithmic Latency & Scalability:**
  - Base Recommendation Latency: **$0.0672\text{ ms}$** ($67.2\text{ µs}$).
  - Scalability at 1,000 Services: **$17.71\text{ ms}$** total pipeline execution (**$56,473\text{ services/sec}$**).
- **Test Suite Verification:** **122 of 122 tests passed (100% pass rate in 11.44s)**.

### Suggested Visual
- Bar chart illustrating the dramatic reduction in switching events (flapping) comparing Greedy (68) vs SLA-Aware (17) vs Proposed System (1), alongside 100% SLA compliance.

### Presenter Notes
> *"Our empirical evaluation demonstrates the clear superiority of the proposed framework. In a 100-step dynamic simulation under stochastic jitter, naive greedy scoring triggered 68 switching events, causing severe thrashing. Adding SLA awareness achieved 100% compliance but still caused 17 switches. Our proposed unified system maintained 100% SLA compliance and zero outage exposure while reducing switching events to just 1—a 94.1% stability improvement. Furthermore, performance benchmarks prove the engine can evaluate over 56,000 services per second."*

---

## Slide 15: Conclusion & Future Research Scope

### Slide Title
**Conclusion & Future Research Directions**

### Main Bullet Points
- **Project Achievements:**
  - Successfully developed an end-to-end, deterministic cloud failure detection and reselection prototype.
  - Enforced zero-tolerance hard SLA constraints and sub-millisecond emergency failover.
  - Eliminated service flapping via configurable hysteresis ($\Delta H$) and cooldown counters.
  - Verified 100% test passing rate across 122 automated test suites.
- **Academic Scope Boundaries & Future Work:**
  - *Live Multi-Cloud Telemetry:* Transition from synthetic simulation to live OpenTelemetry collectors and cloud APIs (AWS CloudWatch, GCP Cloud Monitoring).
  - *DAG Workflow Composition:* Extend from atomic single-service selection to composite multi-stage service graphs.
  - *Adaptive Learning:* Integrate lightweight online reinforcement learning for dynamic weight tuning based on observed request patterns.

### Suggested Visual
- Roadmap diagram illustrating the transition from current Prototype $\to$ OpenTelemetry Collector $\to$ Multi-Cloud Live Deployment $\to$ Composite Workflow Orchestration.

### Presenter Notes
> *"In conclusion, this project demonstrates that cloud service reselection can be made resilient, stable, and deterministic without sacrificing execution speed or explainability. By enforcing strict SLA boundaries, applying hysteresis to eliminate flapping, and supporting guarded manual overrides, we have constructed a robust framework for autonomic cloud management. Future extensions will bridge this simulation prototype with live cloud monitoring APIs and composite DAG workflows. Thank you, and I look forward to your questions."*

