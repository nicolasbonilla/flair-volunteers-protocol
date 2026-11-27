"""Gate of section 5: each tool against its published figure on MSLesSeg (CC BY 4.0), first visit of the 53 people.

Published medians (FLAMeS article, table 4, 51 of the 53, two exclusions not identified): Dice FLAMeS 0.74, LST-AI 0.43,
SAMSEG 0.55; lesion-wise F1 0.77, 0.57, 0.53. "Reproduced" = both within 0.05. Lesions are 26-connected clusters, as there.
A lesion is detected when any voxel overlaps (the published script is not public: stated as an assumption).
Usage: python gate_mslesseg.py <folder with the masks> > gate_result.json
"""
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

PUBLISHED = {"FLAMeS": (0.74, 0.77), "LST-AI": (0.43, 0.57), "SAMSEG": (0.55, 0.53)}
MARGIN = 0.05
TOUCHING = np.ones((3, 3, 3), bool)


def scores(prediction, truth):
    p, t = prediction.astype(bool), truth.astype(bool)
    total = p.sum() + t.sum()
    dice = 1.0 if total == 0 else 2 * (p & t).sum() / total
    tl, nt = ndimage.label(t, TOUCHING)
    pl, npred = ndimage.label(p, TOUCHING)
    found = len(set(np.unique(tl[p])) - {0})                   # truth lesions touched by the prediction
    true_marks = len(set(np.unique(pl[t])) - {0})              # predicted lesions touching the truth
    recall = found / nt if nt else 1.0
    precision = true_marks / npred if npred else 1.0
    f1 = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)
    return {"dice": float(dice), "ltpr": recall, "lfpr": 1 - precision, "f1": f1, "truth_lesions": nt, "marks": npred}


def load(path, like=None):
    image = nib.load(str(path))
    if like is not None and (image.shape != like.shape or not np.allclose(image.affine, like.affine, atol=1e-3)):
        raise ValueError(f"{path.name} is not on the grid of the expert mask")
    return np.asanyarray(image.dataobj)


def masks(folder, case):
    """{tool: binary mask} for one case; FLAMeS = mean of the 5 folds' probabilities at 0.5 (nnU-Net ensembling)."""
    out = {}
    truth_image = nib.load(str(folder / f"{case}_gt.nii.gz"))
    folds = [folder / f"{case}_f{k}_prob.nii.gz" for k in range(5)]
    if all(f.exists() for f in folds):
        stack = np.stack([load(f, truth_image).astype(np.float32) for f in folds])
        scale = 255.0 if stack.max() > 1.5 else 1.0
        out["FLAMeS"] = stack.mean(0) / scale >= 0.5
    for tool, name, rule in (("LST-AI", "lstai_prob", lambda a: a >= 0.5),
                             ("MindGlide", "mindglide_seg", lambda a: a == (1 if a.max() == 1 else 18)),
                             ("WMH-SynthSeg", "wmhsynthseg_seg", lambda a: a == (1 if a.max() == 1 else 77)),
                             ("SAMSEG", "samseg_seg", lambda a: a == (1 if a.max() == 1 else 99))):
            # files of the October runs were stored already binary (1 = lesion); raw outputs carry the tool's label
        f = folder / f"{case}_{name}.nii.gz"
        if not f.exists() and (folder / f"{case}_{name}.mgz").exists():
            f = folder / f"{case}_{name}.mgz"                    # SAMSEG writes FreeSurfer's format
        if f.exists():
            data = load(f, truth_image).astype(np.float32)
            if tool == "LST-AI" and data.max() > 1.5:
                data = data / 255.0
            out[tool] = rule(data)
    return np.asanyarray(truth_image.dataobj) > 0, out


def main(folder):
    folder = Path(folder)
    cases = sorted({p.name.split("_T1_")[0] + "_T1" for p in folder.glob("mslesseg_P*_T1_gt.nii.gz")},
                   key=lambda c: int(c.split("_P")[1].split("_")[0]))
    per_case = {}
    for case in cases:
        truth, predictions = masks(folder, case)
        per_case[case] = {tool: scores(m, truth) for tool, m in predictions.items()}
    result = {"cases": len(cases), "published": PUBLISHED, "margin": MARGIN, "tools": {}}
    for tool in sorted({t for v in per_case.values() for t in v}):
        values = [v[tool] for v in per_case.values() if tool in v]
        summary = {k: float(np.median([x[k] for x in values])) for k in ("dice", "f1", "ltpr", "lfpr")}
        summary["n"] = len(values)
        # sensitivity: how far the median moves when any two people are left out (the authors dropped two)
        dice = np.array([x["dice"] for x in values])
        drop = [np.median(np.delete(dice, [i, j])) for i in range(len(dice)) for j in range(i + 1, len(dice))]
        summary["dice_median_without_any_two"] = [float(min(drop)), float(max(drop))]
        if tool in PUBLISHED:
            d, f = PUBLISHED[tool]
            summary["reproduced"] = abs(summary["dice"] - d) <= MARGIN and abs(summary["f1"] - f) <= MARGIN
        else:
            summary["reproduced"] = "no published figure: installation check only"
        result["tools"][tool] = summary
    result["per_case"] = per_case
    return result


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), indent=1))
