#version 330
uniform sampler2D p3d_Texture0;
in vec2 uv;
out vec4 fragColor;
void main() {
    // 原图地平线在距底部 38% 处，映射到球体赤道。
    vec2 sample_uv = vec2(uv.x, clamp(0.38 + (uv.y - 0.5) * 2.0, 0.0, 1.0));
    vec3 sky = texture(p3d_Texture0, sample_uv).rgb;
    // 天空是定稿色稿：逆 simplepbr 0.13 的 filmic 曲线后进入统一后处理。
    // 只校正天空，不改变车辆、场景或 UI 的曝光。
    sky = clamp(sky, 0.01, 0.96);
    vec3 a = 6.2 * (sky - 1.0);
    vec3 b = 1.7 * sky - 0.5;
    vec3 hdr = (-b - sqrt(b * b - 4.0 * a * 0.06 * sky)) / (2.0 * a) + 0.004;
    fragColor = vec4(hdr, 1.0);
}
