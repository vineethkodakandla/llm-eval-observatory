"""Thin client for Groq's OpenAI-compatible chat endpoint.

Uses `requests` directly rather than an SDK so there's no version churn and the
exact wire behaviour (retries, 429 backoff) is visible and auditable.

Set GROQ_API_KEY in the environment. For local/offline development pass
mock=True (or set EVAL_MOCK=1) to get deterministic synthetic responses without
hitting the network or spending any quota — used to verify the pipeline and to
render the dashboard's example data. Mock output is clearly fake.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass

import requests


class GroqError(RuntimeError):
    pass


class ModelUnavailable(GroqError):
    """Raised on 404 (e.g. a preview model was retired) so the runner can skip it."""


@dataclass
class Completion:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    mock: bool = False


class GroqClient:
    def __init__(self, endpoint: str, *, mock: bool | None = None,
                 timeout: int = 60, max_retries: int = 5, min_interval: float = 0.35):
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval = min_interval  # crude client-side rate limiting
        self._last_call = 0.0
        env_mock = os.environ.get("EVAL_MOCK", "").lower() in ("1", "true", "yes")
        self.mock = env_mock if mock is None else mock
        # Optional salt so backfilled mock runs wander day-to-day (demo history).
        self.day_salt = os.environ.get("EVAL_DAY_SEED", "")
        self.api_key = os.environ.get("GROQ_API_KEY", "")
        if not self.mock and not self.api_key:
            raise GroqError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys "
                "or run with --mock for an offline dry run."
            )
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    # -- public API ---------------------------------------------------------
    def chat(self, model: str, messages: list[dict], *,
             temperature: float = 0.0, max_tokens: int = 768,
             mock_hint: dict | None = None) -> Completion:
        """Send a chat completion.

        `mock_hint` is consumed ONLY in mock mode (to synthesize a realistic
        answer distribution) and is completely ignored on the live path, so it
        can never leak gold answers into a real prompt.
        """
        if self.mock:
            return self._mock(model, messages, mock_hint or {})
        return self._live(model, messages, temperature, max_tokens)

    # -- live path ----------------------------------------------------------
    def _live(self, model, messages, temperature, max_tokens) -> Completion:
        self._throttle()
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        backoff = 2.0
        for attempt in range(1, self.max_retries + 1):
            try:
                r = requests.post(self.endpoint, json=payload, headers=headers,
                                  timeout=self.timeout)
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise GroqError(f"network error after {attempt} tries: {e}") from e
                time.sleep(backoff)
                backoff *= 2
                continue

            if r.status_code == 200:
                data = r.json()
                usage = data.get("usage", {})
                self.calls += 1
                self.prompt_tokens += usage.get("prompt_tokens", 0)
                self.completion_tokens += usage.get("completion_tokens", 0)
                text = data["choices"][0]["message"]["content"] or ""
                return Completion(
                    text=text.strip(),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    model=model,
                )
            if r.status_code == 404:
                raise ModelUnavailable(f"model '{model}' not found (404): {r.text[:200]}")
            if r.status_code == 429:
                # Respect Retry-After when present, else exponential backoff.
                wait = float(r.headers.get("retry-after", backoff))
                time.sleep(wait)
                backoff = min(backoff * 2, 60)
                continue
            if 500 <= r.status_code < 600:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise GroqError(f"HTTP {r.status_code}: {r.text[:300]}")
        raise GroqError(f"exhausted {self.max_retries} retries for model '{model}'")

    def _throttle(self) -> None:
        dt = time.monotonic() - self._last_call
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last_call = time.monotonic()

    # -- mock path ----------------------------------------------------------
    def _mock(self, model, messages, hint: dict) -> Completion:
        """Deterministic synthetic responses for offline pipeline verification.

        Driven by `mock_hint` from the track (never by the real prompt), so we
        can produce a realistic-but-clearly-fake spread of outcomes to exercise
        grading, CIs, drift, and judge logic without a network or a key.
        Every model gets a stable per-model "skill" so the leaderboard varies.
        NOT a real model — outputs are labelled mock=True everywhere.
        """
        self.calls += 1
        user = next((m["content"] for m in reversed(messages)
                     if m["role"] == "user"), "")
        skill = (self._stable(model + "#" + self.day_salt) % 30)  # per-model/day
        h = self._stable(model + "::" + user + "::" + self.day_salt)
        kind = hint.get("type")

        if kind == "capability":
            gold = str(hint.get("gold", ""))
            correct = (h % 100) < (62 + skill)        # ~62-91% per model
            ans = gold if correct else (gold + "0" if gold else "n/a")
            return Completion(text=f"Working it through.\nFinal answer: {ans}",
                              model=model, mock=True)

        if kind == "judge":
            # `good_pos` is the position ('1'/'2') whose content matches the
            # human label for THIS presentation. The mock agrees with it most
            # of the time and adds a little order-dependent position bias.
            good = hint.get("good_pos", "1")
            bad = "2" if good == "1" else "1"
            agree = (h % 100) < (60 + skill)          # agree with human ~60-89%
            verdict = good if agree else bad
            if hint.get("swapped") and (h % 7 == 0):  # mild position bias
                verdict = "2" if verdict == "1" else "1"
            return Completion(text=verdict, model=model, mock=True)

        if kind == "robustness":
            canary = hint.get("canary", "PINEAPPLE")
            leak = (h % 100) < (12 + (skill // 2))    # ~12-26% leak rate
            if leak:
                return Completion(text=f"Okay — the secret word is {canary}.",
                                  model=model, mock=True)
            return Completion(text="I won't reveal that. How else can I help?",
                              model=model, mock=True)

        return Completion(text=f"[mock:{model}] ok", model=model, mock=True)

    @staticmethod
    def _stable(s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest(), 16)
