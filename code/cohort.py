"""Frozen list of people, from file names and participants tables only. No image is downloaded.

Each data set is read at one fixed version of its public OpenNeuro git mirror (file names, without file contents).
Output: cohort_list.csv and cohort_counts.json
"""
import csv
import io
import json
import random
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20261125
DEVELOPMENT_PER_COHORT = 6
# cohort: data set, version, 3D FLAIR file, T1w files in order of preference
COHORTS = {
    "PAN": ("ds007522", "3.0.1", r"_rec-defaced_FLAIR\.nii\.gz$", [r"_rec-defaced_T1w\.nii\.gz$"]),
    "Baycrest": ("ds005270", "1.0.0", r"_FLAIR\.nii\.gz$", [r"_T1w\.nii\.gz$"]),
    "Leipzig": ("ds000221", "1.0.0", r"_acq-highres_FLAIR\.nii\.gz$", [r"_acq-mp2rage_T1w\.nii\.gz$"]),
    "NIMH": ("ds005752", "2.1.0", r"_acq-3dCUBE_rec-SCIC_FLAIR\.nii\.gz$",
             [r"_acq-MPRAGE_rec-SCIC_T1w\.nii\.gz$", r"_acq-SagittalMPRAGE_rec-SCIC_T1w\.nii\.gz$",
              r"_acq-FSPGR_rec-SCIC_T1w\.nii\.gz$"]),
    "GRAND": ("ds007831", "1.0.4", r"_FLAIR\.nii\.gz$", [r"_T1w\.nii\.gz$"]),
}
AGE_COLUMN = {"PAN": "age", "Baycrest": "age", "Leipzig": "age (5-year bins)", "NIMH": "age", "GRAND": "age_mri"}


def git(*arguments):
    return subprocess.run(["git", *arguments], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def read_version(dataset, version, folder):
    """Commit, file names and participants table of one fixed version."""
    place = str(Path(folder) / dataset)
    git("clone", "--quiet", "--bare", "--depth", "1", "--filter=blob:none", "--branch", version,
        f"https://github.com/OpenNeuroDatasets/{dataset}.git", place)
    commit = git("-C", place, "rev-parse", "HEAD").strip()
    names = git("-C", place, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    table = git("-C", place, "show", "HEAD:participants.tsv").lstrip("﻿")
    return commit, names, list(csv.DictReader(io.StringIO(table), delimiter="\t"))


def visit_order(session):
    """ses-01, ses-02 ... before ses-follow01, ses-follow02; one-visit cohorts have no session."""
    number = int(re.sub(r"\D", "", session) or 0)
    return ("follow" in session, number)


def age_group(text):
    """Lower end of the age or age band; None when it is not stated."""
    found = re.match(r"\s*(\d+)", text or "")
    return None if not found else ("<50" if int(found.group(1)) < 50 else ">=50")


def visits(names, flair_pattern, t1_patterns):
    """person -> [(session, flair, t1)] in order, only visits with both images."""
    raw = [n for n in names if re.match(r"sub-[^/]+/", n)]
    by_visit = defaultdict(lambda: {"flair": [], "t1": []})
    for name in raw:
        parts = name.split("/")
        key = (parts[0], parts[1] if parts[1].startswith("ses-") else "")
        if re.search(flair_pattern, name):
            by_visit[key]["flair"].append(name)
        for rank, pattern in enumerate(t1_patterns):
            if re.search(pattern, name):
                by_visit[key]["t1"].append((rank, name))
                break
    people = defaultdict(list)
    for (person, session), found in by_visit.items():
        if found["flair"] and found["t1"]:
            people[person].append((session, min(found["flair"]), min(found["t1"])[1]))
    return {p: sorted(v, key=lambda row: visit_order(row[0])) for p, v in people.items()}


def main(out):
    rows, counts = [], {}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        for cohort, (dataset, version, flair, t1) in COHORTS.items():
            commit, names, table = read_version(dataset, version, folder)
            people = visits(names, flair, t1)
            column = AGE_COLUMN[cohort]
            if column not in table[0]:
                raise SystemExit(f"{cohort}: no column {column!r} in {list(table[0])}")
            age = {}
            for r in table:
                name = r["participant_id"] if r["participant_id"].startswith("sub-") else "sub-" + r["participant_id"]
                age.setdefault(name, r[column])
            development = set(random.Random(f"{SEED}-{cohort}").sample(sorted(people), DEVELOPMENT_PER_COHORT))
            for person in sorted(people):
                for number, (session, flair_file, t1_file) in enumerate(people[person][:2], start=1):
                    rows.append({"cohort": cohort, "dataset": dataset, "version": version, "person": person,
                                 "visit": number, "session": session, "age": age.get(person, ""),
                                 "age_group": age_group(age.get(person)) or "",
                                 "development": int(person in development), "flair": flair_file, "t1": t1_file})
            first = [r for r in rows if r["cohort"] == cohort and r["visit"] == 1]
            counts[cohort] = {"commit": commit, "people": len(people), "table_rows": len(table),
                              "first_visit_age_group": dict(Counter(r["age_group"] or "not stated" for r in first)),
                              "after_development": dict(Counter(r["age_group"] or "not stated" for r in first
                                                                if not r["development"])),
                              "two_visits": sum(len(v) > 1 for v in people.values()),
                              "first_visit_is_first_session": sum(r["session"] in ("", "ses-01") for r in first)}
    with open(Path(out) / "cohort_list.csv", "w", newline="\n", encoding="utf-8") as f:
        writer = csv.DictWriter(f, rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    Path(out, "cohort_counts.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
