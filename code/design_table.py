"""Probability of each of the three readings, by true proportion. Exact calculation, no data."""
import numpy as np
from scipy.stats import binom

from statistics_p1 import exact_interval, reading

for n in (255,):
    readings = np.array([reading(x, n) for x in range(n + 1)])
    above = min(x for x in range(n + 1) if readings[x] == "above the margin")
    below = max(x for x in range(n + 1) if readings[x] == "below the margin")
    print(f"n={n}: below the margin if x<={below} ({100*below/n:.1f}%), above if x>={above} ({100*above/n:.1f}%)")
    for p in (0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30):
        w = binom.pmf(np.arange(n + 1), n, p)
        print(f"   true {100*p:4.0f}%  below {100*w[readings == 'below the margin'].sum():5.1f}"
              f"  inconclusive {100*w[readings == 'inconclusive'].sum():5.1f}"
              f"  above {100*w[readings == 'above the margin'].sum():5.1f}")
for n in (95, 105):
    print("two visits", n, [(x, [round(100 * v, 1) for v in exact_interval(x, n)]) for x in (5, 10, 20)])
