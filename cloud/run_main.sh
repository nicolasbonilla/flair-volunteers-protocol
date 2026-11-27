#!/bin/bash
# Step 1 of PROTOCOL_v6 section 9 after the deviations of section 15 (Leipzig, NIMH, GRAND: 300 scans).
# Worst case on Spot: 3 machines x 70 h x 0.168 USD/h = about 35 USD; budget guard 45 USD; expected about 28 USD.
# Approved by the author on 2026-11-27 ("hazlo todo de forma automatica, tienes todos mis permisos").
set -u
cd "$(dirname "$0")"
export CLOUDSDK_CONFIG=C:/Users/Nicolas/.gcloud-mstool CLOUDSDK_STORAGE_PROCESS_COUNT=1
B=gs://mstool-research-data/p1run
for f in ../code/*.py; do timeout 120 gcloud storage cp "$f" "$B/main-1/code/" --quiet || { echo "STOP: code not uploaded"; exit 1; }; done
timeout 120 gcloud storage cp ../worklists/main.tsv "$B/main-1/list.tsv" --quiet || { echo "STOP: list not uploaded"; exit 1; }
python supervise.py main-1 ../worklists/main.tsv 3 70 45 0.55 || { echo "STOP: step 1 incomplete"; exit 1; }
echo "STEP 1 COMPLETE"
