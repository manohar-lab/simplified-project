"""
Cloud Service API — Cloud Command Center
========================================
Independent production-ready FastAPI service deployable across multiple cloud platforms.
Configured dynamically via environment variables (SERVICE_NAME, CLOUD_PROVIDER).
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Configuration from Environment
# -----------------------------------------------------------------------------
def get_service_name() -> str:
    """Retrieve service name from environment with safe default."""
    return os.getenv("SERVICE_NAME", "Cloud-A")

def get_cloud_provider() -> str:
    """Retrieve cloud provider from environment with safe default."""
    return os.getenv("CLOUD_PROVIDER", "Render")

# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "healthy"})
    service_name: str = Field(..., json_schema_extra={"example": "Cloud-A"})
    timestamp: str = Field(..., json_schema_extra={"example": "2026-11-28T08:35:00.000000Z"})

class DemoResponse(BaseModel):
    message: str = Field(..., json_schema_extra={"example": "Cloud service is responding"})
    service_name: str = Field(..., json_schema_extra={"example": "Cloud-A"})
    provider: str = Field(..., json_schema_extra={"example": "Render"})
    status: str = Field(..., json_schema_extra={"example": "success"})
    timestamp: str = Field(..., json_schema_extra={"example": "2026-11-28T08:35:00.000000Z"})

class ServiceInfoResponse(BaseModel):
    name: str
    service_name: str
    provider: str
    description: str
    version: str
    endpoints: List[str]
    documentation: str
    timestamp: str

# -----------------------------------------------------------------------------
# FastAPI Application Factory
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Cloud Command Center — Real Cloud Service",
    description=(
        "Production-ready FastAPI service designed for multi-cloud deployment "
        "and health evaluation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for cross-origin dashboard/client interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def current_utc_iso() -> str:
    """Return formatted ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get(
    "/",
    response_model=ServiceInfoResponse,
    summary="Service Information",
    tags=["General"],
)
async def root() -> Dict[str, Any]:
    """Return basic information about the running API and available endpoints."""
    return {
        "name": "Cloud Command Center Service Node",
        "service_name": get_service_name(),
        "provider": get_cloud_provider(),
        "description": "Real cloud service instance for health monitoring and dynamic failover.",
        "version": "1.0.0",
        "endpoints": [
            "GET /",
            "GET /health",
            "GET /api/demo",
            "GET /docs",
        ],
        "documentation": "/docs",
        "timestamp": current_utc_iso(),
    }

@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    tags=["Monitoring"],
)
async def health_check() -> Dict[str, Any]:
    """
    Lightweight health check endpoint returning HTTP 200, service name, and UTC timestamp.
    Suitable for frequent polling by QoS monitors or load balancers.
    """
    return {
        "status": "healthy",
        "service_name": get_service_name(),
        "timestamp": current_utc_iso(),
    }

@app.get(
    "/api/demo",
    response_model=DemoResponse,
    status_code=status.HTTP_200_OK,
    summary="Demo API Endpoint",
    tags=["Demo"],
)
async def demo_api() -> Dict[str, Any]:
    """
    Sample payload endpoint returning service identity, cloud provider, and timestamp.
    """
    return {
        "message": "Cloud service is responding",
        "service_name": get_service_name(),
        "provider": get_cloud_provider(),
        "status": "success",
        "timestamp": current_utc_iso(),
    }

# -----------------------------------------------------------------------------
# Standalone Execution Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
