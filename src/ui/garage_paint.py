"""车库车漆透明面层；只扩展锁定版本PBR，不影响道路着色或车辆硬件。"""

from functools import lru_cache

from panda3d.core import Shader
from simplepbr._shaderutils import _load_shader_str

from paths import resource_root


@lru_cache(maxsize=2)
def garage_paint_shader(use_330):
    defines = {'MAX_LIGHTS': 1, 'USE_330': use_330}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    layer = (resource_root()/'assets/game/shaders/garage-clearcoat.glsl').read_text(encoding='utf-8')
    changes = {
        'void main() {': layer+'\nvoid main() {',
        'float n_dot_v = clamp(abs(dot(n, v)), 0.0, 1.0);':
            'float n_dot_v = clamp(abs(dot(n, v)), 0.0, 1.0);\n    vec3 garage_coat_light = vec3(0.0);',
        'color.rgb += func_params.n_dot_l * lightcol * (diffuse_contrib + spec_contrib) * shadow;':
            'color.rgb += func_params.n_dot_l * lightcol * (diffuse_contrib + spec_contrib) * shadow;\n'
            '        garage_coat_light += garage_coat_direct(func_params, lightcol, shadow);',
        'color.rgb += emission;':
            'color.rgb += emission;\n    color.rgb = garage_coat_layer(color.rgb, n_dot_v, ibl_r, '
            'garage_coat_light, ambient_occlusion);',
    }
    for original, replacement in changes.items():
        if fragment.count(original) != 1:
            raise RuntimeError('车库透明漆需要锁定的simplepbr 0.13.1着色接口')
        fragment = fragment.replace(original, replacement)
    return Shader.make(Shader.SLGLSL, vertex, fragment)
