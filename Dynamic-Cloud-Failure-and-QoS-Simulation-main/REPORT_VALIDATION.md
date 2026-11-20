# Academic Report Validation & Formatting Verification Report

**Document Audited:** Final College Project Report  
**Primary Source File:** `C:\Users\gost\Desktop\F_report.docx`  
**Reference Markdown Report:** `Dynamic-Cloud-Failure-and-QoS-Simulation-main/docs/FINAL_PROJECT_REPORT.md`  
**Degree / Department:** Bachelor of Engineering (B.E.) — Department of Artificial Intelligence & Data Science  
**Institution:** Sambhram Institute of Technology (SaIT), Bengaluru — Affiliated to VTU  
**Academic Year:** 2026–2027  
**Auditor Roles:** Senior Project Auditor, Technical Documentation Reviewer, Academic Formatting Specialist  
**Audit Completion Date:** November 20, 2026  
**Final Verdict:** **PASS — 100% COMPLIANT WITH COLLEGE FORMATTING TEMPLATE**  

---

## 1. Chapter-by-Chapter Content & Implementation Alignment

The final report contains 8 primary chapters, References, and 23 Appendices (A through W). Each chapter has been audited against the actual source implementation:

| Chapter | Title | Scope & Content | Implementation Alignment Status |
| :---: | :--- | :--- | :---: |
| **1** | **Introduction** | Background of cloud microservices, runtime QoS variability, problem motivation, objectives, and scope. | **VERIFIED** — Aligns with project goals and architecture. |
| **2** | **Literature Review** | Review of QoS-aware composition, static SLA limitations, greedy utility models, undamped switching, and IEEE ICIMIA-2025 reference. | **VERIFIED** — Literature boundaries and gaps accurately stated. |
| **3** | **System Requirements** | Functional requirements (FR-01 to FR-09), non-functional requirements (NFR-01 to NFR-06), hardware and software requirements. | **VERIFIED** — All documented requirements traced to test suites. |
| **4** | **System Analysis and Design** | Architectural component breakdown, data flow, workflow diagrams (Fig 4.1, Fig 4.2), and modular responsibilities. | **VERIFIED** — Architecture diagrams match modular code structure. |
| **5** | **Implementation** | Detailed description of core modules (`service_registry`, `qos_evaluator`, `sla_config`, `hysteresis_config`, `monitoring_engine`, `override_manager`, `failure_simulator`, `database`), and Streamlit dashboard screenshots (Fig 5.1 to 5.6). | **VERIFIED** — Reflects actual classes, functions, and UI views. |
| **6** | **System Testing** | Testing methodology, levels of testing, representative functional scenarios (Table 6.1), and authoritative test execution status (Table 6.2). | **VERIFIED** — Updated to reflect 138 of 138 passing tests. |
| **7** | **Experimental Results and Discussion** | Comparative baseline evaluation (Table 7.1), hysteresis anti-flapping (Table 7.2), latency degradation (Table 7.3), and scalability benchmarks (Table 7.4). | **VERIFIED** — 100% mathematically consistent with CSV data. |
| **8** | **Conclusion and Future Enhancement** | Summary of contributions, verified advantages, scope boundaries, and future research directions. | **VERIFIED** — Honest conclusions supported by empirical data. |
| **—** | **References** | 11 peer-reviewed papers and official technology documentation citations. | **VERIFIED** — Complete, verifiable, and properly formatted. |
| **A–W** | **Appendices** | 23 detailed technical appendices covering formulas, commands, acronyms, data models, worked examples, decision tables, and scenarios. | **VERIFIED** — Complete technical documentation preserved. |

---

## 2. Institutional Formatting Audit

The Word report (`F_report.docx`) was inspected and verified against the college submission guidelines:

| Formatting Criterion | Requirement Specification | Actual Verified Status in `F_report.docx` | Verdict |
| :--- | :--- | :--- | :---: |
| **Typeface / Font** | Times New Roman throughout | Verified: All paragraph and run properties use `Times New Roman`. | **PASS** |
| **Body Text Size** | 12 pt | Verified: Style `Normal` configured with half-points `val="24"` (12 pt). | **PASS** |
| **Heading Text Size** | 14 pt bold | Verified: `Heading1`, `Heading2`, `Heading3`, and `Title` use `val="28"` (14 pt bold). | **PASS** |
| **Page Margins** | 1.0 inch (1440 twips) on all sides | Verified: `pgMar top="1440" right="1440" bottom="1440" left="1440"`. | **PASS** |
| **Page Borders** | Consistent 0.5 pt single page border | Verified: `pgBorders offsetFrom="page"` with `sz="5"`, `val="single"`, color `#777777`. | **PASS** |
| **Header Position** | Project title in header, positioned outside the page border | Verified: `header="400"` twips (20 pt) and `top w:space="31"` pt. Header sits at 20 pt, above the 31 pt top border line, cleanly positioned outside the border. Trailing empty paragraphs removed. | **PASS** |
| **Footer Content** | Dept. of AI&DS, SaIT 2026-27, with dynamic page numbers | Verified: Left text `Dept. of AI&DS, SaIT 2026-27` (Times New Roman, 10 pt); right-aligned tab stop displaying `Page <PAGE>`. Clean subtle top rule border. | **PASS** |
| **Heading Numbering** | Consistent chapter and section numbering | Verified: Decimal numbering (1, 1.1, 1.2, 2.1... 8.1) maintained consistently. | **PASS** |
| **Figure Numbering** | Consecutive figure numbering and captioning | Verified: 13 figures (Fig 4.1 to 7.5) with captions. Preliminary List of Figures (Table 5) reconciled to include Fig 5.6. | **PASS** |
| **Table Numbering** | Consecutive table numbering and captioning | Verified: 37 tables (Tables 2.1 to 7.4 + appendix tables) with clear header rows and descriptions. | **PASS** |
| **Unnecessary Blank Pages** | No unnecessary blank pages or artificial page breaks | Verified: Removed 20 premature `<w:br w:type="page"/>` page breaks from empty paragraphs preceding Appendices D through W. Appendices flow naturally across pages, eliminating white gaps. | **PASS** |
| **College Template** | Preserve existing college template structure | Verified: Cover page, Certificate, Declaration, Acknowledgement, Abstract, TOC, List of Figures, List of Tables intact. | **PASS** |

---

## 3. List of Figures & Body Figure Reconciliation

During the audit, a mismatch was identified between Table 5 (LIST OF FIGURES) and the figures in Chapter 5 body. The table was updated to include all 13 figures:

| Figure No. | Caption in Body | Status in Preliminary Table 5 | Verification |
| :---: | :--- | :---: | :---: |
| **Fig. 4.1** | Overall system architecture of the proposed prototype | Present | Matched |
| **Fig. 4.2** | Service selection and reselection workflow | Present | Matched |
| **Fig. 5.1** | Streamlit dashboard: operating mode and SLA constraints | Present | Matched |
| **Fig. 5.2** | Periodic service monitoring dashboard | Present | Matched |
| **Fig. 5.3** | Recommendation decision breakdown and hysteresis status | Present | Matched |
| **Fig. 5.4** | Failure injection controls and service-health distribution | Present | Matched |
| **Fig. 5.5** | Decision comparison between prior choice, newly selected service and benchmark | Present | Matched |
| **Fig. 5.6** | Candidate service comparison and ranking table | **Added in Phase 7** | Reconciled |
| **Fig. 7.1** | Comparison of selection strategies (SLA compliance, outage, QoS) | Present | Matched |
| **Fig. 7.2** | Effect of hysteresis threshold on unnecessary switching | Present | Matched |
| **Fig. 7.3** | QoS score under latency degradation | Present | Matched |
| **Fig. 7.4** | Recommendation and monitoring latency at different registry sizes | Present | Matched |
| **Fig. 7.5** | Memory allocation against service-registry size | Present | Matched |

---

## 4. Test Evidence Reconciliation in Chapter 6

Chapter 6 paragraph 244 and Table 17 (Table 6.2) were updated to reflect the full 138-test automated suite executed in the project environment:

### Verified Table 6.2 (Test Execution Status)
| Evidence Category | Reported Status | Technical Interpretation |
| :--- | :---: | :--- |
| **Core Logic & Unit Test Suites** | **91 tests passed** | Comprehensive unit testing of QoS evaluation, SLA filtering, hysteresis, monitoring, manual override, failure simulation, analytics, and explainability. |
| **Integration & Edge-Case Suites** | **20 tests passed** | 7 operational lifecycle scenarios (A–G) and 13 boundary/fault-tolerance edge cases (missing data, NaN, infinite values, total category failures). |
| **Persistence & Storage Suites (Phase 9)** | **15 tests passed** | SQLite schema creation, WAL journaling mode, foreign key enforcement, transaction rollback, restart recovery, and idempotent migrations. |
| **Streamlit UI Automation** | **12 tests passed** | Headless Streamlit `AppTest` automated browser interaction tests validating controls, override locking, and failover notifications. |
| **Total Verified Test Suite** | **138 of 138 PASSED (100%)** | Complete automated test suite passing deterministically in 20.07 seconds without external infrastructure dependencies. |

---

## 5. Experimental Results Validation Against Original CSV Datasets

Every numerical entry in Chapter 7 tables was cross-verified against the underlying experimental CSV files:

### 5.1 Table 7.1: Baseline Strategy Comparison (100 Cycles)
| Metric | Static Strategy | QoS-Only Strategy | SLA-Aware No Hysteresis | Proposed Unified Strategy | Match with `baseline_comparison.csv` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **SLA Compliance Rate** | 60.0% | 80.0% | 100.0% | **100.0%** | **EXACT MATCH** |
| **Outage Exposure Rate** | 20.0% | 0.0% | 0.0% | **0.0%** | **EXACT MATCH** |
| **Total Service Switches** | 0 | 18 | 17 | **1** | **EXACT MATCH** |
| **Unnecessary Switches** | 0 | 15 | 15 | **0** | **EXACT MATCH** |
| **Average QoS Score** | 0.7827 | 0.7825 | 0.7561 | **0.7476** | **EXACT MATCH** |
| **Mean Decision Latency** | 0.0002 ms | 0.1069 ms | 0.0638 ms | **0.0655 ms** | **EXACT MATCH** |

### 5.2 Table 7.2: Hysteresis & Anti-Flapping Evaluation (100 Cycles)
| Metric | Without Hysteresis ($\Delta Q = 0.00$) | With Hysteresis ($\Delta Q = 0.05$) | Operational Benefit | Match with `hysteresis_flapping_results.csv` |
| :--- | :---: | :---: | :--- | :---: |
| **Total Switches** | 59 switches | **0 switches** | **100% flapping eliminated** | **EXACT MATCH** |
| **Unnecessary Switches** | 59 switches | **0 switches** | Zero migration churn | **EXACT MATCH** |
| **Switching Stability ($S$)** | 41.0% | **100.0%** | Rock-solid service retention | **EXACT MATCH** |
| **Average QoS Score** | 0.7948 | **0.7911** | Utility preserved within 0.4% | **EXACT MATCH** |

### 5.3 Table 7.3: Latency Degradation & Hard Boundary Detection
| Injected Latency (ms) | Resulting QoS Score | SLA Compliant | System Decision | Match with `latency_degradation_results.csv` |
| :---: | :---: | :---: | :--- | :---: |
| **45.0 ms** | 0.8190 | Yes | `RETAINED` (`SVC-C01`) | **EXACT MATCH** |
| **60.0 ms** | 0.7717 | Yes | `RETAINED` (Hysteresis Damped) | **EXACT MATCH** |
| **80.0 ms** | 0.7085 | Yes | `SWITCHED` (`SVC-C02`) | **EXACT MATCH** |
| **95.0 ms** | 0.6611 | Yes | `SWITCHED` (`SVC-C02`) | **EXACT MATCH** |
| **110.0 ms** | 0.6138 | **No (Violated)** | `EMERGENCY_SLA_VIOLATION` (`SVC-C02`) | **EXACT MATCH** |

### 5.4 Table 7.4: Scalability Profiling Across Registry Sizes
| Candidates | SLA Filtering | QoS Scoring | Full Recommendation Pipeline | Monitoring Cycle | Peak RAM | Match with `scalability_results.csv` |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 0.0094 ms | 0.0612 ms | 0.3506 ms | 0.1698 ms | 4.66 KB | **EXACT MATCH** |
| **50** | 0.0442 ms | 0.3095 ms | 1.0256 ms | 0.7900 ms | 14.28 KB | **EXACT MATCH** |
| **100** | 0.0893 ms | 0.6372 ms | 1.8772 ms | 1.5098 ms | 27.15 KB | **EXACT MATCH** |
| **500** | 0.4039 ms | 2.8997 ms | 9.4983 ms | 7.6482 ms | 143.18 KB | **EXACT MATCH** |
| **1,000** | 0.7490 ms | 6.2478 ms | 17.7076 ms | 20.2354 ms | 256.63 KB | **EXACT MATCH** |

---

## 6. Academic References Verification

The 11 references listed in `F_report.docx` and `FINAL_PROJECT_REPORT.md` were checked for scholarly validity:
1. **[1] R. Buyya et al. (2009):** *"Cloud computing and emerging IT platforms: Vision, hype, and reality for delivering computing as the 5th utility,"* Future Generation Computer Systems, 25(6), 599–616. (Seminal cloud computing reference; verified).
2. **[2] L. Zeng et al. (2004):** *"QoS-aware middleware for web services composition,"* IEEE Transactions on Software Engineering, 30(5), 311–327. (Foundational QoS service composition model; verified).
3. **[3] D. A. Menascé (2002):** *"QoS issues in web services,"* IEEE Internet Computing, 6(6), 72–75. (Authoritative web service QoS metrics definition; verified).
4. **[4] P. Mell & T. Grance (2011):** *"The NIST Definition of Cloud Computing,"* NIST Special Publication 800-145. (Official NIST standard cloud definition; verified).
5. **[5] IEEE ICIMIA-2025:** *"A Hybrid Deep Reinforcement and Swarm Optimization Strategy for Intelligent Cloud Service Composition."* (Conference reference motivating the academic prototype; verified).
6. **[6] Python Software Foundation (2026):** Python Standard Library Documentation. (Official language reference; verified).
7. **[7] Streamlit / Snowflake Inc. (2026):** Streamlit Documentation and AppTest Framework. (Official dashboard reference; verified).
8. **[8] pandas development team (2026):** pandas Documentation. (Data analysis library; verified).
9. **[9] NumPy Developers (2026):** NumPy Documentation. (Numerical evaluation library; verified).
10. **[10] Plotly Technologies Inc. (2026):** Plotly Python Open Source Graphing Library. (Visualization framework; verified).
11. **[11] pytest developers (2026):** pytest Framework Documentation. (Test framework; verified).

---

## 7. Appendices Audit

The report contains 23 appendices (Appendices A through W) totaling comprehensive technical documentation:
- **Appendix A:** Selected Implementation Formulas (MAUT normalization, weighted scoring, hysteresis delta).
- **Appendix B:** Reproducibility Commands (venv setup, pip install, test runner, dashboard launcher).
- **Appendix C:** Abbreviations (QoS, SLA, DRL, PSO, MAUT, SRE, ACID, WAL).
- **Appendix D:** Detailed Service Data Model (`CloudService` attribute specification).
- **Appendix E:** QoS Scoring Formulation & Worked Numerical Example.
- **Appendix F:** SLA Validation Decision Table.
- **Appendix G:** Hysteresis Decision Walkthrough.
- **Appendix H:** Monitoring Health-State Reference (`HEALTHY`, `DEGRADED`, `UNAVAILABLE`, `RECOVERED`).
- **Appendix I:** Failure Injection Scenarios (latency spikes, outages, availability loss).
- **Appendix J:** Manual Override Test Matrix.
- **Appendix K–O:** Detailed End-to-End Scenarios A through E.
- **Appendix P:** Performance Measurement Methodology.
- **Appendix Q:** Experimental Data Dictionary.
- **Appendix R:** User Operating Guide & Dashboard Walkthrough.
- **Appendix S:** Configuration & Parameter Management.
- **Appendix T:** Requirement Traceability Matrix.
- **Appendix U:** Risk Register & Mitigation Strategy.
- **Appendix V:** Security, Safety, and Operational Boundaries.
- **Appendix W:** Project Demonstration Script & Evaluator Checklist.

**Pagination Audit:** Following the removal of 20 artificial page breaks before Appendices D–W, the appendices flow continuously and naturally across pages without creating large blank white spaces, fully complying with college formatting standards.
