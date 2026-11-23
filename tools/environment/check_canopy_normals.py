"""固定原追车镜位，比较原叶片朝向、双面处理和树冠大形候选。"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from check_driving_composition import check
from local_kcd_drive import tree_shader
from panda3d.core import Filename, Shader, ShaderAttrib


def glsl_vector(values):
    return 'vec3('+','.join(str(float(v)) for v in values)+')'


def compare(app, output):
    templates = app.scene.expressway_kit['local-kcd-trees']
    shapes = {}
    for tree in templates:
        low, high = tree.getTightBounds(tree)
        center = ((low.x+high.x)*.5, (low.y+high.y)*.5, high.z*.6)
        radius = ((high.x-low.x)*.5, (high.y-low.y)*.5, high.z*.4)
        shapes[tree.getName()] = center, radius
    items = []
    for node in app.scene.render.findAllMatches('**/+GeomNode'):
        if not node.getName().startswith('kcd-oak-'):
            continue
        key = node.getName().split('_lod')[0]
        for number in range(node.node().getNumGeoms()):
            state = node.node().getGeomState(number)
            attrib = node.getNetState().compose(state).getAttrib(ShaderAttrib)
            items.append((node, number, state, attrib, shapes[key]))
    for tree in app.scene.render.findAllMatches('**/+FadeLODNode'):
        tree.node().setFadeTime(0.)
    rows, frames = [], []
    baseline_shader = tree_shader(app.scene.expressway_kit['foliage-shader'], filtered_shadows=False)
    for label, unflip, strength, filter_radius in (
            ('current', False, 0., 0.), ('pcf-1', False, 0., 1.), ('pcf-2', False, 0., 2.),
            ('crown-70-pcf-1', True, .7, 1.), ('current-repeat', False, 0., 0.)):
        changed = {}
        for node, number, state, attrib, shape in items:
            key = attrib.getShader(), shape
            if key not in changed:
                shader = baseline_shader
                vertex, fragment = shader.getText(Shader.STVertex), shader.getText(Shader.STFragment)
                if filter_radius:
                    original = 'return mix(1.0, texture(shadowmap, p), coverage);'
                    assert original in fragment
                    fragment = fragment.replace(original, '''
    vec2 texel=1./vec2(textureSize(shadowmap,0));
    float filtered=0.;
    for(int y=-1;y<=1;y++) for(int x=-1;x<=1;x++) {
        float weight=(x==0?2.:1.)*(y==0?2.:1.);
        filtered+=weight*texture(shadowmap,vec3(p.xy+vec2(x,y)*texel*'''+str(filter_radius)+''',p.z));
    }
    return mix(1.,filtered/16.,coverage);
''')
                if unflip:
                    original = 'vec3 n = normalize(geometric_normal) * (gl_FrontFacing ? 1. : -1.);'
                    assert original in fragment
                    fragment = fragment.replace(original,
                        'vec3 n = normalize(geometric_normal) * '
                        '((gl_FrontFacing || texture(local_transmission,v_texcoord).r>.001) ? 1. : -1.);')
                if strength:
                    center, radius = shape
                    vertex = vertex.replace('void main() {', 'uniform sampler2D local_transmission;\nvoid main() {')
                    normal = 'vec3 model_normal = p3d_Normal;'
                    assert normal in vertex
                    vertex = vertex.replace(normal, normal + '\nvec3 crown=normalize((p3d_Vertex.xyz-'
                        +glsl_vector(center)+')/('+glsl_vector(radius)+'*'+glsl_vector(radius)+'));\n'
                        'float leaf=textureLod(local_transmission,(p3d_TextureMatrix*vec4(p3d_MultiTexCoord0,0,1)).xy,0.).r;\n'
                        'model_normal=normalize(mix(model_normal,crown,'+str(strength)+'*leaf));')
                changed[key] = Shader.make(Shader.SLGLSL, vertex, fragment)
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed[key], 2), 2))
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        assert all(not shader.getErrorFlag() for shader in changed.values()), label
        picture = app.win.getScreenshot()
        picture.write(Filename.fromOsSpecific(str(output / (label+'.png'))))
        frames.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
        texture = app.scene.sun_path.node().getShadowBuffer(app.win.getGsg()).getTexture()
        assert app.graphicsEngine.extractTextureData(texture, app.win.getGsg())
        rows.append({'variant': label, 'unflip_leaves': unflip, 'crown_strength': strength,
                     'shadow_filter_radius_texels': filter_radius,
                     'shadow_sha256': hashlib.sha256(texture.getRamImage()).hexdigest()})
    for node, number, state, _attrib, _shape in items:
        node.node().setGeomState(number, state)
    differences = []
    for index in range(1, len(frames)):
        delta = np.abs(frames[0].astype(np.int16)-frames[index])
        differences.append({'variant': rows[index]['variant'], 'max_rgb8': int(delta.max()),
                            'changed_channels': int(np.count_nonzero(delta)), 'mean_rgb8': float(delta.mean())})
    report = {'scope': '沿海120m原随车镜位；仅大橡树候选，0/40/70为本项目选型，非原引擎参数；没有改变源网格或太阳投影',
              'geometry_entries': len(items), 'variants': rows, 'differences_from_current': differences}
    (output/'canopy-normals.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert len({row['shadow_sha256'] for row in rows}) == 1, report
    assert np.array_equal(frames[0], frames[-1]), report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve(), False, (1440, 810), end_distance=120, inspect_at_120=compare, hd2_rocks=True)
