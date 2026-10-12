from typing import Optional, Dict, Any, List
from agent_mesh.domain.models import AgentNode, AgentStatus, RouteCriteria, RoutingStrategy
from agent_mesh.routing.registry import ServiceRegistry

class RoutingEngine:
    def __init__(self, nodes: Optional[List[AgentNode]] = None, default_strategy: Any = None, registry: Optional[ServiceRegistry] = None):
        self.registry = registry or ServiceRegistry()
        if nodes:
            for n in nodes:
                self.registry.register(n)

    def route(self, criteria: RouteCriteria) -> AgentNode:
        nodes = self.registry.list_active()
        req_cap = criteria.required_capability
        matched = []
        for n in nodes:
            caps = n.capabilities
            cap_matched = True
            if req_cap:
                if isinstance(caps, (set, list)):
                    cap_matched = any(str(c) == str(req_cap) for c in caps)
            if cap_matched:
                if criteria.metadata_filters:
                    if all(n.metadata.get(k) == v for k, v in criteria.metadata_filters.items()):
                        matched.append(n)
                else:
                    matched.append(n)
        if not matched:
            raise ValueError("No healthy agent found matching routing criteria")
        return matched[0]
