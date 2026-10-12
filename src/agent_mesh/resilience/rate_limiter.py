import time
import asyncio
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: float
    retry_after: Optional[float] = None

class BaseRateLimiter(ABC):
    @abstractmethod
    async def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        pass

class TokenBucketRateLimiter(BaseRateLimiter):
    def __init__(self, capacity: int, refill_rate_per_second: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_second
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        async with self._lock:
            now = time.time()
            if key not in self._buckets:
                self._buckets[key] = (float(self.capacity), now)

            tokens, last_update = self._buckets[key]
            
            elapsed = now - last_update
            tokens = min(float(self.capacity), tokens + elapsed * self.refill_rate)
            
            if tokens >= cost:
                tokens -= cost
                self._buckets[key] = (tokens, now)
                remaining = int(tokens)
                return RateLimitResult(
                    allowed=True,
                    limit=self.capacity,
                    remaining=remaining,
                    reset_after_seconds=0.0
                )
            else:
                deficit = cost - tokens
                retry_after = deficit / self.refill_rate if self.refill_rate > 0 else float('inf')
                self._buckets[key] = (tokens, now)
                return RateLimitResult(
                    allowed=False,
                    limit=self.capacity,
                    remaining=int(tokens),
                    reset_after_seconds=retry_after,
                    retry_after=retry_after
                )

class SlidingWindowRateLimiter(BaseRateLimiter):
    def __init__(self, limit: int, window_size_seconds: float):
        self.limit = limit
        self.window_size = window_size_seconds
        self._windows: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        async with self._lock:
            now = time.time()
            if key not in self._windows:
                self._windows[key] = []

            timestamps = self._windows[key]
            cutoff = now - self.window_size
            
            while timestamps and timestamps[0] <= cutoff:
                timestamps.pop(0)

            current_usage = len(timestamps)
            
            if current_usage + cost <= self.limit:
                for _ in range(cost):
                    timestamps.append(now)
                remaining = self.limit - len(timestamps)
                return RateLimitResult(
                    allowed=True,
                    limit=self.limit,
                    remaining=remaining,
                    reset_after_seconds=self.window_size
                )
            else:
                oldest_relevant = timestamps[0] if timestamps else now
                retry_after = max(0.0, (oldest_relevant + self.window_size) - now)
                remaining = max(0, self.limit - current_usage)
                return RateLimitResult(
                    allowed=False,
                    limit=self.limit,
                    remaining=remaining,
                    reset_after_seconds=retry_after,
                    retry_after=retry_after
                )

class DistributedRateLimiter:
    def __init__(self, limiter: BaseRateLimiter):
        self.limiter = limiter

    async def check_rate_limit(self, key: str, cost: int = 1) -> RateLimitResult:
        return await self.limiter.acquire(key, cost=cost)
