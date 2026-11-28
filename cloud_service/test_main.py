"""
Tests for Cloud Service API (FastAPI)
======================================
Verifies:
1. Root endpoint responds with status 200 and schema.
2. Health endpoint returns HTTP 200 with service_name and UTC timestamp.
3. Demo endpoint returns configured service_name and provider.
4. Environment variable customization (Cloud-A / Render vs Cloud-B / Koyeb).
"""

import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

# Import app from main
from cloud_service.main import app, get_service_name, get_cloud_provider


@pytest.fixture
def client():
    """Create a FastAPI TestClient fixture."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test 1: Root endpoint responds with 200 and valid structure."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "service_name" in data
    assert "provider" in data
    assert "endpoints" in data
    assert any("/health" in ep for ep in data["endpoints"])
    assert any("/api/demo" in ep for ep in data["endpoints"])


def test_health_endpoint_status(client):
    """Test 2: Health endpoint returns HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_health_endpoint_content(client, monkeypatch):
    """Test 3: Health response contains configured service name and valid timestamp."""
    monkeypatch.setenv("SERVICE_NAME", "Cloud-A")
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "Cloud-A"
    assert "timestamp" in data
    
    # Verify timestamp is ISO-8601 parsable
    parsed = datetime.fromisoformat(data["timestamp"])
    assert parsed is not None


def test_demo_endpoint_service_name_and_provider_deployment_a(client, monkeypatch):
    """Test 4: Demo endpoint returns configured service name and provider for Deployment A."""
    monkeypatch.setenv("SERVICE_NAME", "Cloud-A")
    monkeypatch.setenv("CLOUD_PROVIDER", "Render")

    response = client.get("/api/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "Cloud-A"
    assert data["provider"] == "Render"
    assert data["status"] == "success"
    assert data["message"] == "Cloud service is responding"
    assert "timestamp" in data


def test_demo_endpoint_service_name_and_provider_deployment_b(client, monkeypatch):
    """Test 5: Demo endpoint returns configured service name and provider for Deployment B."""
    monkeypatch.setenv("SERVICE_NAME", "Cloud-B")
    monkeypatch.setenv("CLOUD_PROVIDER", "Koyeb")

    response = client.get("/api/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["service_name"] == "Cloud-B"
    assert data["provider"] == "Koyeb"
    assert data["status"] == "success"
    assert data["message"] == "Cloud service is responding"
    assert "timestamp" in data


def test_fallback_defaults(client, monkeypatch):
    """Test safe defaults when optional environment variables are missing."""
    monkeypatch.delenv("SERVICE_NAME", raising=False)
    monkeypatch.delenv("CLOUD_PROVIDER", raising=False)

    assert get_service_name() == "Cloud-A"
    assert get_cloud_provider() == "Render"
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service_name"] == "Cloud-A"
