import logging
from typing import Dict, Any, Optional
from opentelemetry import trace
from opentelemetry.trace import Span, Tracer
try:
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    try:
        from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator
    except Exception:
        class TraceContextTextMapPropagator:
            def inject(self, carrier, context=None): pass
            def extract(self, carrier): return None

logger = logging.getLogger(__name__)

class TelemetryContextManager:
    """Manages trace context injection and extraction for inter-agent communication."""

    def __init__(self, tracer_name: str = "agent-mesh.telemetry") -> None:
        self.tracer: Tracer = trace.get_tracer(tracer_name)
        self.propagator: TraceContextTextMapPropagator = TraceContextTextMapPropagator()

    def inject_context(self, carrier: Dict[str, Any], span: Optional[Span] = None) -> Dict[str, Any]:
        """
        Injects the current or provided span context into the carrier dictionary
        for propagation across network boundaries.

        Args:
            carrier: The dictionary to inject headers into (e.g., HTTP headers).
            span: Optional span to use. If None, uses the current active span.

        Returns:
            The carrier dictionary containing the trace context headers.
        """
        try:
            context_to_inject = None
            if span:
                context_to_inject = trace.set_span_in_context(span)
            
            self.propagator.inject(carrier=carrier, context=context_to_inject)
            logger.debug("Successfully injected trace context into carrier.")
        except Exception as e:
            logger.error("Failed to inject trace context: %s", str(e), exc_info=True)
            
        return carrier

    def extract_context(self, carrier: Dict[str, Any]) -> trace.Context:
        """
        Extracts trace context from the carrier dictionary received from another agent or service.

        Args:
            carrier: The dictionary containing trace context headers.

        Returns:
            An OpenTelemetry Context object containing the extracted span context.
        """
        try:
            extracted_context = self.propagator.extract(carrier=carrier)
            logger.debug("Successfully extracted trace context from carrier.")
            return extracted_context
        except Exception as e:
            logger.error("Failed to extract trace context: %s", str(e), exc_info=True)
            return trace.get_current_span()

    def start_span_with_remote_context(
        self, 
        name: str, 
        carrier: Dict[str, Any], 
        kind: trace.SpanKind = trace.SpanKind.SERVER
    ) -> Span:
        """
        Extracts context from a carrier and starts a new child span linked to the remote parent.

        Args:
            name: The name of the new span.
            carrier: The carrier dictionary containing inbound trace context headers.
            kind: The OpenTelemetry SpanKind (default: SERVER).

        Returns:
            A new active OpenTelemetry Span.
        """
        parent_context = self.extract_context(carrier)
        span = self.tracer.start_span(name, context=parent_context, kind=kind)
        logger.debug("Started remote-linked span '%s' of kind %s", name, kind.name)
        return span


def get_current_context():
    return trace.get_current_span().get_span_context()

def set_current_context(ctx):
    pass


def get_current_trace_context():
    return {}

def inject_trace_context(carrier):
    return carrier

def extract_trace_context(carrier):
    return {}
