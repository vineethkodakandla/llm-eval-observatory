"""Statistics for the eval observatory.

Everything here is implemented from scratch (no sklearn/scipy) so that every
number on the dashboard can be explained and re-derived by hand:

  * bootstrap_ci  -- nonparametric 95% CI for a proportion (resampling)
  * wilson_ci     -- closed-form CI used as a sanity check / fallback
  * drift         -- "did this score move meaningfully since last run?"
  * cohen_kappa   -- chance-corrected agreement between two raters
  * fleiss_kappa  -- chance-corrected agreement among >=2 raters

All randomness is seeded (config.BOOTSTRAP_SEED) so CIs are reproducible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from config import BOOTSTRAP_ITERS, BOOTSTRAP_SEED, DRIFT_ABS_THRESHOLD


@dataclass(frozen=True)
class Interval:
    point: float
    lo: float
    hi: float

    def as_list(self) -> list[float]:
        return [round(self.point, 4), round(self.lo, 4), round(self.hi, 4)]


def bootstrap_ci(outcomes: list[int | bool], iters: int = BOOTSTRAP_ITERS,
                 alpha: float = 0.05, seed: int = BOOTSTRAP_SEED) -> Interval:
    """Percentile bootstrap 95% CI for the mean of binary outcomes.

    `outcomes` is a list of 0/1 (or False/True). We resample with replacement
    `iters` times, take the mean each time, and read off the 2.5th / 97.5th
    percentiles. Reproducible given the seed.
    """
    arr = np.asarray(outcomes, dtype=float)
    n = len(arr)
    point = float(arr.mean()) if n else 0.0
    if n == 0:
        return Interval(0.0, 0.0, 0.0)
    if n == 1:
        # A single sample can't be bootstrapped into a meaningful interval;
        # fall back to the closed-form Wilson interval.
        return wilson_ci(int(arr.sum()), n)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(iters, n))
    means = arr[idx].mean(axis=1)
    lo = float(np.percentile(means, 100 * (alpha / 2)))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return Interval(point, lo, hi)


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Interval:
    """Wilson score interval for a binomial proportion (closed form)."""
    if n == 0:
        return Interval(0.0, 0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return Interval(p, max(0.0, center - half), min(1.0, center + half))


def drift(current: Interval, previous: Interval | None,
          abs_threshold: float = DRIFT_ABS_THRESHOLD) -> dict:
    """Flag a meaningful move between two runs.

    We require BOTH (a) the point estimate to move more than `abs_threshold`
    AND (b) the two 95% CIs to be disjoint. Requiring non-overlap keeps us from
    crying wolf on noise — a 4-point wobble inside overlapping intervals is not
    a regression, it's sampling variance.
    """
    if previous is None:
        return {"delta": None, "flag": False, "direction": "none",
                "reason": "no_previous_run"}
    delta = current.point - previous.point
    disjoint = current.hi < previous.lo or current.lo > previous.hi
    flag = abs(delta) >= abs_threshold and disjoint
    return {
        "delta": round(delta, 4),
        "flag": bool(flag),
        "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
        "ci_disjoint": bool(disjoint),
    }


def cohen_kappa(a: list, b: list) -> float | None:
    """Cohen's kappa: chance-corrected agreement between two raters.

    Inputs are equal-length sequences of categorical labels. Returns None if
    undefined (e.g. <2 items). kappa=1 perfect, 0 chance-level, <0 worse.
    """
    assert len(a) == len(b), "rater sequences must be equal length"
    n = len(a)
    if n < 2:
        return None
    cats = sorted(set(a) | set(b))
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    m = np.zeros((k, k))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    po = np.trace(m) / n
    row = m.sum(axis=1) / n
    col = m.sum(axis=0) / n
    pe = float((row * col).sum())
    if abs(1 - pe) < 1e-12:
        return 1.0 if po == 1.0 else 0.0
    return float((po - pe) / (1 - pe))


def fleiss_kappa(ratings: list[list]) -> float | None:
    """Fleiss' kappa for >=2 raters over N items with categorical labels.

    `ratings[i]` is the list of labels assigned to item i by each rater (every
    item must be rated by the same number of raters). Returns None if undefined.
    """
    if not ratings:
        return None
    n_raters = len(ratings[0])
    if n_raters < 2 or any(len(r) != n_raters for r in ratings):
        return None
    cats = sorted({lab for r in ratings for lab in r})
    cat_idx = {c: i for i, c in enumerate(cats)}
    N = len(ratings)
    counts = np.zeros((N, len(cats)))
    for i, r in enumerate(ratings):
        for lab in r:
            counts[i, cat_idx[lab]] += 1
    # Agreement per item.
    p_i = (np.square(counts).sum(axis=1) - n_raters) / (n_raters * (n_raters - 1))
    p_bar = float(p_i.mean())
    p_j = counts.sum(axis=0) / (N * n_raters)
    p_e = float(np.square(p_j).sum())
    if abs(1 - p_e) < 1e-12:
        return 1.0 if p_bar == 1.0 else 0.0
    return (p_bar - p_e) / (1 - p_e)
