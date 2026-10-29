"""HyperCore policy must preserve privacy and authorization boundaries."""
import pytest

from jervis.hypercore_policy import (
    CircuitBreaker, PolicyRouter, Provider, RequestPolicy,
)


def test_offline_fast_path_and_action_gate():
    router = PolicyRouter()
    assert router.choose("hello", RequestPolicy("public", "fast"), ()).route == "offline_fast"
    blocked = router.choose("delete files", RequestPolicy(
        "public", "fast", cloud_consent=True, requires_action=True,
    ), (Provider("cloud", "cloud", 100, 0.1),))
    assert not blocked.permitted
    assert blocked.route == "authorization"


def test_local_only_and_explicit_cloud_consent():
    router = PolicyRouter()
    cloud = Provider("external", "cloud", 10, 0.1, supports_deep=True)
    local = Provider("offline-llm", "offline_model", 300, 0, supports_deep=True)
    decision = router.choose("Explain my private notes",
                             RequestPolicy("local_only", "deep", cloud_consent=True),
                             (cloud, local))
    assert decision.route == "offline-llm"
    assert not router.choose("private", RequestPolicy("personal", "balanced"),
                             (cloud,)).permitted
    assert router.choose("public", RequestPolicy("public", "balanced",
                             cloud_consent=True), (cloud,)).route == "external"


def test_failure_circuit_and_recovery():
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=30)
    router = PolicyRouter(breaker)
    provider = Provider("model", "offline_model", 100, 0)
    breaker.record("model", False, now=100)
    breaker.record("model", False, now=101)
    assert not router.choose("nonoffline query", RequestPolicy(
        "public", "fast"), (provider,), now=120).permitted
    assert router.choose("nonoffline query", RequestPolicy(
        "public", "fast"), (provider,), now=132).route == "model"
    breaker.record("model", True, now=133)
    assert breaker.allowed("model", now=134)


def test_respects_latency_cost_complexity_and_failure():
    router = PolicyRouter()
    providers = (
        Provider("slow", "offline_model", 1000, 0),
        Provider("fast", "offline_model", 50, 0, supports_deep=False),
        Provider("deep", "offline_model", 400, 0, supports_deep=True),
    )
    assert router.choose("diagnose complicated code", RequestPolicy(
        "public", "deep", max_latency_ms=500), providers).route == "deep"
    assert not router.choose("research", RequestPolicy(
        "public", "deep", max_latency_ms=100), providers).permitted
    with pytest.raises(ValueError):
        router.choose("test", RequestPolicy("public", "fast", max_cost_units=float("nan")),
                      providers)
