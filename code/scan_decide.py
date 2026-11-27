"""One scan, all tools: quality check of the registration, then one row per tool (decide_person).

Usage: python scan_decide.py <scan_folder> <scan_id> [extra]   ->  prints JSON lines, one per tool
       extra: only LST-AI with its own HD-BET (development people, protocol section 3), from lstai_hdbet.nii.gz
The folder holds flair.nii.gz, labels_on_flair.nii.gz (SynthSeg on T1w, already on the FLAIR grid) and the tools' masks:
flames.nii.gz, lstai.nii.gz, mindglide.nii.gz, wmhsynthseg.nii.gz, samseg_on_flair.nii.gz. A missing or unreadable mask is
a failure of that tool; a failed quality check is a failure of every tool. Never a negative.
"""
import json
import sys
import traceback
from pathlib import Path

import nibabel as nib
import numpy as np

from decide_person import LESION_LABEL, person

MASKS = {"FLAMeS": "flames.nii.gz", "LST-AI": "lstai.nii.gz", "MindGlide": "mindglide.nii.gz",
         "WMH-SynthSeg": "wmhsynthseg.nii.gz", "SAMSEG": "samseg_on_flair.nii.gz"}
EXTRA = {"LST-AI own HD-BET": "lstai_hdbet.nii.gz"}
LABEL_OF = {"LST-AI own HD-BET": "LST-AI"}                            # same tool, other skull stripping
WHITE_MATTER, VENTRICLES = (2, 41), (4, 43)


def registration_check(flair, labels):
    """On FLAIR the lateral ventricles are dark: their median must be below half of the white matter's (both from the
    labels moved onto the FLAIR grid). A wrong registration puts the ventricle labels on brain tissue."""
    f = np.asanyarray(flair.dataobj).astype(np.float32)
    lab = np.asanyarray(labels.dataobj)
    wm, vent = f[np.isin(lab, WHITE_MATTER)], f[np.isin(lab, VENTRICLES)]
    if wm.size < 1000 or vent.size < 100:
        return {"passed": False, "reason": "too few white matter or ventricle voxels on the FLAIR grid"}
    ratio = float(np.median(vent) / np.median(wm)) if np.median(wm) > 0 else float("inf")
    return {"passed": ratio < 0.5, "ventricle_to_white_matter": round(ratio, 3)}


def main(folder, scan, extra=False):
    folder = Path(folder)
    flair = nib.load(str(folder / "flair.nii.gz"))
    labels = nib.load(str(folder / "labels_on_flair.nii.gz"))
    check = registration_check(flair, labels)
    for tool, name in (EXTRA if extra else MASKS).items():
        row = {"scan": scan, "tool": tool, "registration": check}
        try:
            if not check["passed"]:
                raise ValueError("registration check failed")
            path = folder / name
            if not path.exists():
                raise FileNotFoundError(f"{name} missing")
            mask = nib.load(str(path))
            data = np.asanyarray(mask.dataobj)
            if LABEL_OF.get(tool, tool) in ("FLAMeS", "LST-AI") and data.max() > 1:      # stored as 0/1 by the pipeline
                raise ValueError("binary mask expected")
            row.update(status="ok", **{k: (int(v) if isinstance(v, (bool, np.bool_)) else v)
                                       for k, v in person(flair, labels, mask, LABEL_OF.get(tool, tool)).items()})
        except Exception as error:                                   # a failure, never a negative
            row.update(status="failed", error=f"{type(error).__name__}: {error}",
                       trace=traceback.format_exc(limit=2)[-400:])
        print(json.dumps(row))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], len(sys.argv) > 3 and sys.argv[3] == "extra")
