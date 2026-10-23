#version 330
uniform sampler2D p3d_Texture0;
in vec2 uv;
out vec4 fragColor;
void main() {
    // 线性实拍HDR与世界照明经过同一全局色调映射。
    fragColor = vec4(texture(p3d_Texture0, uv).rgb, 1.0);
}
