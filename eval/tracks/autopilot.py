"""Track 4 — Autopilot reliability (KYC/AML alert triage).

The other three tracks ask "how good is the *model*?" This one asks the question
a services-as-software company actually has to answer before it can sell an
outcome instead of a tool: **can you trust an autopilot built on this model to
DO the work end-to-end?**

The task is a real already-outsourced, intelligence-heavy job — triaging an
anti-money-laundering (AML) alert. For each flagged case the model must, using
only the evidence and a fixed policy, decide:

    ESCALATE  – file a SAR / freeze (suspicious)
    CLEAR     – no suspicious activity
    REVIEW    – genuinely ambiguous; a human must resolve it

and cite the evidence lines that justify the call. We then measure the four
things that decide whether an autopilot is shippable, all graded deterministically
(no LLM-as-judge here — see grading.parse_decision_block):

  * decision accuracy  – is the call right? (bootstrapped 95% CI + drift)
  * typology accuracy  – on escalations, did it name the right money-laundering
                         pattern? (the "did it extract the right field" signal)
  * grounding faithfulness / hallucinated-citation rate – when it cites evidence,
    is that evidence real and relevant, or fabricated?
  * escalation calibration – the safety numbers: how often it CLEARED something
    that should have been escalated (false clears — the dangerous error), how
    often it over-escalated a benign case (cost/noise), and whether it correctly
    abstains to REVIEW on the ambiguous cases instead of guessing.
"""
from __future__ import annotations

from collections import defaultdict

from config import DATA_IN, Config, ModelSpec
from dataio import load_jsonl
from grading import parse_decision_block
from providers.groq_client import GroqClient, ModelUnavailable
from stats import Interval, bootstrap_ci, drift

# Closed policy rule-set. Included in every prompt so RULE citations are drawn
# from a fixed vocabulary (P1–P7) and are gradable.
POLICY = (
    "AML decision policy — apply these rules and cite the governing one by tag:\n"
    "P1 STRUCTURING — cash/transactions deliberately kept just under the $10,000 "
    "reporting threshold, or split across branches/days to dodge a CTR. → ESCALATE.\n"
    "P2 SANCTIONS — a party, bank, vessel, route, or end-user tied to an OFAC/SDN "
    "entity or a comprehensively sanctioned jurisdiction. → ESCALATE.\n"
    "P3 PEP — a politically exposed person (or close associate) with activity "
    "inconsistent with their profile or source of wealth. → ESCALATE.\n"
    "P4 LAYERING — rapid pass-through, funnel, or round-tripping that hides the "
    "source of funds with no economic purpose. → ESCALATE.\n"
    "P5 CTR-ONLY — a legitimate transaction that merely exceeds the $10,000 cash "
    "reporting threshold and reconciles to the customer's business. → CLEAR (file "
    "a CTR, no SAR).\n"
    "P6 CONSISTENT-WITH-PROFILE — documented activity consistent with the "
    "customer's known income/business. → CLEAR.\n"
    "P7 INSUFFICIENT-INFORMATION — genuinely ambiguous: a weak/partial match or "
    "missing source-of-funds evidence a human must resolve. → REVIEW."
)

SYSTEM = (
    "You are an AML analyst triaging a flagged transaction alert. Decide whether "
    "to ESCALATE (file a SAR / freeze), CLEAR (no suspicious activity), or send to "
    "REVIEW (a human must resolve genuine ambiguity). Use ONLY the evidence given "
    "and the numbered policy rules. Cite the exact evidence lines that justify your "
    "decision — never invent an evidence tag that is not listed.\n\n"
    "Think briefly if needed, then end your reply with EXACTLY these four lines and "
    "nothing after them:\n"
    "DECISION: <ESCALATE|CLEAR|REVIEW>\n"
    "TYPOLOGY: <STRUCTURING|SANCTIONS|PEP|LAYERING|NONE>\n"
    "RULE: <the single governing policy tag, e.g. P1, or NONE>\n"
    "EVIDENCE: <comma-separated evidence tags you relied on, e.g. E2,E4, or NONE>"
)


def _render(case: dict) -> str:
    c, a = case["customer"], case["alert"]
    lines = [
        f"CUSTOMER: {c['name']} — {c['kind']}; {c['profile']}; home country "
        f"{c['country']}; KYC risk {c['kyc_risk']}; account age {c['tenure']}.",
        f"ALERT [{a['id']}]: {a['kind']}, {a['amount']}, over {a['period']}. "
        f"{a['note']}.",
        "EVIDENCE:",
    ]
    lines += [f"{e['id']}: {e['text']}" for e in case["evidence"]]
    return "\n".join(lines)


def run(client: GroqClient, cfg: Config, prev: dict | None) -> dict:
    cases = load_jsonl(DATA_IN / "kyc_cases.jsonl")
    prev_models = {m["model"]: m for m in (prev or {}).get("per_model", [])}

    per_model = []
    for spec in cfg.models:
        res = _run_model(client, cfg, spec, cases)
        if res is None:
            continue
        res["drift"] = drift(_interval(res), _prev_interval(prev_models.get(spec.id)))
        per_model.append(res)

    per_model.sort(key=lambda r: r["accuracy"], reverse=True)
    n_esc = sum(1 for c in cases if c["gold"]["decision"] == "ESCALATE")
    return {
        "n_cases": len(cases),
        "categories": sorted({c["category"] for c in cases}),
        "escalate_base_rate": round(n_esc / len(cases), 4) if cases else 0.0,
        "per_model": per_model,
    }


def _run_model(client: GroqClient, cfg: Config, spec: ModelSpec,
               cases: list[dict]) -> dict | None:
    outcomes: list[int] = []                       # decision correct (0/1)
    cat_ok: dict[str, int] = defaultdict(int)
    cat_tot: dict[str, int] = defaultdict(int)

    n_esc = n_clear = n_review = 0
    false_clears = over_esc = abstain_ok = 0
    typo_ok = typo_tot = 0
    faith_ok = faith_tot = 0
    halluc = 0
    failures: list[dict] = []

    try:
        for case in cases:
            gold = case["gold"]
            gold_dec = gold["decision"]
            all_ev = {e["id"] for e in case["evidence"]}
            gold_ev = set(gold["evidence_ids"])

            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": POLICY + "\n\n" + _render(case)},
            ]
            comp = client.chat(
                spec.id, messages,
                temperature=cfg.temperature, max_tokens=cfg.max_tokens,
                extra_params=spec.params,
                mock_hint={
                    "type": "autopilot",
                    "gold_decision": gold_dec,
                    "gold_evidence": sorted(gold_ev),
                    "all_evidence": sorted(all_ev),
                    "gold_rule": gold["rule"],
                    "gold_typology": gold.get("typology", "NONE"),
                },
            )
            p = parse_decision_block(comp.text)
            dec, cited = p["decision"], set(p["evidence"])

            ok = int(dec == gold_dec)
            outcomes.append(ok)
            cat_tot[case["category"]] += 1
            cat_ok[case["category"]] += ok

            # grounding: fabricated citation (id not in the case) is a trust red flag
            if cited - all_ev:
                halluc += 1
            # faithfulness: when it makes a hard call WITH citations, are they
            # real (exist) AND relevant (overlap the case's decisive evidence)?
            if dec in ("ESCALATE", "CLEAR") and cited:
                faith_tot += 1
                if cited <= all_ev and (cited & gold_ev):
                    faith_ok += 1

            # escalation calibration + typology, bucketed by the gold decision
            if gold_dec == "ESCALATE":
                n_esc += 1
                if dec == "CLEAR":
                    false_clears += 1            # the dangerous miss
                typo_tot += 1
                typo_ok += int(p["typology"] == gold.get("typology"))
            elif gold_dec == "CLEAR":
                n_clear += 1
                if dec == "ESCALATE":
                    over_esc += 1
            else:  # REVIEW
                n_review += 1
                if dec == "REVIEW":
                    abstain_ok += 1

            if not ok and len(failures) < 6:
                failures.append({
                    "id": case["id"], "category": case["category"],
                    "gold": gold_dec, "got": dec or "unparsed",
                    "false_clear": bool(gold_dec == "ESCALATE" and dec == "CLEAR"),
                })
    except ModelUnavailable as e:
        print(f"  ! autopilot: skipping {spec.id} ({e})")
        return None

    # surface the dangerous failures first
    failures.sort(key=lambda f: not f["false_clear"])

    ci = bootstrap_ci(outcomes)
    by_category = {
        cat: round(cat_ok[cat] / cat_tot[cat], 4) for cat in sorted(cat_tot)
    }
    return {
        "model": spec.id,
        "label": spec.label,
        "family": spec.family,
        "n": len(outcomes),
        "accuracy": round(ci.point, 4),
        "ci95": ci.as_list(),
        "typology_accuracy": _rate(typo_ok, typo_tot),
        "faithfulness": _rate(faith_ok, faith_tot),
        "hallucinated_citation_rate": _rate(halluc, len(outcomes)),
        "false_clear_rate": _rate(false_clears, n_esc),
        "over_escalation_rate": _rate(over_esc, n_clear),
        "abstention_accuracy": _rate(abstain_ok, n_review),
        "by_category": by_category,
        "sample_failures": failures[:5],
    }


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _interval(res: dict) -> Interval:
    point, lo, hi = res["ci95"]
    return Interval(point, lo, hi)


def _prev_interval(prev: dict | None) -> Interval | None:
    if not prev:
        return None
    point, lo, hi = prev["ci95"]
    return Interval(point, lo, hi)
