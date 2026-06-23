"""Nightly eval orchestrator.

Runs all three tracks against the configured open-source models on Groq, writes
the dashboard's data files, and appends a compact summary to the run history.

Usage:
    python eval/run_eval.py            # live run (needs GROQ_API_KEY)
    python eval/run_eval.py --mock     # offline dry run, no key, synthetic data
    python eval/run_eval.py --tracks capability robustness

Outputs (read by the Next.js dashboard):
    public/data/latest.json     full snapshot of the most recent run
    public/data/history.jsonl   append-only one-line-per-run summary (time series)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

from config import (HISTORY_PATH, LATEST_PATH, git_repo, git_sha, load_config)
from dataio import append_jsonl, load_jsonl
from providers.groq_client import GroqClient
from tracks import capability, judge, robustness

TRACKS = {
    "capability": capability,
    "robustness": robustness,
    "judge": judge,
}


def _load_prev(mock: bool) -> dict:
    """Previous run's tracks, used as the drift baseline.

    Only reuse it when the previous run was in the same mode (mock vs live),
    so we never compare synthetic numbers against real ones.
    """
    if not LATEST_PATH.exists():
        return {}
    try:
        prev = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if prev.get("mock", False) != mock:
        return {}
    return prev.get("tracks", {})


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the LLM eval observatory suite.")
    ap.add_argument("--mock", action="store_true",
                    help="offline dry run with synthetic responses (no API key).")
    ap.add_argument("--tracks", nargs="*", default=list(TRACKS),
                    choices=list(TRACKS), help="subset of tracks to run.")
    args = ap.parse_args()

    cfg = load_config()
    client = GroqClient(cfg.endpoint, mock=args.mock or None,
                        timeout=cfg.request_timeout_sec)
    mock = client.mock
    prev_tracks = _load_prev(mock)

    # EVAL_DATE lets a backfill loop stamp synthetic mock runs on past dates so
    # the trend charts have history to draw. Live runs ignore it.
    date_override = os.environ.get("EVAL_DATE")
    if date_override and mock:
        now = datetime.fromisoformat(date_override).replace(tzinfo=timezone.utc)
    else:
        now = datetime.now(timezone.utc)
    print(f"== LLM Eval Observatory == {'MOCK' if mock else 'LIVE'} run "
          f"@ {now.isoformat()}")
    print(f"   models: {', '.join(m.id for m in cfg.models)}")

    started = time.monotonic()
    tracks_out: dict[str, dict] = {}
    for name in args.tracks:
        print(f"\n-- track: {name} --")
        t0 = time.monotonic()
        tracks_out[name] = TRACKS[name].run(client, cfg, prev_tracks.get(name))
        print(f"   done in {time.monotonic() - t0:.1f}s "
              f"(api calls so far: {client.calls})")

    duration = round(time.monotonic() - started, 1)

    snapshot = {
        "schema_version": 1,
        "status": "ok",
        "mock": mock,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "run_id": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": now.strftime("%Y-%m-%d"),
        "git_sha": git_sha(),
        "git_repo": git_repo(),
        "provider": cfg.provider,
        "models": [
            {"id": m.id, "label": m.label, "family": m.family,
             "tier": m.tier, "weights": m.weights}
            for m in cfg.models
        ],
        "duration_sec": duration,
        "totals": {
            "api_calls": client.calls,
            "prompt_tokens": client.prompt_tokens,
            "completion_tokens": client.completion_tokens,
        },
        "tracks": tracks_out,
    }

    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    append_jsonl(HISTORY_PATH, _history_record(snapshot))

    _print_summary(snapshot)
    print(f"\nWrote {LATEST_PATH}")
    print(f"Appended run to {HISTORY_PATH}")
    return 0


def _history_record(s: dict) -> dict:
    t = s["tracks"]
    rec = {
        "run_id": s["run_id"], "date": s["date"],
        "generated_at": s["generated_at"], "git_sha": s["git_sha"],
        "mock": s["mock"],
    }
    if "capability" in t:
        rec["capability"] = {
            m["model"]: {"accuracy": m["accuracy"], "ci95": m["ci95"]}
            for m in t["capability"]["per_model"]
        }
    if "robustness" in t:
        rec["robustness"] = {
            m["model"]: {"defense_rate": m["defense_rate"], "ci95": m["ci95"]}
            for m in t["robustness"]["per_model"]
        }
    if "judge" in t:
        rec["judge"] = {
            m["model"]: {
                "agreement": m["agreement_with_human"],
                "flip_rate": m["position_bias"]["flip_rate"],
                "verbosity_bias": m["verbosity_bias"]["bias"],
            }
            for m in t["judge"]["per_judge"]
        }
        rec["judge_fleiss_kappa"] = t["judge"]["inter_rater"]["fleiss_kappa"]
    return rec


def _print_summary(s: dict) -> None:
    print("\n================ SUMMARY ================")
    t = s["tracks"]
    if "capability" in t:
        print("Capability (accuracy, 95% CI):")
        for m in t["capability"]["per_model"]:
            lo, hi = m["ci95"][1], m["ci95"][2]
            flag = "  <DRIFT>" if m["drift"]["flag"] else ""
            print(f"  {m['label']:<16} {m['accuracy']:.0%}  "
                  f"[{lo:.0%}, {hi:.0%}]{flag}")
    if "robustness" in t:
        print("Robustness (defense rate, 95% CI):")
        for m in t["robustness"]["per_model"]:
            lo, hi = m["ci95"][1], m["ci95"][2]
            print(f"  {m['label']:<16} {m['defense_rate']:.0%}  [{lo:.0%}, {hi:.0%}]")
    if "judge" in t:
        print("Judge (agreement w/ human | order-flip | verbosity bias):")
        for m in t["judge"]["per_judge"]:
            print(f"  {m['label']:<16} {m['agreement_with_human']:.0%}  | "
                  f"flip {m['position_bias']['flip_rate']:.0%} | "
                  f"verb {m['verbosity_bias']['bias']:+.2f}")
        fk = t["judge"]["inter_rater"]["fleiss_kappa"]
        print(f"  inter-rater Fleiss' kappa: {fk}")
    print("========================================")


if __name__ == "__main__":
    raise SystemExit(main())
