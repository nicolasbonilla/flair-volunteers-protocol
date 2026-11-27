"""From one lesion mask and one anatomical label map to one decision per person.

Input: two 3D arrays on the SAME grid (the native grid of the FLAIR image).
  lesions  0 = background, anything else = lesion
  anatomy  SynthSeg labels, brought to the FLAIR grid with nearest neighbour
The lesion mask is never resampled when the tool writes it on the FLAIR grid, so lesion sizes do not change.

Definitions (frozen before any image of the study cohorts is downloaded):
  component      group of lesion voxels touching by a face, an edge or a corner
  extent         largest distance between two voxel centres + half a voxel (geometric mean of the voxel sides);
                 chosen on artificial ellipsoids (size_choice.py): the smallest error of the options tried
  periventricular  at least one voxel of the component is, or touches, a lateral ventricle voxel
  juxtacortical    at least one voxel of the component is, or touches, a cerebral cortex voxel
  infratentorial   at least half of the component lies in the brainstem or the cerebellum
  pattern        components of at least 3 mm in at least 2 of the 3 regions
"""
import itertools

import numpy as np
from scipy import ndimage
from scipy.spatial import ConvexHull, QhullError
from scipy.spatial.distance import pdist

# SynthSeg labels (FreeSurfer numbering)
LATERAL_VENTRICLES = (4, 5, 43, 44)
CEREBRAL_CORTEX = (3, 42)
INFRATENTORIAL = (7, 8, 16, 46, 47)

MIN_EXTENT_MM = 3.0
REGIONS = ("PV", "JC", "IT")
TOUCHING = np.ones((3, 3, 3), bool)
EPS = 1e-6


def extent_mm(voxels, sides):
    """Largest centre-to-centre distance of the voxels (N x 3 indices) plus half a voxel."""
    half_voxel = float(np.prod(sides)) ** (1 / 3) / 2
    points = voxels * np.asarray(sides, float)
    if len(points) == 1:
        return half_voxel
    if len(points) > 50:                                   # only the outer points matter
        try:
            points = points[ConvexHull(points).vertices]
        except QhullError:                                 # flat component: use every point
            pass
    return float(pdist(points).max()) + half_voxel


def components(lesions, anatomy, sides, gap_voxels=0):
    """One dictionary per component: voxels, volume, extent and regions."""
    lesions = np.asarray(lesions) != 0
    anatomy = np.asarray(anatomy)
    if lesions.shape != anatomy.shape or lesions.ndim != 3:
        raise ValueError("mask and anatomy must be 3D and on the same grid")
    if len(sides) != 3 or min(sides) <= 0:
        raise ValueError("three positive voxel sides are needed")

    # A region grown by one voxel marks every voxel that is, or touches, the region.
    grow = 1 + gap_voxels
    near_ventricle = ndimage.binary_dilation(np.isin(anatomy, LATERAL_VENTRICLES), TOUCHING, grow)
    near_cortex = ndimage.binary_dilation(np.isin(anatomy, CEREBRAL_CORTEX), TOUCHING, grow)
    infratentorial = np.isin(anatomy, INFRATENTORIAL)

    labelled, _ = ndimage.label(lesions, TOUCHING)
    found = []
    for number, box in enumerate(ndimage.find_objects(labelled), start=1):
        inside = labelled[box] == number
        voxels = np.argwhere(inside)
        regions = set()
        if infratentorial[box][inside].mean() >= 0.5:
            regions.add("IT")
        else:                                              # the temporal horn and the cortex are supratentorial
            if near_ventricle[box][inside].any():
                regions.add("PV")
            if near_cortex[box][inside].any():
                regions.add("JC")
        found.append({"voxels": len(voxels),
                      "volume_mm3": len(voxels) * float(np.prod(sides)),
                      "extent_mm": extent_mm(voxels, sides),
                      "half_voxel_mm": float(np.prod(sides)) ** (1 / 3) / 2,
                      "regions": regions})
    return found


def large_enough(component, rule="extent"):
    if rule == "extent":
        return component["extent_mm"] >= MIN_EXTENT_MM - EPS
    if rule == "generous":                                 # a whole voxel instead of half
        return component["extent_mm"] + component["half_voxel_mm"] >= MIN_EXTENT_MM - EPS
    if rule == "volume":                                   # sphere of 3 mm, as in Gabelic 2014
        return component["volume_mm3"] >= 14.1 - EPS
    if rule == "any":
        return True
    raise ValueError(rule)


def pattern(found, rule="extent", separate=False):
    """True when the kept components reach at least 2 of the 3 regions.

    separate=True (sensitivity): one component may count for one region only, so two different ones are needed.
    """
    kept = [c["regions"] for c in found if large_enough(c, rule)]
    if not separate:
        return len(set().union(*kept)) >= 2
    reaching = {r: {i for i, regions in enumerate(kept) if r in regions} for r in REGIONS}
    return any(reaching[a] and reaching[b] and len(reaching[a] | reaching[b]) >= 2
               for a, b in itertools.combinations(REGIONS, 2))


def decide(lesions, anatomy, sides):
    """Primary decision and every prespecified sensitivity decision of one person and one tool."""
    touching = components(lesions, anatomy, sides)
    one_voxel_gap = components(lesions, anatomy, sides, gap_voxels=1)
    kept = [c for c in touching if large_enough(c)]
    return {"pattern": pattern(touching),
            "pattern_volume_rule": pattern(touching, "volume"),
            "pattern_generous_size": pattern(touching, "generous"),
            "pattern_any_size": pattern(touching, "any"),
            "pattern_separate": pattern(touching, separate=True),
            "pattern_one_voxel_gap": pattern(one_voxel_gap),
            **{region: any(region in c["regions"] for c in kept) for region in REGIONS},
            "components": len(touching),
            "components_3mm": len(kept),
            "volume_ml": sum(c["volume_mm3"] for c in touching) / 1000}
