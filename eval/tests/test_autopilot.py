"""Tests for the autopilot (KYC/AML triage) track.

Two things must hold for the track's numbers to mean anything:
  1. the decision-block parser reads a model's answer deterministically, even
     when the model wraps it in reasoning, markdown, or restates it; and
  2. the track wires up end-to-end on the mock client, producing every metric
     (decision accuracy, grounding, false-clear rate, ...) without a network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_config
from grading import parse_decision_block
from providers.groq_client import GroqClient
from tracks import autopilot


def test_parses_clean_block():
    p = parse_decision_block(
        "DECISION: ESCALATE\nTYPOLOGY: STRUCTURING\nRULE: P1\nEVIDENCE: E2,E4"
    )
    assert p == {"decision": "ESCALATE", "typology": "STRUCTURING",
                 "rule": "P1", "evidence": ["E2", "E4"]}


def test_ignores_reasoning_and_markdown_and_takes_last_block():
    text = (
        "<think>looks like structuring but let me hedge</think>\n"
        "First pass: **DECISION:** REVIEW\n"
        "On reflection:\n"
        "**DECISION:** ESCALATE\n- **TYPOLOGY:** Structuring\n"
        "RULE: P1 (structuring)\nEVIDENCE: E2, E4"
    )
    p = parse_decision_block(text)
    assert p["decision"] == "ESCALATE"          # last block wins, not the hedge
    assert p["typology"] == "STRUCTURING"
    assert p["rule"] == "P1"
    assert p["evidence"] == ["E2", "E4"]


def test_unparseable_is_empty_not_crash():
    p = parse_decision_block("I think this one is fine, no action needed.")
    assert p["decision"] == ""
    assert p["evidence"] == []


def test_evidence_deduped_and_uppercased():
    p = parse_decision_block("DECISION: CLEAR\nEVIDENCE: e1, E1, e3")
    assert p["evidence"] == ["E1", "E3"]


def test_track_runs_end_to_end_on_mock():
    cfg = load_config()
    client = GroqClient(cfg.endpoint, mock=True, timeout=cfg.request_timeout_sec)
    out = autopilot.run(client, cfg, None)

    assert out["n_cases"] > 0
    assert 0.0 < out["escalate_base_rate"] < 1.0
    assert len(out["per_model"]) == len(cfg.models)

    for m in out["per_model"]:
        assert 0.0 <= m["accuracy"] <= 1.0
        lo, hi = m["ci95"][1], m["ci95"][2]
        assert lo <= m["accuracy"] <= hi          # point inside its own CI
        # every calibration metric is a rate in [0,1] or None (no cases)
        for k in ("false_clear_rate", "over_escalation_rate",
                  "abstention_accuracy", "faithfulness",
                  "hallucinated_citation_rate", "typology_accuracy"):
            v = m[k]
            assert v is None or 0.0 <= v <= 1.0
        assert "drift" in m


def test_mock_produces_some_false_clears_and_hallucinations():
    # The mock's error model should exercise the trust metrics across the fleet,
    # so at least one model shows a non-zero false-clear or hallucination rate —
    # otherwise those dashboard columns would never be exercised offline.
    cfg = load_config()
    client = GroqClient(cfg.endpoint, mock=True, timeout=cfg.request_timeout_sec)
    out = autopilot.run(client, cfg, None)
    assert any((m["false_clear_rate"] or 0) > 0 for m in out["per_model"])
    assert any((m["hallucinated_citation_rate"] or 0) > 0 for m in out["per_model"])
