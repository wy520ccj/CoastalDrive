#version 330
uniform sampler2D p3d_Texture0;
uniform vec3 coastal_sky_tint;
in vec2 uv;
out vec4 fragColor;
void main() {
    // 8K原始云层保留角度比例，色平衡与离线反射一致。
    fragColor=vec4(texture(p3d_Texture0,uv).rgb*coastal_sky_tint,1.);
}
