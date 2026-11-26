// 天空地平线的辐亮度用于空气透视；远端先完全融入天空再整体裁剪，不引入棋盘格抖动。
uniform sampler2D expressway_sky;
uniform mat4 expressway_sky_inverse;
uniform vec3 expressway_sky_tint;

void expressway_far_clip(vec3 world_position) {
    if (length(world_position - camera_world_position) > 1050.0) discard;
}

vec3 expressway_sky_radiance(vec3 direction) {
    vec3 sky_direction = normalize((expressway_sky_inverse * vec4(direction, 0.0)).xyz);
    // 与天空球相同的经纬映射；高处远景不能拿地平线颜色覆盖云层。
    vec2 uv = vec2(atan(sky_direction.y, sky_direction.x) / 6.28318530718,
                   0.5 + asin(clamp(sky_direction.z, -1.0, 1.0)) / 3.14159265359);
    return texture(expressway_sky, uv).rgb * expressway_sky_tint;
}

vec3 expressway_haze(vec3 color, vec3 world_position) {
    vec3 direction = world_position - camera_world_position;
    float distance = length(direction);
    float haze = smoothstep(340.0, 920.0, distance);
    if (haze <= 0.0) return color;
    return mix(color, expressway_sky_radiance(direction), haze);
}
