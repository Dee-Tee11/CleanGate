"""Evaluation statistics for the ClinGate release gate. Stdlib only."""
import math
from statistics import NormalDist


def _z(confidence):
    """Two-sided z value: 0.95 -> 1.96."""
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def wilson_ci(k, n, confidence=0.95):
    """Wilson score interval for a proportion: k events (errors or passes) in n cases."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError(f"need n > 0 and 0 <= k <= n, got k={k}, n={n}")
    z = _z(confidence)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def rule_of_three(n):
    """95% upper bound on the error rate after observing 0 errors in n cases.
    Inverse: cases needed to show error < target is ceil(3 / target)."""
    return 3 / n


def required_n(p, margin, confidence=0.95):
    """Cases needed for a CI of roughly +/- margin around an expected rate p."""
    z = _z(confidence)
    return math.ceil(z**2 * p * (1 - p) / margin**2)


def mcnemar(b, c):
    """Exact two-sided McNemar p-value for two versions run on the same cases.
    b = cases the old version passes and the new one fails; c = the reverse."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / 2**n)


if __name__ == "__main__":
    def approx(got, want):
        return all(math.isclose(g, w, abs_tol=1e-4) for g, w in zip(got, want))

    assert approx(wilson_ci(1, 50), (0.0035, 0.1050))
    assert approx(wilson_ci(12, 600), (0.0115, 0.0346))
    assert approx(wilson_ci(0, 600), (0.0, 0.0064))
    assert rule_of_three(600) == 0.005
    assert required_n(0.02, 0.01) == 753
    assert math.isclose(mcnemar(10, 2), 0.0386, abs_tol=1e-4)
    assert mcnemar(5, 5) == 1.0
    print("stats.py: all checks pass")
