import logging
import threading
from typing import Any, Dict, Optional, Mapping

from opentelemetry import trace, baggage, propagators
try:
    from opentelemetry.baggage.propagation import W3CBaggagePropagator as BaggagePropagator
except ImportError:
    try:
        from opentelemetry.baggage.propagation import BaggagePropagator
    except Exception:
        class BaggagePropagator:
            pass
from opentelemetry.context import Context
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)
from opentelemetry.trace import Tracer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)


class TelemetryInitializationError(Exception):
    """Raised when OpenTelemetry initialization fails."""


class TracerManager:
    """Singleton manager for initializing and controlling the OpenTelemetry TracerProvider

    and associated exporters/processors within the Agent Mesh framework.
    """

    _instance: Optional["TracerManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._provider: Optional[TracerProvider] = None
        self._span_processor: Optional[SpanProcessor] = None
        self._exporter: Optional[SpanExporter] = None
        self._initialized: bool = False

    @classmethod
    def get_instance(cls) -> "TracerManager":
        """Get the global instance of the TracerManager."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_initialized(self) -> bool:
        """Check if the tracing system has been initialized."""
        return self._initialized

    def initialize(
        self,
        service_name: str = "agent-mesh",
        service_version: str = "0.1.0",
        node_id: Optional[str] = None,
        environment: str = "production",
        exporter_type: str = "otlp_grpc",
        otlp_endpoint: Optional[str] = None,
        otlp_headers: Optional[Dict[str, str]] = None,
        otlp_insecure: bool = True,
        sample_rate: float = 1.0,
        batch_export: bool = True,
        extra_resource_attributes: Optional[Dict[str, Any]] = None,
    ) -> TracerProvider:
        """Initialize the OpenTelemetry TracerProvider, configure context propagators,

        and set up span exporters.
        """
        with self._lock:
            if self._initialized:
                logger.warning("TracerManager is already initialized. Returning existing provider.")
                return self._provider  # type: ignore[return-value]

            try:
                # 1. Build Resource Attributes
                resource_attrs: Dict[str, Any] = {
                    SERVICE_NAME: service_name,
                    SERVICE_VERSION: service_version,
                    "deployment.environment": environment,
                    "agent_mesh.node_id": node_id or "unknown-node",
                }
                if extra_resource_attributes:
                    resource_attrs.update(extra_resource_attributes)

                resource = Resource.create(resource_attrs)

                # 2. Configure Sampler
                sampler = self._resolve_sampler(sample_rate)

                # 3. Create TracerProvider
                provider = TracerProvider(resource=resource, sampler=sampler)

                # 4. Resolve Exporter
                self._exporter = self._create_exporter(
                    exporter_type=exporter_type,
                    endpoint=otlp_endpoint,
                    headers=otlp_headers,
                    insecure=otlp_insecure,
                )

                # 5. Attach Processor
                if batch_export and not isinstance(self._exporter, InMemorySpanExporter):
                    self._span_processor = BatchSpanProcessor(self._exporter)
                else:
                    self._span_processor = SimpleSpanProcessor(self._exporter)

                provider.add_span_processor(self._span_processor)

                # 6. Set Global Trace Provider
                trace.set_tracer_provider(provider)
                self._provider = provider

                # 7. Configure Global Propagators (W3C Trace Context + Baggage)
                propagators.set_global_textmap(
                    CompositePropagator([
                        TraceContextTextMapPropagator(),
                        BaggagePropagator(),
                    ])
                )

                self._initialized = True
                logger.info(
                    "OpenTelemetry tracing initialized successfully (service: %s, exporter: %s, sample_rate: %.2f)",
                    service_name,
                    exporter_type,
                    sample_rate,
                )
                return self._provider

            except Exception as exc:
                logger.error("Failed to initialize OpenTelemetry tracing: %s", exc, exc_info=True)
                raise TelemetryInitializationError(f"Tracing setup failed: {exc}") from exc

    def _resolve_sampler(self, rate: float) -> Sampler:
        """Resolve OpenTelemetry sampler based on configured sampling rate."""
        if rate <= 0.0:
            return ParentBased(root=ALWAYS_OFF)
        if rate >= 1.0:
            return ParentBased(root=ALWAYS_ON)
        return ParentBased(root=TraceIdRatioBased(rate))

    def _create_exporter(
        self,
        exporter_type: str,
        endpoint: Optional[str],
        headers: Optional[Dict[str, str]],
        insecure: bool,
    ) -> SpanExporter:
        """Instantiate requested SpanExporter based on configuration string."""
        normalized_type = exporter_type.strip().lower()

        if normalized_type == "console":
            return ConsoleSpanExporter()

        if normalized_type == "in_memory":
            return InMemorySpanExporter()

        if normalized_type in ("otlp_grpc", "otlp"):
            return self._create_otlp_grpc_exporter(endpoint, headers, insecure)

        if normalized_type == "otlp_http":
            return self._create_otlp_http_exporter(endpoint, headers)

        if normalized_type == "none":
            return InMemorySpanExporter()

        logger.warning(
            "Unknown exporter type '%s'. Falling back to ConsoleSpanExporter.", exporter_type
        )
        return ConsoleSpanExporter()

    def _create_otlp_grpc_exporter(
        self, endpoint: Optional[str], headers: Optional[Dict[str, str]], insecure: bool
    ) -> SpanExporter:
        """Attempt to instantiate gRPC OTLP SpanExporter."""
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            target_endpoint = endpoint or "localhost:4317"
            return OTLPSpanExporter(
                endpoint=target_endpoint,
                headers=headers or {},
                insecure=insecure,
            )
        except ImportError as err:
            logger.error(
                "opentelemetry-exporter-otlp-proto-grpc is not installed. Falling back to Console exporter."
            )
            return ConsoleSpanExporter()
        except Exception as exc:
            logger.error("Failed to create OTLP gRPC exporter: %s. Fallback to Console.", exc)
            return ConsoleSpanExporter()

    def _create_otlp_http_exporter(
        self, endpoint: Optional[str], headers: Optional[Dict[str, str]]
    ) -> SpanExporter:
        """Attempt to instantiate HTTP OTLP SpanExporter."""
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            target_endpoint = endpoint or "http://localhost:4318/v1/traces"
            return OTLPSpanExporter(
                endpoint=target_endpoint,
                headers=headers or {},
            )
        except ImportError as err:
            logger.error(
                "opentelemetry-exporter-otlp-proto-http is not installed. Falling back to Console exporter."
            )
            return ConsoleSpanExporter()
        except Exception as exc:
            logger.error("Failed to create OTLP HTTP exporter: %s. Fallback to Console.", exc)
            return ConsoleSpanExporter()

    def shutdown(self) -> None:
        """Flush and shutdown active span processors and provider."""
        with self._lock:
            if not self._initialized or not self._provider:
                return

            try:
                self._provider.shutdown()
                logger.info("OpenTelemetry tracer provider shutdown complete.")
            except Exception as exc:
                logger.error("Error during OpenTelemetry provider shutdown: %s", exc)
            finally:
                self._provider = None
                self._span_processor = None
                self._exporter = None
                self._initialized = False


def setup_tracing(
    service_name: str = "agent-mesh",
    service_version: str = "0.1.0",
    node_id: Optional[str] = None,
    environment: str = "production",
    exporter_type: str = "otlp_grpc",
    otlp_endpoint: Optional[str] = None,
    otlp_headers: Optional[Dict[str, str]] = None,
    otlp_insecure: bool = True,
    sample_rate: float = 1.0,
    batch_export: bool = True,
    extra_resource_attributes: Optional[Dict[str, Any]] = None,
) -> TracerProvider:
    """Convenience function to initialize mesh distributed tracing."""
    manager = TracerManager.get_instance()
    return manager.initialize(
        service_name=service_name,
        service_version=service_version,
        node_id=node_id,
        environment=environment,
        exporter_type=exporter_type,
        otlp_endpoint=otlp_endpoint,
        otlp_headers=otlp_headers,
        otlp_insecure=otlp_insecure,
        sample_rate=sample_rate,
        batch_export=batch_export,
        extra_resource_attributes=extra_resource_attributes,
    )


def get_tracer(name: str = "agent_mesh", version: Optional[str] = None) -> Tracer:
    """Obtain a tracer instance from global tracer provider."""
    return trace.get_tracer(name, version)


def shutdown_tracing() -> None:
    """Shutdown globally configured tracer provider."""
    TracerManager.get_instance().shutdown()


def inject_trace_context(carrier: Dict[str, str], context: Optional[Context] = None) -> Dict[str, str]:
    """Inject W3C tracecontext and baggage headers into caller headers dict/carrier."""
    propagators.get_global_textmap().inject(carrier=carrier, context=context)
    return carrier


def extract_trace_context(carrier: Mapping[str, str]) -> Context:
    """Extract OpenTelemetry Context from headers dict/carrier."""
    # Ensure dictionary keys are evaluated consistently
    normalized_carrier = {str(k).lower(): str(v) for k, v in carrier.items()}
    return propagators.get_global_textmap().extract(carrier=normalized_carrier)


def set_mesh_baggage(key: str, value: str, context: Optional[Context] = None) -> Context:
    """Attach a key-value baggage entry to the current context for downstream propagation."""
    return baggage.set_baggage(key, value, context=context)


def get_mesh_baggage(key: str, context: Optional[Context] = None) -> Optional[Any]:
    """Retrieve baggage entry by key from current context."""
    return baggage.get_baggage(key, context=context)
