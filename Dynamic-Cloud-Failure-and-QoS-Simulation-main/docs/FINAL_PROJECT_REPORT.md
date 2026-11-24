# Dynamic Cloud Failure Detection and QoS-Aware Service Reselection
## Final Academic Project Report

**Degree / Course Requirement:** Major Capstone Project in Computer Science and Engineering / Cloud Computing  
**Academic Reference:** Inspired by IEEE ICIMIA-2025 (*A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*)  
**Authorship / Role:** Senior Software Documentation Engineer, Academic Project Reviewer, and Technical Report Specialist  
**Submission Date:** November 2026  
**Status:** Complete & Submission-Ready (Release Candidate RC-1.0.0)  

---

## Table of Contents

1. [Chapter 1: Introduction](#chapter-1-introduction)
2. [Chapter 2: Problem Statement](#chapter-2-problem-statement)
3. [Chapter 3: Project Objectives](#chapter-3-project-objectives)
4. [Chapter 4: Existing System](#chapter-4-existing-system)
5. [Chapter 5: Proposed System](#chapter-5-proposed-system)
6. [Chapter 6: Literature Review](#chapter-6-literature-review)
7. [Chapter 7: Software and Hardware Requirements](#chapter-7-software-and-hardware-requirements)
8. [Chapter 8: System Architecture](#chapter-8-system-architecture)
9. [Chapter 9: System Design and Module Description](#chapter-9-system-design-and-module-description)
10. [Chapter 10: Methodology](#chapter-10-methodology)
11. [Chapter 11: QoS Evaluation and Scoring Method](#chapter-11-qos-evaluation-and-scoring-method)
12. [Chapter 12: SLA-Based Service Eligibility](#chapter-12-sla-based-service-eligibility)
13. [Chapter 13: Failure Detection and Simulation](#chapter-13-failure-detection-and-simulation)
14. [Chapter 14: Dynamic Service Reselection](#chapter-14-dynamic-service-reselection)
15. [Chapter 15: Hysteresis and Anti-Flapping](#chapter-15-hysteresis-and-anti-flapping)
16. [Chapter 16: Periodic Monitoring](#chapter-16-periodic-monitoring)
17. [Chapter 17: Manual Service Override](#chapter-17-manual-service-override)
18. [Chapter 18: Implementation Details](#chapter-18-implementation-details)
19. [Chapter 19: Experimental Setup](#chapter-19-experimental-setup)
20. [Chapter 20: Results and Performance Analysis](#chapter-20-results-and-performance-analysis)
21. [Chapter 21: Testing and Validation](#chapter-21-testing-and-validation)
22. [Chapter 22: Advantages and Limitations](#chapter-22-advantages-and-limitations)
23. [Chapter 23: Future Enhancements](#chapter-23-future-enhancements)
24. [Chapter 24: Conclusion](#chapter-24-conclusion)
25. [Chapter 25: References](#chapter-25-references)

---

## Chapter 1: Introduction

Modern enterprise software systems, cloud-native architectures, and microservice pipelines increasingly rely on third-party cloud service providers for core functionality, such as compute workers, managed databases, storage endpoints, and specialized inference APIs. While cloud providers offer published Service Level Agreements (SLAs), real-world operational environments frequently experience transient network congestion, latency degradation, packet loss, hardware throttling, and total provider outages.

When an active cloud service degrades or fails, workflow execution stalls, end-to-end response times balloon, and downstream dependent tasks violate their service agreements. To mitigate these risks, automated Quality of Service (QoS)-aware service reselection mechanisms are necessary. 

This project, **Dynamic Cloud Failure Detection and QoS-Aware Service Reselection**, presents an end-to-end, deterministic, and explainable software simulation prototype. The system continuously evaluates candidate cloud services across multi-attribute QoS parameters (latency, invocation cost, availability, reliability), enforces hard SLA constraints as non-negotiable filtering boundaries, prevents service flapping through hysteresis damping, executes autonomous background surveillance, and provides fail-safe operator overrides.

---

## Chapter 2: Problem Statement

Distributed cloud workflows and microservices depend on external cloud services that exhibit non-stationary, unpredictable runtime behavior. The fundamental challenges in existing cloud management systems include:
1. **Static SLA Vulnerability:** Traditional service composition frameworks rely on static, design-time SLA contracts and fail to react to dynamic runtime QoS degradation.
2. **SLA Violations under Pure QoS Optimization:** Unconstrained multi-attribute scoring frameworks often select services with strong aggregate scores (e.g., low cost) even when they violate hard latency or availability constraints.
3. **Service Flapping and Migration Churn:** Naive reactive reselection engines switch providers whenever a competitor exhibits a negligible utility advantage (e.g., $< 1\%$). This causes rapid oscillation (flapping), incurring excessive API re-binding, connection teardown, and operational overhead.
4. **Lack of Explainability:** Black-box optimization techniques (such as Deep Reinforcement Learning) lack mathematical transparency, making it difficult for cloud site reliability engineers (SREs) to understand why a failover occurred.
5. **Absence of Operator Controls:** Fully autonomous reselection engines often prevent human operators from intervening during compliance reviews or scheduled maintenance.

---

## Chapter 3: Project Objectives

The primary objectives of this project are:
1. **Multi-Attribute QoS Evaluation:** Develop a mathematical normalization and scoring engine anchored to immutable baseline reference bounds to evaluate candidate services across Latency, Cost, Availability, and Reliability.
2. **Strict SLA Constraint Enforcement:** Implement hard constraint filtering that immediately disqualifies any candidate violating configured maximum latency, minimum availability, or minimum reliability thresholds *prior* to utility scoring.
3. **Anti-Flapping Hysteresis Damping:** Implement an intelligent switching policy requiring candidate score improvements to exceed a configurable delta ($\Delta Q \ge 0.05$) before migrating away from an eligible current provider.
4. **Autonomous Emergency Failover:** Guarantee that operational outages and hard SLA breaches immediately bypass hysteresis damping to execute microsecond failover.
5. **Periodic Background Surveillance:** Engineer a thread-safe monitoring engine capable of classifying service health (`HEALTHY`, `DEGRADED`, `CRITICAL`, `DOWN`) and logging deduplicated state transitions.
6. **Controlled Manual Override:** Support dual operating modes (`AUTOMATIC` vs `MANUAL_OVERRIDE`) allowing authorized operators to select specific eligible services with automatic emergency revocation.
7. **Comprehensive Visual Operations Console:** Develop a modern, interactive Streamlit operations dashboard featuring KPI cards, Plotly visualizations, before/after impact analysis, and chronological audit trails.
8. **Empirical Benchmarking & Validation:** Verify system performance across automated unit tests, headless UI automation, and scalability evaluations up to 1,000 services.

---

## Chapter 4: Existing System

In existing cloud service brokerage and selection architectures:
- **Static Brokerage:** Services are selected once at deployment time based on advertised SLA documentation. Runtime degradation is ignored until complete system failure occurs.
- **Unconstrained Greedy Scoring:** Systems calculate a weighted utility score across available services. However, a service with low cost and high historical availability can achieve a high aggregate score even while its response latency degrades to 200 ms, violating real-time SLA contracts.
- **Undamped Reactive Reselection:** Systems that monitor performance often switch providers on infinitesimal score variations ($Q_A = 0.810$ vs $Q_B = 0.811$). In noisy cloud networks, this produces severe flapping.
- **Limitations of Existing Systems:**
  - High SLA failure rates (typically 20% to 40% breach rates during degradation).
  - High switching churn and API reconnection overhead.
  - Zero explainability regarding mathematical reselection causes.

---

## Chapter 5: Proposed System

The proposed system addresses the limitations of existing frameworks through a unified, multi-stage decision pipeline:
1. **Immutable Baseline Reference Bounds:** Normalization bounds ($\min$ and $\max$ per metric) are anchored to pre-computed baseline states. When a service experiences an outage or latency spike, competitor scores remain stable.
2. **Strict Pre-Scoring SLA Filtering:** Candidates violating any SLA threshold are disqualified before QoS scoring. A service violating an SLA constraint can never be recommended, regardless of its cost or historical reputation.
3. **Hysteresis Anti-Flapping Policy:** Switching away from an eligible current provider requires a statistically significant improvement ($\Delta Q \ge 0.05$). Score micro-jitter is damped, preserving service stability.
4. **Emergency Bypass Protocol:** Catastrophic events (outages or SLA violations on the active provider) immediately bypass hysteresis thresholds and cooldown timers.
5. **Autonomous Background Surveillance:** A periodic monitoring engine continuously tracks health states and logs deduplicated audit events.
6. **Fail-Safe Manual Override:** Operators can explicitly select an eligible service; however, the system enforces hard SLA constraints on manual selection and automatically terminates manual override upon fault detection.

---

## Chapter 6: Literature Review

The academic foundation of this project is inspired by recent advances in cloud service composition:
- **Reference Paper:** *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition* (IEEE ICIMIA-2025). The reference work explores combining Deep Reinforcement Learning (DRL) and Particle Swarm Optimization (PSO) for exploring complex multi-cloud composite workflow dependency graphs.
- **Academic Focus of this Prototype:** While the reference paper investigates heuristic optimization over large dependency graphs, this project isolates, hardens, and empirically evaluates the **dynamic service reselection, SLA constraint enforcement, and switching stability subsystem**.
- **Utility Theory in Cloud Brokerage:** Multi-Attribute Utility Theory (MAUT) provides a mathematically transparent foundation for combining conflicting criteria (such as latency minimization vs availability maximization) without neural black-box opacity.
- **Hysteresis in Distributed Systems:** Hysteresis and deadband controllers are well-established in control engineering and telecommunications for preventing rapid oscillation between competing cell towers or routing paths. This prototype adapts hysteresis thresholding to cloud service reselection.

---

## Chapter 7: Software and Hardware Requirements

### 7.1 Hardware Environment (Tested & Benchmark-Verified)
- **Host Architecture:** x86_64 / AMD64 architecture.
- **Processor:** Intel Core i7 / 10-core (10 physical cores, 12 logical processors) or equivalent multi-core CPU.
- **RAM:** Minimum 4.0 GB RAM (Tested on 15.69 GB Total RAM).
- **Disk Storage:** Minimum 500 MB free disk space for repository, logs, virtual environment, and interactive Plotly HTML outputs.

### 7.2 Software Environment
- **Operating System:** Microsoft Windows 11 / Windows 10 (64-bit), Linux (Ubuntu 20.04+), or macOS (12.0+).
- **Programming Language:** Python 3.10, 3.11, 3.12, 3.13, or 3.14 (Verified on Python 3.14.3 64-bit).
- **Core Dependencies:**
  - `streamlit>=1.35.0` (Verified on 1.66.1)
  - `pandas>=2.0.0` (Verified on 2.2.3)
  - `numpy>=1.24.0` (Verified on 2.2.6)
  - `plotly>=5.15.0` (Verified on 5.24.1)
  - `pytest>=7.4.0` (Verified on 9.1.1)
  - `psutil>=5.9.0` (Verified on 6.1.1)

---

## Chapter 8: System Architecture

The overall architecture is partitioned into four decoupled layers:
1. **Presentation Layer (`app.py`, `src/analytics.py`):** Cloud Command Center interface built with Streamlit, featuring a dark navy theme, system health banner, visual service cards with health badges and QoS progress bars, connected-node SVG topology map, 7-step failover workflow tracker, six navigable views (Dashboard, Cloud Service Map, Performance Analytics, Failure Lab, Decision History, Configuration), and Plotly visualization charts.
2. **Control & Surveillance Layer (`src/failure_simulator.py`, `src/monitoring_engine.py`, `src/override_manager.py`):** Fault injection mutating service states, background periodic surveillance, and manual mode state management.
3. **Decision & Recommendation Pipeline (`src/recommendation_engine.py`, `src/sla_config.py`, `src/hysteresis_config.py`):** Linear multi-stage pipeline executing category filtering, SLA exclusion, QoS evaluation, deterministic ranking, and hysteresis control.
4. **Data & State Management Layer (`src/service_registry.py`, `src/explainability.py`):** Canonical data models, immutable baseline reference bounds, and append-only audit logs.

*(Refer to `docs/SYSTEM_ARCHITECTURE.md` for complete architectural and workflow Mermaid diagrams).*

---

## Chapter 9: System Design and Module Description

The system comprises 11 core modules in `src/`:
- **`service_registry.py`:** Defines `CloudService`, baseline dictionaries, and reference bound extraction.
- **`qos_evaluator.py`:** Implements lower/higher-is-better normalization, weight validation, and weighted scoring.
- **`sla_config.py`:** Manages `SLAConfig` dataclass, threshold parameter validation, and multi-violation detection.
- **`hysteresis_config.py`:** Manages `HysteresisConfig`, switching threshold evaluation, and cooldown management.
- **`monitoring_config.py`:** Defines polling intervals, enablement status, and retention caps.
- **`monitoring_engine.py`:** Thread-safe surveillance engine managing 4-tier health states and deduplicated logging.
- **`override_manager.py`:** Dual operating mode state machine enforcing strict validation and emergency revocation.
- **`failure_simulator.py`:** Implements latency spikes, outage injection, availability drops, restore, and reset.
- **`recommendation_engine.py`:** Coordinates the multi-stage pipeline and outputs `RecommendationResult`.
- **`explainability.py`:** Decomposes mathematical scores into human-readable tables and explanations.
- **`analytics.py`:** Health classification, history tracking, and Plotly chart builders.

---

## Chapter 10: Methodology

The project follows an empirical, test-driven research engineering methodology:
1. **Baseline Invariant Modeling:** Candidate cloud services are initialized with immutable baseline reference bounds, preventing normalization distortion during fault injection.
2. **Constraint-First Pipeline:** Hard SLA constraints are evaluated prior to ranking, guaranteeing that utility scores cannot override safety thresholds.
3. **Threshold Damping Formulation:** Hysteresis deadbands suppress switching under small score fluctuations, reducing flapping.
4. **Automated Verification Harness:** 138 automated unit, integration, and UI tests verify all execution paths.
5. **Empirical Benchmarking:** A standalone evaluation harness (`experiments/run_research_experiments.py`) executes 8 experiments and a 100-step realistic trace comparing 4 baseline strategies.

---

## Chapter 11: QoS Evaluation and Scoring Method

Raw candidate metrics with different physical units are scaled to $[0.0, 1.0]$ using baseline-anchored normalization:

### 11.1 Lower-is-Better Normalization (Latency, Cost)
$$U_{\text{lower}}(v) = \max\left(0.0, \min\left(1.0, \frac{\max_{\text{bound}} - v}{\max_{\text{bound}} - \min_{\text{bound}}}\right)\right)$$

### 11.2 Higher-is-Better Normalization (Availability, Reliability)
$$U_{\text{higher}}(v) = \max\left(0.0, \min\left(1.0, \frac{v - \min_{\text{bound}}}{\max_{\text{bound}} - \min_{\text{bound}}}\right)\right)$$

### 11.3 Weighted Multi-Criteria Utility Formulation
$$Q(s) = \sum_{m \in M} w_m \cdot U_m(s_m)$$
Default weights: $w_{\text{lat}} = 0.35, \; w_{\text{cost}} = 0.20, \; w_{\text{avail}} = 0.30, \; w_{\text{rel}} = 0.15$.

---

## Chapter 12: SLA-Based Service Eligibility

Hard SLA constraints are validated by `validate_service_sla()`:
1. Latency Condition: $s.\text{latency} \le \text{SLA}.\text{max\_latency}$
2. Availability Condition: $s.\text{availability} \ge \text{SLA}.\text{min\_availability}$
3. Reliability Condition: $s.\text{reliability} \ge \text{SLA}.\text{min\_reliability}$

Candidates failing any condition are disqualified before QoS scoring and populated into `excluded_services` with specific violation descriptions.

---

## Chapter 13: Failure Detection and Simulation

The `FailureSimulator` provides controlled fault injection:
- **Latency Spike:** Adds positive latency delta, simulating network congestion.
- **Service Outage:** Transitions status to `UNAVAILABLE`, simulating provider hardware failure.
- **Availability Degradation:** Decreases availability percentage, simulating intermittent packet drops.
- **Service Restoration & Global Reset:** Restores target or all services to baseline state idempotently.

---

## Chapter 14: Dynamic Service Reselection

When the active service degrades or fails, `RecommendationEngine.recommend()` executes reselection:
1. Filters services by requested category (`Compute` vs `Storage`).
2. Excludes unavailable candidates.
3. Excludes SLA-violating candidates.
4. Ranks eligible candidates by descending QoS score.
5. Breaks ties deterministically by alphabetical `service_id`.
6. Evaluates hysteresis switching rules.
7. Generates transparent markdown decision explanations.

---

## Chapter 15: Hysteresis and Anti-Flapping

To prevent service oscillation:
- **Switching Threshold:** Switching occurs only if $Q(S_{\text{best}}) - Q(S_{\text{current}}) > \Delta_{\text{threshold}}$ (default: $0.05$ or 5.0%).
- **Cooldown Steps:** Enforces a minimum interval between performance-driven switches.
- **Emergency Bypass:** Operational outages (`UNAVAILABLE`) or SLA breaches on the active provider immediately bypass hysteresis and cooldown, executing immediate failover.

---

## Chapter 16: Periodic Monitoring

The `MonitoringEngine` runs autonomous background surveillance:
- **Health Classification:** Categorizes candidates into `HEALTHY`, `DEGRADED`, `CRITICAL`, and `DOWN`.
- **Deduplicated Logging:** Emits `SERVICE_HEALTH_CHANGED` events only when a service transitions between health states.
- **Automated Reselection Trigger:** Automatically invokes the recommendation pipeline when active service health degrades.

---

## Chapter 17: Manual Service Override

The `ManualOverrideManager` provides operator control:
- **Modes:** `MODE_AUTOMATIC` and `MODE_MANUAL`.
- **Validation Guard:** Validates candidate existence, category match, operational status, and SLA compliance.
- **Automatic Emergency Revocation:** If an outage or SLA breach hits the manually overridden service, manual mode is immediately revoked and failover triggers automatically.

---

## Chapter 18: Implementation Details

- **Code Organization:** Modular layout in `src/` with clear separation of responsibilities.
- **Thread Safety:** `threading.Lock` guards monitoring lifecycle and event history.
- **Version Compatibility:** Adaptive `_render_full_width_kwargs()` supports Streamlit $\ge$ 1.35 and legacy versions without deprecation warnings.
- **Memory Profiling:** Linear memory footprint (< 260 KB peak heap memory for 1,000 services).

---

## Chapter 19: Experimental Setup

Evaluated on Windows 11 (Python 3.14.3, 10-core CPU, 15.69 GB RAM) using `experiments/run_research_experiments.py`:
- **Scenarios:** 8 distinct experiments covering baseline selection, latency degradation, outage failover, cascading failures, hysteresis anti-flapping, manual override, monitoring overhead, and scalability.
- **Baseline Comparison:** 100-step realistic workload comparing Static, QoS-Only, SLA-Aware No Hysteresis, and Proposed Unified.

---

## Chapter 20: Results and Performance Analysis

### 20.1 Baseline Comparison Results (100-Step Realistic Workload)
| Strategy | SLA Compliance (%) | Outage Exposure (%) | Total Switches | Unnecessary Switches | Recommendation Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Static** | $60.00\%$ | $20.00\%$ | **0** | 0 | $0.0002\text{ ms}$ |
| **QoS-Only** | $80.00\%$ | $0.00\%$ | **18** | 16 | $0.1069\text{ ms}$ |
| **SLA-Aware No Hyst** | **$100.00\%$** | $0.00\%$ | **17** | 16 | $0.0638\text{ ms}$ |
| **Proposed Unified** | **$100.00\%$** | **$0.00\%$** | **1** | **0** | **$0.0655\text{ ms}$** |

### 20.2 Key Empirical Takeaways
1. **SLA Compliance:** Proposed system achieves 100% compliance, eliminating SLA failures.
2. **Outage Exposure:** Achieves 0% outage exposure with sub-40 microsecond emergency reselection.
3. **Flapping Elimination:** Reduces switching churn by **94.1% to 100.0%** under micro-jitter.
4. **Scalability:** Processes 1,000 services in **17.71 ms** (> 56,000 services/second throughput).

---

## Chapter 21: Testing and Validation

All 138 automated tests pass with 100% success rate across 13 test suites:
- **Unit Tests:** `test_service_registry` (via baseline models), `test_qos_evaluator` (9), `test_sla_eligibility` (14), `test_hysteresis` (15), `test_monitoring` (17), `test_manual_override` (15), `test_failure_simulator` (6), `test_recommendation_engine` (6), `test_explainability` (5), `test_analytics` (4).
- **Persistence & Audit Tests (Phase 9):** `test_persistence` (15 automated ACID, SQLite pragma, recovery, and migration tests).
- **Integration Tests:** `test_e2e_integration_scenarios` (7 comprehensive operational lifecycle scenarios A–G).
- **Edge Case Tests:** `test_reliability_edge_cases` (13 extreme boundary and fault-tolerance tests).
- **UI Automation:** `test_ui_dashboard` (12 headless Streamlit `AppTest` automated browser interaction tests).

---

## Chapter 22: Advantages and Limitations

### Advantages
1. Deterministic, mathematically explainable recommendations.
2. Strict SLA safety guarantees.
3. High switching stability via hysteresis damping (100% reduction in micro-jitter flapping).
4. Sub-millisecond execution latency ($< 0.1\text{ ms}$).
5. Zero memory leaks and linear scalability up to 1,000 services ($17.7\text{ ms}$).
6. ACID-compliant persistent local storage (Phase 9 SQLite database with WAL mode and transaction rollback).

### Limitations
1. Single-node local simulation rather than distributed multi-node cluster deployment.
2. Synthetic cloud metrics rather than live AWS CloudWatch / Azure Monitor API telemetry.
3. Atomic single service selection rather than multi-service DAG composition.
4. Single-operator console without multi-user role-based access control (RBAC).

---

## Chapter 23: Future Enhancements

1. **Distributed Event Streaming:** Integrate Apache Kafka or RabbitMQ for high-throughput enterprise event streaming.
2. **Live Cloud API Connectors:** Poll AWS CloudWatch, Google Cloud Monitoring, and Azure Monitor for real telemetry.
3. **Composite DAG Workflow Engine:** Extend reselection to multi-stage workflow graphs and dependency DAGs.
4. **Multi-User RBAC & OAuth2:** Enforce role-based access control and JWT authentication for manual override actions.
5. **Predictive SLA Violation Early-Warning:** Use time-series forecasting (ARIMA / LSTM) to detect degradation trends before SLA breach occurs.

---

## Chapter 24: Conclusion

This project successfully designs, implements, and experimentally validates a **Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** prototype. By integrating multi-criteria utility theory, strict SLA constraint filtering, hysteresis anti-flapping, periodic background surveillance, and manual override safety, the system provides a robust, high-performance, and explainable solution for cloud service resilience.

Empirical benchmarks demonstrate 100% SLA compliance, 0% outage exposure, a 94.1% to 100% reduction in service flapping, and sub-20ms scalability to 1,000 candidate services, fully satisfying all academic and engineering objectives.

---

## Chapter 25: References

1. IEEE ICIMIA-2025. *A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition*. In Proceedings of the IEEE International Conference on Inventive Media, Information and Communication Technologies.
2. Keeney, R. L., & Raiffa, H. (1993). *Decisions with Multiple Objectives: Preferences and Value Trade-Offs*. Cambridge University Press.
3. Menasce, D. A., Casalicchio, E., & Dubey, V. (2010). *On Optimal Service Selection in Service Oriented Architectures*. Performance Evaluation, 67(8), 659-675.
4. Streamlit Documentation. (2026). *Streamlit API Reference & AppTest Framework*. Snowflake Inc.
5. Python Software Foundation. (2026). *Python 3.14 Standard Library Documentation*. PSF.

