"""Bullet ray/support checks for the curved highway display mesh."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from curve_surface_check import run


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("hills", [False, True])
def test_curve_mesh_support(seed, hills):
    result = run(seed, hills)
    assert result["max_error_m"] <= 0.015
    assert result["max_marking_error_m"] <= 0.015
    assert result["max_join_gap_m"] <= 1e-8
    assert result["join_comparisons"] > 0
    assert result["min_tree_clearance_m"] >= 20.0
