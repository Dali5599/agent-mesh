import time
from typing import Dict, List, Optional
from agent_mesh.domain.models import AgentNode, AgentStatus

class ServiceRegistry:
    def __init__(self, node_ttl_seconds: float = 30.0):
        self._nodes: Dict[str, AgentNode] = {}
        self._last_heartbeat: Dict[str, float] = {}

    def register(self, node: AgentNode) -> None:
        node_id = getattr(node, "agent_id", getattr(node, "id", str(id(node))))
        self._nodes[node_id] = node
        self._last_heartbeat[node_id] = time.time()

    def unregister(self, node_id: str) -> Optional[AgentNode]:
        return self._nodes.pop(node_id, None)

    def get(self, node_id: str) -> Optional[AgentNode]:
        return self._nodes.get(node_id)

    def list_active(self) -> List[AgentNode]:
        return [n for n in self._nodes.values() if n.status == AgentStatus.ACTIVE]

    def get_all_nodes(self) -> List[AgentNode]:
        return list(self._nodes.values())

AgentRegistry = ServiceRegistry
NodeRegistry = ServiceRegistry
