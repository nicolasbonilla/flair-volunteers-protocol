# Automated lesion locations on 3D FLAIR in adult volunteers — registered protocol

Nicolás Bonilla Vargas, MSc (Physics), independent researcher, Munich, Germany · ORCID [0009-0006-6155-4391](https://orcid.org/0009-0006-6155-4391)

This repository is the public registration of a study protocol, made **before the study images were analysed**.
The protocol is [`work/PROTOCOL_v6.md`](work/PROTOCOL_v6.md). It asks how often the unreviewed output of five public
lesion-segmentation tools (FLAMeS, LST-AI, MindGlide, WMH-SynthSeg, SAMSEG) places lesions in at least two of the
periventricular, juxtacortical and infratentorial regions in adult volunteers imaged with 3D FLAIR, using five CC0 OpenNeuro
data sets. It is not a diagnostic study and makes no clinical recommendation.

## What is frozen, and how to check it

| File | What it proves |
|---|---|
| `freeze/MANIFEST_2026-11-27.sha256` + `.ots` | First freeze: SHA-256 of methods, code and work lists, timestamped on public OpenTimestamps calendars **before** the 30 development people were processed. Files changed since are listed in section 14 of the protocol. |
| `freeze/MANIFEST_2026-11-27b.sha256` + `.ots` | Final freeze: SHA-256 of every file of this registration, timestamped before any primary-analysis image was downloaded. |

```
sha256sum -c freeze/MANIFEST_2026-11-27b.sha256      # every line must say OK
ots verify freeze/MANIFEST_2026-11-27b.sha256.ots    # OpenTimestamps client; Bitcoin attestation after a few hours
```

## Contents

- `work/PROTOCOL_v6.md` — the protocol (questions, cohorts, tools, region rules, statistics, stop rules, deviations).
- `code/` — region rules, per-person decisions, statistics, analysis, work lists; `pytest` runs 95 tests on artificial data.
- `cloud/` — the scripts that run every tool on every scan (containers pinned by digest, no network inside the containers).
- `worklists/` — the scans of the development set and of the primary step, with the checksum promised by each pinned data version.

Every deviation from this protocol will be logged with what had been seen when it was decided.

## Licences

Code: MIT (see `LICENSE`). Protocol text: CC BY 4.0. The participant lists are derived from the CC0 participants tables of the
OpenNeuro data sets named in the protocol. Code and text were written with an AI system (Claude Code, Anthropic) under the
author's direction; see section 12 of the protocol.
