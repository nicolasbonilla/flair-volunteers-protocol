#!/bin/bash
# Development run to the end, a check of its rows, then step 1 of PROTOCOL_v6 section 9 (Baycrest, Leipzig, NIMH, GRAND).
# Budgets (worst case, Spot): development 15 USD, step 1 70 USD; the credit left on 2026-11-27 was about 90 USD.
# Approved by the author on 2026-11-27 ("hazlo todo de forma automatica, tienes todos mis permisos").
set -u
cd "$(dirname "$0")"
export CLOUDSDK_CONFIG=C:/Users/Nicolas/.gcloud-mstool CLOUDSDK_STORAGE_PROCESS_COUNT=1
B=gs://mstool-research-data/p1run
python supervise.py dev-2 ../worklists/development.tsv 3 20 15 1.3 hdbet=1 || { echo "STOP: development run incomplete"; exit 1; }
# every development scan has its five rows; stop if more than 3 of 30 scans failed in any tool
mkdir -p /c/tmp/p1dev2 && rm -f /c/tmp/p1dev2/*.jsonl
timeout 900 gcloud storage cp "$B/dev-2/rows/*.jsonl" /c/tmp/p1dev2/ --quiet || { echo "STOP: rows not downloaded"; exit 1; }
python - <<'PY' || { echo "STOP: development check failed"; exit 1; }
import glob, json, sys
rows = [json.loads(l) for f in glob.glob("C:/tmp/p1dev2/*.jsonl") for l in open(f) if l.strip()]
scans = {r["scan"] for r in rows}
bad = {r["scan"] for r in rows if r["status"] != "ok"}
print("development scans", len(scans), "scans with a failed tool", len(bad), sorted(bad))
sys.exit(0 if len(scans) == 30 and len(bad) <= 3 else 1)
PY
for f in ../code/*.py; do timeout 120 gcloud storage cp "$f" "$B/main-1/code/" --quiet; done
timeout 120 gcloud storage cp ../worklists/main.tsv "$B/main-1/list.tsv" --quiet || { echo "STOP: list not uploaded"; exit 1; }
python supervise.py main-1 ../worklists/main.tsv 3 90 70 0.55 || { echo "STOP: step 1 incomplete"; exit 1; }
echo "STEP 1 COMPLETE"
