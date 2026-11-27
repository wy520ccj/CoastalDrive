"""独立高速与生涯赛道的地中海海岸地表三层 PBR、球壳平滑植被、风浪草甸、石灰岩与 4K 裁切阴影。"""

from __future__ import annotations

import math

from panda3d.core import (
    AlphaTestAttrib,
    BitMask32,
    Filename,
    PTALVecBase3f,
    Shader,
    ShaderAttrib,
    Texture,
    TransparencyAttrib,
    Vec3,
)

from environment.expressway_materials import add_distance_haze, add_shadow_transition
from paths import resource_root

SHADOW_MASK = BitMask32.bit(28)
CANOPY_SHADOW_SPAN = 320
CANOPY_SHADOW_LEAD = 45
DAYLIGHT_SH_SCALE = 0.90
DAYLIGHT_SUN_SCALE = 1.38
# 温暖明媚的地中海午后日光（暖金直射光 + 清澈天蓝环境光，拉出通透冷暖层次）。
_SUN_RGB = (0.268, 0.222, 0.172)
_SUN_LUX = 79963.62


MEADOW_COLOR = '''
uniform sampler2D local_ground_meadow;
uniform sampler2D local_ground_dry;
uniform float local_origin_y;
uniform sampler2D local_forest_coverage;
uniform vec4 local_forest_bounds;
float woodland_cover(vec2 position) {
    vec2 uv = (position+vec2(0.,local_origin_y)-local_forest_bounds.xy)*local_forest_bounds.zw;
    if (any(lessThan(uv,vec2(0.))) || any(greaterThan(uv,vec2(1.)))) return 0.;
    return textureLod(local_forest_coverage,uv,0.).r;
}
float meadow_patch(vec2 p) {
    p.y += local_origin_y;
    vec2 alternate = mat2(.8,-.6,.6,.8)*p*.016+vec2(.73,.19);
    float patch = mix(textureLod(local_ground_dry,p*.025+vec2(.31,.67),6.).g,
                      textureLod(local_ground_dry,alternate,6.).g,.35);
    return smoothstep(.13,.17,patch);
}
float meadow_dry_weight(vec2 p) {
    return mix(.06,.42,meadow_patch(p));
}
float meadow_growth(vec2 p) {
    p.y += local_origin_y;
    vec2 rotated = mat2(.93,-.37,.37,.93)*p*.041+vec2(.19,.83);
    float patch = mix(textureLod(local_ground_meadow,rotated,6.).g,
                      textureLod(local_ground_meadow,p*.019+vec2(.6,.2),6.).g,.25);
    return smoothstep(.059,.071,patch);
}
vec3 meadow_color(vec2 p,vec2 uv,float dry_weight) {
    float patch = textureLod(local_ground_meadow,(p+vec2(0.,local_origin_y))*.012,6.).g;
    float macro = mix(.72,1.16,smoothstep(.05,.085,patch));
    vec2 alternate = mat2(.8,-.6,.6,.8)*uv/1.37+vec2(.32,.57);
    vec3 pasture = mix(texture(local_ground_meadow,uv).rgb,
                       texture(local_ground_meadow,alternate).rgb,.4);
    return mix(pasture,
               texture(local_ground_dry,uv).rgb,dry_weight)*macro*mix(.88,1.08,meadow_growth(p));
}
vec3 meadow_color(vec2 p,vec2 uv) {
    return meadow_color(p,uv,meadow_dry_weight(p));
}
'''

TERRAIN_MATERIAL = MEADOW_COLOR + '''
const float ground_grass_albedo_scale=.56;
uniform vec2 city_lawn_phase;
float city_lawn_weight() {
    if (city_lawn_phase.y < .5) return 0.;
    float phase = mod(v_texcoord.y+city_lawn_phase.x,8000.);
    float town = smoothstep(3200.,3440.,phase)*(1.-smoothstep(6160.,6400.,phase));
    float zone = floor(phase/1600.);
    float shift = -24.;
    float bridge_local = v_texcoord.y+(mod(city_lawn_phase.x,1600.)-820.);
    if (bridge_local > 800.) bridge_local -= 1600.;
    if (bridge_local < -800.) bridge_local += 1600.;
    if (zone == 1. || zone == 3.) shift *= smoothstep(18.,75.,abs(bridge_local));
    float across = v_texcoord.x-shift;
    return town*smoothstep(61.5,68.5,across)*(1.-smoothstep(151.5,158.5,across));
}
float ground_dry_weight() {
    return meadow_dry_weight(v_world_position.xy)*(1.-city_lawn_weight());
}
uniform sampler2D expressway_rock;
uniform sampler2D pasture_normal;
uniform sampler2D pasture_gloss;
uniform sampler2D pasture_height;
uniform sampler2D forest_albedo;
uniform sampler2D forest_normal;
uniform sampler2D forest_gloss;
uniform sampler2D forest_height;
uniform sampler2D dry_normal;
uniform sampler2D dry_gloss;
uniform sampler2D dry_height;
float forest_weight() { return woodland_cover(v_world_position.xy)*.85; }
vec2 terrain_parallax_uv() {
    vec3 n = normalize(v_world_tbn[2]);
    vec3 dx = dFdx(v_world_position), dy = dFdy(v_world_position);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 t = normalize(cross(dy,n)*ux.x + cross(n,dx)*uy.x);
    vec3 b = normalize(cross(dy,n)*ux.y + cross(n,dx)*uy.y);
    vec3 eye = normalize(camera_world_position-v_world_position);
    float w = forest_weight();
    float height = mix(mix(texture(pasture_height,v_texcoord*.25).r,
                          texture(dry_height,v_texcoord*.25).r,ground_dry_weight()),
                       texture(forest_height,v_texcoord*.25).r,w)-.5;
    return v_texcoord - vec2(dot(eye,t),dot(eye,b)) / max(dot(eye,n),.38)
                           * height * mix(.030,.024,w)*mix(1.,.25,city_lawn_weight());
}
vec4 expressway_albedo() {
    vec2 p = terrain_parallax_uv();
    float w = forest_weight();
    vec3 pasture = meadow_color(v_world_position.xy,p*.5,ground_dry_weight());
    vec3 forest = texture(forest_albedo,p*.25).rgb*.58;
    vec3 base = mix(pasture*ground_grass_albedo_scale,forest,w);
    // 护栏外侧 8.5–10.8m 柔和砂砾碎石路缘过渡，避免草皮硬切混凝土底座。
    float verge_gravel = smoothstep(10.8, 8.6, abs(v_texcoord.x)) * (1. - city_lawn_weight()) * 0.52;
    vec3 gravel = texture(expressway_rock, p * 0.35).rgb * vec3(0.56, 0.52, 0.44);
    base = mix(base, gravel, verge_gravel);
    vec3 rock = texture(expressway_rock,vec2(p.y/5.,(v_world_position.z+p.x*.08)/3.)).rgb;
    return vec4(mix(base,rock*vec3(.74,.70,.62),v_color.a),1.0);
}
float terrain_roughness() {
    vec2 p = terrain_parallax_uv();
    float mip_footprint = length(fwidth(v_texcoord));
    float filter_amount = smoothstep(.08, .70, mip_footprint);
    float gloss = mix(mix(texture(pasture_gloss,p*.25).r,
                         texture(dry_gloss,p*.25).r,ground_dry_weight()),
                      texture(forest_gloss,p*.25).r,forest_weight());
    float roughness = clamp(1.0-gloss,.08,1.0);
    return mix(roughness, max(roughness, .92), filter_amount);
}
vec3 terrain_normal(vec3 geometric_normal,vec3 position) {
    vec3 n = normalize(geometric_normal);
    vec3 dx = dFdx(position),dy = dFdy(position);
    vec2 ux = dFdx(v_texcoord),uy = dFdy(v_texcoord);
    vec3 t = cross(dy,n)*ux.x + cross(n,dx)*uy.x;
    vec3 b = cross(dy,n)*ux.y + cross(n,dx)*uy.y;
    float magnitude = max(dot(t,t),dot(b,b));
    if (magnitude < 1e-16) return n;
    float mip_footprint = length(fwidth(v_texcoord));
    float detail_filter = 1.0 - smoothstep(.08, .70, mip_footprint);
    vec2 p = terrain_parallax_uv()*.25;
    float w = forest_weight();
    vec3 detail = mix(mix(texture(pasture_normal,p).rgb,
                         texture(dry_normal,p).rgb,ground_dry_weight()),
                      texture(forest_normal,p).rgb,w)*2.-1.;
    detail.xy *= mix(1.15,0.98,w)*mix(1.,.3,city_lawn_weight())*detail_filter;
    detail.z = max(detail.z, .01)*sqrt(magnitude);
    return normalize(mat3(t,b,n)*detail);
}
'''

MOUNTAIN_MATERIAL = '''
uniform sampler2D expressway_rock;
vec4 expressway_albedo() {
    vec3 normal = normalize(v_world_tbn[2]);
    vec3 w = pow(abs(normal),vec3(4.));
    w /= max(w.x+w.y+w.z,.0001);
    vec3 p = v_world_position/18.;
    vec3 stone = texture(expressway_rock,p.yz).rgb*w.x
               + texture(expressway_rock,p.xz).rgb*w.y
               + texture(expressway_rock,p.xy).rgb*w.z;
    vec3 meadow = texture(p3d_TextureBaseColor,v_texcoord/4.).rgb;
    float macro = texture(p3d_TextureBaseColor,v_texcoord/70.+vec2(.37,.61)).g;
    // 远山改为浓郁海岸松林绿 + 暖石灰岩断崖，不再发泥发灰。
    vec3 pine = mix(vec3(.045,.095,.038), vec3(.11,.17,.055), clamp(macro*4.5, 0., 1.));
    vec3 forest = mix(pine, meadow * vec3(.85,1.05,.65), 0.35) * (0.78 + 0.45 * v_color.g);
    float slope_rock = smoothstep(0.42, 0.72, 1.0 - normal.z);
    float rocky = clamp(max(v_color.a, slope_rock * 0.85) + (stone.r - 0.16) * 0.55, 0., 1.);
    vec3 rock = stone * vec3(.62,.58,.50);
    return vec4(mix(forest,rock,rocky),1.);
}
'''

FOLIAGE_DETAIL = '''
uniform sampler2D local_normal;
uniform sampler2D local_gloss;
uniform sampler2D local_transmission;
uniform vec3 local_transmittance_color;
uniform float local_back_diffuse;
uniform float local_normal_view_dependency;
uniform vec3 local_specular_color;
uniform float local_canopy_occlusion;
uniform float local_sky_transmission;
vec3 local_opposite_sky(vec3 normal,vec3 front) {
    return max(front-.977206*(sh_coeffs[1]*normal.x+sh_coeffs[2]*normal.z+sh_coeffs[3]*normal.y),0.);
}
vec3 local_view_normal(vec3 n,vec3 eye) {
    vec3 facing = eye * (dot(n,eye) < 0. ? -1. : 1.);
    return normalize(mix(n,facing,local_normal_view_dependency*texture(local_transmission,v_texcoord).r));
}
vec3 local_leaf_normal(vec3 geometric_normal, vec3 position) {
    // 保持烘焙球壳平滑法线为主，近距微混叶脉凹凸，彻底避免纸片明暗断层。
    vec3 n = normalize(geometric_normal);
    float detail_weight = 1.-smoothstep(10.,34.,length(v_world_position-camera_world_position));
    if (detail_weight <= 0.) return n;
    vec3 dx = dFdx(position), dy = dFdy(position);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 t = cross(dy,n)*ux.x + cross(n,dx)*uy.x;
    vec3 b = cross(dy,n)*ux.y + cross(n,dx)*uy.y;
    float magnitude = max(dot(t,t),dot(b,b));
    if (magnitude < 1e-16) return n;
    vec3 detail = texture(local_normal,v_texcoord).rgb*2.-1.;
    detail.z *= sqrt(magnitude);
    return normalize(mix(n,normalize(mat3(t,b,n)*detail),detail_weight*0.35));
}
'''


def source_texture(path, *, color: bool = False) -> Texture:
    texture = Texture(path.stem)
    if not texture.read(Filename.fromOsSpecific(str(path))):
        raise OSError(f"无法读取高速材质：{path}")
    if color:
        texture.setFormat(Texture.FSrgbAlpha if texture.getNumComponents() == 4 else Texture.FSrgb)
    texture.setWrapU(Texture.WMRepeat)
    texture.setWrapV(Texture.WMRepeat)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(8)
    return texture


def soft_cutout(node) -> None:
    """使用已有 4x MSAA 的 Alpha-to-Coverage，边缘柔化且保持深度写入。"""
    node.setTransparency(TransparencyAttrib.MMultisample, 3)
    node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MNone, 0.0), 3)


def vegetation_material(shader: Shader) -> Shader:
    """支持逐顶点植物色相（v_color.rgb）与独立深度树冠 AO（v_color.a）的球壳平滑植被材质。"""
    fragment = shader.getText(Shader.STFragment)
    fragment = fragment.replace("void main() {", FOLIAGE_DETAIL + "\nvoid main() {")
    # RGB 走逐树种/逐部位植物色相，Alpha 仅取贴图透明度（v_color.a 专供树冠深层 AO）。
    fragment = fragment.replace(
        "p3d_Material.baseColor * v_color * p3d_ColorScale *",
        "vec4(p3d_Material.baseColor.rgb * v_color.rgb * p3d_ColorScale.rgb, "
        "p3d_Material.baseColor.a * p3d_ColorScale.a) *",
    )
    fragment = fragment.replace(
        "float ambient_occlusion = 1.0;",
        "float canopy_ao = clamp((v_color.a - 0.45) / 0.55, 0.0, 1.0);\n"
        "    float ambient_occlusion = mix(1.0, mix(0.18, 1.0, canopy_ao), local_canopy_occlusion);",
    )
    fragment = fragment.replace(
        "p3d_Material.roughness * metal_rough.g",
        "max(.68,1.-texture(local_gloss,v_texcoord).r)",
    )
    fragment = fragment.replace(
        "vec3 spec_color = mix(F0, base_color.rgb, metallic);",
        "vec3 spec_color = mix(local_specular_color, base_color.rgb, metallic);",
    )
    fragment = fragment.replace(
        "if (base_color.a < foliage_alpha_cutoff) discard;",
        '''
float lod_alpha = p3d_ColorScale.a;
base_color.a /= max(lod_alpha,.0001);
float opacity_width = max(fwidth(base_color.a),.001);
float foliage_visibility = 1.;
if (base_color.a < foliage_alpha_cutoff) discard;
base_color.a = clamp((base_color.a-foliage_alpha_cutoff)/opacity_width+.5,0.,1.)*foliage_visibility*lod_alpha;
''',
    )
    fragment = fragment.replace(
        "vec3 ibl_f = fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness);",
        "vec3 ibl_f = mix(spec_color, "
        "fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness), .08);",
    )
    fragment = fragment.replace(
        "ibl_f * env_brdf.x + env_brdf.y",
        "ibl_f * env_brdf.x + env_brdf.y*.08",
    )
    fragment = fragment.replace(
        "normalize(v_view_tbn * normalmap)",
        "local_view_normal(local_leaf_normal(v_view_tbn[2],v_view_position), normalize(-v_view_position))",
    )
    fragment = fragment.replace(
        "normalize(v_world_tbn * normalmap)",
        "local_view_normal(local_leaf_normal(v_world_tbn[2],v_world_position), "
        "normalize(camera_world_position-v_world_position))",
    )
    fragment = fragment.replace(
        "func_params.n_dot_l = max(nl, 0.0) + max(-nl, 0.0)*0.35;",
        "float transmission = texture(local_transmission,v_texcoord).r;\n"
        "        // 球壳法线柔和包裹直射光，减少阴影交界硬折线。\n"
        "        func_params.n_dot_l = clamp((nl + 0.14) / 1.14, 0.0, 1.0);",
    )
    direct = "color.rgb += func_params.n_dot_l * lightcol * (diffuse_contrib + spec_contrib) * shadow;"
    fragment = fragment.replace(
        direct,
        direct
        + '''
        float back_wrap = clamp(.45-.55*nl,0.,1.);
        color.rgb += lightcol * local_transmittance_color * local_back_diffuse * transmission
                   * base_color.rgb * back_wrap * diffuse_function() * shadow;
''',
    )
    fragment = fragment.replace(
        "vec3 ibl_diff = base_color.rgb * max(irradiance_from_sh(world_normal), 0.0) * diffuse_function();",
        "vec3 local_sky_irradiance = irradiance_from_sh(world_normal);\n"
        "vec3 ibl_diff = base_color.rgb * max(local_sky_irradiance,0.) * diffuse_function();",
    )
    indirect = "color.rgb += (ibl_kd * ibl_diff  + ibl_spec) * ambient_occlusion;"
    fragment = fragment.replace(
        indirect,
        indirect
        + '''
    if (local_sky_transmission > 0.) {
        vec3 opposite_sky = local_opposite_sky(world_normal,local_sky_irradiance);
        color.rgb += opposite_sky*base_color.rgb*local_transmittance_color
                   *texture(local_transmission,v_texcoord).r*local_back_diffuse
                   *diffuse_function()*ambient_occlusion*local_sky_transmission;
    }
''',
    )
    return Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)


def rooted_vertex(vertex: str, position_line: str, position_name: str) -> str:
    vertex = vertex.replace("void main() {", "\nuniform float root_anchor;\nvoid main() {")
    return vertex.replace(
        position_line,
        position_line
        + f'''
vec2 root_slope = p3d_TextureMatrix[2].xy;
float root_blend = 1.0 - smoothstep(0.0, 2.0, p3d_Vertex.z + root_anchor);
{position_name}.z += root_blend * dot(root_slope, p3d_Vertex.xy);
''',
    )


def tree_shader(foliage: Shader, *, filtered_shadows: bool = True, fade_range=None) -> Shader:
    fragment = foliage.getText(Shader.STFragment)
    if filtered_shadows:
        fragment = fragment.replace(
            "return mix(1.0, texture(shadowmap, p), coverage);",
            '''
    vec2 texel = 2. / vec2(textureSize(shadowmap, 0));
    float filtered = 0.;
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
        float weight = (x == 0 ? 2. : 1.) * (y == 0 ? 2. : 1.);
        filtered += weight * texture(shadowmap, vec3(p.xy + vec2(x,y)*texel, p.z));
    }
    return mix(1., filtered/16., coverage);
''',
        )
    vertex = rooted_vertex(foliage.getText(Shader.STVertex), "vec4 model_position = p3d_Vertex;", "model_position")
    if fade_range is not None:
        start, end = fade_range
        vertex = vertex.replace(
            "void main() {",
            f'''
uniform vec3 camera_world_position;
flat out float understory_fade;
void main() {{
float understory_dist = length((p3d_ModelMatrix*vec4(0.,0.,0.,1.)).xyz-camera_world_position);
understory_fade = 1.-smoothstep({start:.1f},{end:.1f},understory_dist);
if (understory_fade <= .0001) {{
    gl_Position=vec4(2.,2.,2.,1.);
    return;
}}
''',
        )
        fragment = fragment.replace("void main() {", "flat in float understory_fade;\nvoid main() {")
        fragment = fragment.replace("float foliage_visibility = 1.;", "float foliage_visibility = understory_fade;")
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def grass_shader(foliage: Shader, *, coastal: bool = False) -> Shader:
    """4m 硬件实例化风浪草甸着色：海风波动摇曳 + 根部与地表无缝融合 + 海岸微野花保色。"""
    vertex = foliage.getText(Shader.STVertex)
    vertex = vertex.replace(
        "void main() {",
        MEADOW_COLOR
        + '''
uniform vec3 grass_floor00[80];
uniform vec3 grass_floor10[80];
uniform vec3 grass_floor01[80];
uniform vec3 grass_floor11[80];
uniform vec3 camera_world_position;
uniform float sea_time;
uniform sampler2D grass_heightfield;
uniform vec2 grass_grid_origin;
uniform float grass_surface_mode;
out float grass_height;
flat out float grass_growth;
flat out float grass_present;
flat out float grass_fade;
void main() {''',
    )
    vertex = vertex.replace(
        "vec4 model_position = p3d_Vertex;",
        '''
grass_height = p3d_Vertex.z;
vec2 cell_uv = (p3d_Vertex.xy + vec2(2.0)) / 4.0;
vec3 floor_position = mix(mix(grass_floor00[gl_InstanceID], grass_floor10[gl_InstanceID], cell_uv.x),
                          mix(grass_floor01[gl_InstanceID], grass_floor11[gl_InstanceID], cell_uv.x), cell_uv.y);
vec2 plant_uv = p3d_Color.rg;
vec3 plant_floor = mix(mix(grass_floor00[gl_InstanceID], grass_floor10[gl_InstanceID], plant_uv.x),
                       mix(grass_floor01[gl_InstanceID], grass_floor11[gl_InstanceID], plant_uv.x), plant_uv.y);
vec3 plant_world = (p3d_ModelMatrix*vec4(plant_floor,1.)).xyz;
float woodland = woodland_cover(plant_world.xy);
float dry = meadow_patch(plant_world.xy);
float family_weight = mix(1.-dry,dry,p3d_Color.b);
float distance_weight = 1.-smoothstep(140.,215.,length(plant_world-camera_world_position));
float woodland_density = mix(1.,.18,smoothstep(.35,.9,woodland));
vec2 cell_world = (p3d_ModelMatrix*vec4(grass_floor00[gl_InstanceID],1.)).xy + vec2(0.,local_origin_y);
float cell_seed = dot(floor(cell_world+vec2(.13)),vec2(127.1,311.7));
float plant_seed = fract(sin(cell_seed+p3d_Color.a*73.13)*43758.5453);
grass_fade = distance_weight;
grass_present = step(plant_seed,family_weight*woodland_density)*step(.0001,distance_weight);
if (grass_present < .5) {
    gl_Position = vec4(2.,2.,2.,1.);
    return;
}
grass_growth = meadow_growth(plant_world.xy);
float grass_vertical_scale = mix(.48,1.25,grass_growth)*mix(1.,.60,smoothstep(.25,.9,woodland));
grass_height *= mix(.85,1.18,dry)*grass_vertical_scale;
float wind_phase = plant_world.x * 0.20 + (plant_world.y + local_origin_y) * 0.14 + sea_time * 1.85;
float sway = (sin(wind_phase) * 0.65 + sin(wind_phase * 2.13 + 1.4) * 0.35) * (grass_height * grass_height) * 0.32;
vec4 model_position = vec4(floor_position + vec3(sway, sway * 0.45, p3d_Vertex.z*mix(.85,1.18,dry)*grass_vertical_scale), 1.0);''',
    )
    vertex = vertex.replace(
        "vec3 model_normal = p3d_Normal;",
        "vec3 model_normal = normalize(vec3(p3d_Normal.xy,p3d_Normal.z/(mix(.85,1.18,dry)*grass_vertical_scale)));",
    )
    vertex = vertex.replace(
        "vec4 view_position = p3d_ModelViewMatrix * model_position;",
        '''
if (grass_surface_mode > .5) {
    vec3 world_floor = (p3d_ModelMatrix*vec4(floor_position,1.)).xyz;
    vec2 grid = (world_floor.xy+vec2(0.,local_origin_y)-grass_grid_origin)/8.;
    ivec2 cell = ivec2(floor(grid));
    vec2 part = fract(grid);
    if (any(lessThan(cell,ivec2(0))) || any(greaterThanEqual(cell,textureSize(grass_heightfield,0)-1))) {
        grass_present = 0.;
    } else {
        float a = texelFetch(grass_heightfield,cell,0).r;
        float b = texelFetch(grass_heightfield,cell+ivec2(1,0),0).r;
        float c = texelFetch(grass_heightfield,cell+ivec2(1,1),0).r;
        float d = texelFetch(grass_heightfield,cell+ivec2(0,1),0).r;
        float z = part.x >= part.y ? a*(1.-part.x)+b*(part.x-part.y)+c*part.y
                                  : a*(1.-part.y)+c*part.x+d*(part.y-part.x);
        model_position.z += z-world_floor.z;
    }
}
vec4 view_position = p3d_ModelViewMatrix * model_position;''',
    )
    vertex = vertex.replace("v_color = p3d_Color;", "v_color = vec4(1.);")
    fragment = foliage.getText(Shader.STFragment).replace(
        "uniform float local_sky_transmission;", "const float local_sky_transmission=0.;"
    ).replace(
        "void main() {",
        "uniform mat4 p3d_ViewMatrix;\nin float grass_height;\n"
        "flat in float grass_present;\nflat in float grass_growth;\nflat in float grass_fade;\n"
        + MEADOW_COLOR
        + "\nvoid main() {",
    )
    fragment = fragment.replace("float foliage_visibility = 1.;", "float foliage_visibility = grass_fade;")
    fragment = fragment.replace(
        "if (base_color.a < foliage_alpha_cutoff) discard;",
        '''
float grass_distance = length(v_world_position - camera_world_position);
if (grass_present < .5) discard;
if (v_texcoord.x < 0.75) {
    vec3 ground_col = meadow_color(v_world_position.xy, (v_world_position.xy+vec2(0.,local_origin_y))*.5) * 0.56;
    // 根部高度无缝融入脚下草坡色，梢头保留温和日光草绿，杜绝高饱和荧光绿。
    float root_blend = 1.0 - smoothstep(0.0, 0.24, grass_height);
    float far_blend = 0.58 * smoothstep(8.0, 36.0, grass_distance);
    base_color.rgb = mix(base_color.rgb, ground_col, max(root_blend * 0.82, far_blend));
    base_color.rgb *= mix(0.74, 1.04, smoothstep(0.0, 0.32, grass_height));
}
if (base_color.a < foliage_alpha_cutoff) discard;''',
    )
    fragment = fragment.replace(
        "local_leaf_normal(v_view_tbn[2],v_view_position)",
        "normalize(mix(local_leaf_normal(v_view_tbn[2],v_view_position), "
        "normalize((p3d_ViewMatrix*vec4(0.,0.,1.,0.)).xyz), 0.78))",
    )
    fragment = fragment.replace(
        "local_leaf_normal(v_world_tbn[2],v_world_position)",
        "normalize(mix(local_leaf_normal(v_world_tbn[2],v_world_position), vec3(0.,0.,1.), 0.78))",
    )
    if coastal:
        vertex = vertex.replace("/8.;", "/2.;")
        vertex = vertex.replace(
            "mix(.48,1.25,grass_growth)*mix(1.,.60,smoothstep(.25,.9,woodland))",
            "mix(.48,1.25,grass_growth)*mix(1.,.60,smoothstep(.25,.9,woodland))*.55",
        )
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def rock_shader() -> Shader:
    """CC0 海岸岩岸/崖壁着色器：温和提亮暖灰岩色并在顶面自然过渡草苔，消除暗洞黑泥感。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {
        "MAX_LIGHTS": 1,
        "ENABLE_SHADOWS": True,
        "USE_330": True,
        "USE_NORMAL_MAP": True,
        "USE_OCCLUSION_MAP": True,
    }
    vertex = _load_shader_str("simplepbr.vert", defines.copy())
    fragment = _load_shader_str("simplepbr.frag", defines.copy())
    fragment = fragment.replace(
        "float ambient_occlusion = 1.0;",
        "float ambient_occlusion = 1.0;",
    )
    # 柔和提亮岩壁过深暗部并托底 AO，使其与前排暖石灰岩巨石色调自然统一
    fragment = fragment.replace(
        "ambient_occlusion = metal_rough.r;",
        "ambient_occlusion = max(metal_rough.r, 0.48);",
    )
    target = "vec3 diffuse_color = base_color.rgb * (vec3(1.0) - F0) * (1.0 - metallic);"
    replacement = (
        "vec3 rock_n = normalize(v_world_tbn[2]);\n"
        "    float rock_moss = smoothstep(0.54, 0.84, rock_n.z) * 0.58;\n"
        "    vec3 lifted_rock = mix(base_color.rgb * vec3(1.85, 1.75, 1.56) + vec3(0.055, 0.050, 0.042), "
        "vec3(0.11, 0.16, 0.055), rock_moss);\n"
        "    vec3 diffuse_color = lifted_rock * (vec3(1.0) - F0) * (1.0 - metallic);"
    )
    fragment = fragment.replace(target, replacement)
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


def boulder_shader() -> Shader:
    """闭合 3D 海岸石灰岩巨石着色器（屏幕导数切线法线 + 暖灰岩纹 + 顶面顶点苔藓与接地 AO）。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {"MAX_LIGHTS": 1, "ENABLE_SHADOWS": True, "USE_330": True}
    vertex = _load_shader_str("simplepbr.vert", defines.copy())
    fragment = _load_shader_str("simplepbr.frag", defines.copy())
    detail = '''
uniform sampler2D boulder_normal;
uniform sampler2D boulder_gloss;
vec3 limestone_normal(vec3 n, vec3 p) {
    n = normalize(n);
    vec3 dx = dFdx(p), dy = dFdy(p);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 t = cross(dy, n) * ux.x + cross(n, dx) * uy.x;
    vec3 b = cross(dy, n) * ux.y + cross(n, dx) * uy.y;
    float mag = max(dot(t, t), dot(b, b));
    if (mag < 1e-16) return n;
    vec3 det = texture(boulder_normal, v_texcoord).rgb * 2.0 - 1.0;
    det.xy *= 1.35;
    det.z = max(det.z, 0.05) * sqrt(mag);
    return normalize(mat3(t, b, n) * det);
}
'''
    fragment = fragment.replace("void main() {", detail + "\nvoid main() {")
    fragment = fragment.replace("p3d_Material.roughness * metal_rough.g", "max(0.68, 1.0 - texture(boulder_gloss, v_texcoord).r)")
    fragment = fragment.replace("normalize(v_view_tbn * normalmap)", "limestone_normal(v_view_tbn[2], v_view_position)")
    fragment = fragment.replace("normalize(v_world_tbn * normalmap)", "limestone_normal(v_world_tbn[2], v_world_position)")
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


def apply_standalone_terrain_materials(kit: dict, render_root) -> None:
    """绑定独立三层草地/林下/干草 PBR 贴图，并升级地表、远山与沥青着色器。"""
    terrain_dir = resource_root() / "assets/game/expressway/terrain"
    kit["ground"] = source_texture(terrain_dir / "pasture-albedo.png", color=True)
    kit["rock"] = source_texture(resource_root() / "assets/game/expressway/strata-albedo.png", color=True)

    render_root.setShaderInput("local_ground_meadow", kit["ground"])
    render_root.setShaderInput("local_ground_dry", source_texture(terrain_dir / "dry-albedo.png", color=True))
    render_root.setShaderInput("local_origin_y", 0.0)
    render_root.setShaderInput("city_lawn_phase", (0.0, 0.0))
    for layer in ("pasture", "forest"):
        for channel in ("normal", "gloss", "height", "albedo"):
            if layer == "pasture" and channel == "albedo":
                continue
            tex = source_texture(terrain_dir / f"{layer}-{channel}.png", color=channel == "albedo")
            render_root.setShaderInput(f"{layer}_{channel}", tex)
    for channel in ("normal", "gloss", "height"):
        render_root.setShaderInput(f"dry_{channel}", source_texture(terrain_dir / f"dry-{channel}.png"))

    terrain = kit["route-terrain-shader"]
    frag = terrain.getText(Shader.STFragment)
    start = frag.index("uniform sampler2D expressway_rock;")
    end = frag.index("\n}\n", start) + 3
    frag = frag[:start] + TERRAIN_MATERIAL + frag[end:]
    frag = frag.replace("p3d_Material.roughness * metal_rough.g", "terrain_roughness()")
    frag = frag.replace(
        "vec3 ibl_f = fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness);",
        "vec3 ibl_f = mix(spec_color, "
        "fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness), .08);",
    )
    frag = frag.replace("ibl_f * env_brdf.x + env_brdf.y", "ibl_f * env_brdf.x + env_brdf.y*.08")
    frag = frag.replace("normalize(v_view_tbn * normalmap)", "terrain_normal(v_view_tbn[2],v_view_position)")
    frag = frag.replace("normalize(v_world_tbn * normalmap)", "terrain_normal(v_world_tbn[2],v_world_position)")
    kit["route-terrain-shader"] = Shader.make(Shader.SLGLSL, terrain.getText(Shader.STVertex), frag)

    mountain = kit["mountain-shader"]
    m_frag = mountain.getText(Shader.STFragment)
    m_start = m_frag.index("uniform sampler2D expressway_rock;")
    m_end = m_frag.index("\n}\n", m_start) + 3
    m_frag = m_frag[:m_start] + MOUNTAIN_MATERIAL + m_frag[m_end:]
    kit["mountain-shader"] = Shader.make(Shader.SLGLSL, mountain.getText(Shader.STVertex), m_frag)

    # 沥青压暗至写实深炭灰，保留车道轮迹与路肩微尘
    asphalt = kit["road-asphalt-shader"]
    a_frag = asphalt.getText(Shader.STFragment).replace(
        "return vec4(base,1.0);",
        "return vec4(base*.42,1.0);",
    )
    kit["road-asphalt-shader"] = Shader.make(Shader.SLGLSL, asphalt.getText(Shader.STVertex), a_frag)


def sun_color(intensity: float = DAYLIGHT_SUN_SCALE) -> tuple[float, float, float, float]:
    luminance = sum(v * w for v, w in zip(_SUN_RGB, (0.2126, 0.7152, 0.0722), strict=True))
    scale = (_SUN_LUX / (10000.0 * luminance)) * intensity
    return (_SUN_RGB[0] * scale, _SUN_RGB[1] * scale, _SUN_RGB[2] * scale, 1.0)


def landscape_lighting(scene, scale: float = DAYLIGHT_SH_SCALE) -> None:
    """晴空间接光缩放并与低常量环境灯配合，保留冷暖阴影对比。"""
    source = scene.expressway_kit["daylight-environment"].sh_coefficients
    coefficients = PTALVecBase3f.emptyArray(9)
    for i in range(9):
        coefficients[i] = source[i] * scale
    scene.render.setShaderInput("sh_coeffs", coefficients)
    scene.ambient_path.node().setColor((0.012, 0.018, 0.026, 1.0))


def update_daylight_sun(scene, position) -> None:
    """高速晴空太阳：对齐 CC0 天空太阳方向、前置 45m 阴影中心并锁定光平面纹素。"""
    metadata = scene.expressway_kit["daylight-metadata"]
    sx, sy, sz = metadata["directional_sun"]
    direction = Vec3(-sx, -sy, -sz)
    offset = -direction * 360.0
    sun = scene.sun_path
    sun.setPos(offset)
    sun.lookAt(0, 0, 0)
    inverse = sun.getQuat().conjugate()
    origin = float(scene.base.session.render_origin())
    current_origin = scene.render.getShaderInput("local_origin_y")
    if current_origin.getValueType() == current_origin.MInvalid or current_origin.getVector().x != origin:
        scene.render.setShaderInput("local_origin_y", origin)
    chase = scene.base.chase_camera
    heading = math.radians(
        chase.heading if chase.position is not None else scene.base.session.current.player.heading
    )
    center = position + Vec3(-math.sin(heading), math.cos(heading), 0) * CANOPY_SHADOW_LEAD
    light_position = inverse.xform(center + offset + Vec3(0, origin, 0))
    lens, resolution = sun.node().getLens(), sun.node().getShadowBufferSize()
    for axis, step in ((0, lens.getFilmSize().x / resolution.x), (2, lens.getFilmSize().y / resolution.y)):
        light_position[axis] = round(light_position[axis] / step) * step
    sun.setPos(sun.getQuat().xform(light_position) - Vec3(0, origin, 0))
    color = sun_color()
    sun.node().setColor(color)
    scene.rail_sun_path.node().setColor(color)
    scene.rail_sun_path.setTransform(sun.getTransform())


def cutout_shadows(scene) -> None:
    """配置 4K 叶片裁切太阳阴影，并将主相机与纯阴影代理分离。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {"USE_330": True}
    vertex = _load_shader_str("shadow.vert", defines.copy())
    fragment = _load_shader_str("shadow.frag", defines.copy()).replace(
        "#ifdef USE_330\n    o_color = base_color;",
        "if (base_color.a < .25) discard;\n#ifdef USE_330\n    o_color = base_color;",
    )
    light = scene.sun_path.node()
    light.setShadowCaster(True, 4096, 4096)
    light.getLens().setFilmSize(CANOPY_SHADOW_SPAN, CANOPY_SHADOW_SPAN)
    light.getLens().setNearFar(20.0, 780.0)
    scene.render.setShaderInput("global_shadow_bias", 0.0003)
    light.setCameraMask(SHADOW_MASK)
    light.setInitialState(
        light.getInitialState().setAttrib(ShaderAttrib.make(Shader.make(Shader.SLGLSL, vertex, fragment)), 10)
    )
    camera = scene.base.cam.node()
    camera.setCameraMask(camera.getCameraMask() & ~SHADOW_MASK)
