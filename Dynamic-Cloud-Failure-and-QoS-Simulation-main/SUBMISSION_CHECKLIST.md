# Comprehensive Academic & Technical Submission Checklist

**Project Title:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Degree Requirement:** Bachelor of Engineering (B.E.) — Department of Artificial Intelligence & Data Science  
**Institution:** Sambhram Institute of Technology (SaIT), Bengaluru — Affiliated to Visvesvaraya Technological University (VTU)  
**Academic Year:** 2026–2027  
**Verification Date:** November 20, 2026  
**Final Status:** **100% VERIFIED — ALL SUBMISSION ITEMS COMPLETE**  

---

## Category 1: Source Code & Implementation Integrity

- [x] **Registry & Data Model (`src/service_registry.py`):**
  - [x] `CloudService` dataclass defines all QoS attributes (id, name, category, latency, cost, availability, reliability, operational status).
  - [x] Synthetic candidate registries for Compute (5 services) and Storage (2 services).
  - [x] Immutable baseline reference bounds computed via `compute_reference_bounds(baseline_services)`.
  - [x] Normalization bounds remain unaffected by simulated runtime degradation or outages.

- [x] **Multi-Criteria QoS Evaluator (`src/qos_evaluator.py`):**
  - [x] Linear min-max normalization for lower-is-better metrics (Latency, Cost).
  - [x] Linear min-max normalization for higher-is-better metrics (Availability, Reliability).
  - [x] Clamping guard preventing utility values outside $[0.0, 1.0]$.
  - [x] Equal min-max boundary guard returning $1.0$.
  - [x] Configurable weights with automatic sum normalization ($\sum w_i = 1.0$).

- [x] **Strict Hard SLA Filtering (`src/sla_config.py`):**
  - [x] Centralized `SLAConfig` dataclass enforcing maximum latency, minimum availability, and minimum reliability.
  - [x] `validate_service_sla()` checks candidate compliance and returns structured violation messages.
  - [x] Disqualification occurs *prior* to QoS ranking; violating services receive score $0.0$ and are excluded.
  - [x] Empty candidate pool gracefully returns `NO_SLA_COMPLIANT_SERVICE` without crashing.

- [x] **Anti-Flapping Hysteresis Engine (`src/hysteresis_config.py`):**
  - [x] Centralized `HysteresisConfig` enforcing switching delta ($\Delta Q \ge 0.05$).
  - [x] Evaluates candidate improvement against current active service score.
  - [x] Flapping prevention suppresses migration churn under micro-jitter ($\pm 4.0\text{ ms}$).
  - [x] Emergency bypass protocol immediately overrides hysteresis and cooldown upon active outage or SLA breach.

- [x] **Periodic Autonomous Monitoring (`src/monitoring_engine.py`):**
  - [x] Background surveillance engine reassessing candidate health at configurable intervals.
  - [x] Health state classifier (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `RECOVERED`).
  - [x] Transition deduplication prevents redundant event logging across identical cycles.
  - [x] Thread-safe execution with manual on-demand `inspect_now()` override.

- [x] **Validated Manual Service Override (`src/override_manager.py`):**
  - [x] Dual operating modes (`AUTOMATIC` vs. `MANUAL_OVERRIDE`).
  - [x] Validates service existence, category match, availability, and SLA compliance.
  - [x] Blocks unauthorized manual selection of degraded or offline services.
  - [x] Automatic emergency revocation and failover if manually selected service fails or breaches SLA.

- [x] **Explainability & Audit Engine (`src/explainability.py`):**
  - [x] `ReselectionRecord` captures switching trigger, previous winner, new winner, and mathematical score deltas.
  - [x] 3-way comparative DataFrame (Active, Previous, Runner-up).
  - [x] Append-only chronological audit trail storing complete decision history.

- [x] **SQLite Persistence & State Management (`src/database/`):**
  - [x] `connection.py`: Thread-isolated SQLite connections, WAL mode, foreign keys, 5000ms busy timeout.
  - [x] `schema.py`: 7 relational tables with 12 performance indexes.
  - [x] `migrations.py`: Schema versioning and idempotent migration execution on startup.
  - [x] `repositories.py`: Parameterized SQL repositories for services, mutations, monitoring, reselections, and overrides.
  - [x] Restart state recovery restores simulation conditions while preserving immutable baseline bounds.
  - [x] Destructive database purge requires explicit checkbox confirmation.

---

## Category 2: Automated Testing & Verification Suite

- [x] **Test Suite Execution Command:**
  - [x] Documented execution command verified: `python -m pytest tests -v`.
  - [x] Total test cases collected: **138 tests**.
  - [x] Total test cases passed: **138 tests (100.0% pass rate)**.
  - [x] Total failed: **0**.
  - [x] Total skipped: **0**.
  - [x] Execution time: **20.07 seconds**.

- [x] **Test Module Breakdown:**
  - [x] `tests/test_qos_evaluator.py`: 9 passed.
  - [x] `tests/test_failure_simulator.py`: 6 passed.
  - [x] `tests/test_recommendation_engine.py`: 6 passed.
  - [x] `tests/test_sla_eligibility.py`: 14 passed.
  - [x] `tests/test_hysteresis.py`: 15 passed.
  - [x] `tests/test_monitoring.py`: 17 passed.
  - [x] `tests/test_manual_override.py`: 15 passed.
  - [x] `tests/test_persistence.py`: 15 passed.
  - [x] `tests/test_explainability.py`: 5 passed.
  - [x] `tests/test_analytics.py`: 4 passed.
  - [x] `tests/test_ui_dashboard.py`: 12 passed.
  - [x] `tests/test_e2e_integration_scenarios.py`: 7 passed.
  - [x] `tests/test_reliability_edge_cases.py`: 13 passed.

- [x] **Test Isolation Fixture (`tests/conftest.py`):**
  - [x] `isolated_test_db` autouse fixture provides a clean temporary database per test invocation, preventing cross-test pollution.

---

## Category 3: Interactive Streamlit Dashboard (`app.py`)

- [x] **Visual Command Center Layout:**
  - [x] Dark navy theme with modern cloud infrastructure aesthetic.
  - [x] Prominent overall cloud system health indicator.
  - [x] 5 visual cloud service cards with green (healthy), yellow (degraded), and red (failed) badges.
  - [x] Prominent visual highlight for the active selected service.
  - [x] Automatic monitoring running/paused visual indicator.

- [x] **Clean 6-View Navigation Structure:**
  - [x] View 1: Main Dashboard (Command Center overview).
  - [x] View 2: Cloud Service Map (Connected visual nodes, directional relationships, failure highlighting).
  - [x] View 3: Performance Analytics (Latency timeline, radar chart, QoS ranking, availability).
  - [x] View 4: Failure Simulation (Interactive Failure Lab with latency spikes, outages, restoration).
  - [x] View 5: Decision History (Chronological audit log and database persistent telemetry).
  - [x] View 6: Configuration (SLA thresholds, QoS weights, hysteresis delta, monitoring interval).

- [x] **Sidebar Telemetry & Control:**
  - [x] SQLite database connection status badge and record count summary.
  - [x] Fault injection controls with instant state mutation feedback.
  - [x] Service restoration and global reset controls.

---

## Category 4: Empirical Research Experiments & CSV Validation

- [x] **Experiment Scripts & Raw Data:**
  - [x] Benchmark runner: `experiments/run_research_experiments.py`.
  - [x] Raw JSON dataset: `experiments/raw_results.json`.
  - [x] Interactive HTML charts generated for all 4 experiment suites.

- [x] **100% Data Consistency Verification:**
  - [x] `experiments/baseline_comparison.csv` verified against Table 7.1 in report.
  - [x] `experiments/hysteresis_flapping_results.csv` verified against Table 7.2 in report.
  - [x] `experiments/latency_degradation_results.csv` verified against Table 7.3 in report.
  - [x] `experiments/scalability_results.csv` verified against Table 7.4 in report.
  - [x] Zero manufactured or fabricated values; all numbers derived from code execution.

---

## Category 5: Academic College Report (`F_report.docx`)

- [x] **Typography & Styling:**
  - [x] Body text: Times New Roman, 12 pt.
  - [x] Headings: Times New Roman, 14 pt bold.
  - [x] Page borders: 0.5 pt single border around pages.
  - [x] Header: Project title in header, positioned outside the page border (`top w:space="31"`, `header="400"`).
  - [x] Footer: `Dept. of AI&DS, SaIT 2026-27` on left, `Page <PAGE>` on right.
  - [x] Margins: 1.0 inch (1440 twips) on all sides.

- [x] **Document Structure & Chapters:**
  - [x] Preliminary pages: Cover page, Certificate, Declaration, Acknowledgement, Abstract.
  - [x] Table of Contents (Table 4) covering Chapters 1–8, References, and Appendices A–W.
  - [x] List of Figures (Table 5) fully reconciled with Chapter 5 body (includes Fig 5.6).
  - [x] List of Tables (Table 6) covering Tables 2.1 through 7.4.
  - [x] Chapters 1 to 8 fully present without missing sections.
  - [x] Chapter 6 paragraph 244 and Table 6.2 updated to 138 passing tests.
  - [x] Chapter 7 experimental results match CSV files exactly.
  - [x] References list verified with complete peer-reviewed and official citations.

- [x] **Appendices Flow:**
  - [x] 20 premature `<w:br w:type="page"/>` page breaks before Appendices D through W removed.
  - [x] Appendices flow naturally across pages, eliminating large white spaces.
  - [x] Complete technical content preserved across Appendices A through W.

---

## Category 6: Technical Documentation Suite Alignment

- [x] `README.md`: Updated with 138 tests, SQLite persistence details, and repository architecture.
- [x] `docs/SYSTEM_ARCHITECTURE.md`: Persistence layer and repository data flow documented.
- [x] `docs/IMPLEMENTATION_DETAILS.md`: Parameterized repository methods and SQLite lifecycle documented.
- [x] `docs/TESTING_REPORT.md`: Comprehensive 138-test breakdown across all 13 test modules.
- [x] `docs/KNOWN_LIMITATIONS.md`: Limitation 2.1 formally marked as resolved by Phase 9.
- [x] `docs/EXPERIMENTAL_RESULTS.md`: Exact numerical consistency with experiment CSVs.
- [x] `docs/FINAL_PROJECT_REPORT.md`: 25 chapters fully aligned with implementation and test counts.

---

## Category 7: Viva Voce & Demonstration Readiness

- [x] `docs/DEMONSTRATION_GUIDE.md`: 12-minute live demonstration script covering normal conditions, latency spike, outage failover, manual override, and reset.
- [x] `docs/PROJECT_PRESENTATION.md`: 15-slide defense presentation outline with presenter delivery notes.
- [x] `docs/VIVA_QUESTIONS.md`: 55 comprehensive examination questions and answers across 15 technical domains.
- [x] `docs/PROJECT_EXPLANATION.md`: 1-minute elevator pitch, 3-minute committee summary, and 5-minute technical review scripts.
- [x] `docs/FINAL_DEMONSTRATION_AUDIT.md`: 14-scenario demonstration audit report verified against code execution.

---

## Category 8: Institutional Submission Deliverables

- [x] **Digital Deliverable Package:**
  - [x] Complete source code in `src/` and `app.py`.
  - [x] Automated test suite in `tests/`.
  - [x] Empirical experimental scripts and datasets in `experiments/`.
  - [x] Complete documentation suite in `docs/`.
  - [x] Clean default SQLite database in `data/`.

- [x] **Academic Report Deliverables:**
  - [x] Authoritative editable source: `C:\Users\gost\Desktop\F_report.docx`.
  - [x] Comprehensive markdown report: `docs/FINAL_PROJECT_REPORT.md`.
  - [x] Backup of pre-Phase-7 report: `C:\Users\gost\Desktop\F_report_backup_pre_phase7.docx`.

- [ ] **Physical Submission Tasks (To be completed by students):**
  - [ ] Enter University Seat Numbers (USNs) on Certificate and Declaration pages.
  - [ ] Sign Declaration (Manohar R, Yashaswini P N, Gagana K S).
  - [ ] Obtain signature of Project Guide (Mr. Vishwanath Rajaput).
  - [ ] Obtain signature of Head of Department and Principal.
  - [ ] Print hardcopy or export to PDF for binding.
