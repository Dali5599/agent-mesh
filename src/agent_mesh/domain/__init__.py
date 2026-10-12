"""
Domain models and entities for Agent Mesh.

This module aggregates and re-exports core domain models, configurations,
value objects, and exceptions used throughout the distributed service mesh.
"""

from agent_mesh.domain.config import (
    CircuitBreakerConfig,
    LoopDetectionConfig,
    MeshConfig,
    RateLimitConfig,
    TracingConfig,
)
from agent_mesh.domain.exceptions import (
    CircuitBreakerOpenError,
    DomainError,
    InvalidMessageError,
    LoopDetectedError,
    RateLimitExceededError,
    ServiceNotFoundError,
)
from agent_mesh.domain.messages import (
    AgentMessage,
    MessageHeader,
    MessagePayload,
    MessageType,
    PriorityLevel,
)
