# Academic Demonstration Guide & Presentation Script

**Project:** Dynamic Cloud Failure Detection and QoS-Aware Service Reselection  
**Target Audience:** Academic Reviewers, Viva Examiners, and Technical Evaluators  
**Estimated Demonstration Time:** 10–15 minutes  
**Repository Working Directory:** [`Dynamic-Cloud-Failure-and-QoS-Simulation-main`](file:///C:/Users/Mahendra/Downloads/Dynamic-Cloud-Failure-and-QoS-Simulation-Simplified/Dynamic-Cloud-Failure-and-QoS-Simulation-main)  

---

## 1. Prerequisites and Environment Setup

### System Requirements
- **Operating System:** Windows 10/11, macOS, or Linux
- **Python Version:** Python 3.10, 3.11, 3.12, 3.13, or 3.14 (64-bit)
- **Terminal Shell:** PowerShell (recommended on Windows) or Bash

### Installation & Virtual Environment Setup
Open a terminal in the project directory:

```powershell
# Navigate to project directory
cd "c:\Users\Mahendra\Downloads\Dynamic-Cloud-Failure-and-QoS-Simulation-Simplified\Dynamic-Cloud-Failure-and-QoS-Simulation-main"

# Optional: Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install required dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 2. Application Startup & Navigation

### Launching the Dashboard
Execute the following command in your terminal:

```powershell
& "C:\Users\Mahendra\AppData\Local\Python\bin\python.exe" -m streamlit run app.py
```

The interactive dashboard opens in your browser at:
`http://localhost:8501`

### Dashboard Visual Architecture
```
+-----------------------------------------------------------------------------------------+
| [Header] Dynamic Cloud Failure Detection and QoS-Aware Service Reselection              |
| [KPI Cards] Active Service | QoS Score | Operating Mode | Service Health Status         |
+-------------------+---------------------------------------------------------------------+
| [SIDEBAR CONTROLS]| [MAIN CONTENT TABS]                                                 |
|                   | Tab 1: Live Service Evaluation & Recommendation                     |
| 1. Operating Mode |   - Active Recommendation Banner & Decision Explanation             |
| 2. Fault Injector |   - Candidate Comparison & Ranking Table                            |
| 3. SLA Thresholds |   - Disqualification Details & Runner-Up Margin                     |
| 4. Hysteresis Cfg | Tab 2: Service Health & Monitoring Telemetry                        |
| 5. Periodic Monit |   - Health Distribution Donuts & State Indicators                   |
| 6. Global Reset   |   - Real-time Monitoring Event Stream & History                     |
|                   | Tab 3: Comparative QoS Radar & Multi-Attribute Analysis             |
|                   |   - Multi-Axis Plotly Radar Chart & Normalized Bar Charts           |
|                   | Tab 4: Audit Logs & Explainability Engine                           |
|                   |   - Chronological Reselection History & Override Event Logs         |
+-------------------+---------------------------------------------------------------------+
```

---

## 3. Step-by-Step Demonstration Sequence (12 Minutes)

### Phase A: Normal Operation & Baseline QoS Evaluation (Minutes 0:00 – 2:30)

#### Objective
Demonstrate baseline service loading, deterministic multi-attribute QoS normalization, and automatic selection of the optimal compliant service.

1. **Category Selection:** In the sidebar, select **Compute** (default).
2. **Review Summary KPI Cards:**
   - **Active Selected Service:** `SVC-C01 (NovaCompute Standard)`.
   - **QoS Score:** `0.8190`.
   - **Operating Mode:** `AUTOMATIC` (green badge).
   - **Service Health:** `HEALTHY` (green badge).
3. **Inspect Tab 1 ("Live Service Evaluation & Recommendation"):**
   - Point out the 5 candidate compute services (`SVC-C01` to `SVC-C05`).
   - All 5 candidates meet default SLA criteria ($150\text{ ms}$ max latency, $98.0\%$ min availability, $97.0\%$ min reliability).
   - `SVC-C01` is selected because its balanced trade-off ($45\text{ ms}$ latency, $\$0.04$ cost, $99.9\%$ availability, $99.5\%$ reliability) yields the highest aggregate score ($0.8190$), surpassing high-cost alternative `SVC-C02` ($0.7917$).
4. **Inspect Tab 3 ("Comparative QoS Radar"):**
   - Show the 4-axis radar chart displaying the trade-offs across latency, cost, availability, and reliability.
5. **Presenter Talking Point:**
   > *"The system uses min-max bound normalization across cost and benefit attributes. Even though SVC-C02 has lower latency (25 ms), its higher cost penalty results in SVC-C01 being selected as the mathematically optimal balanced candidate."*

---

### Phase B: Hard SLA Constraint Enforcement (Minutes 2:30 – 4:30)

#### Objective
Demonstrate that SLA constraints act as hard filters, disqualifying non-compliant services regardless of their aggregate score.

1. **Locate Sidebar "SLA Configuration" panel:**
   - Observe default Compute SLA: Max Latency $= 150.0\text{ ms}$, Min Availability $= 98.0\%$, Min Reliability $= 97.0\%$.
2. **Tighten Max Allowed Latency:**
   - Adjust the **Max Allowed Latency** slider from $150.0\text{ ms}$ down to **$50.0\text{ ms}$**.
3. **Observe Tab 1 Ranking Table:**
   - `SVC-C04` ($55.0\text{ ms}$), `SVC-C05` ($75.0\text{ ms}$), and `SVC-C03` ($120.0\text{ ms}$) are immediately marked **DISQUALIFIED** with red violation tags: `Latency > SLA max 50.0ms`.
   - Only two services remain eligible: `SVC-C02` ($25.0\text{ ms}$) and `SVC-C01` ($45.0\text{ ms}$).
   - `SVC-C01` remains active because its $45.0\text{ ms}$ complies with the tightened SLA.
4. **Restore SLA Threshold:**
   - Reset Max Allowed Latency back to $150.0\text{ ms}$.
5. **Presenter Talking Point:**
   > *"SLA filtering operates before QoS score ranking. A service violating even one SLA threshold is strictly disqualified from selection, preventing poor-quality services from being chosen simply due to a low invocation cost."*

---

### Phase C: Anti-Flapping Hysteresis & Micro-Jitter (Minutes 4:30 – 6:30)

#### Objective
Demonstrate how the hysteresis threshold $\Delta H$ and cooldown counters prevent service flapping when candidate rankings fluctuate marginally.

1. **Review Hysteresis Settings:**
   - In sidebar "Hysteresis Configuration", observe Minimum QoS Delta $\Delta H = \mathbf{0.05}$ and Cooldown Steps $= \mathbf{2}$.
2. **Inject Small Latency Spike on Active Service:**
   - In sidebar "Dynamic Fault Injection", select Target Service: `SVC-C01`.
   - Set Spike (ms) to **$15$** (latency increases from $45\text{ ms}$ to $60\text{ ms}$).
   - Click **"Inject Latency Spike"**.
3. **Observe System Response:**
   - `SVC-C01` QoS score decreases from $0.8190$ to $0.7765$.
   - Competitor `SVC-C02` now has a slightly higher score ($0.7917$).
   - The QoS improvement is $\Delta = 0.7917 - 0.7765 = 0.0152$, which is less than the threshold $\Delta H = 0.05$.
   - **System retains `SVC-C01`!**
   - Tab 1 decision explanation confirms: `Decision: RETAINED. Competitor improvement (+0.0152) does not exceed hysteresis threshold (0.0500)`.
4. **Presenter Talking Point:**
   > *"In distributed systems, micro-jitter causes constant rank oscillation. Our hysteresis mechanism prevents unnecessary reselection churn unless the alternative candidate offers a statistically meaningful QoS advantage exceeding delta H."*

---

### Phase D: Service Failure, Outage & Emergency Failover (Minutes 6:30 – 8:30)

#### Objective
Demonstrate instantaneous failure detection and emergency reselection that bypasses hysteresis cooldown when active service integrity is breached.

1. **Inject Hard SLA Breach:**
   - Select Target Service: `SVC-C01`.
   - Set Spike (ms) to **$150$** (total latency $= 195\text{ ms} > 150\text{ ms}$ SLA limit).
   - Click **"Inject Latency Spike"**.
2. **Observe Immediate Reselection:**
   - System immediately switches from `SVC-C01` to `SVC-C02 (AetherCompute HighPerf)`.
   - Reselection banner displays: `EMERGENCY_SLA_VIOLATION — Active service breached hard SLA limit`.
   - Cooldown timers are automatically bypassed.
3. **Simulate Total Outage on New Active Service:**
   - Select Target Service: `SVC-C02`.
   - Click **"Simulate Complete Outage"**.
4. **Observe Outage Failover:**
   - `SVC-C02` operational status transitions to `UNAVAILABLE` ($0.0\%$ availability and reliability).
   - System instantly switches to the next best eligible candidate: `SVC-C04 (TitanCompute Enterprise)`.
   - Detection latency: $0.9\text{ µs}$; Reselection latency: $38.6\text{ µs}$. Zero service outage exposure.
5. **Presenter Talking Point:**
   > *"While normal performance switching respects hysteresis and cooldown, hard SLA breaches and total outages trigger immediate emergency failover, prioritizing application availability over stability."*

---

### Phase E: Periodic Automatic Monitoring & Health Telemetry (Minutes 8:30 – 10:30)

#### Objective
Demonstrate background health reassessment, status categorization, and recovery detection without manual operator intervention.

1. **Open Tab 2 ("Service Health & Monitoring Telemetry"):**
   - Inspect the health donut chart and candidate telemetry table.
   - Note that `SVC-C02` is shown as `UNAVAILABLE` (red) and `SVC-C01` as `DEGRADED` (yellow).
2. **Restore Service `SVC-C01`:**
   - In sidebar, select `SVC-C01` and click **"Restore Service"**.
3. **Trigger Monitoring Cycle:**
   - Click the **"Inspect Health Now"** button in Tab 2.
4. **Observe Telemetry Stream:**
   - Monitoring cycle counter increments.
   - Log stream records: `Service 'NovaCompute Standard' recovered from UNAVAILABLE to healthy SLA-compliant baseline state`.
   - Candidate `SVC-C01` transitions to `RECOVERED` (green).
5. **Presenter Talking Point:**
   > *"The periodic monitoring engine operates on a configurable interval. It detects state transitions, identifies recovered services, and logs deduplicated audit events to provide complete operational observability."*

---

### Phase F: Controlled Manual Override & Safety Failover (Minutes 10:30 – 12:30)

#### Objective
Demonstrate operator manual override capabilities, strict SLA validation guards, and automated safety revocation under fault conditions.

1. **Activate Manual Override:**
   - In sidebar "Operating Mode", select **"Manual Service Override"**.
   - Select Candidate: **`SVC-C03 (EcoCompute Budget)`** (compliant with SLA, latency $120\text{ ms}$).
   - Enter Override Reason: *"Cost Optimization for non-critical batch processing"*.
   - Click **"Confirm Manual Override"**.
2. **Observe UI State:**
   - Top KPI card updates Mode badge to `MANUAL_OVERRIDE` (amber).
   - Selected service locks to `SVC-C03`, despite its lower QoS score ($0.2000$).
   - Reason badge clearly indicates manual operator enforcement.
3. **Demonstrate Safety Guard (Fault on Overridden Service):**
   - In sidebar fault injection, target `SVC-C03` and click **"Simulate Complete Outage"**.
4. **Observe Emergency Safety Termination:**
   - The system detects the failure on the manually overridden service.
   - **Manual override is immediately revoked** and mode returns to `AUTOMATIC`.
   - System executes emergency failover to the best eligible automatic candidate (`SVC-C01` or `SVC-C04`).
   - Audit trail records: `OVERRIDE_EVENT_EMERGENCY_TERMINATED`.
5. **Presenter Talking Point:**
   > *"Manual override empowers authorized operators to select preferred services, but safety guards guarantee that manual mode can never bypass SLA constraints. If an overridden service fails, the system revokes the override and executes emergency failover."*

---

### Phase G: Reset Simulation & History Audit Inspection (Minutes 12:30 – 14:00)

1. **Global Reset:** In sidebar, click **"Reset All Services"**.
   - All services return to default baseline QoS and operational status.
   - Mode returns to `AUTOMATIC`.
2. **Inspect Tab 4 ("Audit Logs & Explainability Engine"):**
   - Review chronological logs across:
     - Reselection decision audit trail.
     - Periodic monitoring events.
     - Manual override activation and termination logs.
3. **Conclusion & Q&A Transition:**
   > *"This concludes our live demonstration. We have shown deterministic QoS scoring, hard SLA filtering, anti-flapping hysteresis, periodic monitoring, emergency failover, and validated manual overrides with complete auditability."*

---

## 4. How to Reset the Simulation

If at any point during your presentation you wish to return to a clean baseline state:
1. Scroll to the bottom of the sidebar.
2. Click the red button: **"Reset All Services"**.
3. All service mutations, injected faults, and override states are instantly cleared, returning the dashboard to the initial Step 1 configuration.

---

## 5. Common Demonstration Pitfalls & Troubleshooting

| Issue / Error | Root Cause | Solution |
| :--- | :--- | :--- |
| **Browser shows blank or disconnected screen** | Streamlit process was interrupted in terminal. | Check terminal for exceptions; re-run `python -m streamlit run app.py`. |
| **All services display "DISQUALIFIED"** | SLA slider was left at an excessively tight value (e.g., $10\text{ ms}$). | Adjust Max Allowed Latency slider back to $150\text{ ms}$ or click "Reset All Services". |
| **"Activate Manual Override" button is disabled** | The candidate selected in the override dropdown violates current SLA or is unavailable. | Select an SLA-compliant service (marked `[Eligible]`) or relax the SLA threshold. |
| **Service does not switch after small latency spike** | Working as designed! Anti-flapping hysteresis is preventing unnecessary churn. | Point this out as proof of hysteresis stability, or increase the spike to $> 150\text{ ms}$ to demonstrate SLA breach. |
| **Port 8501 already in use** | Another instance of Streamlit is running. | Use a different port: `streamlit run app.py --server.port 8502`. |

