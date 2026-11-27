"""From the cloud rows (one JSON line per scan and tool, rows/<scan>.jsonl) to decisions.csv for analyse.py.

Usage: python collate.py <folder with the .jsonl rows> <worklist.tsv> [<worklist.tsv> ...] > decisions.csv
Every scan of the worklists must have exactly one row per tool: a scan without rows stops here (a failure is a row with
status "failed", written by the chain; a missing row means the run is not finished). Scan id = <cohort>_<person>_v<visit>.
"""
import csv
import json
import sys
from pathlib import Path

TOOLS = ("FLAMeS", "LST-AI", "MindGlide", "WMH-SynthSeg", "SAMSEG")
COLUMNS = ("cohort", "person", "visit", "tool", "status", "pattern", "pattern_volume_rule", "pattern_generous_size",
           "pattern_any_size", "pattern_separate", "pattern_one_voxel_gap", "PV", "JC", "IT", "components",
           "components_3mm", "volume_ml", "ventricle_to_white_matter", "error")


def split(scan):
    """'Baycrest_sub-0001_v1' -> ('Baycrest', 'sub-0001', 1)."""
    head, visit = scan.rsplit("_v", 1)
    cohort, person = head.split("_", 1)
    return cohort, person, int(visit)


def main(folder, worklists):
    scans = [line.split("\t")[0] for w in worklists for line in open(w, encoding="utf-8").read().splitlines()
             if line and not line.startswith("#")]
    if len(scans) != len(set(scans)):
        raise SystemExit("a scan appears in two worklists")
    out = csv.DictWriter(sys.stdout, COLUMNS, extrasaction="ignore", lineterminator="\n")
    out.writeheader()
    for scan in scans:
        path = Path(folder) / f"{scan}.jsonl"
        if not path.exists():
            raise SystemExit(f"no rows for {scan}: the run is not finished")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if sorted(r["tool"] for r in rows) != sorted(TOOLS) or any(r["scan"] != scan for r in rows):
            raise SystemExit(f"{scan}: expected one row per tool")
        cohort, person, visit = split(scan)
        for r in rows:
            out.writerow({**r, "cohort": cohort, "person": person, "visit": visit,
                          "ventricle_to_white_matter": (r.get("registration") or {}).get("ventricle_to_white_matter", "")})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
