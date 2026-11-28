"""Keep the machines of one run alive until every scan of its list has its rows, with a hard limit on relaunches.

Usage: python supervise.py <run> <local list.tsv> <machines> <hours per machine> <budget USD> <hours per scan> [extra metadata]
A shard is relaunched (launch_study.sh, Spot) only when it has no machine and still has scans without rows; at most
MAX_LAUNCHES times per shard; a relaunch lasts only what its remaining scans need (hours per scan x scans left + 1 h), and no
launch is made if the worst case of all launches so far would pass the budget (price as in launch_study.sh). Exits 0 when the run is
complete, 1 when a shard used up its launches. Project mstool-research only (isolated gcloud configuration).
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

MAX_LAUNCHES = 3
PRICE = 4 * 0.01896 + 32 * 0.002542 + 120 * 0.10 / 730         # USD per hour, Spot n2-highmem-4 + 120 GB disk, catalog 2026-11-27
BUCKET = "mstool-research-data"
ENV = {**os.environ, "CLOUDSDK_CONFIG": "C:/Users/Nicolas/.gcloud-mstool"}
HERE = os.path.dirname(os.path.abspath(__file__))
# On Windows a bare "bash" can resolve to the WSL launcher (System32), which has no Linux installed: use Git's bash.
BASH = next((p for p in (os.environ.get("P1_BASH"), r"C:\Program Files\Git\bin\bash.exe") if p and os.path.exists(p)),
            "bash") if os.name == "nt" else "bash"


def gcloud(*args):
    out = subprocess.run(["gcloud", *args], capture_output=True, text=True, env=ENV, shell=os.name == "nt")
    if out.returncode:
        raise RuntimeError(out.stderr[-300:])
    return out.stdout


def done_scans(run, token):
    names, page = set(), ""
    while True:
        url = (f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?prefix=p1run/{run}/rows/"
               f"&fields=items(name),nextPageToken&maxResults=1000" + (f"&pageToken={page}" if page else ""))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        data = json.load(urllib.request.urlopen(req, timeout=60))
        names |= {i["name"].rsplit("/", 1)[1][:-len(".jsonl")] for i in data.get("items", [])}
        page = data.get("nextPageToken")
        if not page:
            return names


def main(run, list_path, machines, hours, budget, per_scan, extra=""):
    scans = [l.split("\t")[0] for l in open(list_path, encoding="utf-8").read().splitlines() if l and not l.startswith("#")]
    shard_of = {s: i % machines for i, s in enumerate(scans)}       # same rule as vm_scans.sh
    launches = {i: 0 for i in range(machines)}
    spent_worst = 0.0                                                 # machines alive at start are counted at full length
    started = False
    while True:
        try:
            token = gcloud("auth", "print-access-token").strip()
            done = done_scans(run, token)
            alive = set(gcloud("compute", "instances", "list", "--project=mstool-research",
                               f"--filter=name~^p1-{run}-", "--format=value(name)").split())
        except Exception as error:                                   # network hiccup: never act on a failed read
            print(time.strftime("%H:%M"), "read failed, waiting:", str(error)[:120], flush=True)
            time.sleep(300)
            continue
        left = {i: sum(1 for s in scans if shard_of[s] == i and s not in done) for i in range(machines)}
        print(time.strftime("%H:%M"), f"done {len(done & set(scans))}/{len(scans)}", "left by shard", left, "alive", sorted(alive), flush=True)
        if not started:
            spent_worst += sum(hours * PRICE for i in range(machines) if f"p1-{run}-{i}" in alive)
            started = True
        if not any(left.values()):
            return 0
        for i in range(machines):
            if left[i] and f"p1-{run}-{i}" not in alive:
                if launches[i] >= MAX_LAUNCHES:
                    print(f"shard {i}: {MAX_LAUNCHES} launches used, stopping", flush=True)
                    return 1
                h = min(hours, int(per_scan * left[i]) + 1)
                if spent_worst + h * PRICE > budget:
                    print(f"shard {i}: a launch of {h} h would pass the budget of {budget} USD, stopping", flush=True)
                    return 1
                launches[i] += 1
                spent_worst += h * PRICE
                print(f"launching shard {i} (launch {launches[i]}, {h} h, worst case so far {spent_worst:.2f} USD)", flush=True)
                launched = subprocess.run([BASH, os.path.join(HERE, "launch_study.sh"), run, f"gs://{BUCKET}/p1run/{run}/list.tsv",
                                           str(machines), str(h), "--go", "--only", str(i)],
                                          env={**ENV, "EXTRA_METADATA": extra}, shell=False)
                if launched.returncode:                               # never count on a machine that was not created
                    print(f"shard {i}: launch failed (code {launched.returncode}), stopping", flush=True)
                    return 1
        time.sleep(600)


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[0], a[1], int(a[2]), int(a[3]), float(a[4]), float(a[5]), a[6] if len(a) > 6 else ""))
