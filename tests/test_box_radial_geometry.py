"""独立圆几何与全空间支持平面核对，未证明的构型不得使用剖面近似。"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from box_radial_geometry import box_section, wheel_support
from vehicle_designs import REFERENCE_DESIGN


@pytest.mark.parametrize("y",[-1.,-.55,-.49,0.,.49,.55,1.])
def test_circle_section_matches_independent_box_edge_distance(y):
    center,half = np.array((0.,y,.315)),np.array((.24,.45,.005))
    result = box_section(center,np.array((1.,0.,0.)),half,REFERENCE_DESIGN)
    assert result is not None
    expected = math.hypot(max(abs(y)-.45,0.),.315-.005)-.33
    assert result[0]==pytest.approx(expected,abs=2e-13)
    assert result[2]-result[3]==pytest.approx(result[0]*result[1],abs=2e-13)


def test_tilted_failed_query_has_real_witnesses_and_dominates_full_sphere_support_planes():
    path = Path(__file__).resolve().parents[1]/"docs/evidence/SIM-UNSPRUNG-01/ride-braking/failed-query.json"
    data = json.loads(path.read_text())
    center,axis = np.asarray(data["center"]),np.asarray(data["axis"])
    half = np.max(np.abs(data["vertices"]),axis=0)
    distance,normal,wheel,road,_plane = box_section(center,axis,half,REFERENCE_DESIGN)
    assert np.max(np.abs(road)-half)<2e-13
    assert wheel-road==pytest.approx(distance*normal,abs=2e-13)
    assert np.dot(normal,road)==pytest.approx(np.dot(half,np.abs(normal)),abs=2e-13)
    # 另一种离散的全空间方向覆盖检验，不复制待测算法的法线锥二分。
    for z in np.linspace(-.999,.999,31):
        for angle in np.linspace(0,2*math.pi,61):
            n = np.array((math.sqrt(1-z*z)*math.cos(angle),math.sqrt(1-z*z)*math.sin(angle),z))
            gap = np.dot(n,center+wheel_support(n,axis,REFERENCE_DESIGN))-np.dot(half,np.abs(n))
            assert gap<=distance+2e-13


def test_section_refuses_box_without_a_containing_axis():
    assert box_section(np.array((0.,0.,.315)),np.array((1.,0.,0.)),(.03,.03,.03),REFERENCE_DESIGN) is None
