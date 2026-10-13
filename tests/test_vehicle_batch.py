"""实际资产的合批不能烘入动态枢轴，后续车身/转向/轮转仍共用原坐标。"""

import pytest
from panda3d.core import NodePath

from skins import apply_skin, vehicle_definition
from vehicle_visual import batch_driving_geometry, load_vehicle


@pytest.mark.parametrize('model', ['sports', 'gr86-2022', 'traffic-compact', 'traffic-sedan', 'traffic-wagon'])
def test_batch_preserves_bounds_after_each_body_and_wheel_pose_change(model):
    parent = NodePath('driving-view')
    root, wheels = load_vehicle(parent, vehicle_definition(model))
    apply_skin(root.getChild(0), 2)

    def poses():
        bounds = []
        for step in range(3):
            root.setPosHpr(3*step, 10+step, .7, 20*step, 2*step, -step)
            for i, wheel in enumerate(wheels):
                wheel.setPosHpr(i-2+step, 10+i+step, .4+.1*step,
                                15*step, 70*step, -3*step)
            bounds.append([tuple(tuple(point) for point in part.getTightBounds(parent))
                           for part in (root, *wheels)])
        return bounds

    try:
        before = poses()
        batch_driving_geometry(root, wheels)
        after = poses()
        for old_pose, new_pose in zip(before, after):
            for old_part, new_part in zip(old_pose, new_pose):
                for old_corner, new_corner in zip(old_part, new_part):
                    assert new_corner == pytest.approx(old_corner, abs=2e-5)
    finally:
        parent.removeNode()
