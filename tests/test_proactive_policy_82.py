"""Proactive policy must respect quiet hours, consent, time bounds and dedupe."""
from jervis.proactive_policy import (
    Candidate, DeliveryContext, DeliveryPolicy,
)


def _candidate(number: int, severity: str = "important") -> Candidate:
    return Candidate(f"{number:032x}", "host.health", "alex", severity, 100, 10000)


def _context(now=1000, minute=12 * 60, present=True, busy=False):
    return DeliveryContext(now, minute, present, busy)


def test_busy_absent_quiet_and_critical_override():
    policy = DeliveryPolicy()
    cand = _candidate(1)
    assert policy.decide(cand, _context(present=False)).action == "defer"
    assert policy.decide(cand, _context(busy=True)).action == "defer"
    assert policy.decide(cand, _context(minute=23 * 60)).reason == "Quiet hours"
    assert policy.decide(_candidate(2, "critical"), _context(minute=23 * 60)).action == "deliver"
    assert policy.decide(cand, _context(now=10000)).action == "discard"


def test_cooldown_rate_limit_and_no_duplicate_delivery():
    policy = DeliveryPolicy(cooldown_seconds=300, max_per_hour=2)
    assert policy.mark_delivered(_candidate(1), _context())
    assert not policy.mark_delivered(_candidate(1), _context())
    assert policy.decide(_candidate(2), _context()).reason == "Event cooldown"
    assert policy.mark_delivered(_candidate(2), _context(now=1400))
    assert policy.decide(_candidate(3), _context(now=1500)).reason == "Rate limit"
    assert policy.decide(_candidate(4), _context(now=5000)).action == "deliver"


def test_no_proactive_deliveries_without_explicit_valid_candidate():
    from pytest import raises
    policy = DeliveryPolicy()
    with raises(ValueError):
        policy.decide(Candidate("untrusted", "host.health", "alex",
                                "critical", 0, 1000), _context())
    with raises(ValueError):
        policy.decide(Candidate("a"*32, "shell;rm", "alex",
                                "critical", 0, 1000), _context())
