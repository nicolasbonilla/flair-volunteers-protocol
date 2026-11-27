"""Read the images of one person and one tool, put the anatomy on the FLAIR grid, and write one row.

anatomy  SynthSeg labels computed on T1w (any grid)
matrix   4x4 world matrix (mm) from FLAIR to T1w, or None when both already share the same space
lesions  mask of the tool: on the FLAIR grid (FLAMeS, LST-AI, MindGlide), on its own 1 mm grid in the FLAIR space
         (WMH-SynthSeg), or on the T1w grid (SAMSEG, which is the only one that also needs the matrix)
"""
import nibabel as nib
import numpy as np
from scipy.ndimage import map_coordinates

from regions import decide

LESION_LABEL = {"FLAMeS": 1, "LST-AI": 1, "MindGlide": 18, "WMH-SynthSeg": 77, "SAMSEG": 99}


def on_grid(image, like, matrix=None):
    """Nearest-neighbour copy of `image` on the grid of `like`. Outside the image: 0."""
    to_voxel = np.linalg.inv(image.affine) @ (np.eye(4) if matrix is None else matrix) @ like.affine
    grid = np.indices(like.shape[:3]).reshape(3, -1)
    where = to_voxel[:3, :3] @ grid + to_voxel[:3, 3:]
    values = map_coordinates(np.asanyarray(image.dataobj), where, order=0, mode="constant", cval=0)
    return values.reshape(like.shape[:3])


def same_grid(a, b):
    return a.shape[:3] == b.shape[:3] and np.allclose(a.affine, b.affine, atol=1e-3)


def person(flair, anatomy, lesions, tool, matrix=None):
    """One dictionary with the decision. Any problem raises an error: it becomes a failure, never a negative."""
    for name, image in (("flair", flair), ("anatomy", anatomy), ("lesions", lesions)):
        if len(image.shape) != 3:
            raise ValueError(f"{name} is not 3D: {image.shape}")
    labels = on_grid(anatomy, flair, matrix)
    if not {4, 43} <= set(np.unique(labels).tolist()):
        raise ValueError("no lateral ventricles on the FLAIR grid: the anatomy or the registration failed")
    if not {3, 42} <= set(np.unique(labels).tolist()):
        raise ValueError("no cerebral cortex on the FLAIR grid")
    data = np.asanyarray(lesions.dataobj)
    if not np.isfinite(data).all():
        raise ValueError("the lesion mask has values that are not numbers")
    mask = data == LESION_LABEL[tool]
    if tool in ("FLAMeS", "LST-AI") and not set(np.unique(data).tolist()) <= {0, 1}:
        raise ValueError("a binary mask was expected")
    if tool == "SAMSEG" or not same_grid(lesions, flair):
        if tool not in ("WMH-SynthSeg", "SAMSEG"):
            raise ValueError(f"{tool} should write its mask on the FLAIR grid")
        mask = on_grid(nib.Nifti1Image(mask.astype(np.uint8), lesions.affine), flair,
                       matrix if tool == "SAMSEG" else None) == 1
    sides = tuple(float(v) for v in np.sqrt((flair.affine[:3, :3] ** 2).sum(0)))
    return decide(mask, labels, sides)
