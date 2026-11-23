"""只移动相机和表现节点，采集正常装配的地区样板；不推进或迁移物理世界。"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(Path(__file__).resolve().parent)]

from local_kcd_drive import LocalVegetation
from panda3d.core import Filename, Geom, Point2, Shader, ShaderAttrib, Vec3

from application import CoastalDrive
from environment import expressway_route
from environment.expressway_route import anchor, terrain_point
from vehicle_workspace import WorkspaceVehicle


def greenbelt_report(group, curve, render):
    """记录本次实际模型外廓与门位开口，不把株位或数量当审美通过。"""
    rows = []
    for kind in ('tree', 'shrub'):
        for node in group.findAllMatches('**/=city-greenbelt-'+kind):
            position = node.getPos(render)
            station, across = curve.project(tuple(position))
            low, high = node.getTightBounds(render)
            along = [curve.project((x, y, low.z))[0]
                     for x in (low.x, high.x) for y in (low.y, high.y)]
            begin, end = min(along), max(along)
            gates = [math.floor(station/200)*200+offset for offset in (35, 78, 121, 164)]
            clearance = min(max(begin-gate, gate-end, 0) for gate in gates)-5
            rows.append({'kind': kind, 'template': node.getName(), 'station': station, 'across': across,
                         'height': high.z-low.z, 'along_bounds': [begin, end],
                         'gate_corridor_clearance_m': clearance})
    return rows


def city_view_report(app, group, curve):
    """投影真实楼体包围盒；只报告视锥关系，不冒充无遮挡面积。"""
    rows = []
    render = app.scene.render
    eye = app.camera.getPos(render)
    for building in group.findAllMatches('**/=city-footprint'):
        center = building.getPos(render)
        station, across = curve.project(tuple(center))
        low, high = building.getTightBounds(render)
        projected = []
        for x in (low.x, high.x):
            for y in (low.y, high.y):
                for z in (low.z, high.z):
                    point = app.cam.getRelativePoint(render, Vec3(x, y, z))
                    if point.y <= app.camLens.getNear():
                        continue
                    film = Point2()
                    app.camLens.project(point, film)
                    projected.append(((film.x+1)*960, (1-film.y)*540))
        if not projected:
            continue
        left, right = min(p[0] for p in projected), max(p[0] for p in projected)
        top, bottom = min(p[1] for p in projected), max(p[1] for p in projected)
        area = max(0, min(1920, right)-max(0, left))*max(0, min(1080, bottom)-max(0, top))
        rows.append({'station': station, 'across': across, 'camera_distance': (center-eye).length(),
                     'model': building.getName(), 'projected_bounds_px': [left, top, right, bottom],
                     'clipped_box_area_px': area})
    return {'scope': '真实楼体AABB投影，未扣除植被/地形/其它楼体遮挡，不能当实际可见像素。',
            'fov': list(app.camLens.getFov()), 'buildings': rows}


def city_static_report(app, group, output, distance, batch_steps):
    """同次加载的原/新图和ABBA静态绘制计时，临时副本只共享原资源。"""
    import numpy as np
    from panda3d.core import SceneGraphAnalyzer

    def statistics(node):
        result = SceneGraphAnalyzer()
        result.addNode(node.node())
        return {'geom_nodes': result.getNumGeomNodes(), 'geoms': result.getNumGeoms(),
                'triangles': result.getNumTris(), 'vertices': result.getNumVertices()}

    candidate = group.copyTo(app.scene.render)
    candidate.hide()
    try:
        for _phase in batch_steps(candidate):
            pass
        before, after = statistics(group), statistics(candidate)
        assert before['triangles'] == after['triangles']
        app.scene.render.prepareScene(app.win.getGsg())
        arrays, rows, images = {}, [], {}
        for number, label in enumerate(('before', 'after', 'after', 'before')):
            group.show() if label == 'before' else group.hide()
            candidate.show() if label == 'after' else candidate.hide()
            # 排除新顶点上传与原生LOD过渡，计时不经过应用的90Hz诊断限帧任务。
            deadline = time.perf_counter()+.7
            while time.perf_counter() < deadline:
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            timings = []
            for _ in range(20):
                begin = time.perf_counter()
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                timings.append((time.perf_counter()-begin)*1000)
            rows.append({'order': number, 'variant': label, 'frames': len(timings),
                         'median_ms': float(np.median(timings)), 'p95_ms': float(np.percentile(timings, 95)),
                         'max_ms': max(timings)})
            if label not in arrays:
                texture = app.win.getScreenshot()
                name = f'{distance:05d}m-city-static-{label}.png'
                assert texture.write(Filename.fromOsSpecific(str(output/name)))
                arrays[label] = np.frombuffer(bytes(texture.getRamImageAs('RGB')), dtype=np.uint8)
                images[label] = name
        changed = (arrays['before'] != arrays['after']).reshape(-1, 3).any(axis=1)
        report = {'scope': '同次离屏应用静态renderFrame+syncFrame的ABBA；不推进物理，不是驾驶FPS或长期Gate。',
                  'before': before, 'after': after, 'images': images, 'changed_pixels': int(changed.sum()),
                  'timing': rows}
        (output/'city-static.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
    finally:
        candidate.removeNode()
        group.show()


def _city_shadow(fragment):
    """隔离的接收平面实验，不属于默认运行材质。"""
    start = fragment.index('float shadow_caster_contrib(')
    end = fragment.index('\n}\n', start)+3
    addition = (ROOT/'art/expressway/candidates/city-shadow/city-shadow.glsl').read_text(encoding='utf-8')
    return fragment[:start]+addition+fragment[end:]


def city_shadow_candidate(app, group, output, distance):
    """仅替换实际城市接收材质；原投影状态优先级保持，核对深度图未被改变。"""
    from environment.expressway_materials import city_plaster_shader

    buffer = app.scene.sun_path.node().getShadowBuffer(app.win.getGsg())
    assert buffer is not None and buffer.isActive() and buffer.isValid()
    depth = buffer.getTexture()

    def depth_hash():
        assert app.graphicsEngine.extractTextureData(depth, app.win.getGsg())
        return hashlib.sha256(bytes(depth.getRamImage())).hexdigest()

    previous_depth = depth_hash()
    originals, shaders = [], {}
    names = {'city-trim', 'city-stone', 'city-soil', 'city-glass', 'city-metal', 'city-roof'}
    try:
        for part in group.findAllMatches('**/+GeomNode'):
            for index, state in enumerate(part.node().getGeomStates()):
                effective = part.getNetState().compose(state).getAttrib(ShaderAttrib)
                if effective is None:
                    continue
                source = effective.getShader()
                if source != city_plaster_shader() and part.getName() not in names:
                    continue
                if source not in shaders:
                    shaders[source] = Shader.make(Shader.SLGLSL, source.getText(Shader.STVertex),
                                                  _city_shadow(source.getText(Shader.STFragment)))
                attrib = state.getAttrib(ShaderAttrib)
                priority = effective.getShaderPriority()
                updated = (ShaderAttrib.make(shaders[source], priority) if attrib is None else
                           attrib.setShader(shaders[source], priority))
                # 不能以100盖过阴影相机的10，否则会改变投影路径或产生深度读写反馈。
                replacement = state.setAttrib(updated, state.getOverride(ShaderAttrib))
                assert part.getNetState().compose(replacement).getAttrib(ShaderAttrib).getShader() == shaders[source]
                part.node().setGeomState(index, replacement)
                originals.append((part.node(), index, state))
        assert originals
        for _ in range(4):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        name = f'{distance:05d}m-city-shadow-candidate.png'
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
        after_depth = depth_hash()
        report = {'screenshot': name, 'receiver_geoms': len(originals), 'shader_variants': len(shaders),
                  'before_depth_sha256': previous_depth, 'after_depth_sha256': after_depth,
                  'shadow_depth_unchanged': previous_depth == after_depth}
        (output/'city-shadow-candidate.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert report['shadow_depth_unchanged']
        lods = group.findAllMatches('**/city-building-lod')
        report['fixed_lod_diagnostics'] = []
        try:
            for level in (0, 1):
                for lod in lods:
                    lod.node().forceSwitch(level)
                for _ in range(4):
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                diagnostic = f'{distance:05d}m-city-shadow-fixed-lod-{level}.png'
                assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/diagnostic)))
                report['fixed_lod_diagnostics'].append(diagnostic)
        finally:
            for lod in lods:
                lod.node().clearForceSwitch()
        # 独立验证只作用于城市投影的原生斜率偏移，主相机与接收shader都恢复原样。
        from panda3d.core import DepthOffsetAttrib, RenderState

        for node, index, state in originals:
            node.setGeomState(index, state)
        sun = app.scene.sun_path.node()
        assert not sun.getTagStateKey()
        districts = group.findAllMatches('**/mainland-city')
        try:
            sun.setTagStateKey('city-shadow-test')
            sun.setTagState('1', RenderState.make(DepthOffsetAttrib.make(-1)))
            for district in districts:
                district.setTag('city-shadow-test', '1')
            for _ in range(4):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            diagnostic = f'{distance:05d}m-city-shadow-caster-offset.png'
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/diagnostic)))
            report['caster_offset_diagnostic'] = diagnostic
            report['caster_depth_offset'] = -1
            report['caster_offset_depth_sha256'] = depth_hash()
        finally:
            sun.clearTagState('1')
            sun.setTagStateKey('')
            for district in districts:
                district.clearTag('city-shadow-test')
        (output/'city-shadow-candidate.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report
    finally:
        for node, index, state in originals:
            node.setGeomState(index, state)


def _career_terrain_cost(app, group, curve, output, distance):
    """同一新植被下只换原地形/新岸坡及海面；不作整版本或驾驶帧率对照。"""
    import numpy as np
    from local_kcd_drive import course_normal_steps

    from career_terrain import terrain
    from environment.surface_mesh import surface_mesh

    work = course_normal_steps(curve.course_id)
    while True:
        try:
            next(work)
        except StopIteration as completed:
            normals = completed.value
            break
    original = terrain(curve.course_id)
    old = group.attachNewNode('cost-original-terrain')
    current, by_segment = [], {}
    try:
        for node in group.findAllMatches('**/+GeomNode'):
            for geom_index, state in enumerate(node.node().getGeomStates()):
                effective = node.getNetState().compose(state)
                shader = effective.getAttrib(ShaderAttrib)
                if shader is None or shader.getShader() != app.scene.expressway_kit['route-terrain-shader']:
                    continue
                parent = node.findNetTag('sample-index')
                index = int(parent.getTag('sample-index'))
                if index in original:
                    geom = node.node().modifyGeom(geom_index)
                    current.append((node.node(), geom_index, geom))
                    by_segment[index] = parent, effective
        assert current
        empty = Geom(current[0][2].getVertexData())
        for index, (parent, state) in by_segment.items():
            origin = Vec3(*anchor(curve, index))
            world, faces = original[index]
            vertices = [tuple(Vec3(*p)-origin) for p in world]
            smooth = [normals[round(x/8), round(y/8)] for x, y, _z in world]
            uv = [(x, y) for x, y, _z in world]
            mesh = surface_mesh('cost-old-ground', vertices, faces, smooth,
                                [(.24, .34, .08, 0)]*len(vertices), uv)
            mesh.setState(state)
            holder = old.attachNewNode('cost-segment')
            holder.setTransform(parent.getTransform(group))
            mesh.reparentTo(holder)
        old.hide()
        app.scene.render.prepareScene(app.win.getGsg())
        rows = []
        for number, label in enumerate(('old_terrain', 'coastal', 'coastal', 'old_terrain')):
            baseline = label == 'old_terrain'
            old.show() if baseline else old.hide()
            for node, index, geom in current:
                node.setGeom(index, empty if baseline else geom)
            app.scene.ocean.hide() if baseline else app.scene.ocean.show()
            for _ in range(8):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            times = []
            for _ in range(40):
                start = time.perf_counter()
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                times.append((time.perf_counter()-start)*1000)
            rows.append({'order': number, 'variant': label, 'frames': len(times),
                         'median_ms': float(np.median(times)), 'p95_ms': float(np.percentile(times, 95)),
                         'p99_ms': float(np.percentile(times, 99)), 'max_ms': max(times),
                         'over33ms': sum(v > 33.33 for v in times), 'over50ms': sum(v > 50 for v in times)})
            if number < 2:
                name = f'{distance:05d}m-coast-cost-{label}.png'
                assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
        report = {'scope': 'Frozen static render+sync, old terrain versus new coast under SAME new vegetation and backdrop; no physics/UI/audio or driving FPS conclusion',
                  'rows': rows}
        (output/f'{distance:05d}m-coast-cost.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report
    finally:
        for node, index, geom in current:
            node.setGeom(index, geom)
        app.scene.ocean.show()
        old.removeNode()


def _career_water_visibility(app, output, distance):
    """保留正常深度与叶片遮罩，只给Scene实际海面着色。"""
    import numpy as np
    from PIL import Image

    ocean = app.scene.ocean
    original = ocean.getShader()
    fragment = original.getText(Shader.STFragment)
    final = 'fragColor = vec4(mix(blue,expressway_haze(blue, v_world_position),water_haze),1.0);'
    assert fragment.count(final) == 1
    marker = Shader.make(Shader.SLGLSL, original.getText(Shader.STVertex),
                         fragment.replace(final, 'fragColor = vec4(2.,0.,2.,1.);'))
    try:
        ocean.setShader(marker, 1)
        for _ in range(3):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert not marker.getErrorFlag()
        name = f'{distance:05d}m-water-visibility.png'
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
        pixels = np.asarray(Image.open(output/name).convert('RGB')).astype(int)
        count = int(((pixels[:, :, 0]-pixels[:, :, 1] > 60)
                      & (pixels[:, :, 2]-pixels[:, :, 1] > 60)).sum())
        return {'screenshot': name, 'pixels': count}
    finally:
        ocean.setShader(original, 1)


def water_time_report(app, group, eye, output, distance):
    """固定物理与镜位，只替换显示快照时间；同时复现旧静止材质。"""
    import numpy as np

    scene = app.scene
    snapshot = app.session.current
    career_water = scene.ocean.getName() == 'career-ocean'
    original = scene.ocean.getShader() if career_water else scene.expressway_kit['route-water-shader']
    fragment = original.getText(Shader.STFragment)
    assert fragment.count('uniform float sea_time;') == 1
    before = fragment.replace('uniform float sea_time;', 'const float sea_time=0.;')
    (output/'water-before.frag').write_text(before, encoding='utf-8')
    old_shader = Shader.make(Shader.SLGLSL, original.getText(Shader.STVertex), before)
    waters = []
    parts = (*group.findAllMatches('**/+GeomNode'), scene.ocean) if career_water else group.findAllMatches('**/+GeomNode')
    for part in parts:
        for index, state in enumerate(part.node().getGeomStates()):
            attrib = part.getNetState().compose(state).getAttrib(ShaderAttrib)
            if attrib is not None and attrib.getShader() == original:
                waters.append((part.node(), index, state, attrib))
    assert waters
    stashed, visible_water_pixels = [], None
    if career_water:
        visible_water_pixels = _career_water_visibility(app, output, distance)['pixels']
        # 时间功能只测水面，隔离无关叶片/MSAA边缘；此图不作正常视野验收。
        for child in tuple(scene.render.getChildren()):
            if child not in (scene.ocean, scene.sky, scene.sun_path, scene.rail_sun_path, scene.ambient_path) and not child.isStashed():
                child.stash()
                stashed.append(child)
    pixels, shots = {}, []
    try:
        for label, clock, baseline in (('before-0', 0., True), ('before-2', 2., True),
                                       ('current-0', 0., False), ('current-half', .5, False),
                                       ('current-1', 1., False), ('current-2', 2., False),
                                       ('current-repeat-2', 2., False)):
            for node, index, state, attrib in waters:
                node.setGeomState(index, state.setAttrib(attrib.setShader(old_shader, 1),
                                  state.getOverride(ShaderAttrib)) if baseline else state)
            # 不写入Session或Simulation，沿生产Scene.apply验证快照的显示消费路径。
            scene.apply(replace(snapshot, time=clock))
            for root in scene.segment_nodes.values():
                root.hide()
            for node in (scene.player, *scene.wheels, *scene.traffic):
                node.hide()
            for wheels in scene.traffic_wheels:
                for wheel in wheels:
                    wheel.hide()
            scene.sky.setPos(eye)
            scene.update_lighting(eye)
            for _ in range(3):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert not original.getErrorFlag() and not old_shader.getErrorFlag()
            texture = app.win.getScreenshot()
            name = f'{distance:05d}m-water-{label}.png'
            assert texture.write(Filename.fromOsSpecific(str(output/name)))
            data = bytes(texture.getRamImageAs('RGB'))
            pixels[label] = np.frombuffer(data, dtype=np.uint8)
            shots.append({'label': label, 'display_time': clock, 'screenshot': name,
                          'rgb_sha256': hashlib.sha256(data).hexdigest()})
            assert app.session.current == snapshot
    finally:
        for node, index, state, _attrib in waters:
            node.setGeomState(index, state)
        for child in stashed:
            child.unstash()
        scene.render.setShaderInput('sea_time', snapshot.time)
    comparisons = {}
    for first, second in (('before-0', 'before-2'), ('before-0', 'current-0'),
                          ('current-0', 'current-2'), ('current-2', 'current-repeat-2')):
        difference = pixels[first] != pixels[second]
        comparisons[first+'/'+second] = int(difference.reshape(-1, 3).any(axis=1).sum())
    stable_before = (pixels['before-0'] == pixels['before-2']).reshape(-1, 3).all(axis=1)
    changed_after = (pixels['current-0'] != pixels['current-2']).reshape(-1, 3).any(axis=1)
    report = {'scope': '离屏GPU功能对照，显示时间为诊断输入；不是驾驶或帧耗结果。',
              'geoms': len(waters), 'shots': shots, 'changed_pixels': comparisons,
              'motion_on_baseline_stable_pixels': int((stable_before & changed_after).sum()),
              'baseline_note': '保留旧材质对照的全部像素差异；运动结论只统计旧对照不变的像素。',
              'physics_tick': snapshot.tick, 'authoritative_time': snapshot.time}
    if career_water:
        report['scope'] = '正常视野先以实际深度测海面开口；时间功能隔离其它景物，仅测水面GPU，不作正常驾驶或性能结论。'
        report['normal_view_water_pixels'] = visible_water_pixels
    (output/'water-time.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert comparisons['before-0/current-0'] == 0
    assert report['motion_on_baseline_stable_pixels'] > 0
    assert comparisons['current-2/current-repeat-2'] == 0
    return report


def capture(output, distances, workspace, scan_atlas, view, shadow_diagnostics=False, onscreen=False,
            mountain_diagnostics=False, water_time_diagnostics=False, city_overview=False,
            city_ground_baseline=False, receiver_candidate=False, static_diagnostics=False,
            career_event=None, career_cost=False, coast_candidate=False):
    if coast_candidate:
        os.environ['COASTALDRIVE_COAST_CANDIDATE'] = '1'
    output.mkdir(parents=True, exist_ok=False)
    sources = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
        'src/environment/expressway_buildings.py', 'src/environment/expressway_city.py',
        'src/environment/expressway_route.py', 'src/environment/expressway_materials.py',
        'src/environment/expressway_mountains.py', 'tools/environment/local_coastal_landscape.py',
        'tools/environment/kcd_local_environment.py',
        'assets/game/expressway/shaders/route-mountain.frag',
        'src/scene.py', 'src/environment/foundation.py', 'src/environment/career_coast.py',
        'assets/game/environment/career-coast/coast-club.npz', 'assets/game/environment/career-coast/coast-final.npz',
        'assets/game/environment/career-coast/water.vert', 'assets/game/environment/career-coast/water.frag',
        'assets/game/expressway/shaders/route-water.frag',
        'assets/game/expressway/shaders/route-water.vert',
        'assets/game/environment/coastal-sunset/daylight-manifest.json',
        'assets/game/expressway/shaders/distance-haze.glsl',
        'assets/game/expressway/shaders/city-plaster.glsl',
        'tools/environment/local_kcd_drive.py', 'tools/environment/capture_regional.py')}
    (output/'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    os.environ['LOCALAPPDATA'] = str(output/'user')
    local = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
    local.install()
    assert expressway_route.segment_steps == local.segment
    app = None
    try:
        app = CoastalDrive(smoke=True, onscreen=onscreen, output=output, render_size=(1920, 1080),
                           track='endless', road_shape='hills',
                           workspace_vehicle=WorkspaceVehicle.load(workspace))
        if career_event is not None:
            from race import GameMode

            app.career_event_id = career_event
            app._enter_game(GameMode.CAREER, 'endless')
        stages = []

        def mark(label):
            if not shadow_diagnostics:
                return
            light = app.scene.sun_path.node()
            buffer = light.getShadowBuffer(app.win.getGsg())
            stages.append({'stage': label, 'light': int(light.this),
                           'shadow': None if buffer is None else {
                               'id': int(buffer.this), 'active': buffer.isActive(), 'valid': buffer.isValid(),
                               'type': buffer.getType().getName(),
                               'registered': buffer in app.graphicsEngine.windows},
                           'preview_buffers': [] if app.workshop_vehicle.buffer is None else [
                               {'name': item.getName(), 'id': int(item.this), 'active': item.isActive()}
                               for item in app.workshop_vehicle.pipeline._filtermgr.buffers]})
            (output/'stages.json').write_text(json.dumps(stages, indent=2), encoding='utf-8')

        mark('constructed')
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        app.session.road_shape = 'hills'
        # smoke构造已按目标地图建立Scene，不再重复进入另一轮资源准备。
        app.session.pause()
        mark('paused')
        app.refresh_panel()
        mark('panel-refreshed')
        app.aspect2d.hide()
        app.workshop_vehicle.hide()
        mark('preview-hidden')
        scene = app.scene

        def ground_baseline(name):
            scene.render.setShaderInput('city_lawn_phase', (0., 0.), 100)
            try:
                for _ in range(3):
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
            finally:
                scene.render.setShaderInput('city_lawn_phase', (0., 0.))
            return name

        for root in scene.segment_nodes.values():
            root.hide()
        for node in (scene.player, *scene.wheels, *scene.traffic):
            node.hide()
        for wheels in scene.traffic_wheels:
            for wheel in wheels:
                wheel.hide()
        curve = app.session.simulation.road.curve
        if scan_atlas:
            from kcd_local_environment import source_texture

            path = ROOT/'art/expressway/sources/coastal-scans/coastal_cliff_01/textures/coastal_cliff_01_diff_2k.jpg'
            scene.expressway_kit['rock'] = source_texture(path, color=True)
        start_tick = app.session.current.tick
        views = []
        for distance in distances:
            group = scene.render.attachNewNode('regional-static-sample')
            try:
                center = math.floor(distance/200)
                for index in range(center-2, center+5):
                    root = group.attachNewNode('sample-segment-'+str(index))
                    root.setTag('sample-index', str(index))
                    for _phase in expressway_route.segment_steps(root, index, app.session.simulation.seed,
                                                                 scene.expressway_kit, lambda _node: None, curve):
                        pass
                    assert root.hasPythonTag('far-tree-batches')
                    root.setPos(*anchor(curve, index))
                if view == 'mountain':
                    eye, target = curve.sample(distance-40, -60), curve.sample(distance+50, -250)
                    eye = Vec3(eye.x, eye.y, eye.z+30)
                elif view == 'city':
                    eye = terrain_point(curve, 45, distance-85, app.session.simulation.seed)+Vec3(0, 0, 24)
                    target = terrain_point(curve, 160, distance+80, app.session.simulation.seed)
                elif view == 'city-detail':
                    eye = terrain_point(curve, 65, distance+5, app.session.simulation.seed)+Vec3(0, 0, 5)
                    target = terrain_point(curve, 110, distance+35, app.session.simulation.seed)
                elif view == 'water':
                    eye, target = curve.sample(distance-10, 70), curve.sample(distance+50, 200)
                    eye = Vec3(eye.x, eye.y, eye.z+8)
                    target = Vec3(target.x, target.y, -3)
                else:
                    eye, target = curve.sample(distance-14, 0), curve.sample(distance+25, 0)
                    eye = Vec3(eye.x, eye.y, eye.z+3.2)
                app.camera.setPos(eye)
                app.camera.lookAt(target.x, target.y, target.z+(8 if view.startswith('city') else .5))
                app.camLens.setFov(68)
                scene.sky.setPos(eye)
                scene.update_lighting(eye)
                mark('before-prepare')
                scene.render.prepareScene(app.win.getGsg())
                mark('after-prepare')
                # /Draw首帧可能才请求阴影缓冲；先完成该帧并打开新输出，再取稳定画面。
                app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                mark('first-frame-complete')
                app.graphicsEngine.openWindows()
                mark('outputs-opened')
                # 让原生LOD渐变在真实时钟上结束，避免把过渡中帧当静态成品。
                deadline = time.perf_counter()+.7
                while time.perf_counter() < deadline:
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                mark('after-render')
                name = f'{distance:05d}m.png'
                assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
                row = {'distance': distance, 'screenshot': name, 'eye': list(eye),
                       'visible_geoms': group.findAllMatches('**/+GeomNode').getNumPaths(),
                       'far_tree_batches': [entry for root in group.getChildren()
                                            for entry in root.getPythonTag('far-tree-batches')]}
                row['city_greenbelt'] = greenbelt_report(group, curve, scene.render)
                if static_diagnostics:
                    from city_static_candidate import batch_static_steps

                    def batch_steps(node):
                        return batch_static_steps(node, scene.expressway_kit['lamp'].getName())

                    row['city_static'] = city_static_report(app, group, output, distance, batch_steps)
                if receiver_candidate:
                    row['city_shadow_candidate'] = city_shadow_candidate(app, group, output, distance)
                if view == 'road':
                    row['city_view'] = city_view_report(app, group, curve)
                if city_ground_baseline:
                    row['city_ground_before'] = ground_baseline(f'{distance:05d}m-ground-before.png')
                if water_time_diagnostics:
                    row['water_time'] = water_time_report(app, group, eye, output, distance)
                elif scene.ocean.getName() == 'career-ocean':
                    row['water_visibility'] = _career_water_visibility(app, output, distance)
                if career_cost and distance == distances[0]:
                    row['coast_cost'] = _career_terrain_cost(app, group, curve, output, distance)
                if mountain_diagnostics:
                    original = scene.expressway_kit['mountain-shader']
                    vertex, fragment = original.getText(Shader.STVertex), original.getText(Shader.STFragment)
                    final = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
                    if fragment.count(final) != 1:
                        raise RuntimeError('山体诊断需要当前PBR最终输出接口')
                    mountains = []
                    # 合批后shader及输入可能在Geom状态上，不能按旧节点名强盖整套输入。
                    for part in group.findAllMatches('**/+GeomNode'):
                        for geom_index in range(part.node().getNumGeoms()):
                            state = part.node().getGeomState(geom_index)
                            effective = part.getNetState().compose(state)
                            shader_state = effective.getAttrib(ShaderAttrib)
                            if shader_state is not None and shader_state.getShader() == original:
                                mountains.append((part.node(), geom_index, state, effective, shader_state))
                    if not mountains:
                        raise RuntimeError('没有找到实际使用山体材质的Geom，不能输出无效对照')
                    row['mountain_diagnostic_geoms'] = len(mountains)
                    row['mountain_diagnostics'] = []
                    try:
                        variants = {
                            'albedo': fragment.replace(final, 'o_color = expressway_albedo();'),
                            'rock-mask': fragment.replace(final, 'o_color = vec4(vec3(v_color.a), 1.);'),
                            'no-haze': fragment.replace(final, 'o_color = color;'),
                            'no-ibl-specular': fragment.replace('ibl_kd * ibl_diff  + ibl_spec',
                                                               'ibl_kd * ibl_diff'),
                        }
                        if mountain_diagnostics == 'lighting':
                            variants = {
                                'no-sun': fragment.replace('func_params.n_dot_l * lightcol',
                                                          'func_params.n_dot_l * vec3(0.)'),
                                'no-ibl-diffuse': fragment.replace('ibl_kd * ibl_diff  + ibl_spec', 'ibl_spec'),
                                'world-normal': fragment.replace(final, 'o_color = vec4(world_normal*.5+.5, 1.);'),
                            }
                        for label, source in variants.items():
                            shader = Shader.make(Shader.SLGLSL, vertex, source)
                            for node, geom_index, _state, effective, shader_state in mountains:
                                node.setGeomState(geom_index, effective.setAttrib(shader_state.setShader(shader), 100))
                            for _ in range(3):
                                app.taskMgr.step()
                            app.graphicsEngine.syncFrame()
                            diagnostic = f'{distance:05d}m-mountain-{label}.png'
                            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/diagnostic)))
                            row['mountain_diagnostics'].append(diagnostic)
                    finally:
                        for node, geom_index, state, _effective, _shader_state in mountains:
                            node.setGeomState(geom_index, state)
                    row['diagnostic_scope'] = '仅隔离山体底色/顶点岩量/空气透视/环境反射，不是候选成品。'
                if shadow_diagnostics:
                    light = scene.sun_path.node()
                    lens = light.getLens()
                    projections = []
                    for foundation in group.findAllMatches('**/city-foundation'):
                        point = foundation.getPos(scene.render)
                        camera_point = scene.sun_path.getRelativePoint(scene.render, point)
                        film = Point2()
                        visible = lens.project(camera_point, film)
                        projections.append({'world': list(point), 'sun_camera': list(camera_point),
                                            'film': list(film), 'inside_lens': visible,
                                            'draw_mask': str(foundation.node().getDrawShowMask())})
                    row['sun'] = {'film_size': list(lens.getFilmSize()), 'near': lens.getNear(),
                                  'far': lens.getFar(), 'position': list(scene.sun_path.getPos(scene.render)),
                                  'foundations': projections}
                    buffer = light.getShadowBuffer(app.win.getGsg())
                    if buffer is None or not buffer.isValid() or not buffer.isActive():
                        raise RuntimeError('太阳阴影输出尚未就绪，不能将此图作为有效光影样板')
                    texture = buffer.getTexture()
                    row['sun'].update(buffer_active=buffer.isActive(), buffer_valid=buffer.isValid(),
                                      shadow_output=buffer.getName())
                    assert app.graphicsEngine.extractTextureData(texture, app.win.getGsg())
                    assert texture.write(Filename.fromOsSpecific(str(output/f'{distance:05d}m-depth.png')))
                    # 同镜位只禁用接收阴影，用于确认太阳遮蔽确实参与实际像素。
                    scene.render.setShaderInput('global_shadow_bias', 1.)
                    for _ in range(4):
                        app.taskMgr.step()
                    app.graphicsEngine.syncFrame()
                    assert app.win.getScreenshot().write(Filename.fromOsSpecific(
                        str(output/f'{distance:05d}m-shadow-off.png')))
                    scene.render.setShaderInput('global_shadow_bias', app.pipeline.shadow_bias)
                if city_overview:
                    overview_eye = terrain_point(curve, 45, distance-85, app.session.simulation.seed)+Vec3(0, 0, 24)
                    target = terrain_point(curve, 160, distance+80, app.session.simulation.seed)
                    app.camera.setPos(overview_eye)
                    app.camera.lookAt(target+Vec3(0, 0, 8))
                    scene.sky.setPos(overview_eye)
                    scene.update_lighting(overview_eye)
                    deadline = time.perf_counter()+.7
                    while time.perf_counter() < deadline:
                        app.taskMgr.step()
                    app.graphicsEngine.syncFrame()
                    name = f'{distance:05d}m-city-overview.png'
                    assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
                    row['city_overview'] = {'screenshot': name, 'eye': list(overview_eye)}
                    if city_ground_baseline:
                        row['city_overview']['ground_before'] = ground_baseline(
                            f'{distance:05d}m-city-overview-ground-before.png')
                views.append(row)
                assert app.session.current.tick == start_tick
            finally:
                group.removeNode()
        (output/'summary.json').write_text(json.dumps({
            'scope': '实际渲染器与正常景观生成器的静态镜位；没有驶到这些位置，不作驾驶或性能验收。',
            'scan_atlas_baseline': scan_atlas, 'view': view, 'onscreen': onscreen,
            'career_event': career_event,
            'segment_generator': 'LocalVegetation.segment (current installed entry)',
            'regional_light': scene.coastal_daylight,
            'exposure_ev': app.pipeline.exposure,
            'sun_direction': list(-scene.sun_path.getQuat().xform(Vec3(0, 1, 0))),
            'seed': app.session.simulation.seed,
            'views': views, 'physics_tick_unchanged': start_tick,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if app is not None:
            app.close_game()
        local.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--distances', type=int, nargs='+', default=(120, 3400))
    parser.add_argument('--scan-atlas-baseline', action='store_true')
    parser.add_argument('--shadow-diagnostics', action='store_true')
    parser.add_argument('--mountain-diagnostics', nargs='?', const='material', choices=('material', 'lighting'))
    parser.add_argument('--onscreen', action='store_true')
    parser.add_argument('--water-time-diagnostics', action='store_true')
    parser.add_argument('--city-overview', action='store_true')
    parser.add_argument('--city-ground-baseline', action='store_true')
    parser.add_argument('--city-shadow-candidate', action='store_true')
    parser.add_argument('--city-static-diagnostics', action='store_true')
    parser.add_argument('--career-event', choices=('coast-sprint', 'ridge-run', 'coastal-cup'))
    parser.add_argument('--career-cost', action='store_true')
    parser.add_argument('--career-coast-candidate', action='store_true')
    parser.add_argument('--view', choices=('road', 'mountain', 'city', 'city-detail', 'water'), default='road')
    args = parser.parse_args()
    capture(args.output.resolve(), args.distances, args.workspace.resolve(), args.scan_atlas_baseline,
            args.view, args.shadow_diagnostics, args.onscreen, args.mountain_diagnostics,
            args.water_time_diagnostics, args.city_overview, args.city_ground_baseline,
            args.city_shadow_candidate, args.city_static_diagnostics, args.career_event, args.career_cost,
            args.career_coast_candidate)
