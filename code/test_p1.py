"""Tests with artificial data only. Run: python -m pytest -q"""
import itertools

import numpy as np
import pytest
from scipy.stats import binom
from statsmodels.stats.inter_rater import fleiss_kappa as sm_kappa
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

import phantom
import regions as r
import statistics_p1 as s

ANATOMY = phantom.anatomy()
MM = (1.0, 1.0, 1.0)


# ---------- decision ----------
@pytest.mark.parametrize("n", range(5))
def test_every_combination_of_sites(n):
    """2 of the 3 regions give the pattern; deep lesions never count."""
    for sites in itertools.combinations(("PV", "JC", "IT", "DEEP"), n):
        got = r.decide(phantom.lesions(sites), ANATOMY, MM)
        wanted = set(sites) - {"DEEP"}
        assert {k for k in r.REGIONS if got[k]} == wanted, sites
        assert got["pattern"] is (len(wanted) >= 2), sites


def test_small_lesions_do_not_count():
    got = r.decide(phantom.lesions(("PV", "JC", "IT"), radius_mm=0.5), ANATOMY, MM)
    assert got["components"] == 3 and got["components_3mm"] == 0
    assert got["pattern"] is False and got["pattern_any_size"] is True


def test_empty_mask():
    got = r.decide(np.zeros(phantom.SHAPE), ANATOMY, MM)
    assert got["pattern"] is False and got["components"] == 0 and got["volume_ml"] == 0


def test_one_component_in_two_regions():
    """A bridge from ventricle to cortex counts in the primary rule, not when two components are required."""
    mask = np.zeros(phantom.SHAPE, bool)
    mask[13:31, 48, 50] = True
    got = r.decide(mask, ANATOMY, MM)
    assert got["components"] == 1 and got["PV"] and got["JC"]
    assert got["pattern"] is True and got["pattern_separate"] is False


def test_separate_needs_two_components_overall():
    both, one = {"PV", "JC"}, {"PV"}
    mk = lambda reg: {"extent_mm": 5, "volume_mm3": 50, "regions": reg}
    assert r.pattern([mk(both), mk(one)], separate=True)
    assert not r.pattern([mk(both)], separate=True)
    assert not r.pattern([mk(one), mk(one)], separate=True)


def test_mirror_image_gives_the_same_answer():
    for sites in (("PV", "JC"), ("PV",), ("JC", "IT")):
        m = phantom.lesions(sites)
        a, b = r.decide(m, ANATOMY, MM), r.decide(m[::-1], ANATOMY[::-1], MM)
        assert {k: a[k] for k in r.REGIONS + ("pattern",)} == {k: b[k] for k in r.REGIONS + ("pattern",)}


@pytest.mark.parametrize("label,region", [(4, "PV"), (5, "PV"), (43, "PV"), (44, "PV"), (3, "JC"), (42, "JC"),
                                          (7, "IT"), (8, "IT"), (16, "IT"), (46, "IT"), (47, "IT"),
                                          (2, None), (41, None), (14, None), (15, None), (0, None)])
def test_each_anatomical_label(label, region):
    """Both hemispheres, one label at a time. Third and fourth ventricles do not count."""
    lab = np.full((15, 15, 15), 2, np.int16)
    lab[5:10, 5:10, 5:10] = label
    mask = np.zeros(lab.shape, bool)
    mask[5:10, 7, 7] = True
    assert r.components(mask, lab, MM)[0]["regions"] == ({region} if region else set())


def test_size_limits_are_exact():
    mk = lambda extent, volume: {"extent_mm": extent, "half_voxel_mm": 0.5, "volume_mm3": volume}
    assert r.large_enough(mk(3.0, 0)) and not r.large_enough(mk(2.99, 99))
    assert r.large_enough(mk(2.5, 0), "generous") and not r.large_enough(mk(2.49, 99), "generous")
    assert r.large_enough(mk(0, 14.1), "volume") and not r.large_enough(mk(9, 14.0), "volume")


def test_axis_order_does_not_matter():
    m = phantom.lesions(("PV", "IT"))
    a = r.decide(m, ANATOMY, MM)
    for axes in itertools.permutations(range(3)):
        b = r.decide(m.transpose(axes), ANATOMY.transpose(axes), MM)
        assert a["pattern"] == b["pattern"] and a["components_3mm"] == b["components_3mm"]


def test_touching_by_a_corner_counts_and_a_gap_does_not():
    lab = np.full((20, 20, 20), 2, np.int16)
    lab[5, 5, 5] = 4
    touching, gap = np.zeros(lab.shape, bool), np.zeros(lab.shape, bool)
    touching[6:10, 6, 6] = True
    gap[7:11, 7, 7] = True
    assert r.components(touching, lab, MM)[0]["regions"] == {"PV"}
    assert r.components(gap, lab, MM)[0]["regions"] == set()
    assert r.components(gap, lab, MM, gap_voxels=1)[0]["regions"] == {"PV"}


def test_infratentorial_majority():
    lab = np.full((20, 20, 20), 2, np.int16)
    lab[:, :, :10] = 16
    for low, expected in ((6, {"IT"}), (8, {"IT"}), (9, set())):
        m = np.zeros(lab.shape, bool)
        m[10, 10, low:low + 4] = True
        assert r.components(m, lab, MM)[0]["regions"] == expected


def test_infratentorial_lesion_near_temporal_horn_is_not_periventricular():
    lab = np.full((20, 20, 20), 16, np.int16)
    lab[5, 5, 5] = 5
    m = np.zeros(lab.shape, bool)
    m[6:10, 5, 5] = True
    assert r.components(m, lab, MM)[0]["regions"] == {"IT"}


# ---------- size ----------
@pytest.mark.parametrize("voxels,expected", [(1, 0.5), (2, 1.5), (3, 2.5), (4, 3.5)])
def test_extent_of_a_line(voxels, expected):
    assert r.extent_mm(np.array([[i, 0, 0] for i in range(voxels)]), MM) == pytest.approx(expected)


def test_extent_uses_the_real_voxel_size():
    line = np.array([[0, 0, i] for i in range(3)])
    assert r.extent_mm(line, (1.2, 1.2, 1.2)) == pytest.approx(3.0)
    assert r.extent_mm(line, (1.0, 1.0, 1.0)) == pytest.approx(2.5)


def test_extent_is_nearly_unbiased_for_balls():
    """Average over 40 random positions: within 0.5 mm of the true diameter at 1.0 and 1.2 mm voxels."""
    rng = np.random.default_rng(1)
    for side in (1.0, 1.2):
        for diameter in (3.0, 5.0, 8.0):
            got = []
            for _ in range(40):
                c = 12 + rng.random(3)
                got.append(r.extent_mm(np.argwhere(phantom.ball(c, diameter / 2, (side,) * 3, (25,) * 3)), (side,) * 3))
            assert abs(np.mean(got) - diameter) < 0.5, (side, diameter, np.mean(got))


def test_lesions_clearly_below_3mm_are_not_counted():
    rng = np.random.default_rng(5)
    for side in (1.0, 1.2):
        for diameter in (1.0, 1.5, 2.0, 2.5):
            for _ in range(60):
                v = np.argwhere(phantom.ball(12 + rng.random(3), diameter / 2, (side,) * 3, (25,) * 3))
                if len(v):
                    assert r.extent_mm(v, (side,) * 3) < 3 + 0.1, (side, diameter)


def test_size_rules_are_ordered():
    """generous keeps everything the primary rule keeps; any keeps everything."""
    for n in (1, 2, 3, 4, 6):
        c = r.components(phantom.ball((10, 10, 10), n / 2, shape=(20,) * 3), np.full((20,) * 3, 2), MM)[0]
        kept = [r.large_enough(c, rule) for rule in ("extent", "generous", "any")]
        assert kept == sorted(kept)
    with pytest.raises(ValueError):
        r.large_enough(c, "other")


def test_hull_shortcut_equals_brute_force():
    from scipy.spatial.distance import pdist
    rng = np.random.default_rng(2)
    for _ in range(50):
        v = np.unique(rng.integers(0, 12, (200, 3)), axis=0)
        side = tuple(rng.uniform(0.5, 2, 3))
        assert r.extent_mm(v, side) == pytest.approx(pdist(v * np.array(side)).max() + np.prod(side) ** (1 / 3) / 2)


def test_flat_component_does_not_fail():
    v = np.array([[0, i, j] for i in range(12) for j in range(12)])
    assert r.extent_mm(v, MM) == pytest.approx(np.hypot(11, 11) + 0.5)


@pytest.mark.parametrize("bad", [np.zeros((5, 5)), np.zeros((5, 5, 6))])
def test_different_grids_are_refused(bad):
    with pytest.raises(ValueError):
        r.components(bad, np.zeros((5, 5, 5)), MM)


# ---------- statistics against independent implementations ----------
def test_exact_interval_against_statsmodels():
    for n in (1, 10, 82, 271):
        for x in range(0, n + 1, max(1, n // 10)):
            assert s.exact_interval(x, n) == pytest.approx(proportion_confint(x, n, method="beta"), abs=1e-9)


def test_reference_figures_of_the_protocol():
    assert [round(100 * v, 1) for v in s.exact_interval(3, 82)] == [0.8, 10.3]
    assert [round(100 * v, 1) for v in s.exact_interval(4, 82)] == [1.3, 12.0]


def test_three_readings():
    assert s.reading(5, 271) == "below the margin"
    assert s.reading(32, 271) == "inconclusive"
    assert s.reading(80, 271) == "above the margin"
    # the limits decide, not the point estimate; limits by n=250 as in design_table.py
    assert [s.reading(x, 250) for x in (19, 20, 40, 41)] == ["below the margin", "inconclusive", "inconclusive",
                                                             "above the margin"]


def test_failures_are_kept():
    low, high = s.failure_bounds(20, 100, 5)
    assert low[0] == 20 / 105 and high[0] == 25 / 105


def test_holm_against_statsmodels():
    p = [0.03, 0.001, 0.2, 0.012]
    assert s.holm(p) == pytest.approx(multipletests(p, method="holm")[1])


def test_fleiss_against_statsmodels():
    d = (np.random.default_rng(3).random((200, 5)) < 0.3).astype(int)
    counts = np.c_[5 - d.sum(1), d.sum(1)]
    assert s.fleiss_kappa(d) == pytest.approx(sm_kappa(counts))
    assert np.isnan(s.fleiss_kappa(np.zeros((10, 5))))


def test_paired_difference():
    a, b = np.r_[np.ones(30), np.zeros(70)], np.r_[np.ones(10), np.zeros(90)]
    got = s.paired_difference(a, b)
    assert (got["difference"], got["only_a"], got["only_b"]) == (0.2, 20, 0)
    assert got["low"] > 0 and got["p"] == pytest.approx(2 * 0.5 ** 20)
    swapped = s.paired_difference(b, a)
    assert swapped["low"] == pytest.approx(-got["high"]) and s.paired_difference(a, a)["p"] == 1


def test_positive_agreement():
    assert s.positive_agreement([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(2 / 3)
    assert np.isnan(s.positive_agreement([0, 0], [0, 0]))


def test_bootstrap_is_repeatable():
    d = (np.random.default_rng(4).random((80, 5)) < 0.4).astype(int)
    assert s.bootstrap_interval(d, s.fleiss_kappa, 7, 300) == s.bootstrap_interval(d, s.fleiss_kappa, 7, 300)


def test_pooled_interval_keeps_its_promise_with_unequal_cohorts():
    """Exact calculation, no simulation: coverage of the pooled interval is at least 95%."""
    sizes = (74, 80, 72, 20)
    for probs in ((0.1,) * 4, (0.02, 0.1, 0.2, 0.3), (0, 0.05, 0.4, 0.9), (0.5, 0.1, 0.01, 0.2)):
        dist = np.ones(1)
        for n, p in zip(sizes, probs):
            dist = np.convolve(dist, binom.pmf(np.arange(n + 1), n, p))
        N, truth = sum(sizes), np.dot(sizes, probs) / sum(sizes)
        inside = [lo <= truth <= hi for lo, hi in (s.exact_interval(x, N) for x in range(N + 1))]
        assert dist[np.array(inside)].sum() >= 0.95, probs
