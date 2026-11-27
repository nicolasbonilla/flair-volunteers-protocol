"""Work list for the cloud chain: one line per scan with the download address and the checksum the pinned version promises.

Usage: python make_worklist.py <step> > list.tsv     step = development | main | pan:<n>
  development: the 30 development people (seeded in cohort.py), all cohorts
  main:        every other person of Leipzig, NIMH and GRAND (step 1 of protocol section 9; Baycrest not processed, deviation D1
               of section 15: its distributed FLAIR does not null the CSF)
  pan:<n>:     seeded age-stratified sample of n PAN people (n <= 300) with their second visits (step 2)
Columns: scan_id, flair_url, t1_url, flair_check, t1_check ("sha256:<hex>" or "md5:<hex>", from the git-annex key of each file at
the pinned commit in cohort_counts.json; Leipzig uses MD5 keys): file names only, no image is read. vm_scans.sh refuses a download that differs.
"""
import csv
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
S3 = "https://s3.amazonaws.com/openneuro.org"
SEED = 20261125
KEY = re.compile(r"(SHA256|MD5)E?-s\d+--([0-9a-f]{32,64})")
NOT_PROCESSED = ("Baycrest",)        # protocol section 15, D1


def git(*arguments):
    return subprocess.run(["git", *arguments], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def annex_hashes(dataset, version, commit, paths, folder):
    """{path: "sha256:<hex>" or "md5:<hex>"} from the annex key of each path at the pinned commit."""
    place = str(Path(folder) / dataset)
    git("clone", "--quiet", "--bare", "--depth", "1", "--branch", version, f"https://github.com/OpenNeuroDatasets/{dataset}.git", place)
    if git("-C", place, "rev-parse", "HEAD").strip() != commit:
        raise SystemExit(f"{dataset} {version}: commit differs from cohort_counts.json")
    batch = subprocess.run(["git", "-C", place, "cat-file", "--batch"], input="".join(f"HEAD:{p}\n" for p in paths),
                           capture_output=True, text=True, encoding="utf-8", check=True).stdout
    out, lines = {}, iter(batch.splitlines())
    for p in paths:
        header = next(lines)
        if header.endswith("missing"):
            raise SystemExit(f"{dataset}: {p} not in the pinned version")
        found = KEY.search(next(lines))
        if not found:
            raise SystemExit(f"{dataset}: {p} has no SHA-256 or MD5 annex key")
        out[p] = f"{found.group(1).lower()}:{found.group(2)}"
    return out


def choose(rows, step):
    if step == "development":
        return [r for r in rows if r["development"] == "1"]
    if step == "main":
        return [r for r in rows if r["development"] == "0" and r["cohort"] not in ("PAN", *NOT_PROCESSED)]
    n = int(step.split(":")[1])
    if not 0 < n <= 300:
        raise SystemExit("PAN sample: 1 to 300 people")
    first = [r for r in rows if r["cohort"] == "PAN" and r["development"] == "0" and r["visit"] == "1"]
    bands = {}
    for r in first:                                   # ten-year bands of age at the first visit; no age = own band
        bands.setdefault(int(float(r["age"]) // 10) if r["age"] else -1, []).append(r)
    rng, total, picked = random.Random(SEED), len(first), []
    for band in sorted(bands):                        # proportional allocation, largest remainders
        bands[band].sort(key=lambda r: r["person"])
    quota = {b: n * len(v) / total for b, v in bands.items()}
    take = {b: int(q) for b, q in quota.items()}
    for b in sorted(quota, key=lambda b: (-(quota[b] - take[b]), b))[: n - sum(take.values())]:
        take[b] += 1
    for band in sorted(bands):
        picked += rng.sample(bands[band], take[band])
    people = {r["person"] for r in picked}
    return [r for r in rows if r["cohort"] == "PAN" and r["person"] in people]


def main(step):
    rows = list(csv.DictReader(open(HERE / "cohort_list.csv", encoding="utf-8")))
    counts = json.load(open(HERE / "cohort_counts.json", encoding="utf-8"))
    chosen = choose(rows, step)
    with tempfile.TemporaryDirectory() as folder:
        hashes = {}
        for cohort in sorted({r["cohort"] for r in chosen}):
            mine = [r for r in chosen if r["cohort"] == cohort]
            paths = sorted({r[k] for r in mine for k in ("flair", "t1")})
            hashes[cohort] = annex_hashes(mine[0]["dataset"], mine[0]["version"], counts[cohort]["commit"], paths, folder)
    for r in chosen:
        scan = f"{r['cohort']}_{r['person']}_v{r['visit']}"
        h = hashes[r["cohort"]]
        print(scan, f"{S3}/{r['dataset']}/{r['flair']}", f"{S3}/{r['dataset']}/{r['t1']}", h[r["flair"]], h[r["t1"]], sep="\t")


if __name__ == "__main__":
    main(sys.argv[1])
