"""Visual check of one scan: FLAIR with the SynthSeg regions and each tool's marks, 4 axial slices, one PNG.

Usage: python qc_montage.py <folder with flair.nii.gz and the unpacked masks> <scan_id> <out.png>
Rows: anatomy (ventricles blue, cortex green, brainstem and cerebellum yellow), then one row per tool (marks in red).
Slices: the four axial slices with most marks of any tool (or evenly spaced when there are none). Reading only, no decision.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
from nibabel.processing import resample_from_to

TOOLS = (("FLAMeS", "flames.nii.gz", 1), ("LST-AI", "lstai.nii.gz", 1), ("MindGlide", "mindglide.nii.gz", 18),
         ("WMH-SynthSeg", "wmhsynthseg.nii.gz", 77), ("SAMSEG", "samseg_on_flair.nii.gz", 99))
REGIONS = {"ventricles": ((4, 43), (0.2, 0.4, 1.0)), "cortex": ((3, 42), (0.1, 0.8, 0.2)),
           "brainstem/cerebellum": ((7, 8, 16, 46, 47), (1.0, 0.85, 0.1))}


def on_flair(path, flair, label):
    image = nib.load(str(path))
    data = np.asanyarray(image.dataobj)
    hit = (data == label) if data.max() > 1 else (data > 0)
    if image.shape != flair.shape or not np.allclose(image.affine, flair.affine, atol=1e-3):
        hit = np.asanyarray(resample_from_to(nib.Nifti1Image(hit.astype(np.uint8), image.affine), flair, order=0).dataobj) > 0
    return hit


def main(folder, scan, out):
    folder = Path(folder)
    flair = nib.as_closest_canonical(nib.load(str(folder / "flair.nii.gz")))
    f = np.asanyarray(flair.dataobj).astype(np.float32)
    labels = np.asanyarray(resample_from_to(nib.load(str(folder / "labels_on_flair.nii.gz")), flair, order=0).dataobj)
    marks = {}
    for tool, name, label in TOOLS:
        if (folder / name).exists():
            marks[tool] = on_flair(folder / name, flair, label)
    per_slice = sum(m.sum(axis=(0, 1)) for m in marks.values()) if marks else np.zeros(f.shape[2])
    gap = max(1, int(round(8 / flair.header.get_zooms()[2])))      # slices at least 8 mm apart
    if per_slice.max() > 0:
        slices = []
        for z in np.argsort(per_slice)[::-1]:
            if per_slice[z] > 0 and all(abs(z - k) >= gap for k in slices):
                slices.append(int(z))
            if len(slices) == 4:
                break
        slices = sorted(slices) if len(slices) == 4 else np.linspace(f.shape[2] * 0.3, f.shape[2] * 0.75, 4).astype(int)
    else:
        slices = np.linspace(f.shape[2] * 0.3, f.shape[2] * 0.75, 4).astype(int)
    box = np.argwhere(labels > 0)                                    # crop to the brain, 5 voxels of margin
    (x0, y0, _), (x1, y1, _) = box.min(0) - 5, box.max(0) + 6
    f, labels = f[max(x0, 0):x1, max(y0, 0):y1], labels[max(x0, 0):x1, max(y0, 0):y1]
    marks = {t: m[max(x0, 0):x1, max(y0, 0):y1] for t, m in marks.items()}
    lo, hi = np.percentile(f[labels > 0], (1, 99.5)) if (labels > 0).any() else np.percentile(f, (1, 99.5))
    rows = 1 + len(TOOLS)
    fig, axes = plt.subplots(rows, 4, figsize=(12, 3.2 * rows), facecolor="black")
    for c, z in enumerate(slices):
        base = np.clip((f[:, :, z] - lo) / (hi - lo), 0, 1).T[::-1]
        ax = axes[0, c]
        rgb = np.dstack([base] * 3)
        for name, (codes, colour) in REGIONS.items():
            m = np.isin(labels[:, :, z], codes).T[::-1]
            rgb[m] = 0.55 * rgb[m] + 0.45 * np.array(colour)
        ax.imshow(rgb)
        ax.set_title(f"slice {z}", color="white", fontsize=8)
        for r, (tool, _, _) in enumerate(TOOLS, start=1):
            ax = axes[r, c]
            rgb = np.dstack([base] * 3)
            if tool in marks:
                m = marks[tool][:, :, z].T[::-1]
                rgb[m] = np.array((1.0, 0.1, 0.1))
            ax.imshow(rgb)
            if c == 0:
                ml = marks[tool].sum() * np.prod(flair.header.get_zooms()[:3]) / 1000 if tool in marks else 0
                ax.set_ylabel(f"{tool}  {ml:.2f} mL" if tool in marks else f"{tool} (missing)", color="white", fontsize=9)
    for ax in axes.ravel():
        ax.set_xticks([]), ax.set_yticks([])
    axes[0, 0].set_ylabel("anatomy", color="white", fontsize=8)
    fig.suptitle(scan, color="white", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=90, facecolor="black")


if __name__ == "__main__":
    main(*sys.argv[1:4])
