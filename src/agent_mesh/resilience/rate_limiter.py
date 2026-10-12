import time
import threading
from typing import Dict
from agent_mesh.resilience.exceptions import RateLimitExceededError

class TokenBucketRateLimiter:
    def __init__(self, capacity: float = 10.0, refill_rate: float = 1.0):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last_update = time.time()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

TokenBucket = TokenBucketRateLimiter

class DistributedRateLimiter:
    def __init__(self, default_capacity: float = 10.0, default_refill_rate: float = 1.0):
        self.default_capacity = float(default_capacity)
        self.default_refill_rate = float(default_refill_rate)
        self.buckets: Dict[str, TokenBucketRateLimiter] = {}
        self._lock = threading.Lock()

    def check_rate(self, key: str, tokens: float = 1.0) -> bool:
        with self._lock:
            if key not in self.buckets:
                self.buckets[key] = TokenBucketRateLimiter(self.default_capacity, self.default_refill_rate)
            return self.buckets[key].consume(tokens)

    def acquire(self, key: str, tokens: float = 1.0) -> None:
        if not self.check_rate(key, tokens):
            raise RateLimitExceededError(key)

RateLimiterManager = DistributedRateLimiter
RateLimiter = DistributedRateLimiter
GlobalRateLimiter = DistributedRateLimiter
