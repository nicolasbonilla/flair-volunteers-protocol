#!/bin/bash
# Gate of PROTOCOL_v6 section 5 for SAMSEG: T1w + FLAIR of MSLesSeg (CC BY 4.0), first visit of the 53 people, as the
# FLAMeS article ran it. Project mstool-research only; bucket gs://mstool-research-data only.
# Safety: standard VM created with --max-run-duration and DELETE; this script also deletes the VM when it ends.
# FreeSurfer 8.2.0 pinned by digest, --network=none; the owner's licence is mounted read-only and never printed.
# Metadata: shard (0..n-1), shards (n), limit (0 = all cases of the shard).
exec > /var/log/job.log 2>&1
set -x
MD="http://metadata/computeMetadata/v1/instance"
meta(){ curl -sf -H "Metadata-Flavor: Google" "$MD/$1" 2>/dev/null || true; }
NAME=$(meta name); ZONE=$(meta zone | awk -F/ '{print $NF}')
SHARD=$(meta attributes/shard); SHARD=${SHARD:-0}
SHARDS=$(meta attributes/shards); SHARDS=${SHARDS:-1}
LIMIT=$(meta attributes/limit); LIMIT=${LIMIT:-0}
FSIMG="freesurfer/freesurfer@sha256:5648104ca75a24f6ee5a8786146f99b405c2bda1da12bff723a15056da8ddf6b"   # 8.2.0
BK="gs://mstool-research-data"; OUT="$BK/p1gate/samseg"
export CLOUDSDK_STORAGE_PROCESS_COUNT=1
upload_log(){ gcloud storage cp /var/log/job.log "$OUT/logs/$NAME.log" --quiet 2>/dev/null || true; }
finish(){ upload_log; rm -rf /w/lic; gcloud compute instances delete "$NAME" --zone "$ZONE" --quiet; }
trap finish EXIT

mkdir -p /w/data /w/lic && cd /w
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq docker.io unzip 2>&1 | tail -1
systemctl start docker
fallocate -l 16G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile || true
for a in 1 2 3; do docker pull "$FSIMG" && break; sleep 30; done
docker image inspect "$FSIMG" > /dev/null || exit 1
set +x
gcloud storage cp "$BK/secrets/freesurfer/license.txt" /w/lic/license.txt --quiet && chmod 600 /w/lic/license.txt
set -x
gcloud storage cp "$BK/inputs/mslesseg_52771814.zip" /w/mslesseg.zip --quiet || exit 1
echo "$(sha256sum /w/mslesseg.zip)"; gcloud storage cat "$BK/inputs/mslesseg_52771814.zip.sha256"
unzip -q /w/mslesseg.zip -d /w/data
find /w/data -iname "*.nii*" | head -20
upload_log

# first visit (T1) of every training person: P<n>_T1_FLAIR and P<n>_T1_T1
python3 - "$SHARD" "$SHARDS" "$LIMIT" > /w/cases.txt <<'PY'
import glob, os, re, sys
shard, shards, limit = map(int, sys.argv[1:])
files = glob.glob("/w/data/**/*.nii*", recursive=True)
def find(person, kind):
    hits = [f for f in files if re.search(rf"(^|/)P{person}_T1_{kind}\.nii(\.gz)?$", f)]
    return hits[0] if len(hits) == 1 else None
people = sorted({int(m.group(2)) for f in files for m in [re.search(r"(^|/)P(\d+)_T1_FLAIR\.nii", f)] if m})
people = [p for i, p in enumerate(people) if i % shards == shard]
rows = [(p, find(p, "FLAIR"), find(p, "T1")) for p in people]
rows = [r for r in rows if r[1] and r[2]]
for p, flair, t1 in rows[: limit or None]:
    print(p, t1, flair, sep="	")            # the folder name has a space: tab-separated
PY
cat /w/cases.txt
[ -s /w/cases.txt ] || exit 1

while IFS=$'	' read -r P T1 FLAIR; do
  CASE="mslesseg_P${P}_T1"
  if gcloud storage ls "$OUT/${CASE}_samseg_seg.mgz" > /dev/null 2>&1; then echo "done before: $CASE"; continue; fi
  rm -rf /w/case && mkdir -p /w/case/in /w/case/out && cp "$T1" /w/case/in/t1.nii.gz && cp "$FLAIR" /w/case/in/flair.nii.gz
  S=$(date +%s)
  docker run --rm --network=none -v /w/case:/work -v /w/lic/license.txt:/usr/local/freesurfer/license.txt:ro \
    -e FS_LICENSE=/usr/local/freesurfer/license.txt --entrypoint /bin/bash "$FSIMG" -c \
    'source "$FREESURFER_HOME/SetUpFreeSurfer.sh" >/dev/null 2>&1; run_samseg --input /work/in/t1.nii.gz /work/in/flair.nii.gz --output /work/out --lesion --lesion-mask-pattern 0 1 --threads 4 --random-seed 12345'
  RC=$?; E=$(( $(date +%s) - S ))
  echo "CASE $CASE rc=$RC seconds=$E"
  if [ $RC -eq 0 ] && [ -f /w/case/out/seg.mgz ]; then
    gcloud storage cp /w/case/out/seg.mgz "$OUT/${CASE}_samseg_seg.mgz" --quiet
    echo "$CASE,$E" > /w/t.csv && gcloud storage cp /w/t.csv "$OUT/times/${CASE}.csv" --quiet
  fi
  upload_log
done < /w/cases.txt
