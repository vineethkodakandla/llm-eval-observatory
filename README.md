# LLM Eval Observatory

[![nightly-eval](https://github.com/vineethkodakandla/llm-eval-observatory/actions/workflows/nightly-eval.yml/badge.svg)](https://github.com/vineethkodakandla/llm-eval-observatory/actions/workflows/nightly-eval.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A **living dashboard that measures open-source LLMs every night** — capability
drift, prompt-injection robustness, and LLM-as-judge bias. A scheduled GitHub
Action runs a fixed eval suite against several open-weight models on Groq's free
tier, computes the statistics, and commits the results JSON back to this repo.
The Next.js site on Vercel reads that file — so **the dashboard is the artifact,
not a screenshot of one**.

Every number is one I computed and can defend cold: how the confidence interval
was bootstrapped, why a drift flag did or didn't fire, what a Fleiss' κ of 0.2
says about trusting a single LLM judge.

> **Architecture:** GitHub Actions is the *engine* (free scheduled compute);
> Vercel + Next.js is the *window* (reads the committed results and renders them
> with ISR). Actions cron → `results.json` → render.

```
                 ┌──────────────────────────┐
   nightly cron  │   GitHub Action (engine)  │   commits results
  ───────────────▶  eval/run_eval.py         ├───────────────────┐
                 │   • capability  • robust. │                   │
                 │   • judge       • stats   │                   ▼
                 └──────────────────────────┘        public/data/latest.json
                                                      public/data/history.jsonl
                                                                  │
                 ┌──────────────────────────┐   reads on build   │
   visitor  ◀────┤  Next.js on Vercel (window)◀──────────────────┘
                 │  /  dashboard + charts     │
                 └──────────────────────────┘
```

---

## The three tracks

### 1 · Capability & drift
Accuracy on a fixed 50-item auto-graded suite (math, logic, instruction-following,
factual recall). Each score gets a **bootstrapped 95% CI** (5,000 seeded
resamples). A **drift flag** fires only when a model's score moves more than 5
points *and* its CI no longer overlaps the previous run's — so noise stays quiet
and only real regressions light up. Almost nobody tracks model drift on a fixed
private task; it's a genuinely senior artifact.

### 2 · Prompt-injection & jailbreak robustness
Defense rate across a 30-prompt attack battery: direct instruction overrides,
social engineering, jailbreak role-play, system-prompt leaks, and **indirect
injection** hidden inside a document the model is asked to summarize. The design
is safe and fully auto-gradable: the model is given a canary passphrase to
protect (defense = never emits it) or a "don't obey the document" rule (defense =
never emits the injected payload). Grading is exact string matching and runs
*conservative* — a model that quotes the payload while refusing still counts as a
leak — so the number understates rather than inflates safety.

### 3 · LLM-as-judge bias & reliability
Judges are themselves unreliable, so this track **quantifies how**. Each model
judges 24 pairwise items against held-out human labels, in **both presentation
orders**, measuring:
- **agreement with the human** (with a bootstrapped CI),
- **position bias** — how often the verdict flips when the order is swapped (an
  unbiased judge never flips),
- **verbosity bias** — tendency to pick the longer answer (the set is
  length-balanced, so 0 is neutral),
- **inter-rater reliability** — Fleiss' κ and pairwise Cohen's κ across the judges.

---

## How the numbers are computed (`eval/stats.py`)

Everything is implemented from scratch — no scikit-learn / SciPy — so each figure
is explainable and re-derivable:

| Quantity | Method |
|---|---|
| Accuracy / defense / agreement CI | Percentile **bootstrap**, 5,000 resamples, seeded (reproducible) |
| Drift flag | Point move ≥ 5pp **and** 95% CIs disjoint |
| Two-judge agreement | **Cohen's κ** (chance-corrected) |
| Multi-judge agreement | **Fleiss' κ** |

`eval/tests/test_stats.py` checks these against known closed-form values
(Wilson interval, the canonical κ = 0.4 example, perfect / chance-level agreement).

---

## Quickstart

### Preview the dashboard (no API key, offline)
```bash
npm install
python eval/run_eval.py --mock      # writes synthetic data, clearly labelled
npm run dev                          # http://localhost:3000
```
Mock runs are loudly badged **Demo data** on the dashboard — they exercise the
full pipeline and charts but are not real model output.

### Run it for real (free)
1. Get a free Groq API key: <https://console.groq.com/keys>
2. Run the suite (~5 min, ~500 free-tier calls):
   ```bash
   pip install -r eval/requirements.txt
   GROQ_API_KEY=your_key python eval/run_eval.py
   npm run dev
   ```
   To start a clean real history, delete `public/data/history.jsonl` first.

### Deploy (the nightly loop)
1. Push this repo to GitHub (public → free unlimited Action minutes).
2. **Settings → Secrets and variables → Actions** → add `GROQ_API_KEY`.
3. Trigger the first run: **Actions → nightly-eval → Run workflow**. It commits
   real results and the badge above goes green.
4. Import the repo on [Vercel](https://vercel.com/new) (zero config — it's a
   standard Next.js app). Each nightly commit auto-deploys with fresh data.

---

## Configuration

- **Models** — `eval/models.yaml`. All defaults are open-weight and on Groq's
  free tier (Llama 3.3 70B, Llama 3.1 8B, GPT-OSS 20B, Qwen3 32B). Model IDs
  drift; refresh them from `https://api.groq.com/openai/v1/models`.
- **Eval items** — `eval/data/*.jsonl`. Add capability questions, attack prompts,
  or judge pairs; keep sets small (50–200) to stay free and fast.
- **Judge labels** — `eval/data/judge_labels.jsonl` ships with seed human labels.
  **Review and own these** — they are the ground truth Track 3 is measured
  against, so be ready to defend any one of them.

---

## Honesty notes (read these before quoting a number)

- All grading is **deterministic** except the judge track, whose unreliability is
  exactly what that track measures.
- CIs are **seeded** bootstraps — re-running on the same answers gives identical
  intervals.
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
  grading.py              deterministic answer graders
  providers/groq_client.py  OpenAI-compatible Groq client (+ offline mock)
  tracks/                 capability.py · robustness.py · judge.py
  data/                   capability.jsonl · attacks.jsonl · judge_labels.jsonl
  tests/test_stats.py     unit tests for the statistics
.github/workflows/nightly-eval.yml   the scheduled engine
app/                      Next.js (App Router) dashboard
public/data/              latest.json + history.jsonl  ← committed by the Action
```

---

Built by **Vineeth Kodakandla**. MIT licensed.
