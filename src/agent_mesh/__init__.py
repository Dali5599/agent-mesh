"""
Agent Mesh: High-Performance Distributed Service Mesh for AI Agent Swarms.
"""

__version__ = "0.1.0"

from agent_mesh.domain.models import (
    AgentMessage,
    AgentMetadata,
    MeshContext,
    RouteDecision,
)
from agent_mesh.orchestrator import AgentOrchestrator
from agent_mesh.resilience.circuit_breaker import CircuitBreaker, CircuitState
from agent_mesh.resilience.exceptions import (
    CircuitOpenError,
    InfiniteLoopDetectedError,
    MeshError,
    RateLimitExceededError,
)
from agent_mesh.resilience.loop_breaker import LoopBreaker
from agent_mesh.resilience.rate_limiter import RateLimiter
from agent_mesh.routing.engine import RoutingEngine
from agent_mesh.routing.registry import AgentRegistry
from agent_mesh.transport.client import MeshClient
from agent_mesh.transport.server import MeshServer
from agent_mesh.config.loader import load_config
from agent_mesh.config.schema import MeshConfig

__all__ = [
    "__version__",
    "AgentMessage",
    "AgentMetadata",
    "MeshContext",
    "RouteDecision",
    "AgentOrchestrator",
    "CircuitBreaker",
    "CircuitState",
    "MeshError",
    "CircuitOpenError",
    "InfiniteLoopDetectedError",
    "RateLimitExceededError",
    "LoopBreaker",
    "RateLimiter",
    "RoutingEngine",
    "AgentRegistry",
    "MeshClient",
    "MeshServer",
    "load_config",
    "MeshConfig",
]
