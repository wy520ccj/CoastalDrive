// 山体保留PBR光照，坡度混合岩壁与林地，细节随屏幕覆盖率过滤。
uniform sampler2D expressway_rock;
vec4 expressway_albedo() {
    vec2 p = v_texcoord;
    vec3 grass = texture2D(p3d_TextureBaseColor, p / 12.0).rgb;
    vec3 stone = texture2D(expressway_rock, vec2(p.y/12.0,v_world_position.z/9.0+p.x/36.0)).rgb;
    vec3 forest = grass * v_color.rgb * vec3(1.6,1.8,2.0);
    vec3 rock = stone * vec3(.49,.48,.43);
    vec3 base = mix(forest,rock,clamp(v_color.a+(stone.r-.5)*.25,0.0,1.0));
    return vec4(base,1.0);
}
