// 从米制立面UV求切线；小尺度灰泥保留几何法线和清楚的建筑转角。
uniform sampler2D city_normal;
uniform sampler2D city_roughness;
uniform vec3 city_albedo_scale;
uniform float city_tex_scale;
uniform float city_color_variation;
uniform float city_normal_strength;
vec4 city_plaster_color() {
    vec3 detail = texture2D(p3d_TextureBaseColor, v_texcoord*city_tex_scale).rgb * city_albedo_scale;
    return vec4(mix(vec3(1.0), detail, city_color_variation), 1.0);
}
vec3 city_surface_normal(vec3 geometric_normal, vec3 position) {
    vec3 n = normalize(geometric_normal);
    vec3 dx = dFdx(position), dy = dFdy(position);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 py = cross(dy, n), px = cross(n, dx);
    vec3 tangent = py * ux.x + px * uy.x;
    vec3 bitangent = py * ux.y + px * uy.y;
    float magnitude = max(dot(tangent, tangent), dot(bitangent, bitangent));
    if (magnitude < 1e-16) return n;
    vec3 detail = texture2D(city_normal, v_texcoord*city_tex_scale).rgb * 2.0 - 1.0;
    detail.xy *= city_normal_strength;
    detail.z *= sqrt(magnitude);
    return normalize(mat3(tangent, bitangent, n) * detail);
}
