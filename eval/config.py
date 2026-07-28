"""Configuration loading and shared paths for the eval engine."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Repo layout. The eval engine writes its outputs into the Next.js app's
# /public/data folder so the dashboard can read them directly (and so they're
# also viewable as raw JSON at /data/latest.json — part of the "it's really
# running" proof).
EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
DATA_IN = EVAL_DIR / "data"
DATA_OUT = REPO_ROOT / "public" / "data"

LATEST_PATH = DATA_OUT / "latest.json"
HISTORY_PATH = DATA_OUT / "history.jsonl"

# Bootstrap resampling is seeded so confidence intervals are reproducible from
# the same raw answers — a reviewer can re-run and get the identical CI.
BOOTSTRAP_SEED = 1729
BOOTSTRAP_ITERS = 5000

# A model's score is flagged as "drift" when it moves more than this from the
# previous run AND the two runs' 95% CIs do not overlap (see stats.drift).
DRIFT_ABS_THRESHOLD = 0.05

# The judge is asked for a single character ('1' or '2'), but reasoning models
# spend generated tokens *thinking* before they answer — an 8-token cap starves
# them and they return empty content. Give the verdict enough headroom for the
# reasoning to complete; non-reasoning models still stop after one token.
JUDGE_MAX_TOKENS = 512


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    family: str
    tier: str
    weights: str
    # Optional per-model request overrides merged into the chat payload
    # (e.g. {"reasoning_format": "parsed"} to keep a reasoning model's <think>
    # out of `content`). Empty for plain instruct models like Llama.
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    provider: str
    endpoint: str
    temperature: float
    max_tokens: int
    request_timeout_sec: int
    models: list[ModelSpec]


def load_config(path: Path | None = None) -> Config:
    path = path or (EVAL_DIR / "models.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    d = raw.get("defaults", {})
    models = [
        ModelSpec(
            id=m["id"],
            label=m.get("label", m["id"]),
            family=m.get("family", "unknown"),
            tier=m.get("tier", "production"),
            weights=m.get("weights", "open"),
            params=m.get("params") or {},
        )
        for m in raw["models"]
    ]
    return Config(
        provider=raw.get("provider", "groq"),
        endpoint=raw["endpoint"],
        temperature=float(d.get("temperature", 0.0)),
        max_tokens=int(d.get("max_tokens", 768)),
        request_timeout_sec=int(d.get("request_timeout_sec", 60)),
        models=models,
    )


def git_sha() -> str:
    return os.environ.get("GITHUB_SHA", "") or os.environ.get("GIT_SHA", "") or "local"


def git_repo() -> str:
    # e.g. "vineethkodakandla/llm-eval-observatory"
    return os.environ.get("GITHUB_REPOSITORY", "") or "local/llm-eval-observatory"
