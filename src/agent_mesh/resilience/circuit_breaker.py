import time
import threading
from enum import Enum
from typing import Callable, Any, Optional, Dict
from agent_mesh.resilience.exceptions import CircuitOpenError, CircuitBreakerOpenError

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 1
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_state_change = time.time()
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_state_change >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._last_state_change = time.time()
            return self._state

    def can_execute(self) -> bool:
        return self.state != CircuitState.OPEN

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self.state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_state_change = time.time()

    def record_success(self) -> None:
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            else:
                self._failure_count = 0

    def __enter__(self):
        if not self.can_execute():
            raise CircuitOpenError(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.record_failure()
        else:
            self.record_success()

class CircuitBreakerRegistry:
    def __init__(self):
        self._circuits = {}
    def get_circuit(self, name: str) -> CircuitBreaker:
        if name not in self._circuits:
            self._circuits[name] = CircuitBreaker(name=name)
        return self._circuits[name]

CircuitBreakerManager = CircuitBreakerRegistry
