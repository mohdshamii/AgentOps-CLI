"""
Fallback handling, circuit breaker, and bounded retries.
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Callable, Any, Awaitable

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}

    def record_success(self, provider_name: str) -> None:
        self.failures[provider_name] = 0
        if provider_name in self.last_failure_time:
            del self.last_failure_time[provider_name]

    def record_failure(self, provider_name: str) -> None:
        self.failures[provider_name] = self.failures.get(provider_name, 0) + 1
        self.last_failure_time[provider_name] = time.time()
        logger.warning(
            f"Provider '{provider_name}' failure recorded. Count: {self.failures[provider_name]}"
        )

    def is_available(self, provider_name: str) -> bool:
        fails = self.failures.get(provider_name, 0)
        if fails < self.failure_threshold:
            return True

        last_time = self.last_failure_time.get(provider_name, 0)
        if time.time() - last_time > self.cooldown_seconds:
            # Half-open: allow a trial request
            return True

        return False


async def execute_with_fallback(
    primary_fn: Callable[[], Awaitable[Any]],
    fallback_fns: List[Callable[[], Awaitable[Any]]],
    max_retries: int = 2,
    retry_delay: float = 1.0,
) -> Any:
    """Attempts execution on primary function, cascading through fallbacks on failure."""
    fns = [primary_fn] + fallback_fns
    last_err = None

    for fn in fns:
        for attempt in range(max_retries):
            try:
                return await fn()
            except Exception as e:
                last_err = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

    raise RuntimeError(f"All providers and fallback attempts failed: {last_err}") from last_err

