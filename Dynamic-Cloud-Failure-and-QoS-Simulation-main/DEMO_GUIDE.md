# Live Demonstration & Evaluation Guide

## Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

This guide provides a verified, step-by-step demonstration walkthrough for technical evaluators, examiners, and project reviewers. It covers the complete lifecycle across all implemented phases: baseline QoS evaluation, strict SLA filtering, hysteresis anti-flapping, periodic automatic monitoring, emergency reselection, and manual service override.

---

## 1. Prerequisites & Launch Instructions

Open Windows PowerShell in the project directory:

```powershell
Set-Location "c:\Users\Mahendra\Downloads\Dynamic-Cloud-Failure-and-QoS-Simulation-Simplified\Dynamic-Cloud-Failure-and-QoS-Simulation-main"

# Launch Streamlit Dashboard:
streamlit run app.py

# Alternatively, specify direct Python interpreter:
& "C:\Users\Mahendra\AppData\Local\Python\bin\python.exe" -m streamlit run app.py
```

The interactive dashboard opens in your default web browser at:
`http://localhost:8501`

---

## 2. Step-by-Step Demonstration Script (9 Verification Steps)

### Step 1: Baseline Inspection & Deterministic QoS Ranking
1. **Category Selector**: Select **`Compute`** in the sidebar.
2. **Review KPI Metrics Cards**:
   - Total Category Services: `5`
   - Healthy / Available: `5`
   - Unavailable / Outage: `0 down`
   - Top Recommended: `NovaCompute Standard` (`SVC-C01`, QoS Score: `0.8168` with default weights).
3. **Inspect Tab 1 (Overview & Recommendations)**:
   - Review the candidate comparison table showing all 5 compute services (`SVC-C01` to `SVC-C05`).
   - Point out that all 5 candidates are marked **ELIGIBLE** and meet all SLA criteria.
4. **Examiner Talking Point**:
   > *"The evaluation engine normalizes latency, cost, availability, and reliability using immutable baseline reference bounds. Unaffected services never experience score warping when another candidate degrades."*

---

### Step 2: Strict SLA Constraint Enforcement & Violation Filtering (Phase 1)
1. **Target Service**: In the sidebar, select `SVC-C01 - NovaCompute Standard`.
2. **Inject Latency Spike**: Set spike magnitude to `60 ms` and click **`⚡ Inject Latency Spike`**.
3. **Inspect Service State**:
   - `SVC-C01` latency rises to `105.0 ms`.
   - Default Max Permitted Latency SLA threshold is `100.0 ms`.
4. **Observed Behavior**:
   - `SVC-C01` is **immediately marked INELIGIBLE** due to SLA violation (`Latency 105.0ms exceeds SLA limit 100.0ms`).
   - Despite having an otherwise strong multi-criteria profile, it is strictly excluded from consideration.
   - Reselection automatically triggers: `AetherCompute HighPerf` (`SVC-C02`) is selected as the highest-scoring eligible candidate.
   - The *Excluded Services* panel explicitly itemizes the violation explanation for `SVC-C01`.
5. **Examiner Talking Point**:
   > *"SLA requirements are hard constraints evaluated before QoS ranking. A service violating even one SLA parameter cannot be recommended regardless of its aggregate score."*

---

### Step 3: Hysteresis Threshold & Anti-Flapping Verification (Phase 2)
1. **Restore Baseline**: Click **`🟢 Restore Service`** for `SVC-C01` (latency returns to `45.0 ms`).
2. **Observe Hysteresis Stability**:
   - In the sidebar, the Hysteresis Improvement Threshold is set to `5.0%` (0.05).
   - Inject a minor latency spike of `+8 ms` into `SVC-C01` (latency `53.0 ms`, QoS drops slightly from `0.8168` to `0.7850`).
   - Candidate `SVC-C02` has a score of `0.7937` (an improvement of only ~0.0087 or ~1.1%, well below the 5% threshold).
3. **Observed Behavior**:
   - The engine **retains `SVC-C01`** and does not flap between providers.
   - The explanation panel indicates: *"Current service retained under hysteresis threshold (improvement 1.1% < required 5.0%)."*
4. **Inject Decisive Degradation**:
   - Increase spike to `+30 ms`. Now `SVC-C02` offers > 5% improvement.
   - Reselection cleanly switches to `SVC-C02`.
5. **Examiner Talking Point**:
   > *"Hysteresis prevents unnecessary migration costs and service flapping when scores fluctuate within an acceptable margin. Switching requires a statistically significant improvement."*

---

### Step 4: Periodic Automatic Service Monitoring (Phase 3)
1. **Monitoring Controls**: In the sidebar or top banner, locate the **Periodic Service Monitoring** section.
2. **Configure Interval**: Set monitoring interval to `5s` or click **`🔍 Inspect Now`** to trigger an immediate assessment.
3. **Observed Behavior**:
   - The monitoring engine evaluates the live health of all registered services.
   - Detects health state transitions (`HEALTHY`, `DEGRADED`, `CRITICAL`, `DOWN`).
   - Generates structured cycle summaries and appends health audit events to the monitoring log without requiring manual UI clicks.
4. **Examiner Talking Point**:
   > *"Monitoring operates continuously in the background, continuously auditing SLA compliance and triggering reselection when health conditions change."*

---

### Step 5: Service Outage Simulation & Emergency Failover (Phase 2 & Phase 3)
1. **Simulate Outage**: Select the currently active service and click **`🔴 Simulate Outage`**.
2. **Observed Behavior**:
   - Active service immediately transitions to `UNAVAILABLE`.
   - **Emergency Bypass**: The hysteresis cooldown timer and margin threshold are instantly bypassed.
   - Emergency reselection chooses the next best eligible alternative without delay.
   - Reselection audit log records an `EMERGENCY_OUTAGE_FAILOVER` event.
3. **Examiner Talking Point**:
   > *"While normal performance switching respects hysteresis and cooldown timers, service outages and SLA breaches immediately trigger emergency failover."*

---

### Step 6: Total Category Outage & Graceful Degradation Handling
1. **Trigger Outages**: Click **`🔴 Simulate Outage`** on each remaining candidate in the category.
2. **Observed Behavior**:
   - The application does not crash, raise unhandled exceptions, or produce NaN values.
   - A prominent warning alert is displayed:
     > *"🚨 NO ELIGIBLE SERVICE AVAILABLE! All 5 service(s) in category 'Compute' are currently UNAVAILABLE."*
   - Dashboard KPI displays `None (Outage)`.
3. **Examiner Talking Point**:
   > *"The system demonstrates fault tolerance and graceful degradation under catastrophic infrastructure failure."*

---

### Step 7: Manual Service Override Mode (Phase 4)
1. **Restore Services**: Click **`🔄 Reset All Services`** in the sidebar.
2. **Locate Override Panel**: In Tab 1, expand the **🎛️ Operating Mode & Manual Override** panel.
3. **Select Candidate**: Choose `SVC-C04 - TitanCompute Enterprise` and provide an audit reason (e.g., `"Designated enterprise compliance benchmark"`).
4. **Activate Override**: Click **`🎯 Activate Manual Override`**.
5. **Observed Behavior**:
   - System operating mode transitions from `AUTOMATIC` to `MANUAL_OVERRIDE`.
   - Active service is locked to `SVC-C04`, overriding the default algorithmic recommendation (`SVC-C01`).
   - Distinct amber warning banner informs the user that manual mode is active.
   - The manual action is logged with timestamp, user reason, and target service ID.

---

### Step 8: Strict SLA Safety on Manual Mode & Emergency Termination
1. **Verify SLA Guard on Manual Selection**:
   - Try selecting an unavailable service or a service violating SLA: the dashboard prevents selection and reports a validation rejection.
2. **Simulate Fault on Manually Overridden Service**:
   - Select `SVC-C04` in the sidebar and click **`🔴 Simulate Outage`** (or inject a large latency spike causing an SLA violation).
3. **Observed Behavior**:
   - **Automatic Emergency Termination**: Manual override is immediately revoked.
   - Operating mode safely returns to `AUTOMATIC`.
   - System performs emergency reselection to the best remaining eligible service.
   - The event log records `MANUAL_OVERRIDE_EMERGENCY_REVOCATION`.
4. **Examiner Talking Point**:
   > *"Manual override empowers operators while maintaining hard safety guarantees. Manual selection can never bypass SLA constraints, and failures on overridden services trigger immediate failover."*

---

### Step 9: Service Recovery, Global Reset & Multi-Tab Audit Trails
1. **Global Reset**: Click **`🔄 Reset All Services`** in the sidebar.
   - All services return to baseline availability and metrics.
   - Operating mode returns to normal automatic evaluation.
2. **Inspect Multi-Tab Views**:
   - **Tab 2 (QoS Analytics)**: Bar charts, Radar charts, and multi-dimensional metric breakdowns across Latency, Availability, Cost, and Reliability.
   - **Tab 3 (Failure Impact)**: Before-and-After comparative delta cards and baseline differential tables.
   - **Tab 4 (History & Audit Trail)**: Inspect the four append-only audit tables:
     1. *Reselection Decision Audit Trail* (chronological recommendation history with trigger causes).
     2. *Performance Trajectory Across Sequence Steps* (historical metrics timeline).
     3. *Periodic Monitoring Event History* (health transitions, detections, and automated cycles).
     4. *Operating Mode & Manual Override Event Log* (mode transitions, override grants, and revocations).

---

## 3. Automated Verification & Regression Protection

Before presenting, run the automated test suite and performance benchmark to verify 100% operational readiness:

### A. Run Comprehensive Test Suite (122 Tests across 12 Modules)
```powershell
& "C:\Users\Mahendra\AppData\Local\Python\bin\python.exe" -m pytest tests -v
```
**Expected Result**: `122 passed in ~15-28s` (0 failures, 0 skipped, 100% pass rate).

### B. Run Performance Benchmark
```powershell
& "C:\Users\Mahendra\AppData\Local\Python\bin\python.exe" benchmark_performance.py
```
**Expected Result**:
- Startup Render Latency: `< 2.0 s`
- SLA Filtering Latency: `< 0.05 ms` per 10 services
- Full QoS Evaluation Latency: `< 0.20 ms` per 10 services
- End-to-End Recommendation: `< 0.25 ms` per 10 services
- Scalability to 1,000 Services: `< 35 ms` total pipeline latency, zero memory leaks.
