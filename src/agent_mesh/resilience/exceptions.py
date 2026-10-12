from typing import Optional, Dict, Any


class MeshError(Exception):
    """Base exception for all Agent Mesh errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ResilienceError(MeshError):
    """Base exception for resilience-related failures (circuit breakers, rate limits)."""
    pass


class CircuitBreakerOpenError(ResilienceError):
    """Raised when a request is blocked because the circuit breaker is open."""

    def __init__(self, circuit_name: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        msg = message or f"Circuit breaker '{circuit_name}' is currently OPEN."
        merged_details = {"circuit_name": circuit_name}
        if details:
            merged_details.update(details)
        super().__init__(msg, merged_details)
        self.circuit_name = circuit_name


class RateLimitExceededError(ResilienceError):
    """Raised when a client or agent exceeds their designated rate limit."""

    def __init__(self, key: str, retry_after: Optional[float] = None, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        msg = message or f"Rate limit exceeded for key '{key}'."
        if retry_after is not None:
            msg += f" Retry after {retry_after} seconds."
        
        merged_details = {"key": key, "retry_after": retry_after}
        if details:
            merged_details.update(details)
            
        super().__init__(msg, merged_details)
        self.key = key
        self.retry_after = retry_after


class RoutingError(MeshError):
    """Base exception for failures during message routing or endpoint discovery."""
    pass


class RouteNotFoundError(RoutingError):
    """Raised when no matching route or healthy agent node can be found for a request."""

    def __init__(self, destination: str, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        msg = message or f"No available route found for destination '{destination}'."
        merged_details = {"destination": destination}
        if details:
            merged_details.update(details)
        super().__init__(msg, merged_details)
        self.destination = destination


class AgentMeshTimeoutError(MeshError):
    """Raised when an operation within the mesh times out."""

    def __init__(self, operation: str, timeout_seconds: float, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        msg = message or f"Operation '{operation}' timed out after {timeout_seconds} seconds."
        merged_details = {"operation": operation, "timeout_seconds": timeout_seconds}
        if details:
            merged_details.update(details)
        super().__init__(msg, merged_details)
        self.operation = operation
        self.timeout_seconds = timeout_seconds

CircuitOpenError = CircuitBreakerOpenError
LoopDetectedError = ResilienceError
InfiniteLoopDetectedError = ResilienceError
MaxHopsExceededError = ResilienceError
