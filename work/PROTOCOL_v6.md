# Automated lesion locations on 3D FLAIR in adult volunteers: frequency, agreement among five public tools, and stability between visits

Protocol v6, registered 2026-11-27 (written 2026-11-25; gate 2026-11-26; whole chain tested 2026-11-27 on 4 public scans of another data set).
Author: Nicolás Bonilla Vargas, MSc (Physics), independent researcher, Munich, Germany. ORCID 0009-0006-6155-4391.
Supersedes PROTOCOL_v4 and v5 (never registered). Independent study: it does not use or depend on any other manuscript.
Order before registration: (a) sections 1-11, code and work lists frozen and timestamped (`freeze/MANIFEST_2026-11-27.sha256`, OpenTimestamps
proof); (b) only then were the 30 development people (section 8) processed; (c) this final text, with the author statements of section 12 and
the corrections listed in section 14, frozen and timestamped again (`freeze/MANIFEST_2026-11-27b.sha256`) and registered. No other image of
the five cohorts was downloaded before registration.

## 1. Question
In adult volunteers imaged with 3D FLAIR, how often does the UNREVIEWED output of public lesion-segmentation tools place
lesions in at least 2 of the 3 brain regions of the McDonald criteria that FLAIR can show ("multiregional pattern"), how
much does the answer depend on the tool, and is it stable between two visits of the same person?

Not a diagnosis. Not clinical specificity: volunteers are not people referred for suspected MS. No marked component is
called false, because nobody has read these images.

## 2. Known before this protocol (complete list, to be reproduced in the paper)
- All results of the author's earlier manuscript, not published (submitted to medRxiv 2026-11-21, declined 2026-11-22) in
  SibBMS, Dallas, WMH 2017 and MS cohorts (MSLesSeg among them), including FLAMeS ensemble 19/100 (SibBMS), 40/75 and
  96/100 (Dallas 21-49, 50-89), and 0-97/100 across tools. Also the results of 2026-10-21 (commit 2fa812d) and the interim
  analysis of 2026-10-22 (commit 6d507c4). The five cohorts below were never processed.
- Of the five cohorts, on 2026-11-25: file names, sizes, participants tables, READMEs, text sidecars, descriptor papers.
- A public table of MindGlide per-case volumes in another data set (its authors' source data).
- The gate of section 5 on MSLesSeg (computed 2026-11-26 from outputs of 2026-10-17/18 and a SAMSEG run of 2026-11-26).
- Expectation, stated openly: frequent with at least one tool, and rising with age.

## 3. Cohorts (CC0, open download; `code/cohort.py`, fixed versions, commit hashes in `cohort_counts.json`)

| Cohort | Data set | People with 3D FLAIR + T1w | <50 | >=50 | 3D FLAIR | Screening stated by the provider | Ethics stated |
|---|---|---|---|---|---|---|---|
| Precision Aging Network | ds007522 3.0.1 | 1,124 | 1 | 1,123 | 3 T, 1.2 mm | memory loss or dementia, psychosis; neurologic disease NOT excluded | WIRB-Copernicus Group |
| Baycrest | ds005270 1.0.0 | 158 | 80 | 78 | 3 T, 1 mm | free from any major psychiatric or neurological condition | Baycrest 16-21 |
| Leipzig | ds000221 1.0.0 | 117 | 86 | 29 | 3 T, SPACE, 1 mm (Babayan 2019, table 7) | neurological disorders, multiple sclerosis by name | Leipzig 154/13-ff, 097/15-ff |
| NIMH | ds005752 2.1.0 | 92 | 79 | 12 | 3 T, 1 mm | medically healthy; 1 person annotated as consistent with MS | NIH 17-M-0181 |
| GRAND | ds007831 1.0.4 | 109 | 26 | 83 | 3 T, 1 mm | no major neurological or psychiatric disorder | Georgetown University IRB |

Age not stated: 2 (Leipzig), 1 (NIMH); they enter no age group. Leipzig publishes 5-year bands; in its <50 group 84 of 86 are in
the bands from 20-25 to 30-35. First visit with both images = the visit analysed. Everyone with both images enters, including people coded as
ineligible or annotated with findings (sensitivity without them). The PAN person under 50 enters neither group.
**After setting aside 30 development people: 255 under 50 (primary) and 1,311 aged 50 or more.**
Why these and not others: CC0, 3D FLAIR of at most 1.2 mm, T1w, adults, no disease group. Not used: SibBMS, WMH 2017, Ljubljana, Dallas.
Faces were removed by the providers; none of the tools was found to have been evaluated on defaced FLAIR except SAMSEG (Schwarz 2023).

## 4. Index test (frozen code: `regions.py`, `decide_person.py`)
Lesion component: 26-connected. Counted if its largest centre-to-centre distance plus half a voxel is at least 3 mm
(chosen on artificial ellipsoids, `size_choice.py`: no lesion of 2.5 mm counted beyond 1%; mean error under 0.5 mm in balls).
Regions from SynthSeg 2.0 on T1w, moved to the FLAIR grid with a rigid registration and nearest neighbour; lesion masks stay on the FLAIR grid (WMH-SynthSeg
writes its own 1 mm grid and is brought back with nearest neighbour; SAMSEG works on the T1w grid and its mask is brought to the FLAIR grid with the same rigid matrix, nearest neighbour).
Periventricular: the component is or touches a lateral ventricle (temporal horns included). Juxtacortical: is or touches cerebral cortex.
Infratentorial: at least half of it in brainstem or cerebellum. Pattern: at least 2 of the 3 regions.
Sensitivity: 14.1 mm3 instead of 3 mm (as Gabelic 2014); a whole voxel instead of half; any size; two different components required;
one-voxel gap allowed. The rule of the author's own software is not part of the study (conflict of interest).

| Tool | Version | Input its developers document | Lesion label | Repeatable |
|---|---|---|---|---|
| FLAMeS, 5-fold ensemble | Zenodo 10.5281/zenodo.17955359 v2.0 (CC BY 4.0), CPU, no test-time mirroring (as in the gate) | FLAIR only, skull-stripped with SynthStrip `--no-csf` | 1 | to be measured |
| LST-AI | last stable container v1.2.0, CPU (no graphics card in the project: its mirror averaging is off), no fast mode | T1w + FLAIR skull-stripped by SynthStrip `--no-csf` (FreeSurfer 8.2.0, as for FLAMeS), `--stripped`. Decided in the plumbing runs of 2026-11-26 on one public Dallas scan (ds004856, not study data), after seeing outputs: its own HD-BET took 55 min per scan on CPU (unaffordable); SynthStrip keeping the outer CSF let LST-AI mark bright CSF (0.92 mL against 0.21 mL with HD-BET). Check in the 6 development people of each cohort: LST-AI also with its own HD-BET, difference reported | 1, threshold 0.5 | no, by its authors (Dice 0.857 between two runs) |
| MindGlide | v1.3.0 | raw FLAIR with skull | 18 | yes, by its authors |
| WMH-SynthSeg | FreeSurfer 8.2.0, CPU | FLAIR with skull | 77 | to be measured |
| SAMSEG | FreeSurfer 8.2.0, `--lesion --lesion-mask-pattern 0 1`, seed 12345, 4 threads (repeatability measured in the development set) | T1w + FLAIR with skull, co-registered | 99, threshold 0.3 | to be measured |

None of the five cohorts appears in the training lists of any tool. Outside every training range: 1.2 mm (PAN), defaced images.

## 5. Gate before the single run (one open data set: MSLesSeg, CC BY 4.0, figshare 27919209 v1, distributed skull-stripped images)
Published medians (FLAMeS article, table 4, 51 of the 53 training people, two exclusions not identified): Dice FLAMeS 0.74, LST-AI 0.43, SAMSEG 0.55;
lesion-wise F1 0.77, 0.57, 0.53. First visit of the 53 people. **Reproduced** = Dice and F1 both within 0.05 of the published medians, for the configuration described there
(skull-stripped input, as they had no other; SAMSEG and LST-AI with T1w). This checks installation, not accuracy, and not the skull-stripping step.
MindGlide and WMH-SynthSeg have no published figure on open data that can be repeated: **installation verified** = the developers' own example or test reproduced and two identical runs.
**Result (2026-11-26, `code/gate_mslesseg.py`, any-voxel lesion overlap):** FLAMeS ensemble Dice 0.744 and F1 0.744 (published 0.74 and 0.77): reproduced; dropping any two people moves the Dice median between 0.741 and 0.744.
LST-AI Dice 0.422 and F1 0.616 (0.43 and 0.57): reproduced (F1 0.046 from the published median; limit 0.05). SAMSEG (run of 2026-11-26, FreeSurfer 8.2.0 by digest, T1w + FLAIR, `--lesion --lesion-mask-pattern 0 1`, seed 12345, 4 threads, 53 of 53 completed, median 666 s per person, 546-1129 s) Dice 0.573 and F1 0.501 (0.55 and 0.53): reproduced (F1 0.029 from the published median; limit 0.05); dropping any two people moves the Dice median between 0.547 and 0.578. Installation only, no published figure: MindGlide Dice 0.274, F1 0.395; WMH-SynthSeg Dice 0.290, F1 0.441 (reported, not used to judge them). FLAMeS and LST-AI outputs are those of 2026-10-17/18 (same weights and containers, skull-stripped MNI input as distributed).
FLAMeS not reproduced: the study stops and that is reported. Another tool not reproduced: it stays out of the main tables, with its failure and its results in the supplement.
Each person of MSLesSeg has MS: nothing of this set enters the estimates.

## 6. Estimands (`analyse.py`, `statistics_p1.py`)
**PRIMARY (one).** Proportion with the pattern, FLAMeS ensemble, 255 people under 50 (Baycrest, Leipzig, NIMH, GRAND; since section 15: 154, Leipzig and NIMH), pooled with the exact interval (conservative when
cohorts differ: Hoeffding 1956; checked exactly in the tests), each cohort shown.
Margin 12%. Closest human reference in healthy volunteers, read in full: Gabelic 2014 (82 people without relatives with MS, mean 39.8 years, 3 T, 3-mm 2D FLAIR,
lesions >=3 mm): 3 fulfilled the criterion with at least 2 regions; by its table 3 (4 people with juxtacortical, 7 periventricular, 0 infratentorial) at most 4 of 82 could have had 2 regions by location
alone. Upper exact limit of 4/82 = 12.0%. Its readers also used T2/PD and excluded vascular patterns: it is a reference, not a ground truth.
Readings fixed now: lower limit >12% = "above the margin"; upper limit <12% = "below the margin"; otherwise "inconclusive".
Below the margin does NOT show that a tool is safe in referred people.
**SECONDARY.** (1) Same at >=50. (2) Other tools against FLAMeS, paired, exact McNemar, Bonett-Price interval, Holm. (3) People with at least two tools in disagreement; Fleiss kappa with
bootstrap by person; positive agreement by pair. (4) Two visits of the PAN people in the credit-limited sample (section 9; about 29 at 300 people): people whose decision changes. Scanner software and interval may differ: a change can be real, technical or
both, never called error. LST-AI and any tool whose two runs differ: three runs of these people give the noise floor. (5) Ten-year age bands within PAN, Baycrest and GRAND, descriptive.
**Failures** are never negatives and never dropped: estimate in completed people plus both bounds. A brain mask that cuts brain tissue in the 30 development people is described.
Never: "equivalent", "as often as", "specificity", "likelihood ratio", "false", "first".

## 7. Precision (`design_table.py`, exact)
n=255 under 50: "below" needs at most 20 positive people (7.8%), "above" at least 42 (16.5%). True 5%: 98% of studies end "below"; 20%: 93% "above"; 25%: about 100%; 10-15%: mostly "inconclusive".
At >=50 the size depends on the credit-limited PAN sample (section 9): with 300 PAN people about 494 people, half-width 3.6 to 4.5 points;
about 29 people with two visits: 3 changes = 2.2-27.4%, so stability is descriptive only.

## 8. Split, freeze and single run
30 development people (6 per cohort, seed 20261125, list in `cohort_list.csv`) for the chain, registration check, defacing, run time and cost,
processed after the first freeze (header). A change they cause is a logged deviation with what had been seen. Then code, containers and hashes
are archived with a DOI; one run.
Deviations logged with what had been seen. Tests: 95 with artificial data; 41 deliberate errors, all detected.

## 9. Compute
Measured times per scan on 4 vCPU (research project's compute record, October-November 2026): FLAMeS 69 s per fold (5 folds: 345 s), LST-AI 100 s on skull-stripped input (so in the study: SynthStrip `--no-csf` on T1w and FLAIR first, about 40 s; plus HD-BET in the 30 development people, about 28 machine-hours),
MindGlide 250-290 s on raw input, WMH-SynthSeg 206-216 s (32 GB machine), SAMSEG T1w+FLAIR median 666 s (546-1129 s, gate of 53 people, 2026-11-26), plus SynthSeg, SynthStrip and
registration (about 4 min). Whole chain measured in the plumbing run of 2026-11-27 (4 public Dallas scans, ds004856, not study data, n2-highmem-4: 4 vCPU, 32 GB): 31-33 min per scan, 20 of 20 tool outputs completed, registration check passed in 4 of 4 (ventricle to white matter 0.17-0.39), SAMSEG the longest step (about 16 min). About 0.55 machine-hours per scan; about 1,700 scans (1,566 first visits, 30 development, 105 second visits), plus two extra
LST-AI runs for the 240 repeated scans and HD-BET in the development people: about 950 machine-hours. Google Cloud price catalog of 2026-11-27, us-central1 (N2 core 0.031611 USD/h, RAM 0.004237 USD/GiB-h; Spot 0.01896 and 0.002542; balanced disk 0.10 USD/GiB-month): 0.27 USD/h standard and 0.17 USD/h Spot for n2-highmem-4 with its 80 GB disk, so about 260 USD standard and about 160 USD Spot (Spot prices change), before a 10-20% allowance for repeats. Cheaper: 16 GB machines for every tool except WMH-SynthSeg.
Spot machines can be stopped by Google at any moment, which the jobs allow because every scan is saved as soon as it ends and a restarted job skips it. Plan: Spot, one job per tool and cohort.
The remaining free credit is read on the billing page by the author before the run; the run starts only if it covers the Spot projection plus 20%.
The run is limited by the author's free research credit (about 90 USD left on 2026-11-27, valid until 2027-01-15). Order fixed now, from cost only: (1) Baycrest, Leipzig, NIMH and GRAND, every person (476 first visits, all of the primary analysis): about 44 USD on Spot plus about 4 USD of HD-BET in their development people; (2) PAN: a seeded sample stratified by age (seed 20261125, at most 300 people, with the second visits of the sampled people), its size set only by the credit left after step 1 minus 20%, before any PAN image is processed and never from any result. Work lists from `code/make_worklist.py` (development 30 scans; step 1: 452 scans; PAN sample of 300 people: 329 scans with 29 second visits, ten-year age bands kept within 0.001): each line carries the checksum of the pinned version (git-annex key: SHA-256, MD5 for Leipzig); a download that differs, or fails, is written as a failure of every tool. Rows are joined by `code/collate.py`, which stops when any scan lacks its five rows; `analyse.py` expects exactly the scans of the lists. Machines are launched only by `cloud/launch_study.sh`, which prints the worst-case cost first and creates nothing without the author's approval. Projected cost of development + step 1: about 293 machine-hours, about 49 USD on Spot. Projected again from the 30 development people before the run; if step 1 alone does not fit, SAMSEG, then MindGlide leave, in this order, before any outcome is computed.

## 10. Human reading
None by default: title, abstract and limits say so and no clinical recommendation is made. If two neuroradiologists ever take part it is an amendment registered before the run.

## 11. Openness
New repository with LICENSE, this protocol, code the author has read, frozen list, per-person results (CC0 allows it), versions, checksums, run guide and DOI. STARD-AI and STARD 2015 checked against the final text.

## 12. Affiliation, ethics, conflicts, AI
- Affiliation: true and current only. The author holds a master's degree in Physics (Universidad Nacional de Colombia) and is NOT a researcher of that university: it is a degree, not an affiliation. Byline: independent
  researcher, Munich, Germany.
- Ethics: secondary analysis of public, de-identified, CC0 images; approvals of the original studies listed; no committee reviewed this study because the author has no institution to ask. Never claim exemption. Only journals that accept that explanation.
- Conflict: the author is the founder and developer of MSTool-AI, research software for MS MRI that uses some of these tools; a result on how
  often these tools mark healthy adults bears on how such software should be used. Compute: the author's Google Cloud free credit.
- AI: code and text were written with an AI system (Claude Code, Anthropic) under the author's direction; the AI system also ran the
  computations. The author made the study decisions and approved this protocol. Code, tests (95, with 41 deliberate errors, all detected),
  logs and the exact record of what was run are public with the study.

## 13. Stop rules
Not submitted if: a fact of sections 3-6 cannot be verified; FLAMeS is not reproduced; the author has not read the code; no independent human expert has read the whole manuscript; or the affiliation or ethics statements are not literally true.

## 14. Changes after the first freeze (2026-11-27), before registration
- Header and section 12: author, affiliation, conflict and AI statements filled in; order of freeze, development run and registration stated.
- Sections 6 and 7: secondary analyses (1) and (4) and their precision restated for the credit-limited PAN sample already fixed in section 9.
- Section 5: "at 0.046/0.029 of the limit" corrected to the distance from the published median. Section 8: development people after the freeze.
- `cloud/vm_scans.sh`: lines of the work lists end with CR when written on Windows; the T1 checksum then never matched, so every scan of the
  first development run (dev-1) was written as failed and nothing was computed. The CR is now removed when a line is read; dev-1 is kept as record.
- `cloud/launch_study.sh`: an optional extra metadata field (used to switch on the HD-BET comparison of section 3 for the development people).
- `work/OSF_registration_answers_DRAFT.md`: the answers for the registry form, brought in line with the above (not part of the protocol).

## 15. Deviations caused by the development set (2026-11-27, after registration, before any study image was downloaded)
The 30 development people (run dev-2) were checked as section 8 asks: per-scan rows, the visual montage of `code/qc_montage.py`
(FLAIR, SynthSeg regions, marks of each tool) and the text sidecars. The automatic check of `cloud/run_all.sh` stopped the run before step 1
because 9 of 30 scans failed the registration check. What was seen, and what changes:
- **D1, Baycrest is not processed.** 6 of 6 Baycrest scans: ventricle to white matter 3.04-3.15. The montage shows correct registration
  (labels on the ventricles) and bright CSF: the image does not null the CSF. Its sidecars (6 development people and 19 of the 152 study
  people, every eighth, read 2026-11-27; text only) give TR 4 s and TI 2.5 s in every case ("Sag 3D SPACE FLAIR"); with TR 4 s the CSF null
  is near 1.6 s, so at 2.5 s the CSF recovers. It is not the FLAIR contrast any of the five tools documents. Under section 6 every Baycrest
  scan would only have been a failure of every tool. The 152 Baycrest people (76 under 50, 76 at 50 or more) are reported as not processed,
  with this reason, and are in no estimate. Their tool outputs in the development set were seen (FLAMeS 5.5 mL, LST-AI 18.9 mL in one person,
  marks along bright ventricle edges) and are not used.
- **D2, registration limit 0.8 instead of 0.5.** 3 scans (NIMH sub-ON65403 0.594, NIMH sub-ON98602 0.604, PAN sub-HML0370 0.607) failed
  at 0.5; the montages of ON65403 and HML0370 show correct registration with dark ventricles (small ventricles, flow signal inside them).
  The 15 other passing scans outside GRAND: 0.20-0.49. A registration error puts the ventricle labels on tissue (about 1 or more); unnulled CSF gives about 3.
  `scan_decide.py`: `REGISTRATION_LIMIT = 0.8`; test `test_registration_limit`.
- **D3, GRAND is reported apart.** 6 of 6 GRAND scans: ventricle to white matter 0.0. The distributed FLAIR and T1w have every voxel outside
  brain tissue set to zero (89% of the volume in sub-LTV, CSF of the ventricles and sulci included; same mask in both images); not stated
  in its dataset description. No tool documents such input. GRAND is processed (cost about 9 USD) but the primary estimate and the
  estimands at >=50 exclude it; `analyse.py` reports every estimate again with GRAND (`with_masked_input`), and GRAND by cohort. Its
  development outputs were seen (pattern in 2 of 6 people with FLAMeS, 3 with LST-AI, 6 with MindGlide, which marked 35-45 mL in two
  people, 3 with WMH-SynthSeg, 3 with SAMSEG): they are stated so the reader can judge the decision, which rests on the input, not on the outputs.
- **Primary population now:** Leipzig and NIMH under 50, 154 people (81 + 73); with GRAND 179. Section 7 restated (exact, as before):
  n=154: "below the margin" needs at most 10 positive people (6.5%), "above" at least 28 (18.2%); true 5%: 85% of studies end "below";
  10%: 9% "below", none "above"; 15%: 16% "above"; 20%: 74% "above"; 25%: 98% "above". The study is now less precise than registered.
  Secondary (5): age bands within PAN and GRAND.
- Step 1 of section 9 is now Leipzig, NIMH and GRAND: 300 scans (`worklists/main.tsv`; the earlier list of 452 kept as
  `worklists/main_before_D1.tsv`), about 0.55 machine-hours each, about 165 machine-hours, about 28 USD on Spot.
- Development rows, montages and notes: `work/development_QC.md`. Tests: 103 with artificial data.
- Operation only, no effect on any decision: `cloud/supervise.py` (relaunches a stopped Spot machine, within a cost limit),
  `cloud/launch_study.sh` (relaunch of one shard; skips a machine that exists), `cloud/run_all.sh`, `cloud/run_main.sh`; reading only:
  `code/qc_montage.py` (montages), `code/make_figures.py` (tables and figures from `results.json`).
- Also seen in the development set: LST-AI with SynthStrip against its own HD-BET (section 3 check) differed in the pattern decision in
  4 of 20 scans (details in `work/development_QC.md`); no change to the chain, reported as registered.
