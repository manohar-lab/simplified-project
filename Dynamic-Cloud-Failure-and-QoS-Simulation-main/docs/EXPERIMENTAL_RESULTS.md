# Experimental Results & Performance Benchmarking Report

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Document Classification:** Empirical Benchmark Report & Baseline Comparison  
**Test Harness Script:** `experiments/run_research_experiments.py`  
**Raw Data Source:** `experiments/raw_results.json`  

---

## 1. Experimental Environment & Configurations

All benchmarks were measured on a local dedicated testing workstation running Python 3.14:
- **Operating System:** Microsoft Windows 11 Enterprise (Build 10.0.26340-SP0, 64-bit)
- **Python Version:** 3.14.3 (tags/v3.14.3:323c59a, MSC v.1944 64-bit AMD64)
- **CPU:** Intel64 Family 6 Model 154 Stepping 4, GenuineIntel (10 Physical Cores, 12 Logical Processors)
- **Total Physical RAM:** 15.69 GB (Available: ~3.43 GB during testing)
- **Random Seeds:** `42` (Scalability benchmark), `12345` (Hysteresis jitter sequence), `999` (Workload simulation)

---

## 2. Benchmark Summary Across All 8 Experiments

### Experiment 1: Baseline Service Selection (Normal Conditions)

Evaluated across 100 repeated trials on the Compute category with default weights:
- **Selected Service:** `SVC-C01` (NovaCompute Standard)
- **Winning Aggregate QoS Score:** `0.8190`
- **SLA Compliance Rate:** `100.0%`
- **Total Candidates Evaluated:** 5 (all 5 marked `ELIGIBLE`)
- **Execution Latency ($N=100$):**
  - **Mean:** `0.0672 ms`
  - **Standard Deviation:** `0.0177 ms`
  - **Minimum:** `0.0350 ms`
  - **Maximum:** `0.1507 ms`

#### Baseline Candidate Rankings
| Candidate ID | Service Name | Latency (ms) | Cost ($) | Availability (%) | Reliability (%) | Normalized QoS Score | SLA Compliant |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SVC-C01** | **NovaCompute Standard** | **45.0** | **0.040** | **99.90** | **99.50** | **0.8190** | **Yes** |
| `SVC-C02` | AetherCompute HighPerf | 25.0 | 0.085 | 99.95 | 99.80 | 0.7917 | Yes |
| `SVC-C04` | TitanCompute Enterprise | 55.0 | 0.050 | 99.85 | 99.90 | 0.7792 | Yes |
| `SVC-C05` | ZenithCompute Flex | 75.0 | 0.028 | 99.20 | 98.40 | 0.4843 | Yes |
| `SVC-C03` | EcoCompute Budget | 120.0 | 0.015 | 98.80 | 97.50 | 0.2000 | Yes |

---

### Experiment 2: Latency Degradation & Hard SLA Boundary Detection

Injected progressive latency spikes into `SVC-C01` (baseline 45.0 ms) with Max Latency SLA = 100.0 ms:

| Step | Delta Added | Resulting Latency | Target QoS Score | SLA Status | Selected Winner | Decision Type | Execution Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | $+0\text{ ms}$ | $45.0\text{ ms}$ | $0.8190$ | Compliant | `SVC-C01` | `RETAINED` | $0.1227\text{ ms}$ |
| **1** | $+15\text{ ms}$ | $60.0\text{ ms}$ | $0.7717$ | Compliant | `SVC-C01` | `RETAINED` (Hysteresis Damped) | $0.1293\text{ ms}$ |
| **2** | $+35\text{ ms}$ | $80.0\text{ ms}$ | $0.7085$ | Compliant | `SVC-C02` | `SWITCHED` (Performance) | $0.0908\text{ ms}$ |
| **3** | $+50\text{ ms}$ | $95.0\text{ ms}$ | $0.6611$ | Compliant | `SVC-C02` | `SWITCHED` (Performance) | $0.0945\text{ ms}$ |
| **4** | $+65\text{ ms}$ | $110.0\text{ ms}$ | $0.6138$ | **VIOLATED** | `SVC-C02` | `EMERGENCY_SLA_VIOLATION` | $0.0563\text{ ms}$ |
| **5** | $+105\text{ ms}$ | $150.0\text{ ms}$ | $0.5822$ | **VIOLATED** | `SVC-C02` | `EMERGENCY_SLA_VIOLATION` | $0.0524\text{ ms}$ |
| **6** | $+155\text{ ms}$ | $200.0\text{ ms}$ | $0.5822$ | **VIOLATED** | `SVC-C02` | `EMERGENCY_SLA_VIOLATION` | $0.0681\text{ ms}$ |

- **Mean Breach Detection Latency:** `0.0589 ms` (58.9 microseconds).

---

### Experiment 3: Service Outage & Emergency Reselection Under Cooldown

Simulated an operational outage (`UNAVAILABLE`) on active candidate `SVC-C01` while a 5-step switching cooldown timer was active:
- **Failed Candidate:** `SVC-C01` (NovaCompute Standard)
- **Replacement Candidate Selected:** `SVC-C02` (AetherCompute HighPerf)
- **Replacement SLA Compliance:** `100.0% Compliant`
- **Cooldown Bypassed:** `True` (emergency failover ignores non-emergency cooldown)
- **Failure Detection Latency ($N=100$):** Mean = `0.0009 ms` ($0.9\text{ µs}$), StDev = `0.0004 ms`, Min = `0.0006 ms`.
- **Emergency Reselection Latency ($N=100$):** Mean = `0.0386 ms` ($38.6\text{ µs}$), StDev = `0.0133 ms`, Min = `0.0308 ms`.

---

### Experiment 4: Cascading Failures & Total Category Failure

Applied sequential outages across all 5 candidate compute services, followed by restoration:
- **Steps 0 to 4:** Services fail sequentially (`SVC-C01` $\to$ `SVC-C02` $\to$ `SVC-C04` $\to$ `SVC-C03` $\to$ `SVC-C05`). System gracefully reselects best remaining candidate at each step.
- **Step 5 (Total Failure):** All 5 services down. Returns `None` with status code `NO_SLA_COMPLIANT_SERVICE`. Zero unhandled exceptions or NaN values.
- **Step 6 (Single Recovery):** `SVC-C04` restored to `AVAILABLE`. System immediately reselects `SVC-C04`.
- **Step 7 (Global Reset with `SVC-C04` active):** All services restored. Hysteresis retains `SVC-C04` because `SVC-C01` score improvement ($0.8190 - 0.7792 = +0.0398$) is less than the $0.05$ threshold, preventing an unnecessary bounce-back switch.
- **Step 7b (Clean Reset):** Re-initializing with `previously_selected_id = None` deterministically selects baseline winner `SVC-C01`.

---

### Experiment 5: Hysteresis Effectiveness (Anti-Flapping Evaluation)

Subjected two competing candidates (`SVC-C01` and `SVC-C02`) with near-identical baseline scores (~0.791) to 100 consecutive cycles of zero-mean synthetic latency micro-jitter ($\pm 4.0\text{ ms}$, oscillating score deltas within $\pm 1.5\%$):

| Metric | Without Hysteresis ($\Delta = 0.00$) | With Hysteresis ($\Delta = 0.05$) | Operational Impact |
| :--- | :--- | :--- | :--- |
| **Total Provider Switches** | **59 switches** | **0 switches** | **100% Flapping Elimination** |
| **Unnecessary Switches** | 59 switches | 0 switches | Eliminated migration churn |
| **Switching Stability ($S$)** | 41.00% | **100.00%** | Rock-solid service stability |
| **Average QoS Score** | 0.8195 | 0.8195 | Identical utility maintained |

---

### Experiment 6: Manual Override Validation & Safety Revocation

| Test Condition | Action Attempted | Result | Safety Status |
| :--- | :--- | :--- | :--- |
| **Eligible Selection** | Operator requests `SVC-C04` | Accepted; Mode $\to$ `MANUAL_OVERRIDE` | **Verified** |
| **Non-Existent Service**| Operator requests `SVC-UNKNOWN-99` | Rejected with validation error; Mode preserved | **Verified** |
| **Category Mismatch** | Operator requests `SVC-S01` (Storage) | Rejected with validation error | **Verified** |
| **Unavailable Candidate**| Operator requests `UNAVAILABLE` service | Rejected with validation error | **Verified** |
| **SLA Violating Service**| Operator requests service with 180ms latency | Rejected with validation error | **Verified** |
| **Outage on Overridden**| Outage injected on active `SVC-C04` | Immediate emergency revocation; Failover | **Verified** |
| **Operator Manual Clear**| Operator clears override | Returned to `AUTOMATIC` cleanly | **Verified** |

---

### Experiment 7: Periodic Monitoring Overhead & Deduplication

Profiled across 5 polling intervals (50 cycles per configuration):

| Polling Interval | Mean Cycle Latency (ms) | StDev Cycle Latency (ms) | Min Cycle Latency (ms) | Max Cycle Latency (ms) |
| :--- | :--- | :--- | :--- | :--- |
| **1.0 second** | 0.1103 | 0.0327 | 0.0973 | 0.3075 |
| **2.0 seconds** | 0.1252 | 0.0322 | 0.0996 | 0.2008 |
| **5.0 seconds** | 0.1134 | 0.0203 | 0.0988 | 0.1927 |
| **10.0 seconds** | 0.1037 | 0.0043 | 0.0996 | 0.1237 |
| **30.0 seconds** | 0.1088 | 0.0067 | 0.1019 | 0.1429 |

- **Deduplication Verification:** Across 20 consecutive monitoring cycles with unchanged service metrics, exactly 3 initialization events were recorded on Cycle 1, and **0 duplicate events** were emitted across Cycles 2 through 20.

---

### Experiment 8: Scalability Benchmarks (10 to 1,000 Services)

Measured over 30 iterations per registry size using deterministic random seed 42:

| Services ($N$) | SLA Filtering Latency (ms) | QoS Evaluation Latency (ms) | Pipeline Latency (ms) | Peak RAM (KB) | Throughput (Services / Sec) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10** | $0.0099 \pm 0.0009$ | $0.0622 \pm 0.0018$ | **$0.3506 \pm 0.1590$** | $4.66\text{ KB}$ | $28,521.4$ |
| **50** | $0.0395 \pm 0.0024$ | $0.2859 \pm 0.0130$ | **$1.0256 \pm 0.0210$** | $14.28\text{ KB}$ | $48,751.6$ |
| **100** | $0.0851 \pm 0.0017$ | $0.6309 \pm 0.0115$ | **$1.8772 \pm 0.0202$** | $27.15\text{ KB}$ | $53,271.5$ |
| **500** | $0.5419 \pm 0.4184$ | $3.3272 \pm 0.4097$ | **$9.4983 \pm 0.3756$** | $143.18\text{ KB}$ | $52,641.2$ |
| **1,000** | $0.8586 \pm 0.0759$ | $6.6537 \pm 0.3930$ | **$17.7076 \pm 1.0190$** | $256.63\text{ KB}$ | **$56,473.0$** |

---

## 3. Baseline Strategy Comparison Suite (100-Step Realistic Workload)

Workload structure:
- **Steps 0–19:** Baseline normal operation.
- **Steps 20–39:** Micro-jitter causing score delta fluctuations within $\pm 1.5\%$.
- **Steps 40–59:** Hard latency SLA violation on primary candidates (`latency = 105.0 ms > 100.0 ms`, low cost).
- **Steps 60–79:** Complete operational outage on primary candidates (`operational_status = "UNAVAILABLE"`).
- **Steps 80–99:** Service recovery and baseline return.

| Strategy | SLA Compliance (%) | Outage Exposure (%) | Total Switches | Unnecessary Switches (Flapping) | Justified Switches | Mean Decision Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Strategy 1: Static** | $60.00\%$ | $20.00\%$ | **0** | 0 | 0 | $0.0002\text{ ms}$ |
| **Strategy 2: QoS-Only** | $80.00\%$ | $0.00\%$ | **18** | 16 | 2 | $0.1069\text{ ms}$ |
| **Strategy 3: SLA-Aware No Hyst** | **$100.00\%$** | $0.00\%$ | **17** | 16 | 1 | $0.0638\text{ ms}$ |
| **Strategy 4: Proposed Unified** | **$100.00\%$** | **$0.00\%$** | **1** | **0** | **1** | **$0.0655\text{ ms}$** |

### Strategic Comparison Observations
1. **Static Selection** is non-resilient, suffering a 40% overall failure rate (20% outage exposure, 20% SLA breach).
2. **QoS-Only Selection** avoids outages, but is fooled by multi-attribute trade-offs, selecting an SLA-violating candidate during Steps 40–59 and flapping 16 times during micro-jitter.
3. **SLA-Aware No Hysteresis** guarantees SLA compliance, but produces severe switching churn (17 switches).
4. **Proposed Unified System** achieves the optimal engineering balance: **100% SLA compliance**, **0% outage exposure**, and **94.1% switching reduction** (1 switch vs 17).

