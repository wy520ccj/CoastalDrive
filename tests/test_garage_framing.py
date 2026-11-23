"""用实际网格检查展示取景，不创建窗口或第二个物理世界。"""

from types import SimpleNamespace

import numpy as np
import pytest
from panda3d.core import Camera, NodePath, PerspectiveLens, Point2, Point3

from career_garage import GARAGE_CARS
from skins import vehicle_for_design
from ui.garage_framing import mesh_vertices, project_vertices
from ui.workshop_vehicle import WorkshopVehicle
from vehicle_designs import vehicle_design
from vehicle_visual import load_vehicle


@pytest.mark.parametrize('design_id', [car.design_id for car in GARAGE_CARS])
def test_actual_cars_fit_garage_and_short_result_viewports(design_id, monkeypatch):
    projections = []

    def record_projection(*args):
        projections.append(1)
        return project_vertices(*args)

    monkeypatch.setattr('ui.workshop_vehicle.project_vertices', record_projection)
    scene = NodePath('framing-contract')
    root = scene.attachNewNode('car')
    config = vehicle_design(design_id).config
    load_vehicle(root, vehicle_for_design(design_id, 'sports'), config=config)
    root.setZ(config.center_of_mass_height)
    lens = PerspectiveLens()
    lens.setFov(46)
    lens.setNearFar(.1, 80)
    camera = scene.attachNewNode(Camera('framing-camera', lens))
    vertices = mesh_vertices(root, scene)
    view = SimpleNamespace(car_root=root, scene=scene, camera=camera,
                           framing_vertices=vertices, studio_angle=55.,
                           framing_cache={}, highlight_topic=None)
    try:
        for aspect in (1.3, 1.6, 2.17):
            lens.setAspectRatio(aspect)
            for angle in (55., 145., 235., 325.):
                WorkshopVehicle.orbit(view, angle-view.studio_angle)
                projected = project_vertices(vertices, scene, camera)
                assert projected is not None
                assert (abs(projected[:, 0]) <= .901).all()
                assert (abs(projected[:, 1]) <= .831).all()
                # 矩阵批量计算与Panda原生镜头坐标一致，包含film offset。
                for index in (0, len(vertices)//2, len(vertices)-1):
                    point = Point2()
                    assert lens.project(camera.getRelativePoint(scene, Point3(*vertices[index, :3])), point)
                    np.testing.assert_allclose(projected[index], tuple(point), atol=2e-6)
                if design_id == 'game-tuned' and aspect == 2.17 and angle == 55.:
                    # 旧35度/包围盒算法在同一短视口仅占56%宽，保留可感知的改善。
                    assert np.ptp(projected[:, 0])/2 > .70
                transform, offset = camera.getTransform(scene), tuple(lens.getFilmOffset())
                count = len(projections)
                camera.setPos(1, 2, 3)
                lens.setFilmOffset(.2, .3)
                WorkshopVehicle.orbit(view, 0)
                assert len(projections) == count
                assert camera.getTransform(scene) == transform
                assert tuple(lens.getFilmOffset()) == offset
    finally:
        scene.removeNode()
