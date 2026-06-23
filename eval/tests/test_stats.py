"""Unit tests for the statistics that back every dashboard number.

Run from the eval/ directory:  pytest -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import stats  # noqa: E402
from stats import (bootstrap_ci, cohen_kappa, drift, fleiss_kappa,  # noqa: E402
                   wilson_ci, Interval)


def test_bootstrap_ci_brackets_point_and_is_reproducible():
    data = [1] * 40 + [0] * 10  # 80% accuracy
    a = bootstrap_ci(data)
    b = bootstrap_ci(data)
    assert abs(a.point - 0.8) < 1e-9
    assert a.lo < a.point < a.hi
    assert (a.lo, a.hi) == (b.lo, b.hi)  # seeded -> identical
    assert 0.6 < a.lo and a.hi < 0.95    # plausible width for n=50


def test_bootstrap_ci_extremes():
    assert bootstrap_ci([]).point == 0.0
    perfect = bootstrap_ci([1] * 30)
    assert perfect.point == 1.0 and perfect.hi <= 1.0


def test_wilson_matches_known_value():
    # 8/10 successes: Wilson 95% CI is about [0.49, 0.94].
    ci = wilson_ci(8, 10)
    assert abs(ci.point - 0.8) < 1e-9
    assert 0.47 < ci.lo < 0.52
    assert 0.92 < ci.hi < 0.96


def test_drift_requires_disjoint_cis():
    # Overlapping intervals -> no drift even if points differ.
    cur = Interval(0.80, 0.70, 0.90)
    prev = Interval(0.86, 0.78, 0.94)
    assert drift(cur, prev)["flag"] is False
    # Disjoint intervals + big move -> drift flagged.
    cur2 = Interval(0.60, 0.50, 0.68)
    prev2 = Interval(0.85, 0.78, 0.92)
    d = drift(cur2, prev2)
    assert d["flag"] is True and d["direction"] == "down"
    # No previous run -> never flags.
    assert drift(cur, None)["flag"] is False


def test_cohen_kappa_perfect_and_chance():
    a = ["A", "B", "A", "B", "A"]
    assert abs(cohen_kappa(a, a) - 1.0) < 1e-9
    # Total disagreement on a balanced 2-class problem -> kappa < 0.
    b = ["B", "A", "B", "A", "B"]
    assert cohen_kappa(a, b) < 0


def test_cohen_kappa_known_value():
    # Canonical 2x2 example (Wikipedia): confusion (Y,Y)=20, (Y,N)=5,
    # (N,Y)=10, (N,N)=15 over 50 items -> po=0.7, pe=0.5, kappa=0.4.
    a = ["Y"] * 20 + ["Y"] * 5 + ["N"] * 10 + ["N"] * 15
    b = ["Y"] * 20 + ["N"] * 5 + ["Y"] * 10 + ["N"] * 15
    k = cohen_kappa(a, b)
    assert abs(k - 0.4) < 1e-9


def test_fleiss_kappa_perfect_agreement():
    # Every rater agrees on every item -> kappa = 1.
    ratings = [["A", "A", "A"], ["B", "B", "B"], ["A", "A", "A"]]
    assert abs(fleiss_kappa(ratings) - 1.0) < 1e-9


def test_fleiss_kappa_guards():
    assert fleiss_kappa([]) is None
    assert fleiss_kappa([["A"]]) is None  # <2 raters
