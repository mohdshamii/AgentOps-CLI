"""
test_smart_router.py
--------------------
Tests for the SmartRouter.
Run: pytest test_smart_router.py -v
"""

import os
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from smart_router import SmartRouter, Provider

# Ensure mock key exists for tests
os.environ["FAKE_KEY"] = "mock-key-value"


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_provider(name, healthy=True, configured=True,
                  latency=100.0, cost=0.002, errors=0, requests=0):
    p = Provider(
        name=name,
        ping_url=f"https://{name}.example.com/health",
        api_key_env="FAKE_KEY",
        cost_per_1k_tokens=cost,
        big_model=f"{name}-big",
        small_model=f"{name}-small",
    )
    p.healthy = healthy
    p.avg_latency_ms = latency
    p.error_count = errors
    p.request_count = requests
    if not configured:
        p.api_key_env = ""  # makes is_configured False for non-ollama
    return p


def make_router(providers=None, strategy="balanced"):
    r = SmartRouter(providers=providers, strategy=strategy)
    r._initialized = True
    return r


# ── Provider.score() ──────────────────────────────────────────────────────────

def test_score_unhealthy_is_inf():
    p = make_provider("openai", healthy=False)
    assert p.score() == float("inf")


def test_score_unconfigured_is_inf():
    p = make_provider("openai", configured=False)
    assert p.score() == float("inf")


def test_score_latency_strategy_prefers_faster():
    fast = make_provider("fast", latency=50.0, cost=0.01)
    slow = make_provider("slow", latency=500.0, cost=0.001)
    assert fast.score("latency") < slow.score("latency")


def test_score_cost_strategy_prefers_cheaper():
    cheap = make_provider("cheap", latency=500.0, cost=0.0001)
    expensive = make_provider("expensive", latency=50.0, cost=0.05)
    assert cheap.score("cost") < expensive.score("cost")


def test_score_balanced_strategy_uses_both():
    p = make_provider("test", latency=100.0, cost=0.002)
    score = p.score("balanced")
    assert 0 < score < float("inf")


def test_score_error_rate_penalty():
    reliable = make_provider("reliable", requests=100, errors=1)
    unreliable = make_provider("unreliable", requests=100, errors=50)
    assert reliable.score() < unreliable.score()


# ── SmartRouter.is_large_request() ───────────────────────────────────────────

def test_is_large_request_short():
    r = make_router()
    messages = [{"role": "user", "content": "What is 2+2?"}]
    assert r.is_large_request(messages) is False


def test_is_large_request_long():
    r = make_router()
    messages = [{"role": "user", "content": "x" * 2500}]
    assert r.is_large_request(messages) is True


# ── SmartRouter.select_provider() ─────────────────────────────────────────────

def test_select_provider_picks_best_score():
    fast = make_provider("fast", latency=50.0, cost=0.001)
    slow = make_provider("slow", latency=500.0, cost=0.001)
    r = make_router(providers=[slow, fast], strategy="latency")
    selected = r.select_provider()
    assert selected.name == "fast"


def test_select_provider_skips_unhealthy():
    p1 = make_provider("bad", healthy=False)
    p2 = make_provider("good", healthy=True)
    r = make_router(providers=[p1, p2])
    selected = r.select_provider()
    assert selected.name == "good"


def test_select_provider_returns_none_when_all_down():
    p1 = make_provider("a", healthy=False)
    p2 = make_provider("b", healthy=False)
    r = make_router(providers=[p1, p2])
    assert r.select_provider() is None


# ── SmartRouter.get_model_for_provider() ─────────────────────────────────────

def test_get_model_large_request():
    p = make_provider("openai")
    r = make_router()
    model = r.get_model_for_provider(p, "claude-sonnet")
    assert model == "openai-big"


def test_get_model_small_request():
    p = make_provider("openai")
    r = make_router()
    model = r.get_model_for_provider(p, "claude-haiku")
    assert model == "openai-small"


# ── SmartRouter.route() ───────────────────────────────────────────────────────

def test_route_returns_best_provider():
    async def _test():
        p1 = make_provider("expensive", cost=0.05, latency=50.0)
        p2 = make_provider("cheap", cost=0.0005, latency=200.0)
        r = make_router(providers=[p1, p2], strategy="cost")
        result = await r.route([{"role": "user", "content": "Hi"}], "claude-haiku")
        assert result["provider"] == "cheap"
    asyncio.run(_test())


def test_route_raises_when_no_providers():
    async def _test():
        p = make_provider("a", healthy=False)
        r = make_router(providers=[p])
        with pytest.raises(RuntimeError, match="no providers available"):
            await r.route([{"role": "user", "content": "Hi"}])
    asyncio.run(_test())


def test_route_excludes_providers():
    async def _test():
        p1 = make_provider("openai", latency=50.0)
        p2 = make_provider("gemini", latency=200.0)
        r = make_router(providers=[p1, p2], strategy="latency")
        result = await r.route(
            [{"role": "user", "content": "Hi"}],
            exclude_providers=["openai"]
        )
        assert result["provider"] == "gemini"
    asyncio.run(_test())


# ── SmartRouter.record_result() ──────────────────────────────────────────────

def test_record_result_updates_latency():
    async def _test():
        p = make_provider("openai", latency=200.0)
        r = make_router(providers=[p])
        await r.record_result("openai", success=True, duration_ms=100.0)
        assert p.avg_latency_ms < 200.0  # should decrease toward 100
    asyncio.run(_test())


def test_record_result_increments_requests():
    async def _test():
        p = make_provider("openai")
        r = make_router(providers=[p])
        await r.record_result("openai", success=True, duration_ms=100.0)
        assert p.request_count == 1
    asyncio.run(_test())


def test_record_result_increments_errors():
    async def _test():
        p = make_provider("openai")
        r = make_router(providers=[p])
        await r.record_result("openai", success=False, duration_ms=0)
        assert p.error_count == 1
    asyncio.run(_test())


# ── SmartRouter.status() ─────────────────────────────────────────────────────

def test_status_returns_all_providers():
    p1 = make_provider("openai")
    p2 = make_provider("gemini")
    r = make_router(providers=[p1, p2])
    status = r.status()
    assert len(status) == 2
    names = [s["provider"] for s in status]
    assert "openai" in names
    assert "gemini" in names


def test_status_contains_required_fields():
    p = make_provider("openai")
    r = make_router(providers=[p])
    status = r.status()[0]
    for field in ["provider", "healthy", "latency_ms",
                  "cost_per_1k", "requests", "errors", "score"]:
        assert field in status
