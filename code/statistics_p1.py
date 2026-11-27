"""All the statistics of the study, in short functions with a published formula each."""
import numpy as np
from scipy.stats import beta, binomtest, norm

MARGIN = 0.12  # upper exact limit of 4/82, the largest value compatible with table 3 of Gabelic 2014


def exact_interval(x, n, level=0.95):
    """Clopper-Pearson. With cohorts of different true proportion it stays conservative (Hoeffding 1956)."""
    if not 0 <= x <= n or n == 0:
        raise ValueError("need 0 <= x <= n and n > 0")
    a = (1 - level) / 2
    low = 0.0 if x == 0 else float(beta.ppf(a, x, n - x + 1))
    high = 1.0 if x == n else float(beta.ppf(1 - a, x + 1, n - x))
    return low, high


def reading(x, n, margin=MARGIN):
    """The three readings fixed before the data."""
    low, high = exact_interval(x, n)
    if low > margin:
        return "above the margin"
    if high < margin:
        return "below the margin"
    return "inconclusive"


def failure_bounds(x, n, failed):
    """Failed cases are never dropped: all negative, then all positive."""
    total = n + failed
    return (x / total, *exact_interval(x, total)), ((x + failed) / total, *exact_interval(x + failed, total))


def paired_difference(a, b, level=0.95):
    """Difference of two paired proportions (a minus b): Bonett and Price 2012, and exact McNemar P."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    if a.shape != b.shape or a.size == 0:
        raise ValueError("paired, non-empty arrays are needed")
    n, only_a, only_b = a.size, int((a & ~b).sum()), int((~a & b).sum())
    p1, p2 = (only_a + 1) / (n + 2), (only_b + 1) / (n + 2)
    half = norm.ppf(0.5 + level / 2) * np.sqrt((p1 + p2 - (p1 - p2) ** 2) / (n + 2))
    d = p1 - p2
    p = 1.0 if only_a + only_b == 0 else binomtest(only_a, only_a + only_b, 0.5).pvalue
    return {"difference": (only_a - only_b) / n, "low": max(-1.0, d - half), "high": min(1.0, d + half),
            "only_a": only_a, "only_b": only_b, "p": float(p)}


def holm(p_values):
    """Holm 1979, in the original order."""
    p = np.asarray(p_values, float)
    order, out, running = np.argsort(p), np.empty(p.size), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (p.size - rank) * p[i]))
        out[i] = running
    return out


def fleiss_kappa(decisions):
    """Fleiss 1971 for a people x tools table of yes/no. Not defined when every answer is the same."""
    d = np.asarray(decisions, float)
    k = d.shape[1]
    yes = d.sum(1)
    observed = ((yes * (yes - 1) + (k - yes) * (k - yes - 1)) / (k * (k - 1))).mean()
    share = yes.sum() / d.size
    expected = share ** 2 + (1 - share) ** 2
    return float("nan") if expected == 1 else float((observed - expected) / (1 - expected))


def positive_agreement(a, b):
    """Of the positives of either tool, how often both agree (2 x both / sum of positives)."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    total = int(a.sum() + b.sum())
    return float("nan") if total == 0 else 2 * int((a & b).sum()) / total


def bootstrap_interval(table, statistic, seed, repeats=10000, level=0.95):
    """Percentile interval resampling people (rows), never single decisions."""
    table, rng = np.asarray(table), np.random.default_rng(seed)
    values = [statistic(table[rng.integers(0, len(table), len(table))]) for _ in range(repeats)]
    values = np.asarray([v for v in values if not np.isnan(v)])
    if values.size < 0.95 * repeats:
        return float("nan"), float("nan")
    a = 100 * (1 - level) / 2
    return float(np.percentile(values, a)), float(np.percentile(values, 100 - a))
