import asyncio
import logging
from typing import Callable, Awaitable, Dict, Any, Optional

from agent_mesh.domain.models import AgentMessage, MeshResponse, ErrorResponse
from agent_mesh.telemetry.tracer import get_tracer
from agent_mesh.telemetry.context import inject_trace_context, extract_trace_context

logger = logging.getLogger(__name__)


class TransportServer:
    """
    High-performance asynchronous message receiver server for node-to-node
    communication within the agent mesh. Handles incoming requests, extracts
    telemetry context, applies routing/handler callbacks, and returns mesh responses.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9090) -> None:
        self.host = host
        self.port = port
        self.handler: Optional[Callable[[AgentMessage], Awaitable[MeshResponse]]] = None
        self._server: Optional[asyncio.Server] = None
        self._is_running: bool = False
        self._tracer = get_tracer()

    def register_handler(self, handler: Callable[[AgentMessage], Awaitable[MeshResponse]]) -> None:
        """
        Registers the core message processing handler for incoming agent requests.
        """
        self.handler = handler
        logger.info("TransportServer handler successfully registered.")

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Handles an individual incoming TCP connection, reading length-prefixed
        serialized messages, processing them, and writing back responses.
        """
        peername = writer.get_extra_info("peername")
        logger.debug(f"Established connection from {peername}")

        try:
            while self._is_running:
                # Read 4-byte big-endian integer representing message length
                raw_length = await reader.read(4)
                if not raw_length:
                    break

                if len(raw_length) < 4:
                    logger.warning(f"Malformed frame header received from {peername}")
                    break

                message_length = int.from_bytes(raw_length, byteorder="big")
                
                # Read exact payload bytes
                payload = await reader.readexactly(message_length)
                
                response_payload = await self._process_payload(payload)

                # Write length-prefixed response
                resp_length = len(response_payload)
                writer.write(resp_length.to_bytes(4, byteorder="big") + response_payload)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.debug(f"Connection closed abruptly by peer {peername}")
        except Exception as e:
            logger.error(f"Error handling connection from {peername}: {e}", exc_info=True)
        finally:
            logger.debug(f"Closing connection for {peername}")
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_payload(self, payload: bytes) -> bytes:
        """
        Deserializes the incoming payload, restores distributed tracing context,
        invokes the registered handler, and serializes the resulting response.
        """
        try:
            message_data = AgentMessage.model_validate_json(payload.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to parse incoming AgentMessage JSON: {e}")
            err_resp = ErrorResponse(
                error="InvalidMessageFormat",
                message=f"Failed to parse payload: {str(e)}",
                details={"raw_bytes_len": len(payload)}
            )
            mesh_resp = MeshResponse(success=False, error=err_resp, payload=None)
            return mesh_resp.model_dump_json().encode("utf-8")

        # Extract distributed tracing context from message metadata if present
        span_context = extract_trace_context(message_data.metadata)
        span_name = f"TransportServer.receive:{message_data.action}"

        with self._tracer.start_span(span_name, context=span_context) as span:
            span.set_attribute("agent.sender", message_data.sender)
            span.set_attribute("agent.recipient", message_data.recipient)
            span.set_attribute("agent.action", message_data.action)
            span.set_attribute("agent.message_id", message_data.message_id)

            if not self.handler:
                logger.error("TransportServer received message but no handler is registered.")
                err_resp = ErrorResponse(
                    error="NoHandlerRegistered",
                    message="The transport server has no message handler registered.",
                    details={"action": message_data.action}
                )
                mesh_resp = MeshResponse(success=False, error=err_resp, payload=None)
                return mesh_resp.model_dump_json().encode("utf-8")

            try:
                # Inject current span context into metadata for outbound tracing propagation if needed
                inject_trace_context(message_data.metadata)
                
                mesh_response = await self.handler(message_data)
                return mesh_response.model_dump_json().encode("utf-8")
            except Exception as e:
                logger.error(f"Handler execution failed for action {message_data.action}: {e}", exc_info=True)
                span.record_exception(e)
                err_resp = ErrorResponse(
                    error="HandlerExecutionError",
                    message=str(e),
                    details={"action": message_data.action}
                )
                mesh_resp = MeshResponse(success=False, error=err_resp, payload=None)
                return mesh_resp.model_dump_json().encode("utf-8")

    async def start(self) -> None:
        """
        Starts the asynchronous TCP server on the configured host and port.
        """
        if self._is_running:
            logger.warning("TransportServer is already running.")
            return

        self._server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        self._is_running = True

        addr = self._server.sockets[0].getsockname()
        logger.info(f"TransportServer started successfully, listening on {addr}")

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """
        Gracefully stops the asynchronous TCP server.
        """
        if not self._is_running:
            return

        logger.info("Stopping TransportServer...")
        self._is_running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        logger.info("TransportServer stopped successfully.")
