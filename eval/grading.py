"""Deterministic graders shared across tracks.

Auto-grading is what keeps this eval honest and reproducible: no LLM is in the
loop for capability/robustness scoring, so the numbers can't drift on grader
mood. The judge track is the one place an LLM grades — and we measure *that*
judge's reliability explicitly (see tracks/judge.py).
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def extract_final_answer(text: str) -> str:
    """Pull the model's final answer out of free-form text.

    Strategy, in order:
      1. text after a "Final answer:" / "Answer:" marker (we ask for this),
      2. the last \\boxed{...} if present,
      3. the whole last non-empty line.
    """
    if not text:
        return ""
    m = re.search(r"(?:final answer|answer)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip().splitlines()[0].strip()
    m = re.search(r"\\boxed\{([^}]*)\}", text)
    if m:
        return m.group(1).strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def normalize(s: str) -> str:
    s = s.strip().lower()
    s = s.strip(" .!?\"'`)(:")
    s = re.sub(r"\s+", " ", s)
    return s


def _as_number(s: str) -> float | None:
    m = _NUM_RE.search(s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def grade(prediction: str, gold: str, kind: str = "exact") -> bool:
    """Grade an extracted answer against gold.

    kind:
      "numeric" -> compare as numbers (tolerant of formatting/units),
      "mcq"     -> first A-E letter must match,
      "exact"   -> normalized string equality OR gold appears as a token,
      "contains"-> gold substring appears in normalized prediction.
    """
    pred = extract_final_answer(prediction)
    g = gold.strip()

    if kind == "numeric":
        pn, gn = _as_number(pred), _as_number(g)
        if pn is None or gn is None:
            return False
        return abs(pn - gn) <= 1e-6 * max(1.0, abs(gn))

    if kind == "mcq":
        pm = re.search(r"[A-Ea-e]", pred)
        return bool(pm) and pm.group(0).upper() == g.strip().upper()[:1]

    if kind == "contains":
        return normalize(g) in normalize(prediction)

    # exact (default)
    np_, ng = normalize(pred), normalize(g)
    if np_ == ng:
        return True
    # accept gold as a standalone token within the prediction line
    return bool(re.search(rf"\b{re.escape(ng)}\b", np_))
