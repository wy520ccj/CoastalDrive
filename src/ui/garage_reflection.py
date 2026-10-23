"""复用实际车模的地面反射；只作用于车库展示。"""

from functools import lru_cache

from panda3d.core import (
    ColorWriteAttrib,
    CullFaceAttrib,
    DepthTestAttrib,
    Shader,
    TransparencyAttrib,
)
from simplepbr._shaderutils import _load_shader_str

from vehicle_visual import WHEEL_NAMES


@lru_cache(maxsize=2)
def reflection_shader(use_330):
    defines = {'MAX_LIGHTS': 1, 'USE_330': use_330}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    # 镜像几何仍接受地面上方的原光照，观察点则镜像到地面下方。
    changes = {
        'void main() {': 'uniform mat4 p3d_ViewMatrix;\n'
            'uniform mat4 p3d_ViewMatrixInverse;\nvoid main() {',
        'vec3 world_normal = normalize(v_world_tbn * normalmap);':
            'vec3 world_normal = normalize(v_world_tbn * normalmap);\n'
            '    world_normal.z = -world_normal.z;',
        'vec3 light_pos = p3d_LightSource[i].position.xyz - v_view_position * p3d_LightSource[i].position.w;':
            'vec4 reflected_light = p3d_ViewMatrixInverse * p3d_LightSource[i].position;\n'
            '        reflected_light.z = -reflected_light.z;\n'
            '        vec3 light_pos = (p3d_ViewMatrix * reflected_light).xyz - '
            'v_view_position * reflected_light.w;',
        'vec3 world_view = normalize(camera_world_position - v_world_position);':
            'vec3 world_view = normalize(vec3(camera_world_position.xy, -camera_world_position.z) - '
            'vec3(v_world_position.xy, -v_world_position.z));',
        'color.rgb += emission;': 'color.rgb += emission;\n'
            '    color.a *= 0.20 * (1.0 - smoothstep(0.0, 0.85, -v_world_position.z));',
    }
    for original, replacement in changes.items():
        if fragment.count(original) != 1:
            raise RuntimeError('车库反射需要锁定的simplepbr 0.13.1着色接口')
        fragment = fragment.replace(original, replacement)
    return Shader.make(Shader.SLGLSL, vertex, fragment)


@lru_cache(maxsize=2)
def reflection_depth_shader(use_330):
    vertex = _load_shader_str('simplepbr.vert', {'MAX_LIGHTS': 1, 'USE_330': use_330})
    fragment = ('#version 330\nout vec4 o_color;\nvoid main() { o_color = vec4(0); }'
                if use_330 else '#version 120\nvoid main() { gl_FragColor = vec4(0); }')
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def reflect_vehicle(root, scene, use_330):
    mirror = scene.attachNewNode('garage-floor-reflection')
    mirror.setScale(1, 1, -1)
    surface = root.copyTo(mirror)
    depth = root.copyTo(mirror)
    for copy in (surface, depth):
        highlight = copy.find('part-highlight')
        if not highlight.isEmpty():
            highlight.removeNode()
        for name in WHEEL_NAMES:
            copy.find(name).clearColorScale()
    # 镜像改变面序，反向剔除；源几何和源节点状态保持独立。
    mirror.setAttrib(CullFaceAttrib.makeReverse(), 3)
    # 先仅写最近表面的深度，再混合一次颜色，避免半透明车体透出内部网格。
    depth.setAttrib(ColorWriteAttrib.make(ColorWriteAttrib.COff), 4)
    depth.setTransparency(TransparencyAttrib.MNone, 4)
    depth.setDepthWrite(True, 4)
    depth.setBin('background', 1)
    depth.setShader(reflection_depth_shader(use_330), 4)
    surface.setTransparency(TransparencyAttrib.MAlpha, 3)
    surface.setDepthWrite(False)
    surface.setAttrib(DepthTestAttrib.make(DepthTestAttrib.MEqual), 3)
    surface.setBin('transparent', 0)
    surface.setShader(reflection_shader(use_330), 3)
    return mirror
