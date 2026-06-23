"""Track 1 — Capability & drift.

Runs a fixed, auto-gradable suite against each model, scores accuracy with a
bootstrapped 95% CI, breaks it down by category, and flags drift versus the
previous run (CI-disjoint moves only — see stats.drift).
"""
from __future__ import annotations

from collections import defaultdict

from config import DATA_IN, Config, ModelSpec
from dataio import load_jsonl
from grading import grade
from providers.groq_client import GroqClient, ModelUnavailable
from stats import Interval, bootstrap_ci, drift

SYSTEM = (
    "You are a careful problem solver. Think briefly if needed, then end your "
    "reply with a line in exactly this format: 'Final answer: X' where X is the "
    "answer only, with no extra words or units unless asked."
)


def run(client: GroqClient, cfg: Config, prev: dict | None) -> dict:
    items = load_jsonl(DATA_IN / "capability.jsonl")
    prev_models = {m["model"]: m for m in (prev or {}).get("per_model", [])}

    per_model = []
    for spec in cfg.models:
        res = _run_model(client, cfg, spec, items)
        if res is None:
            continue
        prev_ci = _prev_interval(prev_models.get(spec.id))
        res["drift"] = drift(_interval(res), prev_ci)
        per_model.append(res)

    per_model.sort(key=lambda r: r["accuracy"], reverse=True)
    return {
        "n_items": len(items),
        "categories": sorted({it["category"] for it in items}),
        "per_model": per_model,
    }


def _run_model(client: GroqClient, cfg: Config, spec: ModelSpec,
               items: list[dict]) -> dict | None:
    outcomes: list[int] = []
    by_cat_correct: dict[str, int] = defaultdict(int)
    by_cat_total: dict[str, int] = defaultdict(int)
    try:
        for it in items:
            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": it["prompt"]},
            ]
            comp = client.chat(
                spec.id, messages,
                temperature=cfg.temperature, max_tokens=cfg.max_tokens,
                mock_hint={"type": "capability", "gold": it["answer"]},
            )
            ok = grade(comp.text, it["answer"], it.get("kind", "exact"))
            outcomes.append(1 if ok else 0)
            by_cat_total[it["category"]] += 1
            by_cat_correct[it["category"]] += 1 if ok else 0
    except ModelUnavailable as e:
        print(f"  ! capability: skipping {spec.id} ({e})")
        return None

    ci = bootstrap_ci(outcomes)
    by_category = {
        cat: round(by_cat_correct[cat] / by_cat_total[cat], 4)
        for cat in sorted(by_cat_total)
    }
    return {
        "model": spec.id,
        "label": spec.label,
        "family": spec.family,
        "n": len(outcomes),
        "correct": sum(outcomes),
        "accuracy": round(ci.point, 4),
        "ci95": ci.as_list(),
        "by_category": by_category,
    }


def _interval(res: dict) -> Interval:
    point, lo, hi = res["ci95"]
    return Interval(point, lo, hi)


def _prev_interval(prev: dict | None) -> Interval | None:
    if not prev:
        return None
    point, lo, hi = prev["ci95"]
    return Interval(point, lo, hi)
