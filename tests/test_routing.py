import pytest
from typing import Dict, Any

from agent_mesh.routing.registry import AgentRegistry, AgentNode
from agent_mesh.routing.engine import RoutingEngine, RouteCriteria
from agent_mesh.domain.models import AgentCapability, AgentStatus, Message, Priority


def test_agent_registry_registration_and_lookup() -> None:
    registry = AgentRegistry()
    node = AgentNode(
        agent_id="agent-1",
        capabilities={AgentCapability.NLP, AgentCapability.SUMMARIZATION},
        endpoint="http://localhost:8001",
        status=AgentStatus.ACTIVE,
        metadata={"region": "us-east"}
    )
    
    registry.register(node)
    fetched = registry.get("agent-1")
    assert fetched is not None
    assert fetched.agent_id == "agent-1"
    assert AgentCapability.NLP in fetched.capabilities
    
    registry.unregister("agent-1")
    assert registry.get("agent-1") is None


def test_routing_engine_criteria_matching() -> None:
    registry = AgentRegistry()
    node1 = AgentNode(
        agent_id="agent-nlp-1",
        capabilities={AgentCapability.NLP},
        endpoint="http://localhost:8001",
        status=AgentStatus.ACTIVE,
        metadata={"region": "us-west", "load": 0.2}
    )
    node2 = AgentNode(
        agent_id="agent-nlp-2",
        capabilities={AgentCapability.NLP},
        endpoint="http://localhost:8002",
        status=AgentStatus.ACTIVE,
        metadata={"region": "us-east", "load": 0.8}
    )
    registry.register(node1)
    registry.register(node2)
    
    engine = RoutingEngine(registry=registry)
    
    criteria = RouteCriteria(
        required_capability=AgentCapability.NLP,
        metadata_filters={"region": "us-west"}
    )
    
    selected = engine.route(criteria)
    assert selected is not None
    assert selected.agent_id == "agent-nlp-1"


def test_routing_engine_no_match_raises() -> None:
    registry = AgentRegistry()
    engine = RoutingEngine(registry=registry)
    
    criteria = RouteCriteria(
        required_capability=AgentCapability.CODE_GEN
    )
    
    with pytest.raises(ValueError, match="No healthy agent found matching routing criteria"):
        engine.route(criteria)


def test_agent_registry_list_active() -> None:
    registry = AgentRegistry()
    node1 = AgentNode(
        agent_id="agent-active",
        capabilities={AgentCapability.REASONING},
        endpoint="http://localhost:9001",
        status=AgentStatus.ACTIVE
    )
    node2 = AgentNode(
        agent_id="agent-busy",
        capabilities={AgentCapability.REASONING},
        endpoint="http://localhost:9002",
        status=AgentStatus.BUSY
    )
    
    registry.register(node1)
    registry.register(node2)
    
    active_nodes = registry.list_active()
    assert len(active_nodes) == 1
    assert active_nodes[0].agent_id == "agent-active"
