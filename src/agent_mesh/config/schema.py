"""
Strict validation schemas for cluster topology, node limits, and mesh configurations.
"""

from enum import Enum
import re
from typing import List, Dict, Any, Optional
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)

HOST_PORT_REGEX = re.compile(
    r"^([a-zA-Z0-9.-]+|\[[a-fA-F0-9:]+\]):([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$"
)


class NodeRole(str, Enum):
    """Supported node operational roles within the swarm mesh."""
    LEADER = "leader"
    WORKER = "worker"
    GATEWAY = "gateway"
    RELAY = "relay"


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies for traffic routing across agent swarm nodes."""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    LATENCY_AWARE = "latency_aware"


class CycleDetectionMode(str, Enum):
    """Execution mode for deterministic infinite loop detection in agent chains."""
    STRICT = "strict"
    PERMISSIVE = "permissive"
    DISABLED = "disabled"


class NodeLimitsConfig(BaseModel):
    """Resource constraints and limits enforced per swarm node."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_nodes: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Maximum allowed nodes in the mesh cluster."
    )
    max_agents_per_node: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum active agents per individual node."
    )
    max_memory_mb_per_node: int = Field(
        default=8192,
        ge=256,
        le=1048576,
        description="Maximum memory allocated per node in Megabytes."
    )
    max_concurrent_tasks_per_agent: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum concurrent executions allowed per agent."
    )
    max_payload_bytes: int = Field(
        default=10485760,
        ge=1024,
        le=1073741824,
        description="Maximum message payload size in bytes (default 10MB)."
    )
    cpu_utilization_threshold_pct: float = Field(
        default=85.0,
        ge=10.0,
        le=99.0,
        description="CPU usage percentage triggering load rejection or shedding."
    )


class ClusterTopologyConfig(BaseModel):
    """Topological architecture definition for the agent cluster."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    cluster_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9\-_]+$",
        description="Unique identifier for the agent mesh cluster."
    )
    datacenter: str = Field(
        default="dc-1",
        min_length=2,
        max_length=32,
        description="Datacenter identifier."
    )
    region: str = Field(
        default="us-east-1",
        min_length=2,
        max_length=32,
        description="Geographic region of the cluster."
    )
    seed_nodes: List[str] = Field(
        ...,
        min_items=1,
        description="List of seed node addresses in host:port format."
    )
    heartbeat_interval_seconds: float = Field(
        default=2.0,
        gt=0.1,
        le=60.0,
        description="Interval between node heartbeat signals."
    )
    node_timeout_seconds: float = Field(
        default=10.0,
        gt=0.5,
        le=300.0,
        description="Duration before marking an unresponsive node as dead."
    )

    @field_validator("seed_nodes")
    @classmethod
    def validate_seed_nodes(cls, seed_nodes: List[str]) -> List[str]:
        """Ensure all seed nodes conform to valid host:port formatting."""
        for address in seed_nodes:
            if not HOST_PORT_REGEX.match(address):
                raise ValueError(
                    f"Invalid seed node endpoint address format '{address}'. Expected 'host:port'."
                )
        return seed_nodes

    @model_validator(mode="after")
    def validate_timeouts(self) -> "ClusterTopologyConfig":
        """Verify node_timeout_seconds is strictly greater than heartbeat_interval_seconds."""
        if self.node_timeout_seconds <= self.heartbeat_interval_seconds:
            raise ValueError(
                f"node_timeout_seconds ({self.node_timeout_seconds}s) must be strictly greater than "
                f"heartbeat_interval_seconds ({self.heartbeat_interval_seconds}s)."
            )
        return self


class CircuitBreakerConfig(BaseModel):
    """Fault tolerance and circuit breaker configurations."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = Field(default=True, description="Enable or disable circuit breaker mechanism.")
    failure_threshold: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Consecutive failure count required to trip the circuit."
    )
    recovery_time_seconds: float = Field(
        default=30.0,
        gt=0.5,
        le=3600.0,
        description="Cooldown duration before entering half-open state."
    )
    half_open_max_requests: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Probing requests allowed during half-open state."
    )


class RateLimiterConfig(BaseModel):
    """Traffic rate limiting and burst capacity control."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = Field(default=True, description="Enable or disable token bucket rate limiting.")
    requests_per_second: int = Field(
        default=500,
        ge=1,
        le=1000000,
        description="Sustained rate limit per second."
    )
    burst_capacity: int = Field(
        default=1000,
        ge=1,
        le=2000000,
        description="Maximum token capacity allowing request bursts."
    )

    @model_validator(mode="after")
    def validate_burst(self) -> "RateLimiterConfig":
        """Verify burst capacity is at least equal to sustained requests per second."""
        if self.burst_capacity < self.requests_per_second:
            raise ValueError(
                f"burst_capacity ({self.burst_capacity}) cannot be less than "
                f"requests_per_second ({self.requests_per_second})."
            )
        return self


class LoopDetectionConfig(BaseModel):
    """Settings for deterministic call chain cycle detection."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = Field(default=True, description="Enable or disable loop detection.")
    max_call_depth: int = Field(
        default=32,
        ge=2,
        le=256,
        description="Maximum nested agent invocation depth before cycle inspection."
    )
    mode: CycleDetectionMode = Field(
        default=CycleDetectionMode.STRICT,
        description="Handling mode when a loop is identified."
    )
    trace_ttl_seconds: float = Field(
        default=300.0,
        gt=1.0,
        le=86400.0,
        description="Time-to-live for stored call graph execution paths."
    )


class AgentMeshConfig(BaseModel):
    """Root configuration schema for Agent Mesh distributed service mesh."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(
        default="1.0",
        pattern=r"^\d+\.\d+$",
        description="Configuration file schema version."
    )
    environment: str = Field(
        default="production",
        min_length=2,
        max_length=32,
        description="Target deployment environment (e.g. production, staging, dev)."
    )
    topology: ClusterTopologyConfig = Field(..., description="Cluster topology settings.")
    limits: NodeLimitsConfig = Field(default_factory=NodeLimitsConfig, description="Node resource limits.")
    circuit_breaker: CircuitBreakerConfig = Field(
        default_factory=CircuitBreakerConfig,
        description="Circuit breaker fault tolerance rules."
    )
    rate_limiter: RateLimiterConfig = Field(
        default_factory=RateLimiterConfig,
        description="Traffic rate limiting settings."
    )
    loop_detection: LoopDetectionConfig = Field(
        default_factory=LoopDetectionConfig,
        description="Infinite loop detection rules."
    )
    load_balancing: LoadBalancingStrategy = Field(
        default=LoadBalancingStrategy.ROUND_ROBIN,
        description="Default traffic load balancing strategy."
    )


MeshConfig = AgentMeshConfig
NodeConfig = NodeLimitsConfig


class TransportConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    timeout_seconds: float = 30.0
