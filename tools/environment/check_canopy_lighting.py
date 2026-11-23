"""固定实际随车镜位，直接读回HDR树冠光照分量与受光消融。"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from check_driving_composition import check
from panda3d.core import Filename, Shader, ShaderAttrib


def compare(app, output):
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName().startswith(('kcd-oak-', 'kcd-young-oak-', 'kcd-hawthorn-'))
             for number in range(node.node().getNumGeoms())]
    for tree in app.scene.render.findAllMatches('**/+FadeLODNode'):
        tree.node().setFadeTime(0.)
    scene_texture = app.pipeline._post_process_quad.getShaderInput('tex').getTexture()
    direct = 'color.rgb += func_params.n_dot_l * lightcol * (diffuse_contrib + spec_contrib) * shadow;'
    transmission = '''color.rgb += lightcol * local_transmittance_color * local_back_diffuse * transmission
                   * base_color.rgb * back_wrap * diffuse_function() * shadow;'''
    output_line = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
    mask, rows, arrays = None, [], {}
    for label in ('mask', 'current', 'direct', 'transmission', 'sky-diffuse', 'sky-transmission', 'specular', 'ambient',
                  'shadow', 'no-shadow', 'no-sky-occlusion', 'double-sky-diffuse', 'no-transmission',
                  'sky-transmission-half', 'sky-transmission-one', 'sky-transmission-two'):
        changed = {}
        for node, number, state, attrib in items:
            shader = attrib.getShader()
            if shader not in changed:
                fragment = shader.getText(Shader.STFragment)
                if label.startswith('sky-transmission-'):
                    factor = {'sky-transmission-half': '.5', 'sky-transmission-one': '1.',
                              'sky-transmission-two': '2.'}[label]
                    fragment = fragment.replace('uniform float local_sky_transmission;',
                                                'const float local_sky_transmission=' + factor + ';')
                assert direct in fragment and transmission in fragment and output_line in fragment
                fragment = fragment.replace('vec4 color = vec4(vec3(0.0), base_color.a);',
                    'vec4 color = vec4(vec3(0.0), base_color.a);\n'
                    'vec3 diagnostic_direct=vec3(0),diagnostic_transmission=vec3(0),diagnostic_specular=vec3(0),diagnostic_sky=vec3(0);\n'
                    'float diagnostic_shadow=1.;')
                fragment = fragment.replace(direct, direct + '''
diagnostic_direct += func_params.n_dot_l*lightcol*diffuse_contrib*shadow;
diagnostic_specular += func_params.n_dot_l*lightcol*spec_contrib*shadow;
diagnostic_shadow = shadow_caster;
''')
                fragment = fragment.replace(transmission, transmission + '''
diagnostic_transmission += lightcol*local_transmittance_color*local_back_diffuse*transmission
                        *base_color.rgb*back_wrap*diffuse_function()*shadow;
''')
                sky = '''color.rgb += opposite_sky*base_color.rgb*local_transmittance_color
                   *texture(local_transmission,v_texcoord).r*local_back_diffuse
                   *diffuse_function()*ambient_occlusion*local_sky_transmission;'''
                assert sky in fragment
                fragment = fragment.replace(sky, sky + sky.replace('color.rgb', 'diagnostic_sky'))
                expressions = {'mask': 'vec3(3.,length(v_world_position-camera_world_position),7.)',
                    'direct': 'diagnostic_direct', 'transmission': 'diagnostic_transmission',
                    'sky-diffuse': 'ibl_kd*ibl_diff*ambient_occlusion',
                    'sky-transmission': 'diagnostic_sky',
                    'specular': 'diagnostic_specular+ibl_spec*ambient_occlusion',
                    'ambient': '(diffuse_color+spec_color)*p3d_LightModel.ambient.rgb*ambient_occlusion',
                    'shadow': 'vec3(diagnostic_shadow)'}
                if label in expressions:
                    fragment = fragment.replace(output_line, 'o_color=vec4(' + expressions[label] + ',1.);')
                elif label == 'no-shadow':
                    fragment = fragment.replace('return mix(1.0, texture(shadowmap, p), coverage);', 'return 1.;')
                elif label == 'no-sky-occlusion':
                    fragment = fragment.replace('mix(1.,v_color.r,local_canopy_occlusion)', '1.')
                elif label == 'double-sky-diffuse':
                    fragment = fragment.replace('ibl_kd * ibl_diff  + ibl_spec', 'ibl_kd * ibl_diff * 2. + ibl_spec')
                elif label == 'no-transmission':
                    fragment = fragment.replace(transmission, '')
                changed[shader] = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed[shader], 100), 100))
        for _ in range(8):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        assert all(not shader.getErrorFlag() for shader in changed.values()), label
        assert app.graphicsEngine.extractTextureData(scene_texture, app.win.getGsg())
        dtype = {2: np.float16, 4: np.float32}[scene_texture.getComponentWidth()]
        values = np.frombuffer(scene_texture.getRamImageAs('RGBA'), dtype=dtype).reshape(
            scene_texture.getYSize(), scene_texture.getXSize(), 4).astype(np.float32)
        assert np.all(np.isfinite(values)), label
        if label == 'mask':
            mask = ((np.abs(values[:, :, 0]-3.) < .01) & (np.abs(values[:, :, 2]-7.) < .01)
                    & (values[:, :, 1] >= 10) & (values[:, :, 1] <= 150))
            assert np.count_nonzero(mask) > 1000
            arrays['mask'] = mask
        else:
            rgb = values[:, :, :3][mask]
            luminance = rgb @ np.array([.2126, .7152, .0722])
            rows.append({'variant': label, 'linear_rgb_mean': rgb.mean(axis=0).tolist(),
                         'linear_luminance_mean': float(luminance.mean()),
                         'linear_luminance_p10_50_90': np.percentile(luminance, [10, 50, 90]).tolist()})
            arrays[label] = values[:, :, :3].astype(np.float16)
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('canopy-light-' + label + '.png'))))
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)
    report = {'scope': '沿海120m原随车镜位；10–150m可见树木（含树干）像素的色调映射前HDR分量/消融；不是物理照度复原或性能Gate',
              'sampled_pixels': int(np.count_nonzero(mask)), 'hdr_format': scene_texture.getFormat(),
              'geometry_entries': len(items), 'variants': rows,
              'vertex_shader_sha256': hashlib.sha256(items[0][3].getShader().getText(Shader.STVertex).encode()).hexdigest()}
    (output / 'canopy-lighting.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez_compressed(output / 'canopy-linear-components.npz', **arrays)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve(), False, (1280, 720), end_distance=120, inspect_at_120=compare)
