"""Tests for the Groq client's rate-limit resilience.

Regression guard for the 24/7 engine: on the free tier Groq returns 429s (often
with a large Retry-After). The client must (a) never sleep longer than its cap,
(b) give up on a persistently-limited model as a *skippable* error rather than
hanging the whole run or crashing it. A single uncapped sleep once turned a
throttled run into a 60-minute CI timeout.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from providers import groq_client as gc
from providers.groq_client import GroqClient, ModelUnavailable, RateLimited


class FakeResp:
    def __init__(self, status, *, body=None, headers=None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = str(self._body)

    def json(self):
        return self._body


def _client(monkeypatch, **kw):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    slept = []
    monkeypatch.setattr(gc.time, "sleep", lambda s: slept.append(s))
    c = GroqClient("https://example/api", mock=False, **kw)
    return c, slept


def test_rate_limited_raises_skippable_and_caps_sleep(monkeypatch):
    c, slept = _client(monkeypatch, max_backoff=5.0, rate_limit_budget=12.0,
                       max_retries=8)
    # Groq keeps returning 429 with an absurd Retry-After.
    monkeypatch.setattr(gc.requests, "post",
                        lambda *a, **k: FakeResp(429, headers={"retry-after": "9999"}))

    with pytest.raises(RateLimited):
        c.chat("some-model", [{"role": "user", "content": "hi"}])

    # RateLimited is skippable (tracks catch ModelUnavailable).
    assert issubclass(RateLimited, ModelUnavailable)
    # No single sleep exceeded the cap, and total waiting stayed near the budget
    # (never an uncapped multi-thousand-second hang).
    assert slept, "expected some backoff sleeps"
    assert max(slept) <= 5.0
    assert sum(slept) <= 12.0 + 5.0


def test_recovers_after_transient_429(monkeypatch):
    c, _ = _client(monkeypatch, max_backoff=5.0)
    seq = [FakeResp(429, headers={"retry-after": "1"}),
           FakeResp(200, body={"choices": [{"message": {"content": " 2 "}}],
                               "usage": {"prompt_tokens": 3, "completion_tokens": 1}})]
    monkeypatch.setattr(gc.requests, "post", lambda *a, **k: seq.pop(0))

    out = c.chat("some-model", [{"role": "user", "content": "1+1?"}])
    assert out.text == "2"
    assert c.calls == 1


def test_400_is_skippable(monkeypatch):
    c, _ = _client(monkeypatch)
    monkeypatch.setattr(gc.requests, "post",
                        lambda *a, **k: FakeResp(400, body={"error": "bad param"}))
    with pytest.raises(ModelUnavailable):
        c.chat("some-model", [{"role": "user", "content": "hi"}])


def test_dead_model_skipped_instantly_on_later_calls(monkeypatch):
    # Once a model is marked dead (rate-limited past budget), later calls to it
    # must skip WITHOUT hitting the network again — so we don't re-pay backoff
    # for the same down model on every track.
    c, slept = _client(monkeypatch, max_backoff=5.0, rate_limit_budget=8.0,
                       max_retries=8)
    calls = {"n": 0}

    def post(*a, **k):
        calls["n"] += 1
        return FakeResp(429, headers={"retry-after": "9999"})

    monkeypatch.setattr(gc.requests, "post", post)

    with pytest.raises(RateLimited):
        c.chat("dead-model", [{"role": "user", "content": "1"}])
    first_round = calls["n"]
    assert "dead-model" in c._dead

    # Second call: no new HTTP request, no new sleeps, instant skip.
    slept.clear()
    with pytest.raises(ModelUnavailable):
        c.chat("dead-model", [{"role": "user", "content": "2"}])
    assert calls["n"] == first_round      # network was not touched again
    assert slept == []                    # and we didn't wait
