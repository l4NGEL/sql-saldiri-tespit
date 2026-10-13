"""Drift ölçütünün saf fonksiyonları (Spark gerektirmez)."""
from __future__ import annotations

import numpy as np
import pytest

from ids.drift import bin_index, interior_edges, level, psi


def test_psi_identical_is_zero():
    assert psi([10, 20, 30], [1, 2, 3]) == pytest.approx(0.0)


def test_psi_known_value():
    # p = (0,5, 0,5), q = (0,9, 0,1): 0,4·ln(1,8) + (-0,4)·ln(0,2)
    expected = 0.4 * np.log(1.8) - 0.4 * np.log(0.2)
    assert psi([50, 50], [90, 10]) == pytest.approx(expected)


def test_psi_symmetric_and_empty_bin_smoothed():
    assert psi([50, 50], [90, 10]) == pytest.approx(psi([90, 10], [50, 50]))
    v = psi([100, 0], [50, 50])  # boş bölme eps ile yumuşatılır, sonsuz olmaz
    assert np.isfinite(v) and v > 1


def test_psi_empty_side_is_nan():
    assert np.isnan(psi([0, 0], [1, 2]))


def test_interior_edges_collapse_for_discrete_and_constant():
    assert interior_edges([0, 0, 0, 0, 1, 1]) == [1.0]
    assert interior_edges([5, 5, 5]) == []
    assert interior_edges([None, 1, 2, float("nan"), 3]) == [2.0, 3.0]


def test_bin_index_rule_and_nulls():
    edges = [1.0, 2.0]
    got = bin_index(np.array([0.5, 1.0, 1.5, 2.0, 9.0, np.nan]), edges)
    assert got.tolist() == [0, 1, 1, 2, 2, -1]
    assert bin_index(np.array([3.0, np.nan]), []).tolist() == [0, -1]


def test_level_thresholds():
    assert level(0.05) == "kararlı"
    assert level(0.2) == "orta"
    assert level(0.3) == "belirgin"
