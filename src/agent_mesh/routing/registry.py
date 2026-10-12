from typing import Dict, List, Optional, Set
import time
import logging

from agent_mesh.domain.models import AgentNode, AgentStatus, Capability

logger = logging.getLogger(__name__)

class ServiceRegistry:
    """
    Dynamic service registry tracking active agent nodes, their health status,
    and advertised capabilities within the high-performance distributed service mesh.
    """

    def __init__(self, node_ttl_seconds: float = 30.0) -> None:
        self._nodes: Dict[str, AgentNode] = {}
        self._last_heartbeat: Dict[str, float] = {}
        self._node_ttl_seconds = node_ttl_seconds

    def register(self, node: AgentNode) -> None:
        """
        Registers or updates an agent node in the mesh.
        """
        if not node.id:
            raise ValueError("AgentNode must have a valid non-empty id.")
        
        self._nodes[node.id] = node
        self._last_heartbeat[node.id] = time.time()
        logger.info(f"Registered agent node {node.id} with status {node.status}.")

    def deregister(self, node_id: str) -> Optional[AgentNode]:
        """
        Removes an agent node from the registry.
        """
        self._last_heartbeat.pop(node_id, None)
        node = self._nodes.pop(node_id, None)
        if node:
            logger.info(f"Deregistered agent node {node_id}.")
        return node

    def heartbeat(self, node_id: str) -> bool:
        """
        Updates the last seen timestamp for a node, marking it active.
        Returns True if the node exists and was updated, False otherwise.
        """
        if node_id in self._nodes:
            self._last_heartbeat[node_id] = time.time()
            if self._nodes[node_id].status == AgentStatus.OFFLINE:
                self._nodes[node_id].status = AgentStatus.ACTIVE
                logger.info(f"Node {node_id} status transitioned to ACTIVE via heartbeat.")
            return True
        return False

    def get_node(self, node_id: str) -> Optional[AgentNode]:
        """
        Retrieves a specific agent node by ID.
        """
        self._check_node_ttl()
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> List[AgentNode]:
        """
        Retrieves all currently registered agent nodes.
        """
        self._check_node_ttl()
        return list(self._nodes.values())

    def get_active_nodes(self) -> List[AgentNode]:
        """
        Retrieves all nodes that are currently active and healthy.
        """
        self._check_node_ttl()
        return [
            node for node in self._nodes.values()
            if node.status == AgentStatus.ACTIVE
        ]

    def find_nodes_by_capability(self, capability: str) -> List[AgentNode]:
        """
        Finds all active agent nodes offering a specific capability.
        """
        self._check_node_ttl()
        matching_nodes = []
        for node in self.get_active_nodes():
            for cap in node.capabilities:
                if cap.name == capability:
                    matching_nodes.append(node)
                    break
        return matching_nodes

    def find_nodes_by_tags(self, tags: Dict[str, str]) -> List[AgentNode]:
        """
        Finds all active agent nodes matching all provided key-value tags.
        """
        self._check_node_ttl()
        matching_nodes = []
        for node in self.get_active_nodes():
            match = True
            for k, v in tags.items():
                if node.metadata.get(k) != v:
                    match = False
                    break
            if match:
                matching_nodes.append(node)
        return matching_nodes

    def _check_node_ttl(self) -> None:
        """
        Internal method to mark nodes as offline if they haven't sent a heartbeat within TTL.
        """
        current_time = time.time()
        expired_nodes = []

        for node_id, last_seen in self._last_heartbeat.items():
            if current_time - last_seen > self._node_ttl_seconds:
                node = self._nodes.get(node_id)
                if node and node.status != AgentStatus.OFFLINE:
                    node.status = AgentStatus.OFFLINE
                    expired_nodes.append(node_id)

        for node_id in expired_nodes:
            logger.warning(f"Agent node {node_id} missed heartbeat and marked OFFLINE.")
