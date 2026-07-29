# LLM Eval Observatory

[![nightly-eval](https://github.com/vineethkodakandla/llm-eval-observatory/actions/workflows/nightly-eval.yml/badge.svg)](https://github.com/vineethkodakandla/llm-eval-observatory/actions/workflows/nightly-eval.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Can you trust an AI to do the work, not just assist with it?**

The next wave of AI sells the *work*, not the tool — an **autopilot** that does an
already-outsourced, intelligence-heavy job end-to-end, not a **copilot** that
speeds up a human (Sequoia, *"Services as the New Software"*). But you can only
sell an *outcome* if the autopilot can be trusted to ship without a human behind
it — which turns the hard problem from "is the model smart?" into "does it
fabricate evidence, and does it wave through the one case that gets you fined?"

This is a **living dashboard that measures exactly that**. A scheduled GitHub
Action runs an eval suite against several open-weight models on Groq's free tier,
computes the statistics, and commits the results JSON back to this repo. The
Next.js site on Vercel reads that file — so **the dashboard is the artifact, not a
screenshot of one**. The flagship track runs a real autopilot end-to-end; three
supporting tracks measure whether its numbers can be believed.

Every number is one I computed and can defend cold: how the confidence interval
was bootstrapped, why a drift flag did or didn't fire, why a false-clear rate
matters more than raw accuracy, what a Fleiss' κ of 0.2 says about trusting a
single LLM judge.

> **Architecture:** GitHub Actions is the *engine* (free scheduled compute);
> Vercel + Next.js is the *window* (reads the committed results and renders them
> with ISR). Actions cron → `latest.json` → render.

```
                 ┌──────────────────────────────┐
   nightly cron  │   GitHub Action (engine)      │   commits results
  ───────────────▶  eval/run_eval.py             ├───────────────────┐
                 │   • autopilot (AML triage)    │                   │
                 │   • capability  • robustness  │                   ▼
                 │   • judge       • stats       │        public/data/latest.json
                 └──────────────────────────────┘        public/data/history.jsonl
                                                                      │
                 ┌──────────────────────────────┐   reads on build   │
   visitor  ◀────┤  Next.js on Vercel (window)   ◀────────────────────┘
                 │  /  dashboard + charts        │
                 └──────────────────────────────┘
```

---

## The flagship track

### 1 · Autopilot reliability — KYC/AML alert triage
An already-outsourced, intelligence-heavy job (KYC/AML is a ~$30–50B outsourced
services market) run **end-to-end**. For each flagged case the model is given a
customer profile, a transaction alert, numbered evidence lines, and a fixed
policy, and must decide **ESCALATE** (file a SAR / freeze), **CLEAR** (no
suspicious activity), or **REVIEW** (genuinely ambiguous — a human must resolve
it), *citing the evidence that justifies the call*. The model's answer is a fixed
four-line block, parsed **deterministically** (`grading.parse_decision_block`) —
no LLM grades another LLM here. What we measure is what decides whether you can
remove the human:

- **decision accuracy** — is the 3-way call right? (bootstrapped 95% CI + drift)
- **typology accuracy** — on escalations, did it name the right laundering pattern
  (structuring / sanctions / PEP / layering)? — the "extract the right field" signal
- **grounding faithfulness** & **fabricated-citation rate** — when it cites
  evidence, is that evidence real *and* relevant, or invented?
- **escalation calibration** — the safety numbers: **false clears** (gold =
  escalate but the model cleared it — the dangerous miss), **over-escalation**
  (cost/noise), and whether it correctly **abstains to REVIEW** on the ambiguous
  cases instead of guessing.

> A 90%-accurate autopilot that quietly clears real laundering is worse than
> useless. The safety columns, not the accuracy column, decide shippability —
> and that gap *is* the trust layer a services-as-software company has to build.

## The three supporting tracks — can you believe those numbers?

### 2 · Capability & drift *(is the model even competent?)*
Accuracy on a fixed 50-item auto-graded suite (math, logic, instruction-following,
factual recall). Each score gets a **bootstrapped 95% CI** (5,000 seeded
resamples). A **drift flag** fires only when a model's score moves more than 5
points *and* its CI no longer overlaps the previous run's — so noise stays quiet
and only real regressions light up.

### 3 · Prompt-injection & jailbreak robustness *(can it be manipulated?)*
Defense rate across a 30-prompt attack battery: direct instruction overrides,
social engineering, jailbreak role-play, system-prompt leaks, and **indirect
injection** hidden inside a document the model is asked to summarize. Fully
auto-gradable via canary/payload string matching, and deliberately
*conservative* — a model that quotes the payload while refusing still counts as a
leak — so the number understates rather than inflates safety. (An autopilot that
reads customer documents is an injection target by definition.)

### 4 · LLM-as-judge bias & reliability *(can you trust automated grading at all?)*
Judges are themselves unreliable, so this track **quantifies how**. Each model
judges 24 pairwise items against held-out human labels, in **both presentation
orders**, measuring agreement (with a bootstrapped CI), **position bias** (verdict
flips when the order is swapped), **verbosity bias** (tendency to pick the longer
answer; the set is length-balanced), and **inter-rater reliability** (Fleiss' κ
and pairwise Cohen's κ). It's the honest footnote under every "an LLM graded it"
claim — including autopilot pipelines that grade themselves.

---

## How the numbers are computed (`eval/stats.py`)

Everything is implemented from scratch — no scikit-learn / SciPy — so each figure
is explainable and re-derivable:

| Quantity | Method |
|---|---|
| Accuracy / defense / agreement / decision CI | Percentile **bootstrap**, 5,000 resamples, seeded (reproducible) |
| Drift flag | Point move ≥ 5pp **and** 95% CIs disjoint |
| False-clear / grounding / calibration rates | Deterministic counts over parsed decision blocks |
| Two-judge agreement | **Cohen's κ** (chance-corrected) |
| Multi-judge agreement | **Fleiss' κ** |

`eval/tests/` checks the statistics against known closed-form values (Wilson
interval, the canonical κ = 0.4 example), the reasoning-aware graders, the Groq
client's rate-limit handling, and the autopilot parser + track end-to-end.

---

## Quickstart

### Preview the dashboard (no API key, offline)
```bash
npm install
python eval/run_eval.py --mock      # writes synthetic data, clearly labelled
npm run dev                          # http://localhost:3000
```
Mock runs are loudly badged **Demo data** on the dashboard — they exercise the
full pipeline and charts (including realistic false-clears and fabricated
citations) but are not real model output.

### Run it for real (free)
1. Get a free Groq API key: <https://console.groq.com/keys>
2. Run the suite (~30 min, ~750 free-tier calls across all four tracks):
   ```bash
   pip install -r eval/requirements.txt
   GROQ_API_KEY=your_key python eval/run_eval.py
   npm run dev
   ```
   Run a single track with `--tracks autopilot`. To start a clean real history,
   delete `public/data/history.jsonl` first.

### Deploy (the scheduled loop)
1. Push this repo to GitHub (public → free unlimited Action minutes).
2. **Settings → Secrets and variables → Actions** → add `GROQ_API_KEY`.
3. Trigger the first run: **Actions → nightly-eval → Run workflow**. It commits
   real results and the badge above goes green.
4. Import the repo on [Vercel](https://vercel.com/new) (zero config — it's a
   standard Next.js app). Each committed run auto-deploys with fresh data.

---

## Configuration

- **Models** — `eval/models.yaml`. All defaults are open-weight and on Groq's
  free tier (Llama 3.3 70B, Llama 3.1 8B, GPT-OSS 20B, GPT-OSS 120B, Qwen3.6 27B).
  Model IDs drift; refresh them from `https://api.groq.com/openai/v1/models`.
- **Eval items** — `eval/data/*.jsonl`. Add capability questions, attack prompts,
  judge pairs, or KYC cases; keep sets small to stay free and fast.
- **KYC cases** — `eval/data/kyc_cases.jsonl` ships with 26 hand-authored,
  synthetic-but-realistic AML alerts (structuring, sanctions, PEP, layering,
  benign, and deliberately ambiguous), each with a gold decision, typology,
  governing rule, and the evidence IDs that justify it. Synthetic on purpose — no
  real customer data — and meant to be reviewed and owned.
- **Judge labels** — `eval/data/judge_labels.jsonl` ships with seed human labels.
  **Review and own these** — they are the ground truth Track 4 is measured against.

---

## Honesty notes (read these before quoting a number)

- **All grading is deterministic** except the judge track, whose unreliability is
  exactly what that track measures. The autopilot decision block is parsed by
  regex, not scored by another model.
- CIs are **seeded** bootstraps — re-running on the same answers gives identical
  intervals.
- The KYC dataset is **small (n = 26) and synthetic** — CIs are correspondingly
  wide and shown honestly; it's a rigorous *methodology* demo, not a compliance
  benchmark, and the numbers understate what a tuned production autopilot would do.
- The robustness grader is intentionally **conservative** (leak-biased).
- The committed demo data is synthetic and **labelled as such** in the UI until a
  real run replaces it. No fake-but-real-looking numbers, by design.

---

## Repo layout

```
eval/                     Python eval engine
  run_eval.py             orchestrator (writes public/data/*)
  models.yaml             models under test (open-weight, Groq free tier)
  stats.py                bootstrap CIs, drift, Cohen's & Fleiss' kappa
  grading.py              deterministic answer graders + decision-block parser
  providers/groq_client.py  OpenAI-compatible Groq client (+ offline mock)
  tracks/                 autopilot.py · capability.py · robustness.py · judge.py
  data/                   kyc_cases.jsonl · capability.jsonl · attacks.jsonl · judge_labels.jsonl
  tests/                  test_stats · test_grading · test_client · test_autopilot
.github/workflows/nightly-eval.yml   the scheduled engine
app/                      Next.js (App Router) dashboard
public/data/              latest.json + history.jsonl  ← committed by the Action
```

---

Built by **Vineeth Kodakandla**. MIT licensed.
