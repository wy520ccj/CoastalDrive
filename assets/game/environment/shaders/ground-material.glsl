// 同源实拍细节按2.5米铺设，原顶点色保留草/土宏观分区。
uniform sampler2D coastal_ground_albedo;
uniform sampler2D coastal_ground_normals;
uniform sampler2D coastal_ground_roughness;

vec2 coastal_ground_uv() {
    return v_world_position.xy / 2.5;
}

vec4 coastal_ground_color() {
    vec3 detail = texture(coastal_ground_albedo, coastal_ground_uv()).rgb;
    vec3 mean_albedo = vec3(0.32378886, 0.23865014, 0.10857235);
    return vec4(v_color.rgb * detail / mean_albedo, 1.0);
}

vec3 coastal_ground_normal(vec3 geometric_normal, vec3 position, vec3 detail) {
    vec3 n = normalize(geometric_normal);
    vec3 dx = dFdx(position), dy = dFdy(position);
    vec2 ux = dFdx(coastal_ground_uv()), uy = dFdy(coastal_ground_uv());
    vec3 py = cross(dy, n), px = cross(n, dx);
    vec3 tangent = py * ux.x + px * uy.x;
    vec3 bitangent = py * ux.y + px * uy.y;
    float magnitude = max(dot(tangent, tangent), dot(bitangent, bitangent));
    detail.xy *= 0.55;
    detail.z *= sqrt(max(magnitude, 1e-16));
    return normalize(mat3(tangent, bitangent, n) * detail);
}
