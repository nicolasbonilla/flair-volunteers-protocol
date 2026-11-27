#!/bin/bash
# Launch one step of PROTOCOL_v6 section 9 on Spot machines, with a hard ceiling on cost.
# Usage: bash launch_study.sh <run> <gs list.tsv> <machines> <hours per machine> [--go]
# EXTRA_METADATA=hdbet=1 for the development people (LST-AI also with its own HD-BET).
# Without --go it only prints the plan and the worst-case cost (machines x hours x price) and creates nothing.
# The owner approves that figure before --go (feedback 2026-11-27: no cloud spend without his prior OK).
# Project mstool-research only; isolated gcloud configuration; never the global one.
set -euo pipefail
RUN=$1; LIST=$2; N=$3; H=$4; GO=${5:-}; ONLY=${7:-}       # [--go --only <shard>]: relaunch one shard (supervise.py)
export CLOUDSDK_CONFIG=C:/Users/Nicolas/.gcloud-mstool
PROJECT=mstool-research; ZONES="us-central1-c us-central1-a us-central1-f"; MT=n2-highmem-4
# Google Cloud catalog of 2026-11-27, us-central1: Spot N2 core 0.01896 USD/h, RAM 0.002542 USD/GiB-h; balanced disk 0.10 USD/GiB-month
PRICE=$(python -c "print(round(4*0.01896 + 32*0.002542 + 80*0.10/730, 4))")
WORST=$(python -c "print(round($N*$H*$PRICE, 2))")
[ "$N" -le 3 ] || { echo "at most 3 machines (CPU quota 12)"; exit 1; }
echo "run=$RUN list=$LIST machines=$N x $MT Spot, at most $H h each, price $PRICE USD/h"
echo "WORST-CASE COST: $WORST USD (each machine deletes itself at the end or after $H h)"
[ "$GO" = "--go" ] || { echo "plan only: nothing created"; exit 0; }
cd "$(dirname "$0")"
for i in $(if [ -n "$ONLY" ]; then echo "$ONLY"; else seq 0 $((N-1)); fi); do
  if gcloud compute instances list --project=$PROJECT --filter="name=p1-$RUN-$i" --format="value(name)" | grep -q .; then echo "p1-$RUN-$i exists"; continue; fi
  for z in $ZONES; do
    if gcloud compute instances create "p1-$RUN-$i" --project=$PROJECT --zone=$z --machine-type=$MT \
        --provisioning-model=SPOT --instance-termination-action=DELETE --max-run-duration=${H}h \
        --boot-disk-size=80GB --boot-disk-type=pd-balanced --image-family=debian-12 --image-project=debian-cloud \
        --service-account=mstool-runner@mstool-research.iam.gserviceaccount.com --scopes=cloud-platform \
        --metadata=list=$LIST,run=$RUN,shard=$i,shards=$N,threads=4${EXTRA_METADATA:+,$EXTRA_METADATA} --metadata-from-file=startup-script=vm_scans.sh \
        --format="value(name,zone)"; then break; fi
  done
done
# A Spot machine stopped by Google loses at most the scan in progress: run this again with the same arguments; finished scans are skipped.
