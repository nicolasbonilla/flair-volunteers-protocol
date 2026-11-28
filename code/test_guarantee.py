"""Tests of guarantee.py (PROTOCOL_v6 section 16) with artificial data only."""
import numpy as np
import pytest

from guarantee import (LAMBDAS, calibrate, confirmed_pattern, new_marks, p_value, pattern_at, patterns_by_lambda,
                       transfer)

SIDES = (1.0, 1.0, 1.0)


def brain():
    """40^3 grid: a lateral ventricle block (label 4) and a cortex block (label 3) with white matter between."""
    a = np.full((40, 40, 40), 2, np.int32)
    a[10:20, 10:20, 10:20] = 4
    a[10:20, 30:40, 10:20] = 3
    return a


def bar(mask, y0, y1, x=15, z=15):
    mask[z, y0:y1, x] = 1
    return mask


def test_p_value_exact():
    assert p_value(0, 59) == pytest.approx(0.95 ** 59)
    assert p_value(0, 59) < 0.10 and p_value(0, 30) > 0.10


def test_calibrate_fixed_sequence_stops_at_first_failure():
    n = 200
    positives = {3: 40, 4: 30, 5: 20, 6: 9, 7: 5, 8: 3, 10: 2, 12: 1, 15: 0}   # p(Bin(200,.05)<=9)=0.45 fails, <=5 is 0.06 passes
    rows = [{lam: i < positives[lam] for lam in LAMBDAS} for i in range(n)]
    best, steps = calibrate(rows)
    assert best == 7                                     # 5/200 passes, 9/200 fails, the sequence stops there
    assert [s["lambda_mm"] for s in steps] == [15, 12, 10, 8, 7, 6]


def test_calibrate_none_when_even_largest_fails():
    rows = [{lam: i < 20 for lam in LAMBDAS} for i in range(100)]
    assert calibrate(rows)[0] is None


def test_pattern_by_lambda_uses_extent():
    lesion = bar(np.zeros((40, 40, 40), np.uint8), 19, 31)   # touches ventricle (y 19) and cortex (y 30): extent 11.5 mm
    p = patterns_by_lambda(lesion, brain(), SIDES)
    assert p[3] and p[10] and not p[12] and not p[15]


def test_pattern_at_counts_two_regions():
    found = [{"regions": {"PV"}, "extent_mm": 4.0}, {"regions": {"JC"}, "extent_mm": 9.0}]
    assert pattern_at(found, 4) and not pattern_at(found, 5)


def test_confirmed_pattern_needs_votes():
    primary = bar(np.zeros((40, 40, 40), np.uint8), 19, 31)
    other = np.zeros_like(primary); other[15, 25, 15] = 1       # touches the primary lesion by one voxel
    empty = np.zeros_like(primary)
    assert confirmed_pattern(primary, [other, empty], brain(), SIDES, 1)
    assert not confirmed_pattern(primary, [other, empty], brain(), SIDES, 2)


def test_new_marks_ignores_shift_of_one_voxel():
    first = bar(np.zeros((40, 40, 40), np.uint8), 22, 28)
    second = bar(np.zeros_like(first), 22, 28, x=16)            # same lesion moved by one voxel
    second = bar(second, 22, 28, x=30, z=30)                    # and a far one of 6 mm
    assert new_marks(first, second, SIDES) == 1
    assert new_marks(first, second, SIDES, lam=7) == 0


def test_transfer_reports_interval_and_flag():
    rows = [{7: i < 8} for i in range(100)]
    t = transfer(rows, 7)
    assert t["positives"] == 8 and t["above_alpha"] and t["interval"][0] < 0.08 < t["interval"][1]
    assert transfer(rows, None)["lambda_mm"] is None
