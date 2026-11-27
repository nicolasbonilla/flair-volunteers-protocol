"""From one row per person, visit and tool to every number of the paper.

Input   cohort_list.csv   frozen list (cohort.py)
        decisions.csv     cohort, person, visit, tool, status (ok or failed), pattern and the sensitivity columns (collate.py)
        pan.tsv           optional: the PAN sample worklist (make_worklist.py pan:<n>); then only those PAN scans are expected
Output  results.json      nothing else is computed by hand
Usage   python analyse.py cohort_list.csv decisions.csv results.json [pan.tsv]
"""
import csv
import json
import sys
from collections import Counter, defaultdict

import numpy as np

import statistics_p1 as s

TOOLS = ("FLAMeS", "LST-AI", "MindGlide", "WMH-SynthSeg", "SAMSEG")
PRIMARY_TOOL = "FLAMeS"
PRIMARY_COHORTS = ("Baycrest", "Leipzig", "NIMH", "GRAND")
SENSITIVITY = ("pattern_volume_rule", "pattern_generous_size", "pattern_any_size", "pattern_separate",
               "pattern_one_voxel_gap", "PV", "JC", "IT")
SEED = 20261125
BOOTSTRAP = 10000


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load(list_path, decisions_path, pan_path=None):
    """(people, decisions) after checking that every expected row is present exactly once."""
    people = {(r["cohort"], r["person"], int(r["visit"])): r for r in read(list_path) if r["development"] == "0"}
    if pan_path:                                             # protocol section 9, step 2: the seeded PAN sample only
        sample = set()
        for line in open(pan_path, encoding="utf-8").read().splitlines():
            head, visit = line.split("\t")[0].rsplit("_v", 1)
            sample.add((*head.split("_", 1), int(visit)))
        people = {k: v for k, v in people.items() if k[0] != "PAN" or k in sample}
    decisions = {}
    for r in read(decisions_path):
        key = (r["cohort"], r["person"], int(r["visit"]), r["tool"])
        if key[:3] not in people or key[3] not in TOOLS:
            raise SystemExit(f"unexpected row: {key}")
        if key in decisions:
            raise SystemExit(f"repeated row: {key}")
        if r["status"] not in ("ok", "failed"):
            raise SystemExit(f"status is neither ok nor failed: {key}")
        if r["status"] == "ok" and any(r[c] not in ("0", "1") for c in ("pattern", *SENSITIVITY)):
            raise SystemExit(f"a decision is not 0 or 1: {key}")
        decisions[key] = r
    missing = [(*k, t) for k in people for t in TOOLS if (*k, t) not in decisions]
    if missing:
        raise SystemExit(f"{len(missing)} rows are missing, first: {missing[0]}")
    return people, decisions


def proportion(keys, decisions, tool, column="pattern"):
    """Positives, completed, failed, exact interval, three-way reading and bounds for failures."""
    rows = [decisions[(*k, tool)] for k in keys]
    ok = [r for r in rows if r["status"] == "ok"]
    x, n, failed = sum(r[column] == "1" for r in ok), len(ok), len(rows) - len(ok)
    if n == 0:
        return {"x": 0, "n": 0, "failed": failed}
    low, high = s.exact_interval(x, n)
    out = {"x": x, "n": n, "failed": failed, "p": x / n, "low": low, "high": high, "reading": s.reading(x, n)}
    if failed:
        out["all_failed_negative"], out["all_failed_positive"] = s.failure_bounds(x, n, failed)
    return out


def table(keys, decisions, tools=TOOLS):
    """People x tools, only people with every tool completed."""
    rows = [[decisions[(*k, t)] for t in tools] for k in keys]
    complete = [[int(r["pattern"]) for r in row] for row in rows if all(r["status"] == "ok" for r in row)]
    return np.array(complete, int).reshape(-1, len(tools))


def agreement(keys, decisions):
    d = table(keys, decisions)
    if not len(d):
        return {"n": 0}
    split = int(((d.sum(1) > 0) & (d.sum(1) < d.shape[1])).sum())
    out = {"n": len(d), "discordant": split, "p": split / len(d), "interval": s.exact_interval(split, len(d)),
           "kappa": s.fleiss_kappa(d), "kappa_interval": s.bootstrap_interval(d, s.fleiss_kappa, SEED, BOOTSTRAP),
           "positive_tools": dict(sorted(Counter(d.sum(1).tolist()).items()))}
    out["pairs"] = {f"{a} / {b}": s.positive_agreement(d[:, i], d[:, j])
                    for i, a in enumerate(TOOLS) for j, b in enumerate(TOOLS) if i < j}
    return out


def against_primary(keys, decisions):
    out = {}
    for tool in TOOLS[1:]:
        d = table(keys, decisions, (tool, PRIMARY_TOOL))
        out[tool] = {"n": len(d), **(s.paired_difference(d[:, 0], d[:, 1]) if len(d) else {"p": 1.0})}
    for tool, p in zip(out, s.holm([v["p"] for v in out.values()])):
        out[tool]["p_holm"] = float(p)
    return out


def stability(people, decisions):
    both = sorted(k[:2] for k in people if k[2] == 2 and (*k[:2], 1) in people)
    out = {"people": len(both)}
    for tool in TOOLS:
        pairs = [(decisions[(*k, 1, tool)], decisions[(*k, 2, tool)]) for k in both]
        pairs = [(a["pattern"], b["pattern"]) for a, b in pairs if a["status"] == b["status"] == "ok"]
        changed = sum(a != b for a, b in pairs)
        out[tool] = {"n": len(pairs), "changed": changed, "appeared": pairs.count(("0", "1")),
                     "disappeared": pairs.count(("1", "0"))}
        if pairs:
            out[tool]["interval"] = s.exact_interval(changed, len(pairs))
    return out


def analyse(people, decisions):
    first = [k for k in people if k[2] == 1]
    young = [k for k in first if k[0] in PRIMARY_COHORTS and people[k]["age_group"] == "<50"]
    older = [k for k in first if people[k]["age_group"] == ">=50"]
    cohorts = defaultdict(list)
    for k in young + older:
        cohorts[f"{k[0]} {people[k]['age_group']}"].append(k)
    return {
        "primary": proportion(young, decisions, PRIMARY_TOOL),
        "primary_by_cohort": {c: proportion(v, decisions, PRIMARY_TOOL) for c, v in sorted(cohorts.items())},
        "tools_under_50": {t: proportion(young, decisions, t) for t in TOOLS},
        "tools_50_or_more": {t: proportion(older, decisions, t) for t in TOOLS},
        "against_primary_under_50": against_primary(young, decisions),
        "agreement_under_50": agreement(young, decisions),
        "agreement_50_or_more": agreement(older, decisions),
        "stability": stability(people, decisions),
        "sensitivity_under_50": {t: {c: proportion(young, decisions, t, c) for c in SENSITIVITY} for t in TOOLS},
        "counts": {"first_visit": len(first), "under_50": len(young), "50_or_more": len(older),
                   "in_neither": len(first) - len(young) - len(older)},
    }


if __name__ == "__main__":
    results = analyse(*load(sys.argv[1], sys.argv[2], sys.argv[4] if len(sys.argv) > 4 else None))
    with open(sys.argv[3], "w", encoding="utf-8", newline="\n") as f:
        json.dump(results, f, indent=1)
        f.write("\n")
