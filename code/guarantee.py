"""Exploratory analyses E1-E3 of PROTOCOL_v6 section 16 (written 2026-11-28, before any estimate of step 1 was computed).

E1  guarantee on the pattern in healthy people (Learn-then-Test on the smallest lesion counted) and whether it travels
E2  agreement between tools as a safeguard (FLAMeS components confirmed by m other tools)
E3  new marks between two visits (second-visit components far from every first-visit voxel)

Per scan: `scan_rows(folder)` reads the saved masks of one scan (masks/<scan>.tgz extracted: labels_on_flair.nii.gz and
the five masks) and returns, per tool, the pattern at every lambda, and for FLAMeS the pattern on confirmed components.
Then `calibrate`, `transfer` work on those rows. Regions, components and extent are those of regions.py, unchanged.
"""
import numpy as np
from scipy import ndimage
from scipy.stats import binom

from regions import EPS, TOUCHING, components
from statistics_p1 import exact_interval

LAMBDAS = (3, 4, 5, 6, 7, 8, 10, 12, 15)            # mm, smallest largest extent counted
ALPHA, DELTA = 0.05, 0.10
CONFIRM_BY = (1, 2, 3)
MASKS = {"FLAMeS": "flames.nii.gz", "LST-AI": "lstai.nii.gz", "MindGlide": "mindglide.nii.gz",
         "WMH-SynthSeg": "wmhsynthseg.nii.gz", "SAMSEG": "samseg_on_flair.nii.gz"}


def pattern_at(found, lam):
    """Pattern (at least 2 of 3 regions) counting only components whose extent is at least lam mm."""
    kept = [c["regions"] for c in found if c["extent_mm"] >= lam - EPS]
    return len(set().union(*kept)) >= 2


def patterns_by_lambda(lesions, anatomy, sides):
    found = components(lesions, anatomy, sides)
    return {lam: pattern_at(found, lam) for lam in LAMBDAS}


def confirmed_pattern(primary, others, anatomy, sides, m):
    """Pattern on the primary tool's components (>= 3 mm, regions.py) that at least m of the other masks touch by a voxel."""
    found = components(primary, anatomy, sides)
    labelled, _ = ndimage.label(np.asarray(primary) != 0, TOUCHING)      # same labelling and order as components()
    keep = []
    for number, (c, box) in enumerate(zip(found, ndimage.find_objects(labelled)), start=1):
        inside = labelled[box] == number
        votes = sum(bool(np.asarray(o)[box][inside].any()) for o in others)
        if votes >= m:
            keep.append(c)
    return pattern_at(keep, 3)


def new_marks(first, second_on_first_grid, sides, lam=3):
    """Second-visit components of at least lam mm with no voxel within one voxel of any first-visit voxel."""
    near_first = ndimage.binary_dilation(np.asarray(first) != 0, TOUCHING, 1)
    labelled, _ = ndimage.label(np.asarray(second_on_first_grid) != 0, TOUCHING)
    found = components(second_on_first_grid, np.zeros_like(labelled), sides)  # regions not needed here
    count = 0
    for number, (c, box) in enumerate(zip(found, ndimage.find_objects(labelled)), start=1):
        inside = labelled[box] == number
        if c["extent_mm"] >= lam - EPS and not near_first[box][inside].any():
            count += 1
    return count


def p_value(k, n, alpha=ALPHA):
    """Exact binomial p-value of 'the proportion is at least alpha' given k positives of n."""
    return float(binom.cdf(k, n, alpha))


def calibrate(rows, alpha=ALPHA, delta=DELTA):
    """rows: one dict per person {lambda: bool}. Fixed sequence from the largest lambda down (Learn-then-Test):
    continue while the p-value is at most delta. Returns (lambda*, steps); lambda* None = no setting reaches the guarantee."""
    n, best, steps = len(rows), None, []
    for lam in sorted(LAMBDAS, reverse=True):
        k = sum(bool(r[lam]) for r in rows)
        p = p_value(k, n, alpha)
        steps.append({"lambda_mm": lam, "positives": k, "n": n, "p": round(p, 4)})
        if p > delta:
            break
        best = lam
    return best, steps


def transfer(rows_held_out, lam, alpha=ALPHA):
    """The held-out proportion at lambda*, its exact 95% interval and whether it is above alpha."""
    if lam is None:
        return {"lambda_mm": None, "note": "no setting reached the guarantee in the calibration set"}
    n, k = len(rows_held_out), sum(bool(r[lam]) for r in rows_held_out)
    low, high = exact_interval(k, n) if n else (None, None)
    return {"lambda_mm": lam, "positives": k, "n": n, "proportion": round(k / n, 4) if n else None,
            "interval": [low, high], "above_alpha": (k / n > alpha) if n else None}
