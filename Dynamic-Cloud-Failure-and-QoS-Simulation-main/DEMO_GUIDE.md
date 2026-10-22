# Live Demonstration Guide

## Dynamic Cloud Failure Detection and QoS-Aware Service Reselection

This guide provides a verified, step-by-step demonstration sequence for presenting this project during evaluations and project reviews.

---

## 1. Prerequisites & Launch Command

Open Windows PowerShell in the project directory:

```powershell
cd "c:\Users\Mahendra\OneDrive\Desktop\Dynamic-Cloud-Failure-and-QoS-Simulation"

# Option A (Using .venv):
.\.venv\Scripts\Activate.ps1
streamlit run app.py

# Option B (Using Anaconda directly):
& "$env:USERPROFILE\anaconda3\python.exe" -m streamlit run app.py
```

The dashboard will open automatically in your browser at:
`http://localhost:8501`

---

## 2. Step-by-Step Demonstration Sequence

### Step 1: Baseline State Inspection
1. **Category**: Ensure the category selector is set to **`Compute`**.
2. **Review Metrics Cards**:
   - Total Category Services: `5`
   - Healthy / Available: `5`
   - Unavailable / Outage: `0 down`
   - Top Recommended: `NovaCompute Standard` (QoS Score: `0.8168` with default weights)
3. **Candidate Table**: Show the five candidates (`SVC-C01` to `SVC-C05`) with their baseline Latency, Cost, Availability, and Reliability.
4. **Key Talking Point**: "The system normalizes metrics using fixed baseline reference bounds, avoiding artificial score warping when a failure occurs."

---

### Step 2: Injecting a Latency Spike (QoS Degradation)
1. **Target**: Select `SVC-C01 - NovaCompute Standard` in the sidebar.
2. **Parameters**: Set Spike to `150` ms.
3. **Action**: Click **`⚡ Inject Latency Spike`**.
4. **Observed Behavior**:
   - Target latency increases from `45.0ms` to `195.0ms`.
   - `SVC-C01` QoS score drops from `0.8168` to `0.5405`.
   - **Dynamic Reselection Occurs**: `AetherCompute HighPerf` (`SVC-C02`) automatically becomes the #1 recommendation (QoS: `0.7937`).
   - The **Recommendation Panel** displays the exact reselection trigger:
     > *"Reselection trigger: Prior choice 'NovaCompute Standard' (SVC-C01) QoS score (0.5405) dropped below 'AetherCompute HighPerf' (0.7937)."*
   - The Plotly bar chart visually displays `SVC-C02` in blue (Recommended) and `SVC-C01` with a diminished bar.
5. **Reviewer Note on Scoring Stability (No Reselection for Minor Spikes)**:
   - If a minor spike is injected (e.g., `+5ms`), `SVC-C01` latency increases to `50.0ms` and its QoS score decreases slightly from `0.8168` to `0.7984`.
   - Because `0.7984` remains higher than `SVC-C02` (`0.7937`), the recommendation correctly does **not** change.
   - *Talking point*: The scoring logic prevents flapping or unnecessary reselection when minor fluctuations do not alter the relative multi-criteria ranking.

---

### Step 3: Simulating a Service Outage (Failure Exclusion)
1. **Target**: In the sidebar, select `SVC-C02 - AetherCompute HighPerf`.
2. **Action**: Click **`🔴 Simulate Outage`**.
3. **Observed Behavior**:
   - `SVC-C02` status transitions to `UNAVAILABLE` (marked with a red badge).
   - Summary metric updates: `Unavailable / Outage` shows `1 (+1 down)`.
   - **Immediate Exclusion**: Despite having a high baseline score, `SVC-C02` is disqualified from recommendation.
   - **Alternative Reselection**: `TitanCompute Enterprise` (`SVC-C04`) is selected as the top eligible candidate (QoS: `0.7634`).
   - The *Excluded Services* panel lists `SVC-C02` with the reason:
     > *"Service is marked UNAVAILABLE (simulated outage/down)."*

---

### Step 4: Total Category Failure (Graceful Degradation)
1. **Action**: For demonstration of edge-case safety, click **`🔴 Simulate Outage`** on each remaining Compute service (`SVC-C01`, `SVC-C03`, `SVC-C04`, `SVC-C05`).
2. **Observed Behavior**:
   - The application does not crash or throw unhandled exceptions.
   - A prominent alert banner appears:
     > *"🚨 NO ELIGIBLE SERVICE AVAILABLE! All 5 service(s) in category 'Compute' are currently UNAVAILABLE."*
   - Top Recommended metric reflects: `None (Outage)` (QoS: `N/A`).

---

### Step 5: Service Restoration and Global Reset
1. **Single Restoration**:
   - Select `SVC-C04` in the sidebar and click **`🟢 Restore Service`**.
   - Notice that `SVC-C04` immediately returns to `AVAILABLE` and becomes the recommended service.
2. **Global Reset**:
   - Click **`🔄 Reset All Services`**.
   - **Observed Behavior**:
     - All 5 compute services return to `AVAILABLE`.
     - Baseline latency, availability, and reliability are restored.
     - `SVC-C01` is once again the top recommended candidate (QoS: `0.8168`).
     - Re-running reset is idempotent (causes zero state drift).

---

### Step 6: Audit Log Inspection
1. Scroll to the **`Simulation Event Audit Log`** table at the bottom of the page.
2. Demonstrate how every action (Latency Spike, Simulate Outage, Restore Service, Reset Simulation) was recorded with timestamp, target service, and descriptive outcome.

---

## 3. Running Automated Tests Before Review

To prove system correctness and compliance with acceptance criteria:

```powershell
# Option A (Using .venv):
.\.venv\Scripts\pytest.exe -v

# Option B (Using Anaconda directly):
& "$env:USERPROFILE\anaconda3\python.exe" -m pytest -v
```

Expected result: **`21 passed in < 0.20s`**.
