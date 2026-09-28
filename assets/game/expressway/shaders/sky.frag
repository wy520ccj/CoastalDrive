#version 330
uniform sampler2D p3d_Texture0;
in vec2 uv;
out vec4 fragColor;
void main() {
    // 原创晴空图的赤道对应地平线；保留天空色稿通过既有全局色调映射。
    vec3 sky = clamp(texture(p3d_Texture0, uv).rgb, 0.01, 0.96);
    vec3 a = 6.2 * (sky - 1.0);
    vec3 b = 1.7 * sky - 0.5;
    fragColor = vec4((-b - sqrt(b*b - 4.0*a*0.06*sky))/(2.0*a) + 0.004, 1.0);
}
