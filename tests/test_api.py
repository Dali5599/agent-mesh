import pytest
from fastapi.testclient import TestClient
from agent_mesh.api.app import create_app
from agent_mesh.domain.models import AgentMessage, MeshResponse

@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_metrics_endpoint(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "active_circuits" in data
    assert "mesh_uptime_seconds" in data

def test_agents_list(client: TestClient) -> None:
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_dispatch_message_success(client: TestClient) -> None:
    payload = {
        "sender_id": "agent-alpha",
        "receiver_id": "agent-beta",
        "payload": {"task": "analyze_data", "data": [1, 2, 3]},
        "metadata": {"api_key": "sk_test_mockkey12345"}
    }
    response = client.post("/api/v1/dispatch", json=payload)
    assert response.status_code in (200, 201, 202)
    data = response.json()
    assert "status" in data
    assert data["status"] in ("success", "dispatched", "routed")

def test_dispatch_message_validation_error(client: TestClient) -> None:
    # Missing required fields like sender_id and receiver_id
    payload = {
        "payload": {"task": "fail"}
    }
    response = client.post("/api/v1/dispatch", json=payload)
    assert response.status_code == 422

def test_circuit_breakers_status(client: TestClient) -> None:
    response = client.get("/api/v1/resilience/circuit-breakers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (list, dict))

def test_rate_limiter_status(client: TestClient) -> None:
    response = client.get("/api/v1/resilience/rate-limiters")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, (list, dict))
