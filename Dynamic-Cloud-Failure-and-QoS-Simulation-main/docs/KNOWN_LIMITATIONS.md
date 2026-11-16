# Known Limitations & Academic Prototype Scope

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Document Classification:** Academic Scope Boundary & Limitations Disclosure  
**Target Audience:** Project Reviewers, Examiners, and Technical Evaluators  

---

## 1. Overview

The **Dynamic Cloud Failure Detection and QoS-Aware Service Reselection** prototype was engineered as an academic proof-of-concept inspired by research in intelligent cloud service composition (IEEE ICIMIA-2025). The system is fully implemented and verified for its intended purpose: demonstrating deterministic multi-criteria QoS evaluation, strict hard SLA filtering, anti-flapping hysteresis, autonomous health monitoring, and operator override safety.

To ensure technical transparency, this document formally delineates the architectural boundaries and known limitations of the prototype.

---

## 2. Verified Technical Limitations

### 2.1 In-Memory Session Volatility
- **Limitation:** All simulation mutations (injected latency spikes, simulated outages), historical metric snapshots (`HistoryTracker`), and audit event logs (`ReselectionAuditTrail`, `MonitoringEngine`, `ManualOverrideManager`) are stored in volatile runtime memory (`st.session_state` and Python heap memory).
- **Impact:** Terminating or restarting the Streamlit application process resets all services to baseline and clears the audit logs.
- **Production Countermeasure:** In production environments, audit logs and state machines would be persisted to a relational database (e.g., PostgreSQL / Neon) or an append-only event stream (e.g., Apache Kafka).

### 2.2 Synthetic Cloud Telemetry
- **Limitation:** Candidate cloud service parameters (latency, cost, availability, reliability) and failure events are synthetically generated.
- **Impact:** The prototype does not connect to live commercial cloud infrastructure (such as AWS CloudWatch, Microsoft Azure Monitor, or Google Cloud Operations Suite) and does not issue real billing or provisioning API calls.
- **Academic Context:** Synthetic data is standard practice for academic evaluation because it allows perfectly reproducible, deterministic fault injection experiments without incurring cloud billing costs or violating provider terms of service.

### 2.3 Atomic Single-Service Reselection (Non-Composite)
- **Limitation:** The reselection pipeline evaluates and selects individual atomic cloud services within a functional category (`Compute` or `Storage`).
- **Impact:** It does not orchestrate or re-plan complete composite Directed Acyclic Graph (DAG) microservice workflows with data dependencies between multiple stages.
- **Reference Context:** While the motivating reference paper explores composite workflows using Deep Reinforcement Learning (DRL) and Particle Swarm Optimization (PSO), this prototype focuses on the atomic reselection and switching damping subsystem to maintain deterministic auditability.

### 2.4 Absence of Multi-User Role-Based Access Control (RBAC)
- **Limitation:** The manual service override interface in `app.py` is accessible to any operator interacting with the dashboard session without user authentication.
- **Impact:** There is no cryptographic signature, multi-factor authentication (MFA), or role hierarchy (e.g., Administrator vs Viewer) governing who may activate an override.
- **Design Rationale:** Designed for single-operator live academic demonstration and headless automated UI testing.

### 2.5 Zero State-Migration Overhead Assumption
- **Limitation:** When switching from an active service to a newly recommended provider, the system assumes instantaneous invocation handover with zero data migration overhead or state re-hydration delay.
- **Impact:** For stateless RESTful APIs or compute workers, this assumption is realistic. For stateful cloud databases or distributed caches, provider migration incurs network transfer latency and data synchronization penalties that would require state-aware hysteresis penalties.

### 2.6 Local Host Execution Environment
- **Limitation:** The recommendation engine, monitoring thread, and simulation mutants execute within the same local process.
- **Impact:** Network partition between the monitoring agent and the service endpoints is simulated via operational status flags rather than real socket timeouts or packet drops.

---

## 3. Scope Boundary Summary

| Feature Category | Prototype Implementation (Verified) | Production Enterprise Requirement |
| :--- | :--- | :--- |
| **QoS Evaluation** | Deterministic weighted utility scoring | Multi-criteria utility + machine learning predictors |
| **SLA Filtering** | Hard boundary constraint disqualification | Dynamic contract negotiation + penalty calculators |
| **Hysteresis Damping** | Threshold delta ($\Delta Q$) + step cooldown | Adaptive thresholding based on historical variance |
| **Fault Injection** | Controlled synthetic mutation | Chaos engineering (e.g., Chaos Mesh, Gremlin) |
| **State Persistence** | In-memory session state & trackers | Distributed relational DB / Kafka event store |
| **Service Composition** | Atomic category-based candidate ranking | Multi-stage DAG workflow orchestration |
| **Security & Auth** | Single-operator console | Multi-tenant RBAC + OAuth2 / OIDC authentication |
