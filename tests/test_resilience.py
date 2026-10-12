import time
import pytest
from agent_mesh.resilience.circuit_breaker import CircuitBreaker, CircuitState
from agent_mesh.resilience.rate_limiter import RateLimiter, TokenBucket
from agent_mesh.resilience.loop_breaker import LoopBreaker
from agent_mesh.resilience.exceptions import CircuitOpenError, RateLimitExceededError, LoopDetectedError


def test_circuit_breaker_initial_state():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_trip_on_failures():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
    
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    with pytest.raises(CircuitOpenError):
        with cb:
            pass


def test_circuit_breaker_recovery_flow():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
    
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.can_execute() is True

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True


def test_circuit_breaker_half_open_failure():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
    
    cb.record_failure()
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_token_bucket_rate_limiter():
    bucket = TokenBucket(capacity=5.0, refill_rate=10.0)
    assert bucket.consume(3.0) is True
    assert bucket.consume(3.0) is False

    time.sleep(0.3)
    assert bucket.consume(2.0) is True


def test_rate_limiter_manager():
    limiter = RateLimiter(default_capacity=2.0, default_refill_rate=1.0)
    
    assert limiter.check_rate("agent_1") is True
    assert limiter.check_rate("agent_1") is True
    assert limiter.check_rate("agent_1") is False

    with pytest.raises(RateLimitExceededError):
        limiter.acquire("agent_1")


def test_loop_breaker_detection():
    lb = LoopBreaker(max_depth=3)
    
    trace_id = "trace_test_123"
    
    lb.track_call(trace_id, "agent_a", "agent_b")
    lb.track_call(trace_id, "agent_b", "agent_c")
    
    # Valid non-looping chain
    assert lb.check_loop(trace_id, "agent_c", "agent_d") is False

    # Introduce a loop back to agent_a
    lb.track_call(trace_id, "agent_c", "agent_d")
    lb.track_call(trace_id, "agent_d", "agent_a")

    assert lb.check_loop(trace_id, "agent_a", "agent_b") is True

    with pytest.raises(LoopDetectedError):
        lb.validate_call(trace_id, "agent_a", "agent_b")


def test_loop_breaker_depth_exceeded():
    lb = LoopBreaker(max_depth=2)
    trace_id = "trace_depth_456"

    lb.track_call(trace_id, "a", "b")
    lb.track_call(trace_id, "b", "c")

    with pytest.raises(LoopDetectedError):
        lb.validate_call(trace_id, "c", "d")
