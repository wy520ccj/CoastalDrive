#version 330
uniform float sea_time;
uniform sampler2D shore_distance;
in vec3 world;
out vec4 fragColor;
void main() {
    vec2 p = world.xy;
    float swell = sin(p.x * 0.10 + p.y * 0.035 + sea_time * 0.27);
    float wave = sin(p.y * 1.6 + sin(p.x * 0.21 + sea_time * 0.18) * 2.0 + sea_time * 0.55);
    float breaks = smoothstep(0.55, 0.99, sin(p.x * 0.48 + p.y * 0.13));
    // 超过像素采样密度的高频波纹逐渐淡出，减少远海闪烁。
    float footprint = length(fwidth(p));
    float glint = pow(max(wave, 0.0), 18.0) * breaks * (1.0 - smoothstep(0.3, 1.3, footprint));
    vec2 shore_uv = (p + 256.0) / 640.0;
    float coast = texture(shore_distance, shore_uv).r * 40.0;
    if (any(lessThan(shore_uv, vec2(0.0))) || any(greaterThan(shore_uv, vec2(1.0)))) coast = 40.0;
    vec3 blue = mix(vec3(0.055, 0.42, 0.35), vec3(0.014, 0.20, 0.32), smoothstep(1.0, 34.0, coast));
    float wash = .35 * sin(p.x*.67+p.y*.43+sea_time*.7);
    float foam = (1.0-smoothstep(.65, 2.3, coast+wash)) * (.65+.35*sin(p.x*1.9+p.y*1.7));
    blue = mix(blue, vec3(.72,.80,.66), foam*.66);
    blue += swell * vec3(0.007, 0.021, 0.026) * (1.0 - smoothstep(1.5, 9.0, footprint));
    blue += glint * vec3(0.08, 0.12, 0.12);
    fragColor = vec4(blue, 1.0);
}
