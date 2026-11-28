# Cloud Command Center — Real Cloud Service API
## Phase 1: Real-World Multi-Cloud Deployable FastAPI Service

This module provides a production-ready, lightweight Python FastAPI service created for the **Cloud Command Center** platform. It is engineered to be deployed independently to multiple free cloud hosting platforms (such as **Render** and **Koyeb**) to provide real public health endpoints and real API endpoints.

---

## 1. Architecture & Design Principles

- **Framework:** FastAPI (ASGI on Uvicorn).
- **Zero Hardcoding:** All node identity parameters (`SERVICE_NAME`, `CLOUD_PROVIDER`, `PORT`) are injected via environment variables.
- **Port Dynamic Binding:** Uses `os.getenv("PORT", "8000")` and binds to `0.0.0.0` to comply with cloud container port mapping requirements.
- **Independence:** Decoupled from Streamlit and QoS simulation math, allowing real-world endpoint consumption in upcoming phases.
- **Interactive Documentation:** Built-in Swagger UI at `/docs` and ReDoc at `/redoc`.

---

## 2. API Endpoints Specification

| Method | Endpoint | Description | Sample Response Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Root info & endpoint catalog | `200 OK` |
| `GET` | `/health` | Lightweight node health check | `200 OK` |
| `GET` | `/api/demo` | Demo workload with provider context | `200 OK` |
| `GET` | `/docs` | Interactive Swagger API docs | `200 OK` |

### Endpoint Responses

#### `GET /health`
```json
{
  "status": "healthy",
  "service_name": "Cloud-A",
  "timestamp": "2026-11-28T08:35:10.123456Z"
}
```

#### `GET /api/demo`
```json
{
  "message": "Cloud service is responding",
  "service_name": "Cloud-A",
  "provider": "Render",
  "status": "success",
  "timestamp": "2026-11-28T08:35:10.123456Z"
}
```

#### `GET /`
```json
{
  "name": "Cloud Command Center Service Node",
  "service_name": "Cloud-A",
  "provider": "Render",
  "description": "Real cloud service instance for health monitoring and dynamic failover.",
  "version": "1.0.0",
  "endpoints": ["GET /", "GET /health", "GET /api/demo", "GET /docs"],
  "documentation": "/docs",
  "timestamp": "2026-11-28T08:35:10.123456Z"
}
```

---

## 3. Local Development Instructions

### Step 1: Navigate to Project Directory
```powershell
cd c:\Users\gost\Desktop\simplified-project
```

### Step 2: (Optional) Set up Python Virtual Environment
If you want an isolated environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Requirements
```powershell
pip install -r cloud_service/requirements.txt
```

### Step 4: Configure Local Environment Variables
Create a `.env` file or export environment variables:
```powershell
$env:SERVICE_NAME="Cloud-A"
$env:CLOUD_PROVIDER="Local-Dev"
$env:PORT="8000"
```

### Step 5: Start the FastAPI Server
Run with Uvicorn:
```powershell
python -m uvicorn cloud_service.main:app --host 0.0.0.0 --port 8000 --reload
```

Or run `main.py` directly:
```powershell
python cloud_service/main.py
```

### Step 6: Test Local Endpoints
Open these URLs in your web browser or test via `curl`:
- Root Info: [http://localhost:8000/](http://localhost:8000/)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)
- Demo API: [http://localhost:8000/api/demo](http://localhost:8000/api/demo)
- Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Step 7: Run Automated Tests
```powershell
python -m pytest cloud_service/test_main.py -v
```

---

## 4. Multi-Cloud Deployment Guide

The **same codebase** is deployed twice with different environment variables to instantiate two independent cloud nodes.

```
                  ┌────────────────────────────────────────────────────────┐
                  │ GitHub Repository: simplified-project                 │
                  │ Directory: /cloud_service                              │
                  └───────────────┬────────────────────────┬───────────────┘
                                  │                        │
                    Deployment A  │                        │  Deployment B
                                  ▼                        ▼
                      ┌──────────────────────┐   ┌──────────────────────┐
                      │    Render (Web)      │   │    Koyeb (Service)   │
                      │ SERVICE_NAME=Cloud-A │   │ SERVICE_NAME=Cloud-B │
                      │ CLOUD_PROVIDER=Render│   │ CLOUD_PROVIDER=Koyeb │
                      └──────────────────────┘   └──────────────────────┘
```

---

### Deployment A: Render Deployment (Cloud-A)

Render offers a Free Web Service tier (spins down after 15 minutes of inactivity; restarts on incoming HTTP request).

1. **Sign in to Render:**
   - Go to [https://dashboard.render.com](https://dashboard.render.com) and log in.

2. **Create New Web Service:**
   - Click **New +** $\to$ **Web Service**.
   - Select **Build and deploy from a Git repository**.
   - Connect your GitHub repository (`simplified-project`).

3. **Configure Service Settings:**
   - **Name:** `cloud-command-service-a` (or any available name).
   - **Region:** Choose closest region (e.g., Oregon, Frankfurt, Singapore).
   - **Branch:** `main`.
   - **Root Directory:** `cloud_service` *(Important: tells Render where to find requirements.txt and main.py)*.
   - **Runtime:** `Python 3`.
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** Select **Free**.

4. **Add Environment Variables:**
   Under **Environment Variables**, add:
   | Key | Value |
   | :--- | :--- |
   | `SERVICE_NAME` | `Cloud-A` |
   | `CLOUD_PROVIDER` | `Render` |
   | `PYTHON_VERSION` | `3.11.9` |

5. **Deploy & Obtain Public URL:**
   - Click **Create Web Service**.
   - Render will build and deploy the container.
   - Once deployment completes (status: *Live*), note your public URL:
     `https://<your-service-name>.onrender.com`
   - Test endpoints:
     - `https://<your-service-name>.onrender.com/health`
     - `https://<your-service-name>.onrender.com/api/demo`

---

### Deployment B: Koyeb Deployment (Cloud-B)

Koyeb provides a free Eco tier with fast microVM deployments.

1. **Sign in to Koyeb:**
   - Go to [https://app.koyeb.com](https://app.koyeb.com) and log in.

2. **Create New Service:**
   - Click **Create App** or **Create Service**.
   - Select **GitHub** as the deployment method.
   - Select your repository (`simplified-project`) and branch `main`.

3. **Configure Service Settings:**
   - **Work directory / Root directory:** Set to `cloud_service`.
   - **Builder:** Select **Buildpack** or **Standard Python**.
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Run / Start Command:**
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** Select **Free (Nano)**.

4. **Add Environment Variables:**
   Under **Environment Variables**, add:
   | Key | Value |
   | :--- | :--- |
   | `SERVICE_NAME` | `Cloud-B` |
   | `CLOUD_PROVIDER` | `Koyeb` |

5. **Deploy & Obtain Public URL:**
   - Click **Deploy**.
   - Koyeb will provision the microVM.
   - Once deployed (status: *Healthy*), note your public URL:
     `https://<your-app-name>.koyeb.app`
   - Test endpoints:
     - `https://<your-app-name>.koyeb.app/health`
     - `https://<your-app-name>.koyeb.app/api/demo`

---

## 5. Free-Tier Operational Notes & Caveats

- **Cold Starts:** Free instances on Render and Koyeb spin down after periods of inactivity. An initial wake-up request may experience a latency of 15–40 seconds.
- **Port Allocation:** Platforms dynamically inject the `$PORT` environment variable. The code automatically binds to this port or defaults to `8000`.
- **Stateless Design:** No state is preserved between container restarts, ensuring zero side-effects and continuous idempotent health monitoring.
