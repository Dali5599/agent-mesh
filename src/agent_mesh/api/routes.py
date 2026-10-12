from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from agent_mesh.domain.models import AgentMessage, NodeRegistration, MeshHealthStatus
from agent_mesh.routing.registry import NodeRegistry
from agent_mesh.routing.engine import RoutingEngine
from agent_mesh.transport.client import MeshClient
from agent_mesh.resilience.exceptions import MeshError, CircuitOpenError, RateLimitExceededError, LoopDetectedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agent-mesh"])

_node_registry: Optional[NodeRegistry] = None
_routing_engine: Optional[RoutingEngine] = None
_mesh_client: Optional[MeshClient] = None

def init_router(registry: NodeRegistry, engine: RoutingEngine, client: MeshClient) -> None:
    global _node_registry, _routing_engine, _mesh_client
    _node_registry = registry
    _routing_engine = engine
    _mesh_client = client

def get_registry() -> NodeRegistry:
    if _node_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node registry not initialized."
        )
    return _node_registry

def get_engine() -> RoutingEngine:
    if _routing_engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing engine not initialized."
        )
    return _routing_engine

def get_client() -> MeshClient:
    if _mesh_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mesh client not initialized."
        )
    return _mesh_client

@router.post("/nodes/register", response_status=status.HTTP_201_CREATED, response_model=Dict[str, Any])
async def register_node(
    registration: NodeRegistration,
    registry: NodeRegistry = Depends(get_registry)
) -> Dict[str, Any]:
    try:
        registry.register(registration)
        logger.info(f"Node successfully registered via API: {registration.node_id} ({registration.agent_type})")
        return {
            "status": "success",
            "message": f"Node {registration.node_id} registered successfully.",
            "node_id": registration.node_id
        }
    except Exception as e:
        logger.error(f"Failed to register node {registration.node_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )

@router.delete("/nodes/{node_id}", response_status=status.HTTP_200_OK, response_model=Dict[str, Any])
async def unregister_node(
    node_id: str,
    registry: NodeRegistry = Depends(get_registry)
) -> Dict[str, Any]:
    try:
        registry.unregister(node_id)
        logger.info(f"Node successfully unregistered via API: {node_id}")
        return {
            "status": "success",
            "message": f"Node {node_id} unregistered successfully."
        }
    except Exception as e:
        logger.error(f"Failed to unregister node {node_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unregistration failed: {str(e)}"
        )

@router.post("/messages/dispatch", response_status=status.HTTP_200_OK, response_model=Dict[str, Any])
async def dispatch_message(
    message: AgentMessage,
    engine: RoutingEngine = Depends(get_engine),
    client: MeshClient = Depends(get_client)
) -> Dict[str, Any]:
    try:
        route_decision = engine.route(message)
        response = await client.send(route_decision.target_node, message)
        return {
            "status": "success",
            "trace_id": message.trace_id,
            "target_node": route_decision.target_node,
            "response": response
        }
    except LoopDetectedError as e:
        logger.warning(f"Infinite loop detected during message dispatch: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Infinite loop detected: {str(e)}"
        )
    except CircuitOpenError as e:
        logger.warning(f"Circuit breaker open during message dispatch: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Circuit open: {str(e)}"
        )
    except RateLimitExceededError as e:
        logger.warning(f"Rate limit exceeded during message dispatch: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {str(e)}"
        )
    except MeshError as e:
        logger.error(f"Mesh error during dispatch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mesh transport error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during message dispatch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal dispatch error: {str(e)}"
        )

@router.get("/health", response_status=status.HTTP_200_OK, response_model=MeshHealthStatus)
async def health_check(
    registry: NodeRegistry = Depends(get_registry)
) -> MeshHealthStatus:
    try:
        nodes = registry.get_all_nodes()
        active_nodes = [n for n in nodes if n.status == "ACTIVE"]
        status_val = "HEALTHY" if len(active_nodes) > 0 or len(nodes) == 0 else "DEGRADED"
        
        return MeshHealthStatus(
            status=status_val,
            total_nodes=len(nodes),
            active_nodes=len(active_nodes),
            message="Agent mesh control and data plane operating normally."
        )
    except Exception as e:
        logger.error(f"Health check failure: {e}", exc_info=True)
        return MeshHealthStatus(
            status="UNHEALTHY",
            total_nodes=0,
            active_nodes=0,
            message=f"Health check failed: {str(e)}"
        )

@router.get("/nodes", response_status=status.HTTP_200_OK, response_model=List[Dict[str, Any]])
async def list_nodes(
    registry: NodeRegistry = Depends(get_registry)
) -> List[Dict[str, Any]]:
    try:
        nodes = registry.get_all_nodes()
        return [
            {
                "node_id": node.node_id,
                "agent_type": node.agent_type,
                "endpoint": node.endpoint,
                "status": node.status,
                "capabilities": node.capabilities,
                "metadata": node.metadata
            }
            for node in nodes
        ]
    except Exception as e:
        logger.error(f"Failed to list nodes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve nodes: {str(e)}"
        )
