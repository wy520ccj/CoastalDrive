#version 330
in vec2 shore_uv;
in vec3 v_world_position;
uniform vec3 camera_world_position;
out vec4 fragColor;
void main() {
    vec2 p = shore_uv;
    float detail = 1.0-smoothstep(.5, 2.5, length(fwidth(p)));
    // 周期整除600m，局部UV跨segment保持连续，远里程不损失精度。
    float swell = sin(p.y*.06283185+p.x*.035);
    float ripple = pow(max(0.0,sin(p.x*.38+sin(p.y*.1256637)*2.0)),12.0)*detail;
    vec3 blue = mix(vec3(.035,.31,.30), vec3(.025,.19,.27), smoothstep(65.0,180.0,p.x));
    blue += swell*vec3(.004,.012,.017)+ripple*vec3(.033,.05,.052);
    fragColor = vec4(expressway_haze(blue, v_world_position),1.0);
}
