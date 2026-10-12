from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, validator


class AgentStatus(str, Enum):
    """Lifecycle status of an agent node within the mesh."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    TERMINATED = "terminated"


class MessageType(str, Enum):
    """Categorization of inter-agent messages for traffic management."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STREAM_CHUNK = "stream_chunk"
    HEARTBEAT = "heartbeat"
    CONTROL_SIGNAL = "control_signal"
    ERROR = "error"


class CircuitState(str, Enum):
    """State of the circuit breaker for resilience."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AgentNode(BaseModel):
    """Represents an autonomous AI agent registered within the service mesh."""
    agent_id: str = Field(..., description="Unique immutable identifier for the agent instance.")
    name: str = Field(..., description="Human-readable or service-level name of the agent.")
    version: str = Field("1.0.0", description="Semantic version of the agent software/model.")
    capabilities: List[str] = Field(default_factory=list, description="List of capabilities or tools supported by the agent.")
    endpoint: str = Field(..., description="Network endpoint URI where the agent can be reached.")
    status: AgentStatus = Field(default=AgentStatus.INITIALIZING, description="Current operational status.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata key-values for routing and filtering.")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the agent joined the mesh.")
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the last received heartbeat.")

    @validator('agent_id')
    def validate_agent_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("agent_id cannot be empty or whitespace.")
        return v


class RoutingContext(BaseModel):
    """Contextual metadata for distributed tracing, loop detection, and routing policies."""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Distributed trace identifier.")
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Current execution span identifier.")
    parent_span_id: Optional[str] = Field(None, description="Parent span identifier for tracing trees.")
    path: List[str] = Field(default_factory=list, description="Ordered history of agent IDs this message has traversed.")
    hop_count: int = Field(0, ge=0, description="Number of hops/transfers this message has undergone.")
    max_hops: int = Field(50, ge=1, description="Hard limit on hops to enforce infinite loop prevention.")
    priority: int = Field(0, ge=0, le=100, description="Routing priority level (0 = lowest, 100 = highest).")
    timeout_seconds: float = Field(30.0, gt=0, description="Execution timeout budget for the request.")

    def add_hop(self, agent_id: str) -> RoutingContext:
        """Creates a new routing context with an appended hop for the given agent."""
        new_path = self.path + [agent_id]
        return RoutingContext(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
            path=new_path,
            hop_count=self.hop_count + 1,
            max_hops=self.max_hops,
            priority=self.priority,
            timeout_seconds=self.timeout_seconds,
        )


class Message(BaseModel):
    """Encapsulates payload data transmitted between agent nodes."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the message.")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Identifier linking requests to responses.")
    sender_id: str = Field(..., description="Agent ID of the message originator.")
    recipient_id: Optional[str] = Field(None, description="Target Agent ID, or None for broadcast/load-balanced routing.")
    message_type: MessageType = Field(..., description="Type classification of the message.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured content or arguments for the agent.")
    routing: RoutingContext = Field(default_factory=RoutingContext, description="Routing, tracing, and loop-detection context.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")

    @validator('sender_id')
    def validate_sender(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("sender_id cannot be empty.")
        return v


class MeshConfig(BaseModel):
    """Global configuration settings for the Agent Service Mesh."""
    mesh_name: str = Field("default-agent-mesh", description="Name of the mesh deployment.")
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for this specific mesh node/gateway.")
    host: str = Field("0.0.0.0", description="Network interface binding address.")
    port: int = Field(8080, ge=1, le=65535, description="Network port for mesh communication.")
    heartbeat_interval_seconds: float = Field(5.0, gt=0, description="Frequency of agent health check heartbeats.")
    node_timeout_seconds: float = Field(15.0, gt=0, description="Duration before an unresponsive agent is marked offline.")
    default_max_hops: int = Field(32, ge=1, description="Default maximum routing hops for loop prevention.")
    circuit_breaker_failure_threshold: int = Field(5, ge=1, description="Failures required to trip the circuit breaker.")
    circuit_breaker_recovery_timeout: float = Field(30.0, gt=0, description="Time window before attempting circuit reset.")
    enable_telemetry: bool = Field(True, description="Flag to enable or disable distributed tracing and metrics.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional mesh-wide configuration properties.")

    @validator('mesh_name')
    def validate_mesh_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("mesh_name cannot be empty.")
        return v
