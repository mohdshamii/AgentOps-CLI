"""
Unit tests for router, scoring, policies, circuit breaker, and privacy enforcement.
"""

import asyncio
import os
import pytest
from agentops.router.scoring import ProviderScoreInfo, compute_provider_score
from agentops.router.policies import classify_task, TaskCategory, requires_large_model, is_local_provider
from agentops.router.fallback import CircuitBreaker
from agentops.router.router import Provider, SmartRouter


def test_scoring_prefers_lower_latency_on_latency_strategy():
    p1 = ProviderScoreInfo(name="fast", avg_latency_ms=50.0, cost_per_1k_tokens=0.01)
    p2 = ProviderScoreInfo(name="slow", avg_latency_ms=500.0, cost_per_1k_tokens=0.001)

    score1 = compute_provider_score(p1, strategy="latency")
    score2 = compute_provider_score(p2, strategy="latency")
    assert score1 < score2


def test_scoring_prefers_cheaper_on_cost_strategy():
    p1 = ProviderScoreInfo(name="cheap", avg_latency_ms=500.0, cost_per_1k_tokens=0.0001)
    p2 = ProviderScoreInfo(name="expensive", avg_latency_ms=50.0, cost_per_1k_tokens=0.05)

    score1 = compute_provider_score(p1, strategy="cost")
    score2 = compute_provider_score(p2, strategy="cost")
    assert score1 < score2


def test_privacy_local_only_enforcement():
    ollama = Provider(
        name="ollama",
        ping_url="http://localhost:11434/api/tags",
        api_key_env="",
        cost_per_1k_tokens=0.0,
        big_model="llama3.1:8b",
        small_model="llama3.2:3b",
        healthy=True,
    )
    openai = Provider(
        name="openai",
        ping_url="https://api.openai.com/v1/models",
        api_key_env="FAKE_KEY",
        cost_per_1k_tokens=0.005,
        big_model="gpt-4o",
        small_model="gpt-4o-mini",
        healthy=True,
    )
    os.environ["FAKE_KEY"] = "mock"

    router = SmartRouter(providers=[openai, ollama], local_only=True)
    router._initialized = True

    # Even if openai has lower score, local_only MUST select ollama
    selected = router.select_provider()
    assert selected.name == "ollama"


def test_circuit_breaker_tripping():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=100.0)
    assert cb.is_available("openai") is True

    cb.record_failure("openai")
    assert cb.is_available("openai") is True

    cb.record_failure("openai")
    # Tripped
    assert cb.is_available("openai") is False

    cb.record_success("openai")
    assert cb.is_available("openai") is True


def test_classify_task():
    assert classify_task([{"content": "Refactor this entire multi-file architecture"}]) == TaskCategory.COMPLEX_IMPLEMENTATION
    assert classify_task([{"content": "Fix the null pointer error and traceback"}]) == TaskCategory.BUG_FIXING
    assert classify_task([{"content": "Write pytest unit tests for this module"}]) == TaskCategory.TEST_GENERATION
    assert classify_task([{"content": "What is Python?"}]) == TaskCategory.SIMPLE_EXPLANATION

