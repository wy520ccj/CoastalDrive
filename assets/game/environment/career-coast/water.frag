#version 330
#define CAREER_COAST
in vec2 shore_uv;
in vec3 v_world_position;
uniform vec3 camera_world_position;
uniform float sea_time;
out vec4 fragColor;
void main() {
    vec2 p = shore_uv;
    float detail = 1.0-smoothstep(.5, 2.5, length(fwidth(p)));
    // 周期整除600m，局部UV跨segment保持连续，远里程不损失精度。
    float swell = sin(p.y*.06283185+p.x*.035+sea_time*.23);
    float ripple = pow(max(0.0,sin(p.x*.38+sin(p.y*.1256637)*2.0-sea_time*.5)),12.0)*detail;
    vec3 blue = mix(vec3(.035,.31,.30), vec3(.025,.19,.27), smoothstep(65.0,180.0,p.x));
    blue += swell*vec3(.004,.012,.017)+ripple*vec3(.033,.05,.052);
#ifdef CAREER_COAST
    // 只复用已有HDR，沿海生涯不新增屏幕反射或动态探针。
    vec3 normal = normalize(vec3(.018*sin(p.x*.035+p.y*.06283185+sea_time*.23),
                                .012*cos(p.x*.38+p.y*.1256637-sea_time*.5),1.));
    vec3 view = normalize(camera_world_position-v_world_position);
    vec3 direction = normalize((expressway_sky_inverse*vec4(reflect(-view,normal),0.)).xyz);
    vec2 reflection_uv = vec2(atan(direction.y,direction.x)/6.28318530718,
                             .5+asin(clamp(direction.z,-1.,1.))/3.14159265359);
    vec3 reflection = textureLod(expressway_sky,reflection_uv,3.).rgb*expressway_sky_tint;
    float fresnel = .02+.63*pow(1.-max(0.,dot(normal,view)),5.);
    blue = mix(blue,reflection,fresnel);
#endif
    float water_haze = smoothstep(700.,1450.,length(v_world_position-camera_world_position));
    fragColor = vec4(mix(blue,expressway_haze(blue, v_world_position),water_haze),1.0);
}
