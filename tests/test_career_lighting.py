"""沿海生涯的同源光照、坡面护栏投影和退出恢复。"""

import math
from types import SimpleNamespace

import pytest
from panda3d.core import DirectionalLight, NodePath, Vec3

from career_courses import CareerCourse
from environment.expressway_materials import daylight_assets
from environment.expressway_route import rail_shadow_coordinate
from environment.foundation import update_daylight
from paths import resource_root


@pytest.mark.parametrize('course_id,station', (
    ('coast-club', 120), ('coast-club', 520),
    ('coast-final', 320), ('coast-final', 560), ('coast-final', 1120)))
def test_coastal_career_rail_shadow_meets_the_actual_road_plane(course_id, station):
    _sky, _environment, metadata = daylight_assets(resource_root()/'assets/game/environment/coastal-sunset')
    curve = CareerCourse(course_id)
    pose = curve.sample(station)
    angle, grade = math.radians(pose.heading), math.tan(math.radians(pose.grade))
    forward = Vec3(-math.sin(angle), math.cos(angle), 0)
    across = Vec3(math.cos(angle), math.sin(angle), 0)
    normal = Vec3(-grade*forward.x, -grade*forward.y, 1)
    ray = -Vec3(*metadata['directional_sun'])
    denominator = normal.dot(ray)
    travel = -.8/denominator if denominator < -1e-5 else 0.
    expected = (ray*travel).dot(across)
    lateral, reach = rail_shadow_coordinate(curve, station, 7.5)
    assert lateral == 7.5
    assert math.isfinite(reach)
    assert reach == pytest.approx(expected, abs=3e-5)


def test_coastal_shadow_grid_stays_in_absolute_world_after_rebase():
    _sky, _environment, metadata = daylight_assets(resource_root()/'assets/game/environment/coastal-sunset')
    light = DirectionalLight('coastal-rebase')
    light.setShadowCaster(True, 4096, 4096)
    light.getLens().setFilmSize(120, 120)
    sun = NodePath(light)
    session = SimpleNamespace(render_origin=lambda: 0.)
    scene = SimpleNamespace(sun_path=sun, coastal_daylight=metadata,
                            base=SimpleNamespace(session=session))
    try:
        world = Vec3(15, 2400, 3)
        update_daylight(scene, world)
        before = sun.getPos()
        session.render_origin = lambda: 2048.
        origin = Vec3(0, 2048, 0)
        update_daylight(scene, world-origin)
        assert (sun.getPos()+origin-before).length() < .001
    finally:
        sun.removeNode()


@pytest.mark.parametrize('candidate', (False, True))
def test_career_entries_pair_coastal_light_and_restore_mountain_and_menu(tmp_path, monkeypatch, candidate):
    monkeypatch.setenv('COASTALDRIVE_COAST_CANDIDATE', '1' if candidate else '0')
    from dataclasses import replace

    from panda3d.core import ShaderAttrib

    from application import CoastalDrive

    sky, environment, metadata = daylight_assets(resource_root()/'assets/game/environment/coastal-sunset')
    game = CoastalDrive(smoke=True, output=tmp_path, render_size=(1024, 768))
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    initial_exposure = game.scene.previous_exposure
    config = game.session.vehicle_config
    # 隔离成绩夹具只解锁入口，不伪造行驶/美术/性能验收。
    game.career_progress.records = {name: {'stars': 3, 'seconds': 20.}
                                    for name in ('first-drive', 'parking', 'slalom')}
    try:
        for event in ('coast-sprint', 'coastal-cup'):
            game.career_action('start', event)
            assert game.career_panel.page == 'challenge'
            game.challenge_action('challenge-start')
            scene = game.scene
            assert game.session.career_event_id == event
            assert scene.coastal_daylight == metadata
            assert game.pipeline.exposure == metadata['exposure_ev']
            assert scene.sky.getTexture() == sky
            assert scene.expressway_kit['daylight-environment'] is environment
            assert scene.render.getShader() == scene.expressway_kit['distance-shader']
            assert scene.render.getShaderInput('filtered_env_map').getTexture() == environment.filtered_env_map
            assert scene.render.getShaderInput('expressway_sky').getTexture() == sky
            if candidate:
                assert scene.ocean.getName() == 'career-ocean'
                assert not scene.ocean.isHidden()
                assert scene.ocean.getParent() == scene.render
                assert scene._career_backdrop.getParent() == scene.render
                assert scene.ocean.node().getGeom(0).getPrimitive(0).getNumPrimitives() < 150
                inputs = []
                for seconds in (.5, 1.5):
                    scene.apply(replace(game.session.current, time=seconds))
                    state = scene.ocean.getNetState().compose(scene.ocean.node().getGeomState(0))
                    inputs.append(state.getAttrib(ShaderAttrib).getShaderInput('sea_time'))
                    assert inputs[-1].getVector().x == seconds
                assert inputs[0].getVector().x == .5
                scene.apply(replace(game.session.current, origin_y=2048.))
                assert scene.ocean.getY() == -2048.
                assert scene._career_backdrop.getY() == -2048.
            else:
                assert scene.ocean.isHidden()
                assert scene._career_backdrop is None
            direction = -scene.sun_path.getQuat().xform(Vec3(0, 1, 0))
            assert direction.dot(Vec3(*metadata['directional_sun'])) > .99999
            assert scene.rail_sun_path.node().getColor() == scene.sun_path.node().getColor()
            assert game.session.vehicle_config == config
        game.career_action('start', 'ridge-run')
        assert game.career_panel.page == 'challenge'
        game.challenge_action('challenge-start')
        assert game.scene.coastal_daylight is None
        assert game.scene.sky.getTexture() != sky
        assert game.scene.ocean.isHidden()
        assert game.pipeline.exposure == initial_exposure
        assert game.session.vehicle_config == config
        game.back_to_menu()
        assert game.scene is None
        assert game.pipeline.exposure == initial_exposure
    finally:
        game.close_game()
