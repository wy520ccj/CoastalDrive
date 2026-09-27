#version 330
uniform float sea_time;
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
    float distance = length(p);
    vec3 blue = mix(vec3(0.022, 0.32, 0.43), vec3(0.025, 0.19, 0.36), smoothstep(160.0, 550.0, distance));
    blue += swell * vec3(0.007, 0.021, 0.026) * (1.0 - smoothstep(1.5, 9.0, footprint));
    blue += glint * vec3(0.08, 0.12, 0.12);
    fragColor = vec4(blue, 1.0);
}
