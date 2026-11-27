#!/bin/bash
# PROTOCOL_v6: every tool on every scan of a list, then one decision row per tool (code/scan_decide.py).
# Project mstool-research only; bucket gs://mstool-research-data only; results under p1run/<run>/.
# Safety: the VM is created with --max-run-duration and DELETE, and this script deletes it when it ends. Containers pinned
# by digest, --network=none. The owner's FreeSurfer licence is mounted read-only and never printed.
# Every scan is uploaded as soon as it ends and skipped when present (a Spot restart loses at most one scan).
# Metadata: list (gs path of a TSV from code/make_worklist.py: scan_id, flair_url, t1_url, flair_check, t1_check), run (name),
# shard, shards, threads (4), hdbet (1 = also LST-AI with its own HD-BET: development people only, protocol section 3).
exec > /var/log/job.log 2>&1
set -x
MD="http://metadata/computeMetadata/v1/instance"
meta(){ curl -sf -H "Metadata-Flavor: Google" "$MD/$1" 2>/dev/null || true; }
NAME=$(meta name); ZONE=$(meta zone | awk -F/ '{print $NF}')
LIST=$(meta attributes/list); RUN=$(meta attributes/run)
SHARD=$(meta attributes/shard); SHARD=${SHARD:-0}; SHARDS=$(meta attributes/shards); SHARDS=${SHARDS:-1}
TH=$(meta attributes/threads); TH=${TH:-4}; HDBET=$(meta attributes/hdbet); HDBET=${HDBET:-0}
FS="freesurfer/freesurfer@sha256:5648104ca75a24f6ee5a8786146f99b405c2bda1da12bff723a15056da8ddf6b"        # 8.2.0
LST="jqmcginnis/lst-ai@sha256:2b2a0d6454e6efff60a350df3c650ae9584f1926338dec7842f9e71912cc6c85"             # v1.2.0
MG="ghcr.io/ms-pinpoint/mindglide@sha256:14e88f61d6cba18322d03774b168682e255383387aaab55e6a5aa33a2dbdd971"   # 1.3.0
BK="gs://mstool-research-data"; OUT="$BK/p1run/$RUN"
export CLOUDSDK_STORAGE_PROCESS_COUNT=1
upload_log(){ gcloud storage cp /var/log/job.log "$OUT/logs/$NAME.log" --quiet 2>/dev/null || true; }
finish(){ upload_log; rm -rf /w/lic; gcloud compute instances delete "$NAME" --zone "$ZONE" --quiet; }
trap finish EXIT
[ -n "$LIST" ] && [ -n "$RUN" ] || exit 1

mkdir -p /w/lic /w/models && cd /w
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq docker.io unzip python3-venv 2>&1 | tail -1
systemctl start docker
fallocate -l 16G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile || true
for img in "$FS" "$LST" "$MG"; do for a in 1 2 3; do docker pull "$img" && break; sleep 30; done; docker image inspect "$img" > /dev/null || exit 1; done
set +x
gcloud storage cp "$BK/secrets/freesurfer/license.txt" /w/lic/license.txt --quiet && chmod 600 /w/lic/license.txt
set -x
gcloud storage cp "$BK/inputs/WMH-SynthSeg_v10_231110.pth" "$BK/inputs/WMH-SynthSeg_v10_231110.pth.sha256" /w/models/ --quiet || exit 1
[ "$(sha256sum /w/models/WMH-SynthSeg_v10_231110.pth | cut -c1-64)" = "$(cut -c1-64 /w/models/WMH-SynthSeg_v10_231110.pth.sha256)" ] || exit 1
gcloud storage cp "$BK/inputs/flames_weights.zip" "$BK/inputs/flames_weights.zip.sha256" /w/ --quiet || exit 1
[ "$(sha256sum /w/flames_weights.zip | cut -c1-64)" = "$(cut -c1-64 /w/flames_weights.zip.sha256)" ] || exit 1
export nnUNet_raw=/w/nn/raw nnUNet_preprocessed=/w/nn/prep nnUNet_results=/w/nn/results
mkdir -p $nnUNet_raw $nnUNet_preprocessed $nnUNet_results && unzip -q -o /w/flames_weights.zip -d $nnUNet_results && rm -f /w/flames_weights.zip
python3 -m venv /opt/venv && . /opt/venv/bin/activate && pip install -q --upgrade pip
gcloud storage cp "$BK/env/requirements.lock" /w/requirements.lock --quiet || exit 1        # FLAMeS environment of October
pip install -q -r /w/requirements.lock --extra-index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -2
python3 -c "import nnunetv2, nibabel, numpy, scipy; print('env ok', nnunetv2.__file__)" || exit 1
gcloud storage cp "$OUT/code/*.py" /w/code/ --quiet 2>/dev/null || { mkdir -p /w/code && gcloud storage cp "$OUT/code/*.py" /w/code/ --quiet; } || exit 1
gcloud storage cp "$LIST" /w/list.tsv --quiet || exit 1
upload_log

fs(){ docker run --rm --network=none -v /w/s:/work -v /w/lic/license.txt:/fs/license.txt:ro -e FS_LICENSE=/fs/license.txt \
        -v /w/models:/fsmodels:ro -e OMP_NUM_THREADS=$TH --entrypoint /bin/bash "$FS" -c \
        "source \$FREESURFER_HOME/SetUpFreeSurfer.sh >/dev/null 2>&1; cp /fsmodels/WMH-SynthSeg_v10_231110.pth \$FREESURFER_HOME/models/; $1"; }
        # WMH-SynthSeg looks for its model in $FREESURFER_HOME/models (8.2.0-1 in this image): copied there in every run
step(){ local s=$(date +%s); "$@"; local rc=$?; echo "STEP $SCAN $1 rc=$rc seconds=$(( $(date +%s) - s ))"; return $rc; }
# checksum promised by the pinned version ("sha256:<hex>" or "md5:<hex>")
checked(){ local want=${2#*:}; [ -n "$want" ] || return 1; local got; got=$("${2%%:*}sum" "$1" | cut -c1-${#want}); [ "$got" = "$want" ]; }
# a scan that cannot be read is a failure of every tool, never a negative, and never a missing row
failed_rows(){ python3 -c 'import json,sys
for t in ("FLAMeS","LST-AI","MindGlide","WMH-SynthSeg","SAMSEG"): print(json.dumps({"scan":sys.argv[1],"tool":t,"status":"failed","error":sys.argv[2]}))' "$SCAN" "$1"; }

i=0
while IFS=$'\t' read -r SCAN FLAIR_URL T1_URL FLAIR_CK T1_CK; do
  T1_CK=${T1_CK%$'\r'}         # lists written on Windows end their lines with CR (run dev-1 of 2026-11-27: every T1 check failed)
  [ -z "$SCAN" ] || [ "${SCAN:0:1}" = "#" ] && continue
  i=$((i+1)); [ $(( (i-1) % SHARDS )) -eq "$SHARD" ] || continue
  if gcloud storage ls "$OUT/rows/$SCAN.jsonl" > /dev/null 2>&1; then echo "done before: $SCAN"; continue; fi
  rm -rf /w/s && mkdir -p /w/s/nnin /w/s/nnout /w/s/lst /w/s/tmp /w/s/samseg && chmod 777 /w/s   # MindGlide runs as a non-root user
  if ! { curl -sfL --retry 3 "$FLAIR_URL" -o /w/s/flair.nii.gz && curl -sfL --retry 3 "$T1_URL" -o /w/s/t1.nii.gz; }; then WHY="download failed"
  elif ! { checked /w/s/flair.nii.gz "$FLAIR_CK" && checked /w/s/t1.nii.gz "$T1_CK"; }; then WHY="checksum differs from the pinned version"; else WHY=""; fi
  if [ -n "$WHY" ]; then echo "INPUT FAILED $SCAN: $WHY"; failed_rows "$WHY" > /w/s/rows.jsonl
    gcloud storage cp /w/s/rows.jsonl "$OUT/rows/$SCAN.jsonl" --quiet; upload_log; continue; fi
  sha256sum /w/s/flair.nii.gz /w/s/t1.nii.gz > /w/s/inputs.sha256
  # anatomy, registration and the co-registered FLAIR for SAMSEG
  step fs "mri_synthseg --i /work/t1.nii.gz --o /work/t1_synthseg.nii.gz --cpu --threads $TH"
  step fs "mri_coreg --mov /work/flair.nii.gz --ref /work/t1.nii.gz --reg /work/flair_to_t1.lta --threads $TH"
  step fs "mri_vol2vol --mov /work/flair.nii.gz --targ /work/t1_synthseg.nii.gz --lta /work/flair_to_t1.lta --inv --nearest --o /work/labels_on_flair.nii.gz"
  step fs "mri_vol2vol --mov /work/flair.nii.gz --targ /work/t1.nii.gz --lta /work/flair_to_t1.lta --o /work/flair_on_t1.nii.gz"
  # FLAMeS: SynthStrip --no-csf, then the 5-fold ensemble (no test-time mirroring, as in the gate)
  step fs "mri_synthstrip -i /work/flair.nii.gz -o /work/nnin/scan_0000.nii.gz --no-csf --threads $TH"
  step nnUNetv2_predict -i /w/s/nnin -o /w/s/nnout -d 004 -c 3d_fullres -tr nnUNetTrainer_8000epochs -f 0 1 2 3 4 --disable_tta -device cpu -npp 1 -nps 1 \
    && cp /w/s/nnout/scan.nii.gz /w/s/flames.nii.gz
  # LST-AI: T1w + FLAIR skull-stripped by SynthStrip --no-csf, as for FLAMeS (its own HD-BET took 55 min per scan on CPU; SynthStrip
  # keeping the outer CSF let LST-AI mark bright CSF: plumbing runs of 2026-11-26 on a public Dallas scan, not study data), CPU
  step fs "mri_synthstrip -i /work/t1.nii.gz -o /work/t1_brain.nii.gz --no-csf --threads $TH"
  step fs "mri_synthstrip -i /work/flair.nii.gz -o /work/flair_brain.nii.gz --no-csf --threads $TH"
  step docker run --rm --network=none -v /w/s:/work -e OMP_NUM_THREADS=$TH "$LST" --t1 /work/t1_brain.nii.gz --flair /work/flair_brain.nii.gz \
    --output /work/lst --temp /work/tmp --segment_only --stripped --device cpu \
    && cp "/w/s/lst/$(ls /w/s/lst | grep -i 'seg-lst\.nii\.gz$' | head -1)" /w/s/lstai.nii.gz
  # MindGlide: raw FLAIR
  step docker run --rm --network=none -v /w/s:/work "$MG" -i /work/flair.nii.gz -o /work/mindglide.nii.gz --device cpu
  # WMH-SynthSeg: FLAIR with skull, its own 1 mm grid
  step fs "mri_WMHsynthseg --i /work/flair.nii.gz --o /work/wmhsynthseg.nii.gz --device cpu --threads $TH"
  # SAMSEG: T1w + co-registered FLAIR, lesions brighter than the atlas mean on FLAIR only; mask back to the FLAIR grid
  step fs "run_samseg --input /work/t1.nii.gz /work/flair_on_t1.nii.gz --output /work/samseg --lesion --lesion-mask-pattern 0 1 --threads $TH --random-seed 12345" \
    && step fs "mri_vol2vol --mov /work/flair.nii.gz --targ /work/samseg/seg.mgz --lta /work/flair_to_t1.lta --inv --nearest --o /work/samseg_on_flair.nii.gz"
  if [ "$HDBET" = "1" ]; then                  # development people: LST-AI also with its own HD-BET, for the difference
    mkdir -p /w/s/lst_hdbet /w/s/tmp_hdbet && chmod 777 /w/s/lst_hdbet /w/s/tmp_hdbet
    step docker run --rm --network=none -v /w/s:/work -e OMP_NUM_THREADS=$TH "$LST" --t1 /work/t1.nii.gz --flair /work/flair.nii.gz \
      --output /work/lst_hdbet --temp /work/tmp_hdbet --segment_only --device cpu \
      && cp "/w/s/lst_hdbet/$(ls /w/s/lst_hdbet | grep -i 'seg-lst\.nii\.gz$' | head -1)" /w/s/lstai_hdbet.nii.gz
    python3 /w/code/scan_decide.py /w/s "$SCAN" extra > /w/s/extra.jsonl
    gcloud storage cp /w/s/extra.jsonl "$OUT/extra/$SCAN.jsonl" --quiet
  fi
  python3 /w/code/scan_decide.py /w/s "$SCAN" > /w/s/rows.jsonl
  cat /w/s/rows.jsonl | cut -c1-300
  tar -czf /w/s_masks.tgz -C /w/s flames.nii.gz lstai.nii.gz lstai_hdbet.nii.gz mindglide.nii.gz wmhsynthseg.nii.gz samseg_on_flair.nii.gz labels_on_flair.nii.gz flair_to_t1.lta inputs.sha256 2>/dev/null
  gcloud storage cp /w/s_masks.tgz "$OUT/masks/$SCAN.tgz" --quiet
  gcloud storage cp /w/s/rows.jsonl "$OUT/rows/$SCAN.jsonl" --quiet           # last: a row means the scan is complete
  upload_log
done < /w/list.tsv
