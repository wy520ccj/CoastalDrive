// 插入已有PBR片元程序：同一面上混合草/土/岩，无透明叠面。
uniform sampler2D expressway_rock;
vec4 expressway_albedo() {
    vec2 p = v_texcoord;
    vec3 grass = texture2D(p3d_TextureBaseColor, p / 3.0).rgb;
    vec3 rock = texture2D(expressway_rock, vec2(p.y / 5.0, (v_world_position.z + p.x*.08)/3.0)).rgb;
    float boundary = clamp(v_color.a + (rock.r-.45)*.08, 0.0, 1.0);
    vec3 tint = clamp(v_color.rgb * vec3(3.2,2.7,4.8), .35, 1.0);
    vec3 base = mix(grass * tint, rock * vec3(.69,.66,.60), boundary);
    float verge = 1.0-smoothstep(9.5,13.5,abs(p.x));
    vec3 soil = rock * vec3(.43,.38,.25);
    base = mix(base, soil, verge*.65);
    float shore = smoothstep(35.0,50.0,p.x) * (1.0-smoothstep(-2.7,-1.1,v_world_position.z));
    base = mix(base,rock*vec3(.67,.61,.44),shore);
    return vec4(base,1.0);
}
