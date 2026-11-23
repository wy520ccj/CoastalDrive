"""冻结实景分别关闭照明分量，并读回阴影深度；只用于定位本地样板。"""

import json
import math
import time

import numpy as np
from panda3d.core import Filename, LColor, PNMImage, PTALVecBase3f, Shader, ShaderAttrib, Vec3


def inspect_leaf_transmission(app, output):
    """普通随车镜位比较底色调制的透光与旧的绝对加亮；冻结物理并还原材质。"""
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName().startswith(('kcd-oak-', 'kcd-young-oak-', 'kcd-hawthorn-'))
             for number in range(node.node().getNumGeoms())]
    assert items
    shaders = {}
    old = '* base_color.rgb * back_wrap * diffuse_function()'
    for label, replacement in (('albedo', old), ('absolute-old', '* back_wrap * .22 * diffuse_function()'),
                               ('albedo-half', '* base_color.rgb * back_wrap * .5 * diffuse_function()')):
        for node, number, state, attrib in items:
            shader = attrib.getShader()
            key = shader.this, label
            if key not in shaders:
                fragment = shader.getText(Shader.STFragment)
                assert old in fragment, node.getName()
                shaders[key] = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex),
                                           fragment.replace(old, replacement))
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(shaders[key], 100), 100))
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert all(not shader.getErrorFlag() for shader in shaders.values())
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('transmission-' + label + '.png'))))
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)


def inspect_rock_normals(app, output):
    """核对中距离完整岩面法线与提前淡出方案，保持模型/镜位/太阳一致。"""
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName().startswith('kcd-sandstone-') for number in range(node.node().getNumGeoms())]
    source = items[0][3].getShader()
    assert all(attrib.getShader() == source for _node, _number, _state, attrib in items)
    fragment = source.getText(Shader.STFragment)
    old = 'float visible=1.;'
    assert old in fragment
    faded = 'float visible=1.-smoothstep(20.,80.,length(v_world_position-camera_world_position));'
    changed = Shader.make(Shader.SLGLSL, source.getText(Shader.STVertex), fragment.replace(old, faded))
    for node, number, state, attrib in items:
        node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed, 100), 100))
    for _ in range(12):
        app.taskMgr.step()
    app.graphicsEngine.syncFrame()
    assert not changed.getErrorFlag()
    app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / 'rock-faded-normal.png')))
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)


def inspect_canopy_shadows(app, output):
    """在正常镜位比较树冠阴影覆盖与深度偏移；计时包含GPU回读，仅作静态诊断。"""
    from kcd_local_environment import CANOPY_SHADOW_LEAD

    sun_path = app.scene.sun_path
    sun = sun_path.node()
    original_transform, original_film = sun_path.getTransform(), sun.getLens().getFilmSize()
    original_state = app.scene.render.getState()
    heading = math.radians(app.session.current.player.heading)
    forward = Vec3(-math.sin(heading), math.cos(heading), 0)
    app.taskMgr.remove('render-frame-pacing')
    results = []
    for span, lead, bias in ((180, 40, .0007), (240, 60, .0007), (320, 80, .0007),
                              (320, 80, .0003), (320, 80, .00015)):
        sun.getLens().setFilmSize(span, span)
        sun_path.setTransform(original_transform)
        sun_path.setPos(sun_path.getPos() + forward * (lead - CANOPY_SHADOW_LEAD))
        app.scene.render.setShaderInput('global_shadow_bias', bias)
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        label = str(span) + '-bias-' + str(round(bias * 100000))
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('canopy-' + label + '.png'))))
        samples = []
        for _ in range(16):
            start = time.perf_counter()
            app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            app.win.getScreenshot()
            samples.append((time.perf_counter() - start) * 1000)
        results.append({'span_m': span, 'lead_m': lead, 'bias': bias,
                        'median_ms': float(np.median(samples)), 'p95_ms': float(np.percentile(samples, 95))})
    sun.getLens().setFilmSize(original_film)
    sun_path.setTransform(original_transform)
    app.scene.render.setState(original_state)
    app.taskMgr.add(app.pace_frame, 'render-frame-pacing', sort=-100)
    (output / 'canopy-shadows.json').write_text(json.dumps({
        'scope': '冻结120m正常随车镜位；关闭工具限帧并包含GPU回读，不是实时性能Gate',
        'variants': results}, ensure_ascii=False, indent=2), encoding='utf-8')


def inspect_ground_match(app, output):
    """同镜位比较裸地与草层的有效亮度，防止草层渐隐后露出一整片浅色地毯。"""
    output.mkdir()
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName() in ('course-landscape', 'route-landscape')
             for number in range(node.node().getNumGeoms())]
    for factor in (.6, .75, 1.):
        shaders = []
        for node, number, state, attrib in items:
            shader = attrib.getShader()
            fragment = shader.getText(Shader.STFragment).replace(
                'const float ground_grass_albedo_scale=.6;',
                'const float ground_grass_albedo_scale=' + str(factor) + ';')
            changed = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
            shaders.append(changed)
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed, 100), 100))
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert all(not shader.getErrorFlag() for shader in shaders)
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / (str(round(factor * 100)) + '.png'))))
        for node, number, state, _attrib in items:
            node.node().setGeomState(number, state)


def inspect_woodland_cover(app, output):
    """冻结普通镜位直接输出GPU覆盖值，并单列无草材质，避免把不可见的RAM数据当效果。"""
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName() in ('course-landscape', 'route-landscape')
             for number in range(node.node().getNumGeoms())]
    assert items, '未找到实际地表材质'
    grass = tuple(app.scene.render.findAllMatches('**/local-kcd-grass-distance'))
    for path in grass:
        path.hide()
    for label in ('floor', 'coverage'):
        if label == 'coverage':
            for node, number, state, attrib in items:
                shader = attrib.getShader()
                original = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
                fragment = shader.getText(Shader.STFragment)
                assert original in fragment
                fragment = fragment.replace(original, 'o_color = vec4(vec3(woodland_cover(v_world_position.xy)),1.);')
                changed = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
                node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed, 100), 100))
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('woodland-' + label + '.png'))))
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)
    for path in grass:
        path.show()
    report = []
    for index, path in app.scene.segment_nodes.items():
        texture, _bounds = path.getPythonTag('woodland-coverage')
        values = np.frombuffer(texture.getRamImage(), dtype=np.uint8)
        report.append({'segment': index, 'size': [texture.getXSize(), texture.getYSize()],
                       'min': int(values.min()), 'max': int(values.max()), 'mean': float(values.mean())})
    (output / 'woodland-coverage.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


def inspect_grass_field(app, output):
    """固定随车镜位检查地被宏观分布和草叶受光，保存原状态后逐项还原。"""
    from collections import Counter

    names = Counter(node.getName() for node in app.scene.render.findAllMatches('**/+GeomNode'))
    (output / 'grass-node-names.json').write_text(json.dumps(names, indent=2), encoding='utf-8')
    texture_report = {}
    for name in ('local_ground_dry', 'local_ground_meadow'):
        texture = app.scene.render.getShaderInput(name).getTexture()
        assert app.graphicsEngine.extractTextureData(texture, app.win.getGsg())
        levels = []
        for level in range(texture.getNumRamMipmapImages()):
            pixels = np.frombuffer(texture.getRamMipmapImage(level), dtype=np.uint8)
            green = pixels.reshape(-1, texture.getNumComponents())[:, 1] / 255
            linear = np.where(green <= .04045, green / 12.92, ((green + .055) / 1.055)**2.4)
            levels.append({'level': level, 'encoded_g': np.percentile(green, [0, 10, 50, 90, 100]).tolist(),
                           'linear_g': np.percentile(linear, [0, 10, 50, 90, 100]).tolist()})
        texture_report[name] = {'format': texture.getFormat(), 'levels': levels}
    (output / 'grass-gpu-textures.json').write_text(json.dumps(texture_report, indent=2), encoding='utf-8')
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName().startswith(('kcd-stream-grass', 'course-landscape', 'route-landscape'))
             for number in range(node.node().getNumGeoms())]
    samples = {}
    for label in ('macro-field', 'albedo', 'source-normals', 'lower-transmission',
                  'dry-mip', 'constant-015', 'constant-05'):
        changed_shaders = []
        for node, number, state, attrib in items:
            shader = attrib.getShader()
            fragment = shader.getText(Shader.STFragment)
            if label in ('macro-field', 'albedo', 'dry-mip', 'constant-015', 'constant-05'):
                expression = {'macro-field': 'vec3(meadow_patch(v_world_position.xy))', 'albedo': 'base_color.rgb',
                              'dry-mip': 'vec3(textureLod(local_ground_dry,vec2(.5),6.).g)',
                              'constant-015': 'vec3(.15)', 'constant-05': 'vec3(.5)'}[label]
                fragment = fragment.replace('o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);',
                                            'o_color = vec4(' + expression + ', color.a);')
            elif node.getName().startswith('kcd-stream-grass'):
                if label == 'source-normals':
                    fragment = fragment.replace('mix(.88,.62,grass_growth)*smoothstep(8.,25.,grass_distance)', '0.')
                    fragment = fragment.replace('float detail_weight = 1.-smoothstep(12.,38.,length(v_world_position-camera_world_position));',
                                                'float detail_weight = 1.;')
                else:
                    fragment = fragment.replace('* base_color.rgb * back_wrap * diffuse_function()',
                                                '* base_color.rgb * back_wrap * .5 * diffuse_function()')
            changed = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
            changed_shaders.append(changed)
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed, 100), 100))
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert all(not shader.getErrorFlag() for shader in changed_shaders), label
        picture = app.win.getScreenshot()
        picture.write(Filename.fromOsSpecific(str(output / ('grass-' + label + '.png'))))
        pixels = PNMImage()
        assert picture.store(pixels)
        samples[label] = list(pixels.getXel(1300, 400))
        for node, number, state, _attrib in items:
            node.node().setGeomState(number, state)
    (output / 'grass-gpu-calibration.json').write_text(json.dumps(samples, indent=2), encoding='utf-8')


def inspect_foliage_distance(app, output):
    """固定正常镜位，区分叶面法线提前淡出与模型距离档；帧时仅为静态诊断。"""
    lods = [node for node in app.scene.render.findAllMatches('**/+LODNode')
            if node.getName().startswith('kcd-oak-')]
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName().startswith('kcd-oak-')
             for number in range(node.node().getNumGeoms())]
    results = []
    for label, normals, high_lod in (('current', False, False), ('leaf-normal', True, False),
                                      ('leaf-normal-lod0', True, True)):
        if normals:
            for node, number, state, attrib in items:
                shader = attrib.getShader()
                fragment = shader.getText(Shader.STFragment).replace(
                    'float detail_weight = 1.-smoothstep(12.,38.,length(v_world_position-camera_world_position));',
                    'float detail_weight = 1.;')
                changed = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
                node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed, 100), 100))
        if high_lod:
            for node in lods:
                node.node().forceSwitch(0)
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('foliage-' + label + '.png'))))
        elapsed = []
        for _ in range(24):
            start = time.perf_counter()
            app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            elapsed.append((time.perf_counter() - start) * 1000)
        results.append({'variant': label, 'frame_ms_median': float(np.median(elapsed)),
                        'frame_ms_p95': float(np.percentile(elapsed, 95))})
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)
    for node in lods:
        node.node().clearForceSwitch()
    sun_path = app.scene.sun_path
    sun = sun_path.node()
    lens, transform = sun.getLens(), sun_path.getTransform()
    film, shadow_size = lens.getFilmSize(), sun.getShadowBufferSize()
    sun.setShadowCaster(True, 4096, 4096)
    lens.setFilmSize(180, 180)
    sun_path.setPos(sun_path.getPos() + app.camera.getQuat().getForward() * 40)
    for _ in range(16):
        app.taskMgr.step()
    app.graphicsEngine.syncFrame()
    app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / 'foliage-medium-shadows.png')))
    elapsed = []
    for _ in range(24):
        start = time.perf_counter()
        app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        elapsed.append((time.perf_counter() - start) * 1000)
    results.append({'variant': 'medium-shadows', 'frame_ms_median': float(np.median(elapsed)),
                    'frame_ms_p95': float(np.percentile(elapsed, 95))})
    sun.setShadowCaster(True, shadow_size.x, shadow_size.y)
    lens.setFilmSize(film)
    sun_path.setTransform(transform)
    (output / 'foliage-distance.json').write_text(json.dumps({
        'scope': '冻结120m正常随车镜位的24帧诊断，不是实时性能Gate', 'variants': results},
        ensure_ascii=False, indent=2), encoding='utf-8')


def inspect_sun_balance(app, output, parameters):
    """同一正常随车快照只改太阳强度，保留镜位/天空/物理，用于选择晴天光比。"""
    from kcd_local_environment import sun_color

    sun, rail = app.scene.sun_path.node(), app.scene.rail_sun_path.node()
    original_sun, original_rail = LColor(sun.getColor()), LColor(rail.getColor())
    source = sun_color(parameters)
    for factor in (.5, .65, .8, 1.):
        color = tuple(value * factor for value in source[:3]) + (1.,)
        sun.setColor(color)
        rail.setColor(color)
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        path = output / ('sun-' + str(round(factor * 100)) + '.png')
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(path)))
    sun.setColor(original_sun)
    rail.setColor(original_rail)
    # 使用已认可晴空原本的太阳方位作构图对照，探针/天空图像及光强均不变。
    sun_path, rail_path = app.scene.sun_path, app.scene.rail_sun_path
    original_transform, original_rail_transform = sun_path.getTransform(), rail_path.getTransform()
    source_direction = Vec3(*(float(value) for value in parameters['lighting']['SunVector'].split(',')))
    center = sun_path.getPos() + source_direction * 156.25
    direction = Vec3(55, 75, -125).normalized()
    sun_path.setPos(center - direction * 156.25)
    sun_path.lookAt(center)
    rail_path.setTransform(sun_path.getTransform())
    for _ in range(12):
        app.taskMgr.step()
    app.graphicsEngine.syncFrame()
    app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / 'sun-approved-sky-direction.png')))
    sun_path.setTransform(original_transform)
    rail_path.setTransform(original_rail_transform)


def inspect_materials(app, output, *, driving_view=False):
    """逐分量输出原件草木的实际GPU材质，区分贴图、直射漫反射与高光。"""
    app.aspect2d.hide()
    if not driving_view:
        app.camera.setPos(-9, 19, 18.)
        app.camera.lookAt(-27, 32, 16.1)
    nodes = [node for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName().startswith(('kcd-oak-', 'kcd-stream-grass', 'course-landscape', 'route-landscape'))]
    # flattenStrong将材质状态下推到单个Geom；只读Node状态会误用父级通用着色器。
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib).getShader())
             for node in nodes for number in range(node.node().getNumGeoms())]
    for name, expression in {
        'base': 'base_color.rgb',
        'direct-diffuse': 'local_direct_diffuse',
        'direct-specular': 'local_direct_specular',
        'indirect': '(ibl_kd*ibl_diff+ibl_spec)*ambient_occlusion',
        'indirect-diffuse': 'ibl_kd*ibl_diff*ambient_occlusion',
        'indirect-specular': 'ibl_spec*ambient_occlusion',
        'normal': 'world_normal*.5+.5',
    }.items():
        for node, number, state, shader in items:
            frag = shader.getText(Shader.STFragment)
            frag = frag.replace('vec4 color = vec4(vec3(0.0), base_color.a);',
                                'vec4 color = vec4(vec3(0.0), base_color.a);\n'
                                'vec3 local_direct_diffuse=vec3(0),local_direct_specular=vec3(0);')
            frag = frag.replace('color.rgb += func_params.n_dot_l * lightcol * (diffuse_contrib + spec_contrib) * shadow;',
                                'local_direct_diffuse += func_params.n_dot_l * lightcol * diffuse_contrib * shadow;\n'
                                'local_direct_specular += func_params.n_dot_l * lightcol * spec_contrib * shadow;')
            frag = frag.replace('o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);',
                                'o_color = vec4(' + expression + ', color.a);')
            debug = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), frag)
            inputs = node.getNetState().compose(state).getAttrib(ShaderAttrib)
            node.node().setGeomState(number, state.setAttrib(inputs.setShader(debug, 100), 100))
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('material-' + name + '.png'))))
        for node, number, state, _shader in items:
            node.node().setGeomState(number, state)
    app.aspect2d.show()


def inspect_lighting(app, output):
    scene = app.scene
    app.aspect2d.hide()
    app.camera.setPos(-9, 19, 18.)
    app.camera.lookAt(-27, 32, 16.1)
    scene.sky.setPos(app.camera.getPos())
    scene.update_lighting(app.camera.getPos())
    sun = scene.sun_path.node()
    ambient = scene.ambient_path.node()
    sun_color, ambient_color = LColor(sun.getColor()), LColor(ambient.getColor())
    coefficients = scene.expressway_kit['daylight-environment'].sh_coefficients
    empty = PTALVecBase3f.emptyArray(9)
    for index in range(9):
        empty[index] = Vec3(0)
    report = {'sun_transform': str(scene.sun_path.getTransform()),
              'sun_color': list(sun_color), 'ambient_color': list(ambient_color),
              'shadow_camera_mask': str(sun.getCameraMask())}

    def image(name):
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('lighting-' + name + '.png'))))

    image('all')
    buffer = sun.getShadowBuffer(app.win.getGsg())
    report['shadow_buffer'] = None if buffer is None else str(buffer)
    if buffer is not None:
        texture = buffer.getTexture()
        app.graphicsEngine.extractTextureData(texture, app.win.getGsg())
        report['depth_texture'] = str(texture)
        raw = np.asarray(texture.getRamImage())
        # Panda的RAM深度回读可能提升为32位整数，不能把整型位模式当浮点。
        dtype = np.uint32 if len(raw) == texture.getXSize() * texture.getYSize() * 4 else np.uint16
        depth = raw.view(dtype) / np.iinfo(dtype).max
        report['depth_range'] = [float(depth.min()), float(depth.max())]
        report['nonempty_fraction'] = float(np.mean(depth < .999))
        preview = PNMImage()
        texture.store(preview)
        preview.write(Filename.fromOsSpecific(str(output / 'shadow-depth.png')))
    sun.setColor((0, 0, 0, 1))
    image('indirect-only')
    scene.render.setShaderInput('sh_coeffs', empty)
    ambient.setColor((0, 0, 0, 1))
    image('reflection-only')
    sun.setColor(sun_color)
    image('direct-reflection')
    # 同一地面直接输出法线、入射角和GPU实际收到的光强，排除亮度曲线的干扰。
    terrain = tuple(scene.render.findAllMatches('**/course-landscape'))
    original_states = tuple(node.getState() for node in terrain)
    shader = scene.expressway_kit['route-terrain-shader']
    fragment = shader.getText(Shader.STFragment)
    diagnostics = {
        'world-normal': 'vec4(world_normal*.5+.5,1.)',
        'sun-angle': 'vec4(vec3(max(dot(n,normalize(p3d_LightSource[0].position.xyz-v_view_position*p3d_LightSource[0].position.w)),0.)),1.)',
        'gpu-sun': 'vec4(p3d_LightSource[0].diffuse.rgb/10.,1.)',
        'gpu-shadow': 'vec4(vec3(shadow_caster_contrib(p3d_LightSource[0].shadowMap,v_shadow_pos[0])),1.)',
    }
    report['terrain_nodes'] = [node.getName() for node in terrain]
    for name, expression in diagnostics.items():
        changed = fragment.replace('o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);',
                                   'o_color = ' + expression + ';')
        debug = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), changed)
        for node in terrain:
            node.setShader(debug, 20)
        image(name)
    for node, state in zip(terrain, original_states, strict=True):
        node.setState(state)
    scene.render.setShaderInput('sh_coeffs', coefficients)
    ambient.setColor(ambient_color)
    previous = app.pipeline.exposure
    app.pipeline.exposure = -2
    image('minus-two-stops')
    app.pipeline.exposure = previous
    attrib = sun.getInitialState().getAttrib(ShaderAttrib)
    report['shadow_shader_error'] = attrib.getShader().getErrorFlag()
    (output / 'lighting-diagnostics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    app.aspect2d.show()
