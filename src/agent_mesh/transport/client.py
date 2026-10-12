import asyncio
import logging
from typing import Any, Dict, Optional, Union
import httpx

from agent_mesh.config.schema import TransportConfig
from agent_mesh.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry
from agent_mesh.resilience.exceptions import CircuitBreakerOpenError, RateLimitExceededError
from agent_mesh.resilience.rate_limiter import GlobalRateLimiter
from agent_mesh.telemetry.tracer import get_tracer
from agent_mesh.telemetry.context import get_current_trace_context, inject_trace_context

logger = logging.getLogger(__name__)


class TransportClient:
    """
    High-performance asynchronous HTTP/gRPC client wrapper with integrated resilience,
    circuit breaking, rate limiting, and distributed tracing.
    """

    def __init__(
        self,
        config: Optional[TransportConfig] = None,
        circuit_breaker_registry: Optional[CircuitBreakerRegistry] = None,
        rate_limiter: Optional[GlobalRateLimiter] = None,
    ):
        self.config = config or TransportConfig()
        self.circuit_breaker_registry = circuit_breaker_registry or CircuitBreakerRegistry()
        self.rate_limiter = rate_limiter or GlobalRateLimiter()
        self.tracer = get_tracer()

        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "TransportClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def start(self) -> None:
        """Initializes the underlying asynchronous HTTP client."""
        async with self._lock:
            if self._client is None or self._client.is_closed:
                timeout = httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.read_timeout,
                    write=self.config.write_timeout,
                    pool=self.config.pool_timeout,
                )
                limits = httpx.Limits(
                    max_keepalive_connections=self.config.max_keepalive_connections,
                    max_connections=self.config.max_connections,
                )
                self._client = httpx.AsyncClient(
                    timeout=timeout,
                    limits=limits,
                    follow_redirects=True,
                )
                logger.debug("TransportClient HTTPX async client initialized.")

    async def close(self) -> None:
        """Closes the underlying asynchronous HTTP client."""
        async with self._lock:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()
                self._client = None
                logger.debug("TransportClient HTTPX async client closed.")

    def _get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        return self.circuit_breaker_registry.get_or_create(service_name)

    async def request(
        self,
        method: str,
        url: str,
        service_name: str = "default",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        data: Optional[Any] = None,
    ) -> httpx.Response:
        """
        Performs an HTTP request with full resilience pipeline:
        Rate Limiting -> Circuit Breaker -> Distributed Tracing Propagation -> HTTP Execution.
        """
        if self._client is None or self._client.is_closed:
            await self.start()

        # 1. Check Rate Limiter
        if not await self.rate_limiter.acquire(service_name):
            raise RateLimitExceededError(f"Rate limit exceeded for service: {service_name}")

        # 2. Get Circuit Breaker for target service
        circuit_breaker = self._get_circuit_breaker(service_name)
        if not circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(f"Circuit breaker is OPEN for service: {service_name}")

        # 3. Prepare headers and inject trace context
        req_headers = dict(headers) if headers else {}
        trace_context = get_current_trace_context()
        if trace_context:
            inject_trace_context(trace_context, req_headers)

        # 4. Execute request with telemetry tracing span
        span_name = f"HTTP {method.upper()} {service_name}"
        with self.tracer.start_span(span_name) as span:
            span.set_attribute("http.method", method.upper())
            span.set_attribute("http.url", url)
            span.set_attribute("service.name", service_name)

            try:
                assert self._client is not None
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=json_data,
                    data=data,
                )

                span.set_attribute("http.status_code", response.status_code)

                # Consider 5xx as failures for circuit breaker tracking
                if response.status_code >= 500:
                    circuit_breaker.record_failure()
                    logger.warning(
                        f"Service {service_name} returned server error status: {response.status_code}"
                    )
                else:
                    circuit_breaker.record_success()

                return response

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                circuit_breaker.record_failure()
                span.record_exception(exc)
                logger.error(f"Transport network/timeout error calling {service_name} at {url}: {exc}")
                raise
            except Exception as exc:
                circuit_breaker.record_failure()
                span.record_exception(exc)
                logger.error(f"Unexpected transport error calling {service_name} at {url}: {exc}")
                raise

    async def get(self, url: str, service_name: str = "default", **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, service_name=service_name, **kwargs)

    async def post(self, url: str, service_name: str = "default", **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, service_name=service_name, **kwargs)

    async def put(self, url: str, service_name: str = "default", **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, service_name=service_name, **kwargs)

    async def delete(self, url: str, service_name: str = "default", **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, service_name=service_name, **kwargs)

MeshClient = TransportClient
