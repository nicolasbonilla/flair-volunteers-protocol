# Development set — visual check (30 people, run dev-2, excluded from every estimate)

Montages: `code/qc_montage.py` (FLAIR, SynthSeg regions, each tool's marks; four axial slices at least 8 mm apart with most marks).
Written as the outputs are seen, with the date. Anything that changes the chain is a deviation of PROTOCOL_v6 section 14.

## 2026-11-27

- **PAN_sub-HML0022_v1** (>=50). Registration correct: ventricle and cortex labels on the dark ventricles and the cortical ribbon
  (ventricle/white matter 0.424, under the 0.5 limit). FLAMeS (0.93 mL), LST-AI (1.31) and SAMSEG (2.01): small marks at the tips of
  the frontal horns and along the bodies of the lateral ventricles. MindGlide (5.36): along the ventricular lining. WMH-SynthSeg (14.44):
  large regions behind the trigones and at the frontal horns. Bright spots inside the ventricles (choroid plexus) mostly not marked.
  No change to the chain. Observation only: frontal-horn marks sit where normal periventricular bright caps are seen in adults.

## 2026-11-27, run dev-2 complete (30 of 30 scans, about 36 machine-hours with HD-BET, 3 Spot machines, about 6 USD)

The check of `cloud/run_all.sh` stopped before step 1: 9 of 30 scans failed the registration check. Montages read for
Baycrest sub-053, NIMH sub-ON65403, PAN sub-HML0370 and GRAND sub-LTV. Decisions: PROTOCOL_v6 section 15 (D1-D3).

- **Baycrest, 6 of 6: ventricle to white matter 3.04-3.15.** sub-053: registration correct (blue ventricle labels exactly on the
  ventricles), CSF bright, image looks T2-weighted. Sidecar: "Sag 3D SPACE FLAIR", TR 4 s, TI 2.5 s (same in 19 study sidecars read).
  Tools marked the bright ventricle edges (FLAMeS 5.49 mL, LST-AI 18.87, MindGlide 2.76, SAMSEG 4.16; WMH-SynthSeg not run). -> D1.
- **NIMH sub-ON65403 (0.594), sub-ON98602 (0.604), PAN sub-HML0370 (0.607).** ON65403: registration correct, small dark ventricles,
  bright FLAIR. HML0370: registration correct, bright flow spots inside the ventricles. Both are good FLAIRs rejected by 0.5. -> D2.
- **GRAND, 6 of 6: ratio 0.0.** sub-LTV: FLAIR and T1w distributed with everything outside brain tissue at zero (89% of voxels, ventricles
  and sulci included). Pattern by tool in the 6: FLAMeS 2, LST-AI 3, MindGlide 6 (35-45 mL in sub-OZL and sub-SEJ), WMH-SynthSeg 3, SAMSEG 3. -> D3.
- **Other 15 scans (Leipzig 6, NIMH 4, PAN 5): 0.20-0.49**, all five tools completed.
- **LST-AI, SynthStrip `--no-csf` (study) against its own HD-BET (section 3 check), 20 scans with both:** pattern 11 against 13; the
  decision differs in 4 of 20 (Leipzig sub-010296 and sub-010309, NIMH sub-ON09681: positive only with HD-BET; PAN sub-HML0051: positive
  only with SynthStrip). Volumes mostly close; GRAND sub-TYO 0.72 against 6.59 mL. To be reported: the LST-AI decision depends on the
  skull-stripping step in about 1 in 5 people, on top of the run-to-run difference its authors report.
