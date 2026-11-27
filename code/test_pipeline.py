"""Image reading, cohort rules and the whole analysis, with artificial data only."""
import csv
import json

import nibabel as nib
import numpy as np
import pytest

import analyse as a
import cohort
import decide_person as d
import phantom
import regions

EYE = np.eye(4)


def image(data, affine=EYE, kind=np.int16):
    return nib.Nifti1Image(np.asarray(data).astype(kind), affine)


MOVED = np.eye(4)
MOVED[0, 3] = 7
FLAIR, ANATOMY = image(np.zeros(phantom.SHAPE)), image(phantom.anatomy())


# ---------- images ----------
@pytest.mark.parametrize("sites", [(), ("PV",), ("PV", "JC"), ("JC", "IT"), ("DEEP",)])
def test_image_path_equals_array_path(sites):
    mask = phantom.lesions(sites)
    assert d.person(FLAIR, ANATOMY, image(mask), "FLAMeS") == regions.decide(mask, phantom.anatomy(), (1, 1, 1))


def test_registration_matrix_is_applied():
    """T1 displaced 7 mm: right with its matrix, different without it."""
    moved = np.eye(4)
    moved[0, 3] = 7
    anatomy = image(phantom.anatomy(), moved)
    mask = image(phantom.lesions(("PV", "JC")))
    right = d.person(FLAIR, anatomy, mask, "FLAMeS", matrix=moved)
    assert right["pattern"] and right["PV"] and right["JC"]
    assert d.person(FLAIR, anatomy, mask, "FLAMeS") != right


def test_samseg_mask_comes_back_from_the_t1_grid():
    """SAMSEG writes on T1w, even when T1w and FLAIR share the same array size and affine."""
    for matrix, affine in ((np.eye(4), np.eye(4)), (MOVED, np.eye(4)), (MOVED, MOVED)):
        t1 = image(np.zeros(phantom.SHAPE), affine)
        mask = image(phantom.lesions(("PV", "JC")) * 99)
        on_t1 = image(d.on_grid(mask, t1, np.linalg.inv(matrix)), affine)
        got = d.person(FLAIR, image(d.on_grid(ANATOMY, t1, np.linalg.inv(matrix)), affine), on_t1, "SAMSEG", matrix)
        assert got["pattern"] and got["components"] == 2


def test_wmh_synthseg_mask_does_not_use_the_matrix():
    shifted = np.eye(4)
    shifted[0, 3] = -1
    data = np.zeros((phantom.SHAPE[0] + 1, *phantom.SHAPE[1:]))
    data[1:] = phantom.lesions(("PV", "JC")) * 77
    got = d.person(FLAIR, image(phantom.anatomy(), MOVED), image(data, shifted), "WMH-SynthSeg", MOVED)
    assert got["PV"] and got["JC"]


def test_other_tools_must_write_on_the_flair_grid():
    for tool in ("FLAMeS", "LST-AI", "MindGlide"):
        with pytest.raises(ValueError):
            d.person(FLAIR, ANATOMY, image(np.zeros((90, 96, 80))), tool)


@pytest.mark.parametrize("flip", [0, 1, 2])
def test_stored_orientation_does_not_matter(flip):
    """The same T1 stored in another direction gives the same answer."""
    affine = np.eye(4)
    affine[flip, flip] = -1
    affine[flip, 3] = phantom.SHAPE[flip] - 1
    anatomy = image(np.flip(phantom.anatomy(), flip), affine)
    mask = image(phantom.lesions(("PV", "JC")))
    assert d.person(FLAIR, anatomy, mask, "FLAMeS") == d.person(FLAIR, ANATOMY, mask, "FLAMeS")


def test_each_tool_uses_its_own_label():
    body = phantom.lesions(("PV", "JC")).astype(int)
    for tool, label in d.LESION_LABEL.items():
        data = body * label
        if tool not in ("FLAMeS", "LST-AI"):
            data[0, 0, 0] = 2                       # another structure of the same output
        assert d.person(FLAIR, ANATOMY, image(data), tool)["components"] == 2, tool


def test_output_on_another_grid():
    """WMH-SynthSeg writes its own 1 mm grid."""
    shifted = np.eye(4)
    shifted[:3, 3] = (-3, -2, -1)
    big = np.zeros(tuple(np.array(phantom.SHAPE) + 6))
    big[3:83, 2:98, 1:81] = phantom.lesions(("PV", "IT")) * 77
    got = d.person(FLAIR, ANATOMY, image(big, shifted), "WMH-SynthSeg")
    assert got["pattern"] and got["PV"] and got["IT"] and not got["JC"]


@pytest.mark.parametrize("flair,anatomy,lesions,tool", [
    (FLAIR, image(np.zeros(phantom.SHAPE)), image(phantom.lesions(())), "FLAMeS"),          # empty anatomy
    (FLAIR, image(np.where(phantom.anatomy() == 42, 3, phantom.anatomy())), image(phantom.lesions(())), "FLAMeS"),
    (FLAIR, image(np.where(phantom.anatomy() == 4, 2, phantom.anatomy())), image(phantom.lesions(())), "FLAMeS"),
    (FLAIR, ANATOMY, image(phantom.lesions(("PV",)) * 2), "FLAMeS"),                          # not binary
    (FLAIR, ANATOMY, image(np.full(phantom.SHAPE, np.nan), kind=np.float32), "MindGlide"),
    (FLAIR, ANATOMY, image(np.zeros((*phantom.SHAPE, 2))), "FLAMeS"),
])
def test_problems_are_errors_not_negatives(flair, anatomy, lesions, tool):
    with pytest.raises(ValueError):
        d.person(flair, anatomy, lesions, tool)


# ---------- cohort ----------
def test_visits_need_both_images_and_keep_order():
    names = ["sub-1/ses-follow01/anat/x_rec-defaced_FLAIR.nii.gz", "sub-1/ses-follow01/anat/x_rec-defaced_T1w.nii.gz",
             "sub-1/ses-02/anat/x_rec-defaced_FLAIR.nii.gz", "sub-1/ses-02/anat/x_rec-defaced_T1w.nii.gz",
             "sub-2/ses-01/anat/x_rec-defaced_FLAIR.nii.gz", "derivatives/sub-3/ses-01/x_rec-defaced_FLAIR.nii.gz"]
    got = cohort.visits(names, cohort.COHORTS["PAN"][2], cohort.COHORTS["PAN"][3])
    assert list(got) == ["sub-1"] and [v[0] for v in got["sub-1"]] == ["ses-02", "ses-follow01"]


def test_t1_preference():
    base = "sub-1/ses-01/anat/x"
    names = [base + "_acq-3dCUBE_rec-SCIC_FLAIR.nii.gz", base + "_acq-FSPGR_rec-SCIC_T1w.nii.gz",
             base + "_acq-MPRAGE_rec-SCIC_T1w.nii.gz", base + "_acq-forMEGCoregistration_T1w.nii.gz"]
    got = cohort.visits(names, cohort.COHORTS["NIMH"][2], cohort.COHORTS["NIMH"][3])
    assert got["sub-1"][0][2].endswith("_acq-MPRAGE_rec-SCIC_T1w.nii.gz")


@pytest.mark.parametrize("text,group", [("49", "<50"), ("50", ">=50"), ("45-50", "<50"), ("50-55", ">=50"),
                                        ("49.9", "<50"), ("n/a", None), ("", None), (None, None)])
def test_age_group(text, group):
    assert cohort.age_group(text) == group


# ---------- analysis ----------
def fake(tmp_path, change=lambda rows: rows):
    """90 people with known answers: every count below can be checked by hand."""
    people, rows = [], []
    for i in range(90):
        name = ("Baycrest", "Leipzig", "PAN")[i // 30]
        group = ">=50" if name == "PAN" or i % 30 >= 20 else "<50"
        for visit in ((1, 2) if name == "PAN" and i % 30 < 10 else (1,)):
            people.append({"cohort": name, "person": f"sub-{i}", "visit": visit, "age_group": group, "development": 0})
            for tool in a.TOOLS:
                positive = int(i % 10 < {"FLAMeS": 2, "LST-AI": 3, "MindGlide": 2, "WMH-SynthSeg": 0, "SAMSEG": 2}[tool])
                if visit == 2 and tool == "FLAMeS" and i % 30 == 0:
                    positive = 0
                rows.append({"cohort": name, "person": f"sub-{i}", "visit": visit, "tool": tool, "status": "ok",
                             "pattern": positive, **{c: positive for c in a.SENSITIVITY}})
    people.append({"cohort": "NIMH", "person": "sub-dev", "visit": 1, "age_group": "<50", "development": 1})
    rows = change(rows)
    for name, content in (("list.csv", people), ("decisions.csv", rows)):
        with open(tmp_path / name, "w", newline="") as f:
            w = csv.DictWriter(f, content[0])
            w.writeheader()
            w.writerows(content)
    return a.load(tmp_path / "list.csv", tmp_path / "decisions.csv")


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(a, "BOOTSTRAP", 200)


def test_known_answers(tmp_path):
    r = a.analyse(*fake(tmp_path))
    assert (r["primary"]["x"], r["primary"]["n"], r["primary"]["failed"]) == (8, 40, 0)
    assert r["counts"] == {"first_visit": 90, "under_50": 40, "50_or_more": 50, "in_neither": 0}
    assert {t: v["x"] for t, v in r["tools_under_50"].items()} == dict(zip(a.TOOLS, (8, 12, 8, 0, 8)))
    assert r["agreement_under_50"]["discordant"] == 12 and r["agreement_under_50"]["n"] == 40
    assert r["agreement_under_50"]["positive_tools"] == {0: 28, 1: 4, 4: 8}
    assert r["against_primary_under_50"]["LST-AI"]["only_a"] == 4
    assert r["against_primary_under_50"]["LST-AI"]["difference"] == pytest.approx(0.1)
    assert r["against_primary_under_50"]["WMH-SynthSeg"]["difference"] == pytest.approx(-0.2)
    assert r["stability"]["people"] == 10
    assert (r["stability"]["FLAMeS"]["changed"], r["stability"]["FLAMeS"]["disappeared"]) == (1, 1)
    assert r["stability"]["SAMSEG"]["changed"] == 0
    assert "PAN <50" not in r["primary_by_cohort"]
    json.dumps(r)


def test_unanimous_people_are_not_discordant(tmp_path):
    def agree(rows):
        for row in rows:
            if row["person"] == "sub-0":
                row.update(pattern=1)
        return rows
    g = a.analyse(*fake(tmp_path, agree))["agreement_under_50"]
    assert g["positive_tools"][5] == 1 and g["discordant"] == 11


def test_pan_person_under_50_is_in_neither_group(tmp_path):
    people, decisions = fake(tmp_path)
    key = next(k for k in people if k[0] == "PAN" and k[2] == 1)
    people[key]["age_group"] = "<50"
    r = a.analyse(people, decisions)
    assert r["counts"] == {"first_visit": 90, "under_50": 40, "50_or_more": 49, "in_neither": 1}


def test_failures_stay_visible(tmp_path):
    def fail(rows):
        for row in rows:
            if row["tool"] == "FLAMeS" and row["person"] in ("sub-0", "sub-5"):
                row.update(status="failed", pattern="", **{c: "" for c in a.SENSITIVITY})
        return rows
    p = a.analyse(*fake(tmp_path, fail))["primary"]
    assert (p["x"], p["n"], p["failed"]) == (7, 38, 2)
    assert p["all_failed_negative"][0] == 7 / 40 and p["all_failed_positive"][0] == 9 / 40


@pytest.mark.parametrize("change", [
    lambda rows: rows[1:],
    lambda rows: rows + rows[:1],
    lambda rows: [{**rows[0], "tool": "Other"}] + rows[1:],
    lambda rows: [{**rows[0], "status": ""}] + rows[1:],
    lambda rows: [{**rows[0], "pattern": ""}] + rows[1:],
    lambda rows: rows + [{**rows[0], "cohort": "NIMH", "person": "sub-dev"}],
])
def test_incomplete_or_unexpected_input_stops(tmp_path, change):
    with pytest.raises(SystemExit):
        fake(tmp_path, change)


def test_pan_sample_only_expects_the_sampled_scans(tmp_path):
    people, decisions = fake(tmp_path)
    pan = sorted(k for k in people if k[0] == "PAN")
    keep = pan[:7]
    (tmp_path / "pan.tsv").write_text("".join(f"PAN_{p}_v{v}\turl\turl\tsha256:x\tsha256:x\n" for _, p, v in keep))
    rows = list(csv.DictReader(open(tmp_path / "decisions.csv")))
    with open(tmp_path / "decisions.csv", "w", newline="") as f:          # the other PAN scans were never processed
        w = csv.DictWriter(f, rows[0])
        w.writeheader()
        w.writerows(r for r in rows if r["cohort"] != "PAN" or (r["cohort"], r["person"], int(r["visit"])) in keep)
    people2, _ = a.load(tmp_path / "list.csv", tmp_path / "decisions.csv", tmp_path / "pan.tsv")
    assert sorted(k for k in people2 if k[0] == "PAN") == keep
    with pytest.raises(SystemExit):                                     # without the sample, the missing PAN rows stop it
        a.load(tmp_path / "list.csv", tmp_path / "decisions.csv")


def test_collate_rows_to_decisions(tmp_path, capsys):
    import collate
    rows = tmp_path / "rows"
    rows.mkdir()
    ok = {"status": "ok", "pattern": 1, "PV": 1, "JC": 0, "IT": 1, "registration": {"passed": True, "ventricle_to_white_matter": 0.3}}
    (rows / "Baycrest_sub-01_v1.jsonl").write_text("".join(
        json.dumps({"scan": "Baycrest_sub-01_v1", "tool": t, **ok}) + "\n" for t in collate.TOOLS))
    (rows / "PAN_sub-HML0002_v2.jsonl").write_text("".join(
        json.dumps({"scan": "PAN_sub-HML0002_v2", "tool": t, "status": "failed", "error": "download failed"}) + "\n"
        for t in collate.TOOLS))
    (tmp_path / "w.tsv").write_text("Baycrest_sub-01_v1\ta\tb\tc\td\nPAN_sub-HML0002_v2\ta\tb\tc\td\n")
    collate.main(rows, [tmp_path / "w.tsv"])
    out = list(csv.DictReader(capsys.readouterr().out.splitlines()))
    assert len(out) == 10
    assert out[0]["cohort"] == "Baycrest" and out[0]["person"] == "sub-01" and out[0]["visit"] == "1"
    assert out[0]["ventricle_to_white_matter"] == "0.3" and out[0]["pattern"] == "1"
    assert out[5]["person"] == "sub-HML0002" and out[5]["visit"] == "2" and out[5]["status"] == "failed"
    (tmp_path / "w2.tsv").write_text("Leipzig_sub-9_v1\ta\tb\tc\td\n")
    with pytest.raises(SystemExit):                                     # a scan without rows: the run is not finished
        collate.main(rows, [tmp_path / "w2.tsv"])
    (rows / "Leipzig_sub-9_v1.jsonl").write_text(json.dumps({"scan": "Leipzig_sub-9_v1", "tool": "FLAMeS", **ok}) + "\n")
    with pytest.raises(SystemExit):                                     # one tool only
        collate.main(rows, [tmp_path / "w2.tsv"])
