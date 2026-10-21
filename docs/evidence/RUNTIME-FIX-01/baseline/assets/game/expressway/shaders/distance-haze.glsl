// 天空地平线的辐亮度用于空气透视；远端轮廓先渐隐再卸载。
uniform sampler2D expressway_sky;
uniform mat4 expressway_sky_inverse;

void expressway_dither(float coverage) {
    ivec2 cell = ivec2(gl_FragCoord.xy) & ivec2(3);
    int bayer[16] = int[16](0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5);
    if (coverage < (float(bayer[cell.x + cell.y * 4]) + 0.5) / 16.0) discard;
}

void expressway_far_clip(vec3 world_position) {
    float distance = length(world_position - camera_world_position);
    expressway_dither(1.0 - smoothstep(850.0, 1050.0, distance));
}

vec3 expressway_haze(vec3 color, vec3 world_position) {
    vec3 direction = world_position - camera_world_position;
    float distance = length(direction);
    float haze = smoothstep(350.0, 850.0, distance);
    if (haze <= 0.0) return color;
    vec3 sky_direction = normalize((expressway_sky_inverse * vec4(direction, 0.0)).xyz);
    vec2 uv = vec2(atan(sky_direction.y, sky_direction.x) / 6.28318530718, 0.5);
    vec3 sky = clamp(texture(expressway_sky, uv).rgb, 0.01, 0.96);
    vec3 a = 6.2 * (sky - 1.0);
    vec3 b = 1.7 * sky - 0.5;
    vec3 radiance = (-b - sqrt(b*b - 4.0*a*0.06*sky))/(2.0*a) + 0.004;
    return mix(color, radiance, haze);
}
