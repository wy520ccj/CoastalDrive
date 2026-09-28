#version 330
uniform float sea_time;
uniform float origin_y;
uniform sampler2D shore_profile;
in vec3 world;
out vec4 fragColor;
void main() {
    vec2 p = world.xy + vec2(0.0, origin_y);
    float slice = smoothstep(0.0, 65.0, p.y) * (1.0-smoothstep(735.0, 800.0, p.y));
    float coast_x = texture(shore_profile, vec2(clamp(p.y/800.0,0.0,1.0),0.5)).r * 160.0;
    float coast = max(0.0, p.x-coast_x);
    float footprint = length(fwidth(p));
    float swell = sin(p.y*.075+p.x*.035+sea_time*.23);
    float waves = sin(p.x*.38+sin(p.y*.075)*2.0-sea_time*.5);
    float ripple = pow(max(0.0,waves),12.0)*(1.0-smoothstep(.5,2.0,footprint));
    vec3 blue = mix(vec3(.043,.38,.33), vec3(.014,.20,.31), smoothstep(0.0,24.0,coast));
    float wash = .25*sin(p.y*.62-sea_time*.7);
    float foam = (1.0-smoothstep(.3,1.7,coast+wash))*slice;
    blue = mix(blue,vec3(.56,.68,.56),foam*.45);
    blue += swell*vec3(.003,.011,.014)+ripple*vec3(.024,.038,.033);
    fragColor = vec4(mix(vec3(.025,.24,.36),blue,slice),1.0);
}
