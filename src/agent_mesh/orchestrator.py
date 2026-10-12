import asyncio
import logging
from typing import Dict, Any, Optional

from agent_mesh.config.schema import MeshConfig
from agent_mesh.domain.models import AgentRequest, AgentResponse
from agent_mesh.telemetry.tracer import get_tracer
from agent_mesh.telemetry.context import set_current_context, get_current_context
from agent_mesh.resilience.circuit_breaker import CircuitBreakerManager
from agent_mesh.resilience.rate_limiter import RateLimiterManager
from agent_mesh.resilience.loop_breaker import LoopBreaker
from agent_mesh.resilience.exceptions import MeshError, CircuitOpenError, RateLimitExceededError, InfiniteLoopDetectedError
from agent_mesh.routing.registry import ServiceRegistry
from agent_mesh.routing.engine import RoutingEngine
from agent_mesh.transport.server import MeshServer
from agent_mesh.transport.client import MeshClient

logger = logging.getLogger("agent_mesh.orchestrator")


class MeshOrchestrator:
    """Central orchestrator wiring transport, routing, resilience, and telemetry for the mesh node."""

    def __init__(self, config: MeshConfig) -> None:
        self.config = config
        self.tracer = get_tracer()

        self.service_registry = ServiceRegistry()
        self.routing_engine = RoutingEngine(self.service_registry, strategy=config.routing.strategy)

        self.circuit_breaker_manager = CircuitBreakerManager(
            failure_threshold=config.resilience.circuit_breaker_failure_threshold,
            recovery_time=config.resilience.circuit_breaker_recovery_time
        )
        self.rate_limiter_manager = RateLimiterManager(
            rate=float(config.resilience.rate_limiter_requests_per_second),
            burst=config.resilience.rate_limiter_burst
        )
        self.loop_breaker = LoopBreaker(
            max_depth=config.resilience.loop_breaker_max_depth
        )

        self.client = MeshClient(circuit_breaker_manager=self.circuit_breaker_manager)
        self.server = MeshServer(host=config.node.host, port=config.node.port, orchestrator=self)

        self._running = False

    async def start(self) -> None:
        """Starts the mesh orchestrator, server, and background routines."""
        if self._running:
            logger.warning("MeshOrchestrator is already running.")
            return

        self._running = True
        logger.info(f"Starting MeshOrchestrator for node {self.config.node.node_id} on {self.config.node.host}:{self.config.node.port}")
        
        await self.server.start()

    async def stop(self) -> None:
        """Stops the mesh orchestrator and its underlying transport server."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping MeshOrchestrator...")
        await self.server.stop()
        await self.client.close()
        logger.info("MeshOrchestrator stopped successfully.")

    async def execute_request(self, request: AgentRequest) -> AgentResponse:
        """Executes an agent request through the mesh applying telemetry, loops, rate limits, routing, and resilience."""
        span = self.tracer.start_span("mesh_orchestrator.execute_request", attributes={
            "agent.source": request.source_agent_id,
            "agent.target": request.target_agent_id,
            "request.id": request.request_id
        })

        try:
            # 1. Context Propagation
            ctx = get_current_context() or {}
            ctx.update({
                "source_agent_id": request.source_agent_id,
                "target_agent_id": request.target_agent_id,
                "request_id": request.request_id
            })
            set_current_context(ctx)

            # 2. Infinite Loop Detection
            path = ctx.get("path", [])
            if not isinstance(path, list):
                path = []
            
            self.loop_breaker.check_and_track(path, request.source_agent_id, request.target_agent_id)
            updated_path = path + [request.source_agent_id]
            ctx["path"] = updated_path

            # 3. Dynamic Rate Limiting
            if not self.rate_limiter_manager.acquire(request.source_agent_id):
                raise RateLimitExceededError(f"Rate limit exceeded for agent {request.source_agent_id}")

            # 4. Service Routing & Discovery
            target_instance = self.routing_engine.route(request.target_agent_id, request.payload)
            if not target_instance:
                raise MeshError(f"No active healthy instance found for target agent: {request.target_agent_id}")

            # 5. Remote or Local Execution
            if target_instance.is_local(self.config.node.node_id):
                response = await self._execute_local(request)
            else:
                response = await self.client.send(target_instance, request)

            span.set_attribute("response.status", response.status)
            return response

        except (CircuitOpenError, RateLimitExceededError, InfiniteLoopDetectedError, MeshError) as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error(f"Mesh execution error: {e}")
            raise
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.critical(f"Unexpected error during mesh execution: {e}", exc_info=True)
            raise MeshError(f"Internal orchestrator error: {str(e)}") from e
        finally:
            span.end()

    async def _execute_local(self, request: AgentRequest) -> AgentResponse:
        """Executes a request locally when the target agent resides on this node."""
        logger.debug(f"Executing local request for agent {request.target_agent_id}")
        
        # Simulate local execution delay / compute
        await asyncio.sleep(0.01)

        return AgentResponse(
            request_id=request.request_id,
            status="success",
            data={
                "message": f"Successfully processed by local agent {request.target_agent_id}",
                "input": request.payload
            },
            node_id=self.config.node.node_id
        )

    def get_health_status(self) -> Dict[str, Any]:
        """Returns comprehensive health and status metrics of the orchestrator and its components."""
        return {
            "node_id": self.config.node.node_id,
            "status": "running" if self._running else "stopped",
            "host": self.config.node.host,
            "port": self.config.node.port,
            "registry_services": len(self.service_registry.list_services()),
            "circuit_breakers": self.circuit_breaker_manager.get_all_states(),
            "rate_limiters": self.rate_limiter_manager.get_stats()
        }

AgentOrchestrator = MeshOrchestrator
