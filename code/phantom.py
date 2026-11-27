"""Artificial heads with known anatomy and known lesions. No person is involved."""
import numpy as np

SHAPE = (80, 96, 80)
LESION_SITES = {"PV": (29, 48, 50), "JC": (13, 48, 50), "DEEP": (22, 48, 50), "IT": (40, 40, 16)}


def anatomy():
    """Cortex shell, white matter, two lateral ventricles, brainstem and cerebellum (SynthSeg numbers)."""
    x, y, z = np.indices(SHAPE)
    out = np.zeros(SHAPE, np.int16)
    head = ((x - 40) / 32) ** 2 + ((y - 48) / 42) ** 2 + ((z - 50) / 26) ** 2
    out[head <= 1] = 3                                       # cortex
    out[head <= 0.72] = 2                                    # white matter
    out[(head <= 1) & (x >= 40) & (out == 3)] = 42
    out[(head <= 0.72) & (x >= 40)] = 41
    for centre, label in ((34, 4), (46, 43)):
        out[((x - centre) / 3) ** 2 + ((y - 48) / 14) ** 2 + ((z - 50) / 6) ** 2 <= 1] = label
    out[((x - 40) / 14) ** 2 + ((y - 34) / 14) ** 2 + ((z - 14) / 8) ** 2 <= 1] = 7
    out[((x - 40) / 5) ** 2 + ((y - 52) / 5) ** 2 + ((z - 14) / 12) ** 2 <= 1] = 16
    return out


def ball(centre, radius_mm, sides=(1.0, 1.0, 1.0), shape=SHAPE):
    grid = np.indices(shape).astype(float)
    distance = sum(((grid[i] - centre[i]) * sides[i]) ** 2 for i in range(3))
    return distance <= radius_mm ** 2 + 1e-9


def lesions(sites, radius_mm=2.0):
    out = np.zeros(SHAPE, bool)
    for site in sites:
        out |= ball(LESION_SITES[site], radius_mm)
    return out
