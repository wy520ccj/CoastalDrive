"""项目深度审查修复回归测试：覆盖物理恢复、UI 焦点/排版、着色器雾化与几何法向。"""

from collections import deque
from types import SimpleNamespace

import pytest
import test_expressway
from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import BitMask32, GeomVertexReader, NodePath, Shader, Vec3

from career_courses import CareerCourse
from environment.expressway_city import city_steps
from environment.expressway_materials import city_asphalt_shader
from environment.expressway_mountains import mountain_point
from environment.expressway_route import anchor, landscape_steps
from highway_curve import HighwayCurve
from physics_workers import PhysicsWorkers
from world_step import advance_world

kit = test_expressway.kit


def test_world_step_recovery_drains_workers_and_recovers_all_uncommitted_vehicles():
    drained = []
    recovered = []

    class FakeChassis:
        def __init__(self):
            self.cleared = 0

        def getTransform(self):
            return SimpleNamespace(getPos=lambda: Vec3(0, 0, 0))

        def getLinearVelocity(self):
            return Vec3(0, 10, 0)

        def getTotalForce(self):
            return Vec3(0, 0, 0)

        def getTotalTorque(self):
            return Vec3(0, 0, 0)

        def clearForces(self):
            self.cleared += 1

    class FakeCar:
        coupled_suspension = True
        _native_action = False

        def __init__(self, name):
            self.name = name
            self._chassis = FakeChassis()
            self.config = SimpleNamespace(unsprung_enabled=False, finite_drivetrain=False, tire_substeps=1)
            self.tires = SimpleNamespace(states=(SimpleNamespace(steering=0.), SimpleNamespace(steering=0.)))
            self.steering = SimpleNamespace(angle=0.)
            self.closed = False

        def prepare_control(self, action):
            return action

        def physics_stages(self, request, dt, **kwargs):
            try:
                yield self.name
            finally:
                self.closed = True

        def after_step(self, velocity):
            pass

    class FakeWorkers:
        def submit(self, inputs, static_shapes, material):
            return (0, inputs)

        def results(self, requests, pending, query_lock=None):
            raise ArithmeticError("boom")

        def drain(self, pending):
            drained.extend(pending)

    class FakeWorld:
        def doPhysics(self, dt, max_sub, fixed_dt):
            pass

    car_a, car_b = FakeCar("A"), FakeCar("B")
    advance_world(
        FakeWorld(),
        [(car_a, None), (car_b, None)],
        substeps=2,
        workers=FakeWorkers(),
        recover=lambda dt, err, vehicles=None: recovered.append((dt, list(vehicles or ()))),
    )
    assert drained == [(0, "A"), (0, "B"), (0, "A"), (0, "B")]
    assert car_a.closed and car_b.closed
    assert len(recovered) == 2
    assert recovered[0][1] == [car_a, car_b]


def test_physics_workers_drain_clears_pending_and_completed_handles():
    workers = PhysicsWorkers.__new__(PhysicsWorkers)
    workers.completed = {1: "cached"}
    workers.pending = {0: deque([2, 3])}
    received = []

    def fake_receive(index, identifier):
        received.append((index, identifier))
        workers.pending[index].popleft()
        if identifier == 2:
            raise ArithmeticError("bad")
        return "ok"

    workers._receive = fake_receive
    workers.drain([None, (0, 1), (0, 2), (0, 3)])
    assert workers.completed == {}
    assert list(workers.pending[0]) == []
    assert received == [(0, 2), (0, 3)]


def test_city_asphalt_shader_includes_distance_haze_and_far_clip():
    shader = city_asphalt_shader()
    fragment = shader.getText(Shader.STFragment)
    assert "expressway_far_clip" in fragment
    assert "expressway_haze" in fragment


def test_city_plant_preserves_shadow_proxy_camera_masks(kit):
    assets = dict(kit[0])
    template = NodePath("proxy-tree")
    # 模拟带主相机隐藏阴影代理的树模板。
    vis = assets["broadleaf-a"].copyTo(template)
    vis.setName("visible-canopy")
    proxy = assets["broadleaf-a"].copyTo(template)
    proxy.setName("shadow-proxy")
    shadow_mask = BitMask32.bit(28)
    proxy.hide(BitMask32.lowerOn(31) & ~shadow_mask)
    assets["tree-0"] = assets["tree-1"] = template

    root = NodePath("city-mask-check")
    try:
        list(city_steps(root, 19, 0, HighwayCurve(0, hills=True), assets))
        proxies = root.findAllMatches("**/shadow-proxy")
        assert len(proxies) > 0
        for node in proxies:
            assert node.isHidden(BitMask32.bit(0))
            assert not node.isHidden(shadow_mask)
    finally:
        root.removeNode()
        template.removeNode()


def test_career_course_terrain_uv_uses_road_lateral_coordinates(kit):
    import curve_mesh

    assets, _ = kit
    curve = CareerCourse("ridge-club")
    origin = Vec3(*anchor(curve, 2))
    raw_vertices, _ = curve_mesh.surfaces(curve, 2)["ground"]
    root = NodePath("career-uv-check")
    try:
        list(landscape_steps(root, 2, 0, curve, assets, lambda _s: root))
        terrain = root.find("**/course-landscape")
        assert not terrain.isEmpty()
        data = terrain.node().getGeom(0).getVertexData()
        uv_reader = GeomVertexReader(data, "texcoord")
        checked = 0
        for p in raw_vertices:
            uv = uv_reader.getData2f()
            distance, lateral = curve.project((p[0] + origin.x, p[1] + origin.y))
            assert uv.x == pytest.approx(lateral, abs=1e-4)
            assert uv.y == pytest.approx(distance, abs=1e-4)
            checked += 1
        assert checked == len(raw_vertices) and checked > 0
    finally:
        root.removeNode()


def test_mountain_and_water_follow_curve_normal():
    curve = CareerCourse("ridge-club")
    # 选取航向明显偏离正北的里程（280m 处航向 50°），验证山体沿曲线法向展开。
    s = 280.0
    pose = curve.sample(s)
    assert abs(pose.heading) > 20.0
    left0 = mountain_point(curve, -1, 0, s, 0)
    left100 = mountain_point(curve, -1, 100, s, 0)
    delta = left100 - left0
    assert abs(delta.y) > 20.0  # 非正北路段应沿曲线法向产生 Y 分量
    right0 = mountain_point(curve, 1, 0, s, 0)
    right_sample = curve.sample(s, 430.0)
    assert (right0.x, right0.y) == pytest.approx((right_sample.x, right_sample.y), abs=1e-4)


@pytest.mark.ui
def test_audit_ui_garage_menu_cards_and_loading(tmp_path):
    from application import CoastalDrive

    app = CoastalDrive(smoke=True, output=tmp_path, load_initial_scene=False)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    try:
        # INT-02: MainMenu 导航、vehicle_note 与单选圆点。
        menu = app.main_menu
        menu.vehicle_note.setText("工坊验证提示")
        app.refresh_panel()
        assert menu.vehicle_note.getText() == "工坊验证提示"
        menu.select(7)
        menu.move(1)
        assert menu.selected == 4
        menu.select(7)
        menu.horizontal(1)
        assert menu.selected == 2
        menu.select(menu.continue_index)
        menu.horizontal(1)
        assert menu.selected == 5
        menu.horizontal(-1)
        assert menu.selected == menu.continue_index
        menu.select(2)
        menu.move(1)
        assert menu.selected == 1
        menu.move(1)
        assert menu.selected == 0

        # INT-01 & UI-01: 车库初始焦点不在禁用按钮、切标签保留预览、恢复原漆归零并持久化。
        app.career_action("garage")
        panel = app.career_panel
        assert panel.buttons[panel.selected]["state"] != DGG.DISABLED
        before_angle = app.workshop_vehicle.studio_angle
        panel.key("arrow_right")
        assert app.workshop_vehicle.studio_angle != before_angle
        app.career_action("garage-car", "coastal-hatch")
        app.career_action("garage-tab", "paint")
        app.career_action("garage-paint", 2)
        app.career_action("garage-paint-save")
        assert app.skin_index == 2
        app.career_action("garage-reset-paint")
        assert app.skin_index == 0 and app.career_preview_skin == 0
        app.career_action("garage-tab", "cars")
        assert app.career_preview.design_id == "coastal-hatch"
        app.career_action("garage-back")

        # UI-02: DrivingCards 底排按钮不压盖提示栏且具备 summary_order。
        app.choose_highway()
        app.choose_sprint_routes()
        assert app.driving_cards.summary_order == (0, 1, 2, 3, 4, 5, 6)
        app.handle_panel_key("arrow_right")
        assert app.panel_selection == 1
        app.handle_panel_key("escape")
        app.handle_panel_key("escape")

        # UI-04: WorkspaceLoading 失败态隐藏进度轨，避免压盖退出按钮。
        app.workspace_loading.show("加载测试")
        assert not app.workspace_loading.road_track.isHidden()
        app.workspace_loading.fail()
        assert app.workspace_loading.road_track.isHidden()
        assert not app.workspace_loading.exit_button.isHidden()
        app.workspace_loading.hide()

        # INT-03: WorkshopVehicle 隐藏时暂停 workshop-pbr-update 任务。
        app.workshop_vehicle.hide()
        assert not app.taskMgr.hasTaskNamed("workshop-pbr-update")
    finally:
        app.close_game()
