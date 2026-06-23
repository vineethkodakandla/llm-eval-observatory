"""Track 3 — LLM-as-judge bias & inter-rater reliability.

The point of this track: judges are themselves unreliable, and we quantify how.
For each pairwise item we ask every judge model which response is better, in
BOTH orders, and measure:

  * agreement_with_human  -- how often the judge matches the held-out human label
  * position_bias         -- flip_rate: how often the verdict changes when we
                             swap the order (an unbiased judge never flips),
                             plus position_1_rate (primacy/recency tendency)
  * verbosity_bias        -- tendency to pick the longer response (dataset is
                             length-balanced, so 0.5 is neutral)
  * inter_rater (Fleiss' kappa + pairwise Cohen's) over the judges' verdicts

Human labels live in eval/data/judge_labels.jsonl. They are seed labels you
should review and OWN — they are the ground truth this whole track is measured
against, so a reviewer may reasonably ask you to defend any one of them.
"""
from __future__ import annotations

from itertools import combinations

from config import DATA_IN, Config, ModelSpec
from dataio import load_jsonl
from providers.groq_client import GroqClient, ModelUnavailable
from stats import bootstrap_ci, cohen_kappa, fleiss_kappa

SYSTEM = (
    "You are an impartial evaluator. You will see a user question and two "
    "candidate responses labelled 1 and 2. Decide which response is better "
    "overall (accuracy first, then helpfulness). Reply with exactly one "
    "character: '1' or '2'. Output nothing else."
)


def _parse_verdict(text: str) -> str | None:
    for ch in text:
        if ch in "12":
            return ch
    return None


def _ask(client, cfg, model_id, prompt, r1, r2, good_pos, swapped) -> str | None:
    user = (
        f"Question:\n{prompt}\n\n"
        f"Response 1:\n{r1}\n\n"
        f"Response 2:\n{r2}\n\n"
        "Which response is better? Reply with only '1' or '2'."
    )
    comp = client.chat(
        model_id,
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        temperature=cfg.temperature, max_tokens=8,
        mock_hint={"type": "judge", "good_pos": good_pos, "swapped": swapped},
    )
    return _parse_verdict(comp.text)


def run(client: GroqClient, cfg: Config, prev: dict | None) -> dict:
    items = load_jsonl(DATA_IN / "judge_labels.jsonl")
    # Which of the two responses is longer (for verbosity bias); content-labelled.
    longer = {
        it["id"]: ("A" if len(it["response_a"]) >= len(it["response_b"]) else "B")
        for it in items
    }

    per_judge = []
    orig_choices: dict[str, list[str]] = {}  # judge_id -> [content choice per item]

    for spec in cfg.models:
        result = _run_judge(client, cfg, spec, items, longer)
        if result is None:
            continue
        res, choices = result
        per_judge.append(res)
        orig_choices[spec.id] = choices

    per_judge.sort(key=lambda r: r["agreement_with_human"], reverse=True)
    inter = _inter_rater(orig_choices, items)

    return {
        "n_items": len(items),
        "human_labels": len(items),
        "judges": [s.id for s in cfg.models if s.id in orig_choices],
        "per_judge": per_judge,
        "inter_rater": inter,
        "balance_note": "Dataset is balanced: the better answer is response A in "
                        "half the items and the longer answer in half, so 0.5 is "
                        "neutral for both position_1_rate and verbosity pick-longer.",
    }


def _run_judge(client, cfg, spec: ModelSpec, items, longer):
    per_item_agreement: list[float] = []
    flips = 0
    pick_pos1 = 0
    pick_longer = 0
    n_judgments = 0
    orig_content: list[str] = []
    try:
        for it in items:
            a, b, human = it["response_a"], it["response_b"], it["human"]

            # Original order: Response 1 = A, Response 2 = B.
            good_o = "1" if human == "A" else "2"
            v_o = _ask(client, cfg, spec.id, it["prompt"], a, b, good_o, False)
            content_o = _content(v_o, swapped=False)

            # Swapped order: Response 1 = B, Response 2 = A.
            good_s = "1" if human == "B" else "2"
            v_s = _ask(client, cfg, spec.id, it["prompt"], b, a, good_s, True)
            content_s = _content(v_s, swapped=True)

            # Agreement (averaged over both presentations; unparseable = miss).
            agree = 0.0
            for c in (content_o, content_s):
                if c is not None and c == human:
                    agree += 0.5
            per_item_agreement.append(agree)

            # Position bias: did the chosen content flip between orders?
            if content_o is not None and content_s is not None:
                if content_o != content_s:
                    flips += 1

            # Primacy/recency + verbosity, per individual judgment.
            for v, content in ((v_o, content_o), (v_s, content_s)):
                if v is None or content is None:
                    continue
                n_judgments += 1
                if v == "1":
                    pick_pos1 += 1
                if content == longer[it["id"]]:
                    pick_longer += 1

            orig_content.append(content_o if content_o is not None else "?")
    except ModelUnavailable as e:
        print(f"  ! judge: skipping {spec.id} ({e})")
        return None

    ci = bootstrap_ci(per_item_agreement)
    n = len(items)
    pos1_rate = round(pick_pos1 / n_judgments, 4) if n_judgments else None
    longer_rate = round(pick_longer / n_judgments, 4) if n_judgments else None
    res = {
        "model": spec.id,
        "label": spec.label,
        "family": spec.family,
        "n": n,
        "agreement_with_human": round(ci.point, 4),
        "agreement_ci95": ci.as_list(),
        "position_bias": {
            "flip_rate": round(flips / n, 4),
            "position_1_rate": pos1_rate,
            "flips": flips,
        },
        "verbosity_bias": {
            "pick_longer_rate": longer_rate,
            "bias": round(longer_rate - 0.5, 4) if longer_rate is not None else None,
        },
    }
    return res, orig_content


def _content(verdict: str | None, swapped: bool) -> str | None:
    """Map a '1'/'2' verdict to the chosen content label A/B given the order."""
    if verdict is None:
        return None
    if not swapped:
        return "A" if verdict == "1" else "B"
    return "B" if verdict == "1" else "A"


def _inter_rater(orig_choices: dict[str, list[str]], items) -> dict:
    judges = [j for j in orig_choices if all(c in ("A", "B") for c in orig_choices[j])]
    if len(judges) < 2:
        return {"fleiss_kappa": None, "pairwise": [],
                "note": "need >=2 judges with fully-parsed verdicts"}

    n = len(items)
    ratings = [[orig_choices[j][i] for j in judges] for i in range(n)]
    fk = fleiss_kappa(ratings)
    pairwise = []
    for j1, j2 in combinations(judges, 2):
        k = cohen_kappa(orig_choices[j1], orig_choices[j2])
        pairwise.append({"a": j1, "b": j2,
                         "cohen_kappa": round(k, 4) if k is not None else None})
    return {
        "fleiss_kappa": round(fk, 4) if fk is not None else None,
        "pairwise": pairwise,
    }
