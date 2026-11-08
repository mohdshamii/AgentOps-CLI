"""
Intelligent Auto-Router for AgentOpsCLI.
Pings configured providers, scores them by latency, cost, and reliability,
routes each request dynamically, and provides graceful failover.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import httpx

from agentops.router.scoring import ProviderScoreInfo, compute_provider_score
from agentops.router.policies import (
    classify_task,
    requires_large_model,
    is_local_provider,
)
from agentops.router.fallback import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class Provider:
    name: str                        # e.g. "openai", "gemini", "ollama", "anthropic"
    ping_url: str                    # URL used to check health
    api_key_env: str                 # env var name for API key
    cost_per_1k_tokens: float        # estimated cost USD per 1k tokens
    big_model: str                   # model for large requests
    small_model: str                 # model for small requests
    latency_ms: float = 9999.0       # updated by benchmark
    healthy: bool = True             # updated by health checks
    request_count: int = 0           # total requests routed here
    error_count: int = 0             # total errors from this provider
    avg_latency_ms: float = 9999.0   # rolling average from real requests

    @property
    def api_key(self) -> Optional[str]:
        if not self.api_key_env:
            return None
        return os.getenv(self.api_key_env)

    @property
    def is_configured(self) -> bool:
        """True if the provider has an API key set or does not require one."""
        if self.name == "ollama":
            return True
        if not self.api_key_env:
            return False
        return bool(self.api_key)

    @property
    def error_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count

    def score(self, strategy: str = "balanced") -> float:
        info = ProviderScoreInfo(
            name=self.name,
            healthy=self.healthy,
            is_configured=self.is_configured,
            avg_latency_ms=self.avg_latency_ms,
            cost_per_1k_tokens=self.cost_per_1k_tokens,
            request_count=self.request_count,
            error_count=self.error_count,
        )
        return compute_provider_score(info, strategy)


def build_default_providers() -> List[Provider]:
    big = os.getenv("BIG_MODEL", "gpt-4o")
    small = os.getenv("SMALL_MODEL", "gpt-4o-mini")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return [
        Provider(
            name="openai",
            ping_url="https://api.openai.com/v1/models",
            api_key_env="OPENAI_API_KEY",
            cost_per_1k_tokens=0.005,
            big_model=big,
            small_model=small,
        ),
        Provider(
            name="gemini",
            ping_url="https://generativelanguage.googleapis.com/v1beta/openai/models",
            api_key_env="GEMINI_API_KEY",
            cost_per_1k_tokens=0.001,
            big_model=os.getenv("GEMINI_BIG_MODEL", "gemini-2.0-flash"),
            small_model=os.getenv("GEMINI_SMALL_MODEL", "gemini-2.0-flash-lite"),
        ),
        Provider(
            name="anthropic",
            ping_url="https://api.anthropic.com/v1/messages",
            api_key_env="ANTHROPIC_API_KEY",
            cost_per_1k_tokens=0.006,
            big_model="claude-3-5-sonnet-20241022",
            small_model="claude-3-5-haiku-20241022",
        ),
        Provider(
            name="ollama",
            ping_url=f"{ollama_url}/api/tags",
            api_key_env="",
            cost_per_1k_tokens=0.0,
            big_model=os.getenv("OLLAMA_BIG_MODEL", "llama3.1:8b"),
            small_model=os.getenv("OLLAMA_SMALL_MODEL", "llama3.2:3b"),
        ),
    ]


class SmartRouter:
    def __init__(
        self,
        strategy: str = "balanced",
        providers: Optional[List[Provider]] = None,
        local_only: bool = False,
    ):
        self.strategy = os.getenv("ROUTER_STRATEGY", strategy)
        self.providers = providers if providers is not None else build_default_providers()
        self.local_only = local_only or (os.getenv("LOCAL_ONLY", "").lower() in ("1", "true", "yes"))
        self.circuit_breaker = CircuitBreaker()
        self._initialized = False

    async def initialize(self) -> None:
        """Pings all providers concurrently to evaluate health and initial latency."""
        tasks = [self.ping_provider(p) for p in self.providers]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._initialized = True

    async def ping_provider(self, p: Provider) -> None:
        if not p.is_configured:
            p.healthy = False
            return

        headers = {}
        if p.api_key:
            if p.name == "anthropic":
                headers["x-api-key"] = p.api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {p.api_key}"

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(p.ping_url, headers=headers)
                latency = (time.perf_counter() - start) * 1000.0
                p.healthy = resp.status_code in (200, 401, 403, 400) # reachable
                p.latency_ms = latency
                p.avg_latency_ms = latency
        except Exception:
            p.healthy = False
            p.latency_ms = 9999.0
            p.avg_latency_ms = 9999.0

    def select_provider(self, exclude: Optional[List[str]] = None) -> Optional[Provider]:
        """Selects the best provider based on current strategy score and constraints."""
        exclude = exclude or []
        candidates = []

        for p in self.providers:
            if p.name in exclude:
                continue
            if self.local_only and not is_local_provider(p.name, p.ping_url):
                continue
            if not p.healthy or not p.is_configured:
                continue
            if not self.circuit_breaker.is_available(p.name):
                continue
            candidates.append(p)

        if not candidates:
            # Fallback to configured providers if health checks failed due to offline environment
            for p in self.providers:
                if p.name in exclude:
                    continue
                if self.local_only and not is_local_provider(p.name, p.ping_url):
                    continue
                if p.is_configured and self.circuit_breaker.is_available(p.name):
                    candidates.append(p)

        if not candidates:
            return None

        candidates.sort(key=lambda x: x.score(self.strategy))
        return candidates[0]

    def is_large_request(self, messages: List[Dict[str, Any]]) -> bool:
        category = classify_task(messages)
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        estimated_tokens = total_chars // 4
        return requires_large_model(category, estimated_tokens)

    def get_model(self, provider: Provider, messages: List[Dict[str, Any]]) -> str:
        if self.is_large_request(messages):
            return provider.big_model
        return provider.small_model

    async def route(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        stream: bool = False,
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Finds the best provider and returns routing metadata."""
        if not self._initialized:
            await self.initialize()

        provider = self.select_provider(exclude=exclude)
        if not provider:
            raise RuntimeError(
                f"No available providers found. (local_only={self.local_only}, strategy={self.strategy})"
            )

        chosen_model = model or self.get_model(provider, messages)
        return {
            "provider": provider.name,
            "model": chosen_model,
            "stream": stream,
            "provider_obj": provider,
        }

    def record_result(self, provider_name: str, latency_ms: float, success: bool = True) -> None:
        """Updates rolling latency and error counts for learning over time."""
        for p in self.providers:
            if p.name == provider_name:
                p.request_count += 1
                if success:
                    # Rolling average: 80% previous + 20% latest
                    p.avg_latency_ms = (p.avg_latency_ms * 0.8) + (latency_ms * 0.2)
                    self.circuit_breaker.record_success(provider_name)
                else:
                    p.error_count += 1
                    self.circuit_breaker.record_failure(provider_name)
                break

    def status(self) -> List[Dict[str, Any]]:
        """Returns the health and telemetry status of all providers."""
        return [
            {
                "name": p.name,
                "healthy": p.healthy,
                "configured": p.is_configured,
                "avg_latency_ms": round(p.avg_latency_ms, 1),
                "cost_per_1k": p.cost_per_1k_tokens,
                "requests": p.request_count,
                "errors": p.error_count,
                "score": round(p.score(self.strategy), 3),
            }
            for p in self.providers
        ]
