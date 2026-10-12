"""Core routing engine for directing agent messages across the mesh based on capabilities, load, and content metadata."""

from enum import Enum
import logging
import math
import random
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from agent_mesh.domain.models import (
    AgentCapability,
    AgentNode,
    AgentStatus,
    Message,
    RouteDecision,
    RoutingStrategy,
)
from agent_mesh.telemetry.tracer import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


class RoutingError(Exception):
    """Base exception for routing failures."""

    pass


class NoRouteFoundError(RoutingError):
    """Raised when no suitable agent node is available for routing."""

    pass


class InvalidStrategyError(RoutingError):
    """Raised when an unsupported or invalid routing strategy is specified."""

    pass


class RoutingEngine:
    """High-performance, content-aware, capability-based agent message routing engine.

    Evaluates active agent nodes using filtering constraints (capabilities, health status, metadata)
    and scoring strategies (least loaded, weighted latency, round-robin, content-aware capability matching).
    """

    def __init__(
        self,
        nodes: Optional[List[AgentNode]] = None,
        default_strategy: RoutingStrategy = RoutingStrategy.LEAST_LOADED,
    ) -> None:
        self._nodes: Dict[str, AgentNode] = {}
        self._default_strategy: RoutingStrategy = default_strategy
        self._lock: threading.RLock = threading.RLock()
        self._round_robin_counters: Dict[str, int] = {}

        if nodes:
            for node in nodes:
                self.register_node(node)

    def register_node(self, node: AgentNode) -> None:
        """Register or update an agent node in the routing table."""
        with self._lock:
            self._nodes[node.node_id] = node
            logger.debug(f"Registered agent node: {node.node_id} (Status: {node.status})")

    def deregister_node(self, node_id: str) -> None:
        """Remove an agent node from the routing table."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                logger.debug(f"Deregistered agent node: {node_id}")

    def get_node(self, node_id: str) -> Optional[AgentNode]:
        """Retrieve a registered agent node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> List[AgentNode]:
        """List all registered agent nodes."""
        with self._lock:
            return list(self._nodes.values())

    def update_node_metrics(
        self,
        node_id: str,
        status: Optional[AgentStatus] = None,
        current_load: Optional[float] = None,
        latency_ms: Optional[float] = None,
        active_tasks: Optional[int] = None,
    ) -> None:
        """Update dynamic operational health and performance metrics for a node."""
        with self._lock:
            node = self._nodes.get(node_id)
            if not node:
                raise KeyError(f"Agent node '{node_id}' is not registered.")

            if status is not None:
                node.status = status
            if current_load is not None:
                node.current_load = max(0.0, min(1.0, current_load))
            if latency_ms is not None:
                node.latency_ms = max(0.0, latency_ms)
            if active_tasks is not None:
                node.active_tasks = max(0, active_tasks)

            node.last_heartbeat = time.time()

    def route(
        self,
        message: Message,
        strategy: Optional[RoutingStrategy] = None,
    ) -> RouteDecision:
        """Select the optimal target AgentNode for a message based on routing rules and evaluation.

        Args:
            message: The agent message containing required capabilities and content payload.
            strategy: Optional explicit routing strategy override.

        Returns:
            RouteDecision containing chosen target agent node ID, evaluation metadata.
        """
        pass
