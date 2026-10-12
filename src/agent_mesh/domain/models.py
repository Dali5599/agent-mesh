from __future__ import annotations
import uuid
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field

class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    TERMINATED = "terminated"

class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STREAM_CHUNK = "stream_chunk"
    HEARTBEAT = "heartbeat"
    CONTROL_SIGNAL = "control_signal"
    ERROR = "error"

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class RoutingStrategy(str, Enum):
    LEAST_LOADED = "least_loaded"
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    LATENCY_AWARE = "latency_aware"
    WEIGHTED = "weighted"

class AgentCapability:
    NLP = "nlp"
    SUMMARIZATION = "summarization"
    CODE_GEN = "code_gen"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    def __init__(self, name="nlp", version="1.0.0", weight=1.0):
        self.name = name
        self.version = version
        self.weight = weight
    def __str__(self): return self.name
    def __repr__(self): return f"AgentCapability({self.name})"
    def __eq__(self, other):
        if isinstance(other, AgentCapability): return self.name == other.name
        return self.name == str(other)
    def __hash__(self): return hash(self.name)

class AgentNode(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field("default-agent")
    version: str = Field("1.0.0")
    capabilities: Any = Field(default_factory=list)
    endpoint: str = Field("http://localhost:8080")
    status: AgentStatus = Field(default=AgentStatus.ACTIVE)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: Any = Field(default_factory=time.time)

    @property
    def id(self) -> str:
        return self.agent_id

class RoutingContext(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    path: List[str] = Field(default_factory=list)
    hop_count: int = 0
    max_hops: int = 50
    priority: int = 0
    timeout_seconds: float = 30.0

class RouteCriteria(BaseModel):
    required_capability: Optional[Any] = None
    metadata_filters: Optional[Dict[str, Any]] = None
    strategy: Optional[RoutingStrategy] = None

class Message(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = Field("agent-sender")
    recipient_id: Optional[str] = None
    receiver_id: Optional[str] = None
    message_type: MessageType = Field(MessageType.TASK_REQUEST)
    payload: Dict[str, Any] = Field(default_factory=dict)
    routing: RoutingContext = Field(default_factory=RoutingContext)
    trace_id: Optional[str] = None
    ttl: int = 30
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def id(self) -> str:
        return self.message_id
    @property
    def sender(self) -> str:
        return self.sender_id
    @property
    def receiver(self) -> str:
        return self.receiver_id or self.recipient_id or ""

class MeshConfig(BaseModel):
    mesh_name: str = "default-agent-mesh"
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    host: str = "0.0.0.0"
    port: int = 8080

AgentMetadata = AgentNode
MeshMessage = Message
AgentMessage = Message
Priority = int
MeshContext = RoutingContext
RouteDecision = RoutingContext
AgentRequest = Message
AgentResponse = Message
NodeRegistration = AgentNode
MeshResponse = Message
ErrorResponse = Message
Capability = AgentCapability

class MeshHealthStatus(BaseModel):
    status: str = "healthy"
    nodes_count: int = 0
