import asyncio
from typing import AsyncGenerator, Generator
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from agent_mesh.api.app import create_app
from agent_mesh.config.schema import MeshConfig, NodeConfig
from agent_mesh.domain.models import AgentCapability, AgentMetadata, MeshMessage, MessageType
from agent_mesh.orchestrator import MeshOrchestrator
from agent_mesh.transport.client import TransportClient
from agent_mesh.transport.server import TransportServer


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_agent_metadata() -> AgentMetadata:
    """Provide valid sample agent metadata for testing."""
    return AgentMetadata(
        agent_id="agent-alpha-01",
        name="AlphaAgent",
        version="1.0.0",
        capabilities=[AgentCapability(name="text_generation", version="1.0.0", weight=1.0)],
        endpoint="http://localhost:8001/mesh",
        tags={"environment": "test", "tier": "primary"},
    )


@pytest.fixture
def sample_mesh_message() -> MeshMessage:
    """Provide a valid sample mesh message for transport and routing tests."""
    return MeshMessage(
        message_id="msg-test-uuid-001",
        sender_id="agent-alpha-01",
        receiver_id="agent-beta-02",
        message_type=MessageType.REQUEST,
        payload={"prompt": "Analyze market trends for sk_test_mock_token_123"},
        trace_id="trace-test-xyz-999",
        ttl=5,
    )


@pytest.fixture
def mesh_config() -> MeshConfig:
    """Provide a baseline MeshConfig for test instances."""
    return MeshConfig(
        mesh_id="test-mesh-swarm",
        node=NodeConfig(
            node_id="node-test-01",
            host="127.0.0.1",
            port=8000,
            heartbeat_interval=1.0,
        ),
    )


@pytest.fixture
async def mesh_orchestrator(mesh_config: MeshConfig) -> AsyncGenerator[MeshOrchestrator, None]:
    """Provide an initialized MeshOrchestrator instance."""
    orchestrator = MeshOrchestrator(config=mesh_config)
    await orchestrator.start()
    yield orchestrator
    await orchestrator.stop()


@pytest.fixture
def transport_client() -> TransportClient:
    """Provide a configured TransportClient instance."""
    return TransportClient(timeout=5.0, max_retries=2)


@pytest.fixture
async def transport_server(mesh_config: MeshConfig, mesh_orchestrator: MeshOrchestrator) -> AsyncGenerator[TransportServer, None]:
    """Provide a running TransportServer instance tied to an orchestrator."""
    server = TransportServer(host=mesh_config.node.host, port=mesh_config.node.port, orchestrator=mesh_orchestrator)
    # Start server tasks or background processing if needed
    yield server


@pytest.fixture
def api_client(mesh_orchestrator: MeshOrchestrator) -> Generator[TestClient, None, None]:
    """Provide a synchronous TestClient for FastAPI endpoints."""
    app = create_app(orchestrator=mesh_orchestrator)
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_api_client(mesh_orchestrator: MeshOrchestrator) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous AsyncClient for FastAPI endpoint testing."""
    app = create_app(orchestrator=mesh_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
